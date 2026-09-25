#!/usr/bin/env python3
"""NeoHorse-Jev 路由回放评测（Jev 决策层规划 Step 0/1，stdlib-only）。

从 hermes SessionDB 导出最近的真实用户 turn，构造路由 state 打决策服务
的 /predict（Choice 三档），输出 JSON 报告。

配套文档: docs/plans/2026-09-25-jev-decision-layer-plan.md（§5c / §6 Step 0-1）

用法（WSL 内，任意 python3 均可，无需 hermes 依赖）:
    python3 scripts/neohorse_replay_eval.py \
        --db /root/.hermes/state.db \
        --server http://127.0.0.1:8001 --allow-private \
        --limit 20 --days 21 \
        --out /root/neohorse/replay1

过滤规则: role=user、非斜杠命令、非注入消息、非 COMPACTION 参考块、
长度>=15 字符；按前 50 字符去重。state 超 384 token 时自动折半重试。

安全说明: 决策服务通常就在本机/内网，但脚本默认拒绝环回/私网/链路本地地址，
仅在操作者显式传 --allow-private 时放行（防误用为 SSRF 跳板）；协议仅允许
http/https；跟随重定向已禁用。
"""

import argparse
import json
import socket
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PREAMBLE = "你是 hermes-agent 的模型路由器。以下是用户本轮消息，判断应路由到哪个执行档位。"
QUESTION = {
    "tier": {
        "type": "choice",
        "instructions": "本轮用户消息应由哪个档位的模型执行？",
        "criteria": {
            "local": "本地小模型(Ollama 2B级)：简单查询/状态询问/机械改动/格式化，最便宜且足够。",
            "balanced": "中档模型(AIMC tier:balanced)：常规编码/调试/多步工具任务/带报错信息的排查。",
            "strong": "旗舰模型(AIMC tier:strong)：复杂推理/方案设计/长文创作/新功能实现/疑难杂症。",
        },
    }
}
EXCLUDE_PREFIXES = ("<", "[CONTEXT COMPACTION")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def validate_server_url(server: str, allow_private: bool) -> str:
    parsed = urllib.parse.urlparse(server)
    if parsed.scheme not in ("http", "https"):
        raise SystemExit(f"仅允许 http/https，收到: {parsed.scheme!r}")
    if not parsed.hostname:
        raise SystemExit("缺少主机名")
    infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    for info in infos:
        ip = info[4][0]
        if ipaddress_is_restricted(ip) and not allow_private:
            raise SystemExit(
                f"目标解析到受限地址 {ip}（环回/私网/链路本地）。"
                "决策服务在本机/内网属预期场景，请显式加 --allow-private 放行。"
            )
    return server


def ipaddress_is_restricted(ip: str) -> bool:
    import ipaddress

    addr = ipaddress.ip_address(ip)
    return (
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def fetch_messages(db_path: str, days: int, limit: int):
    since = time.time() - days * 86400
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = con.execute(
        """
        SELECT m.timestamp, s.source, m.content
        FROM messages m JOIN sessions s ON m.session_id = s.id
        WHERE m.role = 'user'
          AND m.timestamp > ?
          AND length(m.content) >= 15
        ORDER BY m.timestamp DESC LIMIT 400
        """,
        (since,),
    ).fetchall()
    con.close()
    seen, out = set(), []
    for ts, source, content in rows:
        text = content.strip()
        if text.startswith("/") or any(text.startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        key = text[:50]
        if key in seen:
            continue
        seen.add(key)
        out.append({"timestamp": ts, "source": source, "content": text})
        if len(out) >= limit:
            break
    out.reverse()  # 时间正序
    return out


def clamp_state(text: str, budget: int) -> str:
    text = " ".join(text.split())
    if len(text) <= budget:
        return text
    head, tail = int(budget * 0.75), int(budget * 0.2)
    return text[:head] + " ……[截断] " + text[-tail:]


def predict(server: str, state: str):
    body = json.dumps({"state": f"{PREAMBLE}\n{state}", "questions": QUESTION}).encode()
    req = urllib.request.Request(
        f"{server}/predict", data=body, headers={"Content-Type": "application/json"}
    )
    opener = urllib.request.build_opener(_NoRedirect)
    t0 = time.time()
    with opener.open(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result, (time.time() - t0) * 1000


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="/root/.hermes/state.db")
    ap.add_argument("--server", default="http://127.0.0.1:8001")
    ap.add_argument("--allow-private", action="store_true",
                    help="显式放行环回/私网目标（决策服务在本机/内网的预期场景）")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--max-state-chars", type=int, default=300,
                    help="state 字符预算（384 token 上限的保守近似）")
    ap.add_argument("--out", default="/root/neohorse/replay")
    args = ap.parse_args()

    server = validate_server_url(args.server, args.allow_private)

    msgs = fetch_messages(args.db, args.days, args.limit)
    print(f"exported {len(msgs)} messages from {args.db}")

    records = []
    for i, m in enumerate(msgs):
        state = clamp_state(m["content"], args.max_state_chars)
        try:
            result, ms = predict(server, state)
        except Exception as exc:  # 超长等运行时错误 → 折半重试一次
            state = clamp_state(m["content"], args.max_state_chars // 2)
            try:
                result, ms = predict(server, state)
            except Exception as exc2:
                records.append({**m, "index": i, "error": repr(exc2)})
                continue
        ans = result["answers"]["tier"]
        records.append({
            "index": i,
            "timestamp": m["timestamp"],
            "time": time.strftime("%m-%d %H:%M", time.localtime(m["timestamp"])),
            "source": m["source"],
            "content": m["content"],
            "state_chars": len(state),
            "input_tokens": result.get("input_tokens"),
            "jev_tier": ans["choice"],
            "probabilities": ans["probabilities"],
            "confidence": ans.get("confidence"),
            "latency_ms": round(ms, 1),
        })
        print(f"[{i:02d}] {records[-1]['time']} jev={ans['choice']:8s} "
              f"conf={ans.get('confidence', 0):.3f} {ms:.0f}ms {m['content'][:40]!r}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = [r for r in records if "error" not in r]
    errors = len(records) - len(ok)
    print(f"\ndone: {len(ok)} ok, {errors} errors -> {out.with_suffix('.json')}")
    if errors:
        print("(errors recorded in json; 检查后可重跑)")


if __name__ == "__main__":
    main()
