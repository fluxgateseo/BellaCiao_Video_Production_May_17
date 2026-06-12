"""
strategy.py — Agent 3: Strategy Director.

Decides WHAT to write next: pillar, enemy, ally, duration, tone, sensory hook,
and director note. Calendar-first, trend-informed, memory-aware.

In v1.2 the strategy director receives a `GateResult` from Agent 2 (the
Logical Gate) as a HARD CONSTRAINT and is not allowed to override the city,
friend, or currency. The sensory hook is RETRIEVED from friends_db.json — never
invented.

Output: a brief dict, also persisted to data/strategy_brief.json.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

import brand
import assets
from network_probe import require_host
from logical_gate import GateResult

# API keys are loaded from the shared Bellaciao Content/.env (parent folder),
# so every project under Bellaciao Content/ uses the same credentials file.
load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR       = Path(__file__).parent
FRIENDS_DB     = BASE_DIR / "data" / "friends_db.json"
CALENDAR_FILE  = BASE_DIR / "data" / "calendar.json"
BRIEF_FILE     = BASE_DIR / "data" / "strategy_brief.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

MODEL_OPUS = "claude-opus-4-6"


# ─── friends_db loader (v2.0 schema, with v1 fallback) ───────────────────────

def _load_friends() -> list[dict]:
    if not FRIENDS_DB.exists():
        # Fallback: legacy data/friends.json
        legacy = BASE_DIR / "data" / "friends.json"
        if legacy.exists():
            raw = json.loads(legacy.read_text())
            return raw if isinstance(raw, list) else raw.get("friends", []) or []
        raise FileNotFoundError(f"friends_db.json not found at {FRIENDS_DB}")
    raw = json.loads(FRIENDS_DB.read_text())
    if isinstance(raw, dict):
        return raw.get("friends", []) or []
    if isinstance(raw, list):
        return raw
    return []


def get_friend(friend_id: str) -> dict:
    for f in _load_friends():
        if f.get("id") == friend_id:
            return f
    raise ValueError(f"Friend '{friend_id}' not found")


# ─── Calendar helpers (kept here so apify_scout can still import this) ──────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> Optional[date]:
    try:
        count, d = 0, date(year, month, 1)
        while d.month == month:
            if d.weekday() == weekday:
                count += 1
                if count == n:
                    return d
            d += timedelta(days=1)
    except Exception:
        pass
    return None


def _next_occurrence(event: dict, today: date) -> Optional[date]:
    try:
        etype = event.get("type", "fixed")
        if etype == "fixed":
            cand = date(today.year, event["month"], event["day"])
            if cand < today:
                cand = date(today.year + 1, event["month"], event["day"])
            return cand
        if etype == "nth_weekday":
            for y in (today.year, today.year + 1):
                d = _nth_weekday_of_month(y, event["month"], event["weekday"], event["n"])
                if d and d >= today:
                    return d
        if etype == "cultural":
            days = (event["weekday"] - today.weekday()) % 7
            return today + timedelta(days=days)
    except Exception:
        pass
    return None


def upcoming_events(days_ahead: int = 30) -> list:
    if not CALENDAR_FILE.exists():
        return []
    events = json.loads(CALENDAR_FILE.read_text()).get("events", [])
    today, out = date.today(), []
    for e in events:
        nxt = _next_occurrence(e, today)
        if not nxt:
            continue
        days_until = (nxt - today).days
        if 0 <= days_until <= days_ahead:
            enriched = dict(e)
            enriched["days_until"] = days_until
            enriched["next_date"]  = nxt.isoformat()
            enriched.setdefault("id", _slug(e.get("name", "")))
            out.append(enriched)
    out.sort(key=lambda e: e["days_until"])
    return out


def _format_events(events: list) -> str:
    if not events:
        return "No major events in the next 30 days."
    tiers = {1: "TIER 1", 2: "TIER 2", 3: "TIER 3"}
    lines = []
    for e in events[:8]:
        tier = e.get("revenue_tier", 3)
        lines.append(
            f"  [{tiers.get(tier, 'TIER 3')}] {e['name']} "
            f"(in {e['days_until']}d, {', '.join(e.get('countries', []))}) — "
            f"{e.get('storytelling_hook', '')[:120]}"
        )
    return "\n".join(lines)


# ─── Sensory-hook retrieval (NEVER invented) ─────────────────────────────────

def _pick_sensory_hook(friend: dict, mandatory_event_id: Optional[str]) -> tuple[str, int]:
    """
    Return (hook, index) from the friend's sensory_hooks array.
    Index 0 is the canonical default; if the calendar event matches the friend's
    real_events, we shift to a stable position so the same event doesn't always
    surface the same hook.
    """
    hooks = friend.get("sensory_hooks") or []
    if not hooks:
        legacy = friend.get("sensory_food_hook")
        return (legacy or "", 0) if legacy else ("", 0)

    if mandatory_event_id and mandatory_event_id in (friend.get("real_events") or []):
        idx = (friend.get("real_events", []).index(mandatory_event_id)) % len(hooks)
        return hooks[idx], idx
    return hooks[0], 0


# ─── Brief generation ────────────────────────────────────────────────────────

def _format_friend_for_prompt(f: dict) -> str:
    return (
        f"  - id={f['id']} | {f.get('name','')} | "
        f"{f.get('cuisine', f.get('restaurant_style',''))} @ "
        f"{f.get('restaurant_name', f.get('fantasy_restaurant_name',''))}, "
        f"{f.get('neighbourhood','')}, {f.get('city', f.get('location',''))} | "
        f"enemy: {f.get('enemy_archetype','')}"
    )


def _mode_directive(mode: str, gate: GateResult) -> str:
    """One-paragraph directive for the strategy director, depending on cadence mode."""
    if mode == "event_day":
        return (
            f"MODE: EVENT_DAY — today the script publishes is {gate.target_date}, "
            f"which IS the day of {gate.mandatory_event}. The story MUST anchor "
            f"on this event. Use the friend's `event_failure_modes[{gate.mandatory_event}]` "
            f"to sharpen Act 2."
        )
    if mode == "event_eve":
        return (
            f"MODE: EVENT_EVE — the script publishes on {gate.target_date}, the day "
            f"BEFORE {gate.mandatory_event}. Frame it as the calm before the storm: "
            f"the friend's quiet prep moment, the operational tension building, the "
            f"thing that always goes wrong on event day if you don't fix it tonight."
        )
    return (
        "MODE: GENERIC — no Tier-1 calendar event today or tomorrow. Write a "
        "friend-driven story rooted in real life on the friend's street. The "
        "real-world anchor is the neighbourhood itself, a specific operational "
        "detail from the friend's profile, or the Pillar theme. DO NOT "
        "fabricate a calendar event."
    )


def _build_director_prompt(
    gate: GateResult,
    friend: dict,
    upcoming: list,
    trend_context: str,
    memory_context: str,
    continuity_context: str,
    sensory_hook: str,
    format_type: str,
    pillar_hint: Optional[int],
    rewrite_feedback: str = "",
    locked_hook: Optional[dict] = None,
    locked_story_seed: Optional[str] = None,
) -> str:
    mode_directive = _mode_directive(gate.mode, gate)

    # Rewrite-loop feedback block — only present when the user has marked a
    # previous version of this brief as verdict=rewrite_needed and written
    # notes about what to change. Drives the regeneration loop.
    rewrite_block = ""
    if rewrite_feedback:
        rewrite_block = (
            "\n## REWRITE NOTES — read this FIRST\n"
            "The user reviewed a previous version of this brief and asked for "
            "specific changes. Address every point. Do not produce the same "
            "angle as before. The director_note in the JSON output should "
            "explicitly call out what you changed in response.\n\n"
            f"USER FEEDBACK:\n{rewrite_feedback}\n"
        )

    # Locked hook block — the user picked one of the 3 hook options in
    # ContentCalendar; that hook MUST be the Section 2 opener verbatim.
    hook_block = ""
    if locked_hook and locked_hook.get("text"):
        hook_block = (
            "\n## LOCKED HOOK — Section 2 opener (DO NOT CHANGE)\n"
            f"The user has selected this scroll-stop hook from the Bella Hooks library "
            f"(hook #{locked_hook.get('id', '?')}, doctrine: {locked_hook.get('doctrine', '?')}). "
            f"This is the FIRST SPOKEN LINE of Section 2. Do NOT paraphrase. Do NOT shorten. "
            f"The rest of the script must deliver on the promise this hook makes.\n\n"
            f'LOCKED HOOK: "{locked_hook["text"]}"\n'
        )

    # Locked story seed block — the user picked one of the 3 story angles in
    # ContentCalendar (operational / personal / sensory). The brief must build
    # the story around THIS angle. The hook opens; the seed sets the body.
    seed_block = ""
    if locked_story_seed:
        seed_block = (
            "\n## LOCKED STORY DIRECTION (user-chosen angle)\n"
            "The user reviewed 3 story angles in the ContentCalendar table and "
            "picked the one below. Build the brief AROUND this angle. The enemy, "
            "ally, tone, and director_note should all reinforce it. Do NOT pivot "
            "to a different angle even if it scores higher in your judgement — "
            "the user has already made the editorial call.\n\n"
            f'LOCKED STORY DIRECTION: "{locked_story_seed}"\n'
        )

    # In generic mode the calendar_event field is left blank.
    calendar_event_default  = gate.mandatory_event or ""
    calendar_event_required = gate.mode != "generic"
    calendar_event_rule = (
        "REQUIRED — must match mandatory_event"
        if calendar_event_required
        else 'leave as empty string ""'
    )

    # Slot-aware spec injection — story or reel get different structural rules.
    slot_spec = brand.SLOT_SPEC.get(format_type, brand.REEL_SPEC)
    slot_band = brand.SLOT_DURATION.get(format_type, brand.SLOT_DURATION["reel"])
    slot_target_default = slot_band["target"]

    return f"""You are the Strategy Director for the Bellaciao content engine.
