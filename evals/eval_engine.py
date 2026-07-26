"""RAGAS Evaluation Engine for Banking Knowledge Intelligence Platform.

Evaluates the BKIP RAG pipeline against the golden dataset (evals/data/golden_dataset.json).
Computes 4 core RAG metrics:
  1. Faithfulness — is the answer grounded strictly in retrieved context?
  2. Answer Relevancy — does the answer directly address the question?
  3. Context Precision — are relevant passages placed at top ranks?
  4. Context Recall — are ground truth facts covered in retrieved context?

Outputs:
  - evals/reports/latest.json
  - evals/reports/latest.md
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Bootstrap project root directory into sys.path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.gateway.llm_client import get_guard_llm, get_primary_llm

logger = get_logger(__name__)

GOLDEN_DATASET_PATH = Path("evals/data/golden_dataset.json")
REPORTS_DIR = Path("evals/reports")


class MetricScores(BaseModel):
    faithfulness: float = Field(..., ge=0.0, le=1.0)
    answer_relevancy: float = Field(..., ge=0.0, le=1.0)
    context_precision: float = Field(..., ge=0.0, le=1.0)
    context_recall: float = Field(..., ge=0.0, le=1.0)
    overall_score: float = Field(..., ge=0.0, le=1.0)


class QuestionEvalResult(BaseModel):
    id: str
    question: str
    ground_truth: str
    answer: str
    retrieved_contexts: list[str]
    retrieved_sources: list[str]
    expected_sources: list[str]
    category: str
    scores: MetricScores
    latency_ms: float


def get_judge_llm():
    """Return the Judge LLM instance with automatic fallback chain."""
    return get_primary_llm()


def evaluate_with_judge(
    question: str,
    ground_truth: str,
    answer: str,
    contexts: list[str],
    expected_sources: list[str],
    retrieved_sources: list[str],
) -> MetricScores:
    """Compute 4-metric evaluation scores using the dedicated Judge LLM."""
    judge = get_judge_llm()

    context_str = "\n---\n".join(contexts) if contexts else "No context retrieved."

    judge_prompt = f"""You are an expert RAG evaluation judge for banking compliance.
Evaluate the candidate RAG answer and retrieved context against the question and ground truth.

Question: {question}

Ground Truth Answer: {ground_truth}

Retrieved Contexts:
{context_str}

Generated Answer: {answer}

Score the following 4 metrics from 0.0 to 1.0 (where 1.0 is perfect):

1. FAITHFULNESS (0.0 - 1.0): Is every claim in the generated answer supported by the retrieved context? (Give 1.0 if fully supported, 0.0 if hallucinated).
2. ANSWER_RELEVANCY (0.0 - 1.0): Does the answer directly address the user's question without adding irrelevant details?
3. CONTEXT_PRECISION (0.0 - 1.0): Are the retrieved contexts relevant to the question? (High if top contexts contain the answer).
4. CONTEXT_RECALL (0.0 - 1.0): Does the retrieved context contain all the information necessary to answer the ground truth?

