"""
briefs_sync.py — push briefs to the Airtable Briefs table.

Two entry points:

1. push_brief_for_job(job) — called from run.py at the end of a successful
   write so the produced script's brief lands on the production calendar
   with script_produced=true.

2. backfill() — walks Scripts/Day */*.json and upserts every existing
   produced script's brief into the Briefs table. Idempotent — re-running
   updates existing rows in place. The user-controlled `verdict` and
   `notes` fields are NEVER overwritten on update.

CLI:
    python3 briefs_sync.py                    # backfill all Day folders
    python3 briefs_sync.py --list             # list Briefs rows
    python3 briefs_sync.py --list --pending   # only verdict=unreviewed
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from network_probe import require_host

load_dotenv(Path(__file__).parent.parent / ".env")

AIRTABLE_PAT     = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
BRIEFS_TABLE     = "Briefs"
BASE_DIR         = Path(__file__).parent
LOCAL_BRIEFS_FILE = BASE_DIR / "data" / "briefs_local.json"

# Fields the pipeline owns. We always overwrite these on update.
# `verdict`, `notes`, `rewrite_notes`, and any user-edited free-form fields
# are NEVER touched on update.
PIPELINE_OWNED_FIELDS = {
    "generated_at", "mode", "slot", "friend", "pillar", "city",
    "calendar_event", "enemy", "enemy_failure_mode",
    "ally", "tone", "target_duration_seconds", "sensory_hook",
    "trend_anchor", "director_note", "target_date", "brief_json",
    "writer_prompt_preview", "script_produced", "episode_id",
    "regeneration_count", "scenario_tags",
    "chosen_hook_id", "chosen_hook_text", "chosen_hook_doctrine",
}


def _table():
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError(
            "Airtable not configured. Set AIRTABLE_PAT and AIRTABLE_BASE_ID "
            "in Bellaciao Content/.env"
        )
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT).table(AIRTABLE_BASE_ID, BRIEFS_TABLE)


def _read_local_records() -> list[dict]:
    if not LOCAL_BRIEFS_FILE.exists():
        return []
    try:
        payload = json.loads(LOCAL_BRIEFS_FILE.read_text())
    except Exception:
        return []
    records = payload.get("records") if isinstance(payload, dict) else payload
    return records or []


def _write_local_records(records: list[dict]) -> None:
    LOCAL_BRIEFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_BRIEFS_FILE.write_text(json.dumps({"records": records}, indent=2))


def _local_row(record: dict) -> dict:
    out = dict(record.get("fields") or {})
    out["_record_id"] = record.get("id") or f"local:{out.get('run_id', 'unknown')}"
    return out


def _sorted_local_rows() -> list[dict]:
    rows = [_local_row(r) for r in _read_local_records()]
    rows.sort(key=lambda r: r.get("generated_at") or "", reverse=True)
    return rows


def _upsert_local_record(fields: dict, record_id: Optional[str] = None) -> str:
    fields = {k: v for k, v in fields.items() if k != "_record_id"}
    records = _read_local_records()
    run_id = fields.get("run_id") or "unknown"
    target = next((r for r in records if (r.get("fields") or {}).get("run_id") == run_id), None)
    if target is None and record_id:
        target = next((r for r in records if r.get("id") == record_id), None)

    if target is None:
        rid = record_id or f"local:{run_id}"
        records.append({"id": rid, "fields": dict(fields)})
        _write_local_records(records)
        return rid

    merged = dict(target.get("fields") or {})
    merged.update(fields)
    target["id"] = record_id or target.get("id") or f"local:{run_id}"
    target["fields"] = merged
    _write_local_records(records)
    return target["id"]


def _local_match(
    predicate,
    *,
    limit: int = 1,
) -> list[dict]:
    out: list[dict] = []
    for row in _sorted_local_rows():
        if predicate(row):
            out.append(row)
            if len(out) >= limit:
                break
    return out


def _run_id_for(brief: dict, generated_at: str, target_date: Optional[str] = None) -> str:
    """
    Stable run_id derived from friend + slot + target_date.

    The slot (story|reel) is part of the id so the day's two briefs
    (one story + one reel for the same friend) don't collide on upsert.
    target_date is used instead of the generation timestamp so re-running
    --stage brief for the same date upserts in place rather than spawning
    a new row every time.
    """
    friend = brief.get("friend", "unknown")
    slot   = (brief.get("format") or "reel").lower()
    if not target_date:
        target_date = (generated_at or "")[:10] or "nodate"
    return f"brief_{friend}_{slot}_{target_date}"


def _brief_to_fields(
    brief: dict,
    generated_at: str,
    target_date: Optional[str],
    episode_id: Optional[str] = None,
    script_produced: bool = False,
    writer_prompt_preview: str = "",
    regeneration_count: int = 0,
) -> dict:
    """Convert a brief dict into Airtable field values."""
    # target_date: prefer explicit, else fall back to the date portion of generated_at
    if not target_date:
        target_date = (generated_at or "")[:10]

    # The Briefs.city select uses pretty case (Melbourne / New York / London).
    # The brief itself stores it the same way already, but normalise just in case.
    city_raw = brief.get("city", "")
    city_map = {
        "melbourne": "Melbourne",
        "new york": "New York",
        "new york city": "New York",
        "nyc": "New York",
        "london": "London",
    }
    city = city_map.get(city_raw.lower(), city_raw)

    # scenario_tags is stored in Airtable as a single comma-separated line
    # (not multi-select) because the tag vocabulary is open-ended — the
    # strategy director invents fresh kebab-case tags per brief. Same
    # gotcha as calendar_event: do NOT turn this into Single select.
    scenario_tags_raw = brief.get("scenario_tags") or []
    if isinstance(scenario_tags_raw, str):
        scenario_tags_str = scenario_tags_raw
    elif isinstance(scenario_tags_raw, list):
        scenario_tags_str = ", ".join(
            str(t).strip() for t in scenario_tags_raw if str(t).strip()
        )
    else:
        scenario_tags_str = ""

    return {
        "generated_at":         generated_at,
        "target_date":          target_date,
        "slot":                 (brief.get("format") or "reel").lower(),
        "mode":                 brief.get("mode") or "generic",
        "friend":               brief.get("friend"),
        "pillar":               brief.get("pillar"),
        "city":                 city,
        "calendar_event":       brief.get("calendar_event") or "",
        "enemy":                brief.get("enemy") or "",
        "enemy_failure_mode":   brief.get("enemy_failure_mode") or "",
        "ally":                 brief.get("ally") or "",
        "tone":                 brief.get("tone") or "",
        "target_duration_seconds": brief.get("target_duration_seconds"),
        "sensory_hook":         brief.get("sensory_hook") or "",
        "trend_anchor":         brief.get("trend_anchor") or "",
        "director_note":        brief.get("director_note") or "",
        "brief_json":           json.dumps(brief, indent=2),
        "writer_prompt_preview": writer_prompt_preview,
        "script_produced":      script_produced,
        "episode_id":           episode_id or "",
        "regeneration_count":   regeneration_count,
        "scenario_tags":        scenario_tags_str,
        "chosen_hook_id":       brief.get("chosen_hook_id") or 0,
        "chosen_hook_text":     brief.get("chosen_hook_text", ""),
        "chosen_hook_doctrine": brief.get("chosen_hook_doctrine", ""),
    }


def push_brief(
    brief: dict,
    *,
    generated_at: str,
    target_date: Optional[str] = None,
    episode_id: Optional[str] = None,
    script_produced: bool = False,
    writer_prompt_preview: str = "",
    initial_verdict: Optional[str] = None,
    regeneration_count: int = 0,
    reset_verdict_on_update: bool = False,
) -> str:
    """
    Upsert a brief into Airtable by run_id.

    On UPDATE we never touch verdict/notes/rewrite_notes by default — those
    are user-owned. EXCEPT: if `reset_verdict_on_update` is True (used by the
    rewrite loop), we DO write verdict='unreviewed' so the regenerated brief
    re-enters review.

    On CREATE we set verdict to `initial_verdict` if given.

    Returns the Airtable record id.
    """
    run_id = _run_id_for(brief, generated_at, target_date)
    fields = _brief_to_fields(
        brief,
        generated_at=generated_at,
        target_date=target_date,
        episode_id=episode_id,
        script_produced=script_produced,
        writer_prompt_preview=writer_prompt_preview,
        regeneration_count=regeneration_count,
    )
    fields["run_id"] = run_id

    # Drop None values — Airtable rejects them
    fields = {k: v for k, v in fields.items() if v is not None}

    existing_local = next(
        (r for r in _read_local_records() if (r.get("fields") or {}).get("run_id") == run_id),
        None,
    )
    existing_local_fields = dict((existing_local or {}).get("fields") or {})
    if reset_verdict_on_update:
        fields["verdict"] = "unreviewed"
    elif initial_verdict and "verdict" not in fields and not existing_local_fields.get("verdict"):
        fields["verdict"] = initial_verdict
    elif existing_local_fields.get("verdict") and "verdict" not in fields:
        fields["verdict"] = existing_local_fields["verdict"]

    try:
        tbl = _table()
        existing = tbl.all(formula=f"{{run_id}} = '{run_id}'")
        if existing:
            # Update — keep only pipeline-owned fields
            update_fields = {k: v for k, v in fields.items() if k in PIPELINE_OWNED_FIELDS}
            if reset_verdict_on_update:
                update_fields["verdict"] = "unreviewed"
            rec = tbl.update(existing[0]["id"], update_fields)
        else:
            if initial_verdict:
                fields["verdict"] = initial_verdict
            rec = tbl.create(fields)
        rec_id = rec["id"]
    except Exception:
        rec_id = existing_local.get("id") if existing_local else None

    return _upsert_local_record(fields, rec_id)


def push_brief_for_job(job: dict, writer_prompt_preview: str = "") -> str:
    """
    Convenience wrapper for run.py --auto / legacy flow — push a brief from
    a finished job dict.

    The brief is treated as `script_produced=true` and given verdict=good
    on first creation, since by the time run.py calls this the script has
    already been written and approved by the supervisor.
    """
    brief        = job.get("brief", {}) or {}
    episode_id   = job.get("episode_id", "")
    generated_at = job.get("generated_at") or datetime.now().isoformat(timespec="seconds")
    target_date  = (job.get("gate_result") or {}).get("target_date") or job.get("target_date")
    return push_brief(
        brief,
        generated_at=generated_at,
        target_date=target_date,
        episode_id=episode_id,
        script_produced=True,
        writer_prompt_preview=writer_prompt_preview,
        initial_verdict="good",
    )


def preview_brief(
    brief: dict,
    *,
    target_date: str,
    writer_prompt_preview: str,
    regeneration_count: int = 0,
    is_regeneration: bool = False,
) -> str:
    """
    Push a brief to Airtable for HUMAN REVIEW before any script is generated.

    This is the staged-workflow path: --stage brief calls this and exits.
    The user reviews subjects, locations, director_note, and the
    full writer_prompt_preview in Airtable, then sets verdict=good. Only then
    does --stage write proceed to call the writers.

    `script_produced` is False because no script exists yet.

    When `is_regeneration` is True (called from the rewrite loop), the existing
    row's verdict is reset to 'unreviewed' so the user re-reviews the new
    version.

    Returns the Airtable record id.
    """
    return push_brief(
        brief,
        generated_at            = datetime.now().isoformat(timespec="seconds"),
        target_date             = target_date,
        episode_id              = "",
        script_produced         = False,
        writer_prompt_preview   = writer_prompt_preview,
        initial_verdict         = "unreviewed",
        regeneration_count      = regeneration_count,
        reset_verdict_on_update = is_regeneration,
    )


def fetch_brief_pending_rewrite(target_date: str, slot: str) -> Optional[dict]:
    """
    Read the brief row for (target_date, slot) where verdict='rewrite_needed'.

    Used by --stage brief: when the user marks a brief rewrite_needed and
    re-runs --stage brief, we pull the rewrite_notes and regeneration_count
    from this row to feed the strategy director.

    Returns the row dict (with airtable record id under '_record_id'), or None.
    """
    formula = (
        f"AND({{target_date}} = '{target_date}', "
        f"{{slot}} = '{slot}', "
        f"{{verdict}} = 'rewrite_needed')"
    )
    try:
        tbl = _table()
        recs = tbl.all(formula=formula, sort=["-generated_at"], max_records=1)
        if recs:
            out = dict(recs[0]["fields"])
            out["_record_id"] = recs[0]["id"]
            _upsert_local_record(out, recs[0]["id"])
            return out
    except Exception:
        pass
    rows = _local_match(
        lambda r: (
            r.get("target_date") == target_date
            and r.get("slot") == slot
            and r.get("verdict") == "rewrite_needed"
        ),
        limit=1,
    )
    return rows[0] if rows else None


def fetch_approved_brief_for_date(
    target_date: str,
    slot: Optional[str] = None,
) -> Optional[dict]:
    """
    Read the most recent verdict=good brief for a given target_date.

    If `slot` is provided, filter to that slot ('story' or 'reel'). Without a
    slot, returns the newest approved brief regardless of slot — but the
    write stage should ALWAYS pass slot to avoid ambiguity (a day has both
    a story and a reel brief).

    Returns the row dict (with airtable record id under '_record_id'), or None.
    """
    if slot:
        formula = (
            f"AND({{target_date}} = '{target_date}', "
            f"{{slot}} = '{slot}', "
            f"{{verdict}} = 'good')"
        )
    else:
        formula = (
            f"AND({{target_date}} = '{target_date}', {{verdict}} = 'good')"
        )
    try:
        tbl = _table()
        recs = tbl.all(formula=formula, sort=["-generated_at"], max_records=1)
        if recs:
            out = dict(recs[0]["fields"])
            out["_record_id"] = recs[0]["id"]
            _upsert_local_record(out, recs[0]["id"])
            return out
    except Exception:
        pass
    rows = _local_match(
        lambda r: (
            r.get("target_date") == target_date
            and (slot is None or r.get("slot") == slot)
            and r.get("verdict") == "good"
        ),
        limit=1,
    )
    return rows[0] if rows else None


def fetch_any_brief_for_date(
    target_date: str,
    slot: Optional[str] = None,
) -> Optional[dict]:
    """
    Read the most recent brief for a given target_date REGARDLESS of verdict.
    Used by `--stage write --force` and `--stage play` so the write stage can
    pick up a freshly-generated brief that's still verdict=unreviewed.
    """
    if slot:
        formula = (
            f"AND({{target_date}} = '{target_date}', {{slot}} = '{slot}')"
        )
    else:
        formula = f"{{target_date}} = '{target_date}'"
    try:
        tbl = _table()
        recs = tbl.all(formula=formula, sort=["-generated_at"], max_records=1)
        if recs:
            out = dict(recs[0]["fields"])
            out["_record_id"] = recs[0]["id"]
            _upsert_local_record(out, recs[0]["id"])
            return out
    except Exception:
        pass
    rows = _local_match(
        lambda r: (
            r.get("target_date") == target_date
            and (slot is None or r.get("slot") == slot)
        ),
        limit=1,
    )
    return rows[0] if rows else None


def fetch_brief_by_record_id(record_id: str) -> Optional[dict]:
    """Read a single brief row by its Airtable record id (rec...)."""
    local = next((r for r in _sorted_local_rows() if r.get("_record_id") == record_id), None)
    if record_id.startswith("local:") and local:
        return local

    try:
        tbl = _table()
        rec = tbl.get(record_id)
    except Exception:
        return local
    out = dict(rec["fields"])
    out["_record_id"] = rec["id"]
    _upsert_local_record(out, rec["id"])
    return out


def parse_brief_json(brief_row: dict) -> Optional[dict]:
    """Pull the original brief dict back out of a Briefs row's brief_json field."""
    raw = brief_row.get("brief_json")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def mark_brief_episode(record_id: str, episode_id: str) -> None:
    """After --stage write succeeds, stamp the brief row with the episode it produced."""
    try:
        tbl = _table()
        if not str(record_id).startswith("local:"):
            tbl.update(record_id, {
                "episode_id":      episode_id,
                "script_produced": True,
            })
    except Exception as e:
        print(f"[briefs] mark_episode failed: {e}")

    records = _read_local_records()
    touched = False
    for rec in records:
        if rec.get("id") != record_id:
            continue
        fields = dict(rec.get("fields") or {})
        fields["episode_id"] = episode_id
        fields["script_produced"] = True
        rec["fields"] = fields
        touched = True
        break
    if touched:
        _write_local_records(records)


