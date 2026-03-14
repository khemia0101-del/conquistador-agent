#!/usr/bin/env bash
# Digital Ocean Droplet setup script for OpenClaw Agent
# Run this on a fresh Ubuntu 22.04+ droplet
set -euo pipefail

echo "=== OpenClaw Agent - Digital Ocean Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose
if ! command -v docker-compose &>/dev/null; then
    echo "Installing Docker Compose..."
    apt-get install -y docker-compose-plugin
fi

# Create app directory
mkdir -p /opt/openclaw
cd /opt/openclaw

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Clone the repo:  git clone <repo-url> /opt/openclaw"
echo "2. Copy .env:       cp .env.example .env"
echo "3. Edit .env:       nano .env  (add your API keys)"
echo "4. Start agent:     docker compose up -d"
echo "5. View logs:       docker compose logs -f"
echo ""
echo "For Zoho Mail setup:"
echo "  - Create a Zoho Mail account for the agent"
echo "  - Generate an App Password in Zoho security settings"
echo "  - Set SMTP_USER and SMTP_PASSWORD in .env"
echo ""
echo "For OpenAI OAuth (optional):"
echo "  - Set OPENAI_CLIENT_ID and OPENAI_CLIENT_SECRET in .env"
echo "  - Run: docker compose run openclaw-agent openclaw-oauth"
