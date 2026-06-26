FROM python:3.12-slim AS builder

WORKDIR /app

# System dependencies for PyTorch (CPU), sentence-transformers, pdfplumber
#   g++ required for opentsne (no pre-built wheel on ARM64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
# Notes:
#   - requirements.txt targets CUDA torch for local dev; Docker strips that for CPU-only
#   - psycopg2 → psycopg2-binary avoids compiling from source
COPY requirements.txt .
RUN sed -i '/^--extra-index-url/d' requirements.txt && \
    sed -i '/^torch==/d' requirements.txt && \
    sed -i 's/^psycopg2==/psycopg2-binary==/' requirements.txt && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt && \
    # app imports umap (not in requirements.txt for dev env compatibility?)
    pip install --no-cache-dir umap-learn

# instructor 1.14.5 does `from mistralai import Mistral` but mistralai==2.4.0
# is a namespace package (no __init__.py) — Mistral is in mistralai.client.
# Add an __init__.py to re-export it.
RUN echo 'from mistralai.client import Mistral' > /usr/local/lib/python3.12/site-packages/mistralai/__init__.py

# ────────────────────────────────────────────────────────────────────────────
# Runtime stage — lean
# ────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system libs (OpenMP for PyTorch/NumPy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY . .

# PYTHONPATH so both `import database` and `from app.embedders import` work
ENV PYTHONPATH=/app:/app/app

# Create runtime directories expected by the app
RUN mkdir -p /app/rag_sessions /app/rag_sessions_csv /app/session_evaluations /app/exports

EXPOSE 8000

CMD ["uvicorn", "app.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
