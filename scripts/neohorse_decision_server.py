#!/usr/bin/env python3
"""NeoHorse-Jev-4B 决策服务参考实现（Jev 决策层规划 §5b，stdlib-only HTTP 包装）。

配套文档: docs/plans/2026-09-25-jev-decision-layer-plan.md
运行位置: 独立 Linux 环境（GGUF runtime 构建完成后），不在 hermes 进程内。

用法:
    python scripts/neohorse_decision_server.py \
        --model ~/neohorse/NeoHorse-Jev-4B-Q4_K_M.gguf \
        --runtime-dir ~/neohorse/runtime --port 8001

接口:
    GET  /predict  -> 405
    GET  /health   -> {"ok": true, "model": ...}
    POST /predict  body: {"state": "...", "questions": {...}, "image_b64": "可选"}
                   -> NeoHorseGGUF.predict() 的 JSON 结果

注意: GGUF runtime 单实例一次一调用，本服务用全局锁串行化；勿并发压测。
若 import 失败，确认 --runtime-dir 指向含 runtime.py 与 libnh_*.so 的目录，
或 cd 到该目录后运行（与官方 example.py 同方式）。
"""

import argparse
import base64
import io
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_lock = threading.Lock()
_model = None
_model_label = None


def _keepalive_loop(model, interval_s: float) -> None:
    """空闲降频对策：小消费级 GPU（如笔记本 4060）在请求间隔数十秒后会
    掉到低功耗 P 态，下一次真实路由要付几百 ms 的拉频延迟。此线程定期跑
    一次微型决策把时钟摁在高位。模型自身锁是非阻塞的（并发报 Model busy），
    与真实请求重叠时本轮直接跳过。"""
    req = {"state": "ok", "questions": {"k": {"type": "noul",
            "instructions": "Is this ok?"}}}
    while True:
        time.sleep(interval_s)
        try:
            model.predict(req)
        except Exception:
            pass  # busy / transient — 下一轮再说


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "model": _model_label})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/predict":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            image = None
            if req.get("image_b64"):
                from PIL import Image
                image = Image.open(io.BytesIO(base64.b64decode(req["image_b64"])))
            request = {"state": req.get("state", ""),
                       "questions": req.get("questions", {})}
            with _lock:
                result = _model.predict(request, image)
            self._send(200, result)
        except BrokenPipeError:
            pass  # 客户端超时先走（如 hermes timeout_ms）——结果作废，别再写
        except Exception as exc:  # noqa: BLE001 — 单请求异常不应杀死服务
            try:
                self._send(500, {"error": repr(exc)})
            except OSError:
                pass

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[decision-server]", fmt % args, flush=True)


def main():
    global _model, _model_label
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="NeoHorse-Jev-4B GGUF 路径")
    ap.add_argument("--runtime-dir", required=True,
                    help="NeoHorse 仓库 runtime/ 目录（含 runtime.py 与 libnh_*.so）")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--keepalive-interval", type=float, default=60.0,
                    help="空闲时钟保持间隔秒数（0=关闭）；对空闲降频的消费级 GPU "
                         "可显著降低间歇性慢调用")
    args = ap.parse_args()

    sys.path.insert(0, args.runtime_dir)
    from runtime import NeoHorseGGUF  # noqa: E402 — 依赖 --runtime-dir

    _model = NeoHorseGGUF(args.model)
    _model_label = args.model
    if args.keepalive_interval > 0:
        threading.Thread(target=_keepalive_loop, args=(_model, args.keepalive_interval),
                         daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[decision-server] listening on {args.host}:{args.port}, model={args.model}",
          flush=True)
    try:
        server.serve_forever()
    finally:
        _model.close()


if __name__ == "__main__":
    main()
