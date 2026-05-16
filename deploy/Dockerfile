# ClawShell Cloud Hub — Dockerfile v2.0
# Build context: project root (..)

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-cloud.txt

# Copy application code
COPY cloud/ ./cloud/
COPY shared/ ./shared/
COPY bin/ ./bin/
COPY CLAWSHELL_VERSION ./

# Create data directory
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "cloud.main"]
