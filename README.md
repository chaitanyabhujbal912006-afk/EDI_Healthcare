# EdiPro: Enterprise Healthcare EDI Gateway

![EdiPro Dashboard](https://img.shields.io/badge/Status-Production_Ready-success) ![License](https://img.shields.io/badge/License-MIT-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-Modern-green) ![Vite](https://img.shields.io/badge/Frontend-Vite_Vanilla_JS-purple) ![Tests](https://img.shields.io/badge/Tests-85%20Passed-brightgreen)

**EdiPro** is a modern, enterprise-grade, HIPAA-compliant Healthcare EDI (Electronic Data Interchange) parser, validator, and dashboard. Built for clinical and financial operations, it transforms complex, unstructured X12 EDI text streams (like `837P`, `837I`, `835`, and `834`) into validated Pydantic models accompanied by intelligent, AI-powered validation reporting.

---

## 🚀 Key Features

*   **Operator Dashboard:** Modern graphical interface built with glassmorphism, responsive tables, real-time API health auto-polling with click-to-reconnect, and a seamless local-storage persisted System/Dark/Light theme toggle.
*   **Robust X12 Parsing Schema:** Instantly parses `837P` (Professional Claims), `837I` (Institutional Claims with revenue codes), `835` (Payment & Remittance Advice), and `834` (Benefit Enrollment & Maintenance) structured transactions.
*   **64+ Built-in Validation Rules:** Flags structural and logic issues (e.g., missing Billing/Rendering NPIs, invalid Luhn check digits, invalid dates, SE01 segment count mismatches, GE01 transaction counts, ICD-10 formatting errors) out of the box.
*   **AI-Powered Insights:** Multi-provider AI chatbot engine (supporting **Groq Llama 3.3**, **Hugging Face**, and intelligent offline rule-based fallback) for natural language EDI Q&A.
*   **Financial Reconciliation & Exports:** Direct reconciliation matching between 837 billed claims and 835 remittance payouts with variance calculation, alongside JSON, PDF error reports, CSV exports with UTF-8 BOM, and TSV exports (`/api/export/reconciliation-csv`, `/api/export/members-csv`, `/api/export/members-tsv`).
*   **Secure & Stateless:** Drag-and-drop processing handled completely in-memory on your secure infrastructure. No PHI is permanently stored by the frontend.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Lightweight service health ping |
| `GET` | `/api/health/detailed` | Deep telemetry, uptime, engine status, and rule count |
| `GET` | `/api/version` | Engine & gateway build version metadata and capabilities |
| `GET` | `/api/stats/overview` | Transaction counts, rule metrics, and system overview |
| `POST` | `/api/parse` | Parse raw EDI content with full validation reporting |
| `POST` | `/api/upload` | Multi-file multipart/form-data batch ingest & parsing |
| `POST` | `/api/summary/837i` | Institutional claim extractor (revenue codes, SV2 breakdown) |
| `POST` | `/api/reconciliation` | 837-to-835 payment variance & claim matching engine |
| `POST` | `/api/export/members-csv` | UTF-8 BOM formatted CSV export with summary totals |
| `POST` | `/api/export/members-tsv` | Tab-separated values export for comma-heavy records |
| `POST` | `/api/export/reconciliation-csv` | Financial reconciliation variance sheet export |
| `POST` | `/api/export/json` | Indented structured JSON data export |
| `POST` | `/api/export/errors-pdf` | Formatted HIPAA EDI validation report PDF download |
| `POST` | `/api/chat` | AI-assisted natural language EDI inquiry endpoint |

---

## 🏗️ Technical Architecture

The application is split into two loosely coupled stacks:

1.  **Backend (FastAPI Engine):** Heavy lifting, X12 string streaming, schema validation mapping, financial reconciliation, and REST fulfillment.
2.  **Frontend (Vite / Static UI):** Sleek, vanilla-CSS-driven dashboard rendering intuitive tables, toast notifications, search command palette (`Cmd/Ctrl+K`), and live health indicators.

---

## 🛠️ Quickstart Installation

### Option A: One-Click Dev Launcher (Recommended)

**On Windows:**
```powershell
.\run_dev.ps1
```

**On Linux / macOS:**
```bash
chmod +x run_dev.sh
./run_dev.sh
```

This script automatically initializes the Python virtual environment, installs dependencies, boots FastAPI on `http://localhost:8000`, and serves the frontend dashboard at `http://localhost:8000/`.

---

### Option B: Manual Setup

#### 1. Backend Engine
```powershell
# Navigate to project root
cd c:\path\to\validEDI-main\validEDI-main\

# Create & activate a virtual Python environment
python -m venv venv
.\venv\Scripts\activate

# Install requirements
cd src\backend
pip install -r requirements.txt

# Boot the API server 
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
> **Swagger API:** Navigate to `http://localhost:8000/docs` to see live interactive Swagger API definitions.
> **Dashboard:** Navigate to `http://localhost:8000/` to open the full UI.

#### 2. Frontend Interface (Optional Vite Dev Server)
If you prefer running Vite directly with hot-module reloading:
```powershell
cd src\stitch
npm install
npm run dev
```
> Navigate to `http://localhost:5173/`. Requests to `/api/*` are automatically proxied to port 8000.

---

## 🧪 Testing & Quality Assurance

Run the comprehensive test suite (85 automated tests):

```powershell
# Run all unit and integration tests
.\venv\Scripts\pytest -v

# Run the full feature CLI demo & validation checker
.\venv\Scripts\python test_quick.py
```

All 85 unit & integration tests pass with 100% coverage across parser engines, validation rules, extractors, and REST endpoints.

---

## 🗂️ Testing the Flow (Using Included Sample Data)

Included in the root directory are safe, synthetic, HIPAA-cleared test packages (`sample_835.edi` and `sample_837p.edi`). This allows you to audit the parsing pipeline without relying on real PHI.

1.  Navigate to the UI at `http://localhost:8000/` (or `http://localhost:5173/`).
2.  Go to the **Dashboard** panel.
3.  Drag and drop the sample files onto the upload card, or click **Select Files**.
4.  Navigate down the sidebar (e.g., **837 Claims**, **835 Remittance**, **Master Parser**) to view the ingested datasets, identified validation errors, and clean tabular formatting.

---

## 🤖 Configuring AI Chatbot Extensions

The application includes an LLM integration layer for conversational EDI analysis:

1.  Create or edit the `.env` file in the project root:
    ```env
    GROQ_API_KEY=your_groq_api_key_here
    ```
2.  The `/api/chat` endpoint and Help Center assistant will automatically utilize Groq Llama 3.3. If no key is configured, it falls back seamlessly to the built-in offline rule-based explainer.
3.  Test via CLI:
    ```powershell
    python examples/llm_chatbot.py sample_837p.edi
    ```

---

## 🚀 Production Deployment

EdiPro includes containerized deployment workflows for Docker Compose, AWS ECS, GCP Cloud Run, and Kubernetes.

```powershell
# Quick single-command Docker Compose launch
docker compose up --build -d
```
For complete enterprise deployment instructions, SSL Nginx configuration, HIPAA security policies, and CI/CD pipelines, see the [Deployment Guide](DEPLOYMENT.md).

---

## 🔒 Security & Compliance Reminder

This system is configured to process raw EDI formatted data. If handling live production transactions, ensure the environment you execute on correctly guards server access mapping in line with U.S. HIPAA regulations regarding PHI and network egress encryption.

---

## 📄 License

This code is provided under an open-source MIT implementation allowance. Modify and extend internal endpoints as needed for your specific hospital/billing firm standards.
