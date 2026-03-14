# Craigslist Hunter — OpenClaw Skill

A custom OpenClaw AgentSkill that scans Craigslist for data entry, bookkeeping, and admin gigs, evaluates them, and sends professional proposals automatically.

## What This Is

This is a **skill plugin** for [OpenClaw](https://github.com/openclaw/openclaw), the open-source AI agent framework. OpenClaw runs 24/7 on your server and you talk to it through Telegram, Discord, WhatsApp, or any other messaging platform.

This skill teaches the agent how to:
1. Scrape Craigslist for relevant job/gig listings
2. Evaluate each listing using NVIDIA NIM AI
3. Auto-send professional proposals to great matches
4. Ask you about borderline matches before responding
5. Skip bad matches and flag scams

## Quick Setup (Non-Technical)

See the full step-by-step walkthrough below. In short:

1. Create a Digital Ocean server ($6/month)
2. Run the setup script
3. Add your API keys
4. The agent runs forever, scanning every 30 minutes

## What You Need Before Starting

- A **Digital Ocean** account ([sign up here](https://www.digitalocean.com))
- An **NVIDIA NIM API key** ([get one free here](https://build.nvidia.com))
- A **Zoho Mail** account for the agent ([sign up here](https://www.zoho.com/mail/))
- A **Telegram** account (or Discord, WhatsApp, etc.) to talk to the agent

## File Structure

```
skills/craigslist-hunter/
├── SKILL.md              # The skill definition (instructions for the agent)
└── scripts/
    ├── scrape.py         # Craigslist scraper
    ├── evaluate.py       # NVIDIA NIM job evaluator
    └── send_proposal.py  # Sends proposals via Zoho Mail

openclaw.example.json     # Example OpenClaw config
deploy/setup-droplet.sh   # Server setup script
.env.example              # API keys template
```

## Talking to Your Agent

Once running, message your agent through Telegram (or whichever channel you set up):

- **"Search Craigslist in Boston for data entry gigs"**
- **"Scan New York and Chicago for accounting jobs"**
- **"Find me some freelance admin work on Craigslist"**
- **"Show me what you found today"**

The agent will scrape, evaluate, and either auto-send proposals or ask for your approval.