You receive HARD CONSTRAINTS from the Logical Gate. You MUST NOT change the
city, friend, or currency. You decide pillar (if not pre-set), enemy, ally,
tone, target duration, and the director note.
{hook_block}{seed_block}{rewrite_block}
## MISSION
{brand.MISSION}

## SLOT — THIS BRIEF IS FOR A {format_type.upper()}
{slot_spec}

## DURATION GUIDE (whole project)
{brand.DURATION_GUIDE}

## EDITORIAL MODE
{mode_directive}

## HARD CONSTRAINTS (from Logical Gate)
  target_date     : {gate.target_date}
  market          : {gate.market}
  city            : {gate.city}
  friend          : {gate.friend_id} ({gate.friend_name})
  neighbourhood   : {gate.neighbourhood}
  street_detail   : {gate.street_detail}
  currency        : {gate.currency}        ← NEVER change
  mandatory_event : {gate.mandatory_event or "(none — generic mode)"}
  days_until      : {gate.days_until_mandatory}
  enemy_archetype : {gate.enemy_archetype}

## BELLA-SPOKEN HOOK (user-chosen in Airtable ContentCalendar — DO NOT change)
  BELLA delivers this line direct-to-camera as the opener, 0-3s.
  Archetype: Pain / Insider / Myth-Buster (hook zone may acknowledge AI).
  "{sensory_hook}"

