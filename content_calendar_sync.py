"""
content_calendar_sync.py — push the local content calendar to the Airtable
ContentCalendar table for human review.

The local content_calendar.py module produces a 28-row plan
(14 days × 2 slots) at data/content_calendar.json. This module flattens
those rows into the ContentCalendar Airtable table where each row carries
a `status` field (draft / planned / skip) the user manually controls.

The brief stage in run.py reads this table and REFUSES to generate a brief
for a (target_date, slot) pair unless the matching row is `status=planned`.

CLI:
    python3 content_calendar_sync.py                  # push the latest local plan
    python3 content_calendar_sync.py --list           # list current plan rows
    python3 content_calendar_sync.py --planned        # only status=planned
    python3 content_calendar_sync.py --pending        # only status=draft

Idempotent: re-running upserts by `plan_id` so existing rows update in place.
The user-controlled `status` and `notes` fields are NEVER touched on update.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from network_probe import require_host

load_dotenv(Path(__file__).parent.parent / ".env")

AIRTABLE_PAT     = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
TABLE_NAME       = "ContentCalendar"

BASE_DIR  = Path(__file__).parent
PLAN_FILE = BASE_DIR / "data" / "content_calendar.json"
PLAN_CACHE_FILE = BASE_DIR / "data" / "content_calendar_cache.json"

# Pipeline-owned fields — overwritten on update.
# User-owned fields (NEVER overwritten on update):
#   status, notes, hook_choice, pillar_choice, story_seed_choice, rejected_reason, regenerate_notes
# Special: regenerate_request is user-owned to TICK but pipeline UNTICKS it
# after honouring the request — it's a one-shot signal.
PIPELINE_OWNED_FIELDS = {
    "target_date", "slot", "day_number", "weekday", "mode",
    "calendar_event", "city", "friend",
    "duration_target", "story_seed",
    "story_seed_1", "story_seed_2", "story_seed_3",
    "sensory_hook_1", "sensory_hook_2", "sensory_hook_3",
    "pillar_1", "pillar_1_theme",
    "pillar_2", "pillar_2_theme",
    "pillar_3", "pillar_3_theme",
    "hook_1_id", "hook_1_text", "hook_1_doctrine",
    "hook_2_id", "hook_2_text", "hook_2_doctrine",
    "hook_3_id", "hook_3_text", "hook_3_doctrine",
    "research_angle", "research_gap", "research_urgency", "research_rationale",
}


def _table():
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError(
            "Airtable not configured. Set AIRTABLE_PAT and AIRTABLE_BASE_ID "
            "in Bellaciao Content/.env"
        )
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT).table(AIRTABLE_BASE_ID, TABLE_NAME)


def _write_plan_cache(records: list[dict]) -> None:
    PLAN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLAN_CACHE_FILE.write_text(json.dumps({"records": records}, indent=2))


def _read_plan_cache() -> list[dict]:
    if not PLAN_CACHE_FILE.exists():
        return []
    try:
        payload = json.loads(PLAN_CACHE_FILE.read_text())
    except Exception:
        return []
    records = payload.get("records") if isinstance(payload, dict) else payload
    out: list[dict] = []
    for rec in records or []:
        fields = dict(rec.get("fields") or {})
        if not fields:
            continue
        fields.setdefault("_record_id", rec.get("id") or f"local:{fields.get('plan_id', 'unknown')}")
        out.append(fields)
    return out


def _local_plan_rows() -> list[dict]:
    if not PLAN_FILE.exists():
        return []
    try:
        payload = json.loads(PLAN_FILE.read_text())
    except Exception:
        return []

    out: list[dict] = []
    for row in payload.get("rows") or []:
        fields = _row_to_fields(row)
        if not fields:
            continue
        for key in (
            "hook_choice",
            "pillar_choice",
            "story_seed_choice",
            "sensory_hook_choice",
            "status",
            "rejected_reason",
            "notes",
            "regenerate_request",
            "regenerate_notes",
        ):
            if key in row:
                fields[key] = row.get(key)
        fields.setdefault("status", row.get("status") or "draft")
        fields.setdefault("_record_id", f"local:{fields['plan_id']}")
        out.append(fields)
    return out


def _fallback_plan_rows() -> list[dict]:
    cached = _read_plan_cache()
    return cached or _local_plan_rows()


def _refresh_plan_cache(tbl=None) -> None:
    table = tbl or _table()
    recs = table.all(sort=["target_date", "slot"])
    _write_plan_cache([{"id": r["id"], "fields": r["fields"]} for r in recs])


# ─── Push ────────────────────────────────────────────────────────────────────

# City labels in friends_db are "Melbourne" / "New York City" / "London".
# The Airtable single-select uses "Melbourne" / "New York" / "London" to
# match the existing Briefs.city options. We normalise on the way in.
_CITY_NORMALISE = {
    "melbourne":     "Melbourne",
    "new york city": "New York",
    "new york":      "New York",
    "nyc":           "New York",
    "london":        "London",
}


def _norm_city(city: str) -> str:
    return _CITY_NORMALISE.get((city or "").lower(), city or "—")


def _plan_id(target_date: str, slot: str) -> str:
    return f"plan_{target_date}_{slot}"


def _row_to_fields(row: dict) -> dict | None:
    target_date = row.get("target_date")
    slot        = row.get("slot")
    if not (target_date and slot):
        return None

    fields = {
        "plan_id":         _plan_id(target_date, slot),
        "target_date":     target_date,
        "slot":            slot,
        "day_number":      row.get("day_number"),
        "weekday":         row.get("weekday", ""),
        "mode":            row.get("mode", "generic"),
        "calendar_event":  row.get("calendar_event", "") or "",
        "city":            _norm_city(row.get("city", "")),
        "friend":          row.get("friend_id", "") or "—",
        "duration_target": row.get("duration_target"),
        "story_seed":      row.get("story_seed", ""),
        # 3 story_seed options
        "story_seed_1":    row.get("story_seed_1", ""),
        "story_seed_2":    row.get("story_seed_2", ""),
        "story_seed_3":    row.get("story_seed_3", ""),
        # 3 sensory_hook options
        "sensory_hook_1":  row.get("sensory_hook_1", ""),
        "sensory_hook_2":  row.get("sensory_hook_2", ""),
        "sensory_hook_3":  row.get("sensory_hook_3", ""),
        # 3 pillar options
        "pillar_1":        row.get("pillar_1") or 0,
        "pillar_1_theme":  row.get("pillar_1_theme", ""),
        "pillar_2":        row.get("pillar_2") or 0,
        "pillar_2_theme":  row.get("pillar_2_theme", ""),
        "pillar_3":        row.get("pillar_3") or 0,
        "pillar_3_theme":  row.get("pillar_3_theme", ""),
        # 3 hook options
        "hook_1_id":       row.get("hook_1_id") or 0,
        "hook_1_text":     row.get("hook_1_text", ""),
        "hook_1_doctrine": row.get("hook_1_doctrine", ""),
        "hook_2_id":       row.get("hook_2_id") or 0,
        "hook_2_text":     row.get("hook_2_text", ""),
        "hook_2_doctrine": row.get("hook_2_doctrine", ""),
        "hook_3_id":       row.get("hook_3_id") or 0,
        "hook_3_text":     row.get("hook_3_text", ""),
        "hook_3_doctrine": row.get("hook_3_doctrine", ""),
        # Research enrichment (Skill 3)
        "research_angle":     row.get("research_angle", ""),
        "research_gap":       row.get("research_gap", ""),
        "research_urgency":   row.get("research_urgency", ""),
        "research_rationale": row.get("research_rationale", ""),
    }
    # Drop empty single_select fields — Airtable rejects empty strings.
    if not fields.get("research_urgency"):
        fields.pop("research_urgency", None)
    for key in ("hook_1_doctrine", "hook_2_doctrine", "hook_3_doctrine"):
        if not fields.get(key):
            fields.pop(key, None)
    return fields


def push_plan_rows(rows: list[dict], honour_regenerate: bool = True) -> dict:
    """
    Upsert a list of plan rows into the ContentCalendar table.

    `rows` is the list-of-dicts shape from content_calendar.json
    (CalendarRow.to_dict() format).

    When `honour_regenerate` is True (default), rows where the existing
    Airtable row has `regenerate_request=true` get their hooks RE-ROLLED
    even if they're already populated. The pipeline then UNTICKS the request
    on the same update so it doesn't fire again next run.

    Rows with `status=planned` are NEVER touched — locked rows are immutable.

    Returns: {"created": N, "updated": N, "regenerated": N, "locked": N, "errors": [...]}
    """
    tbl = _table()

    # Pre-fetch existing rows so we upsert in one round-trip
    existing = tbl.all()
    by_id: dict[str, dict] = {}
    for r in existing:
        pid = r["fields"].get("plan_id")
        if pid:
            by_id[pid] = r

    created, updated, regenerated, locked, skipped = 0, 0, 0, 0, 0
    errors: list[str] = []

    for row in rows:
        fields = _row_to_fields(row)
        if not fields:
            skipped += 1
            continue
        # Drop None values — Airtable rejects them
        fields = {k: v for k, v in fields.items() if v is not None}

        pid = fields["plan_id"]
        try:
            if pid in by_id:
                existing_row = by_id[pid]
                ex_fields = existing_row["fields"]
                # Locked rows are immutable
                if ex_fields.get("status") == "planned":
                    locked += 1
                    continue

                regen_requested = bool(ex_fields.get("regenerate_request"))
                # Always update pipeline-owned fields
                update_fields = {k: v for k, v in fields.items() if k in PIPELINE_OWNED_FIELDS or k == "plan_id"}

                if honour_regenerate and regen_requested:
                    # Honour the request — untick it on the update
                    update_fields["regenerate_request"] = False
                    regenerated += 1
                else:
                    # Don't re-roll already-populated hooks unless requested
                    if ex_fields.get("hook_1_text"):
                        for k in ("hook_1_id","hook_1_text","hook_1_doctrine",
                                  "hook_2_id","hook_2_text","hook_2_doctrine",
                                  "hook_3_id","hook_3_text","hook_3_doctrine"):
                            update_fields.pop(k, None)
                    updated += 1

                tbl.update(existing_row["id"], update_fields)
            else:
                fields["status"] = "draft"
                tbl.create(fields)
                created += 1
        except Exception as e:
            errors.append(f"{pid}: {e}")
            skipped += 1

    try:
        _refresh_plan_cache(tbl)
    except Exception:
        pass

    return {
        "created":     created,
        "updated":     updated,
        "regenerated": regenerated,
        "locked":      locked,
        "skipped":     skipped,
        "errors":      errors,
        "total":       len(rows),
    }


def push_latest_local() -> dict:
    """Convenience: push whatever content_calendar.py last wrote."""
    if not PLAN_FILE.exists():
        return {"created": 0, "updated": 0, "skipped": 0,
                "errors": [f"missing local file: {PLAN_FILE}"]}
    payload = json.loads(PLAN_FILE.read_text())
    rows = payload.get("rows") or []
    return push_plan_rows(rows)


# ─── Fetch (used by run.py --stage brief to gate on planned status) ─────────

def fetch_planned_row(target_date: str, slot: str) -> Optional[dict]:
    """
    Read the ContentCalendar row for a (target_date, slot) pair where
    status='planned'. Returns the fields dict (with airtable record id under
    '_record_id'), or None if no planned row exists.
    """
    pid = _plan_id(target_date, slot)
    formula = f"AND({{plan_id}} = '{pid}', {{status}} = 'planned')"
    try:
        tbl = _table()
        recs = tbl.all(formula=formula, max_records=1)
        if recs:
            try:
                _refresh_plan_cache(tbl)
            except Exception:
                pass
            out = dict(recs[0]["fields"])
            out["_record_id"] = recs[0]["id"]
            return out
    except Exception:
        pass

    for row in _fallback_plan_rows():
        if (
            row.get("plan_id") == pid
            and (row.get("status") or "draft") == "planned"
        ):
            out = dict(row)
            out.setdefault("_record_id", f"local:{pid}")
            return out
    return None


def list_plan(status: Optional[str] = None, limit: int = 200) -> list[dict]:
    formula = f"{{status}} = '{status}'" if status else None
    try:
        tbl = _table()
        recs = tbl.all(formula=formula, sort=["target_date", "slot"], max_records=limit)
        try:
            _refresh_plan_cache(tbl)
        except Exception:
            pass
        return [r["fields"] for r in recs]
    except Exception:
        rows = _fallback_plan_rows()
        if status:
            rows = [r for r in rows if (r.get("status") or "draft") == status]
        rows.sort(key=lambda r: ((r.get("target_date") or ""), (r.get("slot") or "")))
        return rows[:limit]


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Sync the local content calendar → Airtable ContentCalendar table")
    p.add_argument("--list",    action="store_true", help="list ContentCalendar rows instead of pushing")
    p.add_argument("--planned", action="store_true", help="with --list, only status=planned")
    p.add_argument("--pending", action="store_true", help="with --list, only status=draft")
    args = p.parse_args()

    if args.list:
        status = "planned" if args.planned else ("draft" if args.pending else None)
        rows = list_plan(status=status)
        if not rows:
            print("(no rows)")
            return
        print(f"{'date':12}  {'slot':5}  {'mode':10}  {'friend':12}  {'status':10}  event")
        print("-" * 80)
        for r in rows:
            print(
                f"{(r.get('target_date') or '')[:12]:12}  "
                f"{(r.get('slot') or ''):5}  "
                f"{(r.get('mode') or ''):10}  "
                f"{(r.get('friend') or '?'):12}  "
                f"{(r.get('status') or 'draft'):10}  "
                f"{r.get('calendar_event','')}"
            )
        return

    print("Pushing latest content_calendar.json to Airtable ContentCalendar...")
    result = push_latest_local()
    print(f"  total  : {result.get('total', 0)}")
    print(f"  created: {result['created']}")
    print(f"  updated: {result['updated']}")
    print(f"  skipped: {result['skipped']}")
    if result["errors"]:
        print("\nErrors:")
        for e in result["errors"]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
