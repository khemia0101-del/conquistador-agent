"""Agent configuration loaded from environment and config files."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class NvidiaSettings(BaseSettings):
    api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    model: str = Field(default="meta/llama-3.1-70b-instruct", alias="NVIDIA_MODEL")
    base_url: str = "https://integrate.api.nvidia.com/v1"


class CraigslistSettings(BaseSettings):
    regions: list[str] = Field(default=["newyork", "sfbay", "losangeles", "chicago"])
    scan_interval_minutes: int = Field(default=30, alias="SCAN_INTERVAL_MINUTES")
    # cpg = computer gigs, acc = accounting+finance, ofc = admin/office
    categories: list[str] = ["cpg", "acc", "ofc"]

    model_config = {"env_prefix": "CRAIGSLIST_"}


class AgentSettings(BaseSettings):
    auto_respond_threshold: float = Field(default=0.85, alias="AUTO_RESPOND_THRESHOLD")
    ignore_threshold: float = 0.40
    max_auto_responses_per_day: int = Field(default=10, alias="MAX_AUTO_RESPONSES_PER_DAY")

    capabilities: list[str] = [
        "data entry",
        "spreadsheet management",
        "bookkeeping",
        "accounts payable / receivable",
        "invoice processing",
        "PDF and document conversion",
        "database entry and cleanup",
        "email management and organization",
        "CRM data entry",
        "transcription",
        "web research and data collection",
        "inventory tracking",
        "payroll data entry",
        "tax document preparation",
        "receipt and expense categorization",
    ]


class NotificationSettings(BaseSettings):
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    notify_email: str = Field(default="", alias="NOTIFY_EMAIL")

    @property
    def enabled(self) -> bool:
        return bool(self.smtp_host and self.notify_email)


class Settings(BaseSettings):
    nvidia: NvidiaSettings = Field(default_factory=NvidiaSettings)
    craigslist: CraigslistSettings = Field(default_factory=CraigslistSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


def load_settings() -> Settings:
    """Load settings from environment variables."""
    return Settings()
