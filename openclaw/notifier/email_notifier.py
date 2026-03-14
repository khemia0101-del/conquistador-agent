"""Email notification for borderline matches that need human review."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog
from jinja2 import Template

from openclaw.config import Settings
from openclaw.models import AgentAction

logger = structlog.get_logger()

_EMAIL_TEMPLATE = Template(
    """\
<html>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
<h2>OpenClaw: {{ actions|length }} Listing(s) Need Your Review</h2>

{% for action in actions %}
<div style="border: 1px solid #ddd; padding: 16px; margin-bottom: 16px; border-radius: 8px;">
  <h3><a href="{{ action.listing.url }}">{{ action.listing.title }}</a></h3>
  <p><strong>Region:</strong> {{ action.listing.region }}
     | <strong>Confidence:</strong> {{ "%.0f"|format(action.evaluation.confidence * 100) }}%
     {% if action.listing.compensation %}
     | <strong>Compensation:</strong> {{ action.listing.compensation }}
     {% endif %}
  </p>
  <p><strong>Reasoning:</strong> {{ action.evaluation.reasoning }}</p>
  {% if action.evaluation.matched_capabilities %}
  <p><strong>Matched:</strong> {{ action.evaluation.matched_capabilities|join(', ') }}</p>
  {% endif %}
  {% if action.evaluation.red_flags %}
  <p style="color: red;"><strong>Red Flags:</strong> {{ action.evaluation.red_flags|join(', ') }}</p>
  {% endif %}
  {% if action.response %}
  <details>
    <summary>Suggested Response</summary>
    <p><strong>Subject:</strong> {{ action.response.subject }}</p>
    <pre style="white-space: pre-wrap;">{{ action.response.body }}</pre>
  </details>
  {% endif %}
</div>
{% endfor %}

<p style="color: #888; font-size: 12px;">Sent by OpenClaw Agent</p>
</body>
</html>
"""
)


class EmailNotifier:
    """Sends email digests for listings that need human review."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings.notifications

    async def notify(self, actions: list[AgentAction]) -> bool:
        """Send a notification email with listings needing review."""
        if not self._settings.enabled:
            logger.warning("notifications_disabled", msg="SMTP not configured, skipping email")
            for action in actions:
                logger.info(
                    "needs_review",
                    title=action.listing.title,
                    url=action.listing.url,
                    confidence=action.evaluation.confidence,
                    reasoning=action.evaluation.reasoning,
                )
            return False

        html = _EMAIL_TEMPLATE.render(actions=actions)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"OpenClaw: {len(actions)} listing(s) need your review"
        msg["From"] = self._settings.smtp_user
        msg["To"] = self._settings.notify_email
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                server.starttls()
                server.login(self._settings.smtp_user, self._settings.smtp_password)
                server.send_message(msg)
            logger.info("notification_sent", recipients=self._settings.notify_email)
            return True
        except Exception as e:
            logger.error("notification_failed", error=str(e))
            return False
