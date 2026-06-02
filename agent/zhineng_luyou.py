"""
智能多模型路由引擎 v2 — 能力感知多后端路由。

Hermes-Agent-CN 核心组件，根据任务需求自动在 本地服务(Ollama/LM Studio/llama.cpp/FastLLM...)
→ 云端API(DeepSeek/MiniMax/Kimi/Zai) → 嵌入式CPU 之间选择最佳模型。

路由策略:
    1. 分析任务需求 (TaskRequirements): 能力分、是否需要视觉、是否需要工具调用
    2. 从所有后端收集可用模型, 按能力分过滤
    3. 本地优先 (满足能力阈值的前提下选最强的本地模型)
    4. 本地不可用/能力不足 → 云端
    5. 云端不可用 → 嵌入式兜底
    6. 熔断机制: 连续失败 2 次的模型临时屏蔽 5 分钟

使用方式:
    from agent.zhineng_luyou import SmartRouter
    router = SmartRouter(config)
    result = router.route(user_message)
    # result.provider, result.model, result.tier, result.reason
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent.model_detection import infer_vision_support, is_embedding_model

logger = logging.getLogger(__name__)


# -- 常量 --------------------------------------------------------------------

OLLAMA_DEFAULT_HOST = "localhost"
OLLAMA_DEFAULT_PORT = 11434
LOCAL_HEALTH_TIMEOUT = 3.0           # 后端探测超时 (秒)
LOCAL_OFFLINE_COOLDOWN = 300          # 离线标记冷却 (秒, =5分钟)
CACHE_TTL = 60                        # 路由决策缓存时间 (秒)
PROBE_COOLDOWN = 60                   # 后端探测冷却 (秒)
CIRCUIT_BREAKER_THRESHOLD = 2         # 连续失败次数触发熔断
CIRCUIT_BREAKER_COOLDOWN = 300        # 熔断冷却时间 (秒, =5分钟)

# 嵌入式模型优先级
EMBEDDED_MODEL_ORDER = ["qwen-coder-1.5b", "qwen-0.5b"]

# 已知后端默认端口映射 (用于 auto-detect 时尝试)
DEFAULT_BACKEND_PORTS = {
    "ollama": 11434,
    "lm-studio": 1234,
    "llama-cpp": 8080,
    "fastllm": 8088,
}

# 路由日志 (Phase C)
ROUTE_LOG_MAX_LINES = 5000           # 路由日志最大行数 (超过自动截断)
ROUTE_LOG_TRUNCATE_TO = 3000         # 截断后保留行数

# -- 云端模型提供商数据库 (CN) -----------------------------------------------

# (provider_id, default_model, [env_var_names], priority)
# priority 越小优先级越高
CN_CLOUD_PROVIDERS: List[Tuple[str, str, List[str], int]] = [
    ("deepseek", "deepseek-chat", ["DEEPSEEK_API_KEY"], 10),
    ("alibaba", "qwen-plus", ["ALIBABA_API_KEY", "DASHSCOPE_API_KEY"], 20),
    ("minimax", "minimax-m2", ["MINIMAX_API_KEY", "MINIMAX_CN_API_KEY"], 30),
    ("zai", "glm-5.1", ["GLM_API_KEY", "ZHIPU_API_KEY"], 40),
    ("stepfun", "step-2-16k", ["STEPFUN_API_KEY"], 50),
    ("kimi-for-coding", "kimi-k2", ["KIMI_API_KEY"], 60),
    ("xiaomi", "mi-1.5b", ["XIAOMI_API_KEY"], 70),
    ("volcengine", "deepseek-r1", ["ARK_API_KEY"], 80),
]

# 云端熔断参数
CLOUD_FAILOVER_THRESHOLD = 2          # 连续失败次数触发熔断
CLOUD_FAILOVER_COOLDOWN = 120         # 熔断冷却时间 (秒, =2分钟)

# 默认成本估算参数
COST_AVG_INPUT_TOKENS = 1500          # 平均每次请求输入 token 数 (用于估算)
COST_AVG_OUTPUT_TOKENS = 500          # 平均每次请求输出 token 数 (用于估算)

# -- 国产模型成本数据库 (CN, 单位: ¥/1M tokens) --------------------------------
#
# 格式: "provider:model" -> (input_price, output_price, context_window, supports_vision)
# input_price: 每 1M 输入 tokens 价格 (¥)
# output_price: 每 1M 输出 tokens 价格 (¥)
# context_window: 最大上下文窗口大小
# supports_vision: 是否支持视觉输入
#
# 价格来源: 各厂商官网公开定价 (2025-07 快照)
CN_MODEL_COSTS: Dict[str, Tuple[float, float, int, bool]] = {
    # ---- DeepSeek (https://api-docs.deepseek.com/quick_start/pricing) ----
    "deepseek:deepseek-chat":       (1.0,   2.0,   65536,   False),
    "deepseek:deepseek-reasoner":   (4.0,   16.0,  65536,   False),

    # ---- 阿里百炼 (https://help.aliyun.com/zh/model-studio/getting-started/models) ----
    "alibaba:qwen-turbo":           (0.3,   0.6,   1048576, True),
    "alibaba:qwen-plus":            (0.8,   2.0,   131072,  True),
    "alibaba:qwen-max":             (20.0,  60.0,  32768,   True),
    "alibaba:qwen-long":            (0.5,   2.0,   1048576, True),
    "alibaba:qwq-plus":             (1.0,   2.0,   131072,  False),

    # ---- MiniMax (https://platform.minimaxi.com/document) ----
    "minimax:minimax-m2":           (2.0,   8.0,   131072,  True),
    "minimax:minimax-t1":           (2.0,   8.0,   131072,  False),

    # ---- 智谱 (https://open.bigmodel.cn/pricing) ----
    "zai:glm-4-flash":              (0.1,   0.1,   131072,  True),
    "zai:glm-4-air":                (1.0,   1.0,   131072,  True),
    "zai:glm-4-plus":               (2.0,   8.0,   131072,  True),
    "zai:glm-5.1":                  (2.0,   8.0,   131072,  True),

    # ---- 阶跃星辰 (https://platform.stepfun.com/docs/overview) ----
    "stepfun:step-1-8k":            (5.0,   5.0,   8192,    False),
    "stepfun:step-2-16k":           (5.0,   15.0,  16384,   False),

    # ---- Kimi / 月之暗面 ----
    "kimi-for-coding:kimi-k2":      (2.0,   8.0,   131072,  True),
    "kimi-for-coding:kimi-k1.5":    (2.0,   8.0,   131072,  True),

    # ---- 小米 ----
    "xiaomi:mi-1.5b":               (0.4,   0.8,   4096,    False),

    # ---- 火山引擎 (https://www.volcengine.com/docs/82379) ----
    "volcengine:deepseek-r1":       (4.0,   16.0,  65536,   False),
    "volcengine:deepseek-v3":       (2.0,   8.0,   65536,   False),
    "volcengine:doubao-pro":        (5.0,   9.0,   131072,  False),
}

# 成本路由策略枚举值
COST_STRATEGY_OFF = "off"          # 按优先级选 (默认行为, M1 兼容)
COST_STRATEGY_BALANCED = "balanced"  # 能力足够的前提下选最便宜的
COST_STRATEGY_STRICT = "strict"    # 始终选最便宜的
COST_STRATEGY_QUALITY = "quality"  # 复杂任务选能力更强, 简单任务选便宜
VALID_COST_STRATEGIES = (COST_STRATEGY_OFF, COST_STRATEGY_BALANCED,
                         COST_STRATEGY_STRICT, COST_STRATEGY_QUALITY)


# -- 后端类型枚举 ------------------------------------------------------------

class BackendKind(Enum):
    """后端类型"""
    OLLAMA = "ollama"
    LM_STUDIO = "lm-studio"
    LLAMA_CPP = "llama-cpp"
    FASTLLM = "fastllm"
    OPENAI_COMPATIBLE = "openai-compatible"  # 通用 OpenAI 兼容后端


# -- 数据类型 ----------------------------------------------------------------

class ModelTier(Enum):
    """模型层级。"""
    LOCAL = "local"         # Tier 1: 本地模型 (所有后端)
    CLOUD = "cloud"         # Tier 2: 国产云端 API
    EMBEDDED = "embedded"   # Tier 3: 嵌入式 CPU 推理
    NONE = "none"           # 无可用的模型

    # 向后兼容
    OLLAMA = "local"        # 废弃，等同于 LOCAL


class TaskComplexity(Enum):
    """任务复杂度 (向后兼容保留, 新代码使用 TaskRequirements)。"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class LocalModel:
    """本地模型描述。"""
    name: str                           # 模型名称, 如 "qwen3-vl:4b"
    backend: str                        # 后端名称, 如 "ollama"
    base_url: str                       # 后端 base_url
    backend_priority: int = 99          # 后端优先级 (越小越优先)
    params_b: int = 0                   # 参数量 (B)
    context_length: int = 8192          # 上下文长度
    supports_vision: bool = False       # 是否支持视觉
    supports_tools: bool = True         # 是否支持工具调用
    estimated_capability: int = 2       # 能力分 (0-10)
    raw_details: Optional[Dict] = field(default_factory=dict)  # 原始 API 数据

    @property
    def provider_model(self) -> str:
        """返回 "backend:name" 格式 (用于 Provider 层消费)。"""
        return f"{self.backend}:{self.name}"


