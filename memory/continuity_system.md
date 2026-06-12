---
name: Continuity Director — serialised narrative state
description: Per-friend arc memory added 2026-04-11. The Continuity Director is a post-approval agent that reads each approved script and updates a per-friend narrative state. The NEXT brief generation for that friend reads the state and advances the arc instead of resetting it.
type: project
---

# Continuity Director (added 2026-04-11, Commit 2 of the staged workflow refactor)

Bella videos are a **serialised, sitcom-style series**. Every approved episode adds to a per-friend arc. The next episode must pick up where the last one left off — different enemy, different elixir, building on what came before. Hard-reset back to the friend's "default" state is forbidden.

## The six design decisions (locked 2026-04-11)

User answers to my N1–N6 scoping questions during the design conversation:

- **N1 = open** — indefinite-run sitcom, not a fixed-length season
- **N2 = d** — per-friend LLM-generated state summary, updated after each approved script (not a rolling window of whole past scripts)
- **N3 = a** — new agent module (`continuity.py`), runs after the Quality Supervisor approves a script
- **N4 = arc+inventory** — track a narrative arc paragraph + a structured inventory of beaten enemies, earned elixirs, and unresolved threads. Bella-friend relationship evolution is explicitly OUT of scope for this first version.
- **N5 = b** — manual resets only (`python3 continuity.py --reset jake`), no surprise auto-resets
- **N6 = a** — per-friend only, no channel-wide thematic arc tracking. Channel-level arcs can be layered on later without a migration.

## What exists

### [continuity.py](../continuity.py) — new module

| Function | Purpose |
|---|---|
| `load_state()` | Reads `data/continuity_state.json`. Never raises. |
| `save_state(state)` | Persists state. Never raises. |
| `get_continuity_context(friend_id) -> str` | Returns a formatted prompt block describing where this friend is in their arc. Empty string if no state yet. |
| `update_state_from_job(job)` | **The core call**. Takes a completed job dict, asks Claude Haiku to extract the arc update, merges into state, persists. Best-effort, never raises. |
| `reset_friend(friend_id)` | Wipes one friend's state. Used for manual resets. |
| `reset_all()` | Wipes the whole state file. |

**Model**: Claude Haiku (`claude-haiku-4-5-20251001`). Cheap (~$0.003 per script). One call per approved script. Do NOT upgrade to Sonnet/Opus without a cost justification — the extraction task is structured and Haiku handles it fine.

**State file**: `data/continuity_state.json` — created on first successful update. Shape:
```jsonc
{
  "friends": {
    "jake": {
      "arc": "3-5 sentence paragraph. Present tense. Where Jake is right now, what just happened, what the next episode should do. Max 1200 chars.",
      "beaten_enemies": [
        {"enemy": "the_no_show", "how": "admitted it in the car", "episode": "bella_jake_p1_20260411_0900"}
      ],
      "earned_elixirs": [
        {"elixir": "the pour-over at 7am even when the room is empty", "episode": "bella_jake_p1_20260411_0900"}
      ],
      "unresolved": ["the Monday pattern is named but not fixed"],
      "episode_count": 1,
      "last_episode_id": "bella_jake_p1_20260411_0900",
      "last_updated": "2026-04-11T14:32:11"
    }
  },
  "last_updated": "2026-04-11T14:32:11"
}
```

**Caps**: `INVENTORY_MAX_ITEMS = 15` (per friend, per list). Older entries fall off the end. `ARC_MAX_CHARS = 1200`.

### [strategy.py](../strategy.py) — new context block

`_build_director_prompt()` takes a new `continuity_context: str` parameter and injects it as `## NARRATIVE CONTINUITY` block right after `## MEMORY CONTEXT` in the director prompt. `generate_brief()` populates it by calling `continuity.get_continuity_context(gate_result.friend_id)`. Empty string falls back to `(no prior state — this is the first episode for this friend)`.

### [run.py](../run.py) `--stage write` — post-approval hook

After the Scripts row is pushed and the brief is marked `script_produced=true`, run.py calls `continuity.update_state_from_job(job)` in a best-effort try block. Gated by new `--no-continuity` CLI flag (for testing). The call is placed AFTER the Scripts push so a failing Haiku call cannot prevent the script from landing in Airtable.

## What it explicitly does NOT do

This list is important because every one of these was discussed during design and deliberately excluded. Future sessions: do NOT add these without a user request.

