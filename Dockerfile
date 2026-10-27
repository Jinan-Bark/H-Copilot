# H-Copilot backend: prediction layer, optimization layer and FastAPI service
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code, trained models and data (the code reads ../data/raw, so keep this layout)
COPY backend/ /app/backend/
COPY data/ /app/data/

WORKDIR /app/backend
EXPOSE 8000

# Default: start the API. DATABASE_URL must be set (docker compose does this).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
