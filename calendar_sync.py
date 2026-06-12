"""
calendar_sync.py — push upcoming calendar events to the Airtable Calendar table
for manual review.

Reads data/calendar.json (the canonical event list), resolves the next
occurrence of each event, filters to a horizon (default 90 days), and upserts
each event into the Airtable Calendar table by event_id.

Idempotent: re-running it updates existing rows in place. The user-controlled
verdict field (`unreviewed` / `scheduled` / `skip`) is NEVER touched on update,
so the user's review state survives every refresh.

CLI:
    python3 calendar_sync.py                # next 90 days
    python3 calendar_sync.py --days 180     # custom horizon
    python3 calendar_sync.py --tier 1       # only Tier-1 (default)
    python3 calendar_sync.py --tier 2       # Tier 1 + 2
    python3 calendar_sync.py --tier 3       # everything

The horizon is inclusive of "today" so an event happening today still gets
pushed.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from network_probe import require_host

# Shared .env at the Bellaciao Content/ level
load_dotenv(Path(__file__).parent.parent / ".env")

AIRTABLE_PAT      = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID  = os.getenv("AIRTABLE_BASE_ID", "")
CALENDAR_TABLE    = "Calendar"

# Map calendar.json `countries` to the Airtable `market` single-select.
# An event in multiple countries gets the first matching market in this order.
COUNTRY_TO_MARKET = {
    "AU": "AU",
    "US": "US",
    "UK": "UK",
}


def _table():
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError(
            "Airtable not configured. Set AIRTABLE_PAT and AIRTABLE_BASE_ID "
            "in Bellaciao Content/.env"
        )
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT).table(AIRTABLE_BASE_ID, CALENDAR_TABLE)


def _slug(text: str) -> str:
    """Stable slug for event_id (used as the upsert key)."""
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "event"


def _market_for(countries: list[str]) -> str:
    """Pick the canonical market label for an event's country list."""
    if not countries:
        return "INT"
    if len(countries) >= 3 and set(countries) >= {"AU", "UK", "US"}:
        return "INT"  # multi-market event — review once, applies everywhere
    for c in countries:
        if c in COUNTRY_TO_MARKET:
            return COUNTRY_TO_MARKET[c]
    return "INT"


def _suggested_friend_for(market: str) -> str:
    """
    Map a market to a default suggested friend (city-aligned). The user can
    override per-row in Airtable. Returns the slug, or 'any' for international.
    """
    return {
        "AU": "jake",       # Melbourne
        "US": "naomi",      # NY (Naomi is the canonical NY default)
        "UK": "sal",        # London
    }.get(market, "any")


def _build_fields(event: dict, year_today: date) -> dict | None:
    """Convert one resolved calendar.json event into Airtable field values."""
    name      = event.get("name", "")
    next_date = event.get("next_date")
    if not (name and next_date):
        return None

    # event_id includes the year so the same recurring event in 2027 vs 2026
    # gets distinct review rows. The user can mark Mother's Day 2026 as
    # scheduled and Mother's Day 2027 as unreviewed independently.
    year = next_date[:4]
    event_id = f"{_slug(name)}_{year}"

    market = _market_for(event.get("countries", []))

    return {
        "event_id":         event_id,
        "event_name":       name,
        "event_date":       f"{next_date}T00:00:00.000Z",
        "market":           market,
        "revenue_tier":     int(event.get("revenue_tier", 3)),
        "suggested_friend": _suggested_friend_for(market),
        # verdict is intentionally NOT set on create — Airtable's default is
        # blank, but our schema uses `unreviewed`. We set it on initial create
        # so the user sees it as a clear "needs review" row, then never touch
        # it on update so their later verdicts survive.
    }


def sync_calendar(days_ahead: int = 90, min_tier: int = 1) -> dict:
    """
    Upsert calendar events into the Airtable Calendar table.

    Args:
        days_ahead: how many days into the future to include
        min_tier:   include events with revenue_tier <= min_tier
                    (1 = only Tier 1, 2 = Tier 1+2, 3 = everything)

    Returns: {"created": N, "updated": N, "skipped": N, "errors": [...]}
    """
    # Reuse strategy.upcoming_events() — single source of truth for event resolution.
    from strategy import upcoming_events

    tbl = _table()
    events = upcoming_events(days_ahead=days_ahead)
    today = date.today()

    # Filter by tier (lower number = more important)
    events = [e for e in events if int(e.get("revenue_tier", 3)) <= min_tier]

    # Pre-fetch existing rows so we can upsert without one GET per event.
    existing = tbl.all()
    by_id: dict[str, dict] = {}
    for r in existing:
        eid = r["fields"].get("event_id")
        if eid:
            by_id[eid] = r

    created, updated, skipped = 0, 0, 0
    errors: list[str] = []

    for ev in events:
        fields = _build_fields(ev, today)
        if not fields:
            skipped += 1
            continue
        eid = fields["event_id"]
        try:
            if eid in by_id:
                # Update — but DO NOT touch the verdict (user-owned).
                tbl.update(by_id[eid]["id"], fields)
                updated += 1
            else:
                # Create — set verdict=unreviewed so it shows up as needs-review.
                fields["verdict"] = "unreviewed"
                tbl.create(fields)
                created += 1
        except Exception as e:
            errors.append(f"{eid}: {e}")
            skipped += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors":  errors,
        "total_resolved": len(events),
    }


def list_calendar(verdict: str | None = None, limit: int = 100) -> list[dict]:
    """List Calendar rows, optionally filtered by verdict. Newest first."""
    tbl = _table()
    formula = f"{{verdict}} = '{verdict}'" if verdict else None
    recs = tbl.all(formula=formula, sort=["event_date"], max_records=limit)
    return [r["fields"] for r in recs]


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Sync calendar.json → Airtable Calendar table")
    p.add_argument("--days", type=int, default=90,
                   help="how many days ahead to include (default: 90)")
    p.add_argument("--tier", type=int, choices=[1, 2, 3], default=1,
                   help="include events with revenue_tier <= this (default: 1, Tier-1 only)")
    p.add_argument("--list", action="store_true",
                   help="list current Calendar rows instead of syncing")
    p.add_argument("--unreviewed", action="store_true",
                   help="with --list, only show rows with verdict=unreviewed")
    args = p.parse_args()

    if args.list:
        rows = list_calendar(verdict="unreviewed" if args.unreviewed else None)
        if not rows:
            print("(no rows)")
            return
        print(f"{'event_date':12}  {'tier':4}  {'mkt':5}  {'verdict':12}  event_name")
        print("-" * 70)
        for r in rows:
            d = (r.get("event_date") or "")[:10]
            print(f"{d:12}  {r.get('revenue_tier','?'):<4}  "
                  f"{r.get('market','?'):<5}  {r.get('verdict','?'):<12}  "
                  f"{r.get('event_name','?')}")
        return

    print(f"Syncing calendar events (next {args.days} days, tier ≤ {args.tier})...")
    result = sync_calendar(days_ahead=args.days, min_tier=args.tier)
    print(f"  resolved: {result['total_resolved']}")
    print(f"  created : {result['created']}")
    print(f"  updated : {result['updated']}")
    print(f"  skipped : {result['skipped']}")
    if result["errors"]:
        print("\nErrors:")
        for e in result["errors"]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
