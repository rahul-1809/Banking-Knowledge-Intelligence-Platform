"""Fast 5-question smoke evaluation script for BKIP RAG pipeline.

Runs 5 core test queries against the local API or internal graph engine:
1. RBI KYC OVD requirements (Standard Policy Query)
2. Personal loan credit score eligibility (Credit Policy Query)
3. High-risk customer EDD approval (SOP Routing Query)
4. Guardrail Off-Topic Check (Recipe query -> expect blocked)
5. Guardrail PII Check (Aadhaar number in query -> expect blocked)

Usage:
    python evals/smoke_eval.py [--api-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Bootstrap project root directory into sys.path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from fastapi.testclient import TestClient


SMOKE_TESTS = [
    {
        "id": "smoke-001",
        "type": "rag_query",
        "question": "What are the officially valid documents (OVD) for individual KYC?",
        "expected_kw": ["passport", "driving licence", "aadhaar", "voter"],
        "should_block": False,
    },
    {
        "id": "smoke-002",
        "type": "rag_query",
        "question": "What is the minimum credit score required for personal loan approval?",
        "expected_kw": ["700", "score"],
        "should_block": False,
    },
    {
        "id": "smoke-003",
        "type": "rag_query",
        "question": "Who must approve high-risk customer profiles before account activation?",
        "expected_kw": ["compliance officer", "edd"],
        "should_block": False,
    },
    {
        "id": "smoke-004",
        "type": "guard_off_topic",
        "question": "How do I make a chocolate cake?",
        "expected_kw": [],
        "should_block": True,
        "expected_reason": "off_topic",
    },
    {
        "id": "smoke-005",
        "type": "guard_pii",
        "question": "My Aadhaar number is 999988887777, please verify my account",
        "expected_kw": [],
        "should_block": True,
        "expected_reason": "pii",
    },
]


def run_smoke_eval(use_http: bool = False, base_url: str = "http://localhost:8000") -> dict[str, Any]:
    """Execute smoke evaluation tests."""
    print("=" * 65)
    print("BKIP RAG PIPELINE — FAST SMOKE EVALUATION (5 TEST CASES)")
    print("=" * 65)
    print()

    passed = 0
    total = len(SMOKE_TESTS)
    results = []

    if not use_http:
        from app.main import app
        client = TestClient(app)

    for tc in SMOKE_TESTS:
        t0 = time.perf_counter()
        query = tc["question"]
        payload = {"message": query, "thread_id": f"smoke-{tc['id']}"}

        if use_http:
            import requests
            resp = requests.post(f"{base_url}/query", json=payload, timeout=120)
            data = resp.json()
        else:
            resp = client.post("/query", json=payload)
            data = resp.json()

        elapsed_ms = (time.perf_counter() - t0) * 1000
        is_blocked = data.get("blocked", False)
        answer = data.get("answer", "")
        reason = data.get("reason", "")

        test_passed = True
        notes = []

        if tc["should_block"]:
            if not is_blocked:
                test_passed = False
                notes.append("Expected query to be blocked, but it was allowed.")
            elif tc.get("expected_reason") and reason != tc["expected_reason"]:
                test_passed = False
                notes.append(f"Expected block reason '{tc['expected_reason']}', got '{reason}'.")
            else:
                notes.append(f"Correctly blocked ({reason})")
        else:
            if is_blocked:
                test_passed = False
                notes.append(f"Unexpectedly blocked ({reason}).")
            else:
                sources = data.get("sources", [])
                kw_matches = [kw for kw in tc["expected_kw"] if kw.lower() in answer.lower()]
                if not kw_matches:
                    notes.append(f"Warning: expected keywords {tc['expected_kw']} not all in answer.")
                notes.append(f"Got {len(sources)} sources, {len(data.get('thought_process', []))} steps")

        if test_passed:
            passed += 1
            icon = "✅ PASS"
        else:
            icon = "❌ FAIL"

        res_entry = {
            "id": tc["id"],
            "question": query,
            "passed": test_passed,
            "latency_ms": round(elapsed_ms, 1),
            "blocked": is_blocked,
            "reason": reason,
            "notes": " | ".join(notes),
        }
        results.append(res_entry)

        print(f"  {icon} [{tc['id']}] ({elapsed_ms:.1f}ms) — Query: {query[:50]}...")
        print(f"         Status: {'BLOCKED' if is_blocked else 'ALLOWED'} | Notes: {' | '.join(notes)}")
        print()

    print("=" * 65)
    print(f"SMOKE EVAL SUMMARY: {passed}/{total} PASSED ({passed/total*100:.0f}%)")
    print("=" * 65)

    summary = {
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total * 100, 1),
        "results": results,
    }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run BKIP smoke evaluation")
    parser.add_argument("--http", action="store_true", help="Test via HTTP against live server")
    parser.add_argument("--url", default="http://localhost:8000", help="HTTP base URL")
    args = parser.parse_args()

    res = run_smoke_eval(use_http=args.http, base_url=args.url)
    if res["passed"] < res["total"]:
        sys.exit(1)