@dataclass
class TaskRequirements:
    """任务对模型能力的需求量化。

    min_capability: 最低能力分要求 (0-10)
        - 0-2: 简单问答、闲聊、翻译
        - 3-4: 代码片段、单文件操作
        - 5-6: 代码审查、短文档
        - 7-8: 架构设计、重构
        - 9-10: 多文件协调、复杂推理
    """
    min_capability: int
    needs_vision: bool = False
    needs_tools: bool = False
    min_context: int = 8192
    prefer_fast: bool = False  # 简单任务优先低延迟本地模型

    @classmethod
    def from_complexity(cls, complexity: TaskComplexity) -> "TaskRequirements":
        """从旧 TaskComplexity 转换 (向后兼容)。"""
        mapping = {
            TaskComplexity.SIMPLE: cls(min_capability=2, prefer_fast=True),
            TaskComplexity.MEDIUM: cls(min_capability=5),
            TaskComplexity.COMPLEX: cls(min_capability=8),
        }
        return mapping.get(complexity, cls(min_capability=5))


@dataclass
class RouteResult:
    """路由决策结果。"""
    provider: str                       # Provider ID
    model: str                          # Model ID
    tier: ModelTier                     # 使用的层级
    reason: str                         # 决策原因 (中文)
    backend: str = ""                   # 后端名称 (本地模型时有效)
    timestamp: float = field(default_factory=time.time)

    @property
    def provider_model(self) -> str:
        """返回 "provider:model" 格式字符串。"""
        return f"{self.provider}:{self.model}"

    def __bool__(self) -> bool:
        """是否为有效路由结果。"""
        return self.tier != ModelTier.NONE


@dataclass
class RoutingRule:
    """用户定义的规则路由条目。

    对应 YAML 配置中的 model_routing.rules 条目:
        rules:
          - name: vision
            match:
              has_image: true
            model: "qwen3-vl:8b"
          - name: coding
            match:
              keywords: ["写代码", "函数", "class"]
              threshold: 2
            model: "deepseek-coder"
    """
    name: str                                  # 规则名称 (用于日志)
    model: str                                 # 目标模型名
    match: Optional[Dict[str, Any]] = None     # 匹配条件
    provider: str = ""                         # 目标 provider (可选)
    priority: int = 0                          # 优先级 (保留字段)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingRule":
        """从字典创建 RoutingRule。"""
        return cls(
            name=d.get("name", "(unnamed)"),
            model=d.get("model", ""),
            match=d.get("match") or {},
            provider=d.get("provider", ""),
            priority=d.get("priority", 0),
        )


# -- 复杂度判断 (保留向后兼容) ------------------------------------------------

SIMPLE_KEYWORDS = [
    "你好", "hi", "hello", "谢谢", "再见", "翻译",
    "thanks", "bye",
    "格式", "format", "缩进", "indent",
    "天气", "weather", "时间", "time", "日期", "date",
]

COMPLEX_KEYWORDS = [
    "架构", "architecture", "设计", "design", "方案",
    "重构", "refactor", "refactoring",
    "多文件", "multi-file", "整个项目", "project",
    "调试", "debug", "性能", "performance", "优化", "optimize",
    "部署", "deploy", "ci/cd", "pipeline",
    "安全", "security", "审计", "audit",
    "数据库", "database", "迁移", "migration",
]


def analyze_complexity(message: str) -> TaskComplexity:
    """分析用户消息的复杂度 (向后兼容保留)。

    新代码请使用 SmartRouter._analyze_task() 获取 TaskRequirements。
    """
    text = message.lower().strip()
    length = len(message)

    complex_score = sum(1 for kw in COMPLEX_KEYWORDS if kw.lower() in text)
    if complex_score >= 1 or length > 500:
        return TaskComplexity.COMPLEX

    simple_score = sum(1 for kw in SIMPLE_KEYWORDS if kw.lower() in text)
    if simple_score >= 1 or length < 50:
        return TaskComplexity.SIMPLE

    return TaskComplexity.MEDIUM


# -- 参数量推断 ----------------------------------------------------------------

def _parse_param_count(model_name: str) -> int:
    """从模型名称推断参数量 (单位: B)。

    支持格式:
        "qwen3-vl:4b" → 4
        "deepseek-r1:7b" → 7
        "qwen3.5-2b-coder:latest" → 2
        "llama3.2:3b-instruct-fp16" → 3
        "phi-3-mini-4k-instruct" → 3
        "glm-ocr:latest" → 0 (无法推断)
    """
    # 匹配 :数字b 或 -数字b 模式
    m = re.search(r'[: -](\d+)b', model_name.lower())
    if m:
        return int(m.group(1))

    # 匹配数字后缀 (如 model-3)
    m = re.search(r'[-_ ](\d+)[-_ ]?([vV]\d+)?$', model_name)
    if m:
        val = int(m.group(1))
        # 过滤数字过小的误匹配 (如 "model-2" 中 2 可能是版本号)
        if 1 <= val <= 500:
            return val

    return 0


def _estimate_params_from_api(model_info: Dict[str, Any]) -> int:
    """从模型 API 信息中估算参数量 (优先使用 model_info)。"""
    # Ollama /api/show 返回 "parameters" 字段
    details = model_info.get("details", {})
    params_str = details.get("parameter_size", "")
    if params_str:
        # "4.0B" → 4
        m = re.match(r'([\d.]+)B', str(params_str), re.IGNORECASE)
        if m:
            return int(float(m.group(1)))

    # 备选: 从名称解析
    name = model_info.get("model", model_info.get("name", ""))
    return _parse_param_count(name)


def _infer_vision_support(model_name: str) -> bool:
    """从模型名称推断是否支持视觉（复用 model_detection 的共享逻辑）。"""
    return infer_vision_support(model_name)


def _estimate_capability(params_b: int, context_length: int,
                         supports_vision: bool = False,
                         supports_tools: bool = True) -> int:
    """根据模型参数估算能力分 (0-10)。

    score ≈ log2(params_b) + context_bonus + feature_bonus
    最终 clamp 到 0-10。
    """
    if params_b <= 0:
        return 2 if supports_vision else 1

    import math
    # 基础分: 参数量对数
    base = min(math.log2(max(params_b, 1)) * 2.0, 8.0)

    # 上下文加分
    if context_length >= 65536:
        base += 1.5
    elif context_length >= 32768:
        base += 1.0
    elif context_length >= 16384:
        base += 0.5

    # 特性加分
    if supports_vision:
        base += 0.5
    if supports_tools:
        base += 0.5

    return max(1, min(10, int(round(base))))


# -- 后端探测 ----------------------------------------------------------------

@dataclass
class _CacheEntry:
    """缓存条目。"""
    value: Any
    timestamp: float
    ttl: float


