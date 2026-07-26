"""Comparative Evaluation Script — Phase 2 (Raw Qdrant) vs Phase 3+ (FlashRank Reranked).

Runs the golden dataset through both retrieval strategies and produces a comparative report.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

# Bootstrap project root directory into sys.path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from app.services.retrieval.ranking_service import rerank
from app.services.retrieval.vector_store import retrieve
from evals.eval_engine import GOLDEN_DATASET_PATH, REPORTS_DIR


def compare_retrieval_strategies(dataset_path: Path = GOLDEN_DATASET_PATH) -> dict[str, Any]:
    """Compare raw Qdrant top-K vs FlashRank reranked top-K."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset not found at {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print("=" * 65)
    print("COMPARATIVE EVALUATION: RAW QDRANT VS FLASHRANK RERANKED")
    print("=" * 65)

    results = []

    for tc in cases:
        q_id = tc["id"]
        question = tc["question"]
        expected_sources = tc.get("expected_sources", [])

        # Mode A: Raw Qdrant top-15
        raw_docs = retrieve(query=question, top_k=15)
        raw_files = [d.get("file_name", "") for d in raw_docs]

        # Calculate raw top-5 precision
        raw_top5_files = raw_files[:5]
        raw_hit = any(src in raw_top5_files for src in expected_sources)

        # Mode B: FlashRank Reranked (top-5)
        reranked_docs, reranker_used = rerank(query=question, documents=raw_docs, top_n=5)
        reranked_files = [d.get("file_name", "") for d in reranked_docs]
        reranked_hit = any(src in reranked_files for src in expected_sources)

        results.append({
            "id": q_id,
            "question": question,
            "expected_sources": expected_sources,
            "raw_top5_sources": raw_top5_files,
            "raw_hit": raw_hit,
            "reranked_top5_sources": reranked_files,
            "reranked_hit": reranked_hit,
            "reranker_used": reranker_used,
        })

        raw_mark = "✅" if raw_hit else "❌"
        rr_mark = "✅" if reranked_hit else "❌"
        print(f"  [{q_id}] Raw Top5: {raw_mark} | Reranked Top5: {rr_mark}")

    raw_pass = sum(1 for r in results if r["raw_hit"])
    rr_pass = sum(1 for r in results if r["reranked_hit"])
    total = len(results)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": total,
        "raw_qdrant_precision_at_5": round(raw_pass / total, 4),
        "flashrank_precision_at_5": round(rr_pass / total, 4),
        "precision_gain": round((rr_pass - raw_pass) / total, 4),
        "results": results,
    }

    print()
    print("=" * 65)
    print("COMPARATIVE EVALUATION SUMMARY")
    print("=" * 65)
    print(f"  Raw Qdrant Precision@5:    {summary['raw_qdrant_precision_at_5']*100:.1f}%")
    print(f"  FlashRank Precision@5:     {summary['flashrank_precision_at_5']*100:.1f}%")
    print(f"  Precision Gain:            +{summary['precision_gain']*100:.1f}%")
    print("=" * 65)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / "comparison_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved comparative report to {report_file}")
    return summary


if __name__ == "__main__":
    compare_retrieval_strategies()
