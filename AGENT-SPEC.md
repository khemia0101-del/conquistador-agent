# Agent Spec: Craigslist Hunter

## What It Does

Autonomous AI agent that runs 24/7 on a $6/month server. Every 30 minutes it:

1. Scrapes Craigslist for data entry, bookkeeping, and admin gigs
2. Evaluates each listing using an LLM to score autonomous deliverability (0.0–1.0)
3. Auto-sends professional proposals for high-confidence matches
4. Asks the user about borderline matches via Telegram/Discord/WhatsApp
5. Skips bad matches and flags scams

The agent only applies to jobs it can actually complete end-to-end with no human help.

## Architecture

```
Cron (every 30 min)
  │
  ▼
scrape.py ── Fetches listings from Craigslist (pure Python, no deps)
  │            - Searches multiple regions and categories
  │            - Parses HTML, extracts title/body/compensation/URL
  │            - Deduplicates via SHA256 hash
  │            - Rate-limited (2s between regions, 1s between details)
  │            - Output: JSON array of listings
  │
  ▼
evaluate.py ── Scores each listing via NVIDIA NIM API (Kimi K2.5 LLM)
  │            - Sends listing text + evaluation criteria to LLM
  │            - LLM returns: confidence score, deliverable, blockers,
  │              matched capabilities, red flags, suggested rate, effort estimate
  │            - Labels: FULFILL (0.85+), MAYBE (0.50–0.84), SKIP (<0.50)
  │            - Output: JSON array of evaluated listings
  │
  ▼
Decision logic (handled by the agent framework, not a script)
  │  FULFILL + no red flags  → auto-send proposal
  │  FULFILL + red flags     → ask user first
  │  MAYBE + no red flags    → show to user, ask for approval
  │  MAYBE + red flags       → show + recommend skip
  │  SKIP                    → ignore silently
  │
  ▼
send_proposal.py ── Sends email via Zoho Mail SMTP
  │            - TLS on port 587
  │            - Takes --to, --subject, --body-file
  │            - Signs as "OpenClaw Professional Services"
  │
  ▼
Report summary to user via messaging channel
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent framework | OpenClaw (open-source, Node.js) |
| LLM | Kimi K2.5 via NVIDIA NIM API (free tier, 256K context) |
| Scripts | Python 3 (zero external dependencies) |
| Email | Zoho Mail SMTP |
| Hosting | Digital Ocean Ubuntu droplet |
| User interface | Telegram, Discord, or WhatsApp (via OpenClaw channels) |

## What the Agent Can Deliver

- Data entry: scans/PDFs/images → spreadsheets
- Spreadsheet creation, formatting, cleaning (CSV/Excel)
- Web research → compiled reports
- Audio/video transcription
- Document format conversion (PDF ↔ Word ↔ CSV ↔ text)
- Data categorization (receipts, expenses, inventory)
- Text drafting (emails, letters, templates)
- Proofreading and copyediting
- Bookkeeping from file-based records (no SaaS logins)
- Invoice processing from PDFs/images

## What It Auto-Rejects

- Jobs requiring proprietary SaaS logins (QuickBooks, Salesforce, etc.)
- Real-time interaction (calls, meetings, live chat)
- Physical presence
- Professional licenses (CPA, legal, etc.)
- Ongoing availability ("be online 9-5")
- Vague/unbounded scope
- Identity verification or background checks
- Software development, design, or website building

## Evaluation Criteria

The LLM scores each listing on these dimensions:

- **Deliverable clarity**: Can you name a concrete output?
- **Workflow feasibility**: Is it file-in, file-out? Or does it need live system access?
- **Blockers**: Anything preventing autonomous completion?
- **Capability match**: Does it align with the agent's skill set?
- **Red flags**: Scams, MLM, upfront payments, personal info requests?
- **Effort estimate**: small / medium / large

## Safety Limits

- Max 10 proposals per day without user approval
- Every proposal logged (URL, subject, timestamp)
- Never shares personal info beyond service provider name and email
- Suspicious listings flagged to user immediately

## Proposal Format

1. **Opening**: Reference the specific posting, state the deliverable back
2. **Approach**: Concrete steps for this specific job
3. **Turnaround**: Realistic timeframe (same day or 24h for small jobs)
4. **Pricing**: Match listed rate, or $18–35/hr data entry, $25–50/hr bookkeeping
5. **Closing**: Brief sign-off as "OpenClaw Professional Services"

## File Structure

```
conquistador-agent/
├── openclaw.example.json         # OpenClaw config (LLM, channels, cron)
├── .env.example                  # API keys template
├── config/cron.json              # 30-minute scan schedule
├── deploy/setup-droplet.sh       # One-command server setup
└── skills/craigslist-hunter/
    ├── SKILL.md                  # Full agent instructions and rules
    └── scripts/
        ├── scrape.py             # Craigslist scraper (pure Python)
        ├── evaluate.py           # NVIDIA NIM evaluator
        └── send_proposal.py      # Zoho SMTP sender
```

## Key Design Decisions

- **Zero external Python dependencies**: All scripts use stdlib only (urllib, html.parser, smtplib, json, argparse)
- **File-based pipeline**: Each script reads JSON in, writes JSON out — loosely coupled
- **LLM does the judgment**: Evaluation criteria are embedded in the prompt, not hardcoded rules
- **Agent framework handles orchestration**: OpenClaw manages scheduling, user interaction, and decision routing
- **Conservative by default**: High threshold (0.85) for auto-sending, user confirmation for anything uncertain
