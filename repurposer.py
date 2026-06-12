"""
repurposer.py — Skill 7a: Long-Form Repurposing

Transforms every approved script into derivative content assets:
  {episode}_BLOG.md      — 800-1200 word blog post in Bella's voice
  {episode}_THREAD.md    — 8-12 tweet Twitter/X thread
  {episode}_SOCIAL.md    — 3 standalone social posts (LinkedIn, Facebook, generic)

Model: Claude Sonnet
Input: An approved job file (video_script + story_spine + caption + brief)
Output: 3 files per script in the same Scripts/Day N/ folder

Usage:
    python3 repurposer.py path/to/job.json         # one script
    python3 repurposer.py --all                     # all Scripts/Day N/
    python3 repurposer.py --target-date 2026-04-12  # all scripts for that date
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


# ─── Blog Post ──────────────────────────────────────────────────────────────

BLOG_PROMPT = """You are Bella — the SEO For Restaurants content persona. You're
writing a blog post based on a video script you just produced. The blog should:

- Be 800-1200 words
- Written in Bella's voice: warm, direct, authority-with-empathy
- Open with the same hook as the video (adapted for reading, not watching)
- Include the friend's story as the narrative anchor
- Include 2-3 actionable SEO/Google profile tips the reader can do today
- End with Bella's voice, not a generic CTA
- Use markdown formatting (headers, bold, bullet points)
- Include a "Key Takeaway" section near the end
- Do NOT mention "watch the video" or link to anything — this is standalone content

FRIEND: {friend} ({city}, {cuisine})
PILLAR: {pillar}
TONE: {tone}

VIDEO SCRIPT:
{video_script}

STORY SPINE:
{story_spine}

Write the blog post now. Return ONLY the blog content in markdown."""


# ─── Twitter/X Thread ──────────────────────────────────────────────────────

THREAD_PROMPT = """You are Bella — the SEO For Restaurants content persona. You're
writing a Twitter/X thread based on a video script you just produced. The thread should:

- Be 8-12 tweets
- Tweet 1 is the hook — must work standalone to stop the scroll
- Each tweet is max 280 characters
- Use the friend's story but keep it punchy (Twitter voice, not video voice)
- Include 2-3 concrete tips/numbers
- End with a Bella sign-off, not a sales pitch
- Format: number each tweet (1/, 2/, 3/, etc.)
- Do NOT use hashtags in every tweet — max 2-3 in the final tweet
- Do NOT say "thread" or "let me explain" — just start

FRIEND: {friend} ({city}, {cuisine})
PILLAR: {pillar}
TONE: {tone}

VIDEO SCRIPT:
{video_script}

Write the thread now. Return ONLY the tweets, numbered."""


# ─── Social Posts ───────────────────────────────────────────────────────────

SOCIAL_PROMPT = """You are Bella — the SEO For Restaurants content persona. Create
3 standalone social media posts from this video script. Each post should work on
its own (LinkedIn, Facebook, or general social). They are NOT excerpts — they're
purpose-built derivative content.

Rules:
- Post 1: INSIGHT post — lead with a surprising data point or counter-intuitive fact
- Post 2: STORY post — lead with the friend's emotional moment
- Post 3: ACTION post — lead with one specific thing the reader can do in 10 minutes

Each post:
- 150-250 words
- Standalone (no "watch the video" or "see thread")
- Written in Bella's voice
- Include the friend's name and neighbourhood
- End with Bella's voice, not a CTA

Format each post with "--- POST 1: INSIGHT ---", "--- POST 2: STORY ---", "--- POST 3: ACTION ---"

FRIEND: {friend} ({city}, {cuisine})
PILLAR: {pillar}
TONE: {tone}

VIDEO SCRIPT:
{video_script}

CAPTION:
{caption}