# ─── Backfill ────────────────────────────────────────────────────────────────

def backfill(scripts_root: Path) -> dict:
    """Walk Scripts/Day */*.json and push every brief to Airtable."""
    pushed, skipped = 0, 0
    errors: list[str] = []

    if not scripts_root.exists():
        return {"pushed": 0, "skipped": 0, "errors": [f"missing dir: {scripts_root}"]}

    for day_dir in sorted(scripts_root.glob("Day */scripts")):
        for job_file in sorted(day_dir.glob("*.json")):
            try:
                job = json.loads(job_file.read_text())
            except Exception as e:
                errors.append(f"{job_file.name}: parse failed — {e}")
                skipped += 1
                continue

            brief = job.get("brief")
            if not brief:
                skipped += 1
                continue

            try:
                rec = push_brief_for_job(job)
                print(f"  {day_dir.parent.name}/{job_file.name} → {rec}")
                pushed += 1
            except Exception as e:
                errors.append(f"{job_file.name}: {e}")
                skipped += 1

    return {"pushed": pushed, "skipped": skipped, "errors": errors}


# ─── Listing ─────────────────────────────────────────────────────────────────

def list_briefs(verdict: Optional[str] = None, limit: int = 100) -> list[dict]:
    formula = f"{{verdict}} = '{verdict}'" if verdict else None
    try:
        tbl = _table()
        recs = tbl.all(formula=formula, sort=["target_date"], max_records=limit)
        for rec in recs:
            _upsert_local_record(rec["fields"], rec["id"])
        return [r["fields"] for r in recs]
    except Exception:
        rows = _sorted_local_rows()
        if verdict:
            rows = [r for r in rows if (r.get("verdict") or "") == verdict]
        return [{k: v for k, v in r.items() if k != "_record_id"} for r in rows[:limit]]


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Backfill / list the Briefs Airtable table")
    p.add_argument("--list", action="store_true", help="list Briefs rows instead of backfilling")
    p.add_argument("--pending", action="store_true",
                   help="with --list, only show verdict=unreviewed")
    p.add_argument("--scripts-root", type=Path,
                   default=Path(__file__).parent.parent / "Creatives" / "Daily assets",
                   help="root folder containing Day N/ subfolders")
    args = p.parse_args()

    if args.list:
        rows = list_briefs(verdict="unreviewed" if args.pending else None)
        if not rows:
            print("(no rows)")
            return
        print(f"{'target_date':12}  {'friend':12}  {'p':2}  "
              f"{'verdict':14}  {'produced':9}  episode")
        print("-" * 80)
        for r in rows:
            produced = "✓" if r.get("script_produced") else "·"
            print(
                f"{(r.get('target_date') or '')[:12]:12}  "
                f"{(r.get('friend') or '')[:12]:12}  "
                f"{r.get('pillar','?'):<2}  "
                f"{(r.get('verdict') or '?'):14}  "
                f"{produced:9}  "
                f"{r.get('episode_id','')}"
            )
        return

    print(f"Backfilling Briefs from {args.scripts_root}...")
    result = backfill(args.scripts_root)
    print(f"\n  pushed : {result['pushed']}")
    print(f"  skipped: {result['skipped']}")
    if result["errors"]:
        print("\nErrors:")
        for e in result["errors"]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
