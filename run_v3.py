"""
run_v3.py — Bella Content Engine v3.0 CLI.

Thin dispatcher over pipeline_v3/ stages. Sits alongside the v2.1 `run.py`,
which is untouched. Both CLIs can coexist; v3 writes to Scripts_v3/Day N/
and the new Airtable tables only.

Stages:
  calendar  — enrich ContentCalendar rows with trend seeds (calendar_v3)
  brief     — populate Briefs.triplet_strategy (brief_v3)
  write     — derive YTShort + Carousel from approved Reels (write_v3)
  package   — generate captions + YT title/thumb/SEO description (package_v3)
  visualize — push ShotApproval rows + image prompts for Day N (visualize_v3)
  kling     — author per-video folder text files (PROMPT.txt + frame descriptions) (kling_pack)
  play      — brief → write → package for one day
  status    — report triplet completion per day

Scope: script-layer only. Video production (B-roll, AI prompts, Opus
config) and publication (ManyChat for IG, future YT) are handled by
separate projects in the Bellaciao ecosystem.

Examples:
  python3 run_v3.py --stage calendar
  python3 run_v3.py --stage brief --day 12
  python3 run_v3.py --stage write --episode-id bella_jake_p1_20260425_1800
  python3 run_v3.py --stage play --day 12
  python3 run_v3.py --stage play --day 12 --dry-run
  python3 run_v3.py --stage status --day 12
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

SCRIPTS_V2_DIR = ROOT.parent / "Creatives" / "Daily assets"
SCRIPTS_V3_DIR = ROOT.parent / "Scripts_v3"

V3_LOCKFILE = ROOT / "pipeline_v3" / ".run_v3.lock"
V2_LOCKFILE = ROOT / ".run.lock"


def _run_stage(module: str, extra_args: list[str]) -> int:
    """Invoke a pipeline_v3 module via `python3 -m` so relative imports work."""
    cmd = [sys.executable, "-m", f"pipeline_v3.{module}", *extra_args]
    print(f"[run_v3] exec: {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(ROOT))


def _refuse_if_v2_running() -> None:
    if V2_LOCKFILE.exists():
        print(f"! refuse: v2 run.py appears active (lockfile {V2_LOCKFILE})")
        print("  Wait for v2 to finish, or remove the lockfile if stale, then retry.")
        sys.exit(2)


def _set_lock() -> None:
    V3_LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
    V3_LOCKFILE.write_text(str(os.getpid()))


def _clear_lock() -> None:
    try:
        V3_LOCKFILE.unlink()
    except FileNotFoundError:
        pass


# ─── Status ──────────────────────────────────────────────────────────────────

TRIPLET_FILES = {
    "REEL":             "_REEL.json",
    "YTSHORT":          "_YTSHORT.json",
    "CAROUSEL":         "_CAROUSEL.json",
    "PACKAGE_YT":       "_PACKAGE_YT.json",
    "CAPTION_REEL":     "_CAPTION_REEL.md",
    "CAPTION_YT":       "_CAPTION_YT.md",
    "CAPTION_CAROUSEL": "_CAPTION_CAROUSEL.md",
}
# Script-layer only. BROLL/AIVIDEO/OPUS belong to the downstream video
# project. COMMENTS/CLIPSUITE belong to future downstream systems.
# See Master Documents/CONTENT_PRODUCTION_SYSTEM_V3.md scope section.


def stage_status(day: int | None) -> int:
    if not SCRIPTS_V3_DIR.exists():
        print("Scripts_v3/ does not exist yet — run `--stage play` to create content.")
        return 0
    day_dirs = (
        [SCRIPTS_V3_DIR / f"Day {day}"]
        if day is not None
        else sorted(SCRIPTS_V3_DIR.glob("Day */"))
    )
    total_episodes = 0
    for day_dir in day_dirs:
        if not day_dir.exists():
            print(f"{day_dir.name}: missing")
            continue
        reels = sorted(day_dir.glob("*_REEL.json"))
        print(f"\n=== {day_dir.name} — {len(reels)} episode(s) ===")
        for reel in reels:
            ep = reel.stem.replace("_REEL", "")
            missing = [
                label for label, suffix in TRIPLET_FILES.items()
                if not (day_dir / f"{ep}{suffix}").exists()
            ]
            marker = "✅" if not missing else f"⚠ missing: {', '.join(missing)}"
            print(f"  {ep}: {marker}")
            total_episodes += 1
    print(f"\nTotal episodes: {total_episodes}")
    return 0


# ─── Dispatch ────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(prog="run_v3.py")
    ap.add_argument(
        "--stage",
        required=True,
        choices=["calendar", "brief", "write", "package", "visualize", "kling", "play", "status"],
    )
    ap.add_argument("--day", type=int, help="Target Scripts_v3/Day N/")
    ap.add_argument("--episode-id", help="Single episode id (supported by write/package)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    _refuse_if_v2_running()
    _set_lock()
    try:
        if args.stage == "status":
            rc = stage_status(args.day)
            sys.exit(rc)

        extra: list[str] = []
        if args.episode_id:
            extra += ["--episode-id", args.episode_id]
        elif args.day is not None:
            extra += ["--day", str(args.day)]
        if args.dry_run:
            extra.append("--dry-run")
        if args.force:
            extra.append("--force")

        if args.stage == "calendar":
            # calendar_v3 uses only --day (no --episode-id)
            cal_extra = [x for x in extra if x != "--episode-id" and not (
                len(extra) > 1 and extra[extra.index(x) - 1] == "--episode-id"
            )] if "--episode-id" in extra else extra
            sys.exit(_run_stage("calendar_v3", cal_extra))

        if args.stage == "brief":
            # brief_v3 uses --run-id or --day
            if args.episode_id:
                # brief_v3 selects by run_id, not episode_id; warn and fall back to --day
                print("[run_v3] note: brief stage selects by run_id; --episode-id mapping not supported. Use --day.")
                sys.exit(2)
            sys.exit(_run_stage("brief_v3", extra))

        if args.stage == "write":
            sys.exit(_run_stage("write_v3", extra))

        if args.stage == "package":
            sys.exit(_run_stage("package_v3", extra))

        if args.stage == "visualize":
            if args.day is None:
                print("! visualize requires --day N")
                sys.exit(2)
            vis_extra = ["--day", str(args.day)]
            if args.dry_run:
                vis_extra.append("--dry-run")
            if args.force:
                vis_extra.append("--force")
            sys.exit(_run_stage("visualize_v3", vis_extra))

        if args.stage == "kling":
            if args.day is None:
                print("! kling requires --day N")
                sys.exit(2)
            kling_extra = ["--day", str(args.day)]
            if args.dry_run:
                kling_extra.append("--dry-run")
            sys.exit(_run_stage("kling_pack", kling_extra))

        if args.stage == "play":
            if args.episode_id:
                print("[run_v3] play does not accept --episode-id because brief_v3 cannot scope to one episode.")
                print("[run_v3] Use `--stage write --episode-id ...` and `--stage package --episode-id ...`,")
                print("[run_v3] or run `--stage play --day N` for the full day.")
                sys.exit(2)
            # Sequence: brief → write → package
            # calendar is excluded from play (it's a once-per-plan-cycle stage)
            for module in ("brief_v3", "write_v3", "package_v3"):
                mod_extra = extra
                if module == "brief_v3":
                    # brief_v3 does not accept --episode-id (see note above)
                    mod_extra = [x for x in extra if x != args.episode_id and x != "--episode-id"]
                rc = _run_stage(module, mod_extra)
                if rc != 0:
                    print(f"[run_v3] stage {module} exited with rc={rc}; aborting play")
                    sys.exit(rc)
            sys.exit(0)

    finally:
        _clear_lock()


if __name__ == "__main__":
    main()
