"""
calendar_v3.py — v3 additive trend-enrichment for ContentCalendar rows.

v3 does NOT replace v2's content_calendar.py. It runs AFTER the v2 plan stage
has already populated ContentCalendar with rows (day + slot + friend + 3 hook
options). It then:

  1. Reads raw trend signals from data/trend_signals.json (produced by
     apify_scout.py, unchanged). If the file is missing, logs and exits
     gracefully — nothing to enrich.
  2. For each ContentCalendar row where status='planned' and trend_seed_id
     is empty, selects a relevant raw trend and invokes the trend-hijacker
     skill to adapt it to the restaurant-SEO niche with the planned friend
     as character context.
  3. Writes the adapted trend to the TrendSignals table (primary key = run_id)
     and patches the ContentCalendar row's trend_seed_id.

Idempotent: rows already carrying a trend_seed_id are skipped.

Usage:
    python3 -m pipeline_v3.calendar_v3            # enrich all planned rows
    python3 -m pipeline_v3.calendar_v3 --day 12   # only rows for day 12
    python3 -m pipeline_v3.calendar_v3 --dry-run  # print plan, no writes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from network_probe import require_host

# v3 package lives as sibling of v2 modules — add parent to sys.path so we can
# import the shared Airtable client pattern at module scope.
_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT))

load_dotenv(_PKG_ROOT.parent / ".env")

from pipeline_v3.skills_client import run_trend_hijacker  # noqa: E402

AIRTABLE_PAT     = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
NICHE            = os.getenv("V3_NICHE", "SEO for restaurants")
TREND_FILE       = _PKG_ROOT / "data" / "trend_signals.json"


def _api():
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError("Airtable not configured (AIRTABLE_PAT/BASE_ID)")
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT)


def _content_calendar():
    return _api().table(AIRTABLE_BASE_ID, "ContentCalendar")


def _trend_signals():
    return _api().table(AIRTABLE_BASE_ID, "TrendSignals")


def load_raw_trends() -> list[dict]:
    if not TREND_FILE.exists():
        print(f"[calendar_v3] no raw trends at {TREND_FILE} — skipping enrichment")
        return []
    data = json.loads(TREND_FILE.read_text())
    if isinstance(data, dict):
        data = data.get("trends") or data.get("items") or []
    return data if isinstance(data, list) else []


def select_trend_for_row(row: dict, trends: list[dict]) -> dict | None:
    """Pick a trend for a ContentCalendar row. Cheap heuristic: match friend
    keyword if present, otherwise round-robin by day_number."""
    if not trends:
        return None
    friend = (row.get("fields", {}).get("friend") or "").lower()
    if friend and friend != "—":
        for t in trends:
            blob = json.dumps(t).lower()
            if friend in blob:
                return t
    day_number = row.get("fields", {}).get("day_number") or 0
    return trends[day_number % len(trends)]


def run_id_for(row_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    short = hashlib.sha1(row_id.encode()).hexdigest()[:8]
    return f"trend_{stamp}_{short}"


def enrich_row(row: dict, trends: list[dict], *, dry_run: bool) -> str:
    fields = row.get("fields", {})
    plan_id = fields.get("plan_id", "?")

    if fields.get("trend_seed_id"):
        return f"= {plan_id}: already has trend_seed_id={fields['trend_seed_id']}"

    trend = select_trend_for_row(row, trends)
    if trend is None:
        return f"- {plan_id}: no raw trend available, skipped"

    goal = (
        f"Friend={fields.get('friend')}, pillar={fields.get('pillar_choice')}, "
        f"event={fields.get('calendar_event') or 'generic'}"
    )
    trend_desc = (
        trend.get("description") or trend.get("title") or json.dumps(trend)[:400]
    )

    if dry_run:
        return (
            f"[dry-run] {plan_id}: would hijack trend "
            f"'{trend_desc[:60]}...' for goal '{goal[:60]}...'"
        )

    try:
        result = run_trend_hijacker(trend_desc, NICHE, goal)
        run_id = run_id_for(row["id"])

        _trend_signals().create({
            "run_id":                run_id,
            "analyzed_at":           datetime.now(timezone.utc).isoformat(),
            "this_week_priority":    result.raw_text[:80_000],  # Airtable long-text cap
            "timely_hooks":          json.dumps(trend, indent=2)[:80_000],
            "trending_formats":      (result.parsed or {}).get("format", "") if isinstance(result.parsed, dict) else "",
            "hashtag_opportunities": "",
            "content_gaps":          "",
            "raw_counts":            f"input_tokens={result.input_tokens}, output_tokens={result.output_tokens}",
            "verdict":               "unreviewed",
            "notes":                 f"Generated by calendar_v3 from ContentCalendar row {plan_id}",
        })

        _content_calendar().update(row["id"], {"trend_seed_id": run_id})
    except Exception as e:  # noqa: BLE001 - keep row-level failures readable
        return f"! {plan_id}: enrichment failed — {type(e).__name__}: {e}"
    return f"+ {plan_id}: enriched with {run_id}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, help="Only enrich rows with day_number=N")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    trends = load_raw_trends()

    formula_parts = ["{status}='planned'", "NOT({trend_seed_id})"]
    if args.day is not None:
        formula_parts.append(f"{{day_number}}={args.day}")
    formula = "AND(" + ",".join(formula_parts) + ")"

    print(f"[calendar_v3] filter: {formula}")
    # Dry-run contract (matches visualize_v3 + brief_v3): no Airtable, no creds.
    if args.dry_run:
        print(
            f"[calendar_v3] [dry-run] would query ContentCalendar with the filter "
            f"above; loaded {len(trends)} local raw trend(s) for enrichment."
        )
        print("[calendar_v3] [dry-run] no network call performed; re-run without --dry-run to execute.")
        return 0

    cc = _content_calendar()
    try:
        rows = cc.all(formula=formula)
    except Exception as e:  # noqa: BLE001
        print(f"! calendar_v3: query failed — {type(e).__name__}: {e}")
        return 1
    print(f"[calendar_v3] candidates: {len(rows)}")
    if not rows:
        return 0

    had_errors = False
    for row in rows:
        result = enrich_row(row, trends, dry_run=args.dry_run)
        print(result)
        had_errors = had_errors or result.startswith("!")
    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
