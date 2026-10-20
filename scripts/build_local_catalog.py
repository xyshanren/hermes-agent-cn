#!/usr/bin/env python3
"""Build CN's local-runtime catalog entries from GGUF headers (measured).

The upstream catalog (``hermes_cli/local_runtime/catalog.json``) carries the
estimator inputs for every model it lists — ``n_ctx_train``, ``full_layers``,
``recurrent_layers``, ``per_layer_f16``, ``n_vocab`` — so the picker can price
a model BEFORE the user downloads gigabytes. Those numbers come from the GGUF
header, so this script reads the header of each candidate model and emits an
entry in the upstream schema.

CN's models live on ModelScope (HF is not reliably reachable from China), so
the fetcher asks ModelScope's file API first and falls back to Hugging Face.
Only the header is fetched (HTTP Range), never the whole model.

Network safety: every URL is checked against an explicit host allowlist and
the repository's own SSRF guard (``tools.url_safety.is_safe_url``) before the
request goes out; redirects are not followed.

Usage:
    python scripts/build_local_catalog.py \
        --candidates scripts/local_catalog_candidates_cn.json \
        --out hermes_cli/local_runtime/catalog_cn.json

    # a single model from a local file (offline):
    python scripts/build_local_catalog.py --local /path/to/model.gguf
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hermes_cli.local_runtime.estimator import profile_from_gguf  # noqa: E402
from hermes_cli.local_runtime.gguf import read_gguf_header  # noqa: E402
from tools.url_safety import is_safe_url  # noqa: E402

# Metadata + tensor table normally live in the first few megabytes; a bigger
# window costs a few MB of download and makes truncation far less likely.
HEADER_BYTES = 12 * 1024 * 1024

USER_AGENT = "hermes-cn-catalog-builder/1.0"
MODELSCOPE_FILE_API = (
    "https://www.modelscope.cn/api/v1/models/{repo}/repo?Revision=master&FilePath={path}"
)
HF_RESOLVE = "https://huggingface.co/{repo}/resolve/main/{path}"

# Hosts this builder may talk to. ModelScope hands out CDN hosts for the file
# itself, so its domains are allowed by suffix; everything else is refused.
ALLOWED_HOST_SUFFIXES = (
    ".modelscope.cn",
    ".huggingface.co",
    ".hf.co",
)


def validate_url(url: str) -> str:
    """Return *url* when it is safe to fetch, else raise.

    Three gates: https only, an explicit host allowlist, and the repository's
    own SSRF guard (which refuses loopback / private / link-local targets).
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"refusing non-https URL: {url}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError(f"refusing URL without host: {url}")
    if not (host == "modelscope.cn" or host.endswith(ALLOWED_HOST_SUFFIXES)):
        raise ValueError(f"host not in the allowlist: {host}")
    if not is_safe_url(url):
        raise ValueError(f"refused by the SSRF guard: {url}")
    return url


def _fetch_range(url: str, limit: int = HEADER_BYTES) -> bytes:
    """Read at most ``limit`` bytes from *url* (HTTP Range).

    ModelScope answers the file API with a redirect to its CDN host, so
    redirects ARE followed — but every hop is re-validated against the
    allowlist and the SSRF guard before the request goes out.
    """
    validate_url(url)
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{limit - 1}"}
    )
    opener = urllib.request.build_opener(_ValidatingRedirect())
    with opener.open(req, timeout=60) as resp:
        chunks = []
        got = 0
        while got < limit:
            block = resp.read(min(65536, limit - got))
            if not block:
                break
            chunks.append(block)
            got += len(block)
        return b"".join(chunks)


class _ValidatingRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when the new target passes the same checks."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _modelscope_files(repo: str) -> list[dict]:
    """List a ModelScope repo's files (path, size, revision)."""
    url = f"https://www.modelscope.cn/api/v1/models/{repo}/repo/files?Revision=master"
    validate_url(url)
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30
    ) as resp:
        doc = json.load(resp)
    return (doc.get("Data") or {}).get("Files") or []


def discover_file(repo: str, quant: str, source: str) -> list[tuple[str, int, str]]:
    """Pick the GGUF file(s) for *quant* inside *repo*.

    Returns [(path, size_bytes, revision), ...] — one entry per part for a
    split model. Vision projectors (mmproj) are skipped: they are a separate
    asset, not the model.
    """
    if source == "modelscope":
        files = _modelscope_files(repo)
        wanted = quant.upper().replace("-", "_")
        best = None
        for f in files:
            path = f.get("Path") or ""
            name = path.rsplit("/", 1)[-1]
            if not name.endswith(".gguf") or "mmproj" in name.lower():
                continue
            if wanted in name.upper().replace("-", "_"):
                best = f
                break
        if best is None:
            ggufs = [
                f for f in files
                if (f.get("Path") or "").endswith(".gguf")
                and "mmproj" not in (f.get("Path") or "").lower()
            ]
            if not ggufs:
                raise ValueError(f"no GGUF file in {repo}")
            best = ggufs[0]
        path = best.get("Path") or ""
        revision = best.get("Revision") or "master"
        # A split model ships as "<stem>-00001-of-000NN.gguf"; upstream lists
        # EVERY part as its own file entry, so collect the siblings.
        parts = [(path, int(best.get("Size") or 0), revision)]
        if "-00001-of-" in path:
            stem = path.rsplit("-00001-of-", 1)[0]
            for f in files:
                fpath = f.get("Path") or ""
                if fpath.startswith(stem) and fpath.endswith(".gguf") and fpath != path:
                    parts.append((fpath, int(f.get("Size") or 0),
                                  f.get("Revision") or revision))
            parts.sort()
        return parts
    raise ValueError("Hugging Face discovery needs an explicit file path")


