FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for LaTeX (optional, for compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex \
    texlive-lang-chinese \
    latexmk \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY tests/ tests/

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8000/health'); assert r.status_code==200"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