Write the 3 posts now."""


# ─── Generator ──────────────────────────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    """Single Sonnet call with DeepSeek fallback."""
    from llm_client import call_with_fallback
    return call_with_fallback(
        primary=MODEL_SONNET,
        prompt=prompt,
        max_tokens=3000,
        caller_name="repurposer",
    )


def repurpose_job(job_path: Path) -> list[Path]:
    """
    Read a job JSON file and generate 3 derivative assets.
    Returns list of paths written.
    """
    job = json.loads(job_path.read_text())
    brief = job.get("brief") or {}
    video_script = job.get("video_script", "")
    if not video_script:
        print(f"  [repurpose] {job_path.name}: no video_script — skipping")
        return []

    ep = job.get("episode_id", job_path.stem)
    out_dir = job_path.parent
    friend = brief.get("friend", "?")
    city = brief.get("city", "?")
    cuisine = ""
    # Try to get cuisine from friends_db
    try:
        db = json.loads((BASE_DIR / "data" / "friends_db.json").read_text())
        items = db.get("friends", db) if isinstance(db, dict) else db
        f_rec = next((f for f in items if f["id"] == friend), None)
        if f_rec:
            cuisine = f_rec.get("cuisine", "")
    except Exception:
        pass

    fmt_args = {
        "friend": friend,
        "city": city,
        "cuisine": cuisine,
        "pillar": brief.get("pillar", "?"),
        "tone": brief.get("tone", "?"),
        "video_script": video_script[:3000],
        "story_spine": job.get("story_spine", "")[:2000],
        "caption": job.get("caption", "")[:1000],
    }

    written: list[Path] = []

    # Blog post
    print(f"  [repurpose] generating blog post for {ep}...")
    try:
        blog = _call_llm(BLOG_PROMPT.format(**fmt_args))
        blog_path = out_dir / f"{ep}_BLOG.md"
        blog_path.write_text(blog)
        written.append(blog_path)
        print(f"    ✓ {blog_path.name}")
    except Exception as e:
        print(f"    ✗ blog failed: {e}")

    # Twitter thread
    print(f"  [repurpose] generating Twitter thread for {ep}...")
    try:
        thread = _call_llm(THREAD_PROMPT.format(**fmt_args))
        thread_path = out_dir / f"{ep}_THREAD.md"
        thread_path.write_text(thread)
        written.append(thread_path)
        print(f"    ✓ {thread_path.name}")
    except Exception as e:
        print(f"    ✗ thread failed: {e}")

    # Social posts
    print(f"  [repurpose] generating social posts for {ep}...")
    try:
        social = _call_llm(SOCIAL_PROMPT.format(**fmt_args))
        social_path = out_dir / f"{ep}_SOCIAL.md"
        social_path.write_text(social)
        written.append(social_path)
        print(f"    ✓ {social_path.name}")
    except Exception as e:
        print(f"    ✗ social failed: {e}")

    return written


def repurpose_all() -> int:
    """Walk all Scripts/Day N/ folders and repurpose every job file."""
    count = 0
    for day_dir in sorted(SCRIPTS_DIR.glob("Day */scripts")):
        for jf in sorted(day_dir.glob("*.json")):
            # Skip if already repurposed (blog exists)
            ep = jf.stem
            if (day_dir / f"{ep}_BLOG.md").exists():
                print(f"  [repurpose] {ep}: already repurposed — skipping")
                continue
            paths = repurpose_job(jf)
            count += len(paths)
    return count


def repurpose_by_date(target_date: str) -> int:
    """Repurpose all scripts for a given target_date."""
    count = 0
    for day_dir in sorted(SCRIPTS_DIR.glob("Day */scripts")):
        for jf in sorted(day_dir.glob("*.json")):
            job = json.loads(jf.read_text())
            if job.get("target_date") != target_date:
                continue
            paths = repurpose_job(jf)
            count += len(paths)
    return count


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Skill 7a — Long-Form Repurposing")
    p.add_argument("job_file", nargs="?", help="path to a single job JSON file")
    p.add_argument("--all", action="store_true", help="repurpose all scripts")
    p.add_argument("--target-date", help="repurpose scripts for a specific date")
    args = p.parse_args()

    if args.all:
        n = repurpose_all()
        print(f"\nGenerated {n} derivative assets")
    elif args.target_date:
        n = repurpose_by_date(args.target_date)
        print(f"\nGenerated {n} derivative assets for {args.target_date}")
    elif args.job_file:
        paths = repurpose_job(Path(args.job_file))
        print(f"\nGenerated {len(paths)} derivative assets")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
