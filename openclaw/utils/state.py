"""Persistent state management for the agent.

Tracks seen listings, daily response counts, and action history
using a simple JSON file store.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import structlog

from openclaw.models import AgentAction

logger = structlog.get_logger()

_STATE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_STATE_FILE = _STATE_DIR / "agent_state.json"


class AgentState:
    """Manages persistent state across agent runs."""

    def __init__(self) -> None:
        self.seen_ids: set[str] = set()
        self.daily_response_count: int = 0
        self.last_response_date: str = ""
        self.action_history: list[dict] = []
        self._load()

    def _load(self) -> None:
        if _STATE_FILE.exists():
            try:
                data = json.loads(_STATE_FILE.read_text())
                self.seen_ids = set(data.get("seen_ids", []))
                self.daily_response_count = data.get("daily_response_count", 0)
                self.last_response_date = data.get("last_response_date", "")
                self.action_history = data.get("action_history", [])
                logger.info("state_loaded", seen=len(self.seen_ids))
            except Exception as e:
                logger.error("state_load_error", error=str(e))

    def save(self) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "seen_ids": list(self.seen_ids),
            "daily_response_count": self.daily_response_count,
            "last_response_date": self.last_response_date,
            "action_history": self.action_history[-500:],  # Keep last 500
        }
        _STATE_FILE.write_text(json.dumps(data, indent=2, default=str))

    def can_auto_respond(self, max_per_day: int) -> bool:
        today = date.today().isoformat()
        if self.last_response_date != today:
            self.daily_response_count = 0
            self.last_response_date = today
        return self.daily_response_count < max_per_day

    def record_response(self) -> None:
        today = date.today().isoformat()
        if self.last_response_date != today:
            self.daily_response_count = 0
            self.last_response_date = today
        self.daily_response_count += 1

    def record_action(self, action: AgentAction) -> None:
        self.action_history.append(
            {
                "listing_id": action.listing.id,
                "title": action.listing.title,
                "url": action.listing.url,
                "decision": action.decision.value,
                "confidence": action.evaluation.confidence,
                "sent": action.sent,
                "acted_at": action.acted_at.isoformat(),
            }
        )
