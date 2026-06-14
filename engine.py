"""
engine.py — Agents 4A-D (writers) + Agent 5 (self-grader) + Agent 6 (judge).

Pipeline:
  1. Build the prompt from brand bible + brief + cast (friend, enemy, ally)
  2. Run the configured writer pool for the current round
  3. Each writer self-grades on the 9-dimension rubric and rewrites the 2 weakest
     dimensions up to 3 times before submitting
  4. Claude Opus judges the surviving scripts blind (labels A/B/C/D)
  5. Returns a JudgeVerdict + winning script

Default operating mode is now cost-aware for the daily channel model:
  - 1 Reel + 1 Story per day
  - YouTube reuses the Reel's core content rather than requiring a separate
    full script branch
  - Round 1 starts lean (Claude only), then broadens only if quality needs it

The Quality Supervisor (quality_supervisor.py) takes over from here for the
7-gate check, rewrite loop, and polish pass.
"""

from __future__ import annotations

import os
import json
import concurrent.futures
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

import anthropic
import openai
from dotenv import load_dotenv

import brand
from network_probe import require_host
from strategy import get_friend

# API keys are loaded from the shared Bellaciao Content/.env (parent folder),
# so every project under Bellaciao Content/ uses the same credentials file.
load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR = Path(__file__).parent

# ─── Clients ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_API_KEYS   = [k for k in (
    GEMINI_API_KEY,
    os.getenv("GEMINI_API_KEY_2", ""),
    os.getenv("GEMINI_API_KEY_3", ""),
) if k]

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
openai_client    = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
deepseek_client  = openai.OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",
) if DEEPSEEK_API_KEY else None

_gemini_key_idx = 0
_gemini_model = None
_gemini_active_key = None
def _get_gemini():
    """Return a Gemini model bound to the currently-active key, or None."""
    global _gemini_model, _gemini_active_key
    if not GEMINI_API_KEYS:
        return None
    if _gemini_model is None:
        try:
            import google.generativeai as genai
            key = GEMINI_API_KEYS[_gemini_key_idx]
            genai.configure(api_key=key)
            _gemini_model = genai.GenerativeModel("gemini-2.5-flash")
            _gemini_active_key = key
        except Exception as e:
            print(f"  [Gemini] init failed: {e}")
    return _gemini_model

def _rotate_gemini_key() -> bool:
    """Advance to the next Gemini key. Returns True if a new key was activated."""
    global _gemini_key_idx, _gemini_model, _gemini_active_key
    if _gemini_key_idx + 1 >= len(GEMINI_API_KEYS):
        return False
    _gemini_key_idx += 1
    _gemini_model = None
    _gemini_active_key = None
    print(f"  [Gemini] quota hit — rotating to key #{_gemini_key_idx + 1}/{len(GEMINI_API_KEYS)}")
    return _get_gemini() is not None

# ─── Models ──────────────────────────────────────────────────────────────────
MODEL_CLAUDE_WRITER = "claude-sonnet-4-6"
MODEL_CLAUDE_JUDGE  = "claude-opus-4-6"
MODEL_GPT4O         = "gpt-4o"
MODEL_DEEPSEEK      = "deepseek-chat"

DIMENSION_LABELS = {
    "sensory":        "Scroll-stop / Bella-spoken hook strength (25%)",
    "recognition":    "Emotional recognition (20%)",
    "spine":          "Story Spine momentum (15%)",
    "enemy":          "Enemy presence (10%)",
    "transformation": "Vogler transformation (10%)",
    "bella":          "Bella as mentor (5%)",
    "ciao":           "Ciao turning point (5%)",
    "elixir":         "The Elixir (10%)",
    "zero_sell":      "Zero-sell integrity — BODY/Elixir only, hook zone exempt (5%, BINARY)",
}

SELF_GRADE_MAX_ATTEMPTS = 3
WRITER_STRATEGY = os.getenv("BELLA_WRITER_STRATEGY", "lean_daily").strip().lower()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA TYPES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SelfGradeResult:
    script: str
    score: float
    passed: bool
    attempts: int
    dimension_scores: dict
    weak_dimensions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class JudgeVerdict:
    winner: Optional[str]
    scores: dict
    rationale: dict
    weak_dimensions: list[str]
    best_script: str
    best_weighted_score: float
    zero_sell_triggered: bool = False
    disqualified: list[str]    = field(default_factory=list)
    scripts: dict              = field(default_factory=dict)   # full script bodies by label
    self_grades: dict          = field(default_factory=dict)   # label → SelfGradeResult dict

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT BUILDING
# ═══════════════════════════════════════════════════════════════════════════════

