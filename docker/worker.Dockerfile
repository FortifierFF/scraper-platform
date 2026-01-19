FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY services/worker/requirements.txt ./services/worker/

# Install Python dependencies
RUN pip install --no-cache-dir -r services/worker/requirements.txt

# Copy application code
COPY services/worker ./services/worker

# Default command (can be overridden in docker-compose)
CMD ["python", "services/worker/main.py"]
