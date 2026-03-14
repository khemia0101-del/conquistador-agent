"""Job listing evaluator powered by NVIDIA NIM API.

Uses the OpenAI-compatible endpoint on NIM to evaluate whether a listing
matches our capabilities, returning a confidence score and reasoning.
"""

from __future__ import annotations

import json

import structlog
from openai import AsyncOpenAI

from openclaw.config import Settings
from openclaw.models import CraigslistListing, EvaluationResult

logger = structlog.get_logger()

_SYSTEM_PROMPT = """\
You are a job-matching evaluator for an AI-powered service provider. Your job is to analyze \
Craigslist listings and determine whether the following service capabilities can fulfill the \
listing with 100% competence.

CAPABILITIES:
{capabilities}

EVALUATION RULES:
1. Score 0.0-1.0 confidence that the listed capabilities can FULLY deliver what the posting asks.
2. Only score >= 0.85 if the task is ENTIRELY within the listed capabilities (e.g., pure data \
entry, bookkeeping, spreadsheet work).
3. Score 0.40-0.84 for partial matches or tasks where some but not all requirements are met.
4. Score < 0.40 for tasks that require physical presence, specialized licenses, creative work, \
software development, or anything outside the capabilities list.
5. Flag red flags: requests for personal info, upfront payments, MLM/scam indicators, \
unrealistic pay, vague descriptions.

Respond ONLY with valid JSON matching this schema:
{{
  "confidence": <float 0.0-1.0>,
  "matched_capabilities": [<list of matching capability strings>],
  "reasoning": "<brief explanation>",
  "suggested_rate": "<suggested hourly/project rate if determinable, else empty string>",
  "red_flags": [<list of concern strings, empty if none>]
}}
"""

_USER_PROMPT = """\
Evaluate this Craigslist listing:

TITLE: {title}
REGION: {region}
COMPENSATION: {compensation}
CATEGORY: {category}

FULL POSTING:
{body}
"""


class NimEvaluator:
    """Evaluates listings using NVIDIA NIM inference."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.nvidia.api_key,
            base_url=settings.nvidia.base_url,
        )
        self._model = settings.nvidia.model
        self._capabilities = settings.agent.capabilities

    async def evaluate(self, listing: CraigslistListing) -> EvaluationResult:
        """Evaluate a single listing and return structured result."""
        capabilities_str = "\n".join(f"- {c}" for c in self._capabilities)
        system_msg = _SYSTEM_PROMPT.format(capabilities=capabilities_str)
        user_msg = _USER_PROMPT.format(
            title=listing.title,
            region=listing.region,
            compensation=listing.compensation or "Not specified",
            category=listing.category.value,
            body=listing.body or "(No description available)",
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=1024,
            )

            content = response.choices[0].message.content or ""
            # Strip markdown fences if present
            content = content.strip()
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

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error("evaluation_parse_error", listing_id=listing.id, error=str(e))
            return EvaluationResult(
                listing_id=listing.id,
                confidence=0.0,
                reasoning=f"Failed to parse LLM response: {e}",
            )
        except Exception as e:
            logger.error("evaluation_error", listing_id=listing.id, error=str(e))
            return EvaluationResult(
                listing_id=listing.id,
                confidence=0.0,
                reasoning=f"Evaluation failed: {e}",
            )

    async def evaluate_batch(
        self, listings: list[CraigslistListing]
    ) -> list[EvaluationResult]:
        """Evaluate multiple listings sequentially (respects rate limits)."""
        results = []
        for listing in listings:
            result = await self.evaluate(listing)
            results.append(result)
            logger.info(
                "evaluated",
                listing_id=listing.id,
                title=listing.title[:60],
                confidence=result.confidence,
            )
        return results
