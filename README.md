# Craigslist Hunter — OpenClaw Skill

An autonomous AI agent that scans Craigslist for data entry, bookkeeping, and admin gigs — evaluates them for fit, drafts professional proposals, and sends them automatically. Built as a skill plugin for [OpenClaw](https://github.com/openclaw/openclaw).

---

## How It Works

```
Every 30 minutes:

  Craigslist ──scrape──▶ Listings ──evaluate──▶ Scored Results ──decide──▶ Action
                                   (NVIDIA NIM)
                                                    FULFILL → auto-send proposal
                                                    MAYBE   → ask user first
                                                    SKIP    → ignore silently
```

The agent only pursues jobs it can **complete end-to-end**. Before applying to any listing, it asks: *"If they hire me right now, can I deliver the finished work product?"*

## What the Agent Can Deliver

| Category | Examples |
|----------|----------|
| **Data Entry** | Scanned receipts → spreadsheets, PDF tables → CSV, handwritten notes → typed documents |
| **Spreadsheets** | Creating, formatting, cleaning, merging CSV/Excel files |
| **Web Research** | Company lists, contact info, market data → compiled reports |
| **Transcription** | Audio/video files → text documents |
| **Document Conversion** | PDF ↔ Word ↔ CSV ↔ text |
| **Data Organization** | Categorizing receipts, expenses, inventory |
| **Writing** | Emails, letters, form responses, templates, proofreading |
| **Bookkeeping** | Invoice processing from PDFs/images (file-based only, no SaaS logins) |

The agent **auto-rejects** jobs requiring proprietary system access (QuickBooks, Salesforce), real-time interaction (calls, meetings), physical presence, professional licenses, or ongoing availability.

## Prerequisites

| Service | Purpose | Link |
|---------|---------|------|
| **Digital Ocean** | Server hosting (~$6/mo) | [digitalocean.com](https://www.digitalocean.com) |
| **NVIDIA NIM** | AI evaluation engine (free tier) | [build.nvidia.com](https://build.nvidia.com) |
| **Zoho Mail** | Sending proposal emails | [zoho.com/mail](https://www.zoho.com/mail/) |
| **Telegram / Discord** | Talking to the agent | Your existing account |

## Quick Start

### 1. Create a server

Spin up an Ubuntu 22.04+ droplet on Digital Ocean (the $6/month tier works fine).

### 2. Run the setup script

SSH into your server and run:

```
bash <(curl -fsSL https://bit.ly/openclaw-setup)
```

Or if you prefer the full URL:

```
bash <(curl -fsSL https://raw.githubusercontent.com/khemia0101-del/conquistador-agent/claude/openclaw-craigslist-agent-4TkQl/deploy/setup-droplet.sh)
```

This installs Node.js 22, Python 3, OpenClaw, and clones this repo.

### 3. Configure API keys

```
cp /opt/openclaw-agent/.env.example /opt/openclaw-agent/.env
```

```
nano /opt/openclaw-agent/.env
```

Fill in your keys:

```
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxx
ZOHO_SMTP_USER=agent@yourdomain.com
ZOHO_SMTP_PASSWORD=your_zoho_app_password
```

Then load them:

```
export $(cat /opt/openclaw-agent/.env | grep -v '^#' | xargs)
```

### 4. Configure a messaging channel

```
openclaw configure --section channels
```

Follow the prompts to connect Telegram, Discord, or WhatsApp.

### 5. Start the agent

```
openclaw gateway run --install-daemon
```

### 6. Enable automatic scanning

```
openclaw cron add --name "craigslist-scan" --every "30m" --session isolated --announce --message "Run the craigslist-hunter skill: scan all regions for new listings, evaluate them, and take action per the decision rules."
```

The agent now runs 24/7, scanning every 30 minutes and reporting results through your messaging channel.

## Talking to the Agent

Message your agent through Telegram (or your configured channel):

- **"Search Craigslist in Boston for data entry gigs"**
- **"Scan New York and Chicago for accounting jobs"**
- **"Find me some freelance admin work on Craigslist"**
- **"Show me what you found today"**
- **"Stop auto-applying, just show me listings"**

## Project Structure

```
conquistador-agent/
├── README.md                          # This file
├── openclaw.example.json              # OpenClaw configuration template
├── .env.example                       # API keys template
├── config/
│   └── cron.json                      # Scheduled scan config (every 30 min)
├── deploy/
│   └── setup-droplet.sh               # One-command server setup script
└── skills/
    └── craigslist-hunter/
        ├── SKILL.md                   # Agent skill definition & instructions
        └── scripts/
            ├── scrape.py              # Craigslist scraper (pure Python, no deps)
            ├── evaluate.py            # NVIDIA NIM job evaluator
            └── send_proposal.py       # Zoho Mail SMTP proposal sender
```

## How Evaluation Works

Each listing is scored on **autonomous deliverability** (0.0–1.0) using NVIDIA NIM (Kimi K2.5):

| Score | Label | Action |
|-------|-------|--------|
| 0.85–1.0 | **FULFILL** | Auto-send proposal |
| 0.50–0.84 | **MAYBE** | Ask user for approval |
| Below 0.50 | **SKIP** | Skip silently |

Red flags (upfront payments, personal financial info, MLM schemes) trigger additional user confirmation even on FULFILL scores.

**Safety limits**: Max 10 proposals/day without user approval. Every proposal is logged with URL, subject, and timestamp.

## Scripts Reference

### scrape.py

Fetches listings from Craigslist. Pure Python — no external dependencies.

```
python3 skills/craigslist-hunter/scripts/scrape.py --regions newyork,sfbay --output /tmp/listings.json
```

| Flag | Description | Default |
|------|-------------|---------|
| `--regions` | Craigslist subdomains (comma-separated) | `newyork,sfbay,losangeles,chicago` |
| `--categories` | `cpg` (computer gigs), `acc` (accounting), `ofc` (admin) | `cpg,acc,ofc` |
| `--output` | Output file path | stdout |
| `--no-details` | Skip fetching individual listing pages (faster) | off |

### evaluate.py

Scores listings using NVIDIA NIM. Requires `NVIDIA_API_KEY` env var.

```
python3 skills/craigslist-hunter/scripts/evaluate.py --listings-file /tmp/listings.json --output /tmp/evaluated.json
```

### send_proposal.py

Sends proposal emails through Zoho Mail SMTP. Requires `ZOHO_SMTP_USER` and `ZOHO_SMTP_PASSWORD` env vars.

```
python3 skills/craigslist-hunter/scripts/send_proposal.py --to client@example.com --subject "Data Entry Proposal" --body-file /tmp/proposal.txt
```

## Configuration

Copy `openclaw.example.json` to `~/.openclaw/openclaw.json` and customize:

- **LLM model**: Uses Kimi K2.5 via NVIDIA NIM by default (256K context, free tier)
- **Channels**: Uncomment and configure your preferred messaging platform
- **Cron**: Scanning frequency (default: every 30 minutes)
- **Gateway auth**: Change the default token to a random string

## Tech Stack

- **[OpenClaw](https://github.com/openclaw/openclaw)** — Open-source AI agent framework
- **[NVIDIA NIM](https://build.nvidia.com)** — AI inference API (Kimi K2.5 model)
- **Python 3** — Scraping and evaluation scripts (zero external dependencies)
- **Zoho Mail** — SMTP email delivery
- **Node.js 22** — OpenClaw runtime

## License

Open source. Use it, modify it, run your own agent.
