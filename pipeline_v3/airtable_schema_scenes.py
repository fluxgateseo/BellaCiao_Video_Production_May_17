"""
airtable_schema_scenes.py — Schema migration for the Scenes table.

Creates a `ShotApproval` table in the Airtable base — one row per shot from an
approved episode. Field design follows VIDEO_INPUT_CONTRACT.md v2.0 and gives
the operator per-scene approve / reroll / skip lifecycle control.

Idempotent. Re-running after success is a no-op. Mirrors the pattern in
`airtable_schema_v3.py`.

Usage:
    python3 pipeline_v3/airtable_schema_scenes.py --dry-run
    python3 pipeline_v3/airtable_schema_scenes.py --apply

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


# ─── Helpers (mirrors airtable_schema_v3.py) ─────────────────────────────────

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


# ─── Field-spec builders ─────────────────────────────────────────────────────

def text_short(name: str)     -> dict: return {"name": name, "type": "singleLineText"}
def text_long(name: str)      -> dict: return {"name": name, "type": "multilineText"}
def checkbox(name: str)       -> dict: return {"name": name, "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}}
def number_int(name: str)     -> dict: return {"name": name, "type": "number", "options": {"precision": 0}}
def url_field(name: str)      -> dict: return {"name": name, "type": "url"}
def datetime_field(name: str) -> dict:
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


# ─── Enums ───────────────────────────────────────────────────────────────────

SLOT_OPTIONS    = ["story", "reel"]
SUBJECT_OPTIONS = ["bella", "friend", "ciao", "scene", "ally"]
STATUS_OPTIONS  = ["draft", "approved", "reroll", "rendered", "skip"]


# ─── Scenes table fields (28 total) ──────────────────────────────────────────

SCENES_FIELDS = [
    # Identity (5)
    text_short("scene_id"),                         # primary — "{episode_id}_shot{NN}"
    text_short("episode_id"),                       # links to Scripts.episode_id by value
    number_int("day_number"),
    single_select("slot", SLOT_OPTIONS),
    number_int("shot_index"),

    # Content — pipeline-owned (14)
    single_select("subject", SUBJECT_OPTIONS),
    text_long("scene_description"),
    text_long("action"),
    text_short("camera"),
    text_short("lighting"),
    text_short("mood"),
    text_long("audio_slice_text"),
    number_int("duration_seconds"),
    text_long("world_description"),
    text_short("continuity_wardrobe"),
    text_short("continuity_props"),
    text_short("negative"),
    text_short("transition_in"),
    text_short("transition_out"),

    # ⭐ Prompts — the creatives handoff (3)
    text_long("image_start_frame_prompt"),
    text_long("image_end_frame_prompt"),
    text_long("prompt_universal"),

    # Reference images (1)
    text_long("reference_images"),                  # JSON array of absolute paths

    # Lifecycle — user-controlled (6)
    single_select("status", STATUS_OPTIONS),
    checkbox("reroll_requested"),
    text_long("reroll_notes"),
    url_field("generated_image_url"),
    url_field("generated_clip_url"),
    text_long("notes"),

    # Timestamps (3)
    datetime_field("generated_at"),
    datetime_field("approved_at"),
    datetime_field("rendered_at"),

    # ⭐ Character / approval taxonomy (3) — added 2026-04-15
    text_short("character_id"),
    checkbox("is_character_reference"),
    text_long("prompt_image_start"),
    text_long("prompt_image_end"),
]


# ─── Patch / create logic ────────────────────────────────────────────────────

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

    patch_table("ShotApproval", SCENES_FIELDS, dry_run)

    print("\n=== Final state (ShotApproval) ===")
    schema = fetch_schema()
    t = find_table(schema, "ShotApproval")
    if t:
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
