#!/usr/bin/env python3
"""Evaluate Craigslist listings using NVIDIA NIM API.

Reads listings JSON (from scrape.py) and scores each one for fit.

Usage:
    python3 evaluate.py --listings-file /tmp/cl_listings.json
    python3 evaluate.py --listings-file /tmp/cl_listings.json --output /tmp/cl_evaluated.json
"""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

DELIVERABLE_CAPABILITIES = [
    "typing data from scans / PDFs / images into spreadsheets",
    "creating, formatting, and cleaning spreadsheets (CSV, Excel)",
    "web research compiled into reports or spreadsheets",
    "transcription of audio/video files to text",
    "document format conversion (PDF, Word, CSV, text)",
    "categorizing and organizing data (receipts, expenses, inventory)",
    "drafting text (emails, letters, form responses, templates)",
    "proofreading and copyediting documents",
    "compiling data from multiple sources into a single report",
    "bookkeeping if client provides books as files (not locked in SaaS)",
    "invoice processing if invoices are provided as PDFs/images",
]

AUTO_REJECT = [
    "requires login to client's proprietary software (QuickBooks Online, Salesforce, HubSpot, etc.)",
    "requires phone calls, video meetings, or real-time screen sharing",
    "requires physical presence or handling physical materials",
    "requires professional licenses (CPA, legal, notary)",
    "requires ongoing real-time availability (be online 9-5, respond within minutes)",
    "vague 'virtual assistant' role with no defined deliverable",
    "requires identity verification, background check, or W-2 employment",
    "software development, graphic design, or website building",
]

SYSTEM_PROMPT = """You are a job fulfillment evaluator. Your job is NOT to assess skill match — it is to determine whether an AI agent can ACTUALLY DELIVER the finished work product for this listing with zero or minimal human intervention.

The agent works by: receiving input files via email, processing them, and returning finished output files via email. It has no access to proprietary SaaS platforms, cannot attend meetings or calls, and cannot be "online" in real time.

WHAT THE AGENT CAN DELIVER:
{caps}

AUTO-REJECT (if listing requires ANY of these, score below 0.50):
{rejects}

EVALUATION RULES:
1. Identify the CONCRETE DELIVERABLE. What does the client get back? A spreadsheet? A report? Organized files? If you cannot name a specific deliverable, score low.
2. Check the WORKFLOW. Can inputs be sent as files and outputs returned as files via email? Or does it require live system access, meetings, or real-time availability?
3. Check the SCOPE. Is the job well-defined enough to execute without extensive back-and-forth? Short, bounded tasks are ideal.
4. Score 0.0-1.0 for AUTONOMOUS DELIVERABILITY (not just skill match):
   - >= 0.85 (FULFILL): Clear deliverable, file-based workflow, well-defined scope, no proprietary access needed. Can start immediately upon receiving inputs.
   - 0.50-0.84 (MAYBE): Probably doable but something is unclear — scope is vague, might need system access, or implies real-time availability without confirming.
   - < 0.50 (SKIP): Cannot deliver — requires meetings, proprietary access, physical presence, ongoing availability, licenses, or deliverable is unclear/unbounded.
5. Flag red flags: upfront payments, personal financial info, MLM, unrealistic pay, extremely vague with no concrete tasks.
6. Estimate effort: small (1-4 hours), medium (4-16 hours), large (16+ hours). Prefer small/medium.

Respond ONLY with valid JSON:
{{"confidence": <float>, "deliverable": "<what the client gets back>", "workflow_feasible": <true/false>, "blockers": [<strings: things that prevent autonomous delivery>], "matched_capabilities": [<strings>], "reasoning": "<brief>", "suggested_rate": "<rate or empty>", "red_flags": [<strings or empty>], "effort_estimate": "<small|medium|large>"}}"""


def call_nim(listing: dict) -> dict:
    caps_str = "\n".join(f"- {c}" for c in DELIVERABLE_CAPABILITIES)
    rejects_str = "\n".join(f"- {r}" for r in AUTO_REJECT)
    system_msg = SYSTEM_PROMPT.format(caps=caps_str, rejects=rejects_str)

    user_msg = (
        f"TITLE: {listing['title']}\n"
        f"REGION: {listing.get('region', 'unknown')}\n"
        f"COMPENSATION: {listing.get('compensation', 'Not specified')}\n\n"
        f"POSTING:\n{listing.get('body', '(No description)')}"
    )

    payload = json.dumps({
        "model": NVIDIA_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
    }).encode()

    req = Request(
        f"{NVIDIA_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        # Strip markdown fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip())
    except Exception as e:
        print(f"WARN: Evaluation failed for '{listing['title']}': {e}", file=sys.stderr)
        return {"confidence": 0.0, "deliverable": "unknown", "workflow_feasible": False, "blockers": [f"Evaluation error: {e}"], "reasoning": f"Error: {e}", "red_flags": [], "matched_capabilities": [], "effort_estimate": "unknown"}


def main():
    if not NVIDIA_API_KEY:
        print("ERROR: Set NVIDIA_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    ap = argparse.ArgumentParser(description="Evaluate listings with NVIDIA NIM")
    ap.add_argument("--listings-file", required=True, help="Path to JSON listings from scrape.py")
    ap.add_argument("--output", default="", help="Output file (default: stdout)")
    args = ap.parse_args()

    with open(args.listings_file) as f:
        listings = json.load(f)

    results = []
    for listing in listings:
        print(f"Evaluating: {listing['title'][:60]} ...", file=sys.stderr)
        evaluation = call_nim(listing)
        evaluation["listing_id"] = listing["id"]
        evaluation["title"] = listing["title"]
        evaluation["url"] = listing["url"]

        conf = evaluation.get("confidence", 0)
        label = "FULFILL" if conf >= 0.85 else "MAYBE" if conf >= 0.50 else "SKIP"
        evaluation["label"] = label
        deliverable = evaluation.get("deliverable", "unknown")
        blockers = evaluation.get("blockers", [])
        print(f"  -> {label} ({conf:.2f}) deliverable={deliverable}", file=sys.stderr)
        if blockers:
            print(f"     blockers: {', '.join(blockers)}", file=sys.stderr)

        results.append(evaluation)

    output = json.dumps(results, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
