"""Retrieval evaluation for Lantern sample corpus (hit@k).

Uses an isolated Chroma directory so the live app library is not wiped.

Usage (from rag-chatbot/):
  .\\.venv\\Scripts\\python scripts\\evaluate_retrieval.py
  .\\.venv\\Scripts\\python scripts\\evaluate_retrieval.py --k 4
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
EVAL_CHROMA = ROOT / "data" / "chroma_eval"
EVAL_UPLOADS = ROOT / "data" / "uploads_eval"
CASES_PATH = Path(__file__).resolve().parent / "eval_cases.json"
RESULTS_MD = ROOT / "data" / "eval_results.md"
RESULTS_JSON = ROOT / "data" / "eval_results.json"


def _hit(chunks: list, case: dict) -> tuple[bool, str]:
    expected = {f.lower() for f in case.get("expected_files", [])}
    needles = [n.lower() for n in case.get("must_include_any", [])]

    filenames = [(c.filename or "").lower() for c in chunks]
    joined = "\n".join((c.text or "").lower() for c in chunks)

    file_ok = any(any(exp in name for exp in expected) for name in filenames) if expected else True
    text_ok = any(n in joined for n in needles) if needles else True
    ok = file_ok and text_ok

    top = ", ".join(f"{c.filename} ({c.score:.2f})" for c in chunks[:3]) or "(none)"
    reason = "file+text" if ok else ("file miss" if not file_ok else "text miss")
    return ok, f"{reason} | top: {top}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Lantern retrieval hit@k")
    parser.add_argument("--k", type=int, default=4, help="top-k passages")
    args = parser.parse_args()

    # Isolate eval index before importing app modules.
    if EVAL_CHROMA.exists():
        shutil.rmtree(EVAL_CHROMA, ignore_errors=True)
    if EVAL_UPLOADS.exists():
        shutil.rmtree(EVAL_UPLOADS, ignore_errors=True)
    EVAL_CHROMA.mkdir(parents=True, exist_ok=True)
    EVAL_UPLOADS.mkdir(parents=True, exist_ok=True)

    import os

    os.environ["LANTERN_CHROMA_DIR"] = str(EVAL_CHROMA)
    os.environ["LANTERN_UPLOAD_DIR"] = str(EVAL_UPLOADS)
    sys.path.insert(0, str(BACKEND))

    from app.config import SAMPLE_DIR, clear_settings_cache
    from app.rag import store

    clear_settings_cache()
    store._client = None
    store._embedder = None

    sample_files = sorted(
        [
            p
            for p in SAMPLE_DIR.glob("*")
            if p.suffix.lower() in {".md", ".txt", ".markdown", ".pdf"} and p.is_file()
        ]
    )
    if not sample_files:
        print("No sample docs found.")
        return 1

    print(f"Indexing {len(sample_files)} sample docs into {EVAL_CHROMA} ...")
    for src in sample_files:
        target = EVAL_UPLOADS / src.name
        target.write_bytes(src.read_bytes())
        info = store.ingest_file(target, original_name=src.name)
        print(f"  + {info.filename} ({info.chunks} chunks)")

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    rows = []
    hits = 0

    print(f"\nRunning {len(cases)} queries at k={args.k} ...")
    for case in cases:
        chunks = store.retrieve(case["question"], top_k=args.k)
        ok, detail = _hit(chunks, case)
        hits += int(ok)
        rows.append(
            {
                "id": case["id"],
                "question": case["question"],
                "hit": ok,
                "detail": detail,
                "top_files": [c.filename for c in chunks],
                "top_scores": [c.score for c in chunks],
            }
        )
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {case['id']}: {case['question']}")

    total = len(cases)
    hit_rate = hits / total if total else 0.0
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md_lines = [
        "# Lantern Retrieval Evaluation",
        "",
        f"- Generated: **{stamp}**",
        f"- Corpus: `{SAMPLE_DIR.relative_to(ROOT)}` ({len(sample_files)} files)",
        f"- Metric: **hit@{args.k}** (expected filename match AND keyword evidence)",
        f"- Result: **{hits}/{total} = {hit_rate:.0%}**",
        "",
        "| ID | Question | Hit@{} | Notes |".format(args.k),
        "|----|----------|--------|-------|",
    ]
    for row in rows:
        q = row["question"].replace("|", "\\|")
        md_lines.append(
            f"| {row['id']} | {q} | {'PASS' if row['hit'] else 'FAIL'} | {row['detail']} |"
        )
    md_lines.extend(
        [
            "",
            "## How to re-run",
            "```powershell",
            "cd rag-chatbot",
            ".\\.venv\\Scripts\\python scripts\\evaluate_retrieval.py --k 4",
            "```",
            "",
        ]
    )
    RESULTS_MD.write_text("\n".join(md_lines), encoding="utf-8")
    RESULTS_JSON.write_text(
        json.dumps(
            {
                "generated_at": stamp,
                "k": args.k,
                "hits": hits,
                "total": total,
                "hit_rate": hit_rate,
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nHit@{args.k}: {hits}/{total} ({hit_rate:.0%})")
    print(f"Wrote {RESULTS_MD}")
    print(f"Wrote {RESULTS_JSON}")
    return 0 if hits == total else 0  # always 0 exit for demo; failures shown in table


if __name__ == "__main__":
    raise SystemExit(main())
