"""
hooks_library.py — load + rotate Bella's scroll-stop hooks.

The XLSX-sourced hook library (data/bella_hooks.json, written by hooks_sync.py)
is read here and exposed via:

    load_hooks()                     → list[dict]
    pick_three_hooks(...)            → 3 hooks for a (friend, market, slot, day) cell
    rotation_state_from_history(...) → dict tracking what's been used

Rotation rules (from the "How To Use" sheet of Bella_Shorts_Hooks.xlsx):

  1. Avoid running two hooks of the same Doctrine Type back-to-back.
  2. Mix Real Event hooks and Friend Cold Opens across the week.
  3. Stories prefer Doctrine Types 1 (Callout — sensory) and 7 (Friend Cold Open).
  4. Reels rotate all 7 doctrine types over time.
  5. Friend-specific hooks beat 'any' hooks for the same friend.
  6. Friends with NO specific hooks (currently arun_priya, sophie) fall back to 'any'.
  7. Hook cooldown: same hook id should not appear within 7 days of itself.

The brief stage reads the chosen hook from a ContentCalendar row's hook_choice
field and passes it to strategy.py as a locked Section 2 opener.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE_DIR  = Path(__file__).parent
HOOKS_JSON = BASE_DIR / "data" / "bella_hooks.json"

# Doctrine types preferred per slot
STORY_PREFERRED_DOCTRINES = (
    "1 — Callout",          # sensory image + diagnosis = perfect story opener
    "7 — Friend Cold Open", # mid-conversation = perfect single-beat story
)
REEL_BLOCKED_DOCTRINES = ()  # reels can use anything

# Hook reuse cooldown — same hook id shouldn't appear within this many slots
HOOK_REUSE_COOLDOWN = 14   # 14 slots ≈ 7 days (28 slots / 14 days)

# ─── Archetype alignment (v1.8+ retention-first) ─────────────────────────────
# When pick_three_hooks is called with themes_for_positions, position N gets a
# hook whose doctrine matches archetype N. This keeps hook_1 / story_seed_1 /
# pillar_1 / sensory_hook_1 / text_overlay_1 / comment_bait_1 coherent across
# the row.
#
# The 3 archetypes mirror the seeds produced by content_calendar._story_seeds():
#   1 — pain        : named operational pain the restaurateur recognises instantly
#   2 — insider     : Bella acknowledges what SHE did (AI-transparent, quiet flex)
#   3 — myth_buster : contrarian reframe ("it's not X, it's Y")
THEME_DOCTRINE_MAP: dict[str, set[str]] = {
    "pain": {
        "3 — Specific Number",       # "The 47 missed calls on Monday morning"
        "6 — Real Event",            # grounded, named moment
    },
    "insider": {
        "1 — Callout",               # Bella's image + diagnosis
        "4 — POV Confession",        # first-person AI-transparent reveal
    },
    "myth_buster": {
        "2 — Counter-Intuitive Fact", # reframes received wisdom
        "5 — Uncomfortable Truth",    # contrarian, debate-inviting
        "7 — Friend Cold Open",       # drops audience into the restaurateur's POV
    },
}


# ─── Loading ─────────────────────────────────────────────────────────────────

def load_hooks() -> dict:
    """Read data/bella_hooks.json. Raises if missing — run hooks_sync.py first."""
    if not HOOKS_JSON.exists():
        raise FileNotFoundError(
            f"{HOOKS_JSON} missing — run `python3 hooks_sync.py` first to "
            f"convert Master Documents/Bella_Shorts_Hooks.xlsx to JSON."
        )
    return json.loads(HOOKS_JSON.read_text())


def all_hooks() -> list[dict]:
    return load_hooks().get("hooks") or []


# ─── Filtering ───────────────────────────────────────────────────────────────

def _hook_matches_friend(hook: dict, friend_id: str) -> bool:
    h_friend = hook.get("friend") or "any"
    if h_friend == "any":
        return True
    return h_friend == friend_id


def _hook_matches_market(hook: dict, market: str) -> bool:
    if not market:
        return True
    markets = hook.get("markets") or []
    return market in markets


def _candidates_for(friend_id: str, market: str) -> list[dict]:
    """All hooks that could match this friend/market, sorted friend-specific first."""
    hooks = all_hooks()
    matches = [h for h in hooks
               if _hook_matches_friend(h, friend_id)
               and _hook_matches_market(h, market)]
    # Friend-specific first, then 'any'
    matches.sort(key=lambda h: 0 if (h.get("friend") or "any") == friend_id else 1)
    return matches


# ─── Rotation state ───────────────────────────────────────────────────────

@dataclass
class RotationState:
    """Tracks what's been used across the planning window so we don't repeat."""
    used_hook_ids: list[int]              = field(default_factory=list)  # in publish order
    last_doctrine_types: list[str]        = field(default_factory=list)  # last 2 in publish order
    real_event_count: int                 = 0
    friend_cold_open_count: int           = 0

    def record(self, hook: dict) -> None:
        self.used_hook_ids.append(hook["id"])
        self.last_doctrine_types.append(hook.get("doctrine_type", ""))
        self.last_doctrine_types = self.last_doctrine_types[-2:]
        dt = hook.get("doctrine_type", "")
        if dt.startswith("6"):
            self.real_event_count += 1
        elif dt.startswith("7"):
            self.friend_cold_open_count += 1


# ─── Picking three hooks for a row ───────────────────────────────────────────

def pick_three_hooks(
    friend_id: str,
    market: str,
    slot: str,
    state: RotationState,
    mode: str = "generic",
    hard_exclude_ids: Optional[set[int]] = None,
    themes_for_positions: Optional[list[str]] = None,
    occurrence_idx: int = 0,
) -> list[dict]:
    """
    Return 3 distinct hooks for this (friend, market, slot, day) cell, ordered
    by preference. The user picks one in Airtable via hook_choice.

    Rules:
      - Friend-specific hooks first, then 'any' fallbacks.
      - Hard-exclude any id in `hard_exclude_ids` (used to prevent the reel
        slot from picking the same hooks as the day's story slot — within-day
        uniqueness is non-negotiable).
      - Skip hooks whose id has appeared in the last HOOK_REUSE_COOLDOWN slots
        (soft penalty).
      - Skip hooks whose doctrine_type matches the last picked one (back-to-back rule).
      - For story slots, prefer doctrine types in STORY_PREFERRED_DOCTRINES.
      - For event_day mode, weight Real Event hooks higher.
      - If we can't find 3 distinct hooks even after relaxing constraints,
        return whatever we have (may be fewer than 3).

    When `themes_for_positions` is provided (a list of 3 theme names from
    THEME_DOCTRINE_MAP), the function picks ONE hook per theme in position
    order. Position N gets the best-scoring hook whose doctrine_type matches
    THEME_DOCTRINE_MAP[themes_for_positions[N-1]]. If no themed candidate
    exists for a position, it falls back to the best-scoring unused candidate
    of any doctrine. This keeps hook_1 thematically aligned with story_seed_1,
    pillar_1, etc.
    """
    full_pool = _candidates_for(friend_id, market)
    if not full_pool:
        return []
    relaxed_exclude: set[int] = set()
    if hard_exclude_ids:
        candidates = [c for c in full_pool if c["id"] not in hard_exclude_ids]
        # Relax the hard exclusion if it leaves fewer than 3 candidates —
        # better to allow a within-day duplicate than to ship empty hook slots.
        # Friends with only 2 candidates total (sophie, arun_priya — XLSX gap)
        # hit this path; they get a soft penalty instead so the picker still
        # prefers a fresh hook over a re-used one when both are available.
        if len(candidates) < 3:
            candidates = full_pool
            relaxed_exclude = set(hard_exclude_ids)
    else:
        candidates = full_pool

    on_cooldown = set(state.used_hook_ids[-HOOK_REUSE_COOLDOWN:])

    def score(hook: dict) -> tuple:
        """Lower score = better fit. Sort ascending."""
        hid = hook["id"]
        dt  = hook.get("doctrine_type", "")
        h_friend = hook.get("friend") or "any"

        # 0. Within-day exclusion penalty (only fires when relaxation kicked in)
        #    — push previously-used hooks to the bottom so 'any' hooks beat them.
        within_day_score = 1 if hid in relaxed_exclude else 0

        # 1. Friend specificity (specific friend > any)
        friend_score = 0 if h_friend == friend_id else 1

        # 2. Cooldown penalty (used recently = worse)
        cooldown_score = 1 if hid in on_cooldown else 0

        # 3. Back-to-back doctrine (same as immediately last = worse)
        last_dt = state.last_doctrine_types[-1] if state.last_doctrine_types else ""
        back_to_back_score = 1 if dt == last_dt else 0

        # 4. Slot preference
        slot_pref_score = 0
        if slot == "story":
            slot_pref_score = 0 if dt in STORY_PREFERRED_DOCTRINES else 1

        # 5. Mode preference (event_day → Real Event hooks; eve → Friend Cold Open)
        mode_pref_score = 1
        if mode == "event_day" and dt.startswith("6"):
            mode_pref_score = 0
        elif mode == "event_eve" and dt.startswith("7"):
            mode_pref_score = 0
        elif mode == "generic":
            mode_pref_score = 0  # no mode preference for generic

        # 6. Total usage count (least used first across the window)
        usage = state.used_hook_ids.count(hid)

        return (within_day_score, cooldown_score, friend_score,
                back_to_back_score, slot_pref_score, mode_pref_score,
                usage, hid)

    ranked = sorted(candidates, key=score)

    # ─── Themed-positions branch ─────────────────────────────────────────
    # When a theme list is given, position N gets a hook whose doctrine
    # matches that theme. Within the themed bucket, the friend's
    # occurrence index in the plan window selects WHICH of the bucket's
    # candidates is picked — so consecutive appearances of the same friend
    # cycle through their themed hooks instead of always returning the
    # best-scoring one. Falls back to any unused candidate if the theme
    # has no available hook.
    if themes_for_positions:
        chosen: list[dict] = []
        used_ids: set[int] = set()
        for theme in themes_for_positions[:3]:
            valid_doctrines = THEME_DOCTRINE_MAP.get(theme, set())
            themed_pool = [
                h for h in ranked
                if h["id"] not in used_ids
                and h.get("doctrine_type") in valid_doctrines
            ]
            if themed_pool:
                pick = themed_pool[occurrence_idx % len(themed_pool)]
            else:
                # Fallback: any unused candidate, also rotated by occurrence
                fallback_pool = [h for h in ranked if h["id"] not in used_ids]
                pick = (
                    fallback_pool[occurrence_idx % len(fallback_pool)]
                    if fallback_pool else None
                )
            if pick:
                chosen.append(pick)
                used_ids.add(pick["id"])
        return chosen

    # ─── Default variety branch (no theme list — legacy behaviour) ───────
    # Pick top 3 distinct doctrine types if possible (variety)
    chosen: list[dict] = []
    seen_doctrines: set[str] = set()
    for h in ranked:
        if h in chosen:
            continue
        dt = h.get("doctrine_type", "")
        if dt in seen_doctrines and len(chosen) < 3:
            continue  # try for variety first
        chosen.append(h)
        seen_doctrines.add(dt)
        if len(chosen) >= 3:
            break

    # If we got fewer than 3 because of the variety filter, fill from the rest
    if len(chosen) < 3:
        for h in ranked:
            if h not in chosen:
                chosen.append(h)
                if len(chosen) >= 3:
                    break

    return chosen


# ─── Lookup helpers ──────────────────────────────────────────────────────────

def hook_by_id(hook_id: int) -> Optional[dict]:
    for h in all_hooks():
        if h["id"] == hook_id:
            return h
    return None


def doctrine_type_choices() -> list[str]:
    """All doctrine types in the library — for Airtable single_select options."""
    payload = load_hooks()
    return payload.get("_meta", {}).get("doctrine_types") or []


# ─── Stats ───────────────────────────────────────────────────────────────────

def coverage_summary() -> dict:
    payload = load_hooks()
    hooks = payload.get("hooks") or []
    by_friend = Counter(h.get("friend") or "any" for h in hooks)
    by_doctrine = Counter(h.get("doctrine_type") for h in hooks)
    by_market: Counter = Counter()
    for h in hooks:
        for m in (h.get("markets") or []):
            by_market[m] += 1
    return {
        "total":     len(hooks),
        "by_friend": dict(by_friend),
        "by_doctrine": dict(by_doctrine),
        "by_market": dict(by_market),
    }


if __name__ == "__main__":
    print("Hook library coverage:")
    print(json.dumps(coverage_summary(), indent=2))
    print()
    print("Picking 3 hooks for jake / AU / story / generic:")
    state = RotationState()
    picks = pick_three_hooks("jake", "AU", "story", state, mode="generic")
    for i, h in enumerate(picks, start=1):
        print(f"  Option {i} (hook #{h['id']} · {h['doctrine_type']}):")
        print(f"    {h['hook'][:120]}")
