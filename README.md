# 🏛️ Banking Knowledge Intelligence Platform (BKIP)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6F00.svg)](https://python.langchain.com/docs/langgraph/)
[![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant%20Cloud-red.svg)](https://qdrant.tech/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Phase 0-6 Complete](https://img.shields.io/badge/Status-Phase%200--6%20Complete%20%E2%9C%85-brightgreen.svg)]()

> **Enterprise-Grade, Policy-Grounded RAG Intelligence Engine for Banking & Compliance Teams**

BKIP transforms unstructured banking documentation—including **RBI master directions, internal credit policies, KYC/AML compliance manuals, treasury guidelines, and audit checklists**—into an accurate, traceable, and policy-compliant intelligence system. Built with local-first vector processing, multi-layer safety guardrails, stateful agentic workflows, and deep observability telemetry.

---

## 📌 Executive Summary & Key Capabilities

- **Zero-Cost Local Embeddings**: Uses `BAAI/bge-small-en-v1.5` (384-dim) via local HuggingFace `sentence-transformers` on CPU, ensuring full data privacy and zero API costs for document embedding.
- **NeMo Safety & Policy Guardrails**: Integrates NVIDIA NeMo Guardrails to intercept prompt injections, filter non-banking out-of-domain queries, and safeguard against PII leaks before retrieval occurs.
- **Stateful Agentic Workflow**: Orchestrated using **LangGraph** with dynamic intent classification, conversational session memory (`MemorySaver`), and specialized planner/retriever/responder routing nodes.
- **Two-Stage Precision Retrieval**: Combines high-speed **Qdrant Cloud** vector search with a CPU-optimized **FlashRank ONNX cross-encoder** (`ms-marco-MiniLM-L-6-v2`) for local reranking.
- **Resilient Multi-Provider LLM Gateway**: Built on **Portkey Gateway** with automatic failover between primary models (`Llama 3.3 70B`) and fallback models (`Llama 3.1 8B`).
- **Dual Telemetry & Observability**: Real-time end-to-end tracing powered by **Pydantic Logfire** and **LangSmith**.
- **Continuous Evaluation Suite**: Integrated **RAGAS** benchmarking pipeline measuring Faithfulness, Answer Relevancy, Context Precision, and Context Recall with a dedicated Streamlit analytics dashboard.

---

## 📐 System Architecture & Agent Workflow

```mermaid
flowchart TD
    subgraph Client Layer
        A[User Query] --> B[Streamlit Chat UI / REST Client]
    end

    subgraph API & Safety Layer
        B --> C[FastAPI Gateway /query]
        C --> D{NeMo Safety Guardrail}
        D -- Off-topic / Breach --> E[Policy Blocked Response]
        E --> B
    end

    subgraph Agent Intelligence Layer (LangGraph)
        D -- Approved --> F[Planner Node]
        F -- Conversational --> G[Direct Generator Node]
        F -- Technical Query --> H[Retriever Node]
        
        subgraph Two-Stage Retrieval
            H --> I[(Qdrant Vector DB)]
            I --> J[FlashRank ONNX Cross-Encoder]
        end
        
        J --> K[Grounded Generator Node]
        G --> L[(LangGraph State Memory)]
        K --> L
    end

    subgraph LLM & Observability Gateway
        K --> M[Portkey Gateway / Groq Primary]
        M -- Failover --> N[Groq Fallback LLM]
        M -. Tracing .-> O[Pydantic Logfire]
        M -. Tracing .-> P[LangSmith Engine]
    end

    L --> Q[Structured JSON Response]
    Q --> B
```

---

## 🛠️ Technology Stack

| Domain | Component / Library | Purpose |
|---|---|---|
| **API Server** | FastAPI & Uvicorn | Asynchronous RESTful service endpoints |
| **Agent Framework** | LangChain & LangGraph | Graph-based stateful agent orchestration & memory |
| **Safety Layer** | NVIDIA NeMo Guardrails | Policy rails, out-of-domain rejection, & safety gating |
| **Embeddings** | `sentence-transformers` | CPU-accelerated `BAAI/bge-small-en-v1.5` embeddings |
| **Vector Store** | Qdrant Cloud | Cloud-native vector search with metadata filtering |
| **Reranker** | FlashRank | Fast ONNX-based local cross-encoder reranking |
| **LLM Engine** | Portkey Gateway + Groq | High-throughput `Llama 3.3 70B` & `Llama 3.1 8B` |
| **Observability** | Pydantic Logfire + LangSmith | Structured telemetry, logging, and chain tracing |
| **Evaluation** | RAGAS Framework | Grounding metrics & automated golden eval benchmarks |
| **Frontend UI** | Streamlit | Executive compliance chat & eval metrics dashboard |

---

## 🚀 Quick Start Guide

### Prerequisites

- **Python 3.11+** installed
- A free **[Qdrant Cloud](https://cloud.qdrant.io/)** cluster
- A free **[Groq API Key](https://console.groq.com/)**

### 1. Repository Setup & Environment

```bash
# Clone repository
git clone https://github.com/rahul-1809/Banking-Knowledge-Intelligence-Platform.git
cd Banking-Knowledge-Intelligence-Platform

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the environment template and edit with your API keys:

```bash
cp .env.example .env
```

Update `.env` with your Qdrant cluster endpoint and API credentials:

```ini
QDRANT_API_KEY=your_qdrant_cloud_api_key
QDRANT_CLUSTER_ENDPOINT=https://your-cluster.aws.cloud.qdrant.io
GROQ_API_KEY=gsk_your_groq_api_key
```

### 3. Ingest Banking Documentation

Process raw PDF/DOCX/TXT files inside `DATA/` into chunked JSON and upload to Qdrant vector index:

```bash
python -m app.ingestion.processor --data-dir DATA/
```

### 4. Launch Backend API Server

Start the FastAPI service:

```bash
uvicorn app.main:app --reload --port 8000
```

Verify service health:
```bash
curl http://localhost:8000/health
# Response: {"status":"ok","qdrant":"connected","gateway":"direct_groq"}
```

### 5. Launch User Interfaces

In separate terminal sessions (with `.venv` activated):

**Streamlit Banking Assistant Chat UI**:
```bash
streamlit run ui/app.py
```
*Access at: `http://localhost:8501`*

**Streamlit RAGAS Evaluation Dashboard**:
```bash
streamlit run evals/app.py
```
*Access at: `http://localhost:8502`*

---

## ⚙️ Configuration & Environment Reference

| Variable | Scope | Required | Default | Description |
|---|---|---|---|---|
| `QDRANT_API_KEY` | Vector DB | Yes | — | Qdrant Cloud cluster API key |
| `QDRANT_CLUSTER_ENDPOINT` | Vector DB | Yes | — | Qdrant Cloud HTTPS endpoint URL |
| `QDRANT_COLLECTION_NAME` | Vector DB | No | `bkip_docs` | Qdrant collection partition name |
| `EMBEDDING_MODEL` | Embedding | No | `BAAI/bge-small-en-v1.5` | Hugging Face embedding model path |
| `GROQ_API_KEY` | Primary LLM | Yes | — | Groq Cloud API key for Llama 3.3 70B |
| `GROQ_FALLBACK_API_KEY` | Fallback LLM | No | — | Secondary key for resilient model switching |
| `PORTKEY_API_KEY` | LLM Gateway | No | — | Portkey routing gateway key |
| `LOGFIRE_TOKEN` | Telemetry | No | — | Pydantic Logfire token |
| `LANGCHAIN_TRACING_V2` | Telemetry | No | `false` | Enable LangSmith tracing (`true`/`false`) |
| `LANGCHAIN_API_KEY` | Telemetry | No | — | LangSmith API key |
| `JUDGE_GROQ_API_KEY` | Evaluation | No | — | Isolated Groq key for RAGAS judge LLM |

---

## 📡 API Specification & Usage Examples

### 1. General Policy Query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the mandatory KYC verification requirements for opening a retail savings account?",
    "thread_id": "session-101"
  }'
```

### 2. Category-Filtered Query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Summarize the high-risk customer Enhanced Due Diligence (EDD) procedures.",
    "thread_id": "session-101",
    "filters": {
      "category": "SOP"
    }
  }'
```

---

## 📂 Project Directory Structure

```
Banking-Knowledge-Intelligence-Platform/
├── app/                        # Main Application Codebase
│   ├── agents/                 # LangGraph Agent Nodes, State, & Graph Builder
│   ├── core/                   # Pydantic Settings & Telemetry Configuration
│   ├── gateway/                # LLM Gateway & Resilient Client Abstraction
│   ├── guardrails/             # NeMo Safety Gating & Content Inspection
│   ├── ingestion/              # Document Ingestion & Chunking Pipeline
│   ├── services/               # Vector Store & FlashRank Reranking Engines
│   └── main.py                 # FastAPI Application Server Entrypoint
├── ui/                         # Streamlit Interactive Chat Application
│   └── app.py                  # Streamlit Compliance Assistant UI
├── evals/                      # RAGAS Automated Evaluation Suite
│   ├── data/                   # Golden Benchmark Datasets
│   ├── reports/                # Evaluation Metrics Summary Reports
│   ├── eval_engine.py          # RAGAS Scoring Pipeline
│   └── app.py                  # Streamlit Evaluation Metrics Dashboard
├── DATA/                       # Sample Banking Policies (PDF, DOCX, TXT)
│   ├── RBI/                    # RBI Circulars & Master Directions
│   ├── CREDIT/                 # Credit & Lending Policy Docs
│   ├── COMPLIANCE/             # AML, KYC, & Sanctions Procedures
│   └── TREASURY/               # Investment & Liquidity Guidelines
├── processed_data/             # Intermediate Parsed JSON Documents
├── scripts/                    # Document & Data Generators
├── ARCHITECTURE.md             # In-Depth Architectural Specifications
├── PLAN.md                     # Implementation Phase Milestones
├── requirements.txt            # Python Project Dependencies
├── .env.example                # Clean Environment Variable Template
└── README.md                   # Enterprise Technical Documentation
```

---

## 📊 Evaluation & Benchmarking

BKIP features an automated continuous evaluation framework in `evals/` powered by **RAGAS**. Benchmark tests run against a banking domain golden dataset (`golden_dataset.json`):

- **Faithfulness**: Verifies answers are strictly grounded in retrieved policy context (zero hallucination).
- **Answer Relevancy**: Evaluates how directly the answer addresses the user query.
- **Context Precision**: Measures precision of top-k retrieved policy passages.
- **Context Recall**: Verifies all required compliance statements are present in context.

Run regression evaluations:
```bash
python -m evals.smoke_eval
```

---

## 🛡️ Security & Compliance Notice

- **No Hardcoded Credentials**: No production keys or secrets are stored in this repository. Ensure `.env` is listed in `.gitignore`.
- **Data Isolation**: Local vector embedding guarantees raw document content is parsed locally before encrypted vector storage.
- **Dev/Prototyping Notice**: This system is designed for prototyping, compliance workflow augmentation, and internal sandbox testing. For full enterprise banking deployment, integrate OAuth2/OIDC authentication, TLS termination, and enterprise audit logging.

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for more information.