class BackendHub:
    """多后端统一管理中心。

    负责:
        1. 注册本地后端 (从 config.yaml 的 local_backends 段)
        2. 并发探测所有后端, 获取可用模型列表
        3. 构建统一模型编目 (ModelCatalog)
        4. 对每个模型估算能力分
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._model_cache: List[LocalModel] = []
        self._probe_timestamp: float = 0.0
        self._backend_status: Dict[str, Dict[str, Any]] = {}
        self._cache: Dict[str, _CacheEntry] = {}

    # -- 注册后端 ----------------------------------------------------------

    def get_registered_backends(self) -> List[Dict[str, Any]]:
        """获取所有注册的本地后端。

        来源: config.yaml → local_backends 段。
        如果未配置, 自动探测 Ollama (默认 localhost:11434)。
        """
        configured = self._config.get("local_backends", [])

        if not configured:
            # 没有显式配置, 退回传统 auto-detect
            return self._auto_detect_backends()

        return [
            {
                "name": entry.get("name", f"local-{i}"),
                "base_url": entry.get("base_url", "").rstrip("/"),
                "priority": entry.get("priority", i + 1),
                "kind": entry.get("kind", "openai-compatible"),
            }
            for i, entry in enumerate(configured)
            if entry.get("base_url")
        ]

    def _auto_detect_backends(self) -> List[Dict[str, Any]]:
        """自动探测常见本地后端 (回退兼容方案)。"""
        backends = []

        # Ollama 默认检测
        backends.append({
            "name": "ollama",
            "base_url": f"http://localhost:{OLLAMA_DEFAULT_PORT}/v1",
            "priority": 1,
            "kind": "ollama",
        })

        # 检测 LM Studio (端口 1234)
        backends.append({
            "name": "lm-studio",
            "base_url": "http://localhost:1234/v1",
            "priority": 2,
            "kind": "lm-studio",
        })

        # 检测 llama.cpp (端口 8080)
        backends.append({
            "name": "llama-cpp",
            "base_url": "http://localhost:8080/v1",
            "priority": 3,
            "kind": "llama-cpp",
        })

        # 检测 FastLLM (端口 8088)
        backends.append({
            "name": "fastllm",
            "base_url": "http://localhost:8088/v1",
            "priority": 4,
            "kind": "fastllm",
        })

        # 检测 vLLM (端口 8000)
        backends.append({
            "name": "vllm",
            "base_url": "http://localhost:8000/v1",
            "priority": 5,
            "kind": "openai-compatible",
        })

        # 检测 LocalAI (端口 8082)
        backends.append({
            "name": "localai",
            "base_url": "http://localhost:8082/v1",
            "priority": 6,
            "kind": "openai-compatible",
        })

        return backends

    # -- 探测 --------------------------------------------------------------

    def probe_all(self, force: bool = False) -> List[LocalModel]:
        """探测所有注册后端, 返回可用模型列表。

        缓存策略: PROBE_COOLDOWN 秒内返回缓存结果。
        """
        if not force and (time.time() - self._probe_timestamp) < PROBE_COOLDOWN:
            return self._model_cache

        all_models: List[LocalModel] = []
        self._backend_status = {}

        for backend_info in self.get_registered_backends():
            name = backend_info["name"]
            base_url = backend_info["base_url"]
            priority = backend_info["priority"]

            # 冷却期检查: 上次标记为离线的后端 PROBE_COOLDOWN 秒内不重试
            status_key = f"probe:{name}"
            cached = self._get_cached(status_key)
            if cached is False:
                self._backend_status[name] = {"online": False, "base_url": base_url, "error": "冷却中"}
                continue

            # 执行探测
            online, models_raw = self._probe_backend(base_url, name)
            self._backend_status[name] = {
                "online": online,
                "base_url": base_url,
                "model_count": len(models_raw),
            }

            if online and models_raw:
                for m in models_raw:
                    lm = self._build_local_model(m, name, base_url, priority)
                    if lm:
                        all_models.append(lm)
                logger.debug("后端 %s: 在线, %d 个模型", name, len(models_raw))
            else:
                logger.debug("后端 %s: 离线或无模型", name)
                # 标记离线, 冷却
                self._set_cache(status_key, False, ttl=PROBE_COOLDOWN)

        self._model_cache = all_models
        self._probe_timestamp = time.time()
        return all_models

    def get_all_models(self, force: bool = False) -> List[LocalModel]:
        """获取所有可用本地模型 (带缓存)。"""
        return self.probe_all(force=force)

    def get_best_for_task(self, req: TaskRequirements,
                          session_history: Optional[List] = None) -> Optional[LocalModel]:
        """从本地模型中选出最适合任务需求的一个。

        策略:
            1. 过滤: 能力分 >= min_capability
            2. 排序: 优先级 (backend_priority) ↑, 能力分 ↓ (在满足需求前提下选最强)
            3. 如果 prefer_fast: 在满足需求的模型中选择最小能力分 (最小延迟)
        """
        all_models = self.get_all_models()

        # 过滤
        candidates = [
            m for m in all_models
            if m.estimated_capability >= req.min_capability
            and (not req.needs_vision or m.supports_vision)
            and m.context_length >= req.min_context
        ]

        if not candidates:
            logger.debug("无本地模型满足需求 (min_cap=%d, vision=%s)",
                        req.min_capability, req.needs_vision)
            return None

        # 排序
        if req.prefer_fast:
            # 选最轻量的满足需求的模型
            candidates.sort(key=lambda m: (m.backend_priority, m.estimated_capability))
        else:
            # 选最强的满足需求的模型
            candidates.sort(key=lambda m: (m.backend_priority, -m.estimated_capability))

        return candidates[0]

    # -- 内部方法 ----------------------------------------------------------

    def _probe_backend(self, base_url: str, backend_name: str) -> Tuple[bool, List[Dict]]:
        """探测单个后端, 返回 (online, models_list)。

        Ollama: GET /api/tags (更准确的结构化返回)
        OpenAI 兼容: GET /v1/models → GET /models
        """
        try:
            import urllib.request as ur

            if "ollama" in backend_name.lower():
                # Ollama 特殊路径: /api/tags (无 /v1)
                ollama_base = base_url.replace("/v1", "")
                url = f"{ollama_base}/api/tags"
            else:
                # OpenAI 兼容后端
                url = base_url.rstrip("/") + "/models"

            req = ur.Request(url, method="GET", headers={"Accept": "application/json"})
            with ur.urlopen(req, timeout=LOCAL_HEALTH_TIMEOUT) as resp:
                if resp.status != 200:
                    return False, []
                data = json.loads(resp.read().decode())

            # 解析模型列表
            if "ollama" in backend_name.lower():
                # Ollama 格式: {"models": [{"name": "qwen3-vl:4b", "details": {...}}]}
                models_raw = data.get("models", [])
                # 过滤 "global" 等非真实模型
                models_raw = [
                    m for m in models_raw
                    if m.get("name") and m["name"] != "global"
                ]
            else:
                # OpenAI 兼容格式: {"data": [{"id": "model-name", ...}]}
                # 或 {"models": [{"name": "model-name", ...}]}
                models_raw = data.get("data", data.get("models", []))

            return True, models_raw

        except Exception as e:
            self._backend_status[backend_name] = {
                "online": False, "base_url": base_url, "error": str(e)
            }
            return False, []

    def _build_local_model(self, raw: Dict, backend: str,
                           base_url: str, priority: int) -> Optional[LocalModel]:
        """从原始 API 返回构建 LocalModel 对象。"""
        name = raw.get("name", raw.get("id", "unknown"))

        # 跳过 embedding 模型（nomic-embed-text, bge-* 等不适合用于 chat）
        if is_embedding_model(name):
            logger.debug("跳过 embedding 模型: %s", name)
            return None

        params = _estimate_params_from_api(raw)
        context_length = self._estimate_context_length(raw, name)
        supports_vision = _infer_vision_support(name)
        capability = _estimate_capability(params, context_length,
                                          supports_vision, True)

        return LocalModel(
            name=name,
            backend=backend,
            base_url=base_url,
            backend_priority=priority,
            params_b=params,
            context_length=context_length,
            supports_vision=supports_vision,
            supports_tools=True,
            estimated_capability=capability,
            raw_details=raw,
        )

    def _estimate_context_length(self, raw: Dict, name: str) -> int:
        """估算模型的上下文长度。"""
        # 尝试从 model details 获取
        details = raw.get("details", {})
        family = details.get("family", "").lower()

        # Ollama 已知模型的默认 context
        known_contexts = {
            "qwen3": 32768, "qwen2.5": 32768, "qwen2": 32768,
            "deepseek": 131072, "deepseek-r1": 131072,
            "llama3.2": 131072, "llama3.1": 131072, "llama3": 8192,
            "gemma3": 32768, "gemma2": 8192,
            "phi": 4096, "phi-3": 128000,
            "mistral": 32768, "mixtral": 32768,
        }

        for key, ctx in known_contexts.items():
            if key in family or key in name.lower():
                return ctx

        return 8192

    # -- 缓存 --------------------------------------------------------------

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and (time.time() - entry.timestamp) < entry.ttl:
            return entry.value
        return None

    def _set_cache(self, key: str, value: Any, ttl: float = CACHE_TTL):
        self._cache[key] = _CacheEntry(value, time.time(), ttl)


# -- 熔断管理 ----------------------------------------------------------------

@dataclass
class _ModelHealth:
    """单个模型健康状态。"""
    consecutive_failures: int = 0
    last_failure: float = 0.0
    last_success: float = 0.0


class HealthTracker:
    """模型健康追踪 + 熔断管理。

    解决"本地服务在线但模型推理失败, 连续重试三次才 Fallback"问题:
        - 连续失败 CIRCUIT_BREAKER_THRESHOLD 次 → 熔断
        - 熔断冷却 CIRCUIT_BREAKER_COOLDOWN 秒后恢复
        - 路由时自动过滤已熔断的模型
    """

    def __init__(self):
        self._stats: Dict[str, _ModelHealth] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def record_success(self, provider: str, model: str):
        """记录一次成功推理。"""
        key = self._key(provider, model)
        h = self._stats.get(key, _ModelHealth())
        h.consecutive_failures = 0
        h.last_success = time.time()
        self._stats[key] = h

    def record_failure(self, provider: str, model: str):
        """记录一次失败推理。"""
        key = self._key(provider, model)
        h = self._stats.get(key, _ModelHealth())
        h.consecutive_failures += 1
        h.last_failure = time.time()
        self._stats[key] = h
        logger.warning("模型 %s 连续失败 %d 次", key, h.consecutive_failures)

    def is_circuited(self, provider: str, model: str) -> bool:
        """检查模型是否已被熔断。"""
        key = self._key(provider, model)
        h = self._stats.get(key)
        if not h:
            return False
        if h.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            elapsed = time.time() - h.last_failure
            if elapsed < CIRCUIT_BREAKER_COOLDOWN:
                return True
            # 冷却结束, 自动恢复
            h.consecutive_failures = 0
        return False

    def filter(self, candidates: List[LocalModel]) -> List[LocalModel]:
        """过滤掉已熔断的模型。"""
        return [
            c for c in candidates
            if not self.is_circuited(c.backend, c.name)
        ]

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模型健康状态。"""
        return {
            key: {
                "consecutive_failures": h.consecutive_failures,
                "circuited": (
                    h.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD
                    and (time.time() - h.last_failure) < CIRCUIT_BREAKER_COOLDOWN
                ),
                "last_failure": h.last_failure,
                "last_success": h.last_success,
            }
            for key, h in self._stats.items()
        }