## FRIEND DETAIL
{_format_friend_for_prompt(friend)}
  before: {friend.get('before_bella', {}).get('operational', '(unknown)')}
  after : {friend.get('after_bella', {}).get('operational', '(unknown)')}

## UPCOMING CALENDAR (next 30 days — context only, do not anchor on these in generic mode)
{_format_events(upcoming)}

## TREND CONTEXT (Apify creator-content signals)
{trend_context}

## MEMORY CONTEXT (mechanical cooldowns — advisory)
{memory_context or "(empty)"}

## NARRATIVE CONTINUITY (serialised arc — where this friend is right now)
{continuity_context or "(no prior state — this is the first episode for this friend)"}

## ENEMIES
{json.dumps(brand.ENEMIES, indent=2)}

## ALLIES
{json.dumps(brand.ALLIES, indent=2)}

## PILLARS
{json.dumps(brand.PILLARS, indent=2)}

## CONSTRAINTS
- format (slot)  : {format_type}    ← {format_type} band: {slot_band["min"]}-{slot_band["max"]}s, target ~{slot_band["target"]}s
- pillar_hint    : {pillar_hint or "(choose)"}
- enemy must be drawn from the ENEMIES dict above
- ally must be drawn from the ALLIES dict above
- calendar_event field: {calendar_event_rule}
- target_duration_seconds MUST fall inside the {format_type} band ({slot_band["min"]}-{slot_band["max"]}s).
  Stories under-fill the band only if the beat is genuinely small. Reels NEVER come in under {slot_band["min"]}s.

