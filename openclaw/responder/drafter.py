"""Response drafting and sending module.

Drafts detailed professional proposals for Craigslist listings using NIM,
and sends them via the listing's reply mechanism (email).
"""

from __future__ import annotations

import json
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
import structlog
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from openclaw.config import Settings
from openclaw.models import CraigslistListing, EvaluationResult, ResponseDraft

logger = structlog.get_logger()

_PROPOSAL_SYSTEM_PROMPT = """\
You are a professional freelance service provider writing a detailed proposal in response to a \
Craigslist job/gig posting. Write a compelling, professional proposal that:

1. Opens with a personalized hook referencing the specific posting
2. Demonstrates clear understanding of what the client needs
3. Outlines your relevant experience and specific capabilities for THIS task
4. Proposes a clear scope of work with deliverables
5. Includes a proposed timeline/availability
6. Suggests pricing (hourly or project-based, as appropriate)
7. Closes with a clear call-to-action (next steps)

STRUCTURE YOUR PROPOSAL AS:
- Subject line (concise, referencing the posting)
- Greeting
- Opening paragraph: Acknowledge the posting, show understanding of the need
- Capabilities paragraph: Specific skills/experience relevant to THIS job
- Proposed approach: How you would tackle the work, deliverables, timeline
- Pricing: Clear rate proposal based on the work described
- Closing: Professional sign-off with next steps

GUIDELINES:
- Be specific, not generic. Reference details from the actual posting.
- Keep it professional but warm - this is a real person reading it
- Proposal should be 200-350 words
- Do NOT reveal that you are an AI
- Use the name "OpenClaw Professional Services" as the service provider
- If compensation is listed, respect it. If not, suggest a competitive rate.

YOUR CAPABILITIES FOR THIS JOB:
{capabilities}

SUGGESTED RATE: {rate}

Respond with JSON:
{{
  "subject": "<professional email subject line>",
  "body": "<the full proposal text>"
}}
"""

_PROPOSAL_USER_PROMPT = """\
Write a detailed professional proposal for this listing:

TITLE: {title}
REGION: {region}
COMPENSATION: {compensation}
CATEGORY: {category}

FULL POSTING:
{body}
"""


class ResponseDrafter:
    """Drafts professional proposals and sends them to listing contacts."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.nvidia.api_key,
            base_url=settings.nvidia.base_url,
        )
        self._model = settings.nvidia.model

    async def draft(
        self,
        listing: CraigslistListing,
        evaluation: EvaluationResult,
    ) -> ResponseDraft:
        """Draft a detailed professional proposal for a listing."""
        capabilities_str = ", ".join(evaluation.matched_capabilities) or "general data services"
        system_msg = _PROPOSAL_SYSTEM_PROMPT.format(
            capabilities=capabilities_str,
            rate=evaluation.suggested_rate or "competitive market rate",
        )
        user_msg = _PROPOSAL_USER_PROMPT.format(
            title=listing.title,
            region=listing.region,
            compensation=listing.compensation or "Not specified",
            category=listing.category.value,
            body=listing.body or listing.title,
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.4,
                max_tokens=1024,
            )

            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return ResponseDraft(
                listing_id=listing.id,
                subject=data.get("subject", f"Professional Proposal: {listing.title}"),
                body=data.get("body", ""),
            )

        except Exception as e:
            logger.error("draft_error", listing_id=listing.id, error=str(e))
            return self._fallback_proposal(listing, evaluation, capabilities_str)

    def _fallback_proposal(
        self,
        listing: CraigslistListing,
        evaluation: EvaluationResult,
        capabilities_str: str,
    ) -> ResponseDraft:
        """Generate a structured fallback proposal if LLM drafting fails."""
        return ResponseDraft(
            listing_id=listing.id,
            subject=f"Professional Proposal: {listing.title}",
            body=(
                f"Hello,\n\n"
                f'I came across your posting for "{listing.title}" and would like to '
                f"submit my proposal for your consideration.\n\n"
                f"I specialize in {capabilities_str} and have extensive experience "
                f"delivering high-quality results for similar projects. I'm confident "
                f"I can meet your requirements efficiently and accurately.\n\n"
                f"Proposed approach:\n"
                f"- Initial review of your requirements and any sample materials\n"
                f"- Clear timeline and milestone agreement\n"
                f"- Regular progress updates throughout the project\n"
                f"- Final delivery with quality assurance review\n\n"
                f"I'm available to start immediately and would be happy to discuss "
                f"the scope, timeline, and pricing in more detail.\n\n"
                f"Looking forward to hearing from you.\n\n"
                f"Best regards,\n"
                f"OpenClaw Professional Services"
            ),
        )

    async def _extract_reply_email(self, listing_url: str) -> str | None:
        """Attempt to extract the anonymized reply-to email from a Craigslist listing."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    listing_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                    follow_redirects=True,
                )
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for the reply button/link with mailto
            reply_link = soup.select_one("a.reply-button, a[href^='mailto:']")
            if reply_link:
                href = reply_link.get("href", "")
                if href.startswith("mailto:"):
                    return href.replace("mailto:", "").split("?")[0]

            # Look for anonymized email pattern in page text
            text = soup.get_text()
            email_match = re.search(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text
            )
            if email_match:
                return email_match.group(0)

        except Exception as e:
            logger.warning("reply_email_extraction_failed", url=listing_url, error=str(e))

        return None

    async def send_proposal(
        self,
        listing: CraigslistListing,
        draft: ResponseDraft,
    ) -> bool:
        """Send a professional proposal to the listing's reply address via email."""
        notifications = self._settings.notifications
        if not notifications.enabled:
            logger.warning(
                "smtp_not_configured",
                msg="Cannot send proposal - SMTP not configured. Proposal logged instead.",
            )
            logger.info(
                "proposal_drafted",
                listing_id=listing.id,
                listing_url=listing.url,
                subject=draft.subject,
                body=draft.body,
            )
            return False

        # Extract the reply-to email from the listing page
        reply_email = await self._extract_reply_email(listing.url)
        if not reply_email:
            logger.warning(
                "no_reply_email",
                listing_id=listing.id,
                msg="Could not extract reply email from listing. Proposal logged.",
            )
            logger.info("proposal_body", subject=draft.subject, body=draft.body)
            return False

        # Build and send the email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = draft.subject
        msg["From"] = notifications.smtp_user
        msg["To"] = reply_email
        msg.attach(MIMEText(draft.body, "plain"))

        try:
            with smtplib.SMTP(notifications.smtp_host, notifications.smtp_port) as server:
                server.starttls()
                server.login(notifications.smtp_user, notifications.smtp_password)
                server.send_message(msg)

            logger.info(
                "proposal_sent",
                listing_id=listing.id,
                to=reply_email,
                subject=draft.subject,
            )
            return True

        except Exception as e:
            logger.error(
                "proposal_send_failed",
                listing_id=listing.id,
                error=str(e),
            )
            return False
