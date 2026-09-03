FROM python:3.12-slim

WORKDIR /app

# Install build essentials for SQLite and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pytest httpx

COPY . .

# Seed synthetic catalog into SQLite and ChromaDB
RUN python scripts/init_db.py

EXPOSE 8000 8501

# Default launch command runs FastAPI backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
