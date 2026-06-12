"""
continuity.py — Continuity Director agent.

Maintains a per-friend narrative state so every Bella video picks up where
the last one left off, like a sitcom or a serialised Disney story. Runs AFTER
a script is approved by the Quality Supervisor — reads the approved script,
asks Claude Haiku to extract the arc update + inventory, and persists the
new state to `data/continuity_state.json`.

The state file is then injected into the strategy director's prompt on the
NEXT brief generation for that friend, so the director knows what just
happened and can advance the arc instead of resetting it.

This module is the "open series" shape the user asked for:
  - Narrative accumulates forever (no auto-resets)
  - One paragraph of arc + a structured inventory per friend
  - Manual resets only (edit the JSON or run --reset <friend_id>)
  - Per-friend state only — no channel-wide theme tracking (kept simple;
    channel-level arcs can be layered on later without a migration)

Reference: memory/continuity_system.md (added in Commit 2 of the staged
workflow design conversation, 2026-04-11).

Public API:
  load_state()                           → ContinuityState
  get_continuity_context(friend_id)      → str (prompt block) or ""
  update_state_from_job(job)             → None (best-effort, never raises)
  reset_friend(friend_id)                → None (wipes that friend's entry)

CLI:
  python3 continuity.py                  # dump full state
  python3 continuity.py --show jake      # show jake's arc + inventory
  python3 continuity.py --reset jake     # wipe jake's state
  python3 continuity.py --reset-all      # wipe everything
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

# Shared .env at the Bellaciao Content/ level — same file every project uses.
load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR    = Path(__file__).parent
STATE_FILE  = BASE_DIR / "data" / "continuity_state.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Haiku is deliberate — the extraction task is structured and cheap. Don't
# upgrade this to Sonnet/Opus without a good reason; it runs on every approved
# script and cost adds up.
MODEL_HAIKU = "claude-haiku-4-5-20251001"

# Cap how much of each friend's inventory we keep. Older entries fall off the
# end. These are soft caps — a friend with 50 beaten enemies over 6 months is
# not useful context; the strategy director only needs "what Jake recently
# beat" to avoid repetition.
ARC_MAX_CHARS         = 1200
INVENTORY_MAX_ITEMS   = 15


# ─── State shape ─────────────────────────────────────────────────────────────

@dataclass
class FriendState:
    """Per-friend narrative state."""
    arc: str                       = ""     # 3-5 sentence paragraph
    beaten_enemies: list[dict]     = field(default_factory=list)
    earned_elixirs: list[dict]     = field(default_factory=list)
    unresolved: list[str]          = field(default_factory=list)
    episode_count: int             = 0
    last_episode_id: str           = ""
    last_updated: str              = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "FriendState":
        return cls(
            arc             = raw.get("arc", "") or "",
            beaten_enemies  = list(raw.get("beaten_enemies") or []),
            earned_elixirs  = list(raw.get("earned_elixirs") or []),
            unresolved      = list(raw.get("unresolved") or []),
            episode_count   = int(raw.get("episode_count", 0) or 0),
            last_episode_id = raw.get("last_episode_id", "") or "",
            last_updated    = raw.get("last_updated", "") or "",
        )


@dataclass
class ContinuityState:
    """Whole channel state — dict of friend_id → FriendState."""
    friends: dict[str, FriendState]  = field(default_factory=dict)
    last_updated: str                = ""

    def to_dict(self) -> dict:
        return {
            "friends":      {k: v.to_dict() for k, v in self.friends.items()},
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "ContinuityState":
        friends = {
            fid: FriendState.from_dict(fdata)
            for fid, fdata in (raw.get("friends") or {}).items()
        }
        return cls(friends=friends, last_updated=raw.get("last_updated", ""))


# ─── Load / save ─────────────────────────────────────────────────────────────

def load_state() -> ContinuityState:
    """Never raises. Returns empty state if file missing or corrupted."""
    try:
        if not STATE_FILE.exists():
            return ContinuityState()
        return ContinuityState.from_dict(json.loads(STATE_FILE.read_text()))
    except Exception as e:
        print(f"[continuity] load failed (using empty state): {e}")
        return ContinuityState()


def save_state(state: ContinuityState) -> None:
    """Persist state to disk. Never raises."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[continuity] save failed (continuing): {e}")