- **No channel-wide theme tracking**. Only per-friend. The answer to N6 was explicit.
- **No auto-resets**. State accumulates forever until you manually reset it. The answer to N5 was explicit.
- **No full-history reads**. The director never sees the raw text of past scripts. Only the LLM-generated arc paragraph + inventory. The answer to N2 was explicit.
- **No rewrite-loop integration**. If a brief is rejected and regenerated, the continuity state is unchanged — the state only updates on APPROVED scripts. Regeneration of a rejected brief does not re-read or re-update state.
- **No Bella-friend relationship tracking**. Explicitly deferred. N4 was `arc+inventory`, not `arc+inventory+relationships`.
- **No brand.py constants**. All tunables (`INVENTORY_MAX_ITEMS`, `ARC_MAX_CHARS`, `MODEL_HAIKU`) live in `continuity.py`. Do NOT move them to `brand.py` — they're agent config, not brand bible rules.
- **No Airtable state mirror**. The state lives in `data/continuity_state.json` only. The user asked for local state in N3. An Airtable mirror could be added later for cross-device review, but it would add sync complexity that isn't justified yet.

## How it interacts with existing memory systems

There are TWO memory systems now. They are DIFFERENT and must NOT be merged:

1. **`memory.py`** — mechanical cooldown tracker. Friend/enemy/event/pillar rotation rules. Pure Python, no LLM. Advises the director with "Jake was used 2 days ago, he's on cooldown". Fast, deterministic.

2. **`continuity.py`** — narrative arc state. LLM-generated arc summaries. Tells the director "Jake just admitted his dry humor is a shield; the next episode should build on that". Slow (Haiku call), reasoning-based.

Both blocks appear in the strategy director prompt. `memory_context` injected as `## MEMORY CONTEXT (mechanical cooldowns — advisory)`. `continuity_context` injected right after as `## NARRATIVE CONTINUITY (serialised arc — where this friend is right now)`. The director is told explicitly that one is mechanical advice and the other is narrative state.

**Why keep them separate**: mechanical rules are deterministic and don't need an LLM. Narrative arcs need reasoning. Merging them would mean either (a) every cooldown check requires a Haiku call, or (b) the LLM-generated state has to also track cooldown counters. Both are worse than the split.

## How to inspect state

```bash
# Dump the whole state file as pretty JSON
python3 continuity.py

# Show one friend's arc + inventory as the director would see it
python3 continuity.py --show jake

# Wipe one friend's state (manual reset — N5=b)
python3 continuity.py --reset jake

# Nuclear — wipe everything (use only when starting over from scratch)
python3 continuity.py --reset-all
```

## How to apply

- **When adding a new friend to friends_db.json**: do nothing. `continuity.py` auto-creates an entry on their first approved script.
- **When the arc drifts wrong**: edit `data/continuity_state.json` directly. The file is human-readable JSON. Save, rerun `--stage brief`.
- **When an episode is regenerated (rewrite_needed → good)**: the continuity state updates only ONCE, when the final version is approved. Rejected intermediate versions are ignored.
- **When retiring a friend**: run `python3 continuity.py --reset <friend_id>` and remove them from the rotation in `friends_db.json`. The reset clears their accumulated state.
- **When the Haiku call fails**: the state is simply not updated. The script is still produced and approved. The next brief for that friend sees stale state (the previous episode, not the one that just failed to update). The failure is logged but non-fatal.

## The "why" for anyone auditing this later

The user explicitly asked for a sitcom/Disney-movie-style series where every episode builds on the last. Hard-resetting characters back to a default state was identified as the failure mode to avoid. The continuity director is the smallest reasonable implementation of that: one cheap LLM call per approved script, one file on disk, one prompt block injection. No new tables, no new agents beyond this one, no user-facing complexity.

If the narrative drifts wrong, the user has three levers: edit the JSON directly, reset a friend, or tighten the `_UPDATE_PROMPT` in continuity.py. All three are reversible.

## Known limitations to accept (not fix)

- **The arc paragraph is generated by Haiku and may drift over time**. After 50 episodes, Jake's arc paragraph will have been rewritten 50 times, each one based on the previous. Semantic drift is a real risk. Mitigation: the user can manually edit the arc, or reset and start over. Not worth building guardrails for until it's observed in practice.
- **The 15-item inventory cap is arbitrary**. A friend with 20+ episodes will start losing older beaten-enemy references. If this becomes a problem, raise `INVENTORY_MAX_ITEMS` or introduce tiered retention (recent in full, older summarised).
- **No enforcement**. The director is TOLD not to repeat a beaten enemy; it's not FORCED. A model can still ignore continuity context under pressure. If this happens regularly, escalate from "advisory" to a logical-gate check.
- **Continuity runs AFTER supervisor approval**, not DURING it. A script that contradicts established continuity will still pass the gates and land in Scripts/. The continuity drift is caught on the NEXT episode, not this one. Accepted trade-off for cost reasons.
