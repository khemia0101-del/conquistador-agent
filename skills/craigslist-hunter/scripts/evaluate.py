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

CAPABILITIES = [
    "data entry", "spreadsheet management", "bookkeeping",
    "accounts payable / receivable", "invoice processing",
    "PDF and document conversion", "database entry and cleanup",
    "email management and organization", "CRM data entry",
    "transcription", "web research and data collection",
    "inventory tracking", "payroll data entry",
    "tax document preparation", "receipt and expense categorization",
]

SYSTEM_PROMPT = """You are a job-matching evaluator. Analyze this Craigslist listing and determine
whether these capabilities can fulfill it with 100% competence:

CAPABILITIES:
{caps}

RULES:
1. Score 0.0-1.0 confidence the capabilities can FULLY deliver.
2. >= 0.85 only if the task is ENTIRELY within capabilities (pure data entry, bookkeeping, etc).
3. 0.40-0.84 for partial matches.
4. < 0.40 for physical presence, licenses, creative work, software dev, etc.
5. Flag red flags: upfront payments, personal financial info, MLM, unrealistic pay, vague descriptions.

Respond ONLY with valid JSON:
{{"confidence": <float>, "matched_capabilities": [<strings>], "reasoning": "<brief>", "suggested_rate": "<rate or empty>", "red_flags": [<strings or empty>]}}"""


def call_nim(listing: dict) -> dict:
    caps_str = "\n".join(f"- {c}" for c in CAPABILITIES)
    system_msg = SYSTEM_PROMPT.format(caps=caps_str)

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
        return {"confidence": 0.0, "reasoning": f"Error: {e}", "red_flags": [], "matched_capabilities": []}


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
        label = "HIGH" if conf >= 0.85 else "MEDIUM" if conf >= 0.40 else "LOW"
        print(f"  -> {label} ({conf:.2f})", file=sys.stderr)

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
