"""
shot_director.py — Agent 9: Shot Director.

Splits an approved Bella script into a sequence of 5-10 second video clips,
each carrying a complete model-agnostic prompt that any text-to-video engine
(Kling / Veo / Runway / Sora / Sync.so / etc.) can consume via a thin adapter.

Why model-agnostic prompts:
  - The user is not committed to a single video engine yet
  - Engine choice may change per day, per clip type, or per cost target
  - The adapter layer (`video_adapters/`) reformats the universal prompt into
    engine-specific syntax — but the structured shot dict is the contract

Output is attached to the job file under `shot_list`. The downstream video
creation tool reads `shot_list.shots` and walks them in order.

Reference: Master Documents/VIDEO_INPUT_CONTRACT.md
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

import brand

# Shared .env at the Bellaciao Content/ level
load_dotenv(Path(__file__).parent.parent / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_OPUS        = "claude-opus-4-6"

DEFAULT_CLIP_SECONDS = 6   # safest middle ground (Kling / Veo / Runway / Sora / Sync.so)
MIN_CLIP_SECONDS     = 5
MAX_CLIP_SECONDS     = 10

# ─── Resilience: backoff + circuit breaker ───────────────────────────────────
# Anthropic flakes ~50% with transient connection errors. One retry helped
# but wasn't enough; backoff smooths bursts and the breaker stops us from
# burning the API (and the user's time) when the service is genuinely down.

_RETRY_ATTEMPTS    = 4           # total tries: initial + 3 retries
_BACKOFF_BASE_S    = 1.0         # 1s, 2s, 4s with jitter
_BACKOFF_CAP_S     = 8.0
_BREAKER_THRESHOLD = 3           # consecutive run-level failures before opening
_BREAKER_COOLDOWN  = 300         # seconds the breaker stays open before half-open

_breaker_state = {"consecutive_failures": 0, "opened_at": 0.0}


def _is_transient(err: Exception) -> bool:
    """Connection blips, timeouts, 5xx, and rate limits are worth retrying.
    Auth/validation errors are not — fail fast to the deterministic fallback."""
    name = type(err).__name__
    if name in {"APIConnectionError", "APITimeoutError", "InternalServerError",
                "RateLimitError", "ServiceUnavailableError", "OverloadedError"}:
        return True
    status = getattr(err, "status_code", None)
    if isinstance(status, int) and (status >= 500 or status == 429):
        return True
    return False


def _breaker_is_open() -> bool:
    if _breaker_state["consecutive_failures"] < _BREAKER_THRESHOLD:
        return False
    if time.time() - _breaker_state["opened_at"] >= _BREAKER_COOLDOWN:
        # half-open: let one call through to test recovery
        return False
    return True


def _breaker_record_success() -> None:
    _breaker_state["consecutive_failures"] = 0
    _breaker_state["opened_at"] = 0.0


def _breaker_record_failure() -> None:
    _breaker_state["consecutive_failures"] += 1
    if _breaker_state["consecutive_failures"] == _BREAKER_THRESHOLD:
        _breaker_state["opened_at"] = time.time()

_SECTION_BOUNDARY_RE = re.compile(r"^\s*(?:#+\s*|\*+\s*)?SECTION\s+\d\b", re.IGNORECASE)
_BOLD_RE             = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE           = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_BACKTICK_RE         = re.compile(r"`([^`]+)`")
_MULTI_WS_RE         = re.compile(r"\s+")
_SENTENCE_SPLIT_RE   = re.compile(r"(?<=[.!?])\s+")
_SPEAKER_RE          = re.compile(r"^\s*([A-Z][A-Z0-9 _'-]{1,30}):\s*(.+)$")


# ─── Data types ──────────────────────────────────────────────────────────────

@dataclass
class Shot:
    shot_id: str
    clip_index: int
    clip_count: int
    duration_seconds: int
    audio_slice: dict           # {"start_ms": int, "end_ms": int, "text": str}
    subject: str                # "bella" | "friend" | "ciao" | "scene"
    reference_images: list[str]
    scene: str
    action: str
    camera: str
    lighting: str
    mood: str
    continuity: dict            # {"wardrobe": str, "props_carry": list, ...}
    negative: list[str]
    transition_in: str
    transition_out: str
    prompt_universal: str       # the single string a T2V engine consumes

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShotList:
    clip_count: int
    default_clip_seconds: int
    total_duration_seconds: int
    world_description: str      # repeated context prepended to every prompt for continuity
    continuity: dict            # global continuity block
    shots: list[Shot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "clip_count":             self.clip_count,
            "default_clip_seconds":   self.default_clip_seconds,
            "total_duration_seconds": self.total_duration_seconds,
            "world_description":      self.world_description,
            "continuity":             self.continuity,
            "shots":                  [s.to_dict() for s in self.shots],
        }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_section(full: str, label: str) -> str:
    if label not in full:
        return _truncate_at_next_section(full)
    lines, in_sec, out = full.split("\n"), False, []
    for line in lines:
        if label in line:
            in_sec = True
            continue
        if in_sec and _SECTION_BOUNDARY_RE.match(line) and label not in line:
            break
        if in_sec:
            out.append(line)
    return _truncate_at_next_section("\n".join(out).strip())


def _truncate_at_next_section(text: str) -> str:
    if not text:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        if _SECTION_BOUNDARY_RE.match(line):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _strip_directions(text: str) -> str:
    """Remove [direction] notes from spoken text — they're for the actor, not TTS."""
    return re.sub(r"\[[^\]]*\]", "", text).strip()


