"""OpenAI/ChatGPT-backed evaluator using OAuth tokens.

Alternative evaluator that uses OpenAI's API (authenticated via OAuth)
instead of or alongside the NVIDIA NIM evaluator.
"""

from __future__ import annotations

import json

import structlog
from openai import AsyncOpenAI

from openclaw.integrations.chatgpt_oauth import ChatGPTOAuthClient
from openclaw.models import CraigslistListing, EvaluationResult

logger = structlog.get_logger()

# Reuse the same prompt structure as the NIM evaluator
_SYSTEM_PROMPT = """\
You are a job-matching evaluator for an AI-powered service provider. Analyze \
Craigslist listings and determine whether the following capabilities can fulfill \
the listing with 100% competence.

CAPABILITIES:
{capabilities}

EVALUATION RULES:
1. Score 0.0-1.0 confidence that the listed capabilities can FULLY deliver what the posting asks.
2. Only score >= 0.85 if the task is ENTIRELY within the listed capabilities.
3. Score 0.40-0.84 for partial matches.
4. Score < 0.40 for tasks requiring physical presence, specialized licenses, creative work, \
software development, or anything outside the capabilities.
5. Flag red flags: requests for personal info, upfront payments, MLM/scam indicators.

Respond ONLY with valid JSON:
{{
  "confidence": <float 0.0-1.0>,
  "matched_capabilities": [<matching capabilities>],
  "reasoning": "<brief explanation>",
  "suggested_rate": "<rate or empty string>",
  "red_flags": [<concerns or empty>]
}}
"""


class OpenAIEvaluator:
    """Evaluates listings using OpenAI API with OAuth authentication."""

    def __init__(
        self,
        oauth_client: ChatGPTOAuthClient,
        capabilities: list[str],
        model: str = "gpt-4o",
    ) -> None:
        self._oauth = oauth_client
        self._capabilities = capabilities
        self._model = model
        self._client: AsyncOpenAI | None = None

    async def _get_client(self) -> AsyncOpenAI | None:
        """Get an authenticated OpenAI client."""
        token = await self._oauth.get_access_token()
        if not token:
            logger.error("openai_not_authenticated")
            return None
        # Create/update client with current token
        self._client = AsyncOpenAI(api_key=token)
        return self._client

    async def evaluate(self, listing: CraigslistListing) -> EvaluationResult | None:
        """Evaluate a listing using OpenAI's API."""
        client = await self._get_client()
        if not client:
            return None

        capabilities_str = "\n".join(f"- {c}" for c in self._capabilities)
        system_msg = _SYSTEM_PROMPT.format(capabilities=capabilities_str)
        user_msg = (
            f"Evaluate this listing:\n\n"
            f"TITLE: {listing.title}\n"
            f"REGION: {listing.region}\n"
            f"COMPENSATION: {listing.compensation or 'Not specified'}\n\n"
            f"POSTING:\n{listing.body or '(No description)'}"
        )

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=1024,
            )

            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return EvaluationResult(
                listing_id=listing.id,
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
                matched_capabilities=data.get("matched_capabilities", []),
                reasoning=data.get("reasoning", ""),
                suggested_rate=data.get("suggested_rate", ""),
                red_flags=data.get("red_flags", []),
            )

        except Exception as e:
            logger.error("openai_evaluation_error", listing_id=listing.id, error=str(e))
            return None