def build_generation_prompt(brief: dict, rewrite_notes: str = "", round_num: int = 1) -> str:
    friend = get_friend(brief["friend"])
    enemy_key = brief.get("enemy", "")
    ally_key  = brief.get("ally", "")
    slot      = (brief.get("format") or "reel").lower()
    slot_band = brand.SLOT_DURATION.get(slot, brand.SLOT_DURATION["reel"])
    target_duration = int(brief.get("target_duration_seconds") or slot_band["target"])
    target_words = int(target_duration * 2.5)

    enemy_desc = brand.ENEMIES.get(enemy_key, "A specific operational or human pressure.")
    ally_desc  = brand.ALLIES.get(ally_key, "A loyal staff member or regular who shows up when needed.")

    rewrite_section = ""
    if rewrite_notes:
        rewrite_section = (
            f"\nREWRITE NOTES FROM ROUND {round_num - 1}:\n{rewrite_notes}\n"
            "These issues must be fixed.\n"
        )

    sensory_hook = brief.get("sensory_hook") or (friend.get("sensory_hooks") or [""])[0]
    failure_mode = brief.get("enemy_failure_mode", "")
    currency     = brief.get("currency", "$")
    city         = brief.get("city", friend.get("city", friend.get("location", "")))
    neighbourhood = friend.get("neighbourhood", "")
    street_detail = friend.get("street_detail", "")
    restaurant_name = friend.get("restaurant_name", friend.get("fantasy_restaurant_name", ""))
    mode         = brief.get("mode", "generic")

    # Editorial mode block — what the writer must / must not do this round.
    if mode == "event_day":
        mode_block = (
            f"  EDITORIAL MODE: EVENT_DAY — {brief.get('calendar_event','')}.\n"
            f"  The story MUST anchor on this event by name. The publish date "
            f"IS the event day."
        )
        anchor_directive = "Anchor: the calendar event above."
    elif mode == "event_eve":
        mode_block = (
            f"  EDITORIAL MODE: EVENT_EVE — the day BEFORE {brief.get('calendar_event','')}.\n"
            f"  Frame the story as the calm-before-the-storm prep moment. The "
            f"event itself happens TOMORROW."
        )
        anchor_directive = "Anchor: the eve-of-event tension and what's about to break tomorrow."
    else:
        mode_block = (
            "  EDITORIAL MODE: GENERIC — no Tier-1 calendar event today or tomorrow.\n"
            "  DO NOT fabricate a calendar event. Anchor the script on the\n"
            "  neighbourhood + one specific operational detail from the friend's\n"
            "  before/after profile. The story is friend-driven."
        )
        anchor_directive = (
            "Anchor: the friend's neighbourhood + one specific operational "
            "detail from their before/after profile."
        )

    # Slot spec — story or reel — drives the structural rules below.
    slot_spec_block = brand.SLOT_SPEC.get(slot, brand.REEL_SPEC)

    # Slot-specific OUTPUT section (Python 3.9 f-strings can't contain nested
    # triple-quoted strings, so we build this block first and interpolate it).
    if slot == "story":
        output_sections = (
            f"SECTION 1: STORY BEAT (3-4 sentences max — internal only, not spoken)\n"
            f"  ONE moment, isolated. The instant a reel would build TOWARD.\n"
            f"  Setting + sensory anchor + the emotional turn. No arc, no resolution.\n"
            f"  Bella's witnessing line is implied by the beat, not stated here.\n"
            f"\n"
            f"SECTION 2: SPOKEN STORY (target {target_duration} seconds — approx {target_words} words)\n"
            f"  Opens with the LOCKED Bella-spoken hook above — delivered BELLA: direct-to-camera.\n"
            f"  The hook MAY acknowledge Bella's AI nature and name what she did (archetype: Pain / Insider / Myth-Buster).\n"
            f"  After the hook: ONE emotional reveal + ONE Bella observational line at the end (body must NOT pitch).\n"
            f"  Friend voice labelled in CAPS: e.g. \"JAKE: ...\"\n"
            f"  Bella's BODY lines and closing line are observational — no pitch, no fourth-wall break outside the hook zone.\n"
            f"  In the BODY, never mention a product or booking system. In the HOOK, Bella may name automation she owns.\n"
            f"  Mandatory final line: \"I'm Bella — ciao for now.\" (delivered as BELLA:, verbatim, always).\n"
            f"  NEVER use a forbidden ending phrase.\n"
            f"  Use {currency} for any monetary figure — never the wrong currency.\n"
            f"  WORD COUNT TARGET: {target_words} words (±5).\n"
            f"  HARD CEILING: 33 seconds. If it runs over, cut a clause not a beat.\n"
            f"\n"
            f"SECTION 3: INSTAGRAM CAPTION (story slot)\n"
            f"  ONE line that names the beat + 3 woven hashtags.\n"
            f"  No bullet structure. Conversational. The caption is the post-roll thought.\n"
            f"  Hashtags: #bella #bellaciao + ONE topical tag."
        )
    else:
        output_sections = (
            f"SECTION 1: STORY SPINE (8 sentences — Pixar)\n"
            f"  ONCE UPON A TIME:\n"
            f"  EVERY DAY:\n"
            f"  BUT ONE DAY:\n"
            f"  BECAUSE OF THAT (1):\n"
            f"  BECAUSE OF THAT (2):\n"
            f"  BECAUSE OF THAT (3):\n"
            f"  UNTIL FINALLY:\n"
            f"  AND EVER SINCE THEN:\n"
            f"\n"
            f"SECTION 2: VIDEO SCRIPT (spoken, target {target_duration} seconds — approx {target_words} words)\n"
            f"  Opens with the LOCKED Bella-spoken hook above — BELLA: direct-to-camera, archetype-aligned (Pain/Insider/Myth-Buster).\n"
            f"  The HOOK ZONE (0-5s) is the ONE place Bella may break the fourth wall or name automation she owns.\n"
            f"  After the hook, return to observational narration. The BODY must NOT pitch, tease features, or break the fourth wall.\n"
            f"  Pacing notes in [brackets]. Friend voices labelled in CAPS: e.g. \"JAKE: ...\"\n"
            f"  The elixir is the quietest moment — always human, never a product. Mandatory close: \"I'm Bella — ciao for now.\"\n"
            f"  In the BODY, never mention a product or booking system.\n"
            f"  NEVER use a forbidden ending phrase.\n"
            f"  Use {currency} for any monetary figure — never the wrong currency.\n"
            f"  WORD COUNT TARGET: {target_words} words (±5).\n"
            f"  HARD FLOOR: 30 seconds. If it runs short, the brief was misclassified.\n"
            f"\n"
            f"SECTION 3: INSTAGRAM CAPTION (reel slot)\n"
            f"  Beat 1 (Ordinary World): Sensory hook + 2-3 sentences.\n"
            f"  Beat 2 (The Call): One sentence. The disruption.\n"
            f"  Beat 3 (Enemy + Ordeal): 3-4 sentences. The cost.\n"
            f"  Beat 4 (The Ally): 1-2 sentences. Who showed up.\n"
            f"  Beat 5 (The Elixir): 2 sentences. Small. Earned.\n"
            f"  Beat 6 (The Transmission): Closing line weaving in 5 hashtags\n"
            f"    + #bella #bellaciao #ciaobella."
        )

    return f"""
{brand.BELLA_BRIEF}

{brand.DISNEY_UNIVERSE}

{brand.DUAL_FRAMEWORK}

{brand.SENSORY_ARC}

{brand.CONTENT_RULES}

═══════════════════════════════════════════════════════════════════════════
SLOT — THIS PIECE IS A {slot.upper()}
═══════════════════════════════════════════════════════════════════════════
{slot_spec_block}

HARD BLOCKERS — the Quality Supervisor rejects and caps the score if any fail:
  1. At least one line in SECTION 2 starts with `BELLA:` (Bella must speak on-camera).
  2. The final spoken line is EXACTLY: "I'm Bella — ciao for now." (delivered as BELLA:).
  3. Ciao the Italian Greyhound appears at the turning point — either as a `CIAO:`
     inner-monologue line in SECTION 2 or as a populated `ciao_moment` in SECTION 4.
     Ciao may be omitted ONLY when the brief explicitly sets `ciao_allowed_absent: true`.

FORBIDDEN ENDINGS — never close with any of these phrases:
{json.dumps(brand.FORBIDDEN_ENDINGS, indent=2)}

THIS STORY'S CAST:
  HERO: {friend.get('name','')} @ {restaurant_name}
        {neighbourhood}{(' — ' + street_detail) if street_detail else ''}, {city}
        Cuisine: {friend.get('cuisine', friend.get('restaurant_style',''))}
        Story angle: {friend.get('story_angle','')}
        Bella-spoken hook (LOCKED — BELLA: delivers this as the opener, 0-3s): "{sensory_hook}"
  SHADOW: {enemy_key} — {enemy_desc}
          Failure mode for this event: {failure_mode or '(use the friend story angle)'}
  ALLY: {ally_key} — {ally_desc}
        (On camera: OPTIONAL. Default is "mentioned in narration only". Put
        the ally in scene with labelled dialogue ONLY when the story
        specifically needs their physical presence — most videos don't.)
  PILLAR: {brief.get('pillar')}  ({brand.PILLARS.get(brief.get('pillar'),{}).get('theme','')})
  TONE: {brief.get('tone','warm_and_real')}
  FORMAT: {brief.get('format','reel')}
  CURRENCY (LOCKED): {currency}
  DIRECTOR'S NOTE: {brief.get('director_note','')}

EDITORIAL CONTEXT:
{mode_block}
  CALENDAR EVENT: {brief.get('calendar_event') or '(none — generic mode)'}
  ANCHOR DIRECTIVE: {anchor_directive}
{rewrite_section}

OUTPUT (generate ALL — slot-aware structure below):

{output_sections}

SECTION 4: SCENE BRIEF (JSON for the video stage)
{{
  "friend_id": "{friend.get('id','')}",
  "city": "{city}",
  "neighbourhood": "{neighbourhood}",
  "enemy_visual": "[how the shadow manifests visually]",
  "ciao_moment": "[exact moment + what he does — bark/think out loud]",
  "scene_description": "[2-3 sentences — what is happening visually]",
  "camera": "[push in / pull back / handheld / static / orbit]",
  "duration_seconds": {target_duration},
  "ssml_notes": "[any pacing notes the SSML tagger should respect]"
}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# WRITERS
# ═══════════════════════════════════════════════════════════════════════════════

def _claude(prompt: str) -> str:
    system = f"You are a world-class short-form storyteller for restaurant owners.\n{brand.MODEL_ROLES['claude']}"
    require_host("api.anthropic.com", "Anthropic")
    r = anthropic_client.messages.create(
        model=MODEL_CLAUDE_WRITER,
        max_tokens=brand.MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text


def _gpt4o(prompt: str) -> str:
    system = f"You are a world-class short-form storyteller for restaurant owners.\n{brand.MODEL_ROLES['gpt4o']}"
    require_host("api.openai.com", "OpenAI")
    r = openai_client.chat.completions.create(
        model=MODEL_GPT4O,
        max_tokens=brand.MAX_TOKENS,
        timeout=90,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content


def _deepseek(prompt: str, timeout: int = 60) -> str:
    system = f"You are a world-class short-form storyteller for restaurant owners.\n{brand.MODEL_ROLES['deepseek']}"
    require_host("api.deepseek.com", "DeepSeek")
    r = deepseek_client.chat.completions.create(
        model=MODEL_DEEPSEEK,
        max_tokens=brand.MAX_TOKENS,
        timeout=timeout,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content


def _gemini(prompt: str) -> str:
    model = _get_gemini()
    if model is None:
        raise RuntimeError("Gemini not configured")
    require_host("generativelanguage.googleapis.com", "Gemini")
    system = f"You are a world-class short-form storyteller for restaurant owners.\n{brand.MODEL_ROLES['gemini']}"
    full = system + "\n\n" + prompt
    while True:
        try:
            return model.generate_content(full).text
        except Exception as e:
            msg = str(e)
            is_quota = "429" in msg or "ResourceExhausted" in type(e).__name__ or "quota" in msg.lower()
            if is_quota and _rotate_gemini_key():
                model = _get_gemini()
                continue
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-GRADER (Agent 5) — runs inside each writer
# ═══════════════════════════════════════════════════════════════════════════════

SELF_GRADE_PROMPT = """You are SELF-GRADING a Bella story script before submitting it to the Judge.
Score every dimension on 0-10. Be HONEST — over-scoring wastes Judge tokens.