# ─── Prompt block for the strategy director ─────────────────────────────────

def get_continuity_context(friend_id: str) -> str:
    """
    Return a formatted prompt block for the strategy director, describing
    where `friend_id` currently is in their arc. Empty string if no state
    exists for that friend (first time appearing, or manually reset).
    """
    if not friend_id:
        return ""
    state = load_state()
    fs    = state.friends.get(friend_id)
    if not fs or (not fs.arc and not fs.beaten_enemies and not fs.earned_elixirs):
        return ""

    lines: list[str] = [
        f"CONTINUITY — WHERE {friend_id.upper()} IS RIGHT NOW",
        f"(accumulated across {fs.episode_count} previous approved episode"
        f"{'s' if fs.episode_count != 1 else ''})",
        "",
    ]
    if fs.arc:
        lines.append("Arc so far:")
        lines.append(f"  {fs.arc}")
        lines.append("")

    if fs.beaten_enemies:
        lines.append(f"Enemies {friend_id} has already beaten (do NOT repeat):")
        for e in fs.beaten_enemies[-INVENTORY_MAX_ITEMS:]:
            enemy_key = e.get("enemy", "?")
            how       = e.get("how", "")
            ep        = e.get("episode", "")
            line = f"  - {enemy_key}"
            if how:
                line += f" ({how})"
            if ep:
                line += f" [ep: {ep}]"
            lines.append(line)
        lines.append("")

    if fs.earned_elixirs:
        lines.append(f"Elixirs {friend_id} has already found (do NOT repeat):")
        for el in fs.earned_elixirs[-INVENTORY_MAX_ITEMS:]:
            text = el.get("elixir", "?")
            ep   = el.get("episode", "")
            line = f"  - {text}"
            if ep:
                line += f" [ep: {ep}]"
            lines.append(line)
        lines.append("")

    if fs.unresolved:
        lines.append("Unresolved threads (still alive — reference if the moment is right):")
        for u in fs.unresolved[-INVENTORY_MAX_ITEMS:]:
            lines.append(f"  - {u}")
        lines.append("")

    lines.append("This brief must ADVANCE the arc, not restart it. Pick an enemy")
    lines.append("this friend hasn't beaten yet. Pick an elixir they haven't")
    lines.append("found yet. Do NOT reset them to their 'usual' state — whatever")
    lines.append("happened last episode still matters.")

    return "\n".join(lines)


# ─── Update state from an approved job (Haiku-driven extraction) ─────────────

