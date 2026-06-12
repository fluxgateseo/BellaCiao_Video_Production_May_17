"""
run.py — Bellaciao Content Engine orchestrator (CLI entry point).

The pipeline is **staged with manual approval gates in Airtable**. The user
controls every step: calendar → plan → brief → write. Each stage refuses
to advance unless the upstream verdict is approved.

USAGE:

    ./.venv/bin/python run.py                                  # default → --status
    ./.venv/bin/python run.py --status                         # show pipeline state per table

    ./.venv/bin/python run.py --stage calendar --days 90                # sync events → Calendar table
    ./.venv/bin/python run.py --stage plan --plan-start 2026-04-12 --plan-days 14
    ./.venv/bin/python run.py --stage brief --target-date 2026-04-25 --slot both
    ./.venv/bin/python run.py --stage write --target-date 2026-04-25 --slot story
    ./.venv/bin/python run.py --stage write --brief-id rec123

    ./.venv/bin/python run.py --auto                           # legacy end-to-end (testing only)
    ./.venv/bin/python run.py --auto --target-date 2026-04-25  # bypasses ALL approval gates

REFUSAL RULES (override with --force):
    --stage brief refuses if ContentCalendar has no status=planned row for
    (target_date, slot), OR if the planned row has no hook_choice set,
    OR if Calendar marks the target_date as verdict=skip.
    --stage write refuses unless the brief's verdict=good.

Reference: Master Documents/CONTROL_SURFACE.md, memory/staged_workflow.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date as _date, datetime, timedelta
from pathlib import Path

BASE_DIR        = Path(__file__).parent
JOBS_DIR        = BASE_DIR / "data" / "jobs"
SCRIPTS_ROOT    = BASE_DIR.parent / "Creatives" / "Daily assets"
SCRIPTS_TEST    = SCRIPTS_ROOT / "Test" / "scripts"

JOBS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Day-folder routing ──────────────────────────────────────────────────────
# Daily assets layout:
#   Creatives/Daily assets/
#     Day N/
#       scripts/    ← episode JSON + companions (this is what we return)
#       avatars/    ← reference PNGs for the day's friend + Bella + Ciao

_DAY_RE = re.compile(r"^Day\s+(\d+)$")

def _list_day_folders() -> list[tuple[int, Path]]:
    """Return (day_number, day_dir/scripts) pairs. Creates scripts/ subfolder on the fly."""
    if not SCRIPTS_ROOT.exists():
        return []
    out: list[tuple[int, Path]] = []
    for child in SCRIPTS_ROOT.iterdir():
        if not child.is_dir():
            continue
        m = _DAY_RE.match(child.name)
        if m:
            scripts_dir = child / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            out.append((int(m.group(1)), scripts_dir))
    out.sort(key=lambda t: t[0])
    return out


def current_day_folder() -> Path:
    days = _list_day_folders()
    if not days:
        target = SCRIPTS_ROOT / "Day 1" / "scripts"
        target.mkdir(parents=True, exist_ok=True)
        return target
    for _n, p in days:
        if not any(p.glob("*.json")):
            return p
    return days[-1][1]


def specific_day_folder(n: int) -> Path:
    target = SCRIPTS_ROOT / f"Day {n}" / "scripts"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _find_day_folder_for_target_date(target_date: str | None) -> Path | None:
    """Return the Day folder that already holds a job with this target_date, or None.

    Ensures both slots for the same publish date land in the same Day folder
    (fixes the bug where slot 2 would jump to the next empty Day N).
    """
    if not target_date:
        return None
    for _n, p in _list_day_folders():
        for jf in p.glob("*.json"):
            if jf.stem.endswith(("_SHORT",)):
                continue
            try:
                j = json.loads(jf.read_text())
            except Exception:
                continue
            if j.get("target_date") == target_date:
                return p
    return None


def _output_dir(*, dry: bool, test: bool, day: int | None, target_date: str | None = None) -> Path:
    if dry or test:
        SCRIPTS_TEST.mkdir(parents=True, exist_ok=True)
        return SCRIPTS_TEST
    if day is not None:
        return specific_day_folder(day)
    match = _find_day_folder_for_target_date(target_date)
    if match is not None:
        return match
    return current_day_folder()


# ─── Section helpers ─────────────────────────────────────────────────────────

_SECTION_RE = re.compile(r"^\s*(?:#+\s*|\*+\s*)?SECTION\s+\d", re.IGNORECASE)

def _extract_section(text: str, label: str) -> str:
    if label not in text:
        return ""
    lines, in_sec, out = text.split("\n"), False, []
    for line in lines:
        if label in line:
            in_sec = True
            continue
        # Boundary: next SECTION heading (with optional markdown prefixes like "# ", "** ", "### ").
        if in_sec and _SECTION_RE.match(line) and label not in line:
            break
        if in_sec:
            out.append(line)
    return "\n".join(out).strip()


def _try_parse_scene_brief(raw: str) -> dict | str:
    if not raw:
        return ""
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("```", 2)[1]
        if candidate.startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.rsplit("```", 1)[0].strip()
    try:
        return json.loads(candidate)
    except Exception:
        return raw


# ─── Job file builder ────────────────────────────────────────────────────────

def _build_job(
    episode_id: str,
    brief: dict,
    gate_dict: dict,
    verdict_dict: dict,
    decision_dict: dict,
    final_script: str,
    final_score: float,
    rounds: int,
    ssml_script: str,
    shot_list_dict: dict | None,
) -> dict:
    spine    = _extract_section(final_script, "SECTION 1")
    spoken   = _extract_section(final_script, "SECTION 2")
    caption  = _extract_section(final_script, "SECTION 3")
    scene    = _try_parse_scene_brief(_extract_section(final_script, "SECTION 4"))

    if isinstance(scene, dict) and brief.get("avatars"):
        scene.setdefault("bella_avatar",  brief["avatars"].get("bella_avatar"))
        scene.setdefault("ciao_avatar",   brief["avatars"].get("ciao_avatar"))
        scene.setdefault("friend_avatar", brief["avatars"].get("friend_avatar"))

    return {
        "episode_id":            episode_id,
        "pipeline_version":      "1.5",
        "mode":                  brief.get("mode") or gate_dict.get("mode") or "generic",
        "target_date":           gate_dict.get("target_date"),
        "brief":                 brief,
        "gate_result":           gate_dict,
        "round":                 rounds,
        "score":                 final_score,
        "verdict":               verdict_dict,
        "supervisor":            decision_dict,
        "story_spine":           spine,
        "video_script":          spoken,
        "video_script_ssml":     ssml_script,
        "caption":               caption,
        "scene_brief":           scene,
        "shot_list":             shot_list_dict or {},
        "near_perfect_override": decision_dict.get("near_perfect_override", False),
        "generated_at":          datetime.now().isoformat(timespec="seconds"),
    }


def _write_job_file(job: dict, dry: bool, test: bool, day: int | None) -> tuple[Path, Path]:
    episode_id = job["episode_id"]
    output_dir  = _output_dir(dry=dry, test=test, day=day, target_date=job.get("target_date"))
    output_path = output_dir / f"{episode_id}.json"

    m = _DAY_RE.match(output_dir.name)
    if m:
        job["day"] = int(m.group(1))

    payload      = json.dumps(job, indent=2, ensure_ascii=False, default=str)
    archive_path = JOBS_DIR / f"{episode_id}.json"
    archive_path.write_text(payload)
    output_path.write_text(payload)

    # Companion readable .txt file — the user reads/edits this, not the JSON.
    txt_path = output_path.with_suffix(".txt")
    txt_path.write_text(_job_to_text(job))

    # Standalone Instagram caption companion — kept separate from the spoken script
    # so social scheduling tools can grab it without parsing sections.
    caption_text = (job.get("caption") or "").strip()
    if caption_text:
        caption_path = output_dir / f"{episode_id}_CAPTION.txt"
        caption_path.write_text(caption_text + "\n")

    # Video engine prompt documents (HeyGen / Seedance / Kling).
    # Only generated if the job has a real shot_list with shots.
    try:
        from video_prompts import generate_prompt_docs
        docs = generate_prompt_docs(output_path)
        if docs:
            print(f"  prompts  → {len(docs)} video engine docs written")
    except Exception as e:
        print(f"  [video-prompts] skipped: {e}")

    return archive_path, output_path


def _job_to_text(job: dict) -> str:
    """Render a job dict as a human-readable text file for review/editing."""
    brief = job.get("brief") or {}
    lines = [
        f"BELLA SCRIPT — {job.get('episode_id', 'unknown')}",
        "=" * 60,
        f"Friend    : {brief.get('friend', '?')} ({brief.get('city', '?')})",
        f"Format    : {brief.get('format', '?')}",
        f"Pillar    : {brief.get('pillar', '?')}",
        f"Tone      : {brief.get('tone', '?')}",
        f"Duration  : {brief.get('target_duration_seconds', '?')}s",
        f"Score     : {job.get('score', '?')}/10",
        f"Mode      : {job.get('mode', '?')}",
        f"Date      : {job.get('target_date', '?')}",
        f"Generated : {job.get('generated_at', '?')}",
        "",
        "",
        "SECTION 1 — STORY SPINE",
        "-" * 60,
        job.get("story_spine", "(empty)"),
        "",
        "",
        "SECTION 2 — VIDEO SCRIPT",
        "-" * 60,
        job.get("video_script", "(empty)"),
        "",
        "",
        "SECTION 3 — INSTAGRAM CAPTION",
        "-" * 60,
        job.get("caption", "(empty)"),
        "",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — CALENDAR SYNC
# ═══════════════════════════════════════════════════════════════════════════════

def stage_calendar(args: argparse.Namespace) -> int:
    """Sync calendar.json events to Airtable Calendar table. STOP for user review."""
    print("=" * 60)
    print(f"STAGE: CALENDAR  (next {args.days} days, tier ≤ {args.tier})")
    print("=" * 60)

    try:
        from calendar_sync import sync_calendar
        result = sync_calendar(days_ahead=args.days, min_tier=args.tier)
    except Exception as e:
        print(f"[calendar] FAILED: {e}")
        return 1

    print(f"  resolved: {result['total_resolved']}")
    print(f"  created : {result['created']}")
    print(f"  updated : {result['updated']}")
    print(f"  skipped : {result['skipped']}")
    if result["errors"]:
        print("  errors:")
        for e in result["errors"]:
            print(f"    {e}")

    print()
    print("Next: open the Airtable Calendar table. For each Tier-1 event you want a")
    print("script for, set verdict='scheduled'. Mark the rest 'skip'. The brief stage")
    print("only anchors on events with verdict='scheduled'.")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — PLAN (regenerate the content calendar + push to ContentCalendar table)
# ═══════════════════════════════════════════════════════════════════════════════

def stage_plan(args: argparse.Namespace) -> int:
    """
    Regenerate the content calendar (N days × 2 slots) and push to the
    ContentCalendar Airtable table for review.

    The user reviews each row in Airtable, edits friend / pillar / story_seed
    if needed, and marks `status=planned` to lock it in. The brief stage
    refuses to run for a (target_date, slot) unless its ContentCalendar row
    is status=planned.
    """
    print("=" * 60)
    print(f"STAGE: PLAN  ({args.plan_days} days from {args.plan_start or 'today'})")
    print("=" * 60)

    import content_calendar
    start = _date.fromisoformat(args.plan_start) if args.plan_start else _date.today()

    rows = content_calendar.generate(start, args.plan_days)
    json_path = content_calendar.write_json(rows, start, args.plan_days)
    md_path   = content_calendar.write_markdown(rows, start, args.plan_days)
    print(f"  generated  : {len(rows)} rows ({args.plan_days} days × 2 slots)")
    print(f"  json       → {json_path}")
    print(f"  markdown   → {md_path}")

    airtable_ok = True
    try:
        from content_calendar_sync import push_plan_rows
        row_dicts = [r.to_dict() for r in rows]
        result = push_plan_rows(row_dicts)
        print(f"  airtable   → ContentCalendar table "
              f"(created={result['created']} updated={result['updated']} skipped={result['skipped']})")
        for e in result.get("errors", [])[:5]:
            print(f"             err: {e}")
    except Exception as e:
        print(f"  [airtable] push failed: {e}")
        airtable_ok = False

    print()
    if airtable_ok:
        print("Next: open the Airtable ContentCalendar table.")
        print("For each (date, slot) row you want to ship, set status='planned'.")
        print("Set status='skip' on rows you want to drop. Edit friend/pillar/story_seed inline first if needed.")
    else:
        print("Next: review the LOCAL plan files because Airtable is unavailable.")
        print("Edit data/content_calendar.json and set, per row:")
        print("  status='planned'")
        print("  hook_choice / pillar_choice / story_seed_choice / sensory_hook_choice")
        print("The brief stage will read those local choices as a fallback.")
    print()
    print("Then per planned day:")
    print("  ./.venv/bin/python run.py --stage brief --target-date YYYY-MM-DD --slot both")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — BRIEF PREVIEW (the user verifies BEFORE writers run)
# ═══════════════════════════════════════════════════════════════════════════════


def _check_calendar_for_target(target_date: str) -> tuple[bool, str]:
    """
    Return (ok, msg). Refuse if a Tier-1 event lands on target_date and the
    user has explicitly marked it skip. Otherwise approve.
    """
    try:
        from calendar_sync import list_calendar
        rows = list_calendar()
    except Exception as e:
        return True, f"(calendar table unreachable, allowing through: {e})"

    for r in rows:
        ed = (r.get("event_date") or "")[:10]
        if ed != target_date:
            continue
        verdict = r.get("verdict")
        if verdict == "skip":
            return False, f"calendar event '{r.get('event_name')}' on {target_date} is verdict=skip"
        if verdict == "scheduled":
            return True, f"calendar event '{r.get('event_name')}' is scheduled for {target_date}"
    return True, f"no scheduled Tier-1 event on {target_date} → generic mode"


def _check_plan_for_target(target_date: str, slot: str) -> tuple[bool, dict | None, str]:
    """
    Return (ok, planned_row, msg). Refuse if there's no status=planned row in
    ContentCalendar for (target_date, slot), OR if the row has no hook_choice set,
    OR if the row has no pillar_choice set, OR if the row has no story_seed_choice set.
    """
    try:
        from content_calendar_sync import fetch_planned_row
        row = fetch_planned_row(target_date, slot)
    except Exception as e:
        return False, None, f"ContentCalendar unreachable: {e}"
    if not row:
        return False, None, (
            f"no ContentCalendar row with status='planned' for "
            f"target_date={target_date} slot={slot}"
        )
    if not row.get("hook_choice"):
        return False, row, (
            f"plan row exists but hook_choice is unset — pick 1, 2, or 3 in Airtable"
        )
    if not row.get("pillar_choice"):
        return False, row, (
            f"plan row exists but pillar_choice is unset — pick 1, 2, or 3 in Airtable"
        )
    if not row.get("story_seed_choice"):
        return False, row, (
            f"plan row exists but story_seed_choice is unset — pick 1, 2, or 3 in Airtable"
        )
    if not row.get("sensory_hook_choice"):
        return False, row, (
            f"plan row exists but sensory_hook_choice is unset — pick 1, 2, or 3 in Airtable"
        )
    chosen_pillar, _ = _resolve_chosen_pillar(row)
    return True, row, (
        f"plan row {row.get('plan_id')} "
        f"(friend={row.get('friend')}, pillar={chosen_pillar}, "
        f"hook_choice={row.get('hook_choice')}, pillar_choice={row.get('pillar_choice')}, "
        f"story_seed_choice={row.get('story_seed_choice')}, "
        f"sensory_hook_choice={row.get('sensory_hook_choice')})"
    )


def _resolve_locked_hook(plan_row: dict) -> dict:
    """
    Pull the chosen hook (1/2/3) out of a planned ContentCalendar row.
    Returns {'id', 'text', 'doctrine'} or empty dict if no choice.
    """
    choice = plan_row.get("hook_choice")
    if choice not in ("1", "2", "3"):
        return {}
    return {
        "id":       plan_row.get(f"hook_{choice}_id") or 0,
        "text":     plan_row.get(f"hook_{choice}_text") or "",
        "doctrine": plan_row.get(f"hook_{choice}_doctrine") or "",
    }


def _resolve_chosen_pillar(plan_row: dict) -> tuple[int, str]:
    """
    Pull the chosen pillar (1/2/3) out of a planned ContentCalendar row.
    Returns (pillar_int, pillar_theme) or (0, "") if no choice.
    Falls back to legacy `pillar` field for backward compatibility.
    """
    choice = plan_row.get("pillar_choice")
    if choice in ("1", "2", "3"):
        return (
            int(plan_row.get(f"pillar_{choice}") or 0),
            plan_row.get(f"pillar_{choice}_theme") or "",
        )
    # Legacy fallback
    return (int(plan_row.get("pillar") or 0), plan_row.get("pillar_theme") or "")


def _resolve_chosen_story_seed(plan_row: dict) -> str:
    """
    Pull the chosen story seed (1/2/3) out of a planned ContentCalendar row.
    Returns the seed text or "" if no choice. Falls back to legacy `story_seed`.
    """
    choice = plan_row.get("story_seed_choice")
    if choice in ("1", "2", "3"):
        return plan_row.get(f"story_seed_{choice}") or ""
    return plan_row.get("story_seed") or ""


def _resolve_chosen_sensory_hook(plan_row: dict) -> str:
    """
    Pull the chosen sensory_hook (1/2/3) out of a planned ContentCalendar row.
    Returns the hook text or "" if no choice. Empty falls back to strategy's
    auto-pick from friends_db.json.
    """
    choice = plan_row.get("sensory_hook_choice")
    if choice in ("1", "2", "3"):
        return plan_row.get(f"sensory_hook_{choice}") or ""
    return ""


def stage_brief(args: argparse.Namespace) -> int:
    """
    Run gate + strategy + push brief to Airtable Briefs table for human review.
    NO writers run here. The expensive stage (--stage write) is gated by the
    verdict the user sets after reviewing this row.

    Bella publishes a story AND a reel each day. Pass --slot story or
    --slot reel to generate one brief at a time, or --slot both to generate
    both back-to-back (two Opus calls, two Briefs rows for review).
    """
    if not args.target_date:
        print("[brief] --target-date YYYY-MM-DD is required for --stage brief")
        return 1

    slot_arg = (args.slot or "").lower()
    if slot_arg not in ("story", "reel", "both"):
        print("[brief] --slot is required: story | reel | both")
        print("        Bella publishes a story AND a reel each day. Pick which to generate.")
        return 1

    slots_to_run = ("story", "reel") if slot_arg == "both" else (slot_arg,)

    print("=" * 60)
    print(f"STAGE: BRIEF  (target_date={args.target_date}, slots={','.join(slots_to_run)})")
    print("=" * 60)

    # Upstream gate check #1 — ContentCalendar must have a planned row per slot
    plan_rows: dict[str, dict] = {}
    for slot_name in slots_to_run:
        ok_plan, plan_row, plan_msg = _check_plan_for_target(args.target_date, slot_name)
        if not ok_plan and not args.force:
            print(f"  [refused] ({slot_name}) {plan_msg}")
            print(f"  Run `./.venv/bin/python run.py --stage plan` and mark this row status='planned' first.")
            print("  Or pass --force to bypass.")
            return 1
        print(f"  plan ({slot_name:5}) : {plan_msg}")
        if plan_row:
            plan_rows[slot_name] = plan_row

    # Upstream gate check #2 — Calendar must not mark target_date as skip
    ok_cal, cal_msg = _check_calendar_for_target(args.target_date)
    if not ok_cal and not args.force:
        print(f"  [refused] {cal_msg}")
        print("  Pass --force if you want to write a script for this date anyway.")
        return 1
    print(f"  calendar   : {cal_msg}")

    # The plan rows carry the user's authoritative friend/pillar choice.
    # Pull it out (both slots share the same friend per day) and pass it to the
    # gate as a forced friend so the gate honours the user's plan.
    forced_friend = args.friend
    forced_pillar = args.pillar
    if plan_rows:
        first_plan = next(iter(plan_rows.values()))
        forced_friend = forced_friend or first_plan.get("friend")
        if not forced_pillar:
            chosen_pillar, _ = _resolve_chosen_pillar(first_plan)
            forced_pillar = chosen_pillar or None
        if forced_friend == "—":
            forced_friend = None
    if forced_friend:
        print(f"  override   : friend={forced_friend} pillar={forced_pillar} (from ContentCalendar)")

    # Run gate ONCE — both slots share the same friend/city/mode for the day
    import logical_gate
    from logical_gate import GateFailure
    target = _date.fromisoformat(args.target_date)
    try:
        gate = logical_gate.run_gate("reel", forced_pillar, forced_friend, target)
    except GateFailure as e:
        print(f"  [refused] LOGICAL GATE FAILED: {e}")
        return 1

    print()
    print(f"  mode     : {gate.mode}")
    print(f"  city     : {gate.city}")
    print(f"  friend   : {gate.friend_id} ({gate.friend_name})")
    print(f"  currency : {gate.currency}")
    print(f"  event    : {gate.mandatory_event or '(none)'}")
    for n in gate.notes:
        print(f"  note     : {n}")

    import strategy
    import engine
    from briefs_sync import preview_brief, fetch_brief_pending_rewrite

    rc = 0
    local_preview_only = False
    for slot_name in slots_to_run:
        print()
        print(f"─── slot: {slot_name} " + "─" * (50 - len(slot_name)))

        # Rewrite-loop check: is there an existing brief for this (date, slot)
        # that the user marked rewrite_needed? If so, pull their feedback and
        # feed it into the strategy director, then upsert the row in place
        # (verdict resets to unreviewed, regeneration_count increments).
        rewrite_feedback = ""
        regeneration_count = 0
        is_regeneration   = False
        try:
            pending = fetch_brief_pending_rewrite(args.target_date, slot_name)
        except Exception as e:
            pending = None
            print(f"  [warn] rewrite-pending check failed: {e}")
        if pending:
            rewrite_feedback   = pending.get("rewrite_notes") or pending.get("notes") or ""
            regeneration_count = int(pending.get("regeneration_count") or 0) + 1
            is_regeneration    = True
            print(f"  REWRITE LOOP: existing brief verdict=rewrite_needed (round {regeneration_count})")
            if rewrite_feedback:
                preview = rewrite_feedback[:120]
                print(f"  user feedback: {preview}{'...' if len(rewrite_feedback) > 120 else ''}")
            else:
                print(f"  [warn] no rewrite_notes/notes on the row — regenerating without specific feedback")

        # Pull the locked hook from the planned ContentCalendar row
        locked_hook = _resolve_locked_hook(plan_rows.get(slot_name) or {})
        if locked_hook.get("text"):
            preview = locked_hook["text"][:80]
            print(f"  locked hook: #{locked_hook['id']} ({locked_hook['doctrine']})")
            print(f"               \"{preview}{'...' if len(locked_hook['text']) > 80 else ''}\"")
        else:
            print(f"  [warn] no locked hook on plan row — writer will fall back to sensory image")

        # Pull the chosen story seed (the user's locked creative direction)
        locked_story_seed = _resolve_chosen_story_seed(plan_rows.get(slot_name) or {})
        if locked_story_seed:
            preview = locked_story_seed[:120]
            print(f"  locked seed: \"{preview}{'...' if len(locked_story_seed) > 120 else ''}\"")

        # Pull the chosen sensory hook (overrides strategy's auto-pick from friends_db)
        locked_sensory = _resolve_chosen_sensory_hook(plan_rows.get(slot_name) or {})
        if locked_sensory:
            preview = locked_sensory[:120]
            print(f"  locked sens: \"{preview}{'...' if len(locked_sensory) > 120 else ''}\"")

        # Resolve pillar PER SLOT (v1.8+) — story and reel may have different
        # pillar_choice values under the archetype doctrine. The shared gate
        # carries only one pillar; override it with the slot-specific choice.
        slot_pillar = args.pillar
        if not slot_pillar and plan_rows.get(slot_name):
            slot_chosen_pillar, _ = _resolve_chosen_pillar(plan_rows[slot_name])
            slot_pillar = slot_chosen_pillar or None
        if slot_pillar and slot_pillar != forced_pillar:
            print(f"  per-slot pillar: {slot_pillar} (overrides shared gate pillar {forced_pillar})")

        print(f"  generating {slot_name} brief...")
        try:
            brief = strategy.generate_brief(
                gate, slot_name, slot_pillar,
                rewrite_feedback=rewrite_feedback,
                locked_hook=locked_hook or None,
                locked_story_seed=locked_story_seed or None,
                locked_sensory_hook=locked_sensory or None,
            )
        except Exception as e:
            print(f"  [refused] strategy director failed: {e}")
            rc = max(rc, 1)
            continue
        # Defensive: stamp the slot in case the director's JSON dropped it
        brief["format"] = slot_name

        print(f"  pillar   : {brief.get('pillar')}")
        print(f"  enemy    : {brief.get('enemy')}")
        print(f"  ally     : {brief.get('ally')}")
        print(f"  tone     : {brief.get('tone')}")
        print(f"  duration : {brief.get('target_duration_seconds')}s")

        try:
            prompt_preview = engine.build_generation_prompt(brief)[:8000]
        except Exception as e:
            print(f"  [warn] writer_prompt_preview build failed: {e}")
            prompt_preview = ""

        try:
            rec_id = preview_brief(
                brief,
                target_date           = args.target_date,
                writer_prompt_preview = prompt_preview,
                regeneration_count    = regeneration_count,
                is_regeneration       = is_regeneration,
            )
            label = "regenerated" if is_regeneration else "unreviewed"
            if str(rec_id).startswith("local:"):
                local_preview_only = True
                print(f"  local brief → {rec_id}  (verdict={label}, slot={slot_name})")
            else:
                print(f"  briefs row → {rec_id}  (verdict={label}, slot={slot_name})")
        except Exception as e:
            print(f"  [warn] briefs push failed: {e}")
            rc = max(rc, 2)

    print()
    if local_preview_only:
        print("Next: review the local brief cache in script_engine/data/briefs_local.json.")
        print("Verify subjects (friend), location (city/neighbourhood),")
        print("director note, and writer_prompt_preview. Set verdict='good' there, or use --force to bypass review.")
    else:
        print("Next: open the Airtable Briefs table and review each new row.")
        print("Verify subjects (friend), location (city/neighbourhood),")
        print("director note, and the writer_prompt_preview. Set verdict='good' to unlock")
    print(f"  ./.venv/bin/python run.py --stage write --target-date {args.target_date} --slot story")
    print(f"  ./.venv/bin/python run.py --stage write --target-date {args.target_date} --slot reel")
    return rc


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — WRITE (only runs if upstream brief verdict=good)
# ═══════════════════════════════════════════════════════════════════════════════

def stage_write(args: argparse.Namespace) -> int:
    """
    Read an approved brief from Airtable and run the writers + judge + supervisor
    + ssml + shot_director. Refuses if the brief is not verdict=good.
    """
    print("=" * 60)
    print("STAGE: WRITE")
    print("=" * 60)

    from briefs_sync import (
        fetch_brief_by_record_id,
        fetch_approved_brief_for_date,
        fetch_any_brief_for_date,
        parse_brief_json,
        mark_brief_episode,
    )

    brief_row: dict | None = None
    if args.brief_id:
        brief_row = fetch_brief_by_record_id(args.brief_id)
        if not brief_row:
            print(f"  [refused] brief {args.brief_id} not found in Airtable")
            return 1
    elif args.target_date:
        slot_arg = (args.slot or "").lower()
        if slot_arg not in ("story", "reel"):
            print("[write] --slot story|reel is required when looking up by --target-date")
            print("        (a day has both a story brief and a reel brief)")
            return 1
        brief_row = fetch_approved_brief_for_date(args.target_date, slot=slot_arg)
        if not brief_row and args.force:
            # --force: fall back to ANY brief for this (date, slot), even
            # one that is still verdict=unreviewed. This is what `--stage play`
            # needs after it just generated the brief in the same loop.
            brief_row = fetch_any_brief_for_date(args.target_date, slot=slot_arg)
            if brief_row:
                print(f"  [--force] using brief verdict='{brief_row.get('verdict')}' (no verdict=good brief found)")
        if not brief_row:
            print(f"  [refused] no {slot_arg} brief with verdict=good for target_date={args.target_date}")
            print(f"  Run `--stage brief --target-date {args.target_date} --slot {slot_arg}` and approve it first.")
            print(f"  Or pass --force to use any brief for this (date, slot).")
            return 1
    else:
        print("[write] either --brief-id or --target-date is required for --stage write")
        return 1

    verdict = brief_row.get("verdict")
    if verdict != "good" and not args.force:
        print(f"  [refused] brief verdict is '{verdict}', not 'good'")
        print("  Approve it in Airtable (set verdict=good) or pass --force.")
        return 1

    if not getattr(args, "_brief_record_id", None):
        args._brief_record_id = brief_row.get("_record_id")

    if brief_row.get("script_produced"):
        print(f"  [refused] this brief already produced episode "
              f"{brief_row.get('episode_id')} — passing the same brief twice would duplicate.")
        if not args.force:
            return 1

    brief = parse_brief_json(brief_row)
    if not brief:
        print("  [refused] could not parse brief_json field on the row")
        return 1

    slot_label = brief_row.get("slot") or brief.get("format") or "?"
    print(f"  brief    : {brief_row.get('_record_id')}  ({brief.get('friend')}/p{brief.get('pillar')}/{slot_label})")
    print(f"  target   : {brief_row.get('target_date')}")
    if str(brief_row.get("_record_id", "")).startswith("local:"):
        print("  source   : local brief cache")
    print(f"  verdict  : {verdict}{' (FORCED)' if verdict != 'good' else ''}")

    # The brief carries the gate's mode/city/currency — we don't re-run the gate here.
    gate_dict = {
        "mode":         brief.get("mode"),
        "target_date":  brief_row.get("target_date"),
        "city":         brief.get("city"),
        "market":       brief.get("market"),
        "friend_id":    brief.get("friend"),
        "currency":     brief.get("currency"),
    }

    return _write_from_brief(brief, gate_dict, args)


def _write_from_brief(brief: dict, gate_dict: dict, args: argparse.Namespace) -> int:
    """
    Common write path — used by both --stage write and --auto. Runs the
    expensive part of the pipeline (writers, judge, supervisor, ssml, shots)
    against an already-approved brief.
    """
    import engine
    import quality_supervisor as qs
    import ssml_tagger
    import memory as memory_mod
    import shot_director

    episode_id = (
        f"bella_{brief['friend']}_p{brief.get('pillar','x')}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M')}"
    )

    print()
    print(f"  episode  : {episode_id}")
    print()

    # Writer + supervisor loop (max 3 rounds)
    rewrite_notes  = ""
    best_verdict   = None
    best_decision  = None
    best_score     = -1.0
    best_script    = ""
    final_round    = 0

    for round_num in range(1, 4):
        print(f"  round {round_num}/3 — writers in parallel...")
        try:
            verdict = engine.write_and_judge(brief, rewrite_notes, round_num)
        except Exception as e:
            print(f"  [run] round {round_num} failed: {e}")
            if round_num >= 3:
                break
            continue

        score = float(verdict.best_weighted_score or 0)
        print(f"  judge    : winner={verdict.winner}  score={score:.2f}/10")

        decision = qs.evaluate(verdict.to_dict(), brief, round_num)
        print(f"  gates    : {decision.status.value}  ({decision.gate_pass_count}/7)")

        if score > best_score:
            best_verdict, best_decision = verdict, decision
            best_score, best_script     = score, verdict.best_script
            final_round = round_num

        if decision.status in (qs.SupervisorStatus.APPROVED,
                               qs.SupervisorStatus.NEAR_PERFECT_OVERRIDE):
            best_verdict, best_decision = verdict, decision
            best_score, best_script     = score, verdict.best_script
            final_round = round_num
            break

        rewrite_notes = decision.feedback.to_prompt_block() if decision.feedback else ""

    if best_verdict is None:
        print("\n  [run] no usable verdict from any round")
        return 1

    # Polish pass if still rejected
    if best_decision and best_decision.status == qs.SupervisorStatus.REJECTED:
        print(f"\n  polish pass (best so far {best_score:.2f})...")
        polished = qs.polish_pass(
            best_script,
            best_decision.feedback.weak_dimensions if best_decision.feedback else [],
            brief,
            score=best_score,
            judge_notes="; ".join((best_verdict.rationale or {}).values()),
        )
        if polished and polished != best_script:
            best_script = polished
            polished_v_dict = best_verdict.to_dict()
            polished_v_dict["best_script"] = polished
            polished_v_dict["scripts"] = {best_verdict.winner: polished}
            best_decision = qs.evaluate(polished_v_dict, brief, final_round + 1)
            print(f"  post-polish: {best_decision.status.value} score≈{best_decision.score:.2f}")

    # SSML
    try:
        ssml_script = ssml_tagger.tag_script(best_script, brief)
    except Exception as e:
        print(f"  [ssml] failed: {e}")
        ssml_script = ""

    # Shot list
    try:
        scene_section = _try_parse_scene_brief(_extract_section(best_script, "SECTION 4"))
        shot_list_obj = shot_director.build_shot_list(
            approved_script = best_script,
            brief           = brief,
            scene_brief     = scene_section,
            clip_length     = args.clip_length,
        )
        shot_list_dict = shot_list_obj.to_dict()
        print(f"  shots    : {shot_list_dict.get('clip_count', 0)} × {args.clip_length}s")
    except Exception as e:
        print(f"  [shot-director] failed: {e}")
        shot_list_dict = {}

    # Build job + write file
    job = _build_job(
        episode_id     = episode_id,
        brief          = brief,
        gate_dict      = gate_dict,
        verdict_dict   = best_verdict.to_dict(),
        decision_dict  = best_decision.to_dict() if best_decision else {},
        final_script   = best_script,
        final_score    = best_score,
        rounds         = final_round,
        ssml_script    = ssml_script,
        shot_list_dict = shot_list_dict,
    )

    archive_path, output_path = _write_job_file(
        job, dry=False, test=args.test, day=args.day,
    )

    try:
        memory_mod.save_memory(job, best_verdict.to_dict())
    except Exception as e:
        print(f"  [memory] save failed: {e}")

    # Push the produced Scripts row
    if not args.no_airtable:
        try:
            from airtable_sync import push_script
            rec_id = push_script(job)
            print(f"  scripts  → {rec_id}")
        except Exception as e:
            print(f"  [scripts] sync skipped: {e}")

    # Mark the brief row as having produced this episode
    if not args.no_airtable and getattr(args, "_brief_record_id", None):
        try:
            from briefs_sync import mark_brief_episode
            mark_brief_episode(args._brief_record_id, episode_id)
        except Exception as e:
            print(f"  [briefs] mark_episode failed: {e}")

    # Continuity Director — update the friend's narrative state so the NEXT
    # brief for this friend picks up where this episode left off. Uses Claude
    # Haiku, best-effort, never blocks. Gated by --no-continuity for tests.
    if not getattr(args, "no_continuity", False):
        try:
            from continuity import update_state_from_job
            update_state_from_job(job)
        except Exception as e:
            print(f"  [continuity] update skipped: {e}")

    print("\n" + "=" * 60)
    print(f"FINAL SCORE: {best_score:.2f}/10  (target ≥ 9.5)")
    print("=" * 60)
    if job.get("video_script"):
        print()
        print(job["video_script"][:600] + ("..." if len(job["video_script"]) > 600 else ""))
    print(f"\n  archive  → {archive_path}")
    print(f"  output   → {output_path}")

    if best_decision and best_decision.status in (
        qs.SupervisorStatus.APPROVED,
        qs.SupervisorStatus.NEAR_PERFECT_OVERRIDE,
    ):
        return 0
    return 2


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS — show pipeline state per table
# ═══════════════════════════════════════════════════════════════════════════════

def stage_status(args: argparse.Namespace) -> int:
    """Show what's at each stage. The default action when no --stage is given."""
    print("=" * 60)
    print("BELLA SCRIPT ENGINE — pipeline status")
    print("=" * 60)

    # Calendar
    try:
        from calendar_sync import list_calendar
        cal_rows = list_calendar()
        by_v = {}
        for r in cal_rows:
            by_v[r.get("verdict") or "unreviewed"] = by_v.get(r.get("verdict") or "unreviewed", 0) + 1
        print(f"\nCalendar ({len(cal_rows)} rows): " + ", ".join(f"{k}={v}" for k, v in sorted(by_v.items())))
        scheduled = [r for r in cal_rows if r.get("verdict") == "scheduled"]
        if scheduled:
            print("  Scheduled events (next 10):")
            for r in scheduled[:10]:
                d = (r.get("event_date") or "")[:10]
                print(f"    {d}  tier{r.get('revenue_tier','?')}  {r.get('event_name','?')}")
    except Exception as e:
        print(f"\nCalendar: unreachable ({e})")

    # ContentCalendar (the daily plan)
    try:
        from content_calendar_sync import list_plan
        plan_rows = list_plan()
        by_status: dict[str, int] = {}
        for r in plan_rows:
            by_status[r.get("status") or "draft"] = by_status.get(r.get("status") or "draft", 0) + 1
        print(f"\nContentCalendar ({len(plan_rows)} rows): "
              + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
        planned = [r for r in plan_rows if r.get("status") == "planned"]
        if planned:
            print("  Planned (next 10):")
            for r in planned[:10]:
                d    = (r.get("target_date") or "")[:10]
                slot = (r.get("slot") or "?")[:5]
                print(f"    {d}  {slot:5}  {r.get('friend','?'):12}  p{r.get('pillar','?')}  "
                      f"{r.get('mode','?')}")
    except Exception as e:
        print(f"\nContentCalendar: unreachable ({e})")

    # Briefs (slot-aware: story vs reel split)
    try:
        from briefs_sync import list_briefs
        brief_rows = list_briefs()
        by_v: dict[str, int] = {}
        by_slot: dict[str, int] = {}
        for r in brief_rows:
            v = r.get("verdict") or "unreviewed"
            s = r.get("slot") or "?"
            by_v[v] = by_v.get(v, 0) + 1
            by_slot[s] = by_slot.get(s, 0) + 1
        print(f"\nBriefs ({len(brief_rows)} rows): "
              + ", ".join(f"{k}={v}" for k, v in sorted(by_v.items())))
        if by_slot:
            print(f"  by slot: " + ", ".join(f"{k}={v}" for k, v in sorted(by_slot.items())))
        pending = [r for r in brief_rows if r.get("verdict") not in ("good", "reject")]
        if pending:
            print("  Pending review (next 10):")
            for r in pending[:10]:
                td   = (r.get("target_date") or "")[:10]
                slot = (r.get("slot") or "?")[:5]
                print(f"    {td}  {slot:5}  {r.get('friend','?'):12}  p{r.get('pillar','?')}  "
                      f"verdict={r.get('verdict','unreviewed')}")
    except Exception as e:
        print(f"\nBriefs: unreachable ({e})")

    # Scripts
    try:
        from airtable_sync import list_scripts
        script_rows = list_scripts(limit=200)
        print(f"\nScripts ({len(script_rows)} rows in archive)")
    except Exception as e:
        print(f"\nScripts: unreachable ({e})")

    print()
    print("Next actions:")
    print("  ./.venv/bin/python run.py --stage calendar --days 90                     # sync calendar events")
    print("  ./.venv/bin/python run.py --stage plan --plan-start YYYY-MM-DD --plan-days 30")
    print("  ./.venv/bin/python run.py --stage brief --target-date YYYY-MM-DD --slot both")
    print("  ./.venv/bin/python run.py --stage write --target-date YYYY-MM-DD --slot story")
    print("  ./.venv/bin/python run.py --stage play                                   # process all rows ticked ready_to_write")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE PLAY — one-click brief+write for all rows the user ticked ready_to_write
# ═══════════════════════════════════════════════════════════════════════════════

def stage_play(args: argparse.Namespace) -> int:
    """
    Pick up every ContentCalendar row where the user has ticked ready_to_write,
    validate the row's required fields, then run brief + write back-to-back
    for it. The user's tick IS the approval — the Briefs verdict gate is
    bypassed (--force) for this flow.

    Behaviour per row:
      - status MUST be 'planned'
      - hook_choice / pillar_choice / story_seed_choice MUST all be set
      - if any of those are missing, the row is REFUSED with a clear message
        and ready_to_write is left ticked (so the user can fix and re-run)
      - on success: the row's ready_to_write checkbox is UNTICKED (one-shot)

    The visual `validation_status` formula field tells the user IN AIRTABLE
    what's missing before they tick the box. This stage is the hard gate
    that backs that visual.
    """
    print("=" * 60)
    print("STAGE: PLAY  (process all rows with ready_to_write=true)")
    print("=" * 60)

    try:
        from content_calendar_sync import _table
    except Exception as e:
        print(f"[play] ContentCalendar unreachable: {e}")
        return 1

    tbl = _table()
    all_rows = tbl.all(formula="{ready_to_write}=TRUE()", sort=["target_date", "slot"])
    if not all_rows:
        print("  No rows with ready_to_write=true. Tick a row in Airtable, then re-run.")
        return 0

    print(f"  found {len(all_rows)} ticked row(s)\n")

    ok_count   = 0
    fail_count = 0
    refused: list[tuple[str, str]] = []

    for rec in all_rows:
        f       = rec["fields"]
        plan_id = f.get("plan_id", "(unknown)")
        td      = f.get("target_date", "")
        slot    = f.get("slot", "")
        print(f"─── {plan_id} ───")

        # Hard validation — same rules as the visual formula field
        missing: list[str] = []
        if f.get("status") != "planned":
            missing.append(f"status≠planned (is '{f.get('status')}')")
        if not f.get("hook_choice"):
            missing.append("hook_choice")
        if not f.get("pillar_choice"):
            missing.append("pillar_choice")
        if not f.get("story_seed_choice"):
            missing.append("story_seed_choice")
        if not f.get("sensory_hook_choice"):
            missing.append("sensory_hook_choice")
        if not (td and slot):
            missing.append("target_date or slot")

        if missing:
            msg = f"REFUSED — missing: {', '.join(missing)}"
            print(f"  {msg}")
            print(f"  (ready_to_write left ticked — fix in Airtable and re-run)")
            refused.append((plan_id, msg))
            fail_count += 1
            continue

        # Build a brief-stage args namespace for this row
        brief_args = argparse.Namespace(
            target_date  = td,
            slot         = slot,
            force        = True,            # the tick IS the approval
            friend       = None,
            pillar       = None,
            brief_id     = None,
        )
        rc = stage_brief(brief_args)
        if rc != 0:
            print(f"  brief stage failed (rc={rc}) — leaving ready_to_write ticked")
            fail_count += 1
            continue

        # Build a write-stage args namespace for the same (target_date, slot).
        # --force bypasses the brief verdict gate; the user's tick is the approval.
        write_args = argparse.Namespace(
            target_date    = td,
            slot           = slot,
            brief_id       = None,
            force          = True,
            no_airtable    = False,
            no_continuity  = False,
            test           = False,
            day            = None,
            clip_length    = 6,
            _brief_record_id = None,
        )
        rc = stage_write(write_args)
        if rc != 0:
            print(f"  write stage failed (rc={rc}) — leaving ready_to_write ticked")
            fail_count += 1
            continue

        # Success — untick ready_to_write so this row doesn't fire again
        try:
            tbl.update(rec["id"], {"ready_to_write": False})
            print(f"  ✓ unticked ready_to_write")
        except Exception as e:
            print(f"  [warn] could not untick ready_to_write: {e}")
        ok_count += 1

    # Final summary
    print()
    print("=" * 60)
    print(f"PLAY SUMMARY  ok={ok_count}  failed={fail_count}")
    print("=" * 60)
    if refused:
        print("\nRefused rows (fix in Airtable, re-tick ready_to_write, re-run):")
        for plan_id, msg in refused:
            print(f"  {plan_id}: {msg}")

    return 0 if fail_count == 0 else 2


# ═══════════════════════════════════════════════════════════════════════════════
# 7-SKILL PIPELINE STAGES — Research, Package, Repurpose, Distill
# ═══════════════════════════════════════════════════════════════════════════════

def _stage_research(args: argparse.Namespace) -> int:
    """Phase 1 — Skills 1-3: Source Mining → Analysis → Competitive Ideation."""
    print("=" * 60)
    print("STAGE: RESEARCH  (Skills 1-3)")
    print("=" * 60)

    # Skill 1: Source Mining
    print("\n── Skill 1: Source Mining ──")
    try:
        from source_mining import mine_all
        source_filter = getattr(args, "source", None)
        result = mine_all(source_filter=source_filter)
        print(f"  → {result['total']} signals collected")
    except Exception as e:
        print(f"  [research] source mining failed: {e}")
        return 1

    # Skill 2: Analysis Pipeline
    print("\n── Skill 2: Analysis Pipeline ──")
    try:
        from analysis import analyze_signals
        analysis = analyze_signals()
        themes = analysis.get("this_week_themes", [])
        angles = analysis.get("actionable_angles", [])
        print(f"  → {len(themes)} themes, {len(angles)} angles")
    except Exception as e:
        print(f"  [research] analysis failed: {e}")
        return 1

    # Skill 3: Competitive Ideation
    print("\n── Skill 3: Competitive Ideation ──")
    try:
        from competitive import generate_opportunities
        opps = generate_opportunities()
        print(f"  → {len(opps)} ranked opportunities")
    except Exception as e:
        print(f"  [research] competitive ideation failed: {e}")
        return 1

    print("\n" + "=" * 60)
    print("Research complete. Review opportunities in data/content_opportunities.json")
    print("Then run: ./.venv/bin/python run.py --stage plan --plan-days 30")
    return 0


def _stage_package(args: argparse.Namespace) -> int:
    """Skill 6: Generate titles + thumbnail concepts for scripts."""
    print("=" * 60)
    print("STAGE: PACKAGE  (Skill 6 — Titles & Thumbnails)")
    print("=" * 60)

    try:
        from packaging import package_job, package_all
    except ImportError as e:
        print(f"  [package] import failed: {e}")
        return 1

    if args.target_date:
        count = 0
        for dd in sorted(SCRIPTS_ROOT.glob("Day */scripts")):
            for jf in sorted(dd.glob("*.json")):
                job = json.loads(jf.read_text())
                if job.get("target_date") == args.target_date:
                    if package_job(jf):
                        count += 1
        print(f"\nGenerated {count} packaging docs for {args.target_date}")
    else:
        count = package_all()
        print(f"\nGenerated {count} packaging docs")
    return 0


def _stage_repurpose(args: argparse.Namespace) -> int:
    """Skill 7a: Transform scripts into blog posts, threads, social posts."""
    print("=" * 60)
    print("STAGE: REPURPOSE  (Skill 7a — Blog + Thread + Social)")
    print("=" * 60)

    try:
        from repurposer import repurpose_job, repurpose_all, repurpose_by_date
    except ImportError as e:
        print(f"  [repurpose] import failed: {e}")
        return 1

    if args.target_date:
        count = repurpose_by_date(args.target_date)
    else:
        count = repurpose_all()
    print(f"\nGenerated {count} derivative assets")
    return 0


def _stage_distill(args: argparse.Namespace) -> int:
    """Skill 7b: Distill reel scripts into platform-native short-form."""
    print("=" * 60)
    print("STAGE: DISTILL  (Skill 7b — Short-Form Distillation)")
    print("=" * 60)

    try:
        from distiller import distill_job, distill_all
    except ImportError as e:
        print(f"  [distill] import failed: {e}")
        return 1

    if args.target_date:
        count = 0
        for dd in sorted(SCRIPTS_ROOT.glob("Day */scripts")):
            for jf in sorted(dd.glob("*.json")):
                if jf.stem.endswith("_SHORT"):
                    continue
                job = json.loads(jf.read_text())
                if job.get("target_date") == args.target_date:
                    paths = distill_job(jf)
                    count += len(paths)
        print(f"\nGenerated {count} short-form assets for {args.target_date}")
    else:
        count = distill_all()
        print(f"\nGenerated {count} short-form assets")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO MODE — legacy bypass (testing only)
# ═══════════════════════════════════════════════════════════════════════════════

def stage_auto(args: argparse.Namespace) -> int:
    """
    Legacy end-to-end run. Bypasses ALL approval gates. For testing /
    smoke checks only — never use this for production output.
    """
    print("=" * 60)
    print("STAGE: AUTO  (bypassing all approval gates)")
    print("=" * 60)

    # 1. Trend scout (Apify)
    if not args.no_scout:
        try:
            from apify_scout import run as run_scout
            run_scout()
        except Exception as e:
            print(f"[run] trend scout failed: {e}")

    # 2. Gate
    import logical_gate
    from logical_gate import GateFailure
    target = _date.fromisoformat(args.target_date) if args.target_date else None
    try:
        gate = logical_gate.run_gate(args.format, args.pillar, args.friend, target)
    except GateFailure as e:
        print(f"[run] LOGICAL GATE FAILED: {e}")
        return 1

    print(f"  mode={gate.mode}  city={gate.city}  friend={gate.friend_id}  currency={gate.currency}")

    # 4. Strategy → brief
    import strategy
    try:
        brief = strategy.generate_brief(gate, args.format, args.pillar)
    except Exception as e:
        print(f"[run] strategy director failed: {e}")
        if "cannot resolve" in str(e):
            print("[run] This smoke path still needs live model access to generate the brief.")
            print("[run] Re-run with network access plus ANTHROPIC_API_KEY and at least one writer-model key.")
        return 1

    # 5+. Write the script
    return _write_from_brief(brief, gate.to_dict(), args)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(
        description="Bella Content Engine — staged orchestrator (Airtable verdict gates)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ./.venv/bin/python run.py                                    # status\n"
            "  ./.venv/bin/python run.py --stage calendar --days 90\n"
            "  ./.venv/bin/python run.py --stage plan --plan-start 2026-04-12 --plan-days 30\n"
            "  ./.venv/bin/python run.py --stage brief --target-date 2026-04-25 --slot both\n"
            "  ./.venv/bin/python run.py --stage write --target-date 2026-04-25 --slot story\n"
            "  ./.venv/bin/python run.py --stage play                       # process all rows ticked ready_to_write\n"
            "  ./.venv/bin/python run.py --stage write --brief-id rec123\n"
            "  ./.venv/bin/python run.py --auto --target-date 2026-04-25   # legacy bypass\n"
        ),
    )
    p.add_argument("--stage",
                   choices=["research", "calendar", "plan", "brief", "write", "play",
                            "package", "repurpose", "distill", "status"],
                   help="which stage to run (default: status)")
    p.add_argument("--auto", action="store_true",
                   help="legacy end-to-end run, bypasses ALL Airtable approval gates")
    p.add_argument("--status", action="store_true",
                   help="alias for --stage status")
    p.add_argument("--force", action="store_true",
                   help="bypass upstream verdict checks for this stage")

    p.add_argument("--target-date",
                   help="ISO date the script will publish "
                        "(used by brief, write, auto stages)")
    p.add_argument("--brief-id",
                   help="Airtable record id of the approved brief (--stage write)")
    p.add_argument("--slot",
                   choices=["story", "reel", "both"],
                   help="--stage brief: which slot(s) to generate (story | reel | both); "
                        "--stage write: which slot to look up by target_date")

    p.add_argument("--format", choices=["reel", "story"], default="reel")
    p.add_argument("--pillar", type=int, choices=[1, 2, 3, 4, 5])
    p.add_argument("--friend",  help="force friend id")

    p.add_argument("--days", type=int, default=90,
                   help="--stage calendar: days ahead to sync (default 90)")
    p.add_argument("--tier", type=int, choices=[1, 2, 3], default=1,
                   help="--stage calendar: include events with revenue_tier ≤ this (default 1)")
    p.add_argument("--plan-start",
                   help="--stage plan: ISO start date for the content calendar (default today)")
    p.add_argument("--plan-days", type=int, default=14,
                   help="--stage plan: days to plan (default 14 → 28 rows)")

    p.add_argument("--no-scout", action="store_true",
                   help="--stage auto: skip Apify trend scout")
    p.add_argument("--no-airtable", action="store_true",
                   help="--stage write: skip the Scripts table push")
    p.add_argument("--no-continuity", action="store_true",
                   help="--stage write: skip the Continuity Director post-approval update")

    p.add_argument("--test", action="store_true",
                   help="--stage write: write to Scripts/Test instead of Scripts/Day N")
    p.add_argument("--day", type=int,
                   help="--stage write: explicit Scripts/Day N folder")
    p.add_argument("--clip-length", type=int, default=6,
                   help="shot director clip length in seconds (5-10, default 6)")

    args = p.parse_args()

    # Resolve stage
    if args.auto:
        code = stage_auto(args)
    elif args.status or args.stage == "status" or not args.stage:
        code = stage_status(args)
    elif args.stage == "calendar":
        code = stage_calendar(args)
    elif args.stage == "plan":
        code = stage_plan(args)
    elif args.stage == "brief":
        code = stage_brief(args)
    elif args.stage == "write":
        # Stash the brief record id for the post-write mark
        args._brief_record_id = args.brief_id
        code = stage_write(args)
    elif args.stage == "play":
        code = stage_play(args)
    elif args.stage == "research":
        code = _stage_research(args)
    elif args.stage == "package":
        code = _stage_package(args)
    elif args.stage == "repurpose":
        code = _stage_repurpose(args)
    elif args.stage == "distill":
        code = _stage_distill(args)
    else:
        code = stage_status(args)

    sys.exit(code)


if __name__ == "__main__":
    main()