DIMENSIONS (weights in parentheses):
  sensory        (20%) — does the opening land in 3 words and use the LOCKED hook?
  recognition    (25%) — would a restaurant owner stop scrolling and feel SEEN?
  spine          (15%) — does each Pixar beat earn the next?
  enemy          (10%) — is the Shadow named and present in Act 2?
  transformation (10%) — is there a clear inner change in the hero?
  bella          (5%)  — Bella is ALWAYS physically on screen (narrating, visible, own avatar shots) AND she witnesses without dominating. Both halves required.
  ciao           (5%)  — Ciao REQUIRED by default — marks the turning point ONCE. Score 0 if absent unless the brief sets ciao_allowed_absent=true (then score the narrative fit alone).
  elixir         (10%) — is the closing small, human, earned — NOT a forbidden ending or product?
  zero_sell      (5%)  — BINARY. ANY pitch / feature mention / fourth-wall break = 0.

THE BRIEF (for context — do not score the brief):
  friend          : {friend}
  pillar          : {pillar}
  calendar_event  : {event}
  currency        : {currency}
  target_duration : {duration}s  (≈ {target_words} words at 2.5 wps)
  enemy           : {enemy}
  director_note   : {director_note}

THE SCRIPT
{script}

Return STRICT JSON, no markdown:
{{
  "sensory": 0,
  "recognition": 0,
  "spine": 0,
  "enemy": 0,
  "transformation": 0,
  "bella": 0,
  "ciao": 0,
  "elixir": 0,
  "zero_sell": 0,
  "weighted_total": 0.0,
  "weak_dimensions": ["...", "..."],
  "best_line": "...",
  "rewrite_note": "the single most useful instruction for a rewrite"
}}
"""


def _weighted_total(scores: dict) -> float:
    total = 0.0
    for k, w in brand.SCORING_WEIGHTS.items():
        v = scores.get(k)
        if isinstance(v, (int, float)):
            total += float(v) * w
    return round(total, 3)


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0]
    elif raw.startswith("```"):
        raw = raw.split("```", 2)[1].split("```", 1)[0]
    raw = raw.strip()
    start = raw.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start:i + 1])
    raise ValueError("unbalanced JSON braces")


def _self_grade_call(writer_fn: Callable[[str], str], grade_prompt: str) -> dict:
    """
    Use the SAME writer model to self-grade. We re-use the writer callable so
    each writer self-grades with its own voice — that is the spec.
    """
    raw = writer_fn(grade_prompt)
    return _extract_json(raw)


def _rewrite_weak_dims(
    writer_fn: Callable[[str], str],
    script: str,
    brief: dict,
    weak_dims: list[str],
) -> str:
    """Targeted rewrite of the weakest dimensions only — preserve everything else."""
    # Slot-aware duration fallback — never hardcode 18s (old pre-alignment default).
    slot       = (brief.get("format") or "reel").lower()
    slot_band  = brand.SLOT_DURATION.get(slot, brand.SLOT_DURATION["reel"])
    target_dur = int(brief.get("target_duration_seconds") or slot_band["target"])
    weak_summary = ", ".join(weak_dims[:2]) or "(none)"
    prompt = f"""You are revising a Bella story script. Lift these dimensions ONLY: {weak_summary}.