def resolve_url(repo: str, path: str, source: str) -> str:
    """Direct download URL for one file (ModelScope first, then Hugging Face).

    ModelScope's file API answers with a redirect to its CDN, which
    ``_fetch_range`` follows after validating the hop.
    """
    if source == "modelscope":
        return validate_url(MODELSCOPE_FILE_API.format(repo=repo, path=path))
    return validate_url(HF_RESOLVE.format(repo=repo, path=path))


def measure(header) -> dict:
    """Numeric catalog scalars measured from one GGUF header.

    Uses the estimator's own profile so the catalog numbers and the runtime
    pricing cannot drift apart.
    """
    profile = profile_from_gguf(header)
    recurrent = 0
    full_values = []
    for kind, kv_bytes in profile.layers:
        if getattr(kind, "name", "") == "RECURRENT":
            recurrent += 1
        else:
            full_values.append(kv_bytes)
    per_layer_f16 = max(full_values) if full_values else 0
    n_ctx_train = int(header.metadata.get(f"{header.architecture}.context_length") or 0)
    return {
        "n_ctx_train": n_ctx_train,
        "lazy_bytes": int(header.lazy_bytes or 0),
        "full_layers": len(full_values),
        "recurrent_layers": recurrent,
        "per_layer_f16": per_layer_f16,
        "n_vocab": int(header.n_vocab or 0),
        "architecture": header.architecture,
    }


def entry_for(candidate: dict, measured: dict, parts: list[tuple[str, int, str]]) -> dict:
    """One catalog entry in the upstream schema."""
    entry = {
        "id": candidate["id"],
        "display_name": candidate.get("display_name", candidate["id"]),
        "description": candidate.get("description", ""),
        "repo": candidate["repo"],
        "variants": [
            {
                "quant": candidate.get("quant", "Q4_K_M"),
                "validated": bool(candidate.get("validated", False)),
                "files": [
                    {"path": p, "size_bytes": int(sz), "revision": rev}
                    for p, sz, rev in parts
                ],
            }
        ],
    }
    entry.update(measured)
    for key in ("moe", "mtp", "mtp_draft_depth", "swa_layers", "swa_window",
                "min_engine", "quality", "decode_fraction", "recommend", "sampling"):
        if key in candidate:
            entry[key] = candidate[key]
    if "mmproj" in candidate:
        entry["mmproj"] = candidate["mmproj"]
    return entry


def _content_length(url: str) -> int:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"}
        )
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(req, timeout=30) as resp:
            cr = resp.headers.get("Content-Range", "")
            if "/" in cr:
                return int(cr.rsplit("/", 1)[1])
    except Exception:  # noqa: BLE001 - size is best-effort metadata
        pass
    return 0


def build(candidates: list[dict], out_path: Path) -> int:
    entries = []
    for cand in candidates:
        print(f"- {cand['id']} ({cand.get('source', 'modelscope')}:{cand['repo']})")
        try:
            source = cand.get("source", "modelscope")
            if cand.get("file"):
                parts = [(cand["file"], int(cand.get("size_bytes") or 0), "master")]
            else:
                parts = discover_file(cand["repo"], cand.get("quant", "Q4_K_M"), source)
            path = parts[0][0]
            url = resolve_url(cand["repo"], path, source)
            head = _fetch_range(url)
            with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as tmp:
                tmp.write(head)
                tmp_path = tmp.name
            try:
                header = read_gguf_header(tmp_path)
            finally:
                os.unlink(tmp_path)
            measured = measure(header)
            if not parts[0][1]:
                parts = [(p, _content_length(url) if p == path else sz, rev)
                         for p, sz, rev in parts]
            entry = entry_for(cand, measured, parts)
            entries.append(entry)
            print(f"  ok: {measured} ({path})")
        except Exception as exc:  # noqa: BLE001 - one bad model must not stop the build
            print(f"  ! skipped: {exc}", file=sys.stderr)
    doc = {"schema_version": 3, "models": entries}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out_path} ({len(entries)} models)")
    return 0 if entries else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", type=Path, help="candidate list (JSON)")
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "hermes_cli" / "local_runtime" / "catalog_cn.json")
    ap.add_argument("--local", type=Path, help="measure one local GGUF file")
    args = ap.parse_args()

    if args.local:
        header = read_gguf_header(args.local)
        print(json.dumps(measure(header), ensure_ascii=False, indent=2))
        return 0
    if not args.candidates:
        ap.error("--candidates or --local is required")
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    return build(candidates, args.out)


if __name__ == "__main__":
    sys.exit(main())
