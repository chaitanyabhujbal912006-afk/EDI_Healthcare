# EdiPro Production Deployment & Security Guide

This document outlines deployment strategies, container orchestration patterns, security configurations, HIPAA compliance requirements, and CI/CD pipelines for **EdiPro Healthcare EDI Gateway**.

---

## 📐 System Architecture Overview

EdiPro utilizes a decoupled architecture consisting of two primary services:

1. **FastAPI Engine (`src/backend`)**: Asynchronous Python microservice handling X12 EDI stream parsing, HIPAA 5010 rule execution, format export (JSON/CSV/PDF), reconciliation logic, and optional LLM insights.
2. **Operator Web UI (`src/stitch`)**: Vite-built vanilla JavaScript web interface served statically or via Nginx, featuring glassmorphism layout, real-time table rendering, persistent themes, and file ingestion controls.

```
                  +-----------------------------------+
                  |        Client Web Browser         |
                  +-----------------------------------+
                                    |
                         Port 80 / 443 (HTTPS)
                                    v
                  +-----------------------------------+
                  |      Nginx Reverse Proxy          |
                  +-----------------------------------+
                       /                     \
                / (Static Assets)         /api/ (Proxy)
                      v                       v
         +------------------------+ +-------------------+
         | Vite Static Distribution| | FastAPI Engine    |
         |  (Container / Storage) | |   (Port 8000)     |
         +------------------------+ +-------------------+
```

---

## ⚙️ Environment Variables Reference

Create a `.env` file in the root directory prior to deployment:

| Variable | Description | Required | Default |
|---|---|---|---|
| `ENVIRONMENT` | Environment type (`development`, `staging`, `production`) | No | `development` |
| `VITE_API_TARGET` | Proxy API endpoint for frontend build | No | `http://localhost:8000` |
| `HUGGINGFACE_API_KEY` | Hugging Face inference key for optional LLM assistance | No | None |
| `GROQ_API_KEY` | Groq LLM API key for AI rule explanations | No | None |
| `CORS_ORIGINS` | Allowed CORS origins for backend (comma-separated) | No | `*` |
| `PORT` | Backend service execution port | No | `8000` |

---

## 🐳 Deployment Strategy 1: Docker Compose

### Local Development / Staging Startup
Launch both frontend (Vite dev mode) and backend using standard Docker Compose:

```bash
# Build and start services in foreground
docker compose up --build

# Or launch detached in background
docker compose up -d
```
- **Frontend Dashboard:** `http://localhost:5173`
- **Backend API Docs (Swagger):** `http://localhost:8000/docs`

### Production Multi-Stage Deployment
Run the optimized multi-stage build (`Dockerfile.prod`) backed by Nginx:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```
- **Production Dashboard (Nginx):** `http://localhost:80`
- **Backend REST Service:** `http://localhost:8000`

---

## ☁️ Deployment Strategy 2: Cloud Managed Services

### AWS Elastic Container Service (ECS Fargate)
1. Build and push images to AWS Elastic Container Registry (ECR):
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com
   
   docker build -t edipro-backend -f src/backend/Dockerfile src/
   docker tag edipro-backend:latest <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/edipro-backend:latest
   docker push <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/edipro-backend:latest
   ```
2. Provision an AWS Application Load Balancer (ALB) with an AWS Certificate Manager (ACM) SSL certificate.
3. Configure ECS Task Definition with 1024 CPU units and 2048MB memory.

### Google Cloud Run
Deploy backend and frontend services directly with GCP Cloud Run:

```bash
# Deploy Backend Service
gcloud run deploy edipro-backend \
  --source ./src \
  --dockerfile ./backend/Dockerfile \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

# Deploy Frontend Service
gcloud run deploy edipro-frontend \
  --source . \
  --dockerfile ./Dockerfile.prod \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

## 🛡️ Nginx Reverse Proxy & SSL/TLS Configuration

For single-node Linux servers (Ubuntu/Debian) running Nginx directly, use the following production block with Let's Encrypt SSL (`certbot`):

```nginx
server {
    listen 80;
    server_name edipro.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name edipro.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/edipro.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/edipro.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Gzip Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    location / {
        root /var/www/edipro/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🔒 HIPAA Security & Privacy Compliance

Handling Protected Health Information (PHI) under U.S. HIPAA regulations mandates specific infrastructural guards:

1. **Stateless Processing**: EdiPro is designed to parse EDI files strictly in memory. File uploads are decoded in streaming memory buffers (`io.BytesIO`) without persisting raw PHI to disk.
2. **Encryption in Transit**: Ensure all public endpoints are forced over TLS 1.2+ (HTTPS). WebSockets and HTTP calls MUST use TLS encryption.
3. **LLM Provider Egress Compliance**: When using LLM insight extensions (`GROQ_API_KEY` or `HUGGINGFACE_API_KEY`), verify that your API agreement with the LLM provider includes a Signed **Business Associate Agreement (BAA)** or disable external LLM routing for confidential PHI workloads.
4. **Access Control & Auditing**: Enable access logs on Nginx/Cloud Load Balancer to capture IP addresses, timestamps, and request routes for compliance reporting.

---

## 🚀 CI/CD Pipeline Integration (GitHub Actions)

Save the following pipeline to `.github/workflows/deploy.yml` to run automated testing and linting on every push:

```yaml
name: EdiPro CI/CD Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    name: Backend & Frontend Validation
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Backend Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]
          pip install -r src/backend/requirements.txt

      - name: Run Pytest Suite
        run: |
          python -m pytest --cov=validedi

      - name: Set up Node.js 20
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: 'src/stitch/package-lock.json'

      - name: Build Frontend Application
        run: |
          cd src/stitch
          npm ci
          npm run build
```

---

## 🛠️ Operational Diagnostics & Monitoring

### Checking Container Logs
```bash
# View backend logs
docker compose logs -f backend

# View frontend logs
docker compose logs -f frontend
```

### Healthcheck Monitoring Endpoint
Ping `/api/health` for automated uptime checks (e.g. AWS Route53 Health Checks or Datadog Synthetic Monitoring):
```bash
curl -i http://localhost:8000/api/health
# Response: HTTP/1.1 200 OK {"status":"ok"}
```