Preserve every other dimension exactly — same SECTION 1/2/3/4 headers, same hero,
sensory hook, currency ({brief.get('currency','$')}), and target duration ({target_dur}s).

If a sentence is fine, leave it alone. Output the FULL revised script with all four
SECTION headers intact and no commentary.

ORIGINAL:
{script}
"""
    revised = writer_fn(prompt)
    if all(f"SECTION {n}" in revised for n in (1, 2, 3, 4)):
        return revised
    return script  # malformed → keep original


def self_grade(
    writer_fn: Callable[[str], str],
    script: str,
    brief: dict,
) -> SelfGradeResult:
    """
    Score → if below threshold and attempts remain, rewrite the 2 weakest dims
    and re-grade. Submits the best-ever version after at most 3 attempts.
    """
    # Slot-aware duration fallback — never hardcode 18s (old pre-alignment default).
    slot         = (brief.get("format") or "reel").lower()
    slot_band    = brand.SLOT_DURATION.get(slot, brand.SLOT_DURATION["reel"])
    target_dur   = int(brief.get("target_duration_seconds") or slot_band["target"])
    target_words = int(target_dur * 2.5)

    best_script = script
    best_score  = -1.0
    best_dims: dict = {}
    best_weak: list[str] = []
    attempts = 0

    current = script
    for attempt in range(1, SELF_GRADE_MAX_ATTEMPTS + 1):
        attempts = attempt
        grade_prompt = SELF_GRADE_PROMPT.format(
            friend        = brief.get("friend", "?"),
            pillar        = brief.get("pillar", "?"),
            event         = brief.get("calendar_event", "(none)"),
            currency      = brief.get("currency", "$"),
            duration      = target_dur,
            target_words  = target_words,
            enemy         = brief.get("enemy", ""),
            director_note = brief.get("director_note", ""),
            script        = current,
        )
        try:
            scores = _self_grade_call(writer_fn, grade_prompt)
        except Exception as e:
            print(f"    [self-grade] parse failed attempt {attempt}: {e}")
            break

        # Binary zero-sell: any pitch zeroes out the dimension AND the total.
        if isinstance(scores.get("zero_sell"), (int, float)) and scores["zero_sell"] == 0:
            total = 0.0
        else:
            total = float(scores.get("weighted_total") or _weighted_total(scores))
        weak = list(scores.get("weak_dimensions") or [])

        if total > best_score:
            best_script, best_score, best_dims, best_weak = current, total, scores, weak

        if total >= brand.PASS_THRESHOLD:
            break

        if attempt < SELF_GRADE_MAX_ATTEMPTS:
            try:
                current = _rewrite_weak_dims(writer_fn, current, brief, weak)
            except Exception as e:
                print(f"    [self-grade] rewrite failed attempt {attempt}: {e}")
                break

    return SelfGradeResult(
        script           = best_script,
        score            = max(best_score, 0.0),
        passed           = best_score >= brand.PASS_THRESHOLD,
        attempts         = attempts,
        dimension_scores = best_dims,
        weak_dimensions  = best_weak,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# WRITER ORCHESTRATION (Agents 4A-D in parallel)
# ═══════════════════════════════════════════════════════════════════════════════

def _writer_with_self_grade(
    writer_fn: Callable[[str], str],
    prompt: str,
    brief: dict,
) -> SelfGradeResult:
    raw = writer_fn(prompt)
    return self_grade(writer_fn, raw, brief)


def _select_writer_tasks(round_num: int, use_fallback: bool) -> list[tuple[str, Callable[[str], str], str]]:
    """
    Return [(name, fn, blind_label)] for the current round.

    Strategies:
      lean_daily (default):
        Round 1: Claude only
        Round 2: Claude + GPT-4o
        Round 3+: Claude + GPT-4o + Gemini (if available) + DeepSeek fallback

      balanced:
        Round 1+: Claude + GPT-4o
        Round 2+: + Gemini
        Round 3+: + DeepSeek fallback

      legacy_parallel:
        Round 1+: Claude + GPT-4o + Gemini (if available)
        Round 3+: + DeepSeek fallback
    """
    label_iter = iter(("A", "B", "C", "D"))
    tasks: list[tuple[str, Callable[[str], str], str]] = []

    def add(name: str, fn: Callable[[str], str], enabled: bool) -> None:
        if enabled:
            tasks.append((name, fn, next(label_iter)))

    strategy = WRITER_STRATEGY or "lean_daily"

    if strategy == "legacy_parallel":
        add("claude", _claude, anthropic_client is not None)
        add("gpt4o", _gpt4o, openai_client is not None)
        add("gemini", _gemini, _get_gemini() is not None)
    elif strategy == "balanced":
        add("claude", _claude, anthropic_client is not None)
        add("gpt4o", _gpt4o, openai_client is not None)
        add("gemini", _gemini, round_num >= 2 and _get_gemini() is not None)
    else:
        # lean_daily
        add("claude", _claude, anthropic_client is not None)
        add("gpt4o", _gpt4o, round_num >= 2 and openai_client is not None)
        add("gemini", _gemini, round_num >= 3 and _get_gemini() is not None)

    if deepseek_client and use_fallback:
        add("deepseek", _deepseek, True)

    return tasks


def generate_scripts_parallel(
    brief: dict,
    prompt: str,
    use_fallback: bool = False,
    round_num: int = 1,
) -> tuple[dict, dict]:
    """
    Run configured writers in parallel. Each writer:
      1. drafts the script
      2. self-grades + rewrites weakest dims (up to 3 attempts)
      3. submits the best-ever version

    Returns (scripts, self_grades) keyed by blind label A/B/C/D.

    Writer pool strategy is selected by BELLA_WRITER_STRATEGY.
    Default `lean_daily` matches the canonical daily contract (Master Bible
    v2 §11): 1 Reel + 1 Story + 1 YouTube reuse package per day:
      - 1 Reel + 1 Story per day (the two generated slots)
      - YT reuses the Reel content (packaging only — title/description/thumb)
      - Round 1 stays lean, broader competition happens only on escalation
      - The "60–90 pieces/month" volume model and the v3 triplet are non-default
    """
    tasks = _select_writer_tasks(round_num, use_fallback)

    if not tasks:
        raise RuntimeError(
            "No writers configured for the current strategy. Set ANTHROPIC_API_KEY and/or "
            "OPENAI_API_KEY. DEEPSEEK_API_KEY is fallback-only."
        )

    scripts: dict = {}
    grades:  dict = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futs = {
            ex.submit(_writer_with_self_grade, fn, prompt, brief): (name, label)
            for name, fn, label in tasks
        }
        for fut in concurrent.futures.as_completed(futs, timeout=300):
            name, label = futs[fut]
            try:
                result: SelfGradeResult = fut.result()
                scripts[label] = result.script
                grades[label]  = result.to_dict()
                print(f"    Writer {label} ({name}): self-grade {result.score:.2f} "
                      f"after {result.attempts} attempt(s)", flush=True)
            except Exception as e:
                print(f"    Writer {label} ({name}): FAILED — {type(e).__name__}: {str(e)[:80]}",
                      flush=True)

    if not scripts:
        raise RuntimeError("All writers failed — no scripts to judge")
    return scripts, grades


# ═══════════════════════════════════════════════════════════════════════════════
# JUDGE (Agent 6)
# ═══════════════════════════════════════════════════════════════════════════════

JUDGE_SYSTEM = """You are the Judge for the Bellaciao content engine. Score blindly.
You see scripts labelled A/B/C/D — model identities are hidden.