# -- 路由引擎 v2 --------------------------------------------------------------

class SmartRouter:
    """智能多模型路由引擎 v2。

    根据任务需求和模型能力, 自动在 本地 → 云端 → 嵌入式 之间选择最佳模型。

    Args:
        config: 完整的 config.yaml 配置字典 (可选)。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._cache: Dict[str, _CacheEntry] = {}
        self._ollama_offline_until: float = 0.0

        # v2: 多后端管理
        self.backend_hub = BackendHub(config)
        # v2: 熔断管理（本地+云端共用）
        self.health_tracker = HealthTracker()

        # 云端 failover 追踪
        self._cloud_health: Dict[str, Dict[str, Any]] = {}  # provider -> {"failures": int, "last_failure": float, "last_success": float}
        self._detected_clouds: List[Tuple[str, str, int]] = []  # (provider, model, priority)

        # 加载路由配置
        routing = self.config.get("routing", self.config.get("agent", {}).get("routing", {}))
        self.routing_mode: str = routing.get("mode", "auto")
        self.ollama_config = routing.get("ollama", {})
        self.embedded_config = routing.get("embedded", {})

        # M2: 成本感知路由配置
        raw_cost_strategy = routing.get("cost_mode", COST_STRATEGY_OFF)
        if raw_cost_strategy not in VALID_COST_STRATEGIES:
            logger.warning("未知 cost_mode '%s', 使用 'off'", raw_cost_strategy)
            raw_cost_strategy = COST_STRATEGY_OFF
        self.cost_mode: str = raw_cost_strategy
        # 用户自定义定价覆盖 (config.yaml → routing.cost_table)
        self._cost_user_overrides = routing.get("cost_table", {})
        # 合并后的成本表 (CN_MODEL_COSTS + 用户覆盖)
        self._cost_table: Dict[str, Tuple[float, float, int, bool]] = {}
        self._init_cost_table()

        # 用户自定义云提供商优先级（可选）
        self._user_cloud_order = routing.get("cloud_providers", [])

        # Fallback 链
        self.fallback_providers = self.config.get("fallback_providers", [])
        if not self.fallback_providers:
            fm = self.config.get("fallback_model", "")
            # fallback_model may be: str, list[str] (legacy), or
            # list[dict] (cfg migration injects {"provider":...,"model":...})
            if isinstance(fm, list) and fm:
                if isinstance(fm[0], dict):
                    self.fallback_providers = fm  # already correct format
                    fm = ""
                else:
                    fm = fm[0]  # string list -> take first entry
            if isinstance(fm, str) and fm:
                # fm = "provider:model" 格式
                p, _, m = fm.partition(":")
                self.fallback_providers = [{
                    "provider": p or "deepseek",
                    "model": m or "deepseek-chat",
                }]

        # 初始化时自动探测云提供商
        self._detect_cloud_providers()
        logger.debug("SmartRouter v2 初始化完成, mode=%s, backends=%d, clouds=%d",
                    self.routing_mode,
                    len(self.backend_hub.get_registered_backends()),
                    len(self._detected_clouds))

    # -- 缓存管理 -------------------------------------------------------------

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and (time.time() - entry.timestamp) < entry.ttl:
            return entry.value
        return None

    def _set_cache(self, key: str, value: Any, ttl: float = CACHE_TTL):
        self._cache[key] = _CacheEntry(value, time.time(), ttl)

    def _invalidate_cache(self):
        """清除所有缓存。"""
        self._cache.clear()

    # -- 云端提供商探测与 failover -------------------------------------------

    def _detect_cloud_providers(self) -> List[Tuple[str, str, int]]:
        """自动探测所有已配置 API KEY 的国产云提供商。

        优先级规则:
            1. 用户自定义 `cloud_providers` 配置 (config.yaml → routing.cloud_providers)
            2. CN_CLOUD_PROVIDERS 默认优先级

        Returns:
            [(provider, model, priority), ...] 按优先级排序。
        """
        from hermes_cli.config import get_env_value

        # 使用用户自定义优先级
        if self._user_cloud_order:
            detected = []
            for entry in self._user_cloud_order:
                if isinstance(entry, dict):
                    pid = entry.get("provider", "")
                    mid = entry.get("model", "")
                    prio = entry.get("priority", 999)
                else:
                    pid, _, mid = str(entry).partition(":")
                    prio = 999
                if pid and self._provider_has_key(pid):
                    detected.append((pid, mid, prio))
            self._detected_clouds = sorted(detected, key=lambda x: x[2])
            return self._detected_clouds

        # 使用默认优先级探测
        detected = []
        for pid, mid, env_vars, priority in CN_CLOUD_PROVIDERS:
            if self._provider_has_key(pid):
                detected.append((pid, mid, priority))

        self._detected_clouds = detected  # 已按 priority 排序
        return self._detected_clouds

    def _provider_has_key(self, provider_id: str) -> bool:
        """检查某个 Provider 是否配置了 API Key。"""
        from hermes_cli.config import get_env_value

        # 从 CN_CLOUD_PROVIDERS 查找环境变量
        for pid, mid, env_vars, prio in CN_CLOUD_PROVIDERS:
            if pid == provider_id:
                for env_var in env_vars:
                    if get_env_value(env_var):
                        return True

        # 从 config.providers 检查
        user_providers = self.config.get("providers", {})
        if isinstance(user_providers, dict) and provider_id in user_providers:
            return True

        return False

    # -- 成本路由 -------------------------------------------------------------

    def _init_cost_table(self) -> None:
        """初始化成本表: 从 CN_MODEL_COSTS 加载 + 用户覆盖合并。"""
        self._cost_table = dict(CN_MODEL_COSTS)

        # 应用用户自定义覆盖
        for key, overrides in self._cost_user_overrides.items():
            if key in self._cost_table:
                curr = list(self._cost_table[key])
            else:
                curr = [0.0, 0.0, 0, False]

            if isinstance(overrides, dict):
                if "input_price" in overrides:
                    curr[0] = float(overrides["input_price"])
                if "output_price" in overrides:
                    curr[1] = float(overrides["output_price"])
                if "context_window" in overrides:
                    curr[2] = int(overrides["context_window"])
                if "supports_vision" in overrides:
                    curr[3] = bool(overrides["supports_vision"])

            self._cost_table[key] = (curr[0], curr[1], curr[2], curr[3])

        logger.debug("成本表已初始化: %d 个模型条目 (%d 用户覆盖)",
                     len(self._cost_table), len(self._cost_user_overrides))

    def _get_model_cost_info(self, provider: str, model: str
                             ) -> Optional[Tuple[float, float, int, bool]]:
        """获取模型成本信息。

        Returns:
            (input_price, output_price, context_window, supports_vision) 或 None。
        """
        # 精确匹配
        key = f"{provider}:{model}"
        if key in self._cost_table:
            return self._cost_table[key]

        # 先找 provider: 后缀匹配 (用户可能在 config 中用 full model name)
        if self._cost_user_overrides:
            for ukey, uval in self._cost_user_overrides.items():
                if ukey.startswith(f"{provider}:") and model in ukey:
                    if isinstance(uval, dict):
                        inp = float(uval.get("input_price", 0))
                        out = float(uval.get("output_price", 0))
                        ctx = int(uval.get("context_window", 0))
                        vis = bool(uval.get("supports_vision", False))
                        return (inp, out, ctx, vis)

        # 回退: 通过 provider 默认模型找
        for pid, mid, _env_vars, _prio in CN_CLOUD_PROVIDERS:
            if pid == provider:
                fkey = f"{pid}:{mid}"
                if fkey in self._cost_table:
                    return self._cost_table[fkey]

        return None

    def _estimate_model_cost(self, provider: str, model: str,
                             input_tokens: int = COST_AVG_INPUT_TOKENS,
                             output_tokens: int = COST_AVG_OUTPUT_TOKENS) -> float:
        """估算单次请求的模型使用成本 (¥)。

        根据成本表中 input_price / output_price 计算。
        如果成本表中没有该模型, 返回 0 (未知价格, 视作免费)。
        """
        info = self._get_model_cost_info(provider, model)
        if not info:
            return 0.0

        input_price, output_price, _ctx, _vis = info
        # 价格单位: ¥/1M tokens
        cost = (input_price * input_tokens + output_price * output_tokens) / 1_000_000
        return round(cost, 6)

    def _cost_sorted_providers(self, req: Optional[TaskRequirements] = None
                               ) -> List[Tuple[str, str, int]]:
        """按成本策略对云提供商排序。

        Returns:
            排序后的 (provider, model, priority) 列表 [最优优先]。
        """
        if not self._detected_clouds:
            return []

        if self.cost_mode == COST_STRATEGY_OFF:
            # 按优先级排序 (M1 兼容)
            return sorted(self._detected_clouds, key=lambda x: x[2])

        # 计算每个 provider:model 的估算成本
        scored = []
        for pid, mid, prio in self._detected_clouds:
            cost = self._estimate_model_cost(pid, mid)

            # balanced / quality 模式: 检查能力匹配
            capability_match = True
            if req and self.cost_mode in (COST_STRATEGY_BALANCED, COST_STRATEGY_QUALITY):
                info = self._get_model_cost_info(pid, mid)
                if info:
                    _inp, _out, ctx, vis = info
                    # 视觉任务: 跳过无视觉支持的
                    if req.needs_vision and not vis:
                        capability_match = False

            scored.append((pid, mid, prio, cost, capability_match))

        if self.cost_mode == COST_STRATEGY_STRICT:
            # 纯价格优先 (不考虑能力)
            scored.sort(key=lambda x: (x[3], x[2]))  # cost asc, priority asc
        elif self.cost_mode == COST_STRATEGY_BALANCED:
            # 能力满足时选便宜的; 都不满足时按优先级
            matched = [s for s in scored if s[4]]
            unmatched = [s for s in scored if not s[4]]
            matched.sort(key=lambda x: (x[3], x[2]))
            unmatched.sort(key=lambda x: x[2])
            scored = matched + unmatched
        elif self.cost_mode == COST_STRATEGY_QUALITY:
            # 复杂任务 (req.min_capability 高) 选能力更强; 简单任务选便宜
            if req and req.min_capability >= 7:
                # 复杂任务: 按能力排序 (用 price / context 做粗略代理)
                matched = [s for s in scored if s[4]]
                matched.sort(key=lambda x: (-x[3], x[2]))  # 贵的模型能力通常更强
                unmatched = [s for s in scored if not s[4]]
                unmatched.sort(key=lambda x: x[2])
                scored = matched + unmatched
            else:
                # 简单任务: 便宜的优先
                matched = [s for s in scored if s[4]]
                unmatched = [s for s in scored if not s[4]]
                matched.sort(key=lambda x: (x[3], x[2]))
                unmatched.sort(key=lambda x: x[2])
                scored = matched + unmatched

        return [(pid, mid, prio) for pid, mid, prio, _cost, _match in scored]

    def record_cloud_failure(self, provider: str) -> None:
        """记录云提供商调用失败，自动熔断检测。

        连续失败达到 CLOUD_FAILOVER_THRESHOLD 次后，
        该提供商在 CLOUD_FAILOVER_COOLDOWN 秒内被跳过。
        """
        now = time.time()
        entry = self._cloud_health.setdefault(provider, {
            "failures": 0,
            "last_failure": 0.0,
            "last_success": now,
        })
        entry["failures"] = entry.get("failures", 0) + 1
        entry["last_failure"] = now
        logger.debug("云提供商 %s 失败 (%d/%d)", provider,
                    entry["failures"], CLOUD_FAILOVER_THRESHOLD)

    def record_cloud_success(self, provider: str) -> None:
        """记录云提供商调用成功，重置熔断计数。"""
        now = time.time()
        entry = self._cloud_health.setdefault(provider, {
            "failures": 0,
            "last_failure": 0.0,
            "last_success": now,
        })
        entry["failures"] = 0
        entry["last_success"] = now

    def _is_cloud_healthy(self, provider: str) -> bool:
        """检查云提供商是否健康（未熔断）。"""
        entry = self._cloud_health.get(provider)
        if not entry:
            return True
        if entry.get("failures", 0) < CLOUD_FAILOVER_THRESHOLD:
            return True
        # 熔断冷却期检查
        cooldown = time.time() - entry.get("last_failure", 0)
        if cooldown > CLOUD_FAILOVER_COOLDOWN:
            # 冷却结束，自动恢复
            entry["failures"] = 0
            return True
        return False

    # -- 任务分析 v2 ----------------------------------------------------------

    def _analyze_task(self, message: str,
                      session_turn_count: int = 0) -> TaskRequirements:
        """分析任务需求, 返回量化能力需求。

        综合考虑:
            - 消息长度
            - 是否含图片
            - 是否含代码/工具调用
            - 会话轮次 (多轮对话需要更大上下文)
            - 关键词 (复杂任务检测)
        """
        text = message.lower()
        length = len(message)
        has_image = any(marker in message for marker in
                       ("<image>", "![[", "![image]", "image_url"))
        has_code = "```" in message or any(kw in text for kw in
                   ("def ", "function", "class ", "import ", "async def"))

        # 关键词加权
        complex_score = sum(1 for kw in COMPLEX_KEYWORDS if kw.lower() in text)

        # 基础能力分
        if complex_score >= 2 or length > 3000:
            base = 8
        elif complex_score >= 1 or length > 1000:
            base = 6
        elif has_code and length > 300:
            base = 5
        elif has_image:
            base = 4  # 图片需要视觉支持
        elif session_turn_count > 20:
            base = 5  # 长对话需要大模型
        elif session_turn_count > 10:
            base = 4
        elif length < 80:
            base = 2  # 短消息 → 简单问答
            prefer_fast = True
        elif length < 300:
            base = 3
            prefer_fast = True
        else:
            base = 4

        prefer_fast = base <= 3 and not has_code and not has_image

        return TaskRequirements(
            min_capability=base,
            needs_vision=has_image,
            needs_tools=has_code,
            min_context=32768 if length > 2000 or session_turn_count > 15 else 8192,
            prefer_fast=prefer_fast,
        )

    # -- 健康检查 (向后兼容保留) -----------------------------------------------

    def check_ollama(self) -> bool:
        """检查是否有任何本地后端在线 (v2: 不再只查 Ollama)。

        缓存策略: 离线后 LOCAL_OFFLINE_COOLDOWN 秒内不重试。
        """
        if time.time() < self._ollama_offline_until:
            return False

        cached = self._get_cached("any_local_online")
        if cached is not None:
            return cached

        models = self.backend_hub.probe_all(force=True)
        online = len(models) > 0

        if online:
            self._ollama_offline_until = 0.0
        else:
            self._ollama_offline_until = time.time() + LOCAL_OFFLINE_COOLDOWN

        self._set_cache("any_local_online", online)
        return online

    def check_local_servers(self) -> Dict[str, Any]:
        """检测所有本地 OpenAI 兼容服务 (v2: BackendHub 版本)。

        返回第一个在线后端的模型列表 (向后兼容)。
        """
        models = self.backend_hub.get_all_models(force=True)
        if models:
            first = models[0]
            return {
                "online": True,
                "provider": first.backend,
                "base_url": first.base_url,
                "models": [m.name for m in models],
            }

        # 回退兼容: 也检查传统 model.base_url
        model_cfg = self.config.get("model", {})
        base_url = (model_cfg.get("base_url") or "").strip()
        result: Dict[str, Any] = {
            "online": False, "provider": "", "base_url": base_url, "models": [],
        }
        if not base_url:
            return result

        is_local = ("localhost" in base_url.lower()
                    or base_url.startswith("http://127.")
                    or base_url.startswith("https://127."))
        if not is_local:
            return result

        try:
            models_url = base_url.rstrip("/") + "/models"
            req = urllib.request.Request(models_url, method="GET",
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=LOCAL_HEALTH_TIMEOUT) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    models_list = data.get("data", data.get("models", []))
                    model_names = [
                        m.get("id", m.get("name", ""))
                        for m in models_list
                        if m.get("id") or m.get("name")
                    ]
                    result["online"] = True
                    result["models"] = model_names
        except Exception:
            pass

        return result

    def check_cloud(self) -> bool:
        """检查是否有可用的云端 Provider（使用 CN_CLOUD_PROVIDERS 数据库）。"""
        cached = self._get_cached("cloud_available")
        if cached is not None:
            return cached

        # 使用已探测云提供商列表
        if not self._detected_clouds:
            self._detect_cloud_providers()
        available = len(self._detected_clouds) > 0

        self._set_cache("cloud_available", available)
        return available

    def check_embedded(self) -> bool:
        """检查嵌入式推理是否可用。"""
        cached = self._get_cached("embedded_available")
        if cached is not None:
            return cached

        try:
            from hermes_cli.embedded import is_embedded_available
            available = is_embedded_available()
            self._set_cache("embedded_available", available)
            return available
        except ImportError:
            self._set_cache("embedded_available", False)
            return False

    # -- 模型选择 -------------------------------------------------------------

    def _select_ollama_model(self, complexity: TaskComplexity) -> Optional[str]:
        """根据复杂度选择 Ollama 模型 (向后兼容保留)。

        v2 建议使用 _analyze_task + BackendHub 代替。
        """
        req = TaskRequirements.from_complexity(complexity)
        best = self.backend_hub.get_best_for_task(req)
        return best.name if best else None

    def _select_cloud_model(self,
                             task_req: Optional[TaskRequirements] = None
                             ) -> str:
        """选择云端模型 (支持 cost-aware failover)。

        策略:
          1. cost_mode=off: 按优先级排序 (M1 兼容)
          2. cost_mode=balanced: 能力足够下最便宜
          3. cost_mode=strict: 始终最便宜
          4. cost_mode=quality: 复杂任务能力优先, 简单任务便宜优先

        熔断: 跳过 _is_cloud_healthy() 返回 False 的提供商。
        """
        if not self._detected_clouds:
            self._detect_cloud_providers()

        # 按成本策略排序候选列表
        candidates = self._cost_sorted_providers(task_req)

        # 第一遍：跳过已熔断的提供商
        for pid, mid, _prio in candidates:
            if self._is_cloud_healthy(pid):
                return f"{pid}:{mid}"

        # 全部熔断：返回第一个（让调用方触发降级逻辑）
        if candidates:
            logger.warning("所有云提供商均已熔断, 降级使用 %s", candidates[0][0])
            return f"{candidates[0][0]}:{candidates[0][1]}"

        return "deepseek:deepseek-chat"

    def _select_embedded_model(self, complexity: TaskComplexity) -> Optional[str]:
        """选择嵌入式模型。"""
        try:
            from hermes_cli.model_manager import get_available_embedded_model
            result = get_available_embedded_model()
            if result:
                return result.get("model_id")
        except ImportError:
            pass
        return None

    # -- 主路由 v2 -----------------------------------------------------------

    def route(
        self,
        user_message: str,
        force_tier: Optional[ModelTier] = None,
        session_turn_count: int = 0,
    ) -> RouteResult:
        """执行智能路由决策 v2。

        能力感知路由: 分析任务需求 → 过滤满足能力的模型 → 选最佳。
        自动记录路由日志到 ~/.hermes/logs/luyou_routes.jsonl。

        Args:
            user_message: 用户消息文本。
            force_tier: 强制使用指定层级 (忽略降级)。
            session_turn_count: 会话轮次 (用于上下文需求评估)。

        Returns:
            RouteResult 路由决策结果。
        """
        result = None
        req = None

        # 手动模式
        if self.routing_mode == "manual":
            default_model = self.config.get("model", {}).get("default", "ollama:qwen3-vl:4b")
            provider, _, model = default_model.partition(":")
            result = RouteResult(
                provider=provider or "ollama",
                model=model or "qwen3-vl:4b",
                tier=ModelTier.LOCAL,
                reason="手动模式，使用默认配置",
            )
            self._log_route(result)
            return result

        # 分析任务需求
        req = self._analyze_task(user_message, session_turn_count)
        logger.debug("任务需求: min_cap=%d, vision=%s, tools=%s, ctx=%d",
                    req.min_capability, req.needs_vision, req.needs_tools,
                    req.min_context)

        # 强制嵌入式
        if force_tier == ModelTier.EMBEDDED or self.routing_mode == "embedded-only":
            complexity = analyze_complexity(user_message)
            model_id = self._select_embedded_model(complexity)
            if model_id:
                result = RouteResult(
                    provider="embedded", model=model_id,
                    tier=ModelTier.EMBEDDED,
                    reason=f"嵌入式模式 (需求 cap={req.min_capability})",
                )
            else:
                result = RouteResult(provider="", model="", tier=ModelTier.NONE,
                              reason="嵌入式模型未安装")
            self._log_route(result, req)
            return result

        # 强制云端
        if force_tier == ModelTier.CLOUD or self.routing_mode == "cloud-only":
            if self.check_cloud():
                cloud_sel = self._select_cloud_model(task_req=req)
                provider, _, model = cloud_sel.partition(":")
                result = RouteResult(
                    provider=provider, model=model,
                    tier=ModelTier.CLOUD,
                    reason=f"云端模式 (需求 cap={req.min_capability})",
                )
            else:
                result = RouteResult(provider="", model="", tier=ModelTier.NONE,
                              reason="云端 API 不可用")
            self._log_route(result, req)
            return result

        # === 自动模式: 能力感知三层路由 ===

        # Tier 1: 本地模型
        local_model = self.backend_hub.get_best_for_task(req)
        if local_model:
            # HealthTracker 过滤: 熔断的模型跳过
            if self.health_tracker.is_circuited(
                    local_model.backend, local_model.name):
                logger.debug("本地模型 %s 已被熔断, 跳过",
                           local_model.provider_model)
            else:
                result = RouteResult(
                    provider=local_model.backend,
                    model=local_model.name,
                    tier=ModelTier.LOCAL,
                    reason=(f"本地 {local_model.backend}"
                            f" cap={local_model.estimated_capability}/10"
                            f" (需求≥{req.min_capability})"
                            f" → {local_model.name}"),
                    backend=local_model.backend,
                )
                self._log_route(result, req)
                return result

        # 本地模型不满足需求或无本地后端 → 云端
        if self.check_cloud():
            cloud_sel = self._select_cloud_model(task_req=req)
            provider, _, model = cloud_sel.partition(":")
            reason = "云端介入"
            if self.backend_hub.get_all_models():
                reason += (" (本地模型能力不足:"
                          f" 需求 cap≥{req.min_capability})")
            else:
                reason += " (本地后端离线)"
            result = RouteResult(
                provider=provider, model=model,
                tier=ModelTier.CLOUD,
                reason=reason,
            )
            self._log_route(result, req)
            return result

        # Tier 3: 嵌入式兜底
        complexity = analyze_complexity(user_message)
        model_id = self._select_embedded_model(complexity)
        if model_id:
            result = RouteResult(
                provider="embedded", model=model_id,
                tier=ModelTier.EMBEDDED,
                reason="本地离线且云端不可用, 启用嵌入式 CPU 推理",
            )
            self._log_route(result, req)
            return result

        # 全部不可用
        result = RouteResult(
            provider="", model="", tier=ModelTier.NONE,
            reason="无可用模型: 请启动本地推理服务 (Ollama/LM Studio/llama.cpp) 或配置云端 API Key",
        )
        self._log_route(result, req)
        return result

    # -- 路由日志 (Phase C) -------------------------------------------------

    def _log_route(self, result: RouteResult, task_req: Optional[TaskRequirements] = None) -> None:
        """将路由决策写入日志文件 (JSONL 格式, ~/.hermes/logs/)。

        记录: 时间戳、 路由模式、 决策结果、 原因、 任务需求。
        日志支持自动截断, 避免无限制增长。
        """
        try:
            log_dir = os.path.join(os.path.expanduser("~"), ".hermes", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "luyou_routes.jsonl")

            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "mode": self.routing_mode,
                "provider": result.provider,
                "model": result.model,
                "tier": result.tier.value if result.tier else "none",
                "reason": result.reason,
                "backend": result.backend,
            }
            if task_req:
                entry["task"] = {
                    "min_cap": task_req.min_capability,
                    "vision": task_req.needs_vision,
                    "tools": task_req.needs_tools,
                    "context": task_req.min_context,
                }

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            # 自动截断: 超过上限时保留最近的记录
            self._truncate_log(log_path)
        except Exception:
            pass  # 日志写入失败不影响主流程

    def _truncate_log(self, log_path: str) -> None:
        """截断路由日志: 超过 ROUTE_LOG_MAX_LINES 时保留最后 ROUTE_LOG_TRUNCATE_TO 行。"""
        try:
            with open(log_path, "rb") as f:
                # quick count via seeking
                f.seek(0, 2)
                file_size = f.tell()
                if file_size < 1024:  # too small to worry
                    return

            line_count = 0
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for _ in f:
                    line_count += 1

            if line_count <= ROUTE_LOG_MAX_LINES:
                return

            # Read and keep last N lines
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            lines = lines[-ROUTE_LOG_TRUNCATE_TO:]
            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            logger.info("路由日志截断: %d → %d 行", line_count, ROUTE_LOG_TRUNCATE_TO)
        except Exception:
            pass
    # -- 规则匹配 (原 run_agent.py AIAgent._match_rule) -----------------------

    @staticmethod
    def _match_rule(match: dict, has_image: bool, text_lower: str, text_length: int) -> bool:
        """检查路由规则是否匹配。

        Returns True when ALL specified conditions are satisfied.
        """
        # has_image condition
        if "has_image" in match:
            if bool(match["has_image"]) != has_image:
                return False

        # keywords condition (any keyword triggers by default)
        keywords = match.get("keywords", [])
        if keywords:
            threshold = int(match.get("threshold", 1))
            matched = sum(1 for kw in keywords if kw.lower() in text_lower)
            if matched < threshold:
                return False

        # max_length condition (message length in chars)
        max_len = match.get("max_length")
        if max_len is not None:
            if text_length > int(max_len):
                return False

        # exclude_keywords condition (any match disqualifies)
        excl = match.get("exclude_keywords", [])
        if excl and any(kw.lower() in text_lower for kw in excl):
            return False

        return True

    def route_with_rules(
        self,
        user_message: str,
        rules: Optional[List[RoutingRule]] = None,
        legacy_cfg: Optional[Dict[str, Any]] = None,
        has_image: bool = False,
        force_tier: Optional[ModelTier] = None,
        session_turn_count: int = 0,
    ) -> RouteResult:
        """规则优先路由: 先匹配用户规则, 未命中则回落能力感知路由。

        统一了 model_routing.rules + legacy model_routing + SmartRouter 的完整流程。
        Args:
            user_message: 用户消息文本。
            rules: 用户定义的规则列表 (model_routing.rules)。
            legacy_cfg: 旧格式 model_routing 配置 (vision/reasoning/default)。
            has_image: 消息是否包含图片附件。
            force_tier: 强制使用指定层级。
            session_turn_count: 会话轮次 (用于上下文需求评估)。
        Returns:
            RouteResult 路由决策结果。
        """
        text_lower = user_message.lower() if user_message else ""
        text_length = len(user_message) if user_message else 0

        # 阶段1: 规则匹配 (新格式 rules)
        if rules:
            for rule in rules:
                match = rule.match or {}
                if not match:
                    continue  # 无条件规则暂不匹配, 最后兜底
                if self._match_rule(match, has_image, text_lower, text_length):
                    logger.debug(
                        "route_with_rules: rule '%s' matched → %s",
                        rule.name, rule.model,
                    )
                    return RouteResult(
                        provider=rule.provider or "auto",
                        model=rule.model,
                        tier=ModelTier.CLOUD,
                        reason=f"规则匹配: {rule.name}",
                    )

            # 无条件的默认规则
            for rule in rules:
                match = rule.match or {}
                if not match:
                    logger.debug(
                        "route_with_rules: default rule '%s' → %s",
                        rule.name, rule.model,
                    )
                    return RouteResult(
                        provider=rule.provider or "auto",
                        model=rule.model,
                        tier=ModelTier.CLOUD,
                        reason=f"默认规则: {rule.name}",
                    )

        # 阶段2: 旧格式匹配 (vision / reasoning / default)
        if legacy_cfg and isinstance(legacy_cfg, dict):
            # 图片附件匹配
            if has_image:
                vision_cfg = legacy_cfg.get("vision", {})
                if isinstance(vision_cfg, dict) and vision_cfg.get("model"):
                    logger.debug(
                        "route_with_rules: legacy vision → %s", vision_cfg["model"],
                    )
                    return RouteResult(
                        provider="auto", model=vision_cfg["model"],
                        tier=ModelTier.CLOUD, reason="旧格式: vision",
                    )

            # 视觉关键词匹配
            _vision_kw = ["看图", "图片", "截图", "识别图中", "这张图"]
            if any(kw in text_lower for kw in _vision_kw):
                vision_cfg = legacy_cfg.get("vision", {})
                if isinstance(vision_cfg, dict) and vision_cfg.get("model"):
                    logger.debug(
                        "route_with_rules: legacy vision kw → %s", vision_cfg["model"],
                    )
                    return RouteResult(
                        provider="auto", model=vision_cfg["model"],
                        tier=ModelTier.CLOUD, reason="旧格式: vision关键词",
                    )

            # 推理关键词匹配
            _reasoning_kw = ["分析", "推理", "证明", "思考"]
            if any(kw in text_lower for kw in _reasoning_kw):
                reasoning_cfg = legacy_cfg.get("reasoning", {})
                if isinstance(reasoning_cfg, dict) and reasoning_cfg.get("model"):
                    logger.debug(
                        "route_with_rules: legacy reasoning → %s", reasoning_cfg["model"],
                    )
                    return RouteResult(
                        provider="auto", model=reasoning_cfg["model"],
                        tier=ModelTier.CLOUD, reason="旧格式: reasoning",
                    )

            # 默认模型
            default_cfg = legacy_cfg.get("default", {})
            if isinstance(default_cfg, dict) and default_cfg.get("model"):
                logger.debug(
                    "route_with_rules: legacy default → %s", default_cfg["model"],
                )
                return RouteResult(
                    provider="auto", model=default_cfg["model"],
                    tier=ModelTier.CLOUD, reason="旧格式: default",
                )

        # 阶段3: 能力感知自动路由
        return self.route(
            user_message,
            force_tier=force_tier,
            session_turn_count=session_turn_count,
        )

    def route_with_config(
        self,
        user_message: str,
        provider_model_config: Optional[str] = None,
    ) -> RouteResult:
        """带用户配置的路由决策。"""
        if provider_model_config and provider_model_config != "auto":
            provider, _, model = provider_model_config.partition(":")
            if provider == "embedded":
                return RouteResult(
                    provider="embedded", model=model,
                    tier=ModelTier.EMBEDDED,
                    reason="用户指定嵌入式模型",
                )
            return RouteResult(
                provider=provider or "deepseek",
                model=model or "deepseek-chat",
                tier=ModelTier.CLOUD,
                reason="用户指定模型",
            )
        return self.route(user_message)

    # -- 状态报告 -------------------------------------------------------------

    def status_dict(self, verbose: bool = False) -> Dict[str, Any]:
        """生成当前路由状态字典 (v2: 多后端)。

        Args:
            verbose: 是否包含详细模型元信息 (param_size, tools_support 等)。

        Returns:
            路由状态字典, 可用于 JSON 输出。
        """
        local_models = self.backend_hub.get_all_models()
        backends = {}
        for b in self.backend_hub.get_registered_backends():
            name = b["name"]
            status = self.backend_hub._backend_status.get(name, {})
            b_models = [m.name for m in local_models if m.backend == name]
            backends[name] = {
                "online": status.get("online", False),
                "base_url": b["base_url"],
                "error": status.get("error", ""),
                "models": b_models,
                "priority": b["priority"],
            }

        model_list = []
        for m in sorted(local_models,
                        key=lambda x: (x.backend_priority, -x.estimated_capability)):
            entry = {
                "name": m.name,
                "backend": m.backend,
                "params_b": m.params_b,
                "context_length": m.context_length,
                "capability": m.estimated_capability,
                "vision": m.supports_vision,
            }
            if verbose:
                entry["backend_priority"] = m.backend_priority
                entry["tools_support"] = m.supports_tools
                entry["raw_details"] = m.raw_details
            model_list.append(entry)

        # 云端状态（含 failover + cost 信息）
        cloud_available = self.check_cloud()
        cloud_health = {}
        for pid, mid, prio in self._detected_clouds:
            h = {
                "model": mid,
                "priority": prio,
                "healthy": self._is_cloud_healthy(pid),
            }
            hc = self._cloud_health.get(pid, {})
            h["failures"] = hc.get("failures", 0)
            # M2: 成本估算
            cost_info = self._get_model_cost_info(pid, mid)
            if cost_info:
                inp_p, out_p, ctx, vis = cost_info
                est = self._estimate_model_cost(pid, mid)
                h["cost"] = {
                    "input_price": inp_p,
                    "output_price": out_p,
                    "context_window": ctx,
                    "supports_vision": vis,
                    "estimated_per_request": est,  # ¥
                }
            cloud_health[pid] = h

        result = {
            "local_backends": backends,
            "local_models": model_list,
            "cloud": {"available": cloud_available, "providers": cloud_health},
            "embedded": {"available": self.check_embedded()},
            "routing_mode": self.routing_mode,
            "health": self.health_tracker.get_status(),
            "cost_mode": self.cost_mode,
        }

        if verbose:
            result["config"] = {
                "cache_ttl": CACHE_TTL,
                "probe_cooldown": PROBE_COOLDOWN,
                "circuit_breaker_threshold": CIRCUIT_BREAKER_THRESHOLD,
                "circuit_breaker_cooldown": CIRCUIT_BREAKER_COOLDOWN,
                "cloud_failover_threshold": CLOUD_FAILOVER_THRESHOLD,
                "cloud_failover_cooldown": CLOUD_FAILOVER_COOLDOWN,
                "default_backend_ports": DEFAULT_BACKEND_PORTS,
            }

        return result

    def status_report(self) -> Dict[str, Any]:
        """向后兼容: status_report() = status_dict(verbose=False)。"""
        return self.status_dict(verbose=False)

    def print_status(self, verbose: bool = False) -> str:
        """生成可读的中文状态报告 (v2: 多后端)。

        Args:
            verbose: 是否显示详细模型元信息。

        Returns:
            格式化的状态文本。
        """
        status = self.status_dict(verbose=verbose)
        lines = ["=== 智能路由引擎 v2 ==="]
        lines.append(f"路由模式: {status['routing_mode']}")

        # 后端状态
        backends = status["local_backends"]
        if backends:
            lines.append("\n▸ 本地后端:")
            for name, info in backends.items():
                icon = "✅" if info["online"] else "❌"
                lines.append(f"  {icon} {name} (p{info['priority']})"
                           f" — {info['base_url']}")
                if info.get("error"):
                    lines.append(f"     错误: {info['error']}")
                if info.get("models"):
                    shown = info["models"][:3]
                    lines.append(f"     模型: {', '.join(shown)}"
                               f"{' ... (+' + str(len(info['models']) - 3) + ')' if len(info['models']) > 3 else ''}")
        else:
            lines.append("  本地后端: ❌ 未配置")

        # 能力编目
        local_models = status["local_models"]
        if local_models:
            lines.append(f"\n▸ 本地模型编目 ({len(local_models)} 个):")
            for m in local_models[:10]:
                vision = "👁" if m["vision"] else "  "
                ctx = f"{m['context_length'] // 1024}K"
                lines.append(f"  {vision} [{m['backend']}] {m['name']}"
                           f" (cap={m['capability']}/10, ctx={ctx})")
            if len(local_models) > 10:
                lines.append(f"  ... 共 {len(local_models)} 个模型")

        # 云端
        lines.append(f"\n▸ 云端 API: {'✅ 可用' if status['cloud']['available'] else '❌ 未配置'}")
        providers = status["cloud"].get("providers", {})
        if providers:
            for pid, info in providers.items():
                icon = "✅" if info["healthy"] else "⛔"
                fail_str = f" (失败{info['failures']}次)" if info["failures"] else ""
                cost_info = info.get("cost")
                if cost_info:
                    ctx = f"{cost_info['context_window'] // 1024}K" if cost_info['context_window'] else "?"
                    est = cost_info['estimated_per_request']
                    cost_str = f" ¥{cost_info['input_price']}/{cost_info['output_price']} ctx={ctx}"
                    if est:
                        cost_str += f" ~¥{est*1000:.2f}‰"
                else:
                    cost_str = ""
                lines.append(f"  {icon} {pid} → {info['model']} p{info['priority']}{fail_str}{cost_str}")
        # 成本模式
        cost_mode = status.get("cost_mode", "off")
        if cost_mode != "off":
            mode_labels = {"balanced": "均衡 (满足需求最便宜)", "strict": "最便宜优先",
                           "quality": "复杂任务能力优先", "off": "按优先级"}
            lines.append(f"  💰 成本模式: {mode_labels.get(cost_mode, cost_mode)}")
        lines.append(f"▸ 嵌入式模型: {'✅ 可用' if status['embedded']['available'] else '❌ 未安装'}")

        # Health
        health = status["health"]
        if health:
            circuited = [k for k, v in health.items() if v.get("circuited")]
            if circuited:
                lines.append(f"\n▸ 熔断中: {', '.join(circuited)}")

        # Verbose: 模型详情
        if verbose:
            cfg = status.get("config", {})
            lines.append(f"\n▸ 配置参数:")
            lines.append(f"  缓存TTL={cfg.get('cache_ttl')}s, "
                       f"探测冷却={cfg.get('probe_cooldown')}s")
            lines.append(f"  熔断阈值={cfg.get('circuit_breaker_threshold')}次, "
                       f"熔断冷却={cfg.get('circuit_breaker_cooldown')}s")
            lines.append(f"  默认后端端口: {cfg.get('default_backend_ports', {})}")
            if local_models:
                lines.append(f"\n▸ 模型详情:")
                for m in local_models:
                    vision = "YES" if m.get("vision") else "NO"
                    tools = "YES" if m.get("tools_support") else "NO"
                    lines.append(
                        f"  [{m['backend']}] {m['name']}"
                        f"\n     params={m.get('params_b')}B, ctx={m.get('context_length')}, "
                        f"cap={m.get('capability')}/10"
                        f"\n     vision={vision}, tools={tools}"
                        f"\n     raw={m.get('raw_details', {})}"
                    )

        return "\n".join(lines)


# -- 全局单例 ----------------------------------------------------------------

_router_instance: Optional[SmartRouter] = None


def get_router(config: Optional[Dict[str, Any]] = None) -> SmartRouter:
    """获取全局路由实例。

    Args:
        config: 配置字典 (首次调用时提供)。

    Returns:
        SmartRouter 实例。
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = SmartRouter(config)
    elif config is not None:
        _router_instance.config = config
        _router_instance._invalidate_cache()
    return _router_instance


def quick_route(message: str) -> RouteResult:
    """快速路由 (使用全局实例)。"""
    router = get_router()
    return router.route(message)