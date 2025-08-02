FROM python:3.9-slim

# Install system dependencies for PyTorch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Security: Create a non-root user
RUN adduser --disabled-password --gecos '' appuser
WORKDIR /app
RUN chown appuser:appuser /app
USER appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Download the model during build to avoid re-downloading on each run
# For GPU support, use: FROM nvidia/cuda:11.8.0-base-ubuntu20.04
# Ensure PyTorch is installed with CUDA support: pip install torch==2.0.1+cu118
ARG MODEL_NAME="distilgpt2"
RUN python -c "from transformers import pipeline; pipeline('text-generation', model='${MODEL_NAME}')"

EXPOSE 5000

# Use gunicorn for a production-ready server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--worker-class", "gevent", "app:app"]
