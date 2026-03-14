"""Main agent orchestrator.

Coordinates the scraping, evaluation, response, and notification pipeline
on a scheduled interval. Supports dual-evaluator mode (NVIDIA NIM + OpenAI).
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from openclaw.config import load_settings
from openclaw.evaluator.nim_evaluator import NimEvaluator
from openclaw.models import ActionDecision, AgentAction, CraigslistListing, EvaluationResult
from openclaw.notifier.email_notifier import EmailNotifier
from openclaw.responder.drafter import ResponseDrafter
from openclaw.scrapers.craigslist import scrape_all
from openclaw.utils.state import AgentState

logger = structlog.get_logger()


async def _evaluate_with_fallback(
    listing: CraigslistListing,
    nim_evaluator: NimEvaluator,
    openai_evaluator=None,
) -> EvaluationResult:
    """Evaluate using NIM primary, OpenAI fallback. Average if both available."""
    nim_result = await nim_evaluator.evaluate(listing)

    if openai_evaluator is None:
        return nim_result

    openai_result = await openai_evaluator.evaluate(listing)
    if openai_result is None:
        return nim_result

    # Average the confidence scores from both evaluators for robustness
    avg_confidence = (nim_result.confidence + openai_result.confidence) / 2.0
    combined_flags = list(set(nim_result.red_flags + openai_result.red_flags))
    combined_caps = list(set(nim_result.matched_capabilities + openai_result.matched_capabilities))

    return EvaluationResult(
        listing_id=listing.id,
        confidence=avg_confidence,
        matched_capabilities=combined_caps,
        reasoning=f"NIM ({nim_result.confidence:.2f}): {nim_result.reasoning} | "
        f"OpenAI ({openai_result.confidence:.2f}): {openai_result.reasoning}",
        suggested_rate=nim_result.suggested_rate or openai_result.suggested_rate,
        red_flags=combined_flags,
    )


async def run_pipeline() -> None:
    """Execute one full scrape -> evaluate -> act pipeline cycle."""
    settings = load_settings()
    state = AgentState()
    nim_evaluator = NimEvaluator(settings)
    drafter = ResponseDrafter(settings)
    notifier = EmailNotifier(settings)

    # Optional: set up OpenAI evaluator if OAuth tokens exist
    openai_evaluator = None
    if os.getenv("OPENAI_CLIENT_ID"):
        try:
            from openclaw.integrations.chatgpt_oauth import ChatGPTOAuthClient
            from openclaw.integrations.openai_evaluator import OpenAIEvaluator

            oauth = ChatGPTOAuthClient()
            if oauth.is_authenticated:
                openai_evaluator = OpenAIEvaluator(
                    oauth_client=oauth,
                    capabilities=settings.agent.capabilities,
                    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                )
                logger.info("dual_evaluator_enabled", msg="Using NIM + OpenAI")
        except Exception as e:
            logger.warning("openai_evaluator_init_failed", error=str(e))

    # 1. Scrape
    logger.info("pipeline_start", phase="scrape")
    listings = await scrape_all(
        regions=settings.craigslist.regions,
        categories=settings.craigslist.categories,
        seen_ids=state.seen_ids,
    )

    if not listings:
        logger.info("no_new_listings")
        state.save()
        return

    # 2. Evaluate
    logger.info("pipeline_evaluate", count=len(listings))
    evaluations = []
    for listing in listings:
        result = await _evaluate_with_fallback(listing, nim_evaluator, openai_evaluator)
        evaluations.append(result)
        logger.info(
            "evaluated",
            listing_id=listing.id,
            title=listing.title[:60],
            confidence=result.confidence,
        )

    # 3. Decide and act
    notify_queue: list[AgentAction] = []

    for listing, evaluation in zip(listings, evaluations):
        if evaluation.red_flags:
            logger.warning(
                "red_flags_detected",
                listing_id=listing.id,
                title=listing.title,
                flags=evaluation.red_flags,
            )

        if evaluation.confidence >= settings.agent.auto_respond_threshold:
            decision = ActionDecision.AUTO_RESPOND
        elif evaluation.confidence >= settings.agent.ignore_threshold:
            decision = ActionDecision.NOTIFY
        else:
            decision = ActionDecision.IGNORE

        if decision == ActionDecision.IGNORE:
            logger.info(
                "listing_ignored",
                listing_id=listing.id,
                title=listing.title[:60],
                confidence=evaluation.confidence,
            )
            state.record_action(
                AgentAction(listing=listing, evaluation=evaluation, decision=decision)
            )
            continue

        # Draft a professional proposal
        draft = await drafter.draft(listing, evaluation)

        if decision == ActionDecision.AUTO_RESPOND:
            if state.can_auto_respond(settings.agent.max_auto_responses_per_day):
                sent = await drafter.send_proposal(listing, draft)
                if sent:
                    state.record_response()
                action = AgentAction(
                    listing=listing,
                    evaluation=evaluation,
                    decision=decision,
                    response=draft,
                    sent=sent,
                )
                state.record_action(action)
                logger.info(
                    "auto_responded",
                    listing_id=listing.id,
                    title=listing.title[:60],
                    confidence=evaluation.confidence,
                    sent=sent,
                )
            else:
                logger.warning("daily_limit_reached", msg="Downgrading to notify")
                decision = ActionDecision.NOTIFY
                action = AgentAction(
                    listing=listing,
                    evaluation=evaluation,
                    decision=decision,
                    response=draft,
                )
                notify_queue.append(action)
                state.record_action(action)

        if decision == ActionDecision.NOTIFY:
            action = AgentAction(
                listing=listing,
                evaluation=evaluation,
                decision=decision,
                response=draft,
            )
            notify_queue.append(action)
            state.record_action(action)
            logger.info(
                "queued_for_review",
                listing_id=listing.id,
                title=listing.title[:60],
                confidence=evaluation.confidence,
            )

    # 4. Send notifications for borderline matches
    if notify_queue:
        await notifier.notify(notify_queue)

    state.save()
    logger.info(
        "pipeline_complete",
        total_scraped=len(listings),
        auto_responded=sum(
            1
            for e in evaluations
            if e.confidence >= settings.agent.auto_respond_threshold
        ),
        notified=len(notify_queue),
    )


def main() -> None:
    """Entry point: run the pipeline on a schedule."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    settings = load_settings()

    if not settings.nvidia.api_key:
        logger.error("missing_nvidia_api_key", msg="Set NVIDIA_API_KEY in .env or environment")
        sys.exit(1)

    logger.info(
        "agent_starting",
        regions=settings.craigslist.regions,
        categories=settings.craigslist.categories,
        interval_min=settings.craigslist.scan_interval_minutes,
        auto_threshold=settings.agent.auto_respond_threshold,
    )

    loop = asyncio.new_event_loop()

    scheduler = AsyncIOScheduler(event_loop=loop)
    scheduler.add_job(
        run_pipeline,
        "interval",
        minutes=settings.craigslist.scan_interval_minutes,
        id="scrape_pipeline",
    )

    def shutdown(sig, frame):
        logger.info("shutting_down")
        scheduler.shutdown(wait=False)
        loop.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    async def start():
        scheduler.start()
        await run_pipeline()
        while True:
            await asyncio.sleep(1)

    try:
        loop.run_until_complete(start())
    except (KeyboardInterrupt, SystemExit):
        logger.info("agent_stopped")


if __name__ == "__main__":
    main()