_UPDATE_PROMPT = """You are the Continuity Director for the Bella content engine.
Bella is a hospitality-kid mentor — the friend who figured out Google
for restaurants. Her content is a serialised conversation with her
three circles of friends across NYC, Melbourne, and London. Every
approved video adds to a per-friend arc.

Your job: read the approved script below and update the narrative state for
{friend_id}. You are extracting structured continuity data, not critiquing.

═══════════════════════════════════════════════════════════════════════════
CURRENT STATE FOR {friend_id} (before this episode)
═══════════════════════════════════════════════════════════════════════════
{current_state}

═══════════════════════════════════════════════════════════════════════════
THE EPISODE THAT JUST WAS APPROVED
═══════════════════════════════════════════════════════════════════════════
Episode ID  : {episode_id}
Pillar      : {pillar}
Enemy       : {enemy}
Ally        : {ally}
Calendar    : {calendar_event}
Tone        : {tone}

SPOKEN SCRIPT:
{spoken}

═══════════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════════
Produce an UPDATED state for {friend_id} as strict JSON, no markdown, no
commentary. The JSON MUST have exactly these fields:

{{
  "arc": "3-5 sentence paragraph describing where {friend_id} is RIGHT NOW in their arc, including what just happened in this episode. Write in past-and-present tense (\\"Jake spent April learning... In his last episode he finally admitted... The next episode should pick up from...\\"). NOT a plot summary — a POV on where he is emotionally + narratively. Max 1200 characters.",
  "new_beaten_enemy": {{"enemy": "enemy_key", "how": "one-phrase how", "episode": "{episode_id}"}} or null if no enemy was beaten this episode,
  "new_earned_elixir": {{"elixir": "short phrase naming the elixir concretely", "episode": "{episode_id}"}} or null if no elixir was earned,
  "new_unresolved": ["short phrase", "short phrase"] — 0-3 unresolved threads THIS episode leaves for future episodes. Empty list if everything wraps cleanly.,
  "resolved_unresolved_ids": [0, 2] — indices from the CURRENT `unresolved` list above that THIS episode resolves. Empty list if none.
}}

RULES:
  - The "arc" field REPLACES the previous arc — rewrite it to include the new episode. Don't append.
  - Never invent facts — only pull from what's literally in the spoken script.
  - The "new_beaten_enemy" should match the enemy listed in the brief context above if the episode actually resolves it. If the enemy is named but Jake doesn't beat it, set this to null.
  - The "new_earned_elixir" is the small, human, earned closing moment — it's almost always present in an approved Bella script. But if it's not clearly there, null is fine.
  - Keep arcs in third person, narrative voice. Think "next writer" not "summary for a human".

Output ONLY the JSON object. No preamble, no explanation.
"""


def _format_current_state_for_prompt(fs: FriendState | None) -> str:
    if not fs:
        return "(no prior state — this is the first episode for this friend)"
    lines = [
        f"episode_count: {fs.episode_count}",
        f"arc: {fs.arc or '(none yet)'}",
    ]
    if fs.beaten_enemies:
        lines.append("beaten_enemies:")
        for e in fs.beaten_enemies[-INVENTORY_MAX_ITEMS:]:
            lines.append(f"  - {e.get('enemy','?')} ({e.get('how','?')}) [{e.get('episode','?')}]")
    if fs.earned_elixirs:
        lines.append("earned_elixirs:")
        for el in fs.earned_elixirs[-INVENTORY_MAX_ITEMS:]:
            lines.append(f"  - {el.get('elixir','?')} [{el.get('episode','?')}]")
    if fs.unresolved:
        lines.append("unresolved:")
        for i, u in enumerate(fs.unresolved):
            lines.append(f"  [{i}] {u}")
    return "\n".join(lines)


