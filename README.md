# OmniKavach EDI Dashboard

A modern healthcare diagnostic dashboard and X12 EDI parser for analyzing medical claims.

## Features

- **X12 EDI Parsing:** Clean data extraction from 837P, 835, and 834 transactions.
- **AI Explanations:** Built-in LLM integration to decipher EDI strings.
- **Web UI:** React/Vite based dashboard for easy navigation.

## How to run

We use a split architecture with a Python FastAPI Backend and a React Vite Frontend.

### Starting the Backend
```powershell
# Open terminal 1
cd src/backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Starting the Frontend
```powershell
# Open terminal 2
cd src/stitch
npm install
npm run dev
```

The frontend will be available at http://localhost:5173.
