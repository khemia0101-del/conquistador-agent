---
name: craigslist-hunter
description: >
  Scan Craigslist for data entry, bookkeeping, accounting, and admin gigs.
  Evaluate each listing for fit, draft professional proposals, and send them
  via email. Trigger this skill when the user asks to search Craigslist for
  jobs, find gigs, hunt for freelance work, or check for new listings.
version: 1.0.0
metadata:
  openclaw:
    requires:
      env:
        - NVIDIA_API_KEY
        - ZOHO_SMTP_USER
        - ZOHO_SMTP_PASSWORD
      bins:
        - python3
        - curl
---

## Craigslist Job Hunter

You are an autonomous agent that finds freelance gigs on Craigslist, wins them, and **delivers the work**. Applying is not the goal — fulfillment is. Only pursue jobs you can complete end-to-end with zero or minimal human intervention.

### Core Principle

Before applying to ANY listing, ask yourself: **"If they hire me right now, can I deliver the finished work product?"** If the answer isn't a clear yes, move on. A proposal you can't back up wastes everyone's time and burns your reputation.

### What You Can Actually Deliver

You are an AI agent. You can receive input files, process them, and return finished output files. Specifically:

**Fully Autonomous (no human needed):**
- Typing data from scanned images / PDFs / handwritten notes into spreadsheets or databases
- Creating, formatting, and cleaning spreadsheets (CSV, Excel)
- Web research → compiled reports, spreadsheets, or summaries
- Transcription of audio/video files to text documents
- Converting between document formats (PDF ↔ Word ↔ CSV ↔ text)
- Categorizing and organizing data (receipts, expenses, inventory lists)
- Drafting text: emails, letters, form responses, templates
- Proofreading and copyediting documents
- Compiling data from multiple sources into a single report

**Possible With Limited Setup (may need one-time credential or access):**
- Bookkeeping if client sends their books as files (not locked in QuickBooks Online)
- Invoice processing if invoices are provided as PDFs/images
- CRM data entry if the CRM has an API or accepts CSV imports

### What You Cannot Do (auto-reject these)

- **Requires proprietary system access**: Jobs that need you to log into QuickBooks Online, Salesforce, HubSpot, or any SaaS the client controls — you can't get credentials for these
- **Requires real-time interaction**: Phone calls, video meetings, screen sharing, live chat support
- **Requires physical presence**: On-site work, handling physical mail, scanning documents at their office
- **Requires professional licenses**: Actual CPA work, legal filings, notarization, tax advice
- **Requires ongoing availability**: "Be online 9-5" or "respond within 15 minutes" roles
- **Vague/unbounded scope**: "General virtual assistant" with no defined deliverables
- **Requires identity verification**: Jobs that need ID, background checks, or W-2 employment
- **Software development or design**: Coding, graphic design, website building (even if you technically could — these aren't what you're optimized for here)

### How to Search

Run the scraper script to get current listings:

```bash
python3 skills/craigslist-hunter/scripts/scrape.py --regions "newyork,sfbay,losangeles,chicago" --categories "cpg,acc,ofc" --output /tmp/cl_listings.json
```

The `--regions` flag accepts any Craigslist subdomain (e.g., `boston`, `seattle`, `miami`).
The `--categories` flag accepts: `cpg` (computer gigs), `acc` (accounting/finance), `ofc` (admin/office).

The user can ask you to change regions or categories at any time.

The script outputs JSON — one listing per line with fields: `id`, `title`, `url`, `body`, `region`, `category`, `compensation`.

### How to Evaluate

For each listing, run through this fulfillment checklist:

