#!/usr/bin/env bash
# =============================================================
# OpenClaw + Craigslist Hunter — Digital Ocean Droplet Setup
# Run this on a fresh Ubuntu 22.04+ droplet as root
# =============================================================
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo ""
echo "======================================"
echo "  OpenClaw Agent — Server Setup"
echo "======================================"
echo ""

# --- 1. System updates ---
echo "[1/6] Updating system..."
apt-get update -qq && apt-get upgrade -y -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

# --- 2. Install Node.js 22 ---
echo "[2/6] Installing Node.js 22..."
if ! command -v node &>/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 22 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y -qq nodejs
fi
echo "  Node.js $(node -v) installed"

# --- 3. Install Python 3 (for skill scripts) ---
echo "[3/6] Ensuring Python 3 is available..."
apt-get install -y -qq python3

# --- 4. Install OpenClaw ---
echo "[4/6] Installing OpenClaw..."
npm install -g openclaw@latest
echo "  OpenClaw installed: $(openclaw --version 2>/dev/null || echo 'ok')"

# --- 5. Initialize OpenClaw ---
echo "[5/6] Initializing OpenClaw..."
openclaw onboard --non-interactive --accept-risk --mode local --skip-health
echo "  OpenClaw initialized"

# --- 6. Clone the repo with the custom skill ---
echo "[6/6] Setting up workspace..."
WORKSPACE="/opt/openclaw-agent"
mkdir -p "$WORKSPACE"

if [ ! -d "$WORKSPACE/skills" ]; then
    echo "  Cloning repo..."
    git clone https://github.com/khemia0101-del/conquistador-agent.git "$WORKSPACE"
    cd "$WORKSPACE"
    git checkout claude/openclaw-craigslist-agent-4TkQl
else
    echo "  Repo already exists, pulling latest..."
    cd "$WORKSPACE"
    git pull origin claude/openclaw-craigslist-agent-4TkQl
fi

# --- Create config directory ---
mkdir -p ~/.openclaw/workspace/skills

# --- Copy skill into OpenClaw's skill directory ---
echo "  Installing craigslist-hunter skill..."
cp -r "$WORKSPACE/skills/craigslist-hunter" ~/.openclaw/workspace/skills/

echo ""
echo "======================================"
echo "  Setup Complete!"
echo "======================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Set your API keys:"
echo "   cp $WORKSPACE/.env.example $WORKSPACE/.env"
echo "   nano $WORKSPACE/.env"
echo "   Then load them:"
echo "   export \$(cat $WORKSPACE/.env | grep -v '^#' | xargs)"
echo ""
echo "2. Configure a messaging channel (Telegram, Discord, etc.):"
echo "   openclaw configure --section channels"
echo ""
echo "3. Start the gateway daemon:"
echo "   openclaw gateway run --install-daemon"
echo ""
echo "4. Set up automatic scanning (every 30 minutes):"
echo "   openclaw cron add \\"
echo "     --name 'craigslist-scan' \\"
echo "     --every '30m' \\"
echo "     --session isolated \\"
echo "     --message 'Run the craigslist-hunter skill: scan all regions for new listings, evaluate them, and take action per the decision rules.' \\"
echo "     --announce"
echo ""
echo "5. Or just talk to it! Message the agent through your configured channel:"
echo "   'Search Craigslist in New York for data entry gigs'"
echo ""
