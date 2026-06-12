"""
packaging.py — Skill 6: Titles & Thumbnails (Packaging)

Generates title options and thumbnail concepts for each content piece,
informed by the script content and Bella's brand voice.

Model: Claude Sonnet
Input: Approved job file (video_script + brief + caption)
Output: {episode}_PACKAGE.md in the same Scripts/Day N/ folder

Usage:
    python3 packaging.py path/to/job.json
    python3 packaging.py --all
    python3 packaging.py --target-date 2026-04-12
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR      = Path(__file__).parent
SCRIPTS_DIR   = BASE_DIR.parent / "Creatives" / "Daily assets"
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_SONNET  = "claude-sonnet-4-6"


PACKAGING_PROMPT = """You are the Packaging Strategist for the Bellaciao content engine.
Bella creates short-form video content about restaurant SEO. You're responsible for
the title, thumbnail concept, and platform-specific packaging that maximizes click-through.

Given the script below, generate packaging options. Return in this format:

## TITLE OPTIONS (ranked by predicted engagement — #1 is your top pick)

1. **[title]** — [why this works in 1 sentence]
2. **[title]** — [why]
3. **[title]** — [why]
4. **[title]** — [why]
5. **[title]** — [why]

## PLATFORM-SPECIFIC TITLES

**YouTube Shorts:** [title — max 100 chars, keyword-front-loaded]
**Instagram Reel:** [title — max 60 chars, emotion-first]
**TikTok:** [title — max 80 chars, curiosity-driven]
**Blog/SEO:** [title — max 60 chars, keyword-optimized for Google]

## THUMBNAIL CONCEPTS (3 options)

**Concept 1: [name]**
- Visual layout: [describe the composition — what's in frame, where text goes]
- Text overlay: "[the 3-5 word text on the thumbnail]"
- Emotion: [what the viewer should feel — curiosity? shock? recognition?]
- Color scheme: [dominant colors]
- Friend in frame: [yes/no, doing what]

**Concept 2: [name]**
[same structure]

**Concept 3: [name]**
[same structure]

## HASHTAGS

**Instagram (5):** [5 hashtags]
**TikTok (3):** [3 hashtags]
**YouTube (5):** [5 tags — not hashtags, YouTube tags]

RULES:
- No clickbait that the video doesn't deliver on
- No "YOU WON'T BELIEVE" / "SHOCKING" / generic viral bait
- Titles must be specific to the friend and the problem
- Thumbnails must show a REAL person or food, never abstract graphics
- Bella's name does NOT go in the title unless it's a cold-open format

FRIEND: {friend} ({city}, {cuisine})
FORMAT: {format}
PILLAR: {pillar}
TONE: {tone}

VIDEO SCRIPT:
{video_script}

CAPTION:
{caption}

Generate the packaging now."""


def package_job(job_path: Path) -> Path | None:
    """Generate a packaging doc for a single job file."""
    job = json.loads(job_path.read_text())
    brief = job.get("brief") or {}
    video_script = job.get("video_script", "")
    if not video_script:
        print(f"  [packaging] {job_path.name}: no video_script — skipping")
        return None

    ep = job.get("episode_id", job_path.stem)
    out_path = job_path.parent / f"{ep}_PACKAGE.md"

    friend = brief.get("friend", "?")
    cuisine = ""
    try:
        db = json.loads((BASE_DIR / "data" / "friends_db.json").read_text())
        items = db.get("friends", db) if isinstance(db, dict) else db
        f_rec = next((f for f in items if f["id"] == friend), None)
        if f_rec:
            cuisine = f_rec.get("cuisine", "")
    except Exception:
        pass

    from llm_client import call_with_fallback
    prompt = PACKAGING_PROMPT.format(
        friend=friend,
        city=brief.get("city", "?"),
        cuisine=cuisine,
        format=brief.get("format", "?"),
        pillar=brief.get("pillar", "?"),
        tone=brief.get("tone", "?"),
        video_script=video_script[:3000],
        caption=job.get("caption", "")[:1000],
    )

    print(f"  [packaging] generating for {ep}...")
    content = call_with_fallback(
        primary=MODEL_SONNET,
        prompt=prompt,
        max_tokens=2000,
        caller_name="packaging",
    )

    header = (
        f"# PACKAGING — {ep}\n"
        f"**Friend:** {friend} | **Format:** {brief.get('format','?')} | "
        f"**Pillar:** {brief.get('pillar','?')} | **Tone:** {brief.get('tone','?')}\n\n"
        f"---\n\n"
    )
    out_path.write_text(header + content)
    print(f"    ✓ {out_path.name}")
    return out_path


def package_all() -> int:
    count = 0
    for day_dir in sorted(SCRIPTS_DIR.glob("Day */scripts")):
        for jf in sorted(day_dir.glob("*.json")):
            ep = jf.stem
            if (day_dir / f"{ep}_PACKAGE.md").exists():
                continue
            if package_job(jf):
                count += 1
    return count


def main() -> None:
    p = argparse.ArgumentParser(description="Skill 6 — Titles & Thumbnails Packaging")
    p.add_argument("job_file", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--target-date")
    args = p.parse_args()

    if args.all:
        n = package_all()
        print(f"\nGenerated {n} packaging docs")
    elif args.target_date:
        count = 0
        for dd in sorted(SCRIPTS_DIR.glob("Day */scripts")):
            for jf in sorted(dd.glob("*.json")):
                job = json.loads(jf.read_text())
                if job.get("target_date") == args.target_date:
                    if package_job(jf):
                        count += 1
        print(f"\nGenerated {count} packaging docs for {args.target_date}")
    elif args.job_file:
        package_job(Path(args.job_file))
    else:
        p.print_help()


if __name__ == "__main__":
    main()
