#!/bin/bash
# ClawShell Cloud Hub — Bootstrap script for Alibaba Cloud ECS
set -e

echo "=== ClawShell Cloud Hub Bootstrap ==="

# Update system
apt-get update -y
apt-get upgrade -y

# Install Docker
apt-get install -y docker.io docker-compose git nginx
systemctl enable docker
systemctl start docker

# Clone repository
cd /opt
git clone https://github.com/jorinyang/ClawShell.git clawshell
cd clawshell

# Start services
docker-compose -f deploy/cloud/docker-compose.yml up -d

# Health check
sleep 5
curl -s http://localhost:8000/health || echo "Waiting for API..."

echo "=== Bootstrap Complete ==="
echo "Cloud Hub API: http://$(curl -s ifconfig.me):8000"
