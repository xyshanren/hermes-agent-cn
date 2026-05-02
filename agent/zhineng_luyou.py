"""
智能多模型路由引擎 — 三层自动降级：Ollama → 云端 → 嵌入式。

Hermes-Agent-CN 核心组件，确保在任何网络条件下都能工作。

路由策略:
    Tier 1 (最佳):   Ollama 本地服务器
                     ├── 简单任务 → qwen3-vl:4b
                     ├── 中等任务 → 用户配置的 Ollama 中等模型 / 云端
                     └── 复杂任务 → 云端

    Tier 2 (云端):   国产 API
                     └── DeepSeek / MiniMax / Kimi / Zai

    Tier 3 (兜底):   嵌入式 CPU 推理
                     ├── Qwen2.5-Coder-1.5B (代码/推理)
                     └── Qwen2.5-0.5B (bundled, 总是可用)

使用方式:
    from agent.zhineng_luyou import SmartRouter
    router = SmartRouter(config)
    result = router.route(user_message)
    # result.provider, result.model, result.tier, result.reason
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# -- 常量 --------------------------------------------------------------------

OLLAMA_DEFAULT_HOST = "localhost"
OLLAMA_DEFAULT_PORT = 11434
OLLAMA_DEFAULT_SIMPLE_MODEL = "qwen3-vl:4b"
OLLAMA_HEALTH_TIMEOUT = 3.0           # 健康检查超时 (秒)
OLLAMA_OFFLINE_COOLDOWN = 300          # 离线标记冷却 (秒, =5分钟)
CACHE_TTL = 60                         # 路由决策缓存时间 (秒)

# 嵌入式模型优先级
EMBEDDED_MODEL_ORDER = ["qwen-coder-1.5b", "qwen-0.5b"]


# -- 数据类型 ----------------------------------------------------------------

class ModelTier(Enum):
    """模型层级。"""
    OLLAMA = "ollama"       # Tier 1: 本地 Ollama
    CLOUD = "cloud"         # Tier 2: 国产云端 API
    EMBEDDED = "embedded"   # Tier 3: 嵌入式 CPU 推理
    NONE = "none"           # 无可用的模型


class TaskComplexity(Enum):
    """任务复杂度。"""
    SIMPLE = "simple"       # 闲聊、翻译、简单问答
    MEDIUM = "medium"       # 代码审查、多步操作、短文档
    COMPLEX = "complex"     # 架构设计、大文件重构、多文件协调


@dataclass
class RouteResult:
    """路由决策结果。"""
    provider: str                       # Provider ID
    model: str                          # Model ID
    tier: ModelTier                     # 使用的层级
    reason: str                         # 决策原因（中文）
    timestamp: float = field(default_factory=time.time)

    @property
    def provider_model(self) -> str:
        """返回 "provider:model" 格式字符串。"""
        return f"{self.provider}:{self.model}"

    def __bool__(self) -> bool:
        """是否为有效路由结果。"""
        return self.tier != ModelTier.NONE


# -- 复杂度判断 ----------------------------------------------------------------

# 简单任务关键词
SIMPLE_KEYWORDS = [
    "你好", "hi", "hello", "谢谢", "再见", "翻译",
    "hi", "hello", "thanks", "bye",
    "格式", "format", "缩进", "indent",
    "天气", "weather", "时间", "time", "日期", "date",
]

# 复杂任务关键词
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
    """分析用户消息的复杂度。

    策略：
        1. 简单关键词匹配 → SIMPLE
        2. 复杂关键词匹配 → COMPLEX（与简单冲突时复杂优先）
        3. 消息长度 > 500 字符 → COMPLEX
        4. 消息长度 < 50 字符 → SIMPLE
        5. 默认 → MEDIUM
    """
    text = message.lower().strip()
    length = len(message)

    # 检查复杂关键词
    complex_score = sum(1 for kw in COMPLEX_KEYWORDS if kw.lower() in text)
    if complex_score >= 1 or length > 500:
        return TaskComplexity.COMPLEX

    # 检查简单关键词
    simple_score = sum(1 for kw in SIMPLE_KEYWORDS if kw.lower() in text)
    if simple_score >= 1 or length < 50:
        return TaskComplexity.SIMPLE

    return TaskComplexity.MEDIUM


# -- 路由引擎 ----------------------------------------------------------------

@dataclass
class _CacheEntry:
    """缓存条目。"""
    value: Any
    timestamp: float
    ttl: float


class SmartRouter:
    """智能多模型路由引擎。

    三层自动降级路由，根据任务复杂度和模型可用性选择最佳 Provider。

    Args:
        config: 完整的 config.yaml 配置字典（可选）。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._cache: Dict[str, _CacheEntry] = {}
        self._ollama_offline_until: float = 0.0

        # 加载路由配置
        routing = self.config.get("agent", {}).get("routing", {})
        self.routing_mode: str = routing.get("mode", "auto")
        self.ollama_config = routing.get("ollama", {})
        self.embedded_config = routing.get("embedded", {})

        logger.debug("SmartRouter 初始化完成, mode=%s", self.routing_mode)

    # -- 缓存管理 -------------------------------------------------------------

    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存值（未过期时）。"""
        entry = self._cache.get(key)
        if entry and (time.time() - entry.timestamp) < entry.ttl:
            return entry.value
        return None

    def _set_cache(self, key: str, value: Any, ttl: float = CACHE_TTL):
        """设置缓存。"""
        self._cache[key] = _CacheEntry(value, time.time(), ttl)

    def _invalidate_cache(self):
        """清除所有缓存。"""
        self._cache.clear()

    # -- 健康检查 -------------------------------------------------------------

    def check_ollama(self) -> bool:
        """检查 Ollama 是否在线。

        缓存策略：离线后 OLLAMA_OFFLINE_COOLDOWN 秒内不重试。
        """
        # 如果还在冷却期，直接返回 False
        if time.time() < self._ollama_offline_until:
            return False

        # 检查缓存
        cached = self._get_cached("ollama_online")
        if cached is not None:
            return cached

        host = self.ollama_config.get("host", OLLAMA_DEFAULT_HOST)
        port = self.ollama_config.get("port", OLLAMA_DEFAULT_PORT)
        url = f"http://{host}:{port}/api/tags"

        try:
            import urllib.request
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=OLLAMA_HEALTH_TIMEOUT) as resp:
                if resp.status == 200:
                    self._set_cache("ollama_online", True)
                    self._ollama_offline_until = 0.0
                    logger.debug("Ollama 在线: %s:%d", host, port)
                    return True
        except Exception as e:
            logger.debug("Ollama 不可达 (%s:%d): %s", host, port, e)

        # 标记离线
        self._ollama_offline_until = time.time() + OLLAMA_OFFLINE_COOLDOWN
        self._set_cache("ollama_online", False)
        return False

    def check_cloud(self) -> bool:
        """检查是否有可用的云端 Provider。

        检查条件：至少有一个国产 Provider 配置了 API Key。
        """
        cached = self._get_cached("cloud_available")
        if cached is not None:
            return cached

        # 国产云端 Provider 列表
        cloud_providers = ["deepseek", "minimax", "minimax-cn", "kimi-for-coding", "zai"]

        # 从环境变量检测
        provider_env_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "minimax-cn": "MINIMAX_CN_API_KEY",
            "kimi-for-coding": "KIMI_API_KEY",
            "zai": "GLM_API_KEY",
        }

        import os
        for provider_id in cloud_providers:
            env_var = provider_env_map.get(provider_id, "")
            if env_var and os.environ.get(env_var):
                self._set_cache("cloud_available", True)
                return True

        # 也检查 config.yaml 的 providers 段
        user_providers = self.config.get("providers", {})
        if isinstance(user_providers, dict):
            for provider_id in cloud_providers:
                if provider_id in user_providers:
                    self._set_cache("cloud_available", True)
                    return True

        self._set_cache("cloud_available", False)
        return False

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
        """根据任务复杂度选择 Ollama 模型。

        优先级：用户配置 > 内置默认。
        """
        if complexity == TaskComplexity.SIMPLE:
            return self.ollama_config.get("simple_model", OLLAMA_DEFAULT_SIMPLE_MODEL)
        elif complexity == TaskComplexity.MEDIUM:
            medium = self.ollama_config.get("medium_model")
            return medium if medium else None  # None 表示走云端
        else:
            complex_model = self.ollama_config.get("complex_model")
            return complex_model if complex_model else None

    def _select_cloud_model(self) -> str:
        """选择云端模型（取第一个可用的）。"""
        cloud_models = [
            ("deepseek", "deepseek-chat"),
            ("minimax", "minimax-m2"),
            ("kimi-for-coding", "kimi-k2"),
            ("zai", "glm-5.1"),
        ]

        import os
        for provider_id, model_id in cloud_models:
            env_var = f"{provider_id.upper().replace('-', '_')}_API_KEY"
            if os.environ.get(env_var):
                return f"{provider_id}:{model_id}"

        # Fallback: 检查 config
        user_providers = self.config.get("providers", {})
        if isinstance(user_providers, dict):
            for provider_id, model_id in cloud_models:
                if provider_id in user_providers:
                    return f"{provider_id}:{model_id}"

        return "deepseek:deepseek-chat"

    def _select_embedded_model(self, complexity: TaskComplexity) -> Optional[str]:
        """选择嵌入式模型。

        代码/推理任务 → qwen-coder-1.5b
        简单任务 → qwen-0.5b
        取第一个已安装的。
        """
        try:
            from hermes_cli.model_manager import get_available_embedded_model
            result = get_available_embedded_model()
            if result:
                return result.get("model_id")
        except ImportError:
            pass
        return None

    # -- 主路由 ---------------------------------------------------------------

    def route(
        self,
        user_message: str,
        force_tier: Optional[ModelTier] = None,
    ) -> RouteResult:
        """执行智能路由决策。

        Args:
            user_message: 用户消息文本。
            force_tier: 强制使用指定层级（忽略降级）。

        Returns:
            RouteResult 路由决策结果。
        """
        complexity = analyze_complexity(user_message)
        logger.debug("路由决策: complexity=%s, mode=%s", complexity.value, self.routing_mode)

        # 手动模式：直接使用指定的 provider/model
        if self.routing_mode == "manual":
            default_model = self.config.get("model", {}).get("default", "ollama:qwen3-vl:4b")
            provider, _, model = default_model.partition(":")
            return RouteResult(
                provider=provider or "ollama",
                model=model or "qwen3-vl:4b",
                tier=ModelTier.OLLAMA,
                reason="手动模式，使用默认配置",
            )

        # 强制嵌入式模式
        if force_tier == ModelTier.EMBEDDED or self.routing_mode == "embedded-only":
            model_id = self._select_embedded_model(complexity)
            if model_id:
                return RouteResult(
                    provider="embedded",
                    model=model_id,
                    tier=ModelTier.EMBEDDED,
                    reason=f"嵌入式模式 (复杂度: {complexity.value})",
                )
            return RouteResult(provider="", model="", tier=ModelTier.NONE,
                              reason="嵌入式模型未安装，请执行模型下载")

        # 强制云端模式
        if force_tier == ModelTier.CLOUD or self.routing_mode == "cloud-only":
            if self.check_cloud():
                cloud_sel = self._select_cloud_model()
                provider, _, model = cloud_sel.partition(":")
                return RouteResult(
                    provider=provider, model=model,
                    tier=ModelTier.CLOUD,
                    reason=f"云端模式 (复杂度: {complexity.value})",
                )
            return RouteResult(provider="", model="", tier=ModelTier.NONE,
                              reason="云端 API 不可用")

        # === 自动模式：三层降级路由 ===

        # Tier 1: Ollama
        if self.check_ollama():
            ollama_model = self._select_ollama_model(complexity)
            if ollama_model:
                return RouteResult(
                    provider="ollama",
                    model=ollama_model,
                    tier=ModelTier.OLLAMA,
                    reason=f"Ollama 本地推理 (复杂度: {complexity.value})",
                )
            # 中等和复杂任务 Ollama 未配置 → 降级到云端
            logger.debug("Ollama 在线但无匹配模型，降级到云端")

        # Tier 2: 云端
        if self.check_cloud():
            cloud_sel = self._select_cloud_model()
            provider, _, model = cloud_sel.partition(":")
            return RouteResult(
                provider=provider, model=model,
                tier=ModelTier.CLOUD,
                reason=f"云端 API (复杂度: {complexity.value})",
            )

        # Tier 3: 嵌入式兜底
        model_id = self._select_embedded_model(complexity)
        if model_id:
            return RouteResult(
                provider="embedded",
                model=model_id,
                tier=ModelTier.EMBEDDED,
                reason="无 Ollama / 无云端配置，启用嵌入式 CPU 推理兜底",
            )

        # 全部不可用
        return RouteResult(
            provider="", model="", tier=ModelTier.NONE,
            reason="无可用模型：请启动 Ollama 或配置云端 API Key 或下载嵌入式模型",
        )

    def route_with_config(
        self,
        user_message: str,
        provider_model_config: Optional[str] = None,
    ) -> RouteResult:
        """带用户配置的路由决策。

        优先使用用户指定的 provider:model，否则自动路由。

        Args:
            user_message: 用户消息。
            provider_model_config: 用户配置的 "provider:model" 字符串。

        Returns:
            RouteResult。
        """
        if provider_model_config and provider_model_config != "auto":
            provider, _, model = provider_model_config.partition(":")
            # 检测是否为嵌入式
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

    def status_report(self) -> Dict[str, Any]:
        """生成当前路由状态报告（中文）。"""
        return {
            "ollama": {
                "online": self.check_ollama(),
                "host": self.ollama_config.get("host", OLLAMA_DEFAULT_HOST),
                "port": self.ollama_config.get("port", OLLAMA_DEFAULT_PORT),
            },
            "cloud": {
                "available": self.check_cloud(),
            },
            "embedded": {
                "available": self.check_embedded(),
            },
            "routing_mode": self.routing_mode,
        }

    def print_status(self) -> str:
        """生成可读的中文状态报告。"""
        status = self.status_report()
        lines = ["=== 路由引擎状态 ==="]
        lines.append(f"模式: {status['routing_mode']}")
        lines.append(f"Ollama: {'✅ 在线' if status['ollama']['online'] else '❌ 离线'}")
        lines.append(f"云端 API: {'✅ 可用' if status['cloud']['available'] else '❌ 未配置'}")
        lines.append(f"嵌入式模型: {'✅ 可用' if status['embedded']['available'] else '❌ 未安装'}")
        return "\n".join(lines)


# -- 全局单例 ----------------------------------------------------------------

_router_instance: Optional[SmartRouter] = None


def get_router(config: Optional[Dict[str, Any]] = None) -> SmartRouter:
    """获取全局路由实例。

    Args:
        config: 配置字典（首次调用时提供）。

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
    """快速路由（使用全局实例，不返回 None 时调用方需自行创建实例）。"""
    router = get_router()
    if router is None:
        return RouteResult(
            provider="", model="", tier=ModelTier.NONE,
            reason="路由引擎未初始化",
        )
    return router.route(message)
