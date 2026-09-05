# 🏦 AI Finance Controller
> **Razorpay Buildathon — Track 04: "Run the books and the cash position"**

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green?logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-red?logo=streamlit)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-blue?logo=postgresql)
![Gemini](https://img.shields.io/badge/Gemini-Q%26A%20Agent-orange?logo=google)
![Tests](https://img.shields.io/badge/Tests-23%2F23%20Passing-brightgreen)
![Precision](https://img.shields.io/badge/Precision-100%25-brightgreen)

A **deterministic-first, measurable** financial reconciliation & treasury engine for high-volume payment batches. Built for sub-second verification, statutory tax compliance, working capital forecasting, and natural language Q&A — all without trusting an LLM to do financial math.

---

## ⚡ The Problem

For high-volume merchants, daily payment reconciliation is a nightmare. Settlement batches from gateways like Razorpay must be matched against thousands of internal ledger entries. Real-world data is messy:
- Missing or mismatched UTR numbers
- Vendor name aliases (e.g. `Swiggy` vs. `Bundl Technologies Pvt. Ltd.`)
- Settlement lags (T+1, T+2 clearing cycles)
- Complex tax deductions: 2% MDR, 18% GST, 1% TDS (Section 194O)

Traditional `VLOOKUP` and SQL joins break immediately when data is dirty.

---

## ✅ The Solution: A Hybrid Deterministic + AI Architecture

We **never** let the LLM do financial math. Instead, we separate concerns strictly:

| Layer | What it does | Technology |
|:---|:---|:---|
| **Ingestion** | Parse, normalize, validate CSVs | Polars (multi-threaded) |
| **Embedding** | Vectorize merchant names | `all-MiniLM-L6-v2` (384-dim) |
| **Retrieval** | UTR exact lookup + cosine similarity | PostgreSQL 17 + pgvector |
| **Scoring** | Multi-signal composite score | Pure Python Decimal math |
| **Matching** | 1-to-1 global bipartite assignment | Deterministic 6-tier tie-breaking |
| **Tax Audit** | GST (18%) + TDS (1%) variance flags | Python Decimal arithmetic |
| **Forecasting** | 7-day liquidity projections | Deterministic scenario engine |
| **Q&A Agent** | Natural language answers | Gemini LLM (with structured fallback) |

---

## 📊 Benchmark Results (106-Record Synthetic Batch)

| Metric | Result |
|:---|:---|
| Bank Records Processed | `106` |
| Ledger Records Ingested | `118` |
| Reconciled Matches | `55` |
| Exceptions Caught | `51` |
| **Reconciliation Precision** | **`100.00%` — Zero False Positives** |
| **Reconciliation Recall** | **`75.34%`** |
| Engine Throughput | **`~180 records/second`** |
| Statutory Tax Flags (GST/TDS) | `5 variance flags` — all injected anomalies caught |
| Pytest Suite | **`23/23 passing`** |

---

## 🏗️ System Architecture

```
bank.csv ──┐
           ├──► Polars Parser ──► pgvector DB ──► UTR Lookup ──┐
ledger.csv─┘                                   ► Vector Search─┤
                                                                ├──► Multi-Signal Scorer
                                                                │    (UTR + Amt + Date + Merchant)
                                                                ├──► Hard Safety Rules
                                                                │    (Currency, ±0.01 Amt, ±3 Days)
                                                                ├──► 1:1 Bipartite Matcher
                                                                │
                                               ┌────────────────┴──────────────────┐
                                               │                                   │
                                        MATCHED (55)                     EXCEPTIONS (51)
                                               │                                   │
                     ┌─────────────────────────┼─────────────┐                    │
                     ▼                         ▼             ▼                    ▼
              Cash Position           Tax & Fee Audit   7-Day Forecast    Exception Explorer
              (Book vs Bank)          (GST 18%, TDS 1%)  (Liquidity Sim)   (Diagnostic Cards)
                     └─────────────────────────┼─────────────┘                    │
                                               ▼                                  │
                                      Gemini Q&A Agent ◄────────────────────────-┘
                                   (Reads structured JSON, never does math)
```

---

## 🚀 Quick Start (Windows PowerShell)

### Prerequisites
- Python 3.11+
- Docker Desktop (running)
- Git

### 1. Clone the repository
```powershell
git clone https://github.com/Mohit0006/ai-finance-controller.git
cd ai-finance-controller
```

### 2. Set up virtual environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Start PostgreSQL with pgvector
```powershell
docker compose up -d postgres
```

### 4. Configure environment
```powershell
Copy-Item .env.example .env
# Optional: Add your GOOGLE_API_KEY for Gemini Q&A
# The system runs 100% offline in deterministic mode without a key
```

### 5. Generate synthetic dataset
```powershell
python synthetic_data.py
```

### 6. Run the test suite
```powershell
pytest tests/ -v
```

### 7. Launch the application
**Terminal 1 — Backend:**
```powershell
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```powershell
streamlit run app.py
```

Open **[http://localhost:8501](http://localhost:8501)** in your browser.

---

## 🖥️ Feature Walkthrough

### Tab 1 — ⚖️ Reconciliation & Audit
- Live KPI cards: Records, Matches, Exceptions, Precision, Recall, Throughput
- Full matched records table with decision scores and reasoning
- **Exception Explorer**: Diagnostic cards showing exactly why each transaction failed (Amount Mismatch, Failed Score Threshold, Duplicate Conflict, No Candidate)
- One-click download of the **Official Controller Sign-Off Pack (.md)**

### Tab 2 — 💵 Cash Position & Treasury Simulator
- Book Balance vs. Bank Balance bridge with Uncleared Float (T+1/T+2)
- **Interactive Working Capital Simulator**: Drag sliders to adjust Daily Burn Rate, Reserve Floor, and Settlement Clearing Lag — see live 7-day cash curve update instantly
- Multi-scenario projections: Base, Optimistic (+10%), Conservative (Stress)

### Tab 3 — 🧾 Tax & Fee Auditor
- Statutory compliance grid for every matched transaction
- Verifies: Platform Fee %, GST at 18%, Section 194O TDS at 1%
- Flags every variance with exact discrepancy reason and rupee amount

### Tab 4 — 🤖 Settlement Q&A Agent
- Ask natural language questions: *"Summarize exceptions"*, *"What is my cash position?"*, *"Show me tax variances"*
- Gemini reads the structured, mathematically verified JSON — it never does the math itself
- Automatically falls back to deterministic structured answers if the API is unavailable

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|:---|:---|
| UTR-first retrieval | Guarantees exact matches are found regardless of merchant text variation |
| `Decimal` arithmetic everywhere | Zero floating-point drift — all amounts quantized to `Decimal("0.01")` |
| LLM excluded from matching pipeline | 100% reproducible results with no external API dependency for core logic |
| Global 1:1 bipartite matching | No ledger ID appears in two matched results; deterministic 6-tier tie-breaking |
| Skip-and-warn validation | One bad row never kills the entire batch |
| Gemini as Q&A-only layer | LLM generates language from structured facts — never invents numbers |

---

## 🛠️ Tech Stack

| Component | Technology |
|:---|:---|
| Language | Python 3.11 |
| Backend API | FastAPI + Uvicorn |
| Frontend UI | Streamlit |
| High-Speed Parsing | Polars |
| Vector Database | PostgreSQL 17 + pgvector |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Financial Math | Python `decimal.Decimal` |
| AI Q&A Layer | Google Gemini (`gemini-2.5-flash`) |
| Testing | Pytest + Pytest-Asyncio |
| Containerization | Docker Compose |

---

## 📁 Project Structure

```
ai-finance-controller/
├── app.py                      # Streamlit UI (4-tab Finance Controller Cockpit)
├── main.py                     # FastAPI backend (REST API endpoints)
├── matching_engine.py          # Core bipartite reconciliation graph
├── scoring.py                  # Multi-signal composite scorer
├── settlement_agent.py         # Gemini Q&A agent with structured fallback
├── cash_position.py            # Book vs. Bank balance engine
├── forecaster.py               # 7-day liquidity forecaster
├── tax_matcher.py              # GST + TDS statutory auditor
├── embeddings.py               # pgvector embedding pipeline
├── data_processing.py          # Polars CSV ingestion & validation
├── database.py                 # PostgreSQL async connection pool
├── schemas.py                  # Pydantic data models & enums
├── config.py                   # App settings & environment config
├── metrics.py                  # Precision, recall & throughput calculator
├── synthetic_data.py           # Synthetic dataset generator (with anomalies)
├── migrations/
│   └── 001_init.sql            # PostgreSQL schema & pgvector setup
├── tests/
│   ├── __init__.py
│   ├── test_api.py             # FastAPI endpoint integration tests
│   ├── test_cash_position.py   # Cash position & bridge calculation tests
│   ├── test_data_processing.py # CSV ingestion & validation tests
│   ├── test_forecaster.py      # 7-day liquidity forecast tests
│   ├── test_matching_engine.py # Bipartite matching & exception tests
│   ├── test_scoring.py         # Multi-signal scorer unit tests
│   ├── test_settlement_agent.py# Q&A agent & fallback tests
│   └── test_tax_matcher.py     # GST / TDS statutory audit tests
├── bank.csv                    # Sample bank settlement data
├── ledger.csv                  # Sample internal ledger data
├── ground_truth.csv            # Ground truth for precision/recall evaluation
├── docker-compose.yml          # PostgreSQL + pgvector container
├── requirements.txt            # Python dependencies
├── pyrightconfig.json          # Pyright type-checker config
└── .env.example                # Environment variable template
```

---

> **Buildathon Prototype Notice:** This implementation satisfies Razorpay Buildathon Track 04 requirements. It demonstrates a controlled reconciliation and treasury simulation workflow and is not a substitute for formal financial statement audits.