THE STANDARD: a restaurant owner reads this at midnight, feels completely seen,
and shares it with their partner without saying anything.
"""

JUDGE_PROMPT_TEMPLATE = """Score every script on the 9-dimension WEIGHTED rubric:

  sensory        (25%) — scroll-stop strength: Bella-spoken hook lands in first 3 seconds, archetype-aligned (Pain/Insider/Myth-Buster), uses the friend's locked hook verbatim. Hook zone (0-5s) MAY acknowledge AI and name automation.
  recognition    (20%) — emotional 'that's me' moment for a real owner
  spine          (15%) — Pixar Spine momentum, each beat earns the next
  enemy          (10%) — Shadow named and present in Act 2
  transformation (10%) — Vogler inner change in the hero
  bella          (5%)  — Bella ALWAYS physically on screen + witnesses without dominating. Both halves required.
  ciao           (5%)  — Ciao REQUIRED by default; marks the turning point ONCE. Score 0 if absent unless brief.ciao_allowed_absent=true.
  elixir         (10%) — small, human, earned — NEVER a product or forbidden ending
  zero_sell      (5%)  — BINARY. Pitch/fourth-wall-break in BODY or ELIXIR = 0. Hook zone (0-5s) is EXEMPT — Bella may name automation there.

CONTEXT (do not score the brief):
  friend         : {friend}
  pillar         : {pillar}
  calendar_event : {event}
  currency       : {currency}
  enemy          : {enemy}