## YOUR TASK
Output ONE brief as STRICT JSON, no markdown, no explanation. Use the pillar_hint above for the "pillar" field — do NOT default to 1:
{{
  "format": "{format_type}",
  "pillar": {pillar_hint if pillar_hint else 1},
  "mode": "{gate.mode}",
  "calendar_event": "{calendar_event_default}",
  "calendar_days_until": {gate.days_until_mandatory if gate.days_until_mandatory is not None else 0},
  "friend": "{gate.friend_id}",
  "city": "{gate.city}",
  "market": "{gate.market}",
  "currency": "{gate.currency}",
  "enemy": "enemy_key_from_dict",
  "enemy_failure_mode": "the specific event_failure_mode for this friend + event, or a general failure mode in generic mode",
  "ally": "ally_key_from_dict",
  "tone": "warm_and_real | funny_and_painful | quietly_proud | late_night_honest",
  "target_duration_seconds": {slot_target_default},
  "duration_rationale": "one sentence on why",
  "sensory_hook": "{sensory_hook}",
  "sensory_hook_index": 0,
  "trend_anchor": "what the script is anchored on (event in event mode, neighbourhood + operational detail in generic mode)",
  "director_note": "one sentence — the single most important thing the writer must nail",
  "scenario_tags": ["2-3 short kebab-case tags naming the narrative beat (e.g. 'empty-friday-night', 'lease-notice-11pm', 'sous-chef-stayed-late'). These are scene-level, not theme-level. Used by the memory system to avoid repeating scenarios. Look at the 'Recent scenario tags' line in MEMORY CONTEXT — do NOT reuse any tag listed there."]
}}
"""


def generate_brief(
    gate_result: GateResult,
    format_type: str = "reel",
    pillar: Optional[int] = None,
    rewrite_feedback: str = "",
    locked_hook: Optional[dict] = None,
    locked_story_seed: Optional[str] = None,
    locked_sensory_hook: Optional[str] = None,
) -> dict:
    """
    Build a brief, anchored to the Logical Gate's hard constraints.
    Saves to data/strategy_brief.json and returns the dict.
    """
    friends = _load_friends()
    friend  = next((f for f in friends if f.get("id") == gate_result.friend_id), None)
    if not friend:
        raise ValueError(f"gate friend {gate_result.friend_id} not found in friends_db.json")

    upcoming = upcoming_events(days_ahead=30)

    # Sensory hook from friends_db (never invented).
    # If the user picked one in ContentCalendar's sensory_hook_choice, that
    # overrides the auto-pick.
    mandatory_id = None
    if gate_result.mandatory_event:
        mandatory_id = _slug(gate_result.mandatory_event)
        # also try matching against the friend's real_events list
        for ev_id in friend.get("real_events", []):
            if ev_id in mandatory_id or mandatory_id in ev_id:
                mandatory_id = ev_id
                break
    if locked_sensory_hook:
        sensory_hook = locked_sensory_hook
        # Look up the index in the friend's array (best effort) for traceability
        try:
            sensory_idx = (friend.get("sensory_hooks") or []).index(locked_sensory_hook)
        except ValueError:
            sensory_idx = -1   # not from this friend's array (rare — manual edit)
    else:
        sensory_hook, sensory_idx = _pick_sensory_hook(friend, mandatory_id)

    # Optional trend context (Apify creator-content scraping)
    try:
        from apify_scout import get_trend_context
        trend_context = get_trend_context()
    except Exception:
        trend_context = "No trend data available."

    # Memory context
    try:
        import memory as memory_mod
        memory_context = memory_mod.get_memory_context(memory_mod.load_memory())
    except Exception:
        memory_context = ""

    # Narrative continuity — per-friend arc state accumulated across all
    # previously-approved episodes. Empty string if this friend has no state
    # yet (first episode, or manually reset via `continuity.py --reset`).
    try:
        import continuity
        continuity_context = continuity.get_continuity_context(gate_result.friend_id)
    except Exception as e:
        print(f"[strategy] continuity context skipped: {e}")
        continuity_context = ""

    # Build the prompt and call the director (Opus)
    prompt = _build_director_prompt(
        gate=gate_result,
        friend=friend,
        upcoming=upcoming,
        trend_context=trend_context,
        memory_context=memory_context,
        continuity_context=continuity_context,
        sensory_hook=sensory_hook,
        format_type=format_type,
        pillar_hint=pillar,
        rewrite_feedback=rewrite_feedback,
        locked_hook=locked_hook,
        locked_story_seed=locked_story_seed,
    )

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY required for the strategy director")

    require_host("api.anthropic.com", "Anthropic")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=MODEL_OPUS,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    brief = json.loads(raw)

    # Re-impose hard constraints (defence in depth — director cannot drift)
    brief["friend"]   = gate_result.friend_id
    brief["city"]     = gate_result.city
    brief["market"]   = gate_result.market
    brief["currency"] = gate_result.currency
    brief["mode"]     = gate_result.mode
    # v1.8+: pillar_hint from ContentCalendar's pillar_choice is authoritative
    # if provided — stamp it so the LLM can't drift off the archetype mapping.
    if pillar is not None:
        brief["pillar"] = int(pillar)

    # Stamp the locked hook on the brief — engine.py reads this for the writer prompt
    if locked_hook and locked_hook.get("text"):
        brief["chosen_hook_id"]       = int(locked_hook.get("id") or 0)
        brief["chosen_hook_text"]     = locked_hook["text"]
        brief["chosen_hook_doctrine"] = locked_hook.get("doctrine", "")
    brief["sensory_hook"]       = sensory_hook
    brief["sensory_hook_index"] = sensory_idx

    # In generic mode, force calendar_event to empty so writers don't fabricate one
    if gate_result.mode == "generic":
        brief["calendar_event"]      = ""
        brief["calendar_days_until"] = 0
    else:
        brief["calendar_event"]      = gate_result.mandatory_event or ""
        brief["calendar_days_until"] = gate_result.days_until_mandatory or 0

    # Pull friend-specific failure mode for the chosen event when available
    if mandatory_id:
        fm = (friend.get("event_failure_modes") or {}).get(mandatory_id)
        if fm and not brief.get("enemy_failure_mode"):
            brief["enemy_failure_mode"] = fm

    # Avatar bundle — flows through to scene_brief in the job file
    brief["avatars"] = assets.avatar_bundle(gate_result.friend_id)

    BRIEF_FILE.parent.mkdir(parents=True, exist_ok=True)
    BRIEF_FILE.write_text(json.dumps(brief, indent=2))
    print(f"[strategy] brief → {BRIEF_FILE.name}  "
          f"({brief.get('friend')}/p{brief.get('pillar')}/{brief.get('target_duration_seconds')}s)")
    return brief


# ─── CLI (manual run for debugging) ─────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from logical_gate import run_gate

    p = argparse.ArgumentParser()
    p.add_argument("--format", choices=["reel", "story"], default="reel")
    p.add_argument("--pillar", type=int, choices=[1, 2, 3, 4, 5])
    p.add_argument("--friend", help="force friend id")
    args = p.parse_args()

    gate = run_gate(args.format, args.pillar, args.friend)
    brief = generate_brief(gate, args.format, args.pillar)
    print(json.dumps(brief, indent=2))
