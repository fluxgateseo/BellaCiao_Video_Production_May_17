"""
memory.py — Agent 8: Memory Keeper.

Cross-session rotation tracking. Friend cooldowns, pillar sequences, enemy
history, event history, and score trends. Loaded before Agent 3, saved after
a successful job file write. Never raises — returns empty state on missing or
corrupted memory file.

Cooldown rules (from PROJECT_SCOPE.md §5):
  - Friend cooldown   : 3 days minimum between appearances
  - Enemy cooldown    : same enemy cannot appear in 2 consecutive scripts
  - Pillar rotation   : no pillar more than twice in any 5-script sequence
  - Event cooldown    : same event cannot anchor 2 consecutive scripts
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

BASE_DIR    = Path(__file__).parent
MEMORY_FILE = BASE_DIR / "data" / "memory.json"

# Cooldown rule values (single source of truth)
FRIEND_COOLDOWN_DAYS         = 3
PILLAR_WINDOW                = 5     # look back this many scripts
PILLAR_MAX_IN_WINDOW         = 2
SCORE_HISTORY_KEEP           = 25    # ring-buffer size for score trend
EVENT_HISTORY_KEEP           = 25
PILLAR_SEQUENCE_KEEP         = 25
ALLY_HISTORY_KEEP            = 25    # same ring-buffer size as enemies
SCENARIO_HISTORY_KEEP        = 30    # keep a few more — scenarios are higher-cardinality
SCENARIO_WINDOW              = 10    # no same scenario tag within this many scripts


@dataclass
class MemoryState:
    friend_cooldowns: dict[str, str]   = field(default_factory=dict)  # friend_id → ISO date last used
    pillar_sequence: list[int]         = field(default_factory=list)
    enemy_history: list[str]           = field(default_factory=list)  # most recent first
    event_history: list[str]           = field(default_factory=list)  # most recent first
    ally_history: list[str]            = field(default_factory=list)  # most recent first
    scenario_history: list[str]        = field(default_factory=list)  # most recent first, tags from brief.scenario_tags
    score_history: list[dict]          = field(default_factory=list)
    last_run_at: str | None            = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MemoryState":
        return cls(
            friend_cooldowns = dict(raw.get("friend_cooldowns") or {}),
            pillar_sequence  = list(raw.get("pillar_sequence")  or []),
            enemy_history    = list(raw.get("enemy_history")    or []),
            event_history    = list(raw.get("event_history")    or []),
            ally_history     = list(raw.get("ally_history")     or []),
            scenario_history = list(raw.get("scenario_history") or []),
            score_history    = list(raw.get("score_history")    or []),
            last_run_at      = raw.get("last_run_at"),
        )


# ─── Load / save ─────────────────────────────────────────────────────────────

def load_memory() -> MemoryState:
    """Never raises. Returns empty state if file is missing or corrupted."""
    try:
        if not MEMORY_FILE.exists():
            return MemoryState()
        return MemoryState.from_dict(json.loads(MEMORY_FILE.read_text()))
    except Exception as e:
        print(f"[memory] load failed (using empty state): {e}")
        return MemoryState()


def save_memory(job: dict, verdict: dict | None = None) -> None:
    """Update memory from a successful job and persist. Never raises."""
    try:
        memory = load_memory()
        brief  = job.get("brief", {}) or {}

        friend_id      = brief.get("friend")
        pillar         = brief.get("pillar")
        enemy          = brief.get("enemy")
        event          = brief.get("calendar_event")
        ally           = brief.get("ally")
        scenario_tags  = brief.get("scenario_tags") or []
        today_iso      = date.today().isoformat()

        if friend_id:
            memory.friend_cooldowns[friend_id] = today_iso
        if isinstance(pillar, int):
            memory.pillar_sequence.append(pillar)
            memory.pillar_sequence = memory.pillar_sequence[-PILLAR_SEQUENCE_KEEP:]
        if enemy:
            memory.enemy_history.insert(0, enemy)
            memory.enemy_history = memory.enemy_history[:EVENT_HISTORY_KEEP]
        if event:
            memory.event_history.insert(0, event)
            memory.event_history = memory.event_history[:EVENT_HISTORY_KEEP]
        if ally:
            memory.ally_history.insert(0, ally)
            memory.ally_history = memory.ally_history[:ALLY_HISTORY_KEEP]
        # scenario_tags is a list — accept either list or comma-separated string
        if isinstance(scenario_tags, str):
            scenario_tags = [t.strip() for t in scenario_tags.split(",") if t.strip()]
        if isinstance(scenario_tags, list):
            for tag in scenario_tags:
                if isinstance(tag, str) and tag.strip():
                    memory.scenario_history.insert(0, tag.strip())
            memory.scenario_history = memory.scenario_history[:SCENARIO_HISTORY_KEEP]

        score = job.get("score")
        if isinstance(score, (int, float)):
            memory.score_history.append({
                "episode_id": job.get("episode_id"),
                "score":      float(score),
                "round":      job.get("round"),
                "friend":     friend_id,
                "pillar":     pillar,
                "at":         datetime.now().isoformat(timespec="seconds"),
            })
            memory.score_history = memory.score_history[-SCORE_HISTORY_KEEP:]

        memory.last_run_at = datetime.now().isoformat(timespec="seconds")

        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(memory.to_dict(), indent=2))
        print(f"[memory] saved → {MEMORY_FILE.name}")
    except Exception as e:
        print(f"[memory] save failed (continuing): {e}")


# ─── Cooldown queries (used by Agent 2 — logical_gate.py) ────────────────────

def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return (date.today() - date.fromisoformat(iso)).days
    except Exception:
        return None


def friend_on_cooldown(memory: MemoryState, friend_id: str) -> bool:
    days = _days_since(memory.friend_cooldowns.get(friend_id))
    return days is not None and days < FRIEND_COOLDOWN_DAYS


def enemy_on_cooldown(memory: MemoryState, enemy: str) -> bool:
    """Same enemy cannot appear in 2 consecutive scripts."""
    return bool(memory.enemy_history) and memory.enemy_history[0] == enemy


def event_on_cooldown(memory: MemoryState, event: str) -> bool:
    """Same event cannot anchor 2 consecutive scripts."""
    return bool(memory.event_history) and memory.event_history[0] == event


def ally_on_cooldown(memory: MemoryState, ally: str) -> bool:
    """Same ally cannot appear in 2 consecutive scripts."""
    return bool(memory.ally_history) and memory.ally_history[0] == ally


def scenario_on_cooldown(memory: MemoryState, tag: str) -> bool:
    """Same scenario tag cannot repeat within the last SCENARIO_WINDOW scripts."""
    recent = memory.scenario_history[:SCENARIO_WINDOW]
    return tag in recent


def pillar_overused(memory: MemoryState, pillar: int) -> bool:
    """Pillar would exceed PILLAR_MAX_IN_WINDOW in the last PILLAR_WINDOW scripts."""
    window = memory.pillar_sequence[-(PILLAR_WINDOW - 1):]
    return window.count(pillar) >= PILLAR_MAX_IN_WINDOW


# ─── Prompt block (consumed by Agent 3 — strategy.py) ────────────────────────

def get_memory_context(memory: MemoryState) -> str:
    """
    Formatted prompt block injected into the strategy director's system prompt.
    Returns an empty string when memory is empty.
    """
    if not (memory.friend_cooldowns or memory.pillar_sequence or memory.score_history
            or memory.ally_history or memory.scenario_history
            or memory.enemy_history or memory.event_history):
        return ""

    lines: list[str] = ["MEMORY CONTEXT (rotation guidance — soft, advisory):"]

    if memory.friend_cooldowns:
        cd = []
        for fid, iso in sorted(memory.friend_cooldowns.items()):
            d = _days_since(iso)
            if d is None:
                continue
            tag = "ON COOLDOWN" if d < FRIEND_COOLDOWN_DAYS else "available"
            cd.append(f"  - {fid}: last used {d}d ago ({tag})")
        if cd:
            lines.append("Friend cooldowns:")
            lines.extend(cd)

    if memory.pillar_sequence:
        recent = memory.pillar_sequence[-PILLAR_WINDOW:]
        lines.append(f"Recent pillar sequence (last {PILLAR_WINDOW}): {recent}")

    if memory.enemy_history:
        lines.append(f"Last enemy used: {memory.enemy_history[0]} (do not repeat consecutively)")
    if memory.event_history:
        lines.append(f"Last calendar event used: {memory.event_history[0]} (do not repeat consecutively)")
    if memory.ally_history:
        lines.append(f"Last ally used: {memory.ally_history[0]} (do not repeat consecutively)")
    if memory.scenario_history:
        recent_tags = memory.scenario_history[:SCENARIO_WINDOW]
        lines.append(
            f"Recent scenario tags (last {SCENARIO_WINDOW}, do NOT repeat any): "
            f"{', '.join(recent_tags)}"
        )

    if memory.score_history:
        recent = memory.score_history[-5:]
        avg = sum(s["score"] for s in recent) / len(recent)
        trend = " → ".join(f"{s['score']:.2f}" for s in recent)
        lines.append(f"Score trend (last {len(recent)}): {trend}  (avg {avg:.2f})")
        if avg < 9.5:
            lines.append("  ⚠ trend below 9.5 — sharpen director note this round")

    return "\n".join(lines)


# ─── CLI inspection ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    m = load_memory()
    print(json.dumps(m.to_dict(), indent=2))
    print("\n— context —\n")
    print(get_memory_context(m) or "(empty)")
