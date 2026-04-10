# EdiPro Healthcare X12 EDI Command Center

EdiPro is a full-stack web app for uploading, parsing, validating, and auditing HIPAA X12 EDI transactions:

- 837P / 837I medical claims
- 835 remittance advice
- 834 member enrollment

Includes AI-assisted explanations via Hugging Face (Llama 7B), export tools, and advanced workflows like batch processing, 834 delta diff, and 835-837 reconciliation.

## Stack

- Backend: FastAPI (Python)
- Frontend: React + TypeScript + Vite
- AI Chat: Hugging Face Inference API (`meta-llama/Llama-2-7b-chat-hf`)

## Features

- Upload `.edi`, `.txt`, `.dat`, `.x12`
- Auto transaction detection from ISA/GS/ST/BHT
- Interactive collapsible parsed segment tree
- Validation engine:
  - required segment checks
  - element format checks (NPI, ZIP, date, amounts)
  - qualifier checks (NM108, CLM05, SVC01)
  - cross-segment consistency checks
  - 835 CAS/CLP validations
  - 834 INS/member duplicate validations
- Error report with actionable fix suggestions
- 835 remittance summary table
- 834 member summary table
- AI contextual Q&A panel
- Batch ZIP processing
- 835 to 837 reconciliation endpoint
- 834 month-over-month delta endpoint
- 834 vs 837 eligibility check endpoint
- Export JSON, errors PDF, and members CSV

## Run Locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:HUGGINGFACE_API_KEY="your_key"
uvicorn app.main:app --reload
```

### Frontend

```powershell
cd stitch
npm install
npm run dev
```

Frontend default URL: `http://localhost:5173`
Backend default URL: `http://localhost:8000`

## Docker Compose

```powershell
copy .env.example .env
# set HUGGINGFACE_API_KEY in .env
docker compose up --build
```

## API Highlights

- `POST /api/upload` single-file parse + validate
- `POST /api/batch` zip batch processing
- `POST /api/chat` contextual AI assistant
- `POST /api/reconcile/835-837` discrepancy report
- `POST /api/delta/834` member delta report
- `POST /api/eligibility/834-837` enrollment cross-check
- `POST /api/export/json`
- `POST /api/export/errors-pdf`
- `POST /api/export/members-csv`
- `POST /api/export/corrected-edi`

## Notes

- Validation rules are extensible and implemented in `backend/app/validation/rules.py`.
- Parser loop tree is built for navigation and can be deepened to full implementation-guide loop granularity.
- For NPI verification with CMS NPPES live API, add a dedicated background lookup endpoint and enrich provider checks.

