"""
airtable_schema_v3.py — Additive schema migration for Bellaciao Content Engine v3.0.

Extends the v2.1 base with:
  - NEW table: Deliverables      (3 rows per episode: reel | ytshort | carousel)
  - NEW table: CommentQueue      (comment-engine outputs staged for posting)
  - NEW fields on Briefs:        triplet_strategy
  - NEW fields on Scripts:       story_arc_framework, triplet_member
  - NEW field  on ContentCalendar: trend_seed_id

Idempotent. Re-running after success is a no-op. Shares the same helpers and
HTTP conventions as _airtable_setup.py (Meta API, PAT from .env).

Usage:
    python3 pipeline_v3/airtable_schema_v3.py --dry-run   # show plan, write nothing
    python3 pipeline_v3/airtable_schema_v3.py --apply     # execute the migration

Requires PAT with schema.bases:write. Remove that scope after success.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

PAT  = os.getenv("AIRTABLE_PAT", "")
BASE = os.getenv("AIRTABLE_BASE_ID", "")
HEAD = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}
META = f"https://api.airtable.com/v0/meta/bases/{BASE}"

if not (PAT and BASE):
    print("Missing AIRTABLE_PAT or AIRTABLE_BASE_ID in .env")
    sys.exit(1)


# ─── Helpers (copied pattern from _airtable_setup.py:36-98) ──────────────────

def fetch_schema() -> dict:
    r = requests.get(f"{META}/tables", headers=HEAD)
    r.raise_for_status()
    return r.json()


def find_table(schema: dict, name: str) -> dict | None:
    for t in schema["tables"]:
        if t["name"] == name:
            return t
    return None


def field_names(table: dict) -> set[str]:
    return {f["name"] for f in table["fields"]}


def add_field(table_id: str, field_spec: dict, dry_run: bool) -> str:
    if dry_run:
        return f"  [dry-run] would add {field_spec['name']} ({field_spec['type']})"
    r = requests.post(
        f"{META}/tables/{table_id}/fields",
        headers=HEAD,
        data=json.dumps(field_spec),
    )
    if r.status_code in (200, 201):
        return f"  + added {field_spec['name']}"
    return f"  ! add {field_spec['name']} FAILED ({r.status_code}): {r.text[:200]}"


def create_table(payload: dict, dry_run: bool) -> str:
    if dry_run:
        return f"  [dry-run] would create table {payload['name']} with {len(payload['fields'])} fields"
    r = requests.post(
        f"{META}/tables",
        headers=HEAD,
        data=json.dumps(payload),
    )
    if r.status_code in (200, 201):
        return f"  + created table {payload['name']}"
    return f"  ! create {payload['name']} FAILED ({r.status_code}): {r.text[:300]}"


# ─── Field-spec builders (same as _airtable_setup.py:103-122) ────────────────

def text_short(name: str)         -> dict: return {"name": name, "type": "singleLineText"}
def text_long(name: str)          -> dict: return {"name": name, "type": "multilineText"}
def checkbox(name: str)           -> dict: return {"name": name, "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}}
def number_int(name: str)         -> dict: return {"name": name, "type": "number", "options": {"precision": 0}}
def number_dec(name: str)         -> dict: return {"name": name, "type": "number", "options": {"precision": 2}}
def url_field(name: str)          -> dict: return {"name": name, "type": "url"}
def datetime_field(name: str)     -> dict:
    return {
        "name": name,
        "type": "dateTime",
        "options": {
            "dateFormat": {"name": "iso"},
            "timeFormat": {"name": "24hour"},
            "timeZone":   "client",
        },
    }
def single_select(name: str, choices: list[str]) -> dict:
    return {"name": name, "type": "singleSelect",
            "options": {"choices": [{"name": c} for c in choices]}}


# ─── v3.0 enums (see CONTENT_PRODUCTION_SYSTEM_V3.md) ────────────────────────

PLATFORM_OPTIONS = ["reel", "ytshort", "carousel"]

DELIVERABLE_STATUS_OPTIONS = [
    "drafted",        # script written, not yet packaged
    "packaged",       # all companion files generated
    "scheduled",      # posting time set
    "posted",         # live
    "rejected",       # abandoned
]

COMMENT_MODE_OPTIONS = [
    "reply",          # response to incoming comment
    "pinned",         # own pinned comment
    "engagement_q",   # engagement-bait question
    "outbound",       # comment to post on another account
]

COMMENT_STATUS_OPTIONS = ["draft", "approved", "posted", "rejected"]

STORY_ARC_OPTIONS = [
    "heros_journey",
    "problem_agitate_solve",
    "contrast",
    "confession",
    "investigative",
    "stakes",
]

TRIPLET_MEMBER_OPTIONS = PLATFORM_OPTIONS  # same enum

COMMENT_PLATFORM_OPTIONS = ["instagram", "youtube", "tiktok", "other"]


# ─── Table specs ─────────────────────────────────────────────────────────────

# Deliverables — one row per (episode, platform). Created by write_v3 when a
# triplet member is drafted; updated through packaging and posting.
DELIVERABLES_FIELDS = [
    text_short("deliverable_id"),            # primary — "{episode_id}_{platform}"
    text_short("episode_id"),                # links to Scripts.episode_id (by value, not record link — keeps v2 base decoupled)
    single_select("platform", PLATFORM_OPTIONS),
    single_select("status", DELIVERABLE_STATUS_OPTIONS),
    text_short("script_ref"),                # filename in Scripts_v3/Day N/
    text_short("package_ref"),               # companion file bundle reference
    datetime_field("drafted_at"),
    datetime_field("packaged_at"),
    datetime_field("posted_at"),
    url_field("post_url"),
    text_long("notes"),
]

# CommentQueue — comment-engine outputs staged for the operator to post.
COMMENT_QUEUE_FIELDS = [
    text_short("comment_id"),                # primary — "{post_url_hash}_{mode}_{n}"
    url_field("target_post_url"),            # the post the comment is intended for
    single_select("platform", COMMENT_PLATFORM_OPTIONS),
    single_select("mode", COMMENT_MODE_OPTIONS),
    text_long("suggested_text"),
    text_short("episode_id"),                # when this comment belongs to our own post
    single_select("status", COMMENT_STATUS_OPTIONS),
    datetime_field("generated_at"),
    datetime_field("posted_at"),
    text_long("notes"),
]


# ─── Additive fields on existing tables ──────────────────────────────────────

BRIEFS_ADDITIONS = [
    # viral-hook-formula Mode B output: 3 platform-differentiated hooks + share trigger.
    # Stored as JSON string so schema stays stable as skill output evolves.
    text_long("triplet_strategy"),
]

# Scripts table is created at runtime by airtable_sync.push_script (no static
# schema exists) — additive fields here are future-safe: if Scripts doesn't yet
# exist in the base, we skip and log.
SCRIPTS_ADDITIONS = [
    single_select("story_arc_framework", STORY_ARC_OPTIONS),
    single_select("triplet_member", TRIPLET_MEMBER_OPTIONS),
]

CONTENT_CALENDAR_ADDITIONS = [
    # trend_seed_id is stored as short text (the TrendSignals.run_id string),
    # NOT a linked-record field. Airtable Meta API requires table IDs for
    # multipleRecordLinks creation, and a string reference decouples the two
    # tables cleanly. Operators can cross-reference via filter in the UI.
    text_short("trend_seed_id"),
]


# ─── Patch / create logic (pattern from _airtable_setup.py:289-305) ──────────

def patch_table(name: str, desired_fields: list[dict], dry_run: bool) -> None:
    schema = fetch_schema()
    table = find_table(schema, name)
    if not table:
        print(f"\n=== {name} (creating) ===")
        payload = {"name": name, "fields": desired_fields}
        print(create_table(payload, dry_run))
        return

    print(f"\n=== {name} (patching) ===")
    existing = field_names(table)
    for spec in desired_fields:
        if spec["name"] in existing:
            print(f"  = {spec['name']} already exists")
            continue
        print(add_field(table["id"], spec, dry_run))


def add_fields_if_table_exists(name: str, additions: list[dict], dry_run: bool) -> None:
    schema = fetch_schema()
    table = find_table(schema, name)
    if not table:
        print(f"\n=== {name} (skipped — table does not exist yet) ===")
        return
    print(f"\n=== {name} (adding v3 fields) ===")
    existing = field_names(table)
    for spec in additions:
        if spec["name"] in existing:
            print(f"  = {spec['name']} already exists")
            continue
        print(add_field(table["id"], spec, dry_run))


def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Print plan; make no API writes")
    mode.add_argument("--apply",   action="store_true", help="Execute the migration")
    args = ap.parse_args()
    dry_run = args.dry_run

    print(f"Base: {BASE}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    print("Probing schema...")
    schema = fetch_schema()
    print("Existing tables:", [t["name"] for t in schema["tables"]])

    # New tables
    patch_table("Deliverables",  DELIVERABLES_FIELDS,  dry_run)
    patch_table("CommentQueue",  COMMENT_QUEUE_FIELDS, dry_run)

    # Additive fields on existing tables
    add_fields_if_table_exists("Briefs",          BRIEFS_ADDITIONS,           dry_run)
    add_fields_if_table_exists("Scripts",         SCRIPTS_ADDITIONS,          dry_run)
    add_fields_if_table_exists("ContentCalendar", CONTENT_CALENDAR_ADDITIONS, dry_run)

    print("\n=== Final state (v3 tables) ===")
    schema = fetch_schema()
    for t in schema["tables"]:
        if t["name"] in ("Deliverables", "CommentQueue"):
            print(f"\n{t['name']}:")
            for f in t["fields"]:
                opts = f.get("options", {})
                tag = ""
                if "choices" in opts:
                    tag = " [" + ", ".join(c["name"] for c in opts["choices"]) + "]"
                print(f"  {f['name']:30} {f['type']}{tag}")

    if dry_run:
        print("\n[dry-run complete — no changes applied. Re-run with --apply to execute.]")


if __name__ == "__main__":
    main()
