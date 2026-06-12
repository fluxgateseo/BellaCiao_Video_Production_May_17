"""
_airtable_setup.py — one-shot table-creation/patching script.

Idempotent: re-running it after success is a no-op (every operation either
adds something missing or reports "already there"). Safe to delete after
the tables are in place.

Requires the PAT to temporarily have schema.bases:write. After success,
remove that scope per minimum-privilege rule.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PAT  = os.getenv("AIRTABLE_PAT", "")
BASE = os.getenv("AIRTABLE_BASE_ID", "")
HEAD = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}
META = f"https://api.airtable.com/v0/meta/bases/{BASE}"

if not (PAT and BASE):
    print("Missing AIRTABLE_PAT or AIRTABLE_BASE_ID in .env")
    sys.exit(1)


# ─── Helpers ─────────────────────────────────────────────────────────────────

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


def add_field(table_id: str, field_spec: dict) -> str:
    r = requests.post(
        f"{META}/tables/{table_id}/fields",
        headers=HEAD,
        data=json.dumps(field_spec),
    )
    if r.status_code in (200, 201):
        return f"  + added {field_spec['name']}"

    # Formula fields can't be created via the Meta API (Airtable limitation
    # — UNSUPPORTED_FIELD_TYPE_FOR_CREATE). Print clear manual-setup steps.
    if field_spec.get("type") == "formula" and "UNSUPPORTED_FIELD_TYPE_FOR_CREATE" in r.text:
        formula_expr = field_spec.get("options", {}).get("formula", "")
        return (
            f"  ! {field_spec['name']} cannot be auto-created (Airtable API blocks formula field creation)\n"
            f"    MANUAL STEP — add it once in the Airtable UI:\n"
            f"      1. Open the table → click '+' to add a field\n"
            f"      2. Name: {field_spec['name']}\n"
            f"      3. Type: Formula\n"
            f"      4. Paste this formula:\n"
            f"         {formula_expr}"
        )

    return f"  ! add {field_spec['name']} FAILED ({r.status_code}): {r.text[:150]}"


def update_field(table_id: str, field_id: str, payload: dict) -> str:
    r = requests.patch(
        f"{META}/tables/{table_id}/fields/{field_id}",
        headers=HEAD,
        data=json.dumps(payload),
    )
    if r.status_code == 200:
        return f"  ~ patched {payload}"
    return f"  ! patch FAILED ({r.status_code}): {r.text[:150]}"


def create_table(payload: dict) -> str:
    r = requests.post(
        f"{META}/tables",
        headers=HEAD,
        data=json.dumps(payload),
    )
    if r.status_code in (200, 201):
        return f"  + created table {payload['name']}"
    return f"  ! create {payload['name']} FAILED ({r.status_code}): {r.text[:300]}"


# ─── Field-spec builders ─────────────────────────────────────────────────────

def text_short(name: str)         -> dict: return {"name": name, "type": "singleLineText"}
def text_long(name: str)          -> dict: return {"name": name, "type": "multilineText"}
def checkbox(name: str)           -> dict: return {"name": name, "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}}
def number_int(name: str)         -> dict: return {"name": name, "type": "number", "options": {"precision": 0}}
def number_dec(name: str)         -> dict: return {"name": name, "type": "number", "options": {"precision": 2}}
def formula(name: str, expr: str) -> dict:
    return {"name": name, "type": "formula", "options": {"formula": expr}}
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


# ─── Table specs ─────────────────────────────────────────────────────────────

TRENDS_FIELDS = [
    text_short("run_id"),
    datetime_field("analyzed_at"),
    text_long("this_week_priority"),
    text_long("timely_hooks"),
    text_long("trending_formats"),
    text_long("hashtag_opportunities"),
    text_long("content_gaps"),
    text_long("raw_counts"),
    single_select("verdict", ["unreviewed", "good", "stale", "reject"]),
    text_long("notes"),
]

FRIEND_OPTIONS = ["naomi", "sal", "jake", "enzo_maria", "yasmin", "danny", "arun_priya", "sophie"]
CITY_OPTIONS   = ["Melbourne", "New York", "London"]
MODE_OPTIONS   = ["event_day", "event_eve", "generic"]
MARKET_OPTIONS = ["AU", "US", "UK", "INT"]

# Calendar table — Tier-1 events the user reviews and marks scheduled/skip
CALENDAR_FIELDS = [
    text_short("event_id"),                  # primary, e.g. "anzac_day_2026"
    text_short("event_name"),
    datetime_field("event_date"),
    single_select("market", MARKET_OPTIONS),
    number_int("revenue_tier"),
    single_select("suggested_friend", FRIEND_OPTIONS + ["any"]),
    single_select("verdict", ["unreviewed", "scheduled", "skip"]),
    text_long("notes"),
]

SLOT_OPTIONS = ["story", "reel"]

# Doctrine types from Bella_Shorts_Hooks.xlsx — used as Airtable single_select.
# Order matches the doctrine numbering in the source spreadsheet.
DOCTRINE_TYPE_OPTIONS = [
    "1 — Callout",
    "2 — Counter-Intuitive Fact",
    "3 — Specific Number",
    "4 — POV Confession",
    "5 — Uncomfortable Truth",
    "6 — Real Event",
    "7 — Friend Cold Open",
]
HOOK_CHOICE_OPTIONS         = ["1", "2", "3"]
PILLAR_CHOICE_OPTIONS       = ["1", "2", "3"]
STORY_SEED_CHOICE_OPTIONS   = ["1", "2", "3"]
SENSORY_HOOK_CHOICE_OPTIONS = ["1", "2", "3"]
STATUS_OPTIONS              = ["draft", "planned", "skip", "rejected"]

# ContentCalendar table — daily plan rows (date + slot + friend + 3 hook options)
# The user reviews each row in Airtable, picks ONE of the 3 hooks via hook_choice,
# and marks status=planned to lock it. If they want different hooks, they tick
# regenerate_request and re-run --stage plan.
CONTENT_CALENDAR_FIELDS = [
    text_short("plan_id"),                # primary, e.g. plan_2026-04-25_story
    text_short("target_date"),
    single_select("slot", SLOT_OPTIONS),
    number_int("day_number"),
    text_short("weekday"),
    single_select("mode", MODE_OPTIONS),
    text_short("calendar_event"),         # ⚠ NOT single_select — open enum
    single_select("city", CITY_OPTIONS + ["—"]),
    single_select("friend", FRIEND_OPTIONS + ["—"]),
    number_int("pillar"),                 # legacy — left blank in v1.6+, resolved at brief time from pillar_choice
    text_short("pillar_theme"),           # legacy — same
    number_int("duration_target"),
    text_long("story_seed"),                # legacy — left blank in v1.7+
    # ─── 3 story_seed options (pipeline-owned, user picks via story_seed_choice) ───
    text_long("story_seed_1"),
    text_long("story_seed_2"),
    text_long("story_seed_3"),
    single_select("story_seed_choice", STORY_SEED_CHOICE_OPTIONS),
    # ─── 3 sensory_hook options (pipeline-owned, user picks via sensory_hook_choice) ───
    text_long("sensory_hook_1"),
    text_long("sensory_hook_2"),
    text_long("sensory_hook_3"),
    single_select("sensory_hook_choice", SENSORY_HOOK_CHOICE_OPTIONS),
    # ─── 3 pillar options (pipeline-owned, user picks via pillar_choice) ───
    number_int("pillar_1"),
    text_short("pillar_1_theme"),
    number_int("pillar_2"),
    text_short("pillar_2_theme"),
    number_int("pillar_3"),
    text_short("pillar_3_theme"),
    single_select("pillar_choice", PILLAR_CHOICE_OPTIONS),
    # ─── 3 hook options (pipeline-owned, sourced from bella_hooks.json) ───
    number_int("hook_1_id"),
    text_long("hook_1_text"),
    single_select("hook_1_doctrine", DOCTRINE_TYPE_OPTIONS),
    number_int("hook_2_id"),
    text_long("hook_2_text"),
    single_select("hook_2_doctrine", DOCTRINE_TYPE_OPTIONS),
    number_int("hook_3_id"),
    text_long("hook_3_text"),
    single_select("hook_3_doctrine", DOCTRINE_TYPE_OPTIONS),
    # ─── Research enrichment (NEW v2.1 — from Skill 3 Competitive Ideation) ───
    text_long("research_angle"),        # strategic angle from competitive analysis
    text_long("research_gap"),          # the competitive gap this row addresses
    single_select("research_urgency", ["high", "medium", "low", ""]),
    text_long("research_rationale"),    # why this angle, why now
    # ─── User-controlled choice + regenerate flow ───
    single_select("hook_choice", HOOK_CHOICE_OPTIONS),
    checkbox("regenerate_request"),       # tick to re-roll the 3 hooks on next --stage plan
    text_long("regenerate_notes"),        # optional feedback for the regen
    single_select("status", STATUS_OPTIONS),
    text_long("rejected_reason"),         # required when status=rejected, optional otherwise
    text_long("notes"),
    # ─── Play-script flow (NEW v1.7) ───
    # Visual validation field — readable in the row before the user ticks the
    # ready_to_write checkbox. Tells you what's missing.
    formula(
        "validation_status",
        "IF(AND({status}='planned',{hook_choice},{pillar_choice},{story_seed_choice},{sensory_hook_choice}),"
        "'✅ READY',"
        "'⛔ MISSING: '"
        "&IF({status}!='planned','status≠planned ','')"
        "&IF(NOT({hook_choice}),'hook ','')"
        "&IF(NOT({pillar_choice}),'pillar ','')"
        "&IF(NOT({story_seed_choice}),'seed ','')"
        "&IF(NOT({sensory_hook_choice}),'sensory ',''))",
    ),
    # User ticks this to fire the brief+write pipeline for this row.
    # `--stage play` picks it up, runs the writers, then UNTICKS it (one-shot).
    checkbox("ready_to_write"),
]

BRIEFS_FIELDS = [
    text_short("run_id"),                # primary
    text_short("target_date"),           # ISO date the script publishes
    single_select("slot", SLOT_OPTIONS), # story or reel — Bella publishes both per day
    datetime_field("generated_at"),
    single_select("mode", MODE_OPTIONS),
    single_select("friend", FRIEND_OPTIONS),
    number_int("pillar"),
    single_select("city", CITY_OPTIONS),
    text_short("calendar_event"),       # ⚠ NOT single_select — open enum
    text_short("enemy"),
    text_long("enemy_failure_mode"),
    text_short("ally"),
    text_short("tone"),
    number_int("target_duration_seconds"),
    text_long("sensory_hook"),
    text_long("trend_anchor"),
    text_long("director_note"),
    text_long("brief_json"),             # full brief dict, JSON-stringified
    text_long("writer_prompt_preview"),  # the assembled writer prompt — "input" gate
    single_select("verdict", ["unreviewed", "good", "reject", "rewrite_needed"]),
    text_long("notes"),
    # Rewrite-loop fields:
    text_long("rewrite_notes"),          # user → system feedback when verdict=rewrite_needed
    number_int("regeneration_count"),    # how many times this brief has been regenerated
    # Hook lock — the brief carries the chosen hook from ContentCalendar
    number_int("chosen_hook_id"),
    text_long("chosen_hook_text"),       # locked Section 2 opener for the writer
    single_select("chosen_hook_doctrine", DOCTRINE_TYPE_OPTIONS),
    # Production-calendar fields:
    checkbox("script_produced"),         # true once a script has been written for this brief
    text_short("episode_id"),            # link from brief → produced script (by episode_id)
    # Scenario/beat tagging (added 2026-04-11, Commit 3) — comma-separated kebab-case
    # tags from the strategy director's brief output, used by memory.py to enforce a
    # 10-script scenario cooldown window. NOT Single select — open enum.
    text_short("scenario_tags"),
]


# ─── Patch / create logic ────────────────────────────────────────────────────

def patch_table(name: str, desired_fields: list[dict]) -> None:
    schema = fetch_schema()
    table = find_table(schema, name)
    if not table:
        print(f"\n=== {name} (creating) ===")
        # primary field = first in desired list
        payload = {"name": name, "fields": desired_fields}
        print(create_table(payload))
        return

    print(f"\n=== {name} (patching) ===")
    existing = field_names(table)
    for spec in desired_fields:
        if spec["name"] in existing:
            print(f"  = {spec['name']} already exists")
            continue
        print(add_field(table["id"], spec))


def ensure_select_choices(table_name: str, field_name: str, desired: list[str]) -> None:
    """
    Make sure a single_select field's choices include every name in `desired`.
    Adds missing names. Does NOT remove existing choices (Airtable would error
    if any rows reference them). Run after patch_table.

    Note: Airtable's meta API requires existing choices to include their IDs
    when patching, otherwise it treats them as deleted-and-recreated and
    rejects the request. New choices must NOT carry an id.
    """
    schema = fetch_schema()
    table = find_table(schema, table_name)
    if not table:
        print(f"  ! ensure_select_choices: table {table_name} not found")
        return
    field = next((f for f in table["fields"] if f["name"] == field_name), None)
    if not field:
        print(f"  ! ensure_select_choices: field {table_name}.{field_name} not found")
        return
    if field.get("type") != "singleSelect":
        print(f"  ! ensure_select_choices: {table_name}.{field_name} is not singleSelect")
        return
    existing_choices = field.get("options", {}).get("choices", [])
    existing_names = [c["name"] for c in existing_choices]
    missing = [n for n in desired if n not in existing_names]
    if not missing:
        print(f"  = {table_name}.{field_name} choices already include {desired}")
        return
    # Build the new choices list: keep existing WITH ids, append missing WITHOUT ids.
    new_choices = [
        {"id": c["id"], "name": c["name"]} for c in existing_choices
    ] + [
        {"name": n} for n in missing
    ]
    payload = {"options": {"choices": new_choices}}
    result = update_field(table["id"], field["id"], payload)
    if "FAILED" in result:
        print(f"  ! {table_name}.{field_name} could not auto-add {missing}")
        print(f"    Add manually in Airtable UI: open the {field_name} field, "
              f"click '+ Add option', type {missing}.")
        print(f"    (Likely cause: PAT lacks field-update scope or workspace plan "
              f"restricts singleSelect choice edits via API.)")
    else:
        print(result + f"  ({table_name}.{field_name}: added {missing})")


def main() -> None:
    print(f"Base: {BASE}")
    print("Probing schema...")
    schema = fetch_schema()
    print("Tables found:", [t["name"] for t in schema["tables"]])

    patch_table("TrendSignals",    TRENDS_FIELDS)
    patch_table("Calendar",        CALENDAR_FIELDS)
    patch_table("ContentCalendar", CONTENT_CALENDAR_FIELDS)
    patch_table("Briefs",          BRIEFS_FIELDS)

    # Expand existing single_select choices on existing tables (idempotent).
    print("\n=== Expanding single_select choices ===")
    ensure_select_choices("ContentCalendar", "status",              STATUS_OPTIONS)
    ensure_select_choices("ContentCalendar", "pillar_choice",       PILLAR_CHOICE_OPTIONS)
    ensure_select_choices("ContentCalendar", "story_seed_choice",   STORY_SEED_CHOICE_OPTIONS)
    ensure_select_choices("ContentCalendar", "sensory_hook_choice", SENSORY_HOOK_CHOICE_OPTIONS)

    print("\n=== Final state ===")
    schema = fetch_schema()
    for t in schema["tables"]:
        if t["name"] in ("TrendSignals", "Calendar", "ContentCalendar", "Briefs"):
            print(f"\n{t['name']}:")
            for f in t["fields"]:
                opts = f.get("options", {})
                tag = ""
                if "choices" in opts:
                    tag = " [" + ", ".join(c["name"] for c in opts["choices"]) + "]"
                print(f"  {f['name']:30} {f['type']}{tag}")


if __name__ == "__main__":
    main()
