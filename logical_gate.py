"""
logical_gate.py — Agent 2: Pre-generation Logical Gate.

Pure logic — no LLM calls. Runs the 4-step alignment check that locks city,
friend, and currency BEFORE a single word is written. If any step fails the
pipeline halts (run.py exits with code 1).

Steps:
  1 — DATE CHECK     : load calendar.json, find mandatory + recommended events
  2 — MARKET SELECT  : derive market from mandatory event, fall back to rotation
  3 — FRIEND ASSIGN  : pick the friend whose city + cooldowns + enemy archetype
                       align with the mandatory event
  4 — CURRENCY LOCK  : read currency directly from friends_db.json — never derive

Reference: PROJECT_SCOPE.md §6, AGENTS.md "Agent 2".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import brand
import memory as memory_mod

BASE_DIR       = Path(__file__).parent
FRIENDS_DB     = BASE_DIR / "data" / "friends_db.json"
CALENDAR_FILE  = BASE_DIR / "data" / "calendar.json"


# ─── Result type ─────────────────────────────────────────────────────────────

# Editorial cadence modes (see Master Documents/CONTENT_CADENCE.md):
#   "event_day"  — target date IS a Tier-1 event day (script publishes day-of)
#   "event_eve"  — target date is the day BEFORE a Tier-1 event (optional teaser)
#   "generic"    — every other day. Friend-driven story, no calendar lock.

GateMode = str  # "event_day" | "event_eve" | "generic"


@dataclass
class GateResult:
    gate_passed: bool
    target_date: str               # the date the script will publish
    current_date: str              # the date the gate was run
    mode: GateMode                 # event_day | event_eve | generic
    mandatory_event: Optional[str] # only set when mode != "generic"
    recommended_events: list[str] = field(default_factory=list)
    days_until_mandatory: Optional[int] = None
    market: str = ""              # "AU" | "US" | "UK"
    city: str = ""
    friend_id: str = ""
    friend_name: str = ""
    neighbourhood: str = ""
    street_detail: str = ""
    currency: str = ""            # "$" | "£" — hard-locked
    enemy_archetype: str = ""
    locked_at: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class GateFailure(RuntimeError):
    """Raised when the logical gate cannot resolve a valid run configuration."""


# ─── Calendar helpers ────────────────────────────────────────────────────────

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


def _all_occurrences_in_range(events: list[dict], start: date, end: date) -> list[dict]:
    """Return every event that falls between start and end inclusive (with concrete date)."""
    out: list[dict] = []
    for e in events:
        # Walk a few candidate years to catch annually-recurring events.
        for year_offset in (-1, 0, 1):
            d = _next_occurrence(e, date(start.year + year_offset, 1, 1))
            if not d:
                continue
            if start <= d <= end:
                enriched = dict(e)
                enriched["resolved_date"] = d.isoformat()
                enriched.setdefault("id", _slug(e.get("name", "")))
                out.append(enriched)
                break
    return out


def _load_calendar() -> list[dict]:
    if not CALENDAR_FILE.exists():
        return []
    try:
        return json.loads(CALENDAR_FILE.read_text()).get("events", []) or []
    except Exception as e:
        print(f"[gate] calendar load failed: {e}")
        return []


def _upcoming(events: list[dict], days_ahead: int = 30) -> list[dict]:
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


# ─── friends_db helpers ──────────────────────────────────────────────────────

def _load_friends() -> list[dict]:
    if not FRIENDS_DB.exists():
        raise GateFailure(f"friends_db_missing: {FRIENDS_DB}")
    try:
        raw = json.loads(FRIENDS_DB.read_text())
    except Exception as e:
        raise GateFailure(f"friends_db_unreadable: {e}")
    # Schema v2.0 wraps friends in {"friends": [...]}; v1 was a bare list.
    if isinstance(raw, dict):
        return raw.get("friends", []) or []
    if isinstance(raw, list):
        return raw
    raise GateFailure("friends_db_unexpected_format")


def _get_friend(friends: list[dict], friend_id: str) -> Optional[dict]:
    for f in friends:
        if f.get("id") == friend_id:
            return f
    return None


# ─── The four steps ──────────────────────────────────────────────────────────

def _step1_date_check(
    notes: list[str],
    target_date: date,
) -> tuple[Optional[dict], GateMode, list[dict]]:
    """
    Decide the editorial mode for the target_date.

    Rules (from CONTENT_CADENCE.md):
      - target_date is a Tier-1 event day  → mode "event_day"
      - target_date + 1 day is a Tier-1 event → mode "event_eve"
      - otherwise                              → mode "generic"

    Tier-2/Tier-3 events are intentionally treated as generic — they exist only
    as soft trend signals, never as mandatory anchors.
    """
    events = _load_calendar()
    if not events:
        notes.append("calendar.json missing or empty — generic mode")
        return None, "generic", []

    # 30-day forward window (for the strategy director's awareness, not the lock)
    upcoming = _upcoming(events, days_ahead=30)

    # Strict day-of / day-eve check on Tier-1 only
    window_events = _all_occurrences_in_range(
        events,
        start=target_date,
        end=target_date + timedelta(days=1),
    )

    tier1_today: Optional[dict] = None
    tier1_eve:   Optional[dict] = None
    for e in window_events:
        tier = int(e.get("revenue_tier", 3) or 3)
        if tier != 1:
            continue
        d = date.fromisoformat(e["resolved_date"])
        if d == target_date and tier1_today is None:
            tier1_today = e
        elif d == target_date + timedelta(days=1) and tier1_eve is None:
            tier1_eve = e

    if tier1_today:
        tier1_today["days_until"] = 0
        return tier1_today, "event_day", upcoming
    if tier1_eve:
        tier1_eve["days_until"] = 1
        return tier1_eve, "event_eve", upcoming

    notes.append("no Tier-1 event on target_date or target_date+1 — generic mode")
    return None, "generic", upcoming


def _step2_market_select(
    mandatory: Optional[dict],
    mem: memory_mod.MemoryState,
    notes: list[str],
) -> tuple[str, str]:
    """
    Derive (market, city). In event modes the market is locked by the event.
    In generic mode we rotate across cities to keep the feed balanced.
    """
    if mandatory:
        countries = mandatory.get("countries") or []
        cities    = mandatory.get("cities") or []
        if cities:
            city = cities[0]
            for m, c in brand.CITIES.items():
                if c == city:
                    return m, city
        for c in countries:
            if c in brand.CITIES:
                return c, brand.CITIES[c]
        notes.append("event has no recognised city/country — falling through to rotation")

    # GENERIC MODE — rotate cities by least-recently-used.
    # We sort the cooldown dict by ISO date (descending) so we get a real
    # recency walk regardless of dict insertion order.
    friends_list = _load_friends()
    fid_to_city  = {f["id"]: f.get("city", "") for f in friends_list}
    sorted_cooldowns = sorted(
        mem.friend_cooldowns.items(),
        key=lambda kv: kv[1],
        reverse=True,   # most recent first
    )
    recently_used_cities = [
        fid_to_city.get(fid, "") for fid, _iso in sorted_cooldowns[:2]
    ]

    rotation = ["Melbourne", "New York City", "London"]
    for c in rotation:
        if c not in recently_used_cities:
            for m, mc in brand.CITIES.items():
                if mc == c:
                    return m, c
    # Every rotation city was used in the last 2 days → pick the city used
    # LEAST recently of the three (not necessarily in rotation order).
    city_last_used = {c: 0 for c in rotation}
    for fid, iso in sorted_cooldowns:
        c = fid_to_city.get(fid, "")
        if c in city_last_used and city_last_used[c] == 0:
            city_last_used[c] = sorted_cooldowns.index((fid, iso)) + 1
    least_recent_city = max(city_last_used, key=lambda c: city_last_used[c] or 999)
    for m, mc in brand.CITIES.items():
        if mc == least_recent_city:
            return m, least_recent_city
    return "AU", brand.CITIES["AU"]


def _enemy_matches_event(friend: dict, event_id: Optional[str]) -> bool:
    if not event_id:
        return True
    failure_modes = friend.get("event_failure_modes") or {}
    return event_id in failure_modes


def _step3_friend_assign(
    friends: list[dict],
    market: str,
    city: str,
    mandatory_id: Optional[str],
    mem: memory_mod.MemoryState,
    force_friend: Optional[str],
    notes: list[str],
) -> dict:
    """Pick a friend in the target city, honouring cooldowns and event match."""
    if force_friend:
        f = _get_friend(friends, force_friend)
        if not f:
            raise GateFailure(f"force_friend_unknown: {force_friend}")
        if mandatory_id and f.get("city") != city:
            raise GateFailure(
                f"friend_city_mismatch: {force_friend} is in {f.get('city')}, "
                f"mandatory event requires {city}"
            )
        if memory_mod.friend_on_cooldown(mem, force_friend):
            notes.append(f"force_friend {force_friend} is on cooldown — overriding (manual)")
        return f

    in_city = [f for f in friends if f.get("city") == city]
    if not in_city:
        # No friend in that city — fall back to whole roster.
        in_city = friends
        notes.append(f"no friend in {city}; falling back to full roster")

    available = [f for f in in_city if not memory_mod.friend_on_cooldown(mem, f["id"])]
    pool = available or in_city
    if not available:
        notes.append("all friends in target city on cooldown — selecting least-recent")

    # Prefer friends whose enemy_archetype matches the mandatory event.
    matched = [f for f in pool if _enemy_matches_event(f, mandatory_id)]
    candidates = matched or pool

    # Tie-break: oldest cooldown first (least recently used).
    def _last_used_key(f: dict) -> tuple[int, str]:
        iso = mem.friend_cooldowns.get(f["id"])
        return (1, iso) if iso else (0, "")  # never used → most preferred

    candidates.sort(key=_last_used_key)
    return candidates[0]


def _step4_currency_lock(friend: dict, notes: list[str]) -> str:
    currency = friend.get("currency")
    if not currency:
        raise GateFailure(f"currency_missing_in_friends_db: {friend.get('id')}")

    expected = brand.CURRENCY_MAP.get(friend.get("city", ""))
    if expected and expected != currency:
        notes.append(
            f"currency_warning: friend {friend['id']} has {currency} but "
            f"city {friend['city']} expects {expected}"
        )
    return currency


# ─── Public entry point ──────────────────────────────────────────────────────

def run_gate(
    format_type: str = "reel",
    pillar: Optional[int] = None,
    force_friend: Optional[str] = None,
    target_date: Optional[date] = None,
    mem: Optional[memory_mod.MemoryState] = None,
) -> GateResult:
    """
    Run the 4-step gate for the given target_date (defaults to today).
    Returns a GateResult on success. Raises GateFailure on misalignment.

    The optional `mem` parameter lets callers (e.g. content_calendar.py) inject
    a forward-simulated memory state instead of loading from disk — useful for
    pre-computing the next N days without persisting cooldowns.
    """
    notes: list[str] = []
    target = target_date or date.today()

    # Step 1 — date check decides the editorial mode
    mandatory, mode, upcoming = _step1_date_check(notes, target)
    mandatory_id   = mandatory.get("id") if mandatory else None
    mandatory_name = mandatory.get("name") if mandatory else None
    days_until     = mandatory.get("days_until") if mandatory else None

    # Step 3 (load memory early — Step 2 needs it for generic-mode rotation)
    friends = _load_friends()
    if mem is None:
        mem = memory_mod.load_memory()

    # Step 2 — market/city
    market, city = _step2_market_select(mandatory, mem, notes)

    # Step 3 (cont.) — friend assignment
    friend  = _step3_friend_assign(
        friends, market, city, mandatory_id, mem, force_friend, notes
    )
    # Re-derive city/market from the chosen friend so the lock matches the friend
    # we actually picked (covers the generic-mode rotation case).
    market = friend.get("market", market)
    city   = friend.get("city", city)

    # Step 4 — currency lock
    currency = _step4_currency_lock(friend, notes)

    result = GateResult(
        gate_passed          = True,
        target_date          = target.isoformat(),
        current_date         = date.today().isoformat(),
        mode                 = mode,
        mandatory_event      = mandatory_name,
        recommended_events   = [e["name"] for e in upcoming[:5]],
        days_until_mandatory = days_until,
        market               = market,
        city                 = city,
        friend_id            = friend["id"],
        friend_name          = friend.get("name", friend["id"]),
        neighbourhood        = friend.get("neighbourhood", ""),
        street_detail        = friend.get("street_detail", ""),
        currency             = currency,
        enemy_archetype      = friend.get("enemy_archetype", ""),
        locked_at            = datetime.now().isoformat(timespec="seconds"),
        notes                = notes,
    )
    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Run the pre-generation logical gate")
    p.add_argument("--format", choices=["reel", "story"], default="reel")
    p.add_argument("--pillar", type=int, choices=[1, 2, 3, 4, 5])
    p.add_argument("--friend", help="force friend id")
    p.add_argument("--target-date", help="ISO date the script will publish (default: today)")
    args = p.parse_args()

    target = date.fromisoformat(args.target_date) if args.target_date else None
    try:
        gr = run_gate(args.format, args.pillar, args.friend, target)
        print(json.dumps(gr.to_dict(), indent=2))
    except GateFailure as e:
        print(f"GATE FAILED: {e}")
        raise SystemExit(1)
