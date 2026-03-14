#!/usr/bin/env python3
"""Send a proposal email via Zoho Mail SMTP.

Usage:
    python3 send_proposal.py --to "reply@email.com" --subject "Proposal: Data Entry" --body-file /tmp/proposal.txt
    python3 send_proposal.py --to "reply@email.com" --subject "Proposal: Data Entry" --body "Hello, I am interested..."
"""

import argparse
import os
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ.get("ZOHO_SMTP_HOST", "smtp.zoho.com")
SMTP_PORT = int(os.environ.get("ZOHO_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("ZOHO_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("ZOHO_SMTP_PASSWORD", "")


def send_email(to: str, subject: str, body: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("ERROR: Set ZOHO_SMTP_USER and ZOHO_SMTP_PASSWORD environment variables", file=sys.stderr)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"OK: Sent to {to}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"ERROR: Failed to send: {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser(description="Send a proposal via Zoho Mail")
    ap.add_argument("--to", required=True, help="Recipient email address")
    ap.add_argument("--subject", required=True, help="Email subject line")
    ap.add_argument("--body", default="", help="Email body text")
    ap.add_argument("--body-file", default="", help="Read body from file instead")
    args = ap.parse_args()

    body = args.body
    if args.body_file:
        with open(args.body_file) as f:
            body = f.read()

    if not body.strip():
        print("ERROR: No body provided (use --body or --body-file)", file=sys.stderr)
        sys.exit(1)

    ok = send_email(args.to, args.subject, body)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
