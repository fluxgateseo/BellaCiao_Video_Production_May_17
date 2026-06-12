"""
content_calendar.py — pre-computed publishing plan for review BEFORE script generation.

Walks N days forward from a start date and, for each day, runs the Logical Gate
to compute mode (event_day / event_eve / generic), the calendar event (if any),
the suggested friend (with rotation simulated forward across the whole window),
the suggested pillar (round-robin), and a one-sentence story seed pulled from
friends_db.json.

Bella publishes a STORY (~30s) AND a REEL (30-60s) each day, so the output
has TWO rows per day:

  - story = ONE beat, isolated. The moment a reel would build TOWARD.
  - reel  = the full Pixar arc + Vogler journey + Ciao turning point.

Same friend across both slots — the story is a slice of the reel's world.
NO LLM CALLS. Pure logic. Runs in seconds. The output is a planning artifact
the user reviews and edits before triggering brief generation for any specific
day.

Outputs:
  data/content_calendar.json                       — machine-readable
  ../Master Documents/CONTENT_CALENDAR.md          — markdown table for review

Usage:
  python3 content_calendar.py
  python3 content_calendar.py --start 2026-04-11 --days 14
  python3 content_calendar.py --days 30
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path

import brand
import logical_gate
import memory as memory_mod

BASE_DIR = Path(__file__).parent
JSON_OUT = BASE_DIR / "data" / "content_calendar.json"
MD_OUT   = BASE_DIR.parent / "Master Documents" / "CONTENT_CALENDAR.md"

PILLARS = {
    1: "Operational",
    2: "Empathy",
    3: "Business",
    4: "Customer",
    5: "Legacy",
}

# ─── Themed alignment (v1.8+ — retention-first doctrine) ────────────────────
# Position N across all 4 choice fields (hook, story_seed, pillar, sensory_hook)
# corresponds to the same scroll-stop archetype. Picking "1" everywhere yields
# a Pain-coordinated post; "2" → Insider (AI-transparent); "3" → Myth-Buster.
# Internal key "sensory" is retained for pipeline/scoring compatibility.
THEMES_PER_POSITION = ("pain", "insider", "myth_buster")
# Pillar IDs that best match each archetype — used to lock pillar_1/2/3
# Pain → Operational (Pillar 1), Insider → Customer (Pillar 4),
# Myth-Buster → Empathy (Pillar 2 — reframes the owner's self-blame).
THEMED_PILLARS = (1, 4, 2)


# ─── Friend lookup ───────────────────────────────────────────────────────────

def _friends_by_id() -> dict[str, dict]:
    raw = json.loads((BASE_DIR / "data" / "friends_db.json").read_text())
    items = raw.get("friends", []) if isinstance(raw, dict) else raw
    return {f["id"]: f for f in items}


def _slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


# ─── Research opportunity lookup (enriches calendar with Skill 3 output) ────

_OPPORTUNITY_CACHE: dict | None = None


def _load_opportunities() -> list[dict]:
    """Load content_opportunities.json if it exists. Cached per-run."""
    global _OPPORTUNITY_CACHE
    if _OPPORTUNITY_CACHE is not None:
        return _OPPORTUNITY_CACHE.get("opportunities", [])
    path = BASE_DIR / "data" / "content_opportunities.json"
    if not path.exists():
        _OPPORTUNITY_CACHE = {}
        return []
    try:
        _OPPORTUNITY_CACHE = json.loads(path.read_text())
    except Exception:
        _OPPORTUNITY_CACHE = {}
    return _OPPORTUNITY_CACHE.get("opportunities", [])


def _pick_opportunity_for(friend_id: str, occurrence_idx: int) -> dict | None:
    """
    Pick a research opportunity that matches this friend. If multiple exist,
    rotate through them by occurrence index so each appearance of the same
    friend shows a different research angle. Returns None if no opportunity
    matches (or no research data available).
    """
    opps = _load_opportunities()
    if not opps:
        return None
    matches = [
        o for o in opps
        if isinstance(o, dict)
        and not o.get("parse_error")
        and friend_id in (o.get("friend_fit") or [])
    ]
    if not matches:
        return None
    return matches[occurrence_idx % len(matches)]


def _story_seeds(
    friend: dict,
    mode: str,
    event_name: str | None,
    slot: str,
    occurrence_idx: int = 0,
) -> list[str]:
    """
    Return 3 DISTINCT archetype-aligned story seeds for the user to pick from
    in Airtable. v1.8+ retention-first doctrine — all three seeds are Bella-
    spoken hooks pulled from the friend's archetype-ordered sensory_hooks array:
      [0] Pain Hook         — named operational moment the restaurateur feels
      [1] Insider Hook      — Bella acknowledges what SHE did (AI-transparent)
      [2] Myth-Buster Hook  — contrarian reframe ("it's not X, it's Y")

    Pure logic, no LLM. `occurrence_idx` is retained for future rotation but
    NOT used in v1.8 — archetype doctrine wants stable archetypal templates,
    not content rotation.

    Migration status per friend: a friend is "archetype-ordered" if their
    `sensory_hooks[0/1/2]` correspond to Pain/Insider/Myth-Buster respectively.
    Friends not yet migrated will produce valid seeds that may not match the
    archetype labels precisely — cosmetic only, pipeline stays functional.
    """
    name = friend.get("name", "the friend")
    hooks = friend.get("sensory_hooks") or []

    def _frame(archetype_label: str, hook_text: str) -> str:
        if slot == "story":
            return f'{archetype_label}: Bella speaks direct to camera — "{hook_text}"'
        return f'{archetype_label}: Bella opens the reel — "{hook_text}"'

    def _fallback(archetype_label: str, default_msg: str) -> str:
        return f"{archetype_label}: {default_msg}"

    seeds: list[str] = []

    # ─── Pos 1 — Pain Hook ──────────────────────────────────────────────
    # Event day wins — a named calendar pain is always more specific than
    # the friend's baseline pain.
    if mode == "event_day" and event_name:
        ev_id = _slug(event_name)
        event_pain = None
        for known_id, failure_text in (friend.get("event_failure_modes") or {}).items():
            if known_id in ev_id or ev_id in known_id:
                event_pain = failure_text
                break
        if event_pain:
            seeds.append(f'Pain ({event_name}): Bella names it — "{event_pain}"')
        elif hooks:
            seeds.append(_frame("Pain", hooks[0]))
        else:
            seeds.append(_fallback("Pain", f"the recurring dead-zone in {name}'s week."))
    else:
        if hooks:
            seeds.append(_frame("Pain", hooks[0]))
        else:
            seeds.append(_fallback("Pain", f"the recurring dead-zone in {name}'s week."))

    # ─── Pos 2 — Insider Hook ──────────────────────────────────────────
    if len(hooks) >= 2:
        seeds.append(_frame("Insider", hooks[1]))
    else:
        seeds.append(_fallback("Insider", f"Bella names a fix she made for {name} while the owner was mid-service."))

    # ─── Pos 3 — Myth-Buster Hook ───────────────────────────────────────
    if len(hooks) >= 3:
        seeds.append(_frame("Myth-Buster", hooks[2]))
    else:
        seeds.append(_fallback("Myth-Buster", f"what {name} blames when they're wrong about why the room's empty."))

    return seeds


# ─── Calendar row type ───────────────────────────────────────────────────────

@dataclass
class CalendarRow:
    day_number: int
    target_date: str       # ISO
    weekday: str
    slot: str              # "story" | "reel"
    duration_target: int   # ~30 for story, ~45 for reel
    mode: str              # event_day | event_eve | generic
    calendar_event: str    # "" if generic
    market: str
    city: str
    friend_id: str
    friend_name: str
    pillar: int            # legacy — left as 0 in v1.6+, resolved at brief time from pillar_choice
    pillar_theme: str      # legacy — same
    story_seed: str        # legacy — left blank in v1.7+, resolved from story_seed_choice
    # Research enrichment (NEW v2.1) — from data/content_opportunities.json
    research_angle: str = ""        # the strategic angle from Skill 3 (competitive)
    research_gap: str = ""          # the competitive gap this row addresses
    research_urgency: str = ""      # high | medium | low
    research_rationale: str = ""    # why this angle, why now
    # 3 story_seed options for the user to pick from
    story_seed_1: str = ""
    story_seed_2: str = ""
    story_seed_3: str = ""
    story_seed_choice: str = ""  # "1" | "2" | "3" — set by user in Airtable
    # 3 sensory_hook options for the user to pick from (NEW v1.7+)
    sensory_hook_1: str = ""
    sensory_hook_2: str = ""
    sensory_hook_3: str = ""
    sensory_hook_choice: str = ""  # "1" | "2" | "3" — set by user in Airtable
    # 3 pillar options for the user to pick from
    pillar_1: int = 0
    pillar_1_theme: str = ""
    pillar_2: int = 0
    pillar_2_theme: str = ""
    pillar_3: int = 0
    pillar_3_theme: str = ""
    pillar_choice: str = ""  # "1" | "2" | "3" — set by user in Airtable
    # 3 hook options for the user to pick from
    hook_1_id: int = 0
    hook_1_text: str = ""
    hook_1_doctrine: str = ""
    hook_2_id: int = 0
    hook_2_text: str = ""
    hook_2_doctrine: str = ""
    hook_3_id: int = 0
    hook_3_text: str = ""
    hook_3_doctrine: str = ""
    # User-controlled fields (kept for round-trip JSON shape)
    hook_choice: str = ""    # "1" | "2" | "3" — set by user in Airtable
    status: str = "draft"    # draft | planned | skip | rejected
    rejected_reason: str = ""
    notes: str = ""
    regenerate_request: bool = False
    regenerate_notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Slot duration targets — pulled from brand.py so they stay in lockstep.
# The previous "kept local to avoid importing brand.py" workaround is RETIRED:
# brand.py has no heavy imports, so importing it is free and it eliminates the
# drift risk where this local dict silently fell out of sync with brand.SLOT_DURATION.
_SLOT_TARGETS = {slot: band["target"] for slot, band in brand.SLOT_DURATION.items()}
_SLOT_ORDER   = ("story", "reel")


# ─── Generation ──────────────────────────────────────────────────────────────

def generate(
    start: date,
    days: int,
    base_mem: memory_mod.MemoryState | None = None,
) -> list[CalendarRow]:
    """
    Walk `days` days forward from `start` and produce TWO rows per day —
    one story slot (~30s) and one reel slot (30-60s).

    Each row carries 3 hook options the user picks from in Airtable.
    Hook rotation tracks doctrine types and reuse cooldown across the
    publish-order sequence (story-then-reel within a day, day-by-day).

    Memory rotation is simulated forward per DAY, not per slot. The same
    friend serves both the day's story and reel.
    """
    import hooks_library

    friends = _friends_by_id()
    mem = deepcopy(base_mem) if base_mem else memory_mod.load_memory()
    rotation = hooks_library.RotationState()

    # Track per-friend occurrence index across the plan window so we can
    # rotate the sensory_hook subset on each new appearance of the same friend.
    friend_occurrence: dict[str, int] = {}

    rows: list[CalendarRow] = []
    for offset in range(days):
        target = start + timedelta(days=offset)

        try:
            gate = logical_gate.run_gate(target_date=target, mem=mem)
        except logical_gate.GateFailure as e:
            for slot in _SLOT_ORDER:
                rows.append(CalendarRow(
                    day_number     = offset + 1,
                    target_date    = target.isoformat(),
                    weekday        = target.strftime("%A"),
                    slot           = slot,
                    duration_target= _SLOT_TARGETS[slot],
                    mode           = "error",
                    calendar_event = "",
                    market         = "",
                    city           = "",
                    friend_id      = "",
                    friend_name    = "",
                    pillar         = 0,
                    pillar_theme   = "",
                    story_seed     = "",
                    story_seed_1   = f"GATE FAILURE: {e}",
                    status         = "draft",
                ))
            continue

        friend = friends.get(gate.friend_id, {})
        # Pillar positions are LOCKED to themes (v1.7+):
        #   pillar_1 = 1 (Operational), pillar_2 = 2 (Empathy), pillar_3 = 4 (Customer)
        # This makes picking "1" across all 4 choice fields a self-consistent set.
        p1, p2, p3 = THEMED_PILLARS

        # Per-friend occurrence index — increments each time this friend appears
        # in the window. Used to rotate the 3-of-N sensory_hook subset so each
        # appearance of the same friend shows different sensory beats.
        occ = friend_occurrence.get(gate.friend_id, 0)
        friend_occurrence[gate.friend_id] = occ + 1

        # Compute the day's sensory_hook trio ONCE — both slots share it.
        # Window of 3 starting at offset `occ` into the friend's array, wrapping.
        friend_hooks = friend.get("sensory_hooks") or []
        sh: list[str] = []
        if friend_hooks:
            n = len(friend_hooks)
            for k in range(3):
                sh.append(friend_hooks[(occ + k) % n])
        else:
            sh = ["", "", ""]

        # Two rows per day — same gate result, slot-specific story_seed + hooks.
        # The reel slot HARD-excludes the story slot's picks so the same hook
        # never appears twice on the same day for the same friend.
        day_used_ids: set[int] = set()
        for slot in _SLOT_ORDER:
            picks = hooks_library.pick_three_hooks(
                friend_id = gate.friend_id,
                market    = gate.market,
                slot      = slot,
                state     = rotation,
                mode      = gate.mode,
                hard_exclude_ids = day_used_ids if slot == "reel" else None,
                themes_for_positions = list(THEMES_PER_POSITION),
                occurrence_idx = occ,
            )
            # Track this slot's picks so the next slot in the day excludes them
            day_used_ids.update(p["id"] for p in picks if p.get("id"))
            # Pad to 3 with empty hooks if the library couldn't find enough
            while len(picks) < 3:
                picks.append({"id": 0, "hook": "", "doctrine_type": ""})

            seeds = _story_seeds(friend, gate.mode, gate.mandatory_event, slot, occurrence_idx=occ)
            # Research enrichment — pull an opportunity for this friend if
            # Skill 3 (competitive ideation) has produced any. Rotates per
            # occurrence so multiple appearances show different angles.
            opp = _pick_opportunity_for(gate.friend_id, occ)
            row = CalendarRow(
                day_number     = offset + 1,
                target_date    = target.isoformat(),
                weekday        = target.strftime("%A"),
                slot           = slot,
                duration_target= _SLOT_TARGETS[slot],
                mode           = gate.mode,
                calendar_event = gate.mandatory_event or "",
                market         = gate.market,
                city           = gate.city,
                friend_id      = gate.friend_id,
                friend_name    = gate.friend_name,
                pillar         = 0,                 # legacy — resolved from pillar_choice at brief time
                pillar_theme   = "",                # legacy
                pillar_1       = p1,
                pillar_1_theme = PILLARS.get(p1, ""),
                pillar_2       = p2,
                pillar_2_theme = PILLARS.get(p2, ""),
                pillar_3       = p3,
                pillar_3_theme = PILLARS.get(p3, ""),
                story_seed     = "",                # legacy — resolved from story_seed_choice at brief time
                story_seed_1   = seeds[0],
                story_seed_2   = seeds[1],
                story_seed_3   = seeds[2],
                sensory_hook_1 = sh[0],
                sensory_hook_2 = sh[1],
                sensory_hook_3 = sh[2],
                hook_1_id       = picks[0].get("id", 0),
                hook_1_text     = picks[0].get("hook", ""),
                hook_1_doctrine = picks[0].get("doctrine_type", ""),
                hook_2_id       = picks[1].get("id", 0),
                hook_2_text     = picks[1].get("hook", ""),
                hook_2_doctrine = picks[1].get("doctrine_type", ""),
                hook_3_id       = picks[2].get("id", 0),
                hook_3_text     = picks[2].get("hook", ""),
                hook_3_doctrine = picks[2].get("doctrine_type", ""),
                research_angle    = (opp or {}).get("angle", ""),
                research_gap      = (opp or {}).get("gap", ""),
                research_urgency  = (opp or {}).get("urgency", ""),
                research_rationale= (opp or {}).get("rationale", ""),
                status         = "draft",
            )
            rows.append(row)

            # Record ALL 3 picks into rotation state so the next slot's
            # cooldown excludes them. Without this, picks[1] and picks[2] from
            # one slot reappear as picks[0] and picks[1] in the next slot
            # (sliding-window bug).
            for h in picks:
                if h.get("id"):
                    rotation.record(h)

        # Simulate that this day was produced — advance memory ONCE per day.
        # Append pillar_1 to the sequence (the day's "default" angle) so the
        # rotation simulation walks forward; user picks the actual angle later.
        mem.friend_cooldowns[gate.friend_id] = target.isoformat()
        mem.pillar_sequence.append(p1)
        if gate.mandatory_event:
            mem.event_history.insert(0, gate.mandatory_event)
        mem.last_run_at = datetime.now().isoformat(timespec="seconds")

    return rows


# ─── Output formats ──────────────────────────────────────────────────────────

def write_json(rows: list[CalendarRow], start: date, days: int) -> Path:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date":   start.isoformat(),
        "end_date":     (start + timedelta(days=days - 1)).isoformat(),
        "day_count":    days,
        "rows":         [r.to_dict() for r in rows],
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=2))
    return JSON_OUT


def write_markdown(rows: list[CalendarRow], start: date, days: int) -> Path:
    lines: list[str] = []
    lines.append("# CONTENT_CALENDAR.md")
    lines.append("## Bella Script Engine — Publishing Plan")
    lines.append(f"### Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  Window: {start.isoformat()} → {(start + timedelta(days=days - 1)).isoformat()}  ·  {days} days × 2 slots = {len(rows)} rows")
    lines.append("")
    lines.append("> Bella publishes ONE story (~30s) and ONE reel (30-60s) each day on Instagram. Two rows per day — same friend, different format. Review BEFORE running `--stage brief`. Edit `script_engine/data/content_calendar.json` to lock rows (`status=planned`), drop rows (`status=skip`), or override friend/seed.")
    lines.append("")
    lines.append("**Mode legend:** `event_day` = main day of the year, anchor on the event. `event_eve` = day before a Tier-1 event, calm-before-the-storm framing. `generic` = friend-driven story anchored on the friend's neighbourhood + a specific operational detail.")
    lines.append("")
    lines.append("**Slot legend:** `story` = ONE beat isolated, ~30s, the moment a reel would build toward. `reel` = full Pixar arc + Vogler journey + Ciao turning point, 30-60s.")
    lines.append("")

    # Summary lines
    by_mode: dict[str, int] = {}
    by_slot: dict[str, int] = {}
    for r in rows:
        by_mode[r.mode] = by_mode.get(r.mode, 0) + 1
        by_slot[r.slot] = by_slot.get(r.slot, 0) + 1
    lines.append("**Mode mix:** " + ", ".join(f"{m}={c}" for m, c in sorted(by_mode.items())))
    lines.append("**Slot mix:** " + ", ".join(f"{s}={c}" for s, c in sorted(by_slot.items())))
    lines.append("")

    # The table
    lines.append("| Day | Date | Wk | Slot | Dur | Mode | Event | City | Friend | Pillar options (3) | Hook options (3) |")
    lines.append("|---:|---|---|---|---:|---|---|---|---|---|---|")
    for r in rows:
        event = r.calendar_event or "—"
        # Render the 3 pillar options
        pillar_md = "<br>".join(
            f"**{n}**: {p} {theme}"
            for n, (p, theme) in enumerate(
                [(r.pillar_1, r.pillar_1_theme),
                 (r.pillar_2, r.pillar_2_theme),
                 (r.pillar_3, r.pillar_3_theme)],
                start=1,
            )
            if p
        ) or "—"
        # Render the 3 hooks as a compact bullet list
        hook_lines: list[str] = []
        for n, (txt, doc, hid) in enumerate(
            [(r.hook_1_text, r.hook_1_doctrine, r.hook_1_id),
             (r.hook_2_text, r.hook_2_doctrine, r.hook_2_id),
             (r.hook_3_text, r.hook_3_doctrine, r.hook_3_id)],
            start=1
        ):
            if not txt:
                continue
            short = txt.replace("|", "/").strip()
            if len(short) > 95:
                short = short[:92] + "..."
            doc_short = (doc or "").split("—", 1)[-1].strip() if "—" in (doc or "") else (doc or "")
            hook_lines.append(f"**{n}** ({doc_short}): {short}")
        hooks_md = "<br>".join(hook_lines) or "—"
        lines.append(
            f"| {r.day_number} "
            f"| {r.target_date} "
            f"| {r.weekday[:3]} "
            f"| `{r.slot}` "
            f"| {r.duration_target}s "
            f"| `{r.mode}` "
            f"| {event} "
            f"| {r.city or '—'} "
            f"| {r.friend_name or r.friend_id or '—'} "
            f"| {pillar_md} "
            f"| {hooks_md} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## How to use this")
    lines.append("")
    lines.append("1. **Scan the table.** Look for: wrong friend on a wrong day, story seeds that don't fit the format, missed Tier-1 events, days where the calendar event is `—` but you wanted one.")
    lines.append("2. **Edit the JSON.** Open `script_engine/data/content_calendar.json` and change any row — `status` to `planned` to lock, `skip` to drop. Override `friend_id`, rewrite `story_seed`, or change `pillar`.")
    lines.append("3. **Generate the briefs.** When a day is ready, run:")
    lines.append("   ```")
    lines.append("   python3 run.py --stage brief --target-date YYYY-MM-DD --slot both")
    lines.append("   ```")
    lines.append("   That generates one story brief AND one reel brief in Airtable. Review each in the Briefs table and set `verdict=good`.")
    lines.append("4. **Write the scripts.** Once a brief is approved:")
    lines.append("   ```")
    lines.append("   python3 run.py --stage write --target-date YYYY-MM-DD --slot story")
    lines.append("   python3 run.py --stage write --target-date YYYY-MM-DD --slot reel")
    lines.append("   ```")
    lines.append("")
    lines.append("**Re-running** `python3 content_calendar.py` regenerates this table fresh from the gate. It does NOT preserve manual edits — the JSON file is overwritten. Lock rows in Airtable, not here.")
    lines.append("")
    lines.append(f"*Generated by `script_engine/content_calendar.py` — pure logic, no LLM calls.*")
    lines.append("")

    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.write_text("\n".join(lines))
    return MD_OUT


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Generate the Bella content calendar")
    p.add_argument("--start", help="ISO start date (default: today)")
    p.add_argument("--days",  type=int, default=14, help="how many days to plan (default 14)")
    p.add_argument("--push",  action="store_true",
                   help="also push to Airtable ContentCalendar table after writing locally")
    args = p.parse_args()

    start = date.fromisoformat(args.start) if args.start else date.today()
    days  = args.days

    print(f"[content-calendar] generating {days} days from {start.isoformat()}...")
    rows = generate(start, days)

    json_path = write_json(rows, start, days)
    md_path   = write_markdown(rows, start, days)

    by_mode: dict[str, int] = {}
    by_friend: dict[str, int] = {}
    by_slot: dict[str, int] = {}
    for r in rows:
        by_mode[r.mode] = by_mode.get(r.mode, 0) + 1
        by_friend[r.friend_id] = by_friend.get(r.friend_id, 0) + 1
        by_slot[r.slot] = by_slot.get(r.slot, 0) + 1

    print(f"[content-calendar] wrote {len(rows)} rows ({days} days × 2 slots)")
    print(f"  json     → {json_path}")
    print(f"  markdown → {md_path}")

    if args.push:
        try:
            from content_calendar_sync import push_plan_rows
            row_dicts = [r.to_dict() for r in rows]
            result = push_plan_rows(row_dicts)
            print(f"  airtable → ContentCalendar table")
            print(f"             total={result.get('total',0)} "
                  f"created={result['created']} updated={result['updated']} "
                  f"skipped={result['skipped']}")
            for e in result.get("errors", [])[:5]:
                print(f"             err: {e}")
        except Exception as e:
            print(f"  [airtable] push failed: {e}")
    print()
    print("Slot mix:")
    for slot, count in sorted(by_slot.items()):
        print(f"  {slot:12} {count}")
    print("Mode mix:")
    for mode, count in sorted(by_mode.items()):
        print(f"  {mode:12} {count}")
    print("Friend mix (across both slots):")
    for fid, count in sorted(by_friend.items(), key=lambda kv: -kv[1]):
        print(f"  {fid:12} {count}")


if __name__ == "__main__":
    main()
