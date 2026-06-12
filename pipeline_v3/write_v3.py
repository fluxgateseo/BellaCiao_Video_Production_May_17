"""
write_v3.py — Script-layer derivative asset generation from a v2-approved Reel.

Model (revised from the v3 spec's "parallel write" idea, see rationale below):

  v2 stays the single source of truth for memory.json and continuity_state.json.
  Its `engine.py` write stage produces Scripts/Day N/{episode}.json — the
  canonical Reel script with all state mutations already applied.

  v3 runs AFTER v2 approves a Reel. It reads:
    - Scripts/Day N/{episode}.json       (v2 output, read-only)
    - Briefs row for that episode        (brief_v3-enriched triplet_strategy)

  It generates one true derivative asset and one reuse package:
    - {episode}_CAROUSEL.json — carousel-writer skill, 7-10 slides
    - {episode}_YTSHORT.json  — Reel reuse payload for YouTube packaging

  And copies the Reel alongside:
    - {episode}_REEL.json     — mirror of v2 output for Scripts_v3 completeness

  The Reel remains the master storytelling asset. The YouTube Short companion
  is no longer a separately-written branch by default; it reuses the Reel's
  core spoken content and only carries YT-specific packaging metadata. The
  Carousel remains a true derivative.

Why this model:
  - No memory/continuity races — v3 never mutates v2 state
  - No duplicated writer-pool logic — reuses v2's proven Reel writer by reading
    its output
  - Operator flow is natural — approve Reel in Airtable, then run v3 to fan out

The spec's "one brief → 3 parallel scripts" remains achievable in a future v3.1
if the operator wants to skip v2's Reel approval gate for speed. Not v3.0 scope.

Idempotent: existing v3 output files are preserved unless --force is passed.

Usage:
    python3 -m pipeline_v3.write_v3 --day 12                # all approved episodes in day 12
    python3 -m pipeline_v3.write_v3 --episode-id bella_...  # one episode
    python3 -m pipeline_v3.write_v3 --day 12 --dry-run
    python3 -m pipeline_v3.write_v3 --episode-id ... --force
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from network_probe import require_host

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT))

load_dotenv(_PKG_ROOT.parent / ".env")

from pipeline_v3.skills_client import (  # noqa: E402
    run_carousel_writer,
    SkillResult,
)

AIRTABLE_PAT     = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
NICHE            = os.getenv("V3_NICHE", "SEO for restaurants")

CONTENT_ROOT   = _PKG_ROOT.parent                        # Bellaciao Content/
SCRIPTS_V2_DIR = CONTENT_ROOT / "Creatives" / "Daily assets"
SCRIPTS_V3_DIR = CONTENT_ROOT / "Scripts_v3"
JOBS_DIR       = _PKG_ROOT / "data" / "jobs"


_DAY_RE = re.compile(r"Day\s+(\d+)", re.IGNORECASE)

# A v2 canonical episode filename is bella_{friend}_p{N}_{yyyymmdd}_{hhmm}.json
# (see brand.py friends, content_calendar.py pillar IDs). Anything with an
# extra suffix like _REEL is a companion artifact, not an episode.
_V2_EPISODE_RE = re.compile(r"^bella_[a-z_]+_p\d+_\d{8}_\d{4}\.json$")


def _api():
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError("Airtable not configured (AIRTABLE_PAT/BASE_ID)")
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT)


def _briefs_table():
    return _api().table(AIRTABLE_BASE_ID, "Briefs")


def _deliverables_table():
    return _api().table(AIRTABLE_BASE_ID, "Deliverables")


# ─── Triplet sourcing ────────────────────────────────────────────────────────

def find_v2_episode_file(episode_id: str, day: int | None) -> Path | None:
    """Locate the v2-produced {episode_id}.json anywhere under Daily assets/Day */full scripts."""
    if day is not None:
        candidate = SCRIPTS_V2_DIR / f"Day {day}" / "full scripts" / f"{episode_id}.json"
        if candidate.exists():
            return candidate
        archive_candidate = JOBS_DIR / f"{episode_id}.json"
        return archive_candidate if archive_candidate.exists() else None
    for day_dir in SCRIPTS_V2_DIR.glob("Day */full scripts"):
        candidate = day_dir / f"{episode_id}.json"
        if candidate.exists():
            return candidate
    archive_candidate = JOBS_DIR / f"{episode_id}.json"
    return archive_candidate if archive_candidate.exists() else None


def iter_day_episodes(day: int) -> list[Path]:
    day_dir = SCRIPTS_V2_DIR / f"Day {day}" / "full scripts"
    if day_dir.exists():
        files = sorted(p for p in day_dir.glob("*.json") if _V2_EPISODE_RE.match(p.name))
        if files:
            return files

    archive_files: list[Path] = []
    for job_file in sorted(JOBS_DIR.glob("*.json")):
        if not _V2_EPISODE_RE.match(job_file.name):
            continue
        try:
            payload = json.loads(job_file.read_text())
        except Exception:
            continue
        if str(payload.get("day", "")) == str(day):
            archive_files.append(job_file)
    return archive_files


def day_label_for(v2_episode_file: Path, reel_job: dict) -> str:
    day_match = _DAY_RE.search(str(v2_episode_file))
    if day_match:
        return day_match.group(0)
    day_num = reel_job.get("day")
    if str(day_num).isdigit():
        return f"Day {day_num}"
    return "Day ?"


def load_brief_row(episode_id: str, v2_job: dict | None = None) -> dict | None:
    """Resolve the Airtable Briefs row for an episode.

    Try 1: {episode_id}='...' — only works if briefs_sync has linked it back.
    Try 2: match on (friend, target_date, format) extracted from the v2 job.
    """
    table = _briefs_table()
    rows = table.all(formula=f"{{episode_id}}='{episode_id}'", max_records=1)
    if rows:
        return rows[0]
    if v2_job is None:
        return None
    friend = (v2_job.get("brief") or {}).get("friend")
    target_date = v2_job.get("target_date")
    fmt = (v2_job.get("brief") or {}).get("format")
    if not (friend and target_date and fmt):
        return None
    formula = (
        f"AND({{friend}}='{friend}',"
        f"{{target_date}}='{target_date}',"
        f"{{slot}}='{fmt}')"
    )
    rows = table.all(formula=formula, max_records=1)
    return rows[0] if rows else None


def extract_triplet_strategy(brief_row: dict) -> dict:
    raw = brief_row.get("fields", {}).get("triplet_strategy", "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_text": raw}


def hook_for_platform(strategy: dict, platform: str, fallback: str) -> str:
    """Pull the platform-specific hook out of triplet_strategy. Strategy shape
    is what viral-hook-formula returned — its `parsed` key may carry the
    structured hooks, or we fall back to scanning raw_text."""
    parsed = strategy.get("parsed")
    if isinstance(parsed, dict):
        for key in (platform, f"{platform}_hook", platform.replace("ytshort", "yt_short")):
            if key in parsed:
                entry = parsed[key]
                if isinstance(entry, str):
                    return entry
                if isinstance(entry, dict):
                    return entry.get("hook_text") or entry.get("hook") or fallback
    return fallback


# ─── Derivative asset generation ─────────────────────────────────────────────

def build_ytshort_reuse_payload(
    episode_id: str,
    reel_job: dict,
    strategy: dict,
    brief_row: dict,
) -> dict:
    """
    Reuse the approved Reel as the YouTube Short source of truth.

    We keep a dedicated _YTSHORT.json companion so downstream packaging stays
    stable, but we do not spend another full writing call on a second script.
    """
    brief = reel_job.get("brief", {}) or {}
    fallback_hook = brief.get("chosen_hook_text") or ""
    yt_hook = hook_for_platform(strategy, "ytshort", fallback_hook)
    spoken = (reel_job.get("video_script") or "").strip()

    key_points: list[str] = []
    if spoken:
        for sentence in re.split(r"(?<=[.!?])\s+", spoken):
            sentence = sentence.strip()
            if sentence:
                key_points.append(sentence)
            if len(key_points) >= 5:
                break

    return {
        "episode_id":       episode_id,
        "platform":         "ytshort",
        "source":           "v2_reel_reuse",
        "reused_from":      f"{episode_id}_REEL",
        "script_text":      spoken,
        "script_parsed": {
            "reuse_mode": True,
            "hook_text": yt_hook or fallback_hook,
            "key_points": key_points,
        },
        "input_tokens":     0,
        "output_tokens":    0,
        "triplet_strategy_ref": brief_row.get("fields", {}).get("run_id"),
    }


def derive_carousel(
    reel_job: dict,
    strategy: dict,
) -> SkillResult:
    brief = reel_job.get("brief", {}) or {}
    topic = (
        brief.get("director_note")
        or brief.get("enemy")
        or "restaurant marketing"
    )
    fallback_hook = brief.get("chosen_hook_text") or ""
    carousel_hook = hook_for_platform(strategy, "carousel", fallback_hook)

    return run_carousel_writer(
        topic=topic,
        niche=NICHE,
        goal="saves",
        slide_count=8,
        hook=carousel_hook or None,
    )


# ─── Output + Airtable sync ──────────────────────────────────────────────────

def deliverable_record(
    episode_id: str,
    platform: str,
    script_ref: str,
    notes: str = "",
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "deliverable_id": f"{episode_id}_{platform}",
        "episode_id":     episode_id,
        "platform":       platform,
        "status":         "drafted",
        "script_ref":     script_ref,
        "drafted_at":     now,
        "notes":          notes,
    }


def upsert_deliverable(record: dict) -> None:
    table = _deliverables_table()
    formula = f"{{deliverable_id}}='{record['deliverable_id']}'"
    existing = table.all(formula=formula, max_records=1)
    if existing:
        table.update(existing[0]["id"], record)
    else:
        table.create(record)


def write_asset(
    out_dir: Path,
    episode_id: str,
    platform: str,
    payload: dict,
    *,
    force: bool,
) -> tuple[str, str]:
    """Write one asset JSON. Returns (path, status) where status ∈ {new, skip}."""
    suffix = {"reel": "_REEL", "ytshort": "_YTSHORT", "carousel": "_CAROUSEL"}[platform]
    out_path = out_dir / f"{episode_id}{suffix}.json"
    if out_path.exists() and not force:
        return str(out_path), "skip"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    return str(out_path), "new"


# ─── Triplet processor ───────────────────────────────────────────────────────

def process_episode(
    v2_episode_file: Path,
    *,
    dry_run: bool,
    force: bool,
) -> str:
    episode_id = v2_episode_file.stem

    try:
        reel_job = json.loads(v2_episode_file.read_text())
    except json.JSONDecodeError as e:
        return f"! {episode_id}: cannot parse v2 JSON — {e}"

    day_label = day_label_for(v2_episode_file, reel_job)
    out_dir = SCRIPTS_V3_DIR / day_label

    if dry_run:
        source = "archive" if v2_episode_file.parent == JOBS_DIR else "scripts"
        return (
            f"[dry-run] {episode_id} ({source}) → {out_dir}/"
            f"{{_REEL,_YTSHORT,_CAROUSEL}}.json"
        )

    try:
        brief_row = load_brief_row(episode_id, reel_job)
    except Exception as e:  # noqa: BLE001 - surface Airtable/network failures clearly
        return f"! {episode_id}: cannot load Briefs row — {type(e).__name__}: {e}"
    if brief_row is None:
        return f"! {episode_id}: no Briefs row found — run brief_v3 first"

    strategy = extract_triplet_strategy(brief_row)
    if not strategy:
        return f"! {episode_id}: Briefs.triplet_strategy empty — run brief_v3 first"

    # YT Short now reuses the approved Reel. Only Carousel remains a real
    # derivative generation branch.
    try:
        yt_payload = build_ytshort_reuse_payload(episode_id, reel_job, strategy, brief_row)
    except Exception as e:  # noqa: BLE001
        return f"! {episode_id}: ytshort reuse failed — {type(e).__name__}: {e}"

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut_car = ex.submit(derive_carousel, reel_job, strategy)
            carousel_branch = fut_car.result()
    except Exception as e:  # noqa: BLE001 — surface any skill error clearly
        return f"! {episode_id}: carousel branch failed — {type(e).__name__}: {e}"

    # Build payloads
    reel_payload = {
        "episode_id":  episode_id,
        "platform":    "reel",
        "source":      "v2_engine",
        "source_file": str(v2_episode_file),
        "v2_job":      reel_job,
        "triplet_strategy_ref": brief_row.get("fields", {}).get("run_id"),
    }
    carousel_payload = {
        "episode_id":       episode_id,
        "platform":         "carousel",
        "source":           "v3_carousel-writer",
        "slides_text":      carousel_branch.raw_text,
        "slides_parsed":    carousel_branch.parsed,
        "input_tokens":     carousel_branch.input_tokens,
        "output_tokens":    carousel_branch.output_tokens,
        "triplet_strategy_ref": brief_row.get("fields", {}).get("run_id"),
    }

    # Write files
    statuses = []
    for platform, payload in (("reel", reel_payload), ("ytshort", yt_payload), ("carousel", carousel_payload)):
        path, status = write_asset(out_dir, episode_id, platform, payload, force=force)
        statuses.append(f"{platform}:{status}")
        if status == "new":
            try:
                upsert_deliverable(deliverable_record(episode_id, platform, path))
            except Exception as e:  # noqa: BLE001
                statuses.append(f"{platform}_airtable_err:{type(e).__name__}")

    total_tokens = carousel_branch.input_tokens + carousel_branch.output_tokens
    return f"+ {episode_id} [{' '.join(statuses)}] tokens={total_tokens}"


def main() -> int:
    ap = argparse.ArgumentParser()
    selector = ap.add_mutually_exclusive_group(required=True)
    selector.add_argument("--episode-id")
    selector.add_argument("--day", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="Overwrite existing v3 asset files")
    args = ap.parse_args()

    if args.episode_id:
        v2_file = find_v2_episode_file(args.episode_id, None)
        if v2_file is None:
            print(f"! episode {args.episode_id} not found under Scripts/Day */")
            return 1
        files = [v2_file]
    else:
        files = iter_day_episodes(args.day)
        if not files:
            print(f"! no v2 episode files for Day {args.day} in Daily assets/Day */full scripts or data/jobs")
            return 1

    print(f"[write_v3] processing {len(files)} episode(s)")
    # Sequential across episodes — parallelism lives inside each process_episode.
    had_errors = False
    for f in files:
        result = process_episode(f, dry_run=args.dry_run, force=args.force)
        print(result)
        had_errors = had_errors or result.startswith("!")
    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
