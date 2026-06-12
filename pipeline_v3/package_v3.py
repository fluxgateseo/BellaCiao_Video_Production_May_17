"""
package_v3.py — Generate script-layer packaging per triplet.

Runs AFTER write_v3.py has produced:
  Scripts_v3/Day N/{ep}_REEL.json
  Scripts_v3/Day N/{ep}_YTSHORT.json
  Scripts_v3/Day N/{ep}_CAROUSEL.json

Produces (per episode):
  {ep}_PACKAGE_YT.json      — yt-title-thumbnail + yt-seo-description (YT channel metadata)
  {ep}_CAPTION_REEL.md      — caption-architect (Reel caption + hashtags)
  {ep}_CAPTION_YT.md        — caption-architect (Static; YouTube community caption)
  {ep}_CAPTION_CAROUSEL.md  — caption-architect (Carousel caption + hashtags)

**Scope: script-layer only.** Video production (B-roll, AI video prompts),
clip-splitting, and publication are handled by other projects in the
Bellaciao ecosystem. See Master Documents/CONTENT_PRODUCTION_SYSTEM_V3.md.

Deliverables rows get their `package_ref` field and `packaged_at` stamp
updated, status transitions drafted → packaged.

Idempotent: existing companion files are preserved unless --force.

Usage:
    python3 -m pipeline_v3.package_v3 --day 12
    python3 -m pipeline_v3.package_v3 --episode-id bella_jake_p1_...
    python3 -m pipeline_v3.package_v3 --day 12 --dry-run
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
    run_caption_architect,
    run_yt_title_thumbnail,
    run_yt_seo_description,
    SkillResult,
)
from pipeline_v3.write_v3 import (  # noqa: E402
    day_label_for,
    find_v2_episode_file,
    iter_day_episodes,
)

AIRTABLE_PAT     = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
NICHE            = os.getenv("V3_NICHE", "SEO for restaurants")

CONTENT_ROOT   = _PKG_ROOT.parent
SCRIPTS_V3_DIR = CONTENT_ROOT / "Scripts_v3"

_DAY_RE = re.compile(r"Day\s+(\d+)", re.IGNORECASE)


def _api():
    if not (AIRTABLE_PAT and AIRTABLE_BASE_ID):
        raise RuntimeError("Airtable not configured (AIRTABLE_PAT/BASE_ID)")
    require_host("api.airtable.com", "Airtable")
    from pyairtable import Api
    return Api(AIRTABLE_PAT)


def _deliverables():
    return _api().table(AIRTABLE_BASE_ID, "Deliverables")


# ─── File discovery ──────────────────────────────────────────────────────────

def find_triplet(day: int | None, episode_id: str | None) -> list[tuple[str, Path]]:
    """Return [(episode_id, day_dir)] tuples where a complete triplet exists."""
    if day is not None:
        day_dir = SCRIPTS_V3_DIR / f"Day {day}"
        if not day_dir.exists():
            return []
        reel_files = sorted(day_dir.glob("*_REEL.json"))
        if episode_id:
            reel_files = [f for f in reel_files if f.stem == f"{episode_id}_REEL"]
    elif episode_id:
        reel_files = list(SCRIPTS_V3_DIR.glob(f"Day */{episode_id}_REEL.json"))
    else:
        return []

    out = []
    for reel in reel_files:
        ep = reel.stem.replace("_REEL", "")
        day_dir = reel.parent
        if (day_dir / f"{ep}_YTSHORT.json").exists() and (day_dir / f"{ep}_CAROUSEL.json").exists():
            out.append((ep, day_dir))
    return out


def infer_triplets_for_dry_run(day: int | None, episode_id: str | None) -> list[tuple[str, Path]]:
    """Infer packaging targets from the v2 source files when write_v3 is also
    running in dry-run mode and has not created Scripts_v3 files yet."""
    files: list[Path] = []
    if day is not None:
        files = iter_day_episodes(day)
    elif episode_id:
        v2_file = find_v2_episode_file(episode_id, None)
        if v2_file is not None:
            files = [v2_file]

    inferred: list[tuple[str, Path]] = []
    for v2_file in files:
        ep = v2_file.stem
        try:
            reel_job = json.loads(v2_file.read_text())
        except Exception:
            continue
        inferred.append((ep, SCRIPTS_V3_DIR / day_label_for(v2_file, reel_job)))
    return inferred


def load_triplet_payloads(ep: str, day_dir: Path) -> dict:
    return {
        "reel":     json.loads((day_dir / f"{ep}_REEL.json").read_text()),
        "ytshort":  json.loads((day_dir / f"{ep}_YTSHORT.json").read_text()),
        "carousel": json.loads((day_dir / f"{ep}_CAROUSEL.json").read_text()),
    }


def extract_topic(reel_payload: dict) -> str:
    job = reel_payload.get("v2_job") or {}
    brief = job.get("brief") or {}
    return (
        brief.get("director_note")
        or brief.get("enemy_failure_mode")
        or brief.get("enemy")
        or "restaurant marketing"
    )


def extract_tone(reel_payload: dict) -> str:
    job = reel_payload.get("v2_job") or {}
    brief = job.get("brief") or {}
    return brief.get("tone") or "mentor, fast-talking, warm"


def extract_yt_key_points(ytshort_payload: dict) -> list[str]:
    parsed = ytshort_payload.get("script_parsed")
    if isinstance(parsed, dict):
        for key in ("key_points", "main_points", "beats"):
            v = parsed.get(key)
            if isinstance(v, list):
                return [str(x) for x in v][:5]
    text = ytshort_payload.get("script_text") or ""
    sents = re.split(r"(?<=[.!?])\s+", str(text))[:3]
    return [s for s in sents if s.strip()]


# ─── Skill invocations ───────────────────────────────────────────────────────

def gen_caption_reel(topic: str, tone: str) -> SkillResult:
    return run_caption_architect(topic, NICHE, "reel", tone, "engagement")

def gen_caption_yt(topic: str, tone: str) -> SkillResult:
    return run_caption_architect(topic, NICHE, "static", tone, "followers")

def gen_caption_carousel(topic: str, tone: str) -> SkillResult:
    return run_caption_architect(topic, NICHE, "carousel", tone, "saves")

def gen_yt_title_thumb(topic: str) -> SkillResult:
    return run_yt_title_thumbnail(topic, NICHE, "restaurant owners 30-55", "curiosity")

def gen_yt_seo(topic: str, title: str, key_points: list[str]) -> SkillResult:
    return run_yt_seo_description(title or topic, topic, key_points or [topic], NICHE)


# ─── Output writers ──────────────────────────────────────────────────────────

def write_json_if_new(path: Path, payload: dict, *, force: bool) -> str:
    if path.exists() and not force:
        return "skip"
    path.write_text(json.dumps(payload, indent=2, default=str))
    return "new"


def write_md_if_new(path: Path, text: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "skip"
    path.write_text(text)
    return "new"


def skill_payload(result: SkillResult, **extra) -> dict:
    return {
        "skill":         result.skill,
        "raw_text":      result.raw_text,
        "parsed":        result.parsed,
        "input_tokens":  result.input_tokens,
        "output_tokens": result.output_tokens,
        **extra,
    }


# ─── Airtable status update ──────────────────────────────────────────────────

def mark_packaged(episode_id: str, platform: str, package_ref: str) -> None:
    table = _deliverables()
    formula = f"{{deliverable_id}}='{episode_id}_{platform}'"
    rows = table.all(formula=formula, max_records=1)
    if not rows:
        return
    table.update(rows[0]["id"], {
        "status":       "packaged",
        "package_ref":  package_ref,
        "packaged_at":  datetime.now(timezone.utc).isoformat(),
    })


# ─── Episode processor ──────────────────────────────────────────────────

def package_episode(ep: str, day_dir: Path, *, dry_run: bool, force: bool) -> str:
    if dry_run:
        return f"[dry-run] {ep} → {day_dir}/: 4 companion files (PACKAGE_YT + 3 captions)"

    try:
        payloads = load_triplet_payloads(ep, day_dir)
    except Exception as e:  # noqa: BLE001 - corrupted local files should not crash the whole stage
        return f"! {ep}: cannot load triplet payloads — {type(e).__name__}: {e}"
    topic = extract_topic(payloads["reel"])
    tone = extract_tone(payloads["reel"])

    yt_key_points = extract_yt_key_points(payloads["ytshort"])

    # YT title runs first — SEO description consumes it.
    try:
        yt_title_res = gen_yt_title_thumb(topic)
    except Exception as e:  # noqa: BLE001
        return f"! {ep}: yt_title branch failed — {type(e).__name__}: {e}"
    yt_title = topic
    if isinstance(yt_title_res.parsed, dict):
        titles = yt_title_res.parsed.get("titles") or yt_title_res.parsed.get("title_variants")
        if isinstance(titles, list) and titles:
            first = titles[0]
            yt_title = first if isinstance(first, str) else first.get("title") or first.get("text") or topic

    # Parallel: 4 remaining Haiku-cheap calls.
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            "caption_reel":     ex.submit(gen_caption_reel, topic, tone),
            "caption_yt":       ex.submit(gen_caption_yt, topic, tone),
            "caption_carousel": ex.submit(gen_caption_carousel, topic, tone),
            "yt_seo":           ex.submit(gen_yt_seo, topic, yt_title, yt_key_points),
        }
        results: dict[str, SkillResult] = {}
        errors: dict[str, str] = {}
        for name, fut in futures.items():
            try:
                results[name] = fut.result()
            except Exception as e:  # noqa: BLE001
                errors[name] = f"{type(e).__name__}: {e}"

    if errors:
        return f"! {ep}: {len(errors)} skill errors: {errors}"

    statuses = {}
    total_tokens = yt_title_res.input_tokens + yt_title_res.output_tokens

    package_yt = {
        "episode_id":   ep,
        "title_thumb":  skill_payload(yt_title_res),
        "seo":          skill_payload(results["yt_seo"]),
    }
    statuses["PACKAGE_YT"] = write_json_if_new(day_dir / f"{ep}_PACKAGE_YT.json", package_yt, force=force)

    statuses["CAPTION_REEL"] = write_md_if_new(
        day_dir / f"{ep}_CAPTION_REEL.md", results["caption_reel"].raw_text, force=force
    )
    statuses["CAPTION_YT"] = write_md_if_new(
        day_dir / f"{ep}_CAPTION_YT.md", results["caption_yt"].raw_text, force=force
    )
    statuses["CAPTION_CAROUSEL"] = write_md_if_new(
        day_dir / f"{ep}_CAPTION_CAROUSEL.md", results["caption_carousel"].raw_text, force=force
    )

    for r in results.values():
        total_tokens += r.input_tokens + r.output_tokens

    airtable_errors = []
    for platform in ("reel", "ytshort", "carousel"):
        try:
            mark_packaged(ep, platform, package_ref=f"Scripts_v3/{day_dir.name}/")
        except Exception as e:  # noqa: BLE001
            airtable_errors.append(f"{platform}:{type(e).__name__}")

    summary = " ".join(f"{k}:{v}" for k, v in statuses.items())
    tail = f" airtable_err={airtable_errors}" if airtable_errors else ""
    return f"+ {ep} [{summary}] tokens={total_tokens}{tail}"


def main() -> int:
    ap = argparse.ArgumentParser()
    selector = ap.add_mutually_exclusive_group(required=True)
    selector.add_argument("--episode-id")
    selector.add_argument("--day", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    triplets = find_triplet(args.day, args.episode_id)
    if not triplets and args.dry_run:
        triplets = infer_triplets_for_dry_run(args.day, args.episode_id)
    if not triplets:
        print("! no complete triplets found under Scripts_v3/")
        return 1

    print(f"[package_v3] processing {len(triplets)} triplet(s)")
    had_errors = False
    for ep, day_dir in triplets:
        result = package_episode(ep, day_dir, dry_run=args.dry_run, force=args.force)
        print(result)
        had_errors = had_errors or result.startswith("!")
    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
