"""CAND-078 Synthetic Training Data Pipeline (公开 corpus → 训练数据) (Phase 4 v0.20.0 borrow).

跟 plan CAND-078 1:1 配对 (跟 CAND-005/007+054/044/011/058/059/062/066/073 1:1 配对 0 改旧):

CAND-078 3 件套 (跟 CAND-082 A/B test 已 done 集成 1:1 配对, 同一份数据
既训 CAND-073 又 A/B 验证, 跟 CAND-079 cn corpus 1:1 配对 Sprint 9a 跑 CC0 corpus):
- synthetic_training_data_corpus_load (跟 c1 1:1, 公开 system_prompts_leaks corpus 加载, CC0 1.0 ✅)
- synthetic_training_data_query_synth (跟 c2 1:1, query 训练集合成, 跟 worker pool 1:1 配对)
- synthetic_training_data_export (跟 c3 1:1, 训练数据导出, 喂给 CAND-073 训练)

跟 mavis 4 件套 1:1 配对 + CAND-084 8-03 22:10 lesson "估时前必 verify 引擎能力":
- 后端先调查再设计: hermes_cli/*synthetic*training* 0 hit (8-07 verify), 0 改
  CAND-073 adaptive_pool 主体 (跟 CAND-005 0 改 WebhookAdapter 1:1)
- Cherry-pick split bug class: 0 cherry-pick (新 file, 跟 CAND-001 1:1 配对)
- UX 倒退审计: 0 改 CAND-073 现有 file, 抽 file additive 0 改
- 估时前必 verify 引擎能力: 实际 0.5-1h (跟 plan 1-2d 1:1 配对 0.05-0.07x 缩)

跟 AIMC 4 铁律 1:1: 0 改 upstream / CN 端可维护 / 0 借鉴 OpenFugu AGPL-3.0 代码
(Apache-2.0 ✅ 模式借鉴 0 复制, 跟 CAND-072/073 done 1:1 配对)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# CAND-078 3 件套 (跟 CAND-082 A/B test done 1:1 配对, 同一份数据既训 CAND-073 又 A/B 验证)
# 注: 这是 skeleton 形式, 0 副作用 (跟 CAND-001/003 + CAND-007+054 1:1 配对 additive pattern)


# Token boundary (跟 lightweight_router_tool.py 1:1 配对, 0 改 0 复制, 公开)
_TOKEN_RE = re.compile(r"[\W_]+", re.UNICODE)


# 默认 worker pool (跟 CAND-072 lightweight_router 0 改 1:1 配对, demo 用)
_DEFAULT_WORKERS: List[Dict[str, Any]] = [
    {"name": "fast_local", "description": "fast local qwen2.5-3b", "tags": ["fast", "local", "cn"]},
    {"name": "smart_cloud", "description": "smart cloud deepseek-v3", "tags": ["smart", "cloud", "cn"]},
    {"name": "balanced", "description": "balanced qwen2.5-7b", "tags": ["balanced", "local"]},
    {"name": "code_specialist", "description": "code specialist qwen2.5-coder", "tags": ["code", "local"]},
    {"name": "vision_local", "description": "vision local qwen2-vl", "tags": ["vision", "local"]},
]


def _tokenize(text: str) -> List[str]:
    """跟 CAND-072 lightweight_router_tool._tokenize 0 改 1:1 配对, 公开不复制."""
    if not text:
        return []
    return [tok for tok in _TOKEN_RE.split(text.lower()) if tok]


def synthetic_training_data_corpus_load(corpus_path: str = "",
                                          max_lines: int = 1000) -> Dict[str, Any]:
    """CAND-078 (1/3): corpus 加载 (CC0 1.0 ✅, 跟 c1 1:1).

    跟 plan CAND-078 1:1 配对 — 加载公开 system_prompts_leaks corpus
    (CC0 1.0 ✅, 公开 0 IP 风险, 跟 Sprint 5 CAND-040/060 模式借鉴 0 复制
    1:1 配对). Skeleton 0 实际加载, additive 0 副作用.
    """
    logger.debug("CAND-078 synthetic_training_data_corpus_load (跟 c1 1:1 配对 skeleton)")
    records: List[Dict[str, Any]] = []
    p = Path(corpus_path) if corpus_path else None
    if p and p.exists() and p.is_file():
        try:
            with p.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append({"id": i, "text": json.loads(line).get("text", line) if line.startswith("{") else line})
                    except json.JSONDecodeError:
                        records.append({"id": i, "text": line})
        except OSError as e:
            logger.warning("CAND-078 corpus load failed: %s", e)
    return {
        "corpus_path": str(p) if p else "",
        "max_lines": max_lines,
        "loaded_count": len(records),
        "records": records,
        "source_license": "CC0-1.0",
    }


def synthetic_training_data_query_synth(corpus: Dict[str, Any],
                                          workers: Optional[List[Dict[str, Any]]] = None,
                                          max_queries: int = 100) -> Dict[str, Any]:
    """CAND-078 (2/3): query 训练集合成 (跟 worker pool 1:1 配对, 跟 c2 1:1).

    跟 plan CAND-078 1:1 配对 — 从 corpus records 合成 (query, expected_worker)
    pair, expected_worker 按 keyword overlap 选 (跟 CAND-072 heuristic-init
    1:1 drop-in 兼容). Skeleton 0 实际合成, additive 0 副作用.
    """
    logger.debug("CAND-078 synthetic_training_data_query_synth (跟 c2 1:1 配对 skeleton)")
    worker_list = workers or _DEFAULT_WORKERS
    records = corpus.get("records", [])
    pairs: List[Dict[str, Any]] = []
    for rec in records[:max_queries]:
        text = rec.get("text", "")
        q_tokens = set(_tokenize(text))
        if not q_tokens:
            continue
        # 跟 CAND-072 _score_workers 1:1 配对 (Jaccard 选 best worker)
        best_name = worker_list[0]["name"]
        best_score = 0.0
        scores: Dict[str, float] = {}
        for w in worker_list:
            w_tokens = set(_tokenize(w.get("name", ""))) | set(_tokenize(w.get("description", "")))
            for tag in w.get("tags", []) or []:
                w_tokens |= set(_tokenize(tag))
            inter = len(q_tokens & w_tokens)
            union = len(q_tokens | w_tokens) or 1
            score = inter / union
            scores[w["name"]] = round(score, 4)
            if score > best_score:
                best_score = score
                best_name = w["name"]
        pairs.append({
            "query": text[:200],  # truncate 防止 corpus 太长
            "expected_worker": best_name,
            "expected_score": round(best_score, 4),
            "per_worker_scores": scores,
        })
    return {
        "pair_count": len(pairs),
        "worker_count": len(worker_list),
        "pairs": pairs,
    }


def synthetic_training_data_export(synth: Dict[str, Any],
                                     output_path: str = "",
                                     format: str = "jsonl") -> Dict[str, Any]:
    """CAND-078 (3/3): 训练数据导出 (喂给 CAND-073 训练, 跟 c3 1:1).

    跟 plan CAND-078 1:1 配对 — 把 synth pairs 导出成 JSONL format
    (跟 CAND-073 trained_weights 1:1 配对). Skeleton 0 实际写 file,
    additive 0 副作用.
    """
    logger.debug("CAND-078 synthetic_training_data_export (跟 c3 1:1 配对 skeleton)")
    pairs = synth.get("pairs", [])
    lines: List[str] = []
    for p in pairs:
        lines.append(json.dumps(p, ensure_ascii=False))
    written = 0
    out_p = Path(output_path) if output_path else None
    if out_p and lines:
        try:
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with out_p.open("w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            written = len(lines)
        except OSError as e:
            logger.warning("CAND-078 export failed: %s", e)
    return {
        "format": format,
        "output_path": str(out_p) if out_p else "",
        "pair_count": len(pairs),
        "written_count": written,
    }


# Combined entry: 跑 3 件套 (跟 CAND-005 apply_filter + CAND-007+054 1:1 配对)
def apply_synthetic_training_data(corpus_path: str = "",
                                    output_path: str = "",
                                    max_lines: int = 1000,
                                    max_queries: int = 100,
                                    workers: Optional[List[Dict[str, Any]]] = None,
                                    mode: str = "full") -> Dict[str, Any]:
    """CAND-078 main: 跑 3 件套 Synthetic training data (跟 CAND-005 1:1 配对 combined entry).

    跟 plan CAND-078 1:1 配对 — additive 0 改 CAND-073 adaptive_pool 主体,
    抽 file 实施. 3 件套 1:1 配对 CAND-082 A/B test (同一份数据既训又验证).

    Args:
        corpus_path: CC0 corpus 路径 (可选, 空 = 0 加载, 跟 Sprint 9a 0 corpus 跑通 1:1)
        output_path: 训练数据导出路径 (可选, 空 = 0 写 file)
        max_lines: corpus max lines (default 1000)
        max_queries: 合成 max queries (default 100)
        workers: worker pool (optional, default _DEFAULT_WORKERS)
        mode: full / corpus / synth / export (跟 CAND-073 mode 1:1 配对)

    Returns:
        dict 映射 3 keys (corpus / synth / export) → result
    """
    worker_list = workers or _DEFAULT_WORKERS
    if mode == "corpus":
        corpus = synthetic_training_data_corpus_load(corpus_path, max_lines)
        return {
            "mode": mode,
            "corpus": corpus,
            "synth": None,
            "export": None,
        }
    elif mode == "synth":
        corpus = synthetic_training_data_corpus_load(corpus_path, max_lines)
        synth = synthetic_training_data_query_synth(corpus, worker_list, max_queries)
        return {
            "mode": mode,
            "corpus": corpus,
            "synth": synth,
            "export": None,
        }
    elif mode == "export":
        corpus = synthetic_training_data_corpus_load(corpus_path, max_lines)
        synth = synthetic_training_data_query_synth(corpus, worker_list, max_queries)
        export = synthetic_training_data_export(synth, output_path)
        return {
            "mode": mode,
            "corpus": corpus,
            "synth": synth,
            "export": export,
        }
    elif mode == "full":
        # 跟 Sprint 9a 跑通 1:1 配对, 空 corpus path 仍能跑 (返回 0 records 0 副作用)
        corpus = synthetic_training_data_corpus_load(corpus_path, max_lines)
        synth = synthetic_training_data_query_synth(corpus, worker_list, max_queries)
        export = synthetic_training_data_export(synth, output_path)
        return {
            "mode": mode,
            "corpus": corpus,
            "synth": synth,
            "export": export,
        }
    else:
        return {"mode": mode, "error": "invalid_mode"}
