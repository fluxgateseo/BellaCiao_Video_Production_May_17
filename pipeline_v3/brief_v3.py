"""
brief_v3.py — v3 additive step: populate Briefs.triplet_strategy.

v3 does NOT replace v2's brief generation (logical_gate → strategy → briefs_sync).
It runs AFTER those have produced an approved brief (verdict='good') and adds
one field: triplet_strategy — the three platform-differentiated hook variants
(Reel / YT Short / Carousel) produced by the viral-hook-formula skill in
Mode B.

The triplet_strategy JSON is the input for write_v3.py (Phase 5), where the
three parallel writer branches each consume their platform's hook.

Idempotent: briefs already carrying a triplet_strategy are skipped unless
--force is passed.

Usage:
    python3 -m pipeline_v3.brief_v3                    # all verdict=good, empty strategy
    python3 -m pipeline_v3.brief_v3 --run-id R_abc     # one specific brief
    python3 -m pipeline_v3.brief_v3 --day 12           # briefs targeting day 12
    python3 -m pipeline_v3.brief_v3 --dry-run          # plan, no writes
    python3 -m pipeline_v3.brief_v3 --force            # overwrite existing strategies
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from network_probe import require_host

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT))

load_dotenv(_PKG_ROOT.parent / ".env")

from pipeline_v3.skills_client import run_viral_hook_formula  # noqa: E402

AIRTABLE_PAT     = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
NICHE            = os.getenv("V3_NICHE", "SEO for restaurants")
BRIEFS_TABLE     = "Briefs"
CONTENT_CALENDAR_TABLE = "ContentCalendar"


def _api():
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError("Airtable not configured (AIRTABLE_PAT/BASE_ID)")
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT)


def _briefs_table():
    return _api().table(AIRTABLE_BASE_ID, BRIEFS_TABLE)


def _content_calendar_table():
    return _api().table(AIRTABLE_BASE_ID, CONTENT_CALENDAR_TABLE)


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def resolve_target_dates(day_selector: str) -> list[str]:
    selector = (day_selector or "").strip()
    if not selector:
        return []
    if _is_iso_date(selector):
        return [selector]
    if not selector.isdigit():
        return [selector]

    rows = _content_calendar_table().all(formula=f"{{day_number}}={int(selector)}")
    return sorted({
        (row.get("fields", {}).get("target_date") or "").strip()
        for row in rows
        if (row.get("fields", {}).get("target_date") or "").strip()
    })


def extract_topic(brief_fields: dict) -> str:
    """Derive a one-line topic string from a Briefs row for viral-hook-formula.

    Priority: director_note → enemy+enemy_failure_mode → sensory_hook →
    chosen_hook_text. Something non-empty is always returned; the skill will
    adapt regardless of quality."""
    if note := (brief_fields.get("director_note") or "").strip():
        return note
    enemy = (brief_fields.get("enemy") or "").strip()
    failure = (brief_fields.get("enemy_failure_mode") or "").strip()
    if enemy and failure:
        return f"{enemy}: {failure}"
    if enemy:
        return enemy
    if sensory := (brief_fields.get("sensory_hook") or "").strip():
        return sensory
    if chosen := (brief_fields.get("chosen_hook_text") or "").strip():
        return chosen
    return "restaurant marketing problem"


def build_strategy(brief_fields: dict) -> dict:
    """Call viral-hook-formula Mode B. Return a dict ready to serialize."""
    topic = extract_topic(brief_fields)
    friend = brief_fields.get("friend") or "unspecified"
    pillar = brief_fields.get("pillar") or brief_fields.get("pillar_choice") or "?"
    tone = brief_fields.get("tone") or "mentor, fast-talking, warm"

    result = run_viral_hook_formula(
        mode="generate",
        niche=NICHE,
        topic=topic,
        platform="multi-platform (Reel, YouTube Short, Carousel)",
        tone=tone,
    )

    strategy = {
        "skill":          "viral-hook-formula",
        "mode":           "generate",
        "niche":          NICHE,
        "topic":          topic,
        "friend":         friend,
        "pillar":         pillar,
        "tone":           tone,
        "input_tokens":   result.input_tokens,
        "output_tokens":  result.output_tokens,
        "parsed":         result.parsed,
        "raw_text":       result.raw_text,
    }
    return strategy


def process_row(row: dict, *, dry_run: bool, force: bool) -> str:
    fields = row.get("fields", {})
    run_id = fields.get("run_id", "?")

    if fields.get("triplet_strategy") and not force:
        return f"= {run_id}: triplet_strategy already populated (skip; use --force to overwrite)"

    if dry_run:
        topic = extract_topic(fields)
        return f"[dry-run] {run_id}: would generate triplet_strategy for topic '{topic[:60]}...'"

    try:
        strategy = build_strategy(fields)
    except Exception as e:  # noqa: BLE001 - bubble up a concise per-row failure
        return f"! {run_id}: cannot build triplet_strategy — {type(e).__name__}: {e}"

    # Airtable long-text cap ≈ 100k chars; stay well under.
    payload_json = json.dumps(strategy, indent=2)
    if len(payload_json) > 90_000:
        # Drop raw_text if we're near the limit; keep parsed + meta.
        strategy.pop("raw_text", None)
        payload_json = json.dumps(strategy, indent=2)

    try:
        _briefs_table().update(row["id"], {"triplet_strategy": payload_json})
    except Exception as e:  # noqa: BLE001
        return f"! {run_id}: cannot update Briefs row — {type(e).__name__}: {e}"
    return (
        f"+ {run_id}: strategy written "
        f"(in={strategy['input_tokens']} out={strategy['output_tokens']})"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", help="Only process the brief with this run_id")
    ap.add_argument("--day", help="Only briefs whose target_date matches YYYY-MM-DD or day_number")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="Overwrite existing triplet_strategy")
    args = ap.parse_args()

    # Dry-run contract (matches visualize_v3): no Airtable, no creds required.
    # We print the scope of what would run and exit cleanly.
    if args.dry_run:
        scope_bits = []
        if args.run_id:
            scope_bits.append(f"--run-id={args.run_id}")
        if args.day:
            scope_bits.append(f"--day={args.day} (would resolve via ContentCalendar)")
        scope_bits.append(f"--force={args.force}")
        print(f"[brief_v3] [dry-run] would query Briefs (verdict='good') with scope: {', '.join(scope_bits)}")
        print("[brief_v3] [dry-run] no network call performed; re-run without --dry-run to execute.")
        return 0

    if args.run_id:
        formula = f"{{run_id}}='{args.run_id}'"
    else:
        parts = ["{verdict}='good'"]
        if not args.force:
            parts.append("NOT({triplet_strategy})")
        if args.day:
            try:
                target_dates = resolve_target_dates(args.day)
            except Exception as e:  # noqa: BLE001
                print(
                    f"! brief_v3: cannot resolve --day {args.day} via ContentCalendar — "
                    f"{type(e).__name__}: {e}"
                )
                return 1
            if not target_dates:
                print(f"[brief_v3] no target_date rows found for day selector {args.day}")
                return 0
            if len(target_dates) == 1:
                parts.append(f"{{target_date}}='{target_dates[0]}'")
            else:
                clauses = ",".join(f"{{target_date}}='{td}'" for td in target_dates)
                parts.append(f"OR({clauses})")
        formula = "AND(" + ",".join(parts) + ")" if len(parts) > 1 else parts[0]

    print(f"[brief_v3] filter: {formula}")
    try:
        rows = _briefs_table().all(formula=formula)
    except Exception as e:  # noqa: BLE001
        print(f"! brief_v3: query failed — {type(e).__name__}: {e}")
        return 1
    print(f"[brief_v3] candidates: {len(rows)}")
    if not rows:
        return 0

    had_errors = False
    for row in rows:
        result = process_row(row, dry_run=args.dry_run, force=args.force)
        print(result)
        had_errors = had_errors or result.startswith("!")
    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
