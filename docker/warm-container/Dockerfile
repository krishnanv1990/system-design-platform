# Warm Container Base Image
# This container is pre-started and waits for candidate API code to be injected.
# Designed for sub-second deployment by keeping all dependencies pre-installed.

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    MODE=warm

# Install system dependencies for all potential database clients
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install common Python dependencies that candidates might need
# Pre-installing these makes code injection faster
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the warm container runner
COPY warm_runner.py .

# Create directory for candidate code injection
RUN mkdir -p /app/candidate

# Health check endpoint
HEALTHCHECK --interval=2s --timeout=1s --start-period=1s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose the port
EXPOSE ${PORT}

# Run the warm container runner
CMD ["python", "warm_runner.py"]
