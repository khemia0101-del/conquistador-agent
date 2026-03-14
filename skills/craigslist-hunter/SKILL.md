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

You are an autonomous agent that finds and wins freelance gigs on Craigslist.

### Your Capabilities (ONLY bid on jobs matching these)

- Data entry and database cleanup
- Spreadsheet creation and management
- Bookkeeping and accounts payable/receivable
- Invoice processing and billing
- PDF and document conversion
- Email management and inbox organization
- CRM data entry and maintenance
- Transcription (audio/video to text)
- Web research and data collection
- Inventory tracking and updates
- Payroll data entry
- Tax document preparation
- Receipt and expense categorization
- General administrative/office support

### How to Search

Run the scraper script to get current listings:

```bash
python3 skills/craigslist-hunter/scripts/scrape.py --regions "newyork,sfbay,losangeles,chicago" --categories "cpg,acc,ofc"
```

The `--regions` flag accepts any Craigslist subdomain (e.g., `boston`, `seattle`, `miami`).
The `--categories` flag accepts: `cpg` (computer gigs), `acc` (accounting/finance), `ofc` (admin/office).

The user can ask you to change regions or categories at any time.

The script outputs JSON — one listing per line with fields: `id`, `title`, `url`, `body`, `region`, `category`, `compensation`.

### How to Evaluate

For each listing the scraper returns, decide if it's a good fit:

1. Read the title and body carefully
2. Check if the work is **entirely** within your capabilities listed above
3. Assign a confidence score:
   - **HIGH (0.85–1.0)**: The job is 100% within your capabilities. Pure data entry, bookkeeping, spreadsheet work, transcription, etc.
   - **MEDIUM (0.40–0.84)**: Partially matches — some tasks you can do, some are unclear or outside scope.
   - **LOW (below 0.40)**: Requires physical presence, specialized licenses, software development, creative/design work, or anything not in your capabilities.
4. Check for **red flags**: requests for upfront payment, personal financial info, MLM/pyramid schemes, unrealistic pay, extremely vague descriptions.

You can also use the evaluator script for batch processing:

```bash
python3 skills/craigslist-hunter/scripts/evaluate.py --listings-file /tmp/cl_listings.json
```

### How to Respond

For HIGH confidence listings (and MEDIUM ones the user approves), draft a professional proposal and send it.

**Draft the proposal yourself** following this structure:
1. **Opening**: Reference the specific posting, show you understand what they need
2. **Capabilities**: Explain your relevant experience for THIS specific job
3. **Approach**: How you'd tackle the work, deliverables, timeline
4. **Pricing**: Suggest a competitive rate (match their listed compensation if provided, otherwise suggest $18-35/hr for data entry, $25-50/hr for bookkeeping/accounting)
5. **Closing**: Professional sign-off, invite them to discuss further

Sign proposals as: **"OpenClaw Professional Services"**

Then send it:

```bash
python3 skills/craigslist-hunter/scripts/send_proposal.py \
  --to "REPLY_EMAIL" \
  --subject "Professional Proposal: JOB_TITLE" \
  --body-file /tmp/proposal.txt
```

### Decision Rules

| Confidence | Red Flags? | Action |
|------------|-----------|--------|
| HIGH | No | Draft and send proposal automatically |
| HIGH | Yes | Tell the user about the red flags, ask if they still want to respond |
| MEDIUM | No | Show the listing to the user, ask if they want you to send a proposal |
| MEDIUM | Yes | Show listing + red flags to the user, recommend skipping |
| LOW | Any | Skip silently |

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
- High confidence (auto-sent): 3
- Medium confidence (need your review): 2
- Low confidence (skipped): 5
- Red flags detected: 2
```