def _word_count(text: str) -> int:
    return len(_strip_directions(text).split())


def _clean_markup(text: str) -> str:
    text = _truncate_at_next_section(_strip_directions(text))
    text = re.sub(r"(?m)^\s*---+\s*$", " ", text)
    text = _BOLD_RE.sub(r"\1", text)
    text = _ITALIC_RE.sub(r"\1", text)
    text = _BACKTICK_RE.sub(r"\1", text)
    text = _MULTI_WS_RE.sub(" ", text)
    return text.strip()


def _extract_json(raw: str) -> dict:
    """
    Extract a single JSON object from a possibly-noisy LLM response.
    Handles ```json fences, leading prose, and braces nested inside string
    literals (the previous brace-balance walker broke on those).
    """
    raw = raw.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0]
    elif raw.startswith("```"):
        raw = raw.split("```", 2)[1].split("```", 1)[0]
    raw = raw.strip()
    start = raw.find("{")
    if start == -1:
        raise ValueError("no JSON object in shot director response")
    # JSONDecoder.raw_decode() understands strings/escapes/arrays — won't
    # be fooled by a `}` inside a quoted value.
    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(raw[start:])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON decode failed at char {e.pos}: {e.msg}") from e
    if not isinstance(obj, dict):
        raise ValueError(f"shot director returned a {type(obj).__name__}, expected object")
    return obj


def _compute_clip_count(target_duration: int, clip_length: int = DEFAULT_CLIP_SECONDS) -> int:
    """ceil(duration / clip_length), clamped to [1, 12]."""
    n = max(1, math.ceil(target_duration / clip_length))
    return min(n, 12)


