# EdiPro: Enterprise Healthcare EDI Gateway

![EdiPro Dashboard](https://img.shields.io/badge/Status-Production_Ready-success) ![License](https://img.shields.io/badge/License-MIT-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-Modern-green) ![Vite](https://img.shields.io/badge/Frontend-Vite_Vanilla_JS-purple)

**EdiPro** is a modern, enterprise-grade, HIPAA-compliant Healthcare EDI (Electronic Data Interchange) parser, validator, and dashboard. Built for clinical and financial operations, it transforms complex, unstructured X12 EDI text streams (like `837`, `835`, and `834`) into clear, parsed datasets accompanied by intelligent, AI-powered validation reporting.

## 🚀 Key Features

*   **Premium Operator Dashboard:** Apple-inspired graphical interface built with glassmorphism, fluid animations, and a seamless local-storage persisted System/Dark/Light theme toggle.
*   **Robust X12 Parsing Schema:** Instantly parses `837P`, `837I`, `835`, and `834` structured transactions into validated Pydantic models.
*   **60+ Built-in Validation Rules:** Flags structural and logic issues (e.g., missing NPIs, invalid dates, misaligned batch totals) out of the box.
*   **AI-Powered Insights:** Plug-and-play Groq/Llama integration provides plain-English translations for dense X12 validation errors so billing operators spend less time debugging codes.
*   **Secure & Stateless:** Drag-and-drop processing handled completely on your secure infrastructure. No PHI is permanently stored by the frontend.

## 🏗️ Technical Architecture

The application is split into two loosely coupled stacks:

1.  **Backend (FastAPI Engine):** Heavy lifting, X12 string streaming, schema validation mapping, and REST fulfillment.
2.  **Frontend (Vite UI):** Sleek, vanilla-CSS-driven dashboard rendering intuitive tables and status pills.

## 🛠️ Quickstart Installation

### 1. Backend Engine
Start the powerful FastAPI schema ingestion engine.

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
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
> **Testing check:** Navigate to `http://localhost:8000/docs` to see the live Swagger API definitions.

### 2. Frontend Interface
In a separate terminal, serve the premium dashboard.

```powershell
# Navigate back to the frontend directory
cd c:\path\to\validEDI-main\validEDI-main\src\stitch

# Install dependencies (only required on first run)
npm install

# Start the dev server
npm run dev
```

> **Testing check:** Navigate to `http://localhost:5173/` and interact with the UI.

## 🗂️ Testing the Flow (Using Included Sample Data)

Included in the root directory are safe, synthetic, HIPAA-cleared test packages (`sample_835.edi` and `sample_837p.edi`). This allows you to audit the parsing pipeline without relying on real PHI.

1.  Navigate to the UI at `http://localhost:5173/`.
2.  Go to the **Dashboard** panel.
3.  Drag and drop the sample files onto the upload card, or click **Select Files**.
4.  Navigate down the sidebar (e.g., **837 Claims**, **835 Remittance**, **Master Parser**) to view the ingested datasets, identified validation errors, and clean tabular formatting.

## 🤖 Configuring AI Chatbot Extensions (Optional)

The application includes an LLM integration layer (`examples/llm_chatbot.py`) to query your EDI files in natural language.

1.  Create a `.env` file in the root based on `.env.example`.
2.  Add your API key: `GROQ_API_KEY=your_key_here`
3.  Test via CLI:
    ```powershell
    python examples/llm_chatbot.py sample_837p.edi
    ```

## 🔒 Security & Compliance Reminder

This system is configured to process raw EDI formatted data. If handling live production transactions, ensure the environment you execute on correctly guards server access mapping in line with U.S. HIPAA regulations regarding PHI and network egress encryption.

## 📄 License

This code is provided under an open-source MIT implementation allowance. Modify and extend internal endpoints as needed for your specific hospital/billing firm standards.