SCRIPTS:
{script_blocks}

Return STRICT JSON, no markdown:
{{
  "scores": {{
{score_template}
  }},
  "winner": "A|B|C|D",
  "best_weighted_score": 0.0,
  "weak_dimensions": ["dim1", "dim2"],
  "rationale": {{ "A": "...", "B": "...", "C": "...", "D": "..." }},
  "zero_sell_triggered": false,
  "disqualified": []
}}
"""


def judge_scripts(scripts: dict, brief: dict, self_grades: dict | None = None) -> JudgeVerdict:
    if len(scripts) < 2:
        # Single-model mode: synthesise a verdict from the only script.
        only_label = next(iter(scripts))
        only_script = scripts[only_label]
        sg = (self_grades or {}).get(only_label, {})
        score = float(sg.get("score") or 0.0)
        print("    [judge] skipped Opus blind-judge — single-writer round", flush=True)
        return JudgeVerdict(
            winner               = only_label,
            scores               = {only_label: sg.get("dimension_scores") or {}},
            rationale            = {only_label: "single-model run, no competition"},
            weak_dimensions      = list(sg.get("weak_dimensions") or []),
            best_script          = only_script,
            best_weighted_score  = score,
            scripts              = dict(scripts),
            self_grades          = dict(self_grades or {}),
        )

    if anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY required for the judge")

    score_template = ",\n".join(
        f'    "{label}": {{ "sensory":0,"recognition":0,"spine":0,"enemy":0,'
        f'"transformation":0,"bella":0,"ciao":0,"elixir":0,"zero_sell":0,'
        f'"weighted_total":0.0 }}'
        for label in scripts
    )
    script_blocks = "\n\n".join(
        f"{'='*60}\nSCRIPT {label}\n{'='*60}\n{content}"
        for label, content in scripts.items()
    )

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        friend        = brief.get("friend", "?"),
        pillar        = brief.get("pillar", "?"),
        event         = brief.get("calendar_event", "(none)"),
        currency      = brief.get("currency", "$"),
        enemy         = brief.get("enemy", ""),
        script_blocks = script_blocks,
        score_template= score_template,
    )

    try:
        require_host("api.anthropic.com", "Anthropic")
        r = anthropic_client.messages.create(
            model=MODEL_CLAUDE_JUDGE,
            max_tokens=3000,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        verdict_raw = _extract_json(r.content[0].text)
    except Exception as e:
        print(f"    [judge] parse failed: {e} — falling back to highest self-grade")
        # Fallback: pick the best self-graded script
        best_label = max(
            scripts.keys(),
            key=lambda lab: float((self_grades or {}).get(lab, {}).get("score") or 0),
        )
        sg = (self_grades or {}).get(best_label, {})
        return JudgeVerdict(
            winner               = best_label,
            scores               = {best_label: sg.get("dimension_scores") or {}},
            rationale            = {best_label: f"judge fallback: {e}"},
            weak_dimensions      = list(sg.get("weak_dimensions") or []),
            best_script          = scripts[best_label],
            best_weighted_score  = float(sg.get("score") or 0.0),
            scripts              = dict(scripts),
            self_grades          = dict(self_grades or {}),
        )

    # Normalise: compute weighted_total per label if Opus omitted it
    norm_scores = verdict_raw.get("scores", {}) or {}
    for dim in norm_scores.values():
        if "weighted_total" not in dim or not isinstance(dim["weighted_total"], (int, float)):
            dim["weighted_total"] = _weighted_total(dim)

    winner = verdict_raw.get("winner") or max(
        norm_scores.keys(),
        key=lambda lab: float(norm_scores[lab].get("weighted_total") or 0),
        default=next(iter(scripts)),
    )
    best_score = float(verdict_raw.get("best_weighted_score") or
                       norm_scores.get(winner, {}).get("weighted_total") or 0.0)

    return JudgeVerdict(
        winner               = winner,
        scores               = norm_scores,
        rationale            = verdict_raw.get("rationale") or {},
        weak_dimensions      = list(verdict_raw.get("weak_dimensions") or []),
        best_script          = scripts.get(winner, ""),
        best_weighted_score  = best_score,
        zero_sell_triggered  = bool(verdict_raw.get("zero_sell_triggered")),
        disqualified         = list(verdict_raw.get("disqualified") or []),
        scripts              = dict(scripts),
        self_grades          = dict(self_grades or {}),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION EXTRACTION (used by run.py to populate the job file)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_section(text: str, label: str) -> str:
    if label not in text:
        return ""
    lines, in_sec, out = text.split("\n"), False, []
    for line in lines:
        if label in line:
            in_sec = True
            continue
        if in_sec and line.startswith("SECTION ") and label not in line:
            break
        if in_sec:
            out.append(line)
    return "\n".join(out).strip()


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE-AND-JUDGE — single round (called by run.py orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

def write_and_judge(
    brief: dict,
    rewrite_notes: str = "",
    round_num: int = 1,
) -> JudgeVerdict:
    """
    One full round: build prompt → parallel writers (with self-grade) → judge.
    The orchestrator calls this once per round; the Quality Supervisor decides
    whether to call it again with rewrite feedback.

    Writer pool strategy:
      Default (`BELLA_WRITER_STRATEGY=lean_daily`):
        Round 1 : Claude only
        Round 2 : Claude + GPT-4o
        Round 3+: Claude + GPT-4o + Gemini (if available) + DeepSeek fallback

      This is intentional: the daily channel model now prioritises one strong
      Reel master and one Story derivative, with YouTube reusing the Reel's
      core content. Broader model competition is escalation, not the default.
    """
    prompt = build_generation_prompt(brief, rewrite_notes, round_num)
    # Escalate to DeepSeek fallback from round 3 onwards (scores haven't hit 9.5).
    use_fallback = (round_num >= 3)
    try:
        scripts, grades = generate_scripts_parallel(
            brief,
            prompt,
            use_fallback=use_fallback,
            round_num=round_num,
        )
    except RuntimeError as e:
        # Primary writers all failed — retry with DeepSeek as emergency fallback
        if "No primary writers" not in str(e) and not use_fallback:
            print(f"    [writer-pool] primary writers failed — escalating to DeepSeek fallback")
            scripts, grades = generate_scripts_parallel(
                brief,
                prompt,
                use_fallback=True,
                round_num=round_num,
            )
        else:
            raise
    return judge_scripts(scripts, brief, grades)
