"""Streamlit Evaluation Dashboard for Banking Knowledge Intelligence Platform.

Interactive UI for running and reviewing RAGAS evaluations, smoke tests,
and comparative benchmarks.

Run with:
    streamlit run evals/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Bootstrap project root directory into sys.path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

import streamlit as st

st.set_page_config(
    page_title="BKIP — RAGAS Evaluation Dashboard",
    page_icon="📊",
    layout="wide",
)

REPORTS_DIR = Path("evals/reports")
GOLDEN_DATASET_PATH = Path("evals/data/golden_dataset.json")

st.title("📊 BKIP — RAGAS Evaluation & Benchmarking Dashboard")
st.markdown(
    "Enterprise evaluation suite measuring **Faithfulness**, **Answer Relevancy**, "
    "**Context Precision**, and **Context Recall** across banking compliance benchmarks."
)

tab1, tab2, tab3 = st.tabs(["🚀 Run Evaluation", "📈 Comparative Analysis", "📋 Latest Report"])

# ── Tab 1: Run Evaluation ────────────────────────────────────────────────────
with tab1:
    st.subheader("Run Benchmark Evaluation")
    col1, col2 = st.columns([2, 1])

    with col1:
        eval_mode = st.radio("Select Mode", ["Smoke Test (5 Queries)", "Full Benchmark (15 Queries)"], horizontal=True)

    with col2:
        run_btn = st.button("▶️ Start Evaluation", type="primary", use_container_width=True)

    if run_btn:
        with st.spinner("Executing benchmark queries and computing RAGAS metrics..."):
            if "Smoke Test" in eval_mode:
                from evals.smoke_eval import run_smoke_eval
                summary = run_smoke_eval(use_http=False)
                st.success(f"Smoke Test Completed! Pass Rate: {summary['pass_rate']}% ({summary['passed']}/{summary['total']})")
                st.json(summary["results"])
            else:
                from evals.eval_engine import run_evaluation
                summary = run_evaluation(save_reports=True)
                st.success(f"Full RAGAS Evaluation Completed! Overall Score: {summary['metrics']['overall_score']}")

                m = summary["metrics"]
                m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
                m_col1.metric("Faithfulness", f"{m['faithfulness']:.2f}")
                m_col2.metric("Answer Relevancy", f"{m['answer_relevancy']:.2f}")
                m_col3.metric("Context Precision", f"{m['context_precision']:.2f}")
                m_col4.metric("Context Recall", f"{m['context_recall']:.2f}")
                m_col5.metric("Overall Score", f"{m['overall_score']:.2f}")

                st.markdown("### Per-Query Results")
                for case in summary["cases"]:
                    with st.expander(f"[{case['id']}] {case['question']} — Score: {case['scores']['overall_score']:.2f}"):
                        st.markdown(f"**Ground Truth**: {case['ground_truth']}")
                        st.markdown(f"**Generated Answer**: {case['answer']}")
                        st.markdown(f"**Retrieved Sources**: {', '.join(case['retrieved_sources'])}")
                        st.markdown(f"**Latency**: {case['latency_ms']} ms")

# ── Tab 2: Comparative Analysis ──────────────────────────────────────────────
with tab2:
    st.subheader("Comparative Retrieval Performance: Raw Qdrant vs FlashRank Reranker")
    if st.button("⚡ Run Comparative Analysis"):
        with st.spinner("Evaluating raw vector search vs FlashRank two-stage retrieval..."):
            from evals.comparator import compare_retrieval_strategies
            comp_summary = compare_retrieval_strategies()
            st.success("Comparison Complete!")

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Raw Qdrant Precision@5", f"{comp_summary['raw_qdrant_precision_at_5']*100:.1f}%")
            col_b.metric("FlashRank Precision@5", f"{comp_summary['flashrank_precision_at_5']*100:.1f}%", f"+{comp_summary['precision_gain']*100:.1f}%")
            col_c.metric("Precision Gain", f"+{comp_summary['precision_gain']*100:.1f}%")

            st.dataframe(comp_summary["results"])
    else:
        st.info("Click above to run a side-by-side comparative evaluation of Raw Qdrant vs FlashRank reranked retrieval.")

# ── Tab 3: Latest Report ─────────────────────────────────────────────────────
with tab3:
    st.subheader("Latest Evaluation Report")
    md_file = REPORTS_DIR / "latest.md"
    json_file = REPORTS_DIR / "latest.json"

    if md_file.exists():
        st.markdown(md_file.read_text(encoding="utf-8"))
    elif json_file.exists():
        st.json(json.loads(json_file.read_text(encoding="utf-8")))
    else:
        st.warning("No evaluation report generated yet. Run an evaluation in Tab 1 first.")
