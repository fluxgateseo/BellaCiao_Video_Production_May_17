"""
publishers/youtube_auth.py — mint a YouTube refresh token (one-time, local).

Uploads need OAuth2. Run this ONCE on a machine with a browser to authorise the
Bella YouTube channel and print a long-lived refresh token. Put that token (and
the client id/secret) into the environment as:

    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN

Prereq: a Google Cloud OAuth client of type "Desktop app" with the YouTube
Data API v3 enabled. Provide its credentials one of two ways:
  1. env: YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET, or
  2. file: a client_secret.json downloaded from Google Cloud (pass --client-secret).

Usage:
    python -m publishers.youtube_auth
    python -m publishers.youtube_auth --client-secret client_secret.json
"""
from __future__ import annotations

import argparse
import os
from typing import Optional, Sequence

from publishers.youtube_publisher import YOUTUBE_SCOPES


def mint_refresh_token(client_secret_file: Optional[str] = None) -> str:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise SystemExit(
            "google-auth-oauthlib not installed. Run: pip install "
            "google-auth-oauthlib google-api-python-client google-auth"
        ) from e

    if client_secret_file:
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, YOUTUBE_SCOPES)
    else:
        client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        if not (client_id and client_secret):
            raise SystemExit(
                "Provide --client-secret client_secret.json, or set "
                "YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in the environment."
            )
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            },
            YOUTUBE_SCOPES,
        )

    # Opens a browser / prints a URL; sign in as the Bella channel owner.
    creds = flow.run_local_server(port=0, prompt="consent")
    if not creds.refresh_token:
        raise SystemExit(
            "No refresh token returned. Revoke prior access and retry with "
            "prompt=consent (already set) — Google only returns it on first consent."
        )
    return creds.refresh_token


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mint a YouTube refresh token.")
    parser.add_argument("--client-secret", help="path to client_secret.json")
    args = parser.parse_args(argv)

    token = mint_refresh_token(args.client_secret)
    print("\n=== YOUTUBE_REFRESH_TOKEN ===")
    print(token)
    print("\nSet this as the YOUTUBE_REFRESH_TOKEN env var (do not commit it).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
