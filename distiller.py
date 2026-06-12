"""
distiller.py — Skill 7b: Short-Form Distillation

Takes a reel script (30-60s) and re-engineers it into purpose-built short-form
content (60-120s) designed natively for TikTok, Reels, and Shorts. The result
feels native to each platform rather than a chopped-up leftover.

Model: Claude Sonnet
Input: An approved reel job file
Output: {episode}_SHORT.json + {episode}_SHORT.txt in Scripts/Day N/

Usage:
    python3 distiller.py path/to/job.json
    python3 distiller.py --all
    python3 distiller.py --target-date 2026-04-12
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR      = Path(__file__).parent
SCRIPTS_DIR   = BASE_DIR.parent / "Creatives" / "Daily assets"
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_SONNET  = "claude-sonnet-4-6"


DISTILL_PROMPT = """You are the Short-Form Content Director for the Bellaciao content engine.

You have a reel script (~30-60 seconds, 80-150 words). Your job is to RE-ENGINEER
it into a purpose-built short-form piece (60-120 seconds, 150-300 words) that feels
native to TikTok/Reels/Shorts — NOT a chopped-up version of the original.

Rules:
- The distilled version is LONGER than the original (expands, doesn't compress)
- It takes the SAME story angle but builds it out with more beats
- The hook must be rewritten for short-form scroll-stop (faster, punchier)
- Add 1-2 extra beats that the original reel didn't have room for
- Include more of the friend's personality and dialogue
- The elixir (resolution) can be more explicit than in the 30s version
- Bella's voice should feel even more intimate (close-up, confessional tone)
- End with "I'm Bella — ciao for now."
- Return valid JSON

Return this JSON shape:
{{
  "platform_variants": {{
    "tiktok": {{
      "hook": "string — TikTok-native opening line (pattern-interrupt style)",
      "script": "string — full script with speaker labels",
      "caption": "string — TikTok caption with 3 hashtags",
      "duration_target_seconds": 90,
      "word_count": 200
    }},
    "reels": {{
      "hook": "string — Instagram Reels opening line (visual-first)",
      "script": "string — full script",
      "caption": "string — IG caption with 5 hashtags",
      "duration_target_seconds": 90,
      "word_count": 200
    }},
    "shorts": {{
      "hook": "string — YouTube Shorts opening line (curiosity-gap)",
      "script": "string — full script",
      "caption": "string — YouTube description with tags",
      "duration_target_seconds": 90,
      "word_count": 200
    }}
  }},
  "expanded_beats": [
    "string — beat 1 description",
    "string — beat 2 description (NEW — not in original)"
  ],
  "production_notes": "string — what to emphasize in filming/generation"
}}

FRIEND: {friend} ({city}, {cuisine})
ORIGINAL FORMAT: {format} ({duration}s)
PILLAR: {pillar}
TONE: {tone}
ENEMY: {enemy}

ORIGINAL VIDEO SCRIPT:
{video_script}

ORIGINAL STORY SPINE:
{story_spine}

Distill and expand now. Return ONLY valid JSON."""


def distill_job(job_path: Path) -> list[Path]:
    """Distill a reel script into platform-native short-form variants."""
    job = json.loads(job_path.read_text())
    brief = job.get("brief") or {}

    # Only distill reels (the longer format has more to work with)
    fmt = brief.get("format", "")
    if fmt == "story":
        print(f"  [distill] {job_path.name}: story format — skipping (only reels distilled)")
        return []

    video_script = job.get("video_script", "")
    if not video_script:
        print(f"  [distill] {job_path.name}: no video_script — skipping")
        return []

    ep = job.get("episode_id", job_path.stem)
    out_dir = job_path.parent

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
    prompt = DISTILL_PROMPT.format(
        friend=friend,
        city=brief.get("city", "?"),
        cuisine=cuisine,
        format=fmt,
        duration=brief.get("target_duration_seconds", "?"),
        pillar=brief.get("pillar", "?"),
        tone=brief.get("tone", "?"),
        enemy=brief.get("enemy", "?"),
        video_script=video_script[:3000],
        story_spine=job.get("story_spine", "")[:2000],
    )

    print(f"  [distill] generating short-form variants for {ep}...")
    raw = call_with_fallback(
        primary=MODEL_SONNET,
        prompt=prompt,
        max_tokens=4000,
        caller_name="distill",
    )

    # Parse JSON
    try:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif text.startswith("```"):
            text = text.split("```", 2)[1].split("```", 1)[0]
        distilled = json.loads(text.strip())
    except json.JSONDecodeError:
        distilled = {"raw_response": raw, "parse_error": True}

    distilled["source_episode"] = ep
    distilled["distilled_at"] = datetime.now().isoformat(timespec="seconds")

    written: list[Path] = []

    # JSON output (machine-readable)
    json_path = out_dir / f"{ep}_SHORT.json"
    json_path.write_text(json.dumps(distilled, indent=2, ensure_ascii=False))
    written.append(json_path)
    print(f"    ✓ {json_path.name}")

    # Text output (human-readable)
    txt_lines = [
        f"SHORT-FORM DISTILLATION — {ep}",
        "=" * 60,
        f"Source: {fmt} ({brief.get('target_duration_seconds','?')}s) → distilled to 60-120s",
        f"Friend: {friend} ({brief.get('city','?')})",
        "",
    ]
    variants = distilled.get("platform_variants", {})
    for platform in ("tiktok", "reels", "shorts"):
        v = variants.get(platform, {})
        if not v:
            continue
        txt_lines.extend([
            "",
            f"{'═' * 60}",
            f"PLATFORM: {platform.upper()}",
            f"{'═' * 60}",
            f"Hook: {v.get('hook', '?')}",
            f"Duration: {v.get('duration_target_seconds', '?')}s",
            f"Words: {v.get('word_count', '?')}",
            "",
            "SCRIPT:",
            "-" * 40,
            v.get("script", "(no script)"),
            "",
            "CAPTION:",
            "-" * 40,
            v.get("caption", "(no caption)"),
            "",
        ])

    notes = distilled.get("production_notes", "")
    if notes:
        txt_lines.extend([
            "",
            "PRODUCTION NOTES:",
            "-" * 40,
            notes,
            "",
        ])

    beats = distilled.get("expanded_beats", [])
    if beats:
        txt_lines.extend([
            "",
            "EXPANDED BEATS (vs original):",
            "-" * 40,
        ])
        for b in beats:
            txt_lines.append(f"  • {b}")
        txt_lines.append("")

    txt_path = out_dir / f"{ep}_SHORT.txt"
    txt_path.write_text("\n".join(txt_lines))
    written.append(txt_path)
    print(f"    ✓ {txt_path.name}")

    return written


def distill_all() -> int:
    count = 0
    for day_dir in sorted(SCRIPTS_DIR.glob("Day */scripts")):
        for jf in sorted(day_dir.glob("*.json")):
            if jf.stem.endswith("_SHORT"):
                continue
            ep = jf.stem
            if (day_dir / f"{ep}_SHORT.json").exists():
                continue
            paths = distill_job(jf)
            count += len(paths)
    return count


def main() -> None:
    p = argparse.ArgumentParser(description="Skill 7b — Short-Form Distillation")
    p.add_argument("job_file", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--target-date")
    args = p.parse_args()

    if args.all:
        n = distill_all()
        print(f"\nGenerated {n} short-form assets")
    elif args.target_date:
        count = 0
        for dd in sorted(SCRIPTS_DIR.glob("Day */scripts")):
            for jf in sorted(dd.glob("*.json")):
                if jf.stem.endswith("_SHORT"):
                    continue
                job = json.loads(jf.read_text())
                if job.get("target_date") == args.target_date:
                    paths = distill_job(jf)
                    count += len(paths)
        print(f"\nGenerated {count} short-form assets for {args.target_date}")
    elif args.job_file:
        distill_job(Path(args.job_file))
    else:
        p.print_help()


if __name__ == "__main__":
    main()
