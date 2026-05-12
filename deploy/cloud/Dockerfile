# ClawShell Cloud Hub — Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-cloud.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "cloud.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
