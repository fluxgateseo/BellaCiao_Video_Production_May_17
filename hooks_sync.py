"""
hooks_sync.py — convert Master Documents/Bella_Shorts_Hooks.xlsx into the
structured JSON the pipeline reads.

The XLSX is the source of truth (the user adds/edits hooks there). This script
parses the "Bella Hooks" sheet and the "How To Use" sheet, normalises friend
names to canonical friend_ids, and writes data/bella_hooks.json.

Run this whenever the XLSX changes:
    python3 hooks_sync.py
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import openpyxl

BASE_DIR  = Path(__file__).parent
XLSX_PATH = BASE_DIR.parent / "Master Documents" / "Bella_Shorts_Hooks.xlsx"
JSON_OUT  = BASE_DIR / "data" / "bella_hooks.json"


# ─── Friend name normalisation ───────────────────────────────────────────────

FRIEND_NAME_TO_ID = {
    "naomi":       "naomi",
    "sal":         "sal",
    "jake":        "jake",
    "enzo":        "enzo_maria",
    "enzo & maria":"enzo_maria",
    "maria":       "enzo_maria",
    "yasmin":      "yasmin",
    "danny":       "danny",
    "arun":        "arun_priya",
    "priya":       "arun_priya",
    "arun & priya":"arun_priya",
    "sophie":      "sophie",
}


def _normalise_friend(raw: str) -> str:
    """Map a 'Friend / Setting' cell to a canonical friend_id (or 'any')."""
    if not raw:
        return "any"
    text = raw.lower().strip()
    if text.startswith("any"):
        return "any"
    # Strip trailing restaurant name after em dash
    main = re.split(r"\s*[—–-]\s*", text, maxsplit=1)[0].strip()
    if main in FRIEND_NAME_TO_ID:
        return FRIEND_NAME_TO_ID[main]
    # Try first word
    first = main.split()[0] if main else ""
    if first in FRIEND_NAME_TO_ID:
        return FRIEND_NAME_TO_ID[first]
    return "any"


# ─── Markets ─────────────────────────────────────────────────────────────────

def _normalise_market(raw: str) -> list[str]:
    """A 'Market' cell can be 'AU', 'US', 'UK', 'AU / US / UK', etc."""
    if not raw:
        return ["AU", "US", "UK"]
    parts = re.split(r"\s*[/,]\s*", raw.strip())
    return [p.upper() for p in parts if p.strip()]


# ─── Doctrine type normalisation ─────────────────────────────────────────────

def _normalise_doctrine(raw: str) -> str:
    """Pull the doctrine type label without the leading number for nicer display."""
    if not raw:
        return "unknown"
    return raw.strip()


# ─── Pillar normalisation ────────────────────────────────────────────────────

PILLAR_LOOKUP = {
    "p1 operational":     1,
    "p2 authority/proof": 2,
    "p3 education/tutorial": 3,
    "p4 myth-busting":    4,
    "p5 life & friendship": 5,
}


def _normalise_pillar(raw: str) -> int | None:
    if not raw:
        return None
    key = raw.lower().strip()
    return PILLAR_LOOKUP.get(key)


# ─── Main parser ─────────────────────────────────────────────────────────────

def parse_xlsx(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Bella_Shorts_Hooks.xlsx not found at {path}")

    wb = openpyxl.load_workbook(path, data_only=True)
    if "Bella Hooks" not in wb.sheetnames:
        raise ValueError(f"sheet 'Bella Hooks' missing — found: {wb.sheetnames}")

    hooks_sheet = wb["Bella Hooks"]
    rows = list(hooks_sheet.iter_rows(values_only=True))
    if len(rows) < 2:
        raise ValueError("Bella Hooks sheet has no data rows")

    headers = [str(h or "").strip() for h in rows[0]]
    # Required columns
    col = {h: i for i, h in enumerate(headers)}
    required = ["#", "Hook (spoken)", "Doctrine Type", "Style",
                "Friend / Setting", "Real Anchor", "Enemy Archetype",
                "Market", "Pillar", "Zero-Sell", "Why It Works"]
    for r in required:
        if r not in col:
            raise ValueError(f"missing column in XLSX: '{r}' (got {headers})")

    hooks: list[dict] = []
    doctrine_types: set[str] = set()
    styles: set[str] = set()

    for raw_row in rows[1:]:
        if not raw_row or all(c is None for c in raw_row):
            continue
        try:
            n = int(raw_row[col["#"]])
        except (TypeError, ValueError):
            continue

        hook_text = (raw_row[col["Hook (spoken)"]] or "").strip()
        if not hook_text:
            continue
        doctrine = _normalise_doctrine(raw_row[col["Doctrine Type"]] or "")
        style    = (raw_row[col["Style"]] or "").strip()
        friend_raw = (raw_row[col["Friend / Setting"]] or "").strip()
        anchor   = (raw_row[col["Real Anchor"]] or "").strip()
        enemy    = (raw_row[col["Enemy Archetype"]] or "").strip()
        markets  = _normalise_market(raw_row[col["Market"]] or "")
        pillar_raw = raw_row[col["Pillar"]] or ""
        zero_sell = (raw_row[col["Zero-Sell"]] or "").strip().upper()
        why = (raw_row[col["Why It Works"]] or "").strip()

        hooks.append({
            "id":              n,
            "hook":            hook_text,
            "doctrine_type":   doctrine,
            "style":           style,
            "friend":          _normalise_friend(friend_raw),
            "friend_label":    friend_raw,
            "real_anchor":     anchor,
            "enemy_archetype": enemy,
            "markets":         markets,
            "pillar":          _normalise_pillar(pillar_raw),
            "pillar_label":    pillar_raw,
            "zero_sell_pass":  zero_sell == "PASS",
            "why_it_works":    why,
        })
        doctrine_types.add(doctrine)
        styles.add(style)

    # Pull the rules from the "How To Use" sheet
    rules: dict[str, str] = {}
    if "How To Use" in wb.sheetnames:
        ws = wb["How To Use"]
        for r in ws.iter_rows(min_row=2, values_only=True):
            if r and r[0] and r[1]:
                rules[str(r[0]).strip()] = str(r[1]).strip()

    payload = {
        "_meta": {
            "source":         str(path.name),
            "synced_at":      date.today().isoformat(),
            "total_hooks":    len(hooks),
            "doctrine_types": sorted(doctrine_types),
            "styles":         sorted(styles),
        },
        "rules": rules,
        "hooks": hooks,
    }

    # Coverage summary
    by_friend: dict[str, int] = {}
    for h in hooks:
        by_friend[h["friend"]] = by_friend.get(h["friend"], 0) + 1
    payload["_meta"]["coverage_by_friend"] = dict(sorted(by_friend.items()))

    return payload


def main() -> None:
    print(f"Reading {XLSX_PATH}...")
    payload = parse_xlsx(XLSX_PATH)

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {JSON_OUT}")
    print()
    print(f"Hooks parsed: {payload['_meta']['total_hooks']}")
    print(f"Doctrine types: {payload['_meta']['doctrine_types']}")
    print(f"Coverage by friend: {payload['_meta']['coverage_by_friend']}")

    missing = set(FRIEND_NAME_TO_ID.values()) - set(payload['_meta']['coverage_by_friend'].keys()) - {"any"}
    if missing:
        print()
        print(f"⚠ Friends with NO specific hooks: {sorted(missing)}")
        print("  These friends will fall back to 'any' / cross-market hooks.")


if __name__ == "__main__":
    main()
