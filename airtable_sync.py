"""
airtable_sync.py — push generated scripts to Airtable + read them back.

Scope: ARCHIVE / BROWSE layer only. This is NOT an approval-gate workflow.
See memory/out_of_scope_rule.md — approval gates are out of scope for the
entire Bellaciao ecosystem. status is only "draft" or "archived".

Usage:
    from airtable_sync import push_script, fetch_script, list_scripts

    push_script(job)                        # upsert by episode_id
    job = fetch_script("bella_jake_p1_...") # one by episode_id
    jobs = list_scripts(friend="jake", min_score=9.5)
"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from network_probe import require_host

# Shared .env at Bellaciao Content/ level — same file every project uses.
load_dotenv(Path(__file__).parent.parent / ".env")

AIRTABLE_PAT        = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID    = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Scripts")
BASE_DIR            = Path(__file__).parent
JOBS_DIR            = BASE_DIR / "data" / "jobs"


def _table():
    """Lazy-construct the pyairtable Table. Raises if credentials missing."""
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError(
            "Airtable not configured. Set AIRTABLE_PAT and AIRTABLE_BASE_ID "
            "in Bellaciao Content/.env"
        )
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT).table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)


def _job_to_fields(job: dict) -> dict:
    """Flatten an engine job dict into the Airtable column schema."""
    brief = job.get("brief", {}) or {}
    scene_brief = job.get("scene_brief")
    if not isinstance(scene_brief, str):
        scene_brief = json.dumps(scene_brief or {}, indent=2)
    return {
        "episode_id":        job.get("episode_id", ""),
        "generated_at":      job.get("generated_at"),
        "day":               job.get("day"),
        "friend":            brief.get("friend"),
        "pillar":            brief.get("pillar"),
        "calendar_event":    brief.get("calendar_event"),
        "score":             job.get("score"),
        "story_spine":       job.get("story_spine", ""),
        "video_script":      job.get("video_script", ""),
        "video_script_ssml": job.get("video_script_ssml", ""),
        "caption":           job.get("caption", ""),
        "scene_brief":       scene_brief,
        "status":            "draft",
    }


def push_script(job: dict) -> str:
    """
    Upsert a job into Airtable by episode_id.

    Returns the Airtable record id. Raises RuntimeError if not configured —
    callers should catch and skip gracefully (Airtable is optional).
    """
    tbl = _table()
    fields = {k: v for k, v in _job_to_fields(job).items() if v is not None}
    episode_id = fields.get("episode_id")
    if not episode_id:
        raise ValueError("job has no episode_id — refusing to push")

    existing = tbl.all(formula=f"{{episode_id}} = '{episode_id}'")
    if existing:
        rec = tbl.update(existing[0]["id"], fields)
    else:
        rec = tbl.create(fields)
    return rec["id"]


def fetch_script(episode_id: str) -> Optional[dict]:
    """Fetch a single script record by episode_id. Returns the fields dict or None."""
    try:
        tbl = _table()
        recs = tbl.all(formula=f"{{episode_id}} = '{episode_id}'")
        if recs:
            return recs[0]["fields"]
    except Exception:
        pass

    local_path = JOBS_DIR / f"{episode_id}.json"
    if not local_path.exists():
        return None
    try:
        job = json.loads(local_path.read_text())
    except Exception:
        return None
    return _job_to_fields(job)


def list_scripts(friend: Optional[str] = None,
                 pillar: Optional[int] = None,
                 min_score: Optional[float] = None,
                 limit: int = 100) -> list[dict]:
    """List scripts, filtered by friend / pillar / min_score. Newest first."""
    clauses = []
    if friend:
        clauses.append(f"{{friend}} = '{friend}'")
    if pillar is not None:
        clauses.append(f"{{pillar}} = {pillar}")
    if min_score is not None:
        clauses.append(f"{{score}} >= {min_score}")
    formula = f"AND({', '.join(clauses)})" if clauses else None

    try:
        tbl = _table()
        recs = tbl.all(
            formula=formula,
            sort=["-generated_at"],
            max_records=limit,
        )
        return [r["fields"] for r in recs]
    except Exception:
        rows: list[dict] = []
        for job_file in JOBS_DIR.glob("*.json"):
            try:
                job = json.loads(job_file.read_text())
            except Exception:
                continue
            row = _job_to_fields(job)
            if friend and row.get("friend") != friend:
                continue
            if pillar is not None and row.get("pillar") != pillar:
                continue
            if min_score is not None and (row.get("score") or 0) < min_score:
                continue
            rows.append(row)
        rows.sort(key=lambda r: r.get("generated_at") or "", reverse=True)
        return rows[:limit]


if __name__ == "__main__":
    # Quick smoke test — list recent scripts.
    import sys
    try:
        rows = list_scripts(limit=10)
        print(f"Airtable reachable. {len(rows)} scripts in table.")
        for r in rows:
            print(f"  {r.get('episode_id', '?')}  {r.get('score', '?')}  {r.get('friend', '?')}")
    except Exception as e:
        print(f"Airtable error: {e}")
        sys.exit(1)