def _parse_update_json(raw: str) -> dict | None:
    """Parse Haiku's JSON output. Returns None on failure."""
    raw = raw.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0]
    elif raw.startswith("```"):
        raw = raw.split("```", 2)[1].split("```", 1)[0]
    raw = raw.strip()
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def update_state_from_job(job: dict) -> None:
    """
    Called after a script is approved and saved. Reads the job, asks Haiku to
    produce a state update, merges it into the per-friend state, persists.
    Never raises — continuity is best-effort.
    """
    try:
        brief      = job.get("brief") or {}
        episode_id = job.get("episode_id") or ""
        friend_id  = brief.get("friend")
        if not friend_id:
            print("[continuity] no friend in brief — skipping update")
            return
        if not episode_id:
            print("[continuity] no episode_id — skipping update")
            return

        spoken = job.get("video_script") or ""
        if not spoken.strip():
            print("[continuity] empty video_script — skipping update")
            return

        if not ANTHROPIC_API_KEY:
            print("[continuity] ANTHROPIC_API_KEY missing — skipping update")
            return

        state = load_state()
        fs    = state.friends.get(friend_id)  # may be None for first episode

        prompt = _UPDATE_PROMPT.format(
            friend_id      = friend_id,
            current_state  = _format_current_state_for_prompt(fs),
            episode_id     = episode_id,
            pillar         = brief.get("pillar", "?"),
            enemy          = brief.get("enemy", "?"),
            ally           = brief.get("ally", "?"),
            calendar_event = brief.get("calendar_event") or "(none)",
            tone           = brief.get("tone", "?"),
            spoken         = spoken[:4000],
        )

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model      = MODEL_HAIKU,
            max_tokens = 1500,
            messages   = [{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text
        update = _parse_update_json(raw)
        if not update:
            print("[continuity] Haiku returned unparseable JSON — skipping update")
            return

        # Merge into state
        if fs is None:
            fs = FriendState()
            state.friends[friend_id] = fs

        new_arc = (update.get("arc") or "").strip()
        if new_arc:
            fs.arc = new_arc[:ARC_MAX_CHARS]

        new_enemy = update.get("new_beaten_enemy")
        if isinstance(new_enemy, dict) and new_enemy.get("enemy"):
            fs.beaten_enemies.append({
                "enemy":   new_enemy.get("enemy"),
                "how":     new_enemy.get("how", ""),
                "episode": new_enemy.get("episode") or episode_id,
            })
            fs.beaten_enemies = fs.beaten_enemies[-INVENTORY_MAX_ITEMS:]

        new_elixir = update.get("new_earned_elixir")
        if isinstance(new_elixir, dict) and new_elixir.get("elixir"):
            fs.earned_elixirs.append({
                "elixir":  new_elixir.get("elixir"),
                "episode": new_elixir.get("episode") or episode_id,
            })
            fs.earned_elixirs = fs.earned_elixirs[-INVENTORY_MAX_ITEMS:]

        # Resolve previous unresolved entries — drop by index (descending so
        # indices stay valid during deletion)
        resolved_ids = update.get("resolved_unresolved_ids") or []
        if isinstance(resolved_ids, list) and resolved_ids and fs.unresolved:
            try:
                drop = sorted({int(i) for i in resolved_ids if isinstance(i, int)},
                              reverse=True)
                for i in drop:
                    if 0 <= i < len(fs.unresolved):
                        fs.unresolved.pop(i)
            except Exception:
                pass

        # Add new unresolved threads
        new_unresolved = update.get("new_unresolved") or []
        if isinstance(new_unresolved, list):
            for u in new_unresolved:
                if isinstance(u, str) and u.strip():
                    fs.unresolved.append(u.strip())
            fs.unresolved = fs.unresolved[-INVENTORY_MAX_ITEMS:]

        fs.episode_count   += 1
        fs.last_episode_id  = episode_id
        fs.last_updated     = datetime.now().isoformat(timespec="seconds")
        state.last_updated  = fs.last_updated

        save_state(state)
        print(f"[continuity] updated → {friend_id} (ep #{fs.episode_count}, "
              f"{len(fs.beaten_enemies)} beaten, {len(fs.earned_elixirs)} elixirs, "
              f"{len(fs.unresolved)} unresolved)")
    except Exception as e:
        print(f"[continuity] update failed (continuing): {e}")


# ─── Manual reset ────────────────────────────────────────────────────────────

def reset_friend(friend_id: str) -> bool:
    """Wipe a single friend's state. Returns True if they existed."""
    state = load_state()
    if friend_id not in state.friends:
        return False
    del state.friends[friend_id]
    state.last_updated = datetime.now().isoformat(timespec="seconds")
    save_state(state)
    return True


def reset_all() -> None:
    """Wipe the whole state file."""
    save_state(ContinuityState())


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Continuity Director state viewer/resetter")
    p.add_argument("--show",      metavar="FRIEND_ID",
                   help="show a specific friend's arc + inventory")
    p.add_argument("--reset",     metavar="FRIEND_ID",
                   help="wipe a specific friend's state")
    p.add_argument("--reset-all", action="store_true",
                   help="wipe the whole continuity state file")
    args = p.parse_args()

    if args.reset_all:
        reset_all()
        print("continuity state wiped")
        return

    if args.reset:
        ok = reset_friend(args.reset)
        print(f"{'reset' if ok else 'not found'}: {args.reset}")
        return

    if args.show:
        ctx = get_continuity_context(args.show)
        print(ctx or f"(no state for {args.show})")
        return

    # Default: dump full state
    state = load_state()
    print(json.dumps(state.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
