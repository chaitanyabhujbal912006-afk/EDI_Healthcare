FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app

COPY pyproject.toml README.md* ./
COPY src/validedi ./src/validedi
RUN pip install --no-cache-dir -e .

COPY src/backend/requirements.txt ./requirements.txt
RUN grep -v '^\-e' requirements.txt > reqs.txt && pip install --no-cache-dir -r reqs.txt

COPY src/validedi ./validedi
COPY src/backend/app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
