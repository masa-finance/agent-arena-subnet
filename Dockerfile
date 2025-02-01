# Use Python 3.10 for stability
FROM --platform=linux/amd64 python:3.10-slim

# Set environment variables
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Set up workspace
WORKDIR /app

# Copy local files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir \
    "bittensor==6.6.0" \
    "loguru==0.7.2" \
    "python-dotenv==1.0.0" \
    "torch==2.1.2" \
    "scikit-learn==1.3.2" \
    "masa-ai==0.2.5" \
    "pytest==7.4.4" \
    "pytest-asyncio==0.23.3" \
    "requests==2.31.0"

# Set environment variables
ENV CONFIG_PATH=/app/subnet-config.json \
    ROLE=validator \
    NETWORK=test \
    PYTHONPATH=/app

# Use Python for entrypoint
ENTRYPOINT ["python", "-u", "/app/startup/entrypoint.py"]