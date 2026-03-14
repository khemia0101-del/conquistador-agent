# OpenClaw - Autonomous Craigslist Job Agent

An AI-powered agent that autonomously scans Craigslist for data entry, accounting, and admin gigs, evaluates them for fit, and sends professional proposals to potential clients.

## Architecture

```
Craigslist ──scrape──▶ Listings ──evaluate──▶ Scored Results ──decide──▶ Actions
                                    │                              │
                              NVIDIA NIM API                 ┌─────┴─────┐
                              + OpenAI (optional)       Auto-respond   Notify
                                                       (≥0.85 conf)  (0.40-0.84)
                                                            │            │
                                                      Send proposal   Email digest
                                                      via Zoho Mail   for review
```

## Features

- **Multi-region scraping**: Searches multiple Craigslist regions for computer gigs, accounting, and admin jobs
- **AI-powered evaluation**: Uses NVIDIA NIM (Llama 3.1 70B) to score listing fit against 15+ service capabilities
- **Dual-evaluator mode**: Optional OpenAI/ChatGPT integration via OAuth for cross-validation
- **Professional proposals**: Auto-drafts detailed, personalized proposals for high-confidence matches
- **Smart thresholds**: Auto-respond (≥85% confidence), notify for review (40-84%), ignore (<40%)
- **Scam detection**: Flags red flags like upfront payments, MLM indicators, unrealistic pay
- **Safety limits**: Configurable daily auto-response cap (default: 10/day)
- **Zoho Mail integration**: Agent has its own email identity for sending proposals

## Quick Start

### 1. Prerequisites

- Python 3.11+
- [NVIDIA NIM API key](https://build.nvidia.com/)
- Zoho Mail account for the agent (for sending proposals)
- (Optional) OpenAI OAuth credentials for dual-evaluator mode

### 2. Setup

```bash
# Clone and install
git clone <repo-url>
cd conquistador-agent
pip install .

# Configure
cp .env.example .env
# Edit .env with your API keys and Zoho Mail credentials
```

### 3. Run

```bash
# Run the agent
openclaw

# Or with Docker
docker compose up -d
docker compose logs -f
```

### 4. (Optional) OpenAI OAuth Setup

```bash
# Set OPENAI_CLIENT_ID and OPENAI_CLIENT_SECRET in .env, then:
openclaw-oauth
# Follow the browser prompt to authenticate
```

## Configuration

All config is via environment variables (`.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NVIDIA_API_KEY` | Yes | - | NVIDIA NIM API key |
| `NVIDIA_MODEL` | No | `meta/llama-3.1-70b-instruct` | NIM model for evaluation |
| `CRAIGSLIST_REGIONS` | No | `newyork,sfbay,losangeles,chicago` | Regions to scan |
| `SCAN_INTERVAL_MINUTES` | No | `30` | Minutes between scan cycles |
| `AUTO_RESPOND_THRESHOLD` | No | `0.85` | Confidence threshold for auto-respond |
| `MAX_AUTO_RESPONSES_PER_DAY` | No | `10` | Safety cap on daily auto-responses |
| `SMTP_HOST` | No | `smtp.zoho.com` | SMTP server |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | No | - | Agent's email (e.g., `agent@yourdomain.com`) |
| `SMTP_PASSWORD` | No | - | Zoho app password |
| `NOTIFY_EMAIL` | No | - | Your email for review notifications |
| `OPENAI_CLIENT_ID` | No | - | OpenAI OAuth client ID |
| `OPENAI_CLIENT_SECRET` | No | - | OpenAI OAuth client secret |

## Deploy to Digital Ocean

```bash
# On a fresh Ubuntu droplet:
bash deploy/setup-droplet.sh

# Then:
cd /opt/openclaw
git clone <repo-url> .
cp .env.example .env
nano .env  # Add your keys
docker compose up -d
```

## Agent Capabilities

The agent advertises competence in:

- Data entry & database cleanup
- Spreadsheet management
- Bookkeeping & accounts payable/receivable
- Invoice processing
- PDF and document conversion
- Email management & organization
- CRM data entry
- Transcription
- Web research & data collection
- Inventory tracking
- Payroll data entry
- Tax document preparation
- Receipt & expense categorization

## Project Structure

```
openclaw/
├── config.py                    # Settings from env vars
├── models.py                    # Pydantic data models
├── main.py                      # Orchestrator & scheduler
├── scrapers/
│   └── craigslist.py            # Craigslist scraper
├── evaluator/
│   └── nim_evaluator.py         # NVIDIA NIM evaluator
├── responder/
│   └── drafter.py               # Proposal drafting & sending
├── notifier/
│   └── email_notifier.py        # Email notifications
├── integrations/
│   ├── chatgpt_oauth.py         # OpenAI OAuth client
│   ├── openai_evaluator.py      # OpenAI-backed evaluator
│   └── oauth_server.py          # OAuth callback server
└── utils/
    └── state.py                 # Persistent state management
```