def _split_unit(text: str) -> tuple[str, str]:
    text = _clean_markup(text)
    if not text:
        return "", ""

    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if len(sentences) >= 2:
        mid = max(1, len(sentences) // 2)
        return " ".join(sentences[:mid]), " ".join(sentences[mid:])

    words = text.split()
    if len(words) < 8:
        return text, ""
    mid = max(1, len(words) // 2)
    return " ".join(words[:mid]), " ".join(words[mid:])


def _spoken_units(spoken: str, clip_count: int) -> list[str]:
    units = [_clean_markup(p) for p in re.split(r"\n\s*\n", spoken) if _clean_markup(p)]
    if not units:
        clean = _clean_markup(spoken)
        units = [clean] if clean else []
    if not units:
        return [""]

    while len(units) < clip_count:
        idx = max(range(len(units)), key=lambda i: len(units[i].split()))
        left, right = _split_unit(units[idx])
        if not right:
            break
        units[idx:idx + 1] = [left, right]

    return units


def _group_units(units: list[str], clip_count: int) -> list[str]:
    if not units:
        return [""] * max(1, clip_count)

    count = max(1, clip_count)
    points = [round(i * len(units) / count) for i in range(count + 1)]
    groups: list[str] = []
    for i in range(count):
        start, end = points[i], points[i + 1]
        chunk = units[start:end]
        if not chunk:
            chunk = [units[min(start, len(units) - 1)]]
        groups.append(" ".join(chunk).strip())
    return groups


def _duration_plan(total_seconds: int, clip_count: int) -> list[int]:
    count = max(1, clip_count)
    total = max(count, int(total_seconds))
    base, remainder = divmod(total, count)
    return [base + (1 if i < remainder else 0) for i in range(count)]


def _avatar_map(brief: dict, scene_brief: dict | str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for src in (brief.get("avatars") or {}, scene_brief if isinstance(scene_brief, dict) else {}):
        for key in ("bella_avatar", "friend_avatar", "ciao_avatar"):
            value = src.get(key) if isinstance(src, dict) else None
            if value:
                out[key] = str(value)
    return out


def _friend_tokens(brief: dict) -> set[str]:
    friend = str(brief.get("friend") or "").replace("_", " ").lower()
    return {t for t in friend.split() if t}


def _infer_wardrobe(brief: dict, scene_brief: dict | str | None) -> str:
    raw = " ".join(
        str(v) for v in (
            brief.get("director_note"),
            brief.get("tone"),
            scene_brief.get("scene_description") if isinstance(scene_brief, dict) else scene_brief,
        ) if v
    ).lower()
    if "apron" in raw:
        return "restaurant apron over work clothes"
    if "linen" in raw:
        return "soft linen service wear"
    if "bar" in raw:
        return "working restaurant blacks with lived-in layers"
    return "real restaurant workwear, practical and slightly worn"


def _infer_props(scene_brief: dict | str | None) -> list[str]:
    raw = " ".join(
        str(v) for v in (
            scene_brief.get("enemy_visual") if isinstance(scene_brief, dict) else scene_brief,
            scene_brief.get("scene_description") if isinstance(scene_brief, dict) else "",
            scene_brief.get("ciao_moment") if isinstance(scene_brief, dict) else "",
        ) if v
    ).lower()
    props: list[str] = []
    for token, label in (
        ("phone", "phone"),
        ("tablecloth", "white tablecloth"),
        ("counter", "counter"),
        ("pass", "service pass"),
        ("sauce", "sauce pot"),
        ("lemon", "cut lemon"),
        ("oyster", "oyster shells"),
        ("glass", "water glass"),
    ):
        if token in raw and label not in props:
            props.append(label)
    return props[:4]


def _infer_lighting(scene_brief: dict | str | None) -> str:
    raw = " ".join(
        str(v) for v in (
            scene_brief.get("scene_description") if isinstance(scene_brief, dict) else scene_brief,
            scene_brief.get("camera") if isinstance(scene_brief, dict) else "",
        ) if v
    ).lower()
    if "afternoon" in raw:
        return "warm afternoon window light cutting across the room"
    if "overhead light" in raw or "single overhead" in raw:
        return "a single overhead practical light with soft falloff"
    if "dusk" in raw or "night" in raw:
        return "low amber restaurant light with gentle shadow"
    return "warm practical restaurant light with natural depth"


def _world_description(
    brief: dict,
    scene_brief: dict | str | None,
    wardrobe: str,
    lighting: str,
) -> str:
    city = str(brief.get("city") or (scene_brief.get("city") if isinstance(scene_brief, dict) else "") or "").strip()
    neighbourhood = str(
        (scene_brief.get("neighbourhood") if isinstance(scene_brief, dict) else "") or ""
    ).strip()
    restaurant = str(brief.get("restaurant_name") or "the restaurant").strip()
    scene = ""
    if isinstance(scene_brief, dict):
        scene = _clean_markup(scene_brief.get("scene_description") or scene_brief.get("enemy_visual") or "")
    else:
        scene = _clean_markup(str(scene_brief or ""))
    location = ", ".join(p for p in (neighbourhood, city) if p)
    lead = f"Photoreal vertical 9:16 video inside {restaurant}" if restaurant else "Photoreal vertical 9:16 restaurant video"
    if location:
        lead += f" in {location}"
    if scene:
        lead += f". {scene}"
    return (
        f"{lead} {lighting}. Keep wardrobe consistent: {wardrobe}. "
        "The room feels lived-in, specific, and emotionally true to a real service day."
    ).strip()


def _infer_subject(
    beat: str,
    clip_index: int,
    clip_count: int,
    brief: dict,
    avatars: dict[str, str],
) -> str:
    low = beat.lower()
    friend_tokens = _friend_tokens(brief)

    if "ciao" in low and avatars.get("ciao_avatar"):
        return "ciao"
    if "bella:" in low and avatars.get("bella_avatar"):
        return "bella"
    if any(marker in low for marker in ("i watched", "i thought", "i'm here", "im here")) and avatars.get("bella_avatar"):
        return "bella"
    if any(token in low for token in friend_tokens) and avatars.get("friend_avatar"):
        return "friend"

    speaker = _SPEAKER_RE.match(beat)
    if speaker:
        name = speaker.group(1).strip().lower()
        if name == "bella" and avatars.get("bella_avatar"):
            return "bella"
        if avatars.get("friend_avatar"):
            return "friend"

    if clip_index == clip_count and avatars.get("bella_avatar"):
        return "bella"
    if avatars.get("friend_avatar"):
        return "friend"
    if avatars.get("bella_avatar"):
        return "bella"
    if avatars.get("ciao_avatar"):
        return "ciao"
    return "scene"


def _reference_images_for_subject(subject: str, avatars: dict[str, str]) -> list[str]:
    primary_key = {
        "bella": "bella_avatar",
        "friend": "friend_avatar",
        "ciao": "ciao_avatar",
    }.get(subject)
    refs: list[str] = []
    if primary_key and avatars.get(primary_key):
        refs.append(avatars[primary_key])
    for key in ("friend_avatar", "bella_avatar", "ciao_avatar"):
        value = avatars.get(key)
        if value and value not in refs:
            refs.append(value)
    return refs[:2]


def _scene_for_beat(
    beat: str,
    subject: str,
    scene_brief: dict | str | None,
) -> str:
    if isinstance(scene_brief, dict):
        low = beat.lower()
        if "phone" in low or "search" in low or "walk past" in low:
            return _clean_markup(scene_brief.get("enemy_visual") or scene_brief.get("scene_description") or "")
        if subject == "ciao":
            return _clean_markup(scene_brief.get("ciao_moment") or scene_brief.get("scene_description") or "")
        return _clean_markup(scene_brief.get("scene_description") or scene_brief.get("enemy_visual") or "")
    return _clean_markup(str(scene_brief or "restaurant interior"))


def _action_for_beat(subject: str, beat: str) -> str:
    if subject == "ciao":
        return f"Ciao marks the turn as this beat lands: {beat}"
    if subject == "bella":
        return f"Bella holds the emotional beat and carries this line: {beat}"
    return f"The restaurant owner lives the beat on camera: {beat}"


def _camera_for_clip(
    clip_index: int,
    clip_count: int,
    scene_brief: dict | str | None,
) -> str:
    if isinstance(scene_brief, dict) and scene_brief.get("camera"):
        base = _clean_markup(str(scene_brief.get("camera")))
    else:
        base = "static medium shot, 50mm, shallow depth of field"
    if clip_count == 1:
        return base
    if clip_index == 1:
        return f"establishing wide, 35mm, gentle push-in; {base}"
    if clip_index == clip_count:
        return f"tight close-up, 50mm, hold on the final beat; {base}"
    return f"medium close-up, 50mm, slow push-in; {base}"


def _mood_for_beat(beat: str) -> str:
    low = beat.lower()
    if "sorry" in low or "quiet" in low or "soft" in low:
        return "quiet recognition"
    if "ciao" in low or "turn" in low:
        return "turning-point tension"
    if "breathe" in low or "still knocking" in low:
        return "restrained resolve"
    if "search" in low or "phone" in low:
        return "low operational dread"
    return "warm observed realism"


def _shorten(text: str, limit: int = 28) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(",;:") + "…"


def _prompt_universal(
    world_description: str,
    scene: str,
    action: str,
    camera: str,
    lighting: str,
    mood: str,
    beat: str,
    duration_seconds: int,
) -> str:
    return " ".join(
        part for part in (
            world_description,
            f"Scene: {_shorten(scene, 26)}.",
            f"Action: {_shorten(action, 30)}.",
            f"Camera: {camera}.",
            f"Lighting: {lighting}.",
            f"Mood: {mood}.",
            f"Anchor the visuals to this spoken beat: \"{beat}\".",
            f"No text. No logos. No modern signage. {duration_seconds} seconds.",
        ) if part
    )


# ─── Director prompt ─────────────────────────────────────────────────────────

DIRECTOR_PROMPT = """You are the Shot Director for the Bellaciao content engine.

Your job: split the approved Bella script below into a sequence of {clip_count}
video clips, each {clip_length} seconds long (total target: {total_seconds}s).
The downstream video tool generates each clip independently with a text-to-video
engine — your prompts must be self-contained, model-agnostic, and visually
specific enough that ANY engine (Kling, Veo, Runway, Sora, Sync.so) could
produce a usable clip from them.

CRITICAL RULES:
1. Visual continuity ACROSS clips is the hardest problem. Use the world_description
   block (repeated verbatim in every clip's prompt_universal) to lock setting,
   wardrobe, and lighting. Refer to characters by their canonical reference image.
2. Each clip's prompt_universal MUST be a single self-contained string. Never
   say "as before" or "same as clip 1". Re-describe everything every time.
3. NO text overlays, NO captions baked into the visual, NO logos.
4. NO modern signage that could date the clip. NO branded products.
5. The audio_slice text per clip is the spoken line(s) the clip must visually
   align with — split the script across clips in roughly equal time chunks.
6. Reference images: every clip with bella/friend/ciao MUST list the relevant
   reference image path so the engine can use image-to-video conditioning.

THE BRIEF (context only — do not score):
  friend             : {friend_name} @ {restaurant_name}
  city/neighbourhood : {city}, {neighbourhood}
  cuisine            : {cuisine}
  tone               : {tone}
  total duration     : {total_seconds}s ({total_words} spoken words)
  bella avatar       : {bella_avatar}
  ciao avatar        : {ciao_avatar}
  friend avatar      : {friend_avatar}

THE APPROVED SCRIPT (Section 2 — spoken):
{script_text}

THE SCENE BRIEF (Section 4 — director notes):
{scene_brief}

OUTPUT FORMAT — strict JSON, no markdown, no commentary:
{{
  "world_description": "ONE paragraph repeated verbatim in every clip prompt. Lock setting, time of day, lighting, wardrobe, restaurant interior. About 50 words. Make it specific enough that two clips generated from it would feel like the same world.",
  "continuity": {{
    "wardrobe": "what {friend_name} is wearing across all clips",
    "lighting_arc": "how light evolves across the {clip_count} clips",
    "props": ["named objects that recur"]
  }},
  "shots": [
    {{
      "shot_id": "01",
      "clip_index": 1,
      "clip_count": {clip_count},
      "duration_seconds": {clip_length},
      "audio_slice": {{
        "start_ms": 0,
        "end_ms": {clip_length_ms},
        "text": "the spoken words this clip covers (verbatim from Section 2)"
      }},
      "subject": "bella | friend | ciao | scene",
      "reference_images": ["paths to reference images for the subjects in this clip"],
      "scene": "where we are, what time of day, what the camera sees first",
      "action": "what happens in 1-2 short sentences. Describe motion and beats.",
      "camera": "shot type + lens + movement (e.g. 'macro push-in, 50mm, shallow depth')",
      "lighting": "specific light source + colour + direction",
      "mood": "one phrase",
      "continuity": {{
        "wardrobe": "what's worn in this specific clip",
        "props_carry": ["specific props in this clip"]
      }},
      "negative": ["text overlays", "modern signage", "extra people", "logos"],
      "transition_in": "cut | match cut on X | hard cut | cross-fade",
      "transition_out": "cut | match cut on X | ...",
      "prompt_universal": "FULL self-contained text-to-video prompt. Start with the world_description verbatim. Then add the action, camera, lighting, mood. End with 'No text. No logos. No modern signage. {clip_length} seconds.' Around 80-120 words total."
    }},
    ...{clip_count_minus_one} more shots
  ]
}}

GENERATE EXACTLY {clip_count} SHOTS. Cover the entire script. The audio_slice
end_ms of the last shot should equal the total duration in milliseconds.
"""


# ─── Public API ──────────────────────────────────────────────────────────────

def build_shot_list(
    approved_script: str,
    brief: dict,
    scene_brief: dict | str | None = None,
    clip_length: int = DEFAULT_CLIP_SECONDS,
) -> ShotList:
    """
    Generate a structured shot list for the approved script.

    Returns an empty (but well-shaped) ShotList on failure rather than raising —
    the rest of the pipeline must keep running so the user still gets the script.
    """
    if not (MIN_CLIP_SECONDS <= clip_length <= MAX_CLIP_SECONDS):
        clip_length = DEFAULT_CLIP_SECONDS

    # Slot-aware duration fallback — never hardcode 18s (old pre-alignment default).
    slot            = (brief.get("format") or "reel").lower()
    slot_band       = brand.SLOT_DURATION.get(slot, brand.SLOT_DURATION["reel"])
    target_duration = int(brief.get("target_duration_seconds") or slot_band["target"])
    clip_count      = _compute_clip_count(target_duration, clip_length)
    total_seconds   = clip_count * clip_length

    spoken = _extract_section(approved_script, "SECTION 2") or approved_script
    if not spoken.strip():
        return _empty_shot_list(target_duration, clip_length, "no_section_2")

    if not ANTHROPIC_API_KEY:
        return _fallback_shot_list(
            approved_script=spoken,
            brief=brief,
            scene_brief=scene_brief,
            clip_count=clip_count,
            clip_length=clip_length,
            target_duration=target_duration,
            reason="no_anthropic_key",
        )

    avatars = brief.get("avatars") or {}
    prompt = DIRECTOR_PROMPT.format(
        clip_count           = clip_count,
        clip_count_minus_one = clip_count - 1,
        clip_length          = clip_length,
        clip_length_ms       = clip_length * 1000,
        total_seconds        = total_seconds,
        total_words          = _word_count(spoken),
        friend_name          = brief.get("friend", "?"),
        restaurant_name      = brief.get("restaurant_name", ""),
        city                 = brief.get("city", ""),
        neighbourhood        = brief.get("neighbourhood", ""),
        cuisine              = brief.get("cuisine", ""),
        tone                 = brief.get("tone", "warm_and_real"),
        bella_avatar         = avatars.get("bella_avatar")  or "(missing)",
        ciao_avatar          = avatars.get("ciao_avatar")   or "(missing)",
        friend_avatar        = avatars.get("friend_avatar") or "(missing)",
        script_text          = _strip_directions(spoken),
        scene_brief          = json.dumps(scene_brief, indent=2) if isinstance(scene_brief, dict) else (scene_brief or ""),
    )

    if _breaker_is_open():
        cooldown_left = int(_BREAKER_COOLDOWN - (time.time() - _breaker_state["opened_at"]))
        print(f"[shot-director] circuit breaker OPEN — skipping API for ~{cooldown_left}s, using fallback")
        return _fallback_shot_list(
            approved_script=spoken,
            brief=brief,
            scene_brief=scene_brief,
            clip_count=clip_count,
            clip_length=clip_length,
            target_duration=target_duration,
            reason="breaker_open",
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    # Exponential backoff with jitter on transient errors only. Permanent
    # errors (auth, validation, 4xx) fail fast — retrying them is waste.
    # Persistent failure trips the module-level circuit breaker so subsequent
    # runs short-circuit straight to the deterministic fallback.
    last_err: Exception | None = None
    resp = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            resp = client.messages.create(
                model      = MODEL_OPUS,
                max_tokens = 8000,
                messages   = [{"role": "user", "content": prompt}],
            )
            _breaker_record_success()
            break
        except Exception as e:
            last_err = e
            transient = _is_transient(e)
            if not transient or attempt == _RETRY_ATTEMPTS:
                _breaker_record_failure()
                kind = "transient" if transient else "permanent"
                print(f"[shot-director] API call failed (attempt {attempt}/{_RETRY_ATTEMPTS}, {kind}): {e}")
                return _fallback_shot_list(
                    approved_script=spoken,
                    brief=brief,
                    scene_brief=scene_brief,
                    clip_count=clip_count,
                    clip_length=clip_length,
                    target_duration=target_duration,
                    reason=f"api_error: {e}",
                )
            sleep_s = min(_BACKOFF_CAP_S, _BACKOFF_BASE_S * (2 ** (attempt - 1)))
            sleep_s += random.uniform(0, sleep_s * 0.25)  # jitter
            print(f"[shot-director] API call failed (attempt {attempt}/{_RETRY_ATTEMPTS}, transient): {e} — retrying in {sleep_s:.1f}s")
            time.sleep(sleep_s)
    if resp is None:
        return _fallback_shot_list(
            approved_script=spoken,
            brief=brief,
            scene_brief=scene_brief,
            clip_count=clip_count,
            clip_length=clip_length,
            target_duration=target_duration,
            reason=f"api_error: {last_err}",
        )

    raw = resp.content[0].text
    try:
        data = _extract_json(raw)
    except Exception as e:
        print(f"[shot-director] JSON parse failed: {e}")
        return _fallback_shot_list(
            approved_script=spoken,
            brief=brief,
            scene_brief=scene_brief,
            clip_count=clip_count,
            clip_length=clip_length,
            target_duration=target_duration,
            reason=f"parse_error: {e}",
        )

    return _hydrate_shot_list(data, clip_count, clip_length, total_seconds)


# ─── Hydration / fallback ────────────────────────────────────────────────────

def _hydrate_shot_list(
    data: dict,
    clip_count: int,
    clip_length: int,
    total_seconds: int,
) -> ShotList:
    """Convert raw model JSON into typed Shot objects, with sane defaults."""
    raw_shots = data.get("shots") or []
    shots: list[Shot] = []
    for i, s in enumerate(raw_shots[:clip_count]):
        slice_default = {
            "start_ms": i * clip_length * 1000,
            "end_ms":   (i + 1) * clip_length * 1000,
            "text":     "",
        }
        audio_slice = {**slice_default, **(s.get("audio_slice") or {})}

        shots.append(Shot(
            shot_id            = s.get("shot_id") or f"{i + 1:02d}",
            clip_index         = int(s.get("clip_index") or i + 1),
            clip_count         = int(s.get("clip_count") or clip_count),
            duration_seconds   = int(s.get("duration_seconds") or clip_length),
            audio_slice        = audio_slice,
            subject            = s.get("subject") or "scene",
            reference_images   = list(s.get("reference_images") or []),
            scene              = s.get("scene") or "",
            action             = s.get("action") or "",
            camera             = s.get("camera") or "",
            lighting           = s.get("lighting") or "",
            mood               = s.get("mood") or "",
            continuity         = dict(s.get("continuity") or {}),
            negative           = list(s.get("negative") or
                                       ["text overlays", "logos", "modern signage", "extra people"]),
            transition_in      = s.get("transition_in") or ("cut" if i == 0 else "hard cut"),
            transition_out     = s.get("transition_out") or "cut",
            prompt_universal   = s.get("prompt_universal") or "",
        ))

    return ShotList(
        clip_count             = len(shots) or clip_count,
        default_clip_seconds   = clip_length,
        total_duration_seconds = total_seconds,
        world_description      = data.get("world_description") or "",
        continuity             = dict(data.get("continuity") or {}),
        shots                  = shots,
    )


def _empty_shot_list(target_duration: int, clip_length: int, reason: str) -> ShotList:
    print(f"[shot-director] returning empty shot list ({reason})")
    return ShotList(
        clip_count             = 0,
        default_clip_seconds   = clip_length,
        total_duration_seconds = target_duration,
        world_description      = f"(shot list unavailable: {reason})",
        continuity             = {},
        shots                  = [],
    )


def _fallback_shot_list(
    *,
    approved_script: str,
    brief: dict,
    scene_brief: dict | str | None,
    clip_count: int,
    clip_length: int,
    target_duration: int,
    reason: str,
) -> ShotList:
    print(f"[shot-director] building deterministic fallback shot list ({reason})")

    clean_spoken = _truncate_at_next_section(_clean_markup(approved_script))
    if not clean_spoken:
        return _empty_shot_list(target_duration, clip_length, reason)

    units = _spoken_units(clean_spoken, clip_count)
    beats = _group_units(units, clip_count)
    durations = _duration_plan(target_duration, len(beats))

    avatars = _avatar_map(brief, scene_brief)
    wardrobe = _infer_wardrobe(brief, scene_brief)
    props = _infer_props(scene_brief)
    lighting = _infer_lighting(scene_brief)
    world = _world_description(brief, scene_brief, wardrobe, lighting)

    shots: list[Shot] = []
    start_ms = 0
    total_clips = len(beats)
    for idx, beat in enumerate(beats, start=1):
        duration_seconds = durations[idx - 1]
        end_ms = start_ms + duration_seconds * 1000
        subject = _infer_subject(beat, idx, total_clips, brief, avatars)
        refs = _reference_images_for_subject(subject, avatars)
        scene = _scene_for_beat(beat, subject, scene_brief) or world
        action = _action_for_beat(subject, beat)
        camera = _camera_for_clip(idx, total_clips, scene_brief)
        mood = _mood_for_beat(beat)

        shots.append(
            Shot(
                shot_id=f"{idx:02d}",
                clip_index=idx,
                clip_count=total_clips,
                duration_seconds=duration_seconds,
                audio_slice={
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": beat,
                },
                subject=subject,
                reference_images=refs,
                scene=scene,
                action=action,
                camera=camera,
                lighting=lighting,
                mood=mood,
                continuity={
                    "wardrobe": wardrobe,
                    "props_carry": props,
                },
                negative=["text overlays", "logos", "modern signage", "extra people"],
                transition_in="cut" if idx == 1 else "hard cut",
                transition_out="cut",
                prompt_universal=_prompt_universal(
                    world_description=world,
                    scene=scene,
                    action=action,
                    camera=camera,
                    lighting=lighting,
                    mood=mood,
                    beat=beat,
                    duration_seconds=duration_seconds,
                ),
            )
        )
        start_ms = end_ms

    if shots:
        shots[-1].audio_slice["end_ms"] = target_duration * 1000

    return ShotList(
        clip_count=len(shots),
        default_clip_seconds=clip_length,
        total_duration_seconds=target_duration,
        world_description=world,
        continuity={
            "wardrobe": wardrobe,
            "lighting_arc": lighting,
            "props": props,
        },
        shots=shots,
    )


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Run the Shot Director on an approved job file")
    p.add_argument("job_file", help="path to a Scripts/Day N/{episode}.json or data/jobs/*.json")
    p.add_argument("--clip-length", type=int, default=DEFAULT_CLIP_SECONDS,
                   help=f"clip length in seconds (default {DEFAULT_CLIP_SECONDS})")
    args = p.parse_args()

    job = json.loads(Path(args.job_file).read_text())
    sl = build_shot_list(
        approved_script = job.get("video_script", ""),
        brief           = job.get("brief", {}),
        scene_brief     = job.get("scene_brief"),
        clip_length     = args.clip_length,
    )
    print(json.dumps(sl.to_dict(), indent=2))
