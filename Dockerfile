# Use official slim Python runtime
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files first (for Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN uv sync --frozen --no-dev

# Copy application source code
COPY app/ ./app/
COPY .env ./

# Pre-download and cache the sentence-transformer model during build phase
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Expose ports for Gateway (8000) and Streamlit (8501)
EXPOSE 8000 8501

# Default command: launch FastAPI Gateway
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]