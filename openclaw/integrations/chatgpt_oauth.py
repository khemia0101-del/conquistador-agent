"""ChatGPT / OpenAI OAuth integration.

Provides OAuth 2.0 authentication flow for connecting the agent to a ChatGPT
account, and an OpenAI-backed evaluator that can be used alongside or instead
of the NVIDIA NIM evaluator.

Setup:
1. Create an OAuth app at https://platform.openai.com
2. Set OPENAI_CLIENT_ID, OPENAI_CLIENT_SECRET, and OPENAI_REDIRECT_URI
3. Run the OAuth flow once to get tokens (stored locally)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import structlog
from pydantic import BaseModel
from pydantic_settings import BaseSettings

logger = structlog.get_logger()

_TOKEN_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "openai_tokens.json"

OPENAI_AUTH_URL = "https://auth.openai.com/authorize"
OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"


class OpenAIOAuthSettings(BaseSettings):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/callback"
    scopes: str = "openai.public"

    model_config = {"env_prefix": "OPENAI_"}


class OAuthTokens(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # 60s buffer


class ChatGPTOAuthClient:
    """Manages OAuth 2.0 flow and token lifecycle for OpenAI/ChatGPT."""

    def __init__(self, settings: OpenAIOAuthSettings | None = None) -> None:
        self._settings = settings or OpenAIOAuthSettings()
        self._tokens: OAuthTokens | None = None
        self._load_tokens()

    def _load_tokens(self) -> None:
        if _TOKEN_FILE.exists():
            try:
                data = json.loads(_TOKEN_FILE.read_text())
                self._tokens = OAuthTokens(**data)
                logger.info("openai_tokens_loaded")
            except Exception as e:
                logger.warning("openai_tokens_load_failed", error=str(e))

    def _save_tokens(self) -> None:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        if self._tokens:
            _TOKEN_FILE.write_text(self._tokens.model_dump_json(indent=2))

    @property
    def is_authenticated(self) -> bool:
        return self._tokens is not None

    def get_auth_url(self, state: str = "openclaw") -> str:
        """Generate the OAuth authorization URL for the user to visit."""
        params = {
            "client_id": self._settings.client_id,
            "redirect_uri": self._settings.redirect_uri,
            "response_type": "code",
            "scope": self._settings.scopes,
            "state": state,
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{OPENAI_AUTH_URL}?{qs}"

    async def exchange_code(self, code: str) -> bool:
        """Exchange an authorization code for access/refresh tokens."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    OPENAI_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": self._settings.client_id,
                        "client_secret": self._settings.client_secret,
                        "redirect_uri": self._settings.redirect_uri,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                self._tokens = OAuthTokens(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token", ""),
                    token_type=data.get("token_type", "Bearer"),
                    expires_at=time.time() + data.get("expires_in", 3600),
                )
                self._save_tokens()
                logger.info("openai_oauth_success")
                return True

            except Exception as e:
                logger.error("openai_oauth_exchange_failed", error=str(e))
                return False

    async def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self._tokens or not self._tokens.refresh_token:
            logger.error("no_refresh_token")
            return False

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    OPENAI_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._tokens.refresh_token,
                        "client_id": self._settings.client_id,
                        "client_secret": self._settings.client_secret,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                self._tokens = OAuthTokens(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token", self._tokens.refresh_token),
                    token_type=data.get("token_type", "Bearer"),
                    expires_at=time.time() + data.get("expires_in", 3600),
                )
                self._save_tokens()
                logger.info("openai_token_refreshed")
                return True

            except Exception as e:
                logger.error("openai_token_refresh_failed", error=str(e))
                return False

    async def get_access_token(self) -> str | None:
        """Get a valid access token, refreshing if needed."""
        if not self._tokens:
            return None
        if self._tokens.is_expired:
            success = await self.refresh_access_token()
            if not success:
                return None
        return self._tokens.access_token
