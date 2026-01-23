# Multi-stage build for optimal Docker layer caching and security
FROM python:3.11-slim AS base

# Set environment variables for Python optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y \
    # Required for asyncpg and other compiled packages
    gcc \
    # Required for health checks
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --shell /bin/bash appuser

# Set work directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml .

# Copy application code
COPY . .

# Install package with all dependencies
RUN pip install --no-cache-dir -e .[dev]

# Create necessary directories and set permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check using the existing health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Expose port
EXPOSE 8000

# Default command - can be overridden in docker-compose for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]