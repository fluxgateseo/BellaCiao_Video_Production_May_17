"""
publishers/youtube_publisher.py — direct YouTube (Shorts) publishing for Bella.

Uploads a finished vertical video to the channel and schedules its PUBLIC
release natively via the YouTube Data API (`status.publishAt`). One call =
one scheduled Short: the video is uploaded as `private` with a future
`publishAt`, and YouTube flips it public itself at that moment — so this
routine does NOT need to be running at post time.

Auth: uploads require OAuth2 (an API key is not enough). Supply a refresh
token + client credentials via the environment (never commit them):

    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN

Mint the refresh token once with `python -m publishers.youtube_auth`.

CLI:
    python -m publishers.youtube_publisher upload \
        --video renders/day10_jake.mp4 \
        --title "Nine calls. Zero tables. #Shorts" \
        --description-file creatives/daily_scripts/day10_caption.txt \
        --tags bella,bellaciao,fitzroy \
        --publish-at 2026-06-15T09:00:00+10:00

Omit --publish-at to publish immediately (privacy defaults to `public`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import time
from pathlib import Path
from typing import Optional, Sequence

# Scopes: upload covers insert; youtube (broad) is needed for thumbnails.set.
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_CATEGORY_ID = "22"  # People & Blogs (UGC / talking-head)
RETRYABLE_STATUS = {500, 502, 503, 504}


class PublishError(RuntimeError):
    pass


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise PublishError(
            f"missing env var {name} — set YOUTUBE_CLIENT_ID / "
            f"YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN (mint the refresh "
            f"token with `python -m publishers.youtube_auth`)."
        )
    return val


def build_service():
    """Build an authenticated youtube v3 service from env refresh-token creds."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:  # pragma: no cover - depends on optional deps
        raise PublishError(
            "Google API client not installed. Run: pip install "
            "google-api-python-client google-auth google-auth-oauthlib "
            "google-auth-httplib2"
        ) from e

    creds = Credentials(
        token=None,
        refresh_token=_require_env("YOUTUBE_REFRESH_TOKEN"),
        client_id=_require_env("YOUTUBE_CLIENT_ID"),
        client_secret=_require_env("YOUTUBE_CLIENT_SECRET"),
        token_uri=TOKEN_URI,
        scopes=YOUTUBE_SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _to_rfc3339_utc(when: str) -> str:
    """Parse an ISO-8601 datetime (tz-aware or naive=UTC) → RFC3339 'Z' UTC."""
    raw = when.strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    parsed_utc = parsed.astimezone(dt.timezone.utc)
    if parsed_utc <= dt.datetime.now(dt.timezone.utc):
        raise PublishError(f"publish_at {when} is not in the future")
    return parsed_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[Sequence[str]] = None,
    category_id: str = DEFAULT_CATEGORY_ID,
    publish_at: Optional[str] = None,
    made_for_kids: bool = False,
    thumbnail_path: Optional[str] = None,
    service=None,
    max_retries: int = 5,
) -> dict:
    """
    Upload `video_path` to YouTube. If `publish_at` is given, the video goes up
    `private` and YouTube publishes it publicly at that time; otherwise it is
    published `public` immediately. Returns
    {video_id, url, privacy, publish_at}.
    """
    path = Path(video_path)
    if not path.is_file():
        raise PublishError(f"video not found: {video_path}")
    if len(title) > 100:
        raise PublishError(f"title exceeds YouTube's 100-char limit: {len(title)}")

    try:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:  # pragma: no cover
        raise PublishError(
            "Google API client not installed — see build_service()."
        ) from e

    yt = service or build_service()

    status: dict = {
        "selfDeclaredMadeForKids": bool(made_for_kids),
    }
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = _to_rfc3339_utc(publish_at)
    else:
        status["privacyStatus"] = "public"

    body = {
        "snippet": {
            "title": title,
            "description": description or "",
            "tags": list(tags) if tags else [],
            "categoryId": category_id,
        },
        "status": status,
    }

    media = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    attempt = 0
    while response is None:
        try:
            _progress, response = request.next_chunk()
        except HttpError as e:  # pragma: no cover - network dependent
            if getattr(e, "resp", None) is not None and e.resp.status in RETRYABLE_STATUS:
                attempt += 1
                if attempt > max_retries:
                    raise PublishError(f"upload failed after {max_retries} retries: {e}")
                time.sleep(2 ** attempt)
                continue
            raise PublishError(f"YouTube API error: {e}") from e

    video_id = response["id"]

    if thumbnail_path:
        tp = Path(thumbnail_path)
        if tp.is_file():
            from googleapiclient.http import MediaFileUpload as _MFU
            yt.thumbnails().set(videoId=video_id, media_body=_MFU(str(tp))).execute()

    return {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "privacy": status["privacyStatus"],
        "publish_at": status.get("publishAt"),
    }


def _read_description(args) -> str:
    if args.description_file:
        return Path(args.description_file).read_text(encoding="utf-8")
    return args.description or ""


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a Bella video to YouTube.")
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("upload", help="upload (optionally scheduled) a video")
    up.add_argument("--video", required=True)
    up.add_argument("--title", required=True)
    up.add_argument("--description")
    up.add_argument("--description-file")
    up.add_argument("--tags", help="comma-separated")
    up.add_argument("--category-id", default=DEFAULT_CATEGORY_ID)
    up.add_argument("--publish-at", help="ISO-8601, e.g. 2026-06-15T09:00:00+10:00")
    up.add_argument("--thumbnail")
    up.add_argument("--made-for-kids", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "upload":
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        result = upload_video(
            video_path=args.video,
            title=args.title,
            description=_read_description(args),
            tags=tags,
            category_id=args.category_id,
            publish_at=args.publish_at,
            made_for_kids=args.made_for_kids,
            thumbnail_path=args.thumbnail,
        )
        when = result["publish_at"] or "now (public)"
        print(f"Uploaded {result['url']} — privacy={result['privacy']} publish={when}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
