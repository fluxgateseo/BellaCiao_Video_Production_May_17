"""
visualize_v3.py — Generate ShotApproval rows + prompt files for one day.

Reads approved episode scripts and KLING.md for Day N, emits:
  - One character-reference row per character per day (auto-copied across days
    when an earlier approved row exists with the same character_id).
  - One shot row per shot listed in each episode's KLING.md.

Pushes rows to Airtable `ShotApproval` table. Writes scene-body prompts as
.txt files into:
  - Daily assets/Day N/avatars/{character_id}_prompt.txt
  - Daily assets/Day N/ShotApproval/{scene_id}_start_prompt.txt (+ {scene_id}_end_prompt.txt when authored)

Source episode layout: `Daily assets/Day N/full scripts/bella_*_p*_*.json`
(+ matching `.KLING.md`). The folder was renamed from `scripts/` → `full scripts/`
on 2026-04-15; pipeline reads from the new location as of 2026-04-19.

Shot rows carry fields: prompt_image_start, prompt_image_end, is_signoff.
Character-reference rows carry only prompt_image_start (no end frame, no signoff).

This project emits prompt bodies only. Sibling Bellaciao project appends
Shared DNA + negatives and calls Runway Gen-4 (see Master Documents/IMAGE_GENERATION_SPEC.md).

Idempotent. Re-running skips existing rows unless their status is `reroll`,
in which case prompt_image_start/end are regenerated and status reset to `draft`.

Usage:
    python3 -m pipeline_v3.visualize_v3 --day 3
    python3 -m pipeline_v3.visualize_v3 --day 3 --dry-run
    python3 -m pipeline_v3.visualize_v3 --day 3 --force
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT))
load_dotenv(_PKG_ROOT.parent / ".env")

from pipeline_v3.image_prompt_builder import (  # noqa: E402
    parse_kling_md, character_prompt, shot_prompt, shot_is_signoff,
)
from pipeline_v3.face_crop import ensure_face_crop  # noqa: E402

PAT  = os.getenv("AIRTABLE_PAT", "")
BASE = os.getenv("AIRTABLE_BASE_ID", "")
HEAD = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}
TABLE_URL = f"https://api.airtable.com/v0/{BASE}/ShotApproval"

CONTENT_ROOT = _PKG_ROOT.parent
DAILY_ASSETS = CONTENT_ROOT / "Creatives" / "Daily assets"

EPISODE_RE = re.compile(r"^bella_([a-z_]+?)_p(\d+)_\d{8}_\d{4}\.json$")


def _at_query(formula: str, max_records: int = 100, dry_run: bool = False) -> list[dict]:
    if dry_run:
        return []
    r = requests.get(TABLE_URL, headers=HEAD, params={
        "filterByFormula": formula, "maxRecords": max_records,
    })
    r.raise_for_status()
    return r.json().get("records", [])


def _at_create(fields: dict, dry_run: bool) -> str:
    if dry_run:
        return f"  [dry-run] would create {fields.get('scene_id')}"
    r = requests.post(TABLE_URL, headers=HEAD,
                      data=json.dumps({"fields": fields}))
    if r.status_code in (200, 201):
        return f"  + created {fields['scene_id']}"
    return f"  ! create {fields['scene_id']} FAILED ({r.status_code}): {r.text[:200]}"


def _at_update(record_id: str, fields: dict, dry_run: bool) -> str:
    if dry_run:
        return f"  [dry-run] would update {record_id}"
    r = requests.patch(f"{TABLE_URL}/{record_id}", headers=HEAD,
                       data=json.dumps({"fields": fields}))
    if r.status_code == 200:
        return f"  ~ updated {record_id}"
    return f"  ! update {record_id} FAILED ({r.status_code}): {r.text[:200]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_cast(episode_id: str, friend_id: str, kling_path: Path) -> list[str]:
    """Return ordered list of character_ids appearing in this episode.

    Compound friend IDs (e.g. enzo_maria, arun_priya) are kept as single
    cast members — friends_db.json has no per-person sub-records and the
    canonical reference PNG already frames both people together.
    """
    cast = ["bella", "ciao", friend_id]

    from pipeline_v3.image_prompt_builder import _load_allies
    allies = _load_allies()
    for aid, a in allies.items():
        tied = a.get("tied_to_friend_id", "")
        if tied == friend_id:
            first = a.get("first_appearance", {}).get("episode_id", "")
            if first == episode_id or first <= episode_id:
                cast.append(aid)

    seen, out = set(), []
    for c in cast:
        if c not in seen:
            out.append(c); seen.add(c)
    return out


def _process_character(
    character_id: str, day: int, episode_id: str, friend_id: str,
    avatars_dir: Path, dry_run: bool, force: bool,
) -> str:
    scene_id = f"day{day}_char_{character_id}"

    existing = _at_query(f"{{scene_id}}='{scene_id}'", max_records=1, dry_run=dry_run)
    if existing:
        rec = existing[0]
        status = rec["fields"].get("status", "draft")
        if status == "reroll":
            new_prompt = character_prompt(character_id)
            return _at_update(rec["id"], {
                "prompt_image_start": new_prompt, "status": "draft",
                "reroll_notes": "",
            }, dry_run)
        if not force:
            return f"  = {scene_id} already exists (status={status})"

    approved_prior = _at_query(
        f"AND({{character_id}}='{character_id}', "
        f"{{is_character_reference}}=1, {{status}}='approved')",
        max_records=1,
        dry_run=dry_run,
    )

    if approved_prior:
        src = approved_prior[0]["fields"]
        prior_url = src.get("generated_image_url", "")
        prior_path = avatars_dir.parent.parent / f"Day {src.get('day_number')}" / "avatars" / f"{character_id}_reference.png"
        dest_path = avatars_dir / f"{character_id}_reference.png"
        if prior_path.exists() and not dest_path.exists() and not dry_run:
            try:
                dest_path.symlink_to(prior_path)
            except OSError:
                shutil.copy2(prior_path, dest_path)

        # Mirror the face crop alongside the reference. Same identity lock
        # has to follow the character across days — see face_crop.py.
        prior_face = prior_path.with_name(f"{character_id}_face.png")
        dest_face = avatars_dir / f"{character_id}_face.png"
        if prior_face.exists() and not dest_face.exists() and not dry_run:
            try:
                dest_face.symlink_to(prior_face)
            except OSError:
                shutil.copy2(prior_face, dest_face)
        elif dest_path.exists() and not dest_face.exists() and not dry_run:
            # Prior day didn't have a face crop yet — build one now from the
            # reference we just materialized. Happens for pre-face-crop days.
            try:
                ensure_face_crop(dest_path)
            except Exception as e:
                print(f"  ! face-crop failed for {character_id}: {e}")

        fields = {
            "scene_id": scene_id, "episode_id": episode_id,
            "day_number": day, "shot_index": 0,
            "subject": "bella" if character_id == "bella"
                       else "ciao" if character_id == "ciao"
                       else "ally" if character_id != friend_id else "friend",
            "character_id": character_id, "is_character_reference": True,
            "status": "approved", "generated_image_url": prior_url,
            "approved_at": _now_iso(),
            "notes": f"auto-copied from day{src.get('day_number')}_char_{character_id}",
        }
        return _at_create(fields, dry_run)

    body = character_prompt(character_id)

    avatars_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = avatars_dir / f"{character_id}_prompt.txt"
    if not dry_run:
        prompt_file.write_text(body, encoding="utf-8")

    fields = {
        "scene_id": scene_id, "episode_id": episode_id,
        "day_number": day, "shot_index": 0,
        "subject": "bella" if character_id == "bella"
                   else "ciao" if character_id == "ciao"
                   else "ally" if character_id not in friend_id.split("_") else "friend",
        "character_id": character_id, "is_character_reference": True,
        "prompt_image_start": body, "status": "draft",
        "generated_at": _now_iso(),
    }
    return _at_create(fields, dry_run)


def _process_shot(
    shot: dict, episode_id: str, day: int, slot: str, friend_id: str,
    avatars_dir: Path, shotapproval_dir: Path, dry_run: bool, force: bool,
) -> str:
    scene_id = f"{episode_id}_shot{shot['shot_index']:02d}"

    existing = _at_query(f"{{scene_id}}='{scene_id}'", max_records=1, dry_run=dry_run)
    if existing:
        rec = existing[0]
        status = rec["fields"].get("status", "draft")
        if status == "reroll":
            char_paths = _shot_reference_paths(_shot_chars(shot, friend_id), avatars_dir)
            bodies = shot_prompt(shot, char_paths)
            update_fields = {
                "prompt_image_start": bodies["start_body"],
                "prompt_image_end": bodies["end_body"] or "",
                "is_signoff": shot_is_signoff(shot),
                "reference_images": json.dumps(char_paths),
                "status": "draft", "reroll_notes": "",
            }
            return _at_update(rec["id"], update_fields, dry_run)
        if not force:
            return f"  = {scene_id} already exists (status={status})"

    char_ids = _shot_chars(shot, friend_id)
    char_paths = _shot_reference_paths(char_ids, avatars_dir)
    bodies = shot_prompt(shot, char_paths)
    signoff = shot_is_signoff(shot)

    shotapproval_dir.mkdir(parents=True, exist_ok=True)
    start_file = shotapproval_dir / f"{scene_id}_start_prompt.txt"
    end_file   = shotapproval_dir / f"{scene_id}_end_prompt.txt"
    if not dry_run:
        start_file.write_text(bodies["start_body"], encoding="utf-8")
        if bodies["end_body"]:
            end_file.write_text(bodies["end_body"], encoding="utf-8")
        elif end_file.exists():
            end_file.unlink()

    fields = {
        "scene_id": scene_id, "episode_id": episode_id,
        "day_number": day, "slot": slot,
        "shot_index": shot["shot_index"],
        "subject": "scene", "is_character_reference": False,
        "scene_description": shot["title"],
        "prompt_image_start": bodies["start_body"],
        "prompt_image_end": bodies["end_body"] or "",
        "is_signoff": signoff,
        "reference_images": json.dumps(char_paths),
        "status": "draft", "generated_at": _now_iso(),
    }
    return _at_create(fields, dry_run)


def _shot_reference_paths(char_ids: list[str], avatars_dir: Path) -> list[str]:
    """For each character, emit the face crop path. Runway Gen-4 caps
    `referenceImages` at 3 per call and uses the face crop as the
    identity-lock slot — wardrobe/build continuity comes from the Shared
    DNA prompt language, not a second reference image."""
    return [str(avatars_dir / f"{cid}_face.png") for cid in char_ids]


def _shot_chars(shot: dict, friend_id: str) -> list[str]:
    """Return character_ids referenced in this shot. Scans the first-frame
    prompt only (not character_refs_named paths — those contain strings
    like 'Bella's Friends avatar' that would spuriously match BELLA).
    Whole-word case-insensitive matching. Also scans allies by their
    canonical name so Frank/Diane/etc get their refs attached."""
    import re
    from pipeline_v3.image_prompt_builder import _load_allies

    text = shot.get("first_frame_prompt", "")

    def has(name: str) -> bool:
        if not name:
            return False
        return re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE) is not None

    out: list[str] = []
    # Priority order matches Runway Gen-4's 3-ref slot allocation per
    # RUNWAY_IMAGE_MIGRATION_SPEC.md §3.2: Bella > friend > Ciao > ally.
    # When >3 chars appear, shot_prompt() truncates the tail first.
    if has("bella"):
        out.append("bella")
    for p in friend_id.split("_"):
        if has(p):
            out.append(friend_id)
            break
    if has("ciao"):
        out.append("ciao")

    for aid, a in _load_allies().items():
        if has(a.get("name", "")):
            out.append(aid)

    seen, dedup = set(), []
    for c in out:
        if c not in seen:
            dedup.append(c); seen.add(c)
    # Fallback when the first-frame prompt names no one explicitly: use the
    # friend_id (the day's subject), NOT Bella — Bella is narrator, not
    # typically on-camera unless explicitly named.
    return dedup or [friend_id]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate even if rows exist with non-draft status")
    args = ap.parse_args()

    if not args.dry_run and not (PAT and BASE):
        print("! refuse: AIRTABLE_PAT or AIRTABLE_BASE_ID missing in .env")
        sys.exit(2)

    day_dir = DAILY_ASSETS / f"Day {args.day}"
    scripts_dir = day_dir / "full scripts"
    avatars_dir = day_dir / "avatars"
    shotapproval_dir = day_dir / "ShotApproval"

    if not scripts_dir.exists():
        print(f"! refuse: {scripts_dir} not found")
        sys.exit(2)

    episodes = []
    for jp in sorted(scripts_dir.glob("bella_*_p*_*.json")):
        m = EPISODE_RE.match(jp.name)
        if not m:
            continue
        friend_id, slot_n = m.group(1), int(m.group(2))
        episode_id = jp.stem
        kling_path = scripts_dir / f"{episode_id}.KLING.md"
        if not kling_path.exists():
            print(f"  ! skip {episode_id}: no KLING.md")
            continue
        slot = "story" if slot_n == 1 else "reel"
        episodes.append((episode_id, friend_id, slot, kling_path))

    if not episodes:
        print(f"! no episodes found in {scripts_dir}")
        sys.exit(0)

    print(f"=== visualize Day {args.day} ({'DRY RUN' if args.dry_run else 'APPLY'}) ===")
    print(f"  episodes: {[e[0] for e in episodes]}")

    seen_chars: set[str] = set()
    for episode_id, friend_id, slot, kling_path in episodes:
        print(f"\n--- {episode_id} ({slot}) ---")
        cast = _resolve_cast(episode_id, friend_id, kling_path)
        print(f"  cast: {cast}")
        for cid in cast:
            if cid in seen_chars:
                continue
            seen_chars.add(cid)
            print(_process_character(cid, args.day, episode_id, friend_id,
                                     avatars_dir, args.dry_run, args.force))

        shots = parse_kling_md(kling_path)
        for shot in shots:
            print(_process_shot(shot, episode_id, args.day, slot, friend_id,
                                avatars_dir, shotapproval_dir,
                                args.dry_run, args.force))

    print(f"\n=== done. characters: {len(seen_chars)}, shots across episodes: vary ===")


if __name__ == "__main__":
    main()
