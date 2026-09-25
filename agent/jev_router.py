"""Jev 决策通道客户端（model routing consumer #1）。

调用本机常驻的 NeoHorse-Jev-4B 决策服务（prefill-only 概率决策），为每
用户轮产出 light/balanced/strong/flagship 档位建议；置信度不足或服务不可
达时由调用方回落基线（model_routing 默认规则），绝不阻塞请求。

规划与验证记录: docs/plans/2026-09-25-jev-decision-layer-plan.md（§6 Step 2）。

config（model_routing.decision，用户 YAML 直读，与 model_routing.rules 同层）:
    mode: off | shadow | live      # 默认 off；shadow=只记日志，live 由调用方按 threshold 采纳
    endpoint: http://127.0.0.1:8001
    threshold: 0.6                 # conf >= threshold 才采纳（调用方使用）
    timeout_ms: 500
    failure_threshold: 5           # 连续失败 N 次进入冷却（熔断）
    cooldown_seconds: 300          # 冷却时长（期间直接回落，不发请求）
    allow_private: true            # 决策服务在本机/内网时的显式放行

安全: endpoint 仅接受 http/https；默认拒绝解析到环回/私网/链路本地的目标，
操作员以 allow_private 显式放行（防误配为 SSRF 跳板）。
"""

import ipaddress
import json
import logging
import socket
import threading
import time
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

#: 通用路由阶梯（vision 组任务型，不在此列）。
LADDER_TIERS = ("light", "balanced", "strong", "flagship")

_STATE_BUDGET_CHARS = 300  # 384-token 上限的保守字符近似
_PREV_EXCERPT_CHARS = 100
_PREAMBLE = (
    "你是 hermes-agent 的模型路由器。"
    "以下是用户本轮消息（可能附上一轮摘要作上下文），判断应路由到哪个执行档位。"
)
_QUESTION = {
    "tier": {
        "type": "choice",
        "instructions": "本轮用户消息应由哪个档位的模型执行？",
        "criteria": {
            "light": "免费小模型(glm-4.7-flash/qwen3-8b级)：状态询问、确认类追问、单步查询、纯文本问答、机械格式化——几乎不需要多步工具编排。",
            "balanced": "中档agent级模型(minimax-m3/deepseek-v3级)：常规编码、调试、多步工具任务、带报错信息的排查、常规运维操作(卸载/清理/检查服务)。",
            "strong": "强模型：复杂推理、疑难排查、跨模块重构、多文件方案实施。",
            "flagship": "最强模型：大型方案设计、长文创作、复杂新功能实现、高难度技术攻关。",
        },
    }
}
_EXCLUDE_PREFIXES = ("<", "[CONTEXT COMPACTION")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


# ── 熔断状态（进程内；gateway 多会话并发下加锁） ──────────────────────────
_LOCK = threading.Lock()
_FAIL_STREAK = 0
_COOLDOWN_UNTIL = 0.0

_ENDPOINT_OK_CACHE: dict = {}


def clamp_head(text: str, budget: int) -> str:
    """压成单行并保头截尾到 budget 字符。"""
    text = " ".join((text or "").split())
    if len(text) <= budget:
        return text
    return text[:budget] + "……"


def _usable_turn_text(text: str) -> str:
    """过滤不适合作为路由信号的 turn（斜杠命令 / 注入参考块）。"""
    text = (text or "").strip()
    if not text or text.startswith("/") or any(text.startswith(p) for p in _EXCLUDE_PREFIXES):
        return ""
    return text


def build_state(user_text: str, prev_user_text: str = "",
                budget: int = _STATE_BUDGET_CHARS) -> str:
    """生产 state v1：当前消息为主，多轮追问前置上一轮摘录。

    任务类型信号（创作/方案/实现/升级评估）倾向出现在消息头部，截断保头。
    """
    state = _usable_turn_text(user_text)
    prev = _usable_turn_text(prev_user_text)
    if prev:
        state = f"[上一轮] {clamp_head(prev, _PREV_EXCERPT_CHARS)}\n[本轮] {state}"
    return clamp_head(state, budget)


def _endpoint_allowed(endpoint: str, allow_private: bool) -> bool:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        logger.info("jev_router: invalid endpoint %r", endpoint)
        return False
    cache_key = (endpoint, allow_private)
    cached = _ENDPOINT_OK_CACHE.get(cache_key)
    if cached is not None:
        return cached
    allowed = True
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 80)
    except OSError as exc:
        logger.info("jev_router: endpoint resolve failed %r (%s)", endpoint, exc)
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            if not allow_private:
                logger.info(
                    "jev_router: endpoint %r resolves to restricted %s; "
                    "set decision.allow_private: true to permit",
                    endpoint, ip,
                )
                allowed = False
            break
    _ENDPOINT_OK_CACHE[cache_key] = allowed
    return allowed


def _http_post_json(url: str, body: bytes, timeout_ms: int) -> dict:
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(req, timeout=max(timeout_ms / 1000.0, 0.05)) as resp:
        return json.loads(resp.read())


def decide(decision_cfg: dict, user_text: str, prev_user_text: str = "",
           *, _clock=time.monotonic, _post=None):
    """调决策服务产出档位建议；不可用一律返回 None（fail-open）。

    返回 {"tier": str, "confidence": float, "probabilities": dict,
          "latency_ms": float}；采纳与否（threshold/mode）由调用方决定。
    """
    if not isinstance(decision_cfg, dict):
        return None
    endpoint = str(decision_cfg.get("endpoint", "http://127.0.0.1:8001")).rstrip("/")
    timeout_ms = int(decision_cfg.get("timeout_ms", 500))
    failure_threshold = int(decision_cfg.get("failure_threshold", 5))
    cooldown_seconds = float(decision_cfg.get("cooldown_seconds", 300))

    if not _endpoint_allowed(endpoint, bool(decision_cfg.get("allow_private", False))):
        return None

    global _FAIL_STREAK, _COOLDOWN_UNTIL
    with _LOCK:
        if _FAIL_STREAK >= failure_threshold and _clock() < _COOLDOWN_UNTIL:
            return None  # 熔断冷却中：直接回落，不发请求

    state = build_state(user_text, prev_user_text)
    body = json.dumps({"state": f"{_PREAMBLE}\n{state}", "questions": _QUESTION}).encode("utf-8")

    post = _post or _http_post_json
    started = time.monotonic()
    try:
        payload = post(endpoint + "/predict", body, timeout_ms)
    except Exception as exc:
        with _LOCK:
            _FAIL_STREAK += 1
            streak = _FAIL_STREAK
            if _FAIL_STREAK >= failure_threshold:
                _COOLDOWN_UNTIL = _clock() + cooldown_seconds
        logger.info("jev_router: call failed (%s); fail_streak=%d", exc, streak)
        return None
    latency_ms = (time.monotonic() - started) * 1000.0
    with _LOCK:
        _FAIL_STREAK = 0
        _COOLDOWN_UNTIL = 0.0

    answers = (payload or {}).get("answers") or {}
    tier_answer = answers.get("tier") or {}
    tier = tier_answer.get("choice")
    if tier not in LADDER_TIERS:
        logger.info("jev_router: unexpected tier %r; ignoring", tier)
        return None
    return {
        "tier": tier,
        "confidence": float(tier_answer.get("confidence") or 0.0),
        "probabilities": tier_answer.get("probabilities") or {},
        "latency_ms": latency_ms,
    }
