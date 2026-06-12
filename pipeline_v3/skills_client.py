"""
skills_client.py — Typed wrappers for the 18 Claude Code skills used by v3.0.

Each Claude Code skill is a SKILL.md file at ~/.claude/skills/{name}/SKILL.md
containing a system prompt + usage instructions. This module loads each
SKILL.md at import time and exposes one Python function per skill that:
  1. Takes typed arguments (topic, niche, format, etc.)
  2. Builds a user-turn prompt from those arguments
  3. Calls Claude Sonnet with the SKILL.md content as the system prompt
  4. Returns a dict with {raw_text, parsed (if JSON), meta}

Reuses the Anthropic SDK directly — engine.py:303 `_claude()` does not take a
system prompt, so we cannot reuse it. The client here is purpose-built.

Model: claude-sonnet-4-6 (matches writer pool default from engine.py:64-67).
Prompt caching is enabled on the SKILL.md system block (each skill's prompt
is ~2-5kB, cached across the day's triplet runs).
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from anthropic import Anthropic, APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

SKILL_DIR = Path.home() / ".claude" / "skills"

# Model tiering: Sonnet for creative/voice-driven outputs, Haiku for
# structured/routine outputs (captions, SEO descriptions,
# comments, calendar scaffolding). Haiku 4.5 is ~3× cheaper with negligible
# quality drop on structured tasks.
MODEL_SONNET = os.getenv("V3_MODEL_SONNET", "claude-sonnet-4-5-20250929")
MODEL_HAIKU  = os.getenv("V3_MODEL_HAIKU",  "claude-haiku-4-5-20251001")
# Back-compat: if V3_MODEL is set, it overrides both tiers.
_OVERRIDE    = os.getenv("V3_MODEL")
if _OVERRIDE:
    MODEL_SONNET = MODEL_HAIKU = _OVERRIDE

MAX_TOK = 4000

_client: Anthropic | None = None


def _anthropic() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


# ─── SKILL.md loading ────────────────────────────────────────────────────

@lru_cache(maxsize=32)
def _load_skill(name: str) -> str:
    """Load a SKILL.md file as the system prompt. Cached per name."""
    path = SKILL_DIR / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill not installed: {path}")
    text = path.read_text(encoding="utf-8")
    # Strip YAML frontmatter if present — the system prompt is the body.
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2].lstrip()
    return text


# ─── Core invocation ─────────────────────────────────────────────────────────

@dataclass
class SkillResult:
    skill: str
    raw_text: str
    parsed: Any | None       # dict/list if we could extract JSON, else None
    input_tokens: int
    output_tokens: int


def _extract_json(text: str) -> Any | None:
    """Try to pull the first JSON object or array out of the response."""
    fence = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    for opener, closer in (("{", "}"), ("[", "]")):
        i = text.find(opener)
        j = text.rfind(closer)
        if 0 <= i < j:
            try:
                return json.loads(text[i : j + 1])
            except json.JSONDecodeError:
                continue
    return None


def _invoke_skill(
    skill_name: str,
    user_input: str,
    *,
    max_tokens: int = MAX_TOK,
    max_retries: int = 5,
    model: str | None = None,
) -> SkillResult:
    system_prompt = _load_skill(skill_name)
    chosen_model = model or MODEL_SONNET
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = _anthropic().messages.create(
                model=chosen_model,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_input}],
            )
            break
        except (APIConnectionError, APITimeoutError, RateLimitError,
                httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectError) as e:
            last_err = e
            wait = min(2 ** attempt, 15)
            time.sleep(wait)
        except APIStatusError as e:
            # 5xx is retryable, 4xx is not
            if getattr(e, "status_code", 0) >= 500:
                last_err = e
                time.sleep(2 ** attempt)
                continue
            raise
    else:
        raise last_err or RuntimeError(f"exhausted retries for {skill_name}")

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return SkillResult(
        skill=skill_name,
        raw_text=text,
        parsed=_extract_json(text),
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


# ─── Skill wrappers (18) ─────────────────────────────────────────────────────
# Each wrapper formats the user turn from typed args. Output shape matches
# what the SKILL.md declares (see Phase 0 skill inventory in v3 spec).

# -- Planning -----------------------------------------------------------------

def run_content_calendar(
    niche: str,
    platforms: list[str],
    posting_frequency: str,
    goals: list[str],
    account_stage: str,
    duration_days: int = 30,
) -> SkillResult:
    user = (
        f"Niche: {niche}\n"
        f"Platforms: {', '.join(platforms)}\n"
        f"Posting frequency: {posting_frequency}\n"
        f"Goals: {', '.join(goals)}\n"
        f"Account stage: {account_stage}\n"
        f"Duration: {duration_days} days\n"
        "Return a day-by-day calendar. Include topic, format, hook, CTA, platform per post."
    )
    return _invoke_skill("content-calendar", user, max_tokens=4000, model=MODEL_HAIKU)


def run_trend_hijacker(trend_description: str, niche: str, goal: str) -> SkillResult:
    user = (
        f"Trend: {trend_description}\n"
        f"Niche: {niche}\n"
        f"Goal: {goal}\n"
        "Adapt this trend for the niche. Output script/caption, visual direction, "
        "risk level, hashtag strategy."
    )
    return _invoke_skill("trend-hijacker", user, max_tokens=1500, model=MODEL_HAIKU)


def run_viral_hook_formula(
    mode: Literal["analyze", "generate"],
    niche: str,
    topic: str,
    platform: str,
    viral_source: str | None = None,
    tone: str | None = None,
) -> SkillResult:
    if mode == "analyze":
        if not viral_source:
            raise ValueError("analyze mode requires viral_source")
        user = (
            f"Mode: A (analyze existing viral content)\n"
            f"Viral content: {viral_source}\n"
            f"My niche: {niche}\n"
            "Reverse-engineer the hook formula. Output formula + steps + 3 niche adaptations."
        )
    else:
        user = (
            f"Mode: B (generate new viral content)\n"
            f"Niche: {niche}\n"
            f"Topic: {topic}\n"
            f"Platform: {platform}\n"
            + (f"Tone: {tone}\n" if tone else "")
            + "Generate platform-differentiated hook variants for Reel, YouTube Short, "
            "and Carousel. Return JSON with keys reel, ytshort, carousel — each with "
            "hook_text, trigger_type, share_mechanism."
        )
    return _invoke_skill("viral-hook-formula", user)


# -- Scripting ----------------------------------------------------------------

def run_hook_generator(
    topic: str,
    niche: str,
    audience: str | None = None,
    content_format: str | None = None,
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Niche: {niche}\n"
        + (f"Audience: {audience}\n" if audience else "")
        + (f"Format: {content_format}\n" if content_format else "")
        + "Generate 10 ranked hook variations."
    )
    return _invoke_skill("hook-generator", user)


def run_reel_script(
    topic: str,
    niche: str,
    duration_s: Literal[15, 30, 60],
    style: str,
    hook: str | None = None,
    platform: Literal["instagram", "youtube_short"] = "instagram",
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Niche: {niche}\n"
        f"Duration: {duration_s}s\n"
        f"Style: {style}\n"
        f"Target platform: {platform}\n"
        + (f"Hook: {hook}\n" if hook else "")
        + "Produce complete time-coded script with spoken dialogue, on-screen text, "
        "visual directions, pacing notes, CTA, caption starter."
    )
    return _invoke_skill("reel-script", user, max_tokens=4000)


def run_carousel_writer(
    topic: str,
    niche: str,
    goal: str,
    slide_count: int = 8,
    hook: str | None = None,
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Niche: {niche}\n"
        f"Goal: {goal}\n"
        f"Slide count: {slide_count}\n"
        + (f"Opening hook: {hook}\n" if hook else "")
        + "Produce complete slide-by-slide copy with headline, body, design notes "
        "per slide. Slide 1 ≤ 5 words. Use open-loop technique between slides."
    )
    return _invoke_skill("carousel-writer", user, max_tokens=4000)


def run_story_arc_builder(
    topic: str,
    medium: str,
    goal: str,
    personal_angle: str | None = None,
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Medium: {medium}\n"
        f"Goal: {goal}\n"
        + (f"Personal angle: {personal_angle}\n" if personal_angle else "")
        + "Recommend best story framework for the goal, then output beat map with "
        "emotional targets, 3 power moments, opening line, title suggestion."
    )
    return _invoke_skill("story-arc-builder", user)


def run_emotional_storytelling(
    topic_or_script: str,
    target_emotion: str,
    platform: str,
    personal_angle: str | None = None,
) -> SkillResult:
    user = (
        f"Content: {topic_or_script}\n"
        f"Target emotion: {target_emotion}\n"
        f"Platform/format: {platform}\n"
        + (f"Personal angle: {personal_angle}\n" if personal_angle else "")
        + "Apply 5-step emotional architecture: destabilize → escalate → peak → "
        "resolve → inspire. Show 6-8 before/after language upgrades."
    )
    return _invoke_skill("emotional-storytelling", user)


def run_faceless_channel_script(
    topic: str,
    niche: str,
    channel_type: str,
    voice_style: str,
    length_min: int,
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Niche: {niche}\n"
        f"Channel type: {channel_type}\n"
        f"Voice style: {voice_style}\n"
        f"Length: {length_min} min\n"
        "Produce TTS-optimized script: narration in short sentences, visual "
        "direction per section, music cues, chapter timestamps, end card."
    )
    return _invoke_skill("faceless-channel-script", user, max_tokens=4000)


def run_youtube_script(
    topic: str,
    niche: str,
    target_length_min: Literal[5, 10, 15, 20],
    tone: str,
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Niche: {niche}\n"
        f"Length: {target_length_min} min\n"
        f"Tone: {tone}\n"
        "Produce complete long-form script with layered hook, chapters, "
        "re-engagement beats, outro, metadata."
    )
    return _invoke_skill("youtube-script", user, max_tokens=4000)


# -- Packaging ----------------------------------------------------------------

def run_caption_architect(
    topic: str,
    niche: str,
    post_format: Literal["reel", "carousel", "static", "story"],
    tone: str,
    goal: str,
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Niche: {niche}\n"
        f"Format: {post_format}\n"
        f"Tone: {tone}\n"
        f"Goal: {goal}\n"
        "Produce caption (Hook-Value-Story-CTA) + hashtag block + engagement prediction."
    )
    return _invoke_skill("caption-architect", user, max_tokens=1500, model=MODEL_HAIKU)


def run_yt_title_thumbnail(
    topic: str,
    niche: str,
    audience: str,
    emotional_angle: str | None = None,
) -> SkillResult:
    user = (
        f"Topic: {topic}\n"
        f"Niche: {niche}\n"
        f"Audience: {audience}\n"
        + (f"Emotional angle: {emotional_angle}\n" if emotional_angle else "")
        + "Output 10 title variants (≤60 chars) across archetypes + 3 thumbnail concepts."
    )
    return _invoke_skill("yt-title-thumbnail", user)


def run_yt_seo_description(
    video_title: str,
    topic: str,
    key_points: list[str],
    niche: str,
    target_keywords: list[str] | None = None,
) -> SkillResult:
    kp = "\n".join(f"  - {p}" for p in key_points)
    user = (
        f"Title: {video_title}\n"
        f"Topic: {topic}\n"
        f"Key points:\n{kp}\n"
        f"Niche: {niche}\n"
        + (f"Target keywords: {', '.join(target_keywords)}\n" if target_keywords else "")
        + "Produce 5-zone description, 30-40 tags, SEO scorecard, chapter timestamps."
    )
    return _invoke_skill("yt-seo-description", user, max_tokens=2000, model=MODEL_HAIKU)


def run_broll_shot_list(
    script_excerpt: str,
    niche: str,
    production_level: Literal["phone", "dslr", "ai_generated", "mixed"],
    style: str,
) -> SkillResult:
    user = (
        f"Script excerpt:\n{script_excerpt}\n\n"
        f"Niche: {niche}\n"
        f"Production level: {production_level}\n"
        f"Style: {style}\n"
        "Produce 20-40 shots with 3 execution paths each (film / stock / AI)."
    )
    return _invoke_skill("broll-shot-list", user, max_tokens=2500)


def run_viral_video_prompt(
    scene_concept: str,
    platform: Literal["runway", "sora", "kling", "pika", "heygen", "generic"],
    style: str,
    niche: str,
) -> SkillResult:
    user = (
        f"Scene concept: {scene_concept}\n"
        f"Target AI platform: {platform}\n"
        f"Style: {style}\n"
        f"Niche/use case: {niche}\n"
        "Generate 3 prompt variations optimized for the platform with negative "
        "prompts and settings. Include 5-10 prompt B-roll batch with shared aesthetic."
    )
    return _invoke_skill("viral-video-prompt", user)


# -- Repurpose & Engage -------------------------------------------------------

def run_short_form_repurpose(
    long_form_source: str,
    niche: str,
    primary_platform: str,
) -> SkillResult:
    user = (
        f"Source content:\n{long_form_source}\n\n"
        f"Niche: {niche}\n"
        f"Primary platform: {primary_platform}\n"
        "Produce full repurposing suite: 9 clips (3×Shorts + 3×Reels + 3×TikTok), "
        "4 adapted assets (carousel, quote, caption, thread), 3 extracted (hooks, "
        "email, story prompts), 2-week posting calendar."
    )
    return _invoke_skill("short-form-repurpose", user, max_tokens=3000)


def run_comment_engine(
    mode: Literal["reply", "outbound", "pinned", "engagement_q"],
    context: str,
    niche: str,
) -> SkillResult:
    user = (
        f"Mode: {mode}\n"
        f"Context: {context}\n"
        f"Niche: {niche}\n"
        "Produce the mode-appropriate output per skill spec (3 reply options / "
        "4 outbound comment types / 5 pinned templates / 5 engagement questions)."
    )
    return _invoke_skill("comment-engine", user, max_tokens=1500, model=MODEL_HAIKU)


# ─── Registry ────────────────────────────────────────────────────────────────

SKILL_FUNCTIONS = {
    "content-calendar":          run_content_calendar,
    "trend-hijacker":            run_trend_hijacker,
    "viral-hook-formula":        run_viral_hook_formula,
    "hook-generator":            run_hook_generator,
    "reel-script":               run_reel_script,
    "carousel-writer":           run_carousel_writer,
    "story-arc-builder":         run_story_arc_builder,
    "emotional-storytelling":    run_emotional_storytelling,
    "faceless-channel-script":   run_faceless_channel_script,
    "youtube-script":            run_youtube_script,
    "caption-architect":         run_caption_architect,
    "yt-title-thumbnail":        run_yt_title_thumbnail,
    "yt-seo-description":        run_yt_seo_description,
    "broll-shot-list":           run_broll_shot_list,
    "viral-video-prompt":        run_viral_video_prompt,
    "short-form-repurpose":      run_short_form_repurpose,
    "comment-engine":            run_comment_engine,
}


def list_installed_skills() -> list[str]:
    """Return skill names whose SKILL.md exists on disk."""
    return sorted(
        name for name in SKILL_FUNCTIONS
        if (SKILL_DIR / name / "SKILL.md").exists()
    )


if __name__ == "__main__":
    # Smoke test — no API calls, just verify every skill's SKILL.md loads.
    print(f"SKILL_DIR: {SKILL_DIR}")
    installed = list_installed_skills()
    missing = [n for n in SKILL_FUNCTIONS if n not in installed]
    print(f"Installed: {len(installed)}/{len(SKILL_FUNCTIONS)}")
    for name in installed:
        size = len(_load_skill(name))
        print(f"  ✓ {name:28}  {size:>6} chars")
    if missing:
        print(f"\nMissing ({len(missing)}):")
        for name in missing:
            print(f"  ✗ {name}")
