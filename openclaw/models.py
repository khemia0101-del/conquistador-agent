"""Data models shared across modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ListingCategory(str, Enum):
    COMPUTER_GIGS = "cpg"
    ACCOUNTING = "acc"
    OFFICE_ADMIN = "ofc"


class CraigslistListing(BaseModel):
    """A single Craigslist posting."""

    id: str
    title: str
    url: str
    body: str = ""
    region: str
    category: ListingCategory
    compensation: str = ""
    posted_at: datetime | None = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class EvaluationResult(BaseModel):
    """LLM evaluation of whether we can fulfill a listing."""

    listing_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    matched_capabilities: list[str] = []
    reasoning: str = ""
    suggested_rate: str = ""
    red_flags: list[str] = []


class ActionDecision(str, Enum):
    AUTO_RESPOND = "auto_respond"
    NOTIFY = "notify"
    IGNORE = "ignore"


class ResponseDraft(BaseModel):
    """A drafted response to a listing."""

    listing_id: str
    subject: str
    body: str
    tone: str = "professional"


class AgentAction(BaseModel):
    """Record of an action taken by the agent."""

    listing: CraigslistListing
    evaluation: EvaluationResult
    decision: ActionDecision
    response: ResponseDraft | None = None
    sent: bool = False
    acted_at: datetime = Field(default_factory=datetime.utcnow)
