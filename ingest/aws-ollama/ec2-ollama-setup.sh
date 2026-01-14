#!/bin/bash
#
# EC2 GPU Instance Setup Script for Ollama Inference Server
# 
# This script sets up an Ubuntu EC2 instance with:
# - NVIDIA drivers
# - Docker + nvidia-container-toolkit
# - Ollama running in a container
#
# Usage: Run this as EC2 user data or SSH in and run manually
#

set -e

echo "=== Starting Ollama GPU Server Setup ==="

# Update system
apt-get update
apt-get upgrade -y

# Install NVIDIA drivers
echo "Installing NVIDIA drivers..."
apt-get install -y ubuntu-drivers-common
ubuntu-drivers autoinstall

# Install Docker
echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Install NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    tee /etc/apt/sources.list.d/nvidia-docker.list

apt-get update
apt-get install -y nvidia-container-toolkit
systemctl restart docker

# Pull and run Ollama with GPU support
echo "Starting Ollama container..."
docker run -d \
    --gpus=all \
    --name ollama \
    -p 11434:11434 \
    -v ollama:/root/.ollama \
    --restart unless-stopped \
    ollama/ollama

# Wait for Ollama to start
echo "Waiting for Ollama to start..."
sleep 10

# Pull models
echo "Pulling LLM models..."
docker exec ollama ollama pull llama3.1:8b
docker exec ollama ollama pull nomic-embed-text

echo "=== Setup Complete ==="
echo ""
echo "Ollama is running on port 11434"
echo "To use from your laptop, set:"
echo "  export OLLAMA_HOST=http://<EC2_PUBLIC_IP>:11434"
echo ""
echo "Test with:"
echo "  curl http://localhost:11434/api/tags"
