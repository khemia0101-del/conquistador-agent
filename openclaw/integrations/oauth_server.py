"""Lightweight OAuth callback server for the initial authentication flow.

Run this once to complete the OAuth handshake with OpenAI, then the agent
uses stored tokens with automatic refresh.
"""

from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import structlog

from openclaw.integrations.chatgpt_oauth import ChatGPTOAuthClient, OpenAIOAuthSettings

logger = structlog.get_logger()


def run_oauth_flow() -> None:
    """Run the interactive OAuth flow to authenticate with OpenAI."""
    settings = OpenAIOAuthSettings()

    if not settings.client_id or not settings.client_secret:
        print("ERROR: Set OPENAI_CLIENT_ID and OPENAI_CLIENT_SECRET environment variables.")
        print("Create an OAuth app at https://platform.openai.com")
        return

    oauth = ChatGPTOAuthClient(settings)

    if oauth.is_authenticated:
        print("Already authenticated with OpenAI. Tokens found.")
        print("Delete data/openai_tokens.json to re-authenticate.")
        return

    auth_url = oauth.get_auth_url()
    print(f"\nOpen this URL in your browser to authenticate:\n\n{auth_url}\n")

    received_code: list[str] = []

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]

            if code:
                received_code.append(code)
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authentication successful!</h1>"
                    b"<p>You can close this window and return to the terminal.</p>"
                )
            else:
                error = params.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {error}</h1>".encode())

        def log_message(self, format, *args):
            pass  # Suppress default logging

    # Parse port from redirect URI
    parsed = urlparse(settings.redirect_uri)
    port = parsed.port or 8080

    server = HTTPServer(("localhost", port), CallbackHandler)
    print(f"Waiting for OAuth callback on localhost:{port}...")

    # Wait for the callback
    while not received_code:
        server.handle_request()

    server.server_close()

    # Exchange code for tokens
    code = received_code[0]
    print("Exchanging authorization code for tokens...")
    success = asyncio.get_event_loop().run_until_complete(oauth.exchange_code(code))

    if success:
        print("Successfully authenticated with OpenAI!")
        print("Tokens saved to data/openai_tokens.json")
    else:
        print("Failed to exchange authorization code. Check your credentials.")


if __name__ == "__main__":
    run_oauth_flow()
