"""
publishers/publish_queue.py — the content-scheduling routine.

Reads a queue file (default data/publish_queue.json) and publishes every
`pending` entry to its platform with that entry's scheduled `publish_at`.
For YouTube, scheduling is native: each pending Short is uploaded once with a
future publish_at and YouTube releases it itself — so you run this routine
whenever new content is queued (or on a cron), NOT at each post's go-live time.

Run:
    python -m publishers.publish_queue run                 # process pending
    python -m publishers.publish_queue run --dry-run       # show what would post
    python -m publishers.publish_queue list                # show the queue

Queue entry schema (see data/publish_queue.example.json):
    {
      "id": "day10_jake",
      "platform": "youtube",
      "video": "renders/day10_jake.mp4",
      "title": "Nine calls. Zero tables. #Shorts",
      "description_file": "creatives/daily_scripts/day10_caption.txt",
      "description": "(used if description_file is absent)",
      "tags": ["bella", "bellaciao", "fitzroy"],
      "category_id": "22",
      "thumbnail": "creatives/daily_scripts/Day10_Jake_cover.png",
      "publish_at": "2026-06-15T09:00:00+10:00",
      "made_for_kids": false,
      "status": "pending"
    }
status transitions: pending -> uploaded (adds `result`) | failed (adds `error`).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from publishers.youtube_publisher import PublishError, upload_video

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE = BASE_DIR / "data" / "publish_queue.json"

PLATFORMS = {"youtube"}


def _load(queue_path: Path) -> list[dict]:
    if not queue_path.is_file():
        raise SystemExit(f"queue not found: {queue_path}")
    data = json.loads(queue_path.read_text(encoding="utf-8"))
    items = data.get("queue") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise SystemExit("queue file must be a list, or an object with a 'queue' list")
    return items


def _save(queue_path: Path, items: list[dict]) -> None:
    tmp = queue_path.with_suffix(queue_path.suffix + ".tmp")
    tmp.write_text(json.dumps({"queue": items}, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(queue_path)


def _description_for(entry: dict) -> str:
    df = entry.get("description_file")
    if df:
        p = (BASE_DIR / df) if not Path(df).is_absolute() else Path(df)
        return p.read_text(encoding="utf-8")
    return entry.get("description", "")


def _resolve(path_str: str) -> str:
    p = Path(path_str)
    return str(p if p.is_absolute() else (BASE_DIR / p))


def _publish_youtube(entry: dict) -> dict:
    return upload_video(
        video_path=_resolve(entry["video"]),
        title=entry["title"],
        description=_description_for(entry),
        tags=entry.get("tags"),
        category_id=str(entry.get("category_id", "22")),
        publish_at=entry.get("publish_at"),
        made_for_kids=bool(entry.get("made_for_kids", False)),
        thumbnail_path=_resolve(entry["thumbnail"]) if entry.get("thumbnail") else None,
    )


def run(queue_path: Path, dry_run: bool = False) -> int:
    items = _load(queue_path)
    pending = [e for e in items if e.get("status", "pending") == "pending"]
    if not pending:
        print("nothing pending.")
        return 0

    failures = 0
    for entry in pending:
        plat = entry.get("platform")
        label = entry.get("id", entry.get("title", "<unnamed>"))
        if plat not in PLATFORMS:
            print(f"SKIP {label}: unsupported platform '{plat}' (supported: {sorted(PLATFORMS)})")
            continue
        when = entry.get("publish_at") or "now (public)"
        if dry_run:
            print(f"DRY-RUN would post [{plat}] {label} -> publish {when}")
            continue
        try:
            result = _publish_youtube(entry)
            entry["status"] = "uploaded"
            entry["result"] = result
            entry.pop("error", None)
            print(f"OK  {label} -> {result['url']} (publish {result['publish_at'] or 'now'})")
        except (PublishError, KeyError, OSError) as e:
            entry["status"] = "failed"
            entry["error"] = str(e)
            failures += 1
            print(f"FAIL {label}: {e}")

    if not dry_run:
        _save(queue_path, items)
    return 1 if failures else 0


def list_queue(queue_path: Path) -> int:
    for e in _load(queue_path):
        print(f"[{e.get('status','pending'):>8}] {e.get('platform','?'):>8}  "
              f"{e.get('id','<unnamed>')}  publish={e.get('publish_at','now')}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bella content scheduling routine.")
    parser.add_argument("command", choices=["run", "list"])
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    queue_path = Path(args.queue)
    if args.command == "run":
        return run(queue_path, dry_run=args.dry_run)
    return list_queue(queue_path)


if __name__ == "__main__":
    raise SystemExit(main())