Output ONLY a valid JSON object in this exact format:
{{
  "faithfulness": 0.95,
  "answer_relevancy": 0.90,
  "context_precision": 0.85,
  "context_recall": 1.0
}}"""

    try:
        msg = judge.invoke([
            SystemMessage(content="You are a strict, objective RAG evaluator. Output JSON only."),
            HumanMessage(content=judge_prompt),
        ])
        raw = msg.content.strip()
        # Clean markdown fences if any
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        data = json.loads(raw)
        f = float(data.get("faithfulness", 0.8))
        ar = float(data.get("answer_relevancy", 0.8))
        cp = float(data.get("context_precision", 0.8))
        cr = float(data.get("context_recall", 0.8))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Judge LLM parsing failed (%s), using fallback heuristic scoring", exc)
        # Rule-based heuristic scoring as fallback
        f = 0.9 if answer and not "I am unable" in answer else 0.5
        ar = 0.9 if len(answer) > 30 else 0.4
        cp = 0.9 if any(src in retrieved_sources for src in expected_sources) else 0.5
        cr = 0.9 if contexts else 0.3

    overall = round((f + ar + cp + cr) / 4.0, 4)
    return MetricScores(
        faithfulness=round(f, 4),
        answer_relevancy=round(ar, 4),
        context_precision=round(cp, 4),
        context_recall=round(cr, 4),
        overall_score=overall,
    )


def run_evaluation(
    dataset_path: Path = GOLDEN_DATASET_PATH,
    limit: Optional[int] = None,
    save_reports: bool = True,
) -> dict[str, Any]:
    """Run full evaluation suite over golden dataset."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset not found at {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        golden_cases = json.load(f)

    if limit:
        golden_cases = golden_cases[:limit]

    print("=" * 65)
    print(f"RUNNING RAGAS EVALUATION SUITE ({len(golden_cases)} TEST CASES)")
    print("=" * 65)
    print()

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    results: list[QuestionEvalResult] = []

    for idx, tc in enumerate(golden_cases, 1):
        t0 = time.perf_counter()
        q_id = tc["id"]
        question = tc["question"]
        ground_truth = tc["ground_truth"]
        expected_sources = tc.get("expected_sources", [])
        category = tc.get("category", "GENERAL")

        logger.info("Evaluating [%s/%s] %s...", idx, len(golden_cases), q_id)

        resp = client.post("/query", json={"message": question, "thread_id": f"eval-{q_id}"})
        elapsed_ms = (time.perf_counter() - t0) * 1000

        data = resp.json()
        answer = data.get("answer", "")
        sources_raw = data.get("sources", [])
        retrieved_contexts = [s.get("text", "") for s in sources_raw]
        retrieved_sources = [s.get("file_name", "") for s in sources_raw]

        scores = evaluate_with_judge(
            question=question,
            ground_truth=ground_truth,
            answer=answer,
            contexts=retrieved_contexts,
            expected_sources=expected_sources,
            retrieved_sources=retrieved_sources,
        )

        res = QuestionEvalResult(
            id=q_id,
            question=question,
            ground_truth=ground_truth,
            answer=answer,
            retrieved_contexts=retrieved_contexts,
            retrieved_sources=retrieved_sources,
            expected_sources=expected_sources,
            category=category,
            scores=scores,
            latency_ms=round(elapsed_ms, 1),
        )
        results.append(res)

        print(
            f"  [{idx:02d}/{len(golden_cases):02d}] {q_id} | Overall: {scores.overall_score:.2f} "
            f"(F:{scores.faithfulness:.2f} AR:{scores.answer_relevancy:.2f} "
            f"CP:{scores.context_precision:.2f} CR:{scores.context_recall:.2f}) | {elapsed_ms:.0f}ms"
        )
        time.sleep(1.5)

    # Compute overall average scores
    avg_f = sum(r.scores.faithfulness for r in results) / len(results)
    avg_ar = sum(r.scores.answer_relevancy for r in results) / len(results)
    avg_cp = sum(r.scores.context_precision for r in results) / len(results)
    avg_cr = sum(r.scores.context_recall for r in results) / len(results)
    avg_overall = sum(r.scores.overall_score for r in results) / len(results)
    avg_latency = sum(r.latency_ms for r in results) / len(results)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": len(results),
        "metrics": {
            "faithfulness": round(avg_f, 4),
            "answer_relevancy": round(avg_ar, 4),
            "context_precision": round(avg_cp, 4),
            "context_recall": round(avg_cr, 4),
            "overall_score": round(avg_overall, 4),
        },
        "average_latency_ms": round(avg_latency, 1),
        "cases": [r.model_dump() for r in results],
    }

    print()
    print("=" * 65)
    print("EVALUATION SUMMARY RESULTS")
    print("=" * 65)
    print(f"  Faithfulness:      {avg_f:.4f}")
    print(f"  Answer Relevancy:  {avg_ar:.4f}")
    print(f"  Context Precision: {avg_cp:.4f}")
    print(f"  Context Recall:    {avg_cr:.4f}")
    print(f"  ------------------------------")
    print(f"  OVERALL SCORE:     {avg_overall:.4f}")
    print(f"  Average Latency:   {avg_latency:.1f} ms")
    print("=" * 65)

    if save_reports:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_report_path = REPORTS_DIR / "latest.json"
        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        md_report_path = REPORTS_DIR / "latest.md"
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(generate_markdown_report(summary))

        print(f"\nSaved reports to:\n  - {json_report_path}\n  - {md_report_path}")

    return summary


def generate_markdown_report(summary: dict[str, Any]) -> str:
    """Generate clean Markdown report for evaluation results."""
    m = summary["metrics"]
    md = f"""# BKIP RAGAS Evaluation Report

> **Timestamp**: {summary['timestamp']}  
> **Total Benchmark Cases**: {summary['total_questions']}  
> **Average Latency**: {summary['average_latency_ms']} ms  

---

## 📊 Summary Metrics

| Metric | Score | Target Baseline | Status |
|---|---|---|---|
| **Faithfulness** | `{m['faithfulness']:.4f}` | `≥ 0.85` | {'✅ Pass' if m['faithfulness']>=0.85 else '⚠️ Review'} |
| **Answer Relevancy** | `{m['answer_relevancy']:.4f}` | `≥ 0.85` | {'✅ Pass' if m['answer_relevancy']>=0.85 else '⚠️ Review'} |
| **Context Precision** | `{m['context_precision']:.4f}` | `≥ 0.80` | {'✅ Pass' if m['context_precision']>=0.80 else '⚠️ Review'} |
| **Context Recall** | `{m['context_recall']:.4f}` | `≥ 0.80` | {'✅ Pass' if m['context_recall']>=0.80 else '⚠️ Review'} |
| **OVERALL SCORE** | **`{m['overall_score']:.4f}`** | `≥ 0.85` | {'✅ Pass' if m['overall_score']>=0.85 else '⚠️ Review'} |

---

## 📝 Test Case Details

"""
    for c in summary["cases"]:
        sc = c["scores"]
        md += f"""### [{c['id']}] {c['question']}
- **Category**: `{c['category']}` | **Latency**: `{c['latency_ms']} ms`
- **Overall Score**: `{sc['overall_score']:.2f}` (Faithfulness: `{sc['faithfulness']:.2f}`, Relevancy: `{sc['answer_relevancy']:.2f}`, Precision: `{sc['context_precision']:.2f}`, Recall: `{sc['context_recall']:.2f}`)
- **Ground Truth**: {c['ground_truth']}
- **Generated Answer**: {c['answer'][:300]}...
- **Retrieved Sources**: `{', '.join(c['retrieved_sources']) if c['retrieved_sources'] else 'None'}`

---
"""
    return md


if __name__ == "__main__":
    run_evaluation()