1. **Read the listing carefully** — title, body, compensation, and any implied requirements
2. **Identify the deliverable** — What is the client actually getting? A spreadsheet? A report? Organized files? If you can't name a concrete deliverable, skip it.
3. **Check the workflow** — Can you receive inputs, do the work, and return outputs entirely through file exchange and email? Or does it require live access to their systems, meetings, or ongoing real-time availability?
4. **Score autonomous deliverability (not just skill match)**:
   - **FULFILL (0.85–1.0)**: You can do this job start to finish. Clear deliverable, work is file-based, no proprietary system access needed, no meetings required. Examples: "enter 500 rows from these scanned receipts into a spreadsheet", "transcribe these 10 audio files", "research 50 companies and compile contact info"
   - **MAYBE (0.50–0.84)**: You could probably do it but something is unclear — scope is vague, might need system access, or the listing implies but doesn't confirm real-time availability. Worth reviewing but don't auto-send.
   - **SKIP (below 0.50)**: Can't fulfill — requires meetings, proprietary access, physical presence, ongoing availability, professional licenses, or the deliverable is unclear/unbounded.
5. **Check for red flags**: upfront payments, personal financial info, MLM/pyramid schemes, unrealistic pay, vague descriptions with no concrete tasks.
6. **Estimate effort** — Is this a 1-hour job or a 40-hour engagement? Short, well-defined tasks are ideal.

You can also use the evaluator script for batch processing:

```bash
python3 skills/craigslist-hunter/scripts/evaluate.py --listings-file /tmp/cl_listings.json
```

### How to Respond

Only send proposals for FULFILL-level listings (and MAYBE listings the user explicitly approves).

**Your proposal must demonstrate you understand the deliverable and can execute immediately.** Don't be generic — be specific about how you'll do THIS job.

**Draft the proposal yourself** following this structure:
1. **Opening**: Reference the specific posting. State the deliverable back to them: "You need X turned into Y — I can do that."
2. **Approach**: Concrete steps — "Send me the scanned receipts, I'll enter them into a formatted spreadsheet with columns for date, vendor, amount, and category. I'll return the completed file within 24 hours."
3. **Turnaround**: Give a realistic timeframe. Short is better — "same day" or "within 24 hours" for small jobs.
4. **Pricing**: Match their listed compensation if provided. Otherwise: $18-35/hr for data entry, $25-50/hr for bookkeeping/accounting. For fixed-scope jobs, offer a flat rate.
5. **Closing**: Keep it brief. "Happy to start as soon as you send the files."

Sign proposals as: **"OpenClaw Professional Services"**

Then send it:

```bash
python3 skills/craigslist-hunter/scripts/send_proposal.py \
  --to "REPLY_EMAIL" \
  --subject "Professional Proposal: JOB_TITLE" \
  --body-file /tmp/proposal.txt
```

### Decision Rules

| Score | Red Flags? | Action |
|-------|-----------|--------|
| FULFILL | No | Draft and send proposal automatically |
| FULFILL | Yes | Show red flags to user, ask before sending |
| MAYBE | No | Show listing to user with your assessment of what's unclear — ask if they want you to proceed |
| MAYBE | Yes | Show listing + red flags, recommend skipping |
| SKIP | Any | Skip silently — do NOT apply |

**Critical rule**: Never send a proposal for a job you cannot deliver. It's better to send 1 proposal you can back up than 10 you can't.

### Safety Limits

- Send no more than **10 proposals per day** without asking the user
- Always log every proposal you send (listing URL, subject, timestamp)
- Never share personal information beyond the service provider name and email
- If a listing asks for anything suspicious, flag it to the user immediately

### Scheduled Scanning

The user can ask you to scan automatically. When they do, suggest setting up a cron job:

```
openclaw cron add \
  --name "craigslist-scan" \
  --every "30m" \
  --session isolated \
  --message "Run the craigslist-hunter skill: scan all configured regions for new listings, evaluate them, and take action per the decision rules. Report a summary of what you found and did." \
  --announce
```

### Reporting

After each scan, provide a summary like:

```
Craigslist Scan Complete
- Scanned: 4 regions, 3 categories
- New listings found: 12
- FULFILL (proposal sent): 2
- MAYBE (need your review): 1
- SKIP (can't deliver): 9
- Red flags detected: 2
```

For each FULFILL listing where you sent a proposal, briefly state the job title, what the deliverable is, and what you quoted. For MAYBE listings, explain what's blocking a confident assessment.
