"""
video_prompts.py — generate engine-specific video prompt documents from a
Bella job file's shot_list.

Produces 3 text files per script in the same directory:
  {episode_id}_HEYGEN.txt     — avatar/talking-head clips
  {episode_id}_SEEDANCE.txt   — Seedance 2.0 text-to-video prompts
  {episode_id}_KLING.txt      — Kling 3.0 text-to-video prompts

Each file is self-contained with:
  - Full prompt text for every clip
  - Camera movement / shot type / lens details
  - Scene transition instructions between clips
  - Step-by-step manual actions for the operator
  - Reference image paths for character consistency
  - Stitching/audio alignment instructions

No LLM calls — pure formatting from the shot_list data.

Usage:
    python3 video_prompts.py path/to/job.json              # one file
    python3 video_prompts.py --all                         # all Scripts/Day N/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BASE_DIR    = Path(__file__).parent
SCRIPTS_DIR = BASE_DIR.parent / "Creatives" / "Daily assets"


# ─── Helpers ────────────────────────────────────────────────────────────────

def _neg(shot: dict) -> str:
    items = shot.get("negative") or ["text overlays", "logos", "modern signage", "extra people"]
    return ", ".join(items)


def _ref_images(shot: dict) -> str:
    refs = shot.get("reference_images") or []
    if not refs:
        return "    (none — use text-to-video mode)"
    return "\n".join(f"    → {r}" for r in refs)


def _audio_text(shot: dict) -> str:
    audio = shot.get("audio_slice") or {}
    return audio.get("text", "(no audio text)")


def _avatar_manual_action(subject: str, friend_name: str) -> str:
    if subject == "bella":
        return "Select Bella avatar"
    elif subject == "friend":
        return f"Upload {friend_name} reference as Photo Avatar"
    elif subject == "ciao":
        return "Upload Ciao mascot image"
    return "Set as background-only scene (no avatar)"


def _avatar_label(subject: str, friend_name: str) -> str:
    if subject == "bella":
        return "Bella avatar"
    elif subject == "friend":
        return f"{friend_name} photo avatar"
    elif subject == "ciao":
        return "Ciao mascot"
    return "No avatar (background only)"


def _audio_timing(shot: dict) -> str:
    audio = shot.get("audio_slice") or {}
    start = audio.get("start_ms", 0)
    end = audio.get("end_ms", 0)
    return f"{start}ms → {end}ms ({(end - start) / 1000:.1f}s)"


def _transition_instruction(t_type: str, engine: str) -> str:
    """Human-readable instruction for how to implement a transition type in each engine."""
    t = (t_type or "cut").lower()
    if "match cut" in t:
        obj = t.replace("match cut on", "").replace("match cut", "").strip() or "subject"
        return (
            f"MATCH CUT on {obj} — end this clip with {obj} centered in frame, "
            f"start the next clip with {obj} in the same position. "
            f"{'In HeyGen: export both clips and align in your editor.' if engine == 'heygen' else ''}"
            f"{'In Seedance: use the last frame as reference image for the next clip.' if engine == 'seedance' else ''}"
            f"{'In Kling: screenshot the last frame, upload as start image for next clip.' if engine == 'kling' else ''}"
        )
    elif "cross-fade" in t or "crossfade" in t:
        return "CROSS-FADE — add a 0.5s dissolve transition between this clip and the next in your editor."
    elif "hard cut" in t:
        return "HARD CUT — no transition, immediate cut. Stitch clips back-to-back with zero overlap."
    else:
        return "CUT — clean cut. Stitch clips sequentially with no transition effect."


# ─── HeyGen ─────────────────────────────────────────────────────────────────

def _heygen_doc(job: dict) -> str:
    sl = job.get("shot_list") or {}
    shots = sl.get("shots") or []
    brief = job.get("brief") or {}
    avatars = brief.get("avatars") or {}
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║           HEYGEN — VIDEO PRODUCTION PROMPTS             ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"Episode    : {job.get('episode_id')}",
        f"Friend     : {brief.get('friend')} ({brief.get('city')})",
        f"Format     : {brief.get('format')} ({'~30s story' if brief.get('format') == 'story' else '30-60s reel'})",
        f"Duration   : {brief.get('target_duration_seconds')}s",
        f"Tone       : {brief.get('tone')}",
        f"Total clips: {sl.get('clip_count', len(shots))}",
        f"Score      : {job.get('score')}/10",
        "",
        "",
        "STEP-BY-STEP WORKFLOW",
        "=" * 60,
        "1. Open HeyGen → Create New Video → choose 9:16 (vertical) aspect ratio",
        "2. For each clip below:",
        "   a. Add a new scene in the timeline",
        "   b. Select the avatar (see AVATAR ASSIGNMENTS below)",
        "   c. Paste the SPOKEN TEXT into the script field",
        "   d. Set the background (upload or generate from SCENE description)",
        "   e. Set the avatar position and gesture style per the CAMERA notes",
        "3. After all clips are added:",
        "   a. Set transitions between scenes (see per-clip TRANSITION notes)",
        "   b. Upload the SSML audio (if using external TTS instead of HeyGen's)",
        "   c. Preview, adjust timing, export",
        "",
        "",
        "AVATAR ASSIGNMENTS",
        "-" * 60,
    ]
    for label, path in avatars.items():
        lines.append(f"  {label}: {path}")
    lines.extend([
        "",
        "  RULE: When subject=bella → use the Bella avatar",
        "  RULE: When subject=friend → upload the friend's reference image as a Photo Avatar",
        "  RULE: When subject=ciao → use the Ciao mascot reference image",
        "  RULE: When subject=scene → no avatar needed, use a background-only scene",
        "",
        "",
        "FULL SSML SCRIPT (paste if using HeyGen's built-in TTS)",
        "-" * 60,
        job.get("video_script_ssml") or job.get("video_script", "(no script)"),
        "",
        "",
        "WORLD / SETTING (consistency reference for all backgrounds)",
        "-" * 60,
        sl.get("world_description", "(no world description)"),
        "",
        "",
        "═" * 60,
        "PER-CLIP BREAKDOWN",
        "═" * 60,
        "",
    ])

    for i, shot in enumerate(shots):
        sid = shot.get("shot_id", "?")
        dur = shot.get("duration_seconds", 6)
        subject = shot.get("subject", "?")
        is_last = (i == len(shots) - 1)

        lines.extend([
            f"┌─ CLIP {sid} ─ {dur}s ─ subject: {subject} ─────────────────────",
            f"│",
            f"│  SCENE         : {shot.get('scene', '(not specified)')}",
            f"│  ACTION        : {shot.get('action', '(not specified)')}",
            f"│  CAMERA        : {shot.get('camera', '(not specified)')}",
            f"│  LIGHTING      : {shot.get('lighting', '(not specified)')}",
            f"│  MOOD          : {shot.get('mood', '(not specified)')}",
            f"│",
            f"│  SPOKEN TEXT (paste into HeyGen script for this scene):",
            f"│  \"{_audio_text(shot)}\"",
            f"│",
            f"│  AUDIO TIMING  : {_audio_timing(shot)}",
            f"│",
            f"│  AVATAR        : {_avatar_label(subject, brief.get('friend', '?'))}",
            f"│  REFERENCE IMG :",
            _ref_images(shot).replace("\n", "\n│  "),
            f"│",
            f"│  BACKGROUND    : Generate or find a stock image matching the SCENE description above.",
            f"│                  The world_description at the top of this document is the consistency anchor.",
            f"│",
        ])

        # Transition instructions
        if not is_last:
            t_out = shot.get("transition_out", "cut")
            next_t_in = shots[i + 1].get("transition_in", "cut") if i + 1 < len(shots) else "cut"
            lines.extend([
                f"│  TRANSITION OUT: {t_out}",
                f"│  → {_transition_instruction(t_out, 'heygen')}",
                f"│",
            ])
        lines.extend([
            f"│  ⚠ MANUAL ACTIONS:",
            f"│    1. Add new scene in HeyGen timeline",
            f"│    2. {_avatar_manual_action(subject, brief.get('friend', '?'))}",
            f"│    3. Paste the SPOKEN TEXT above into the script field",
            f"│    4. Upload/generate the background from the SCENE description",
            f"│    5. Set scene duration to {dur}s",
            f"│    6. {'Set transition to next scene' if not is_last else 'This is the final scene — no outgoing transition'}",
            f"└────────────────────────────────────────────────────────",
            "",
            "",
        ])

    lines.extend([
        "POST-PRODUCTION CHECKLIST",
        "=" * 60,
        "□ Preview the full video end-to-end before exporting",
        "□ Check that avatar lip-sync aligns with the spoken text",
        "□ Verify scene transitions match the TRANSITION notes above",
        "□ Check total duration matches the target above",
        "□ Export at 1080x1920 (9:16) for Instagram Reels/Stories",
        "□ Overlay the Instagram caption from the .txt companion file",
        "",
    ])

    return "\n".join(lines)


# ─── Seedance 2.0 ──────────────────────────────────────────────────────────

def _seedance_doc(job: dict) -> str:
    sl = job.get("shot_list") or {}
    shots = sl.get("shots") or []
    brief = job.get("brief") or {}
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║        SEEDANCE 2.0 — VIDEO PRODUCTION PROMPTS          ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"Episode    : {job.get('episode_id')}",
        f"Friend     : {brief.get('friend')} ({brief.get('city')})",
        f"Format     : {brief.get('format')} ({'~30s story' if brief.get('format') == 'story' else '30-60s reel'})",
        f"Duration   : {brief.get('target_duration_seconds')}s",
        f"Tone       : {brief.get('tone')}",
        f"Total clips: {sl.get('clip_count', len(shots))}",
        f"Score      : {job.get('score')}/10",
        "",
        "",
        "STEP-BY-STEP WORKFLOW",
        "=" * 60,
        "1. Open Seedance 2.0 → Text to Video",
        "2. Set aspect ratio: 9:16 (portrait / vertical)",
        "3. For EACH clip below:",
        "   a. Copy the PROMPT text (inside the triple quotes)",
        "   b. Paste it into the Seedance prompt field",
        "   c. Copy the NEGATIVE PROMPT and paste into the negative prompt field",
        "   d. If REFERENCE IMAGES are listed → switch to Image-to-Video mode",
        "      and upload the reference image as the 'start frame'",
        "   e. Set duration to the value shown (5s or 10s)",
        "   f. Generate the clip → download the .mp4",
        "   g. Name the file: clip_{shot_id}.mp4 (e.g., clip_01.mp4)",
        "4. After all clips are generated:",
        "   a. Import all clips into your editor in shot_id order",
        "   b. Apply transitions as noted per clip",
        "   c. Import the SSML-generated TTS audio track",
        "   d. Align each clip's start to its AUDIO TIMING below",
        "   e. Export at 1080x1920 (9:16)",
        "",
        "",
        "WORLD DESCRIPTION (repeat in every prompt for visual consistency)",
        "-" * 60,
        sl.get("world_description", "(no world description)"),
        "",
        "GLOBAL CONTINUITY (keep consistent across ALL clips)",
        "-" * 60,
        f"  Wardrobe     : {(sl.get('continuity') or {}).get('wardrobe', '(not specified)')}",
        f"  Lighting arc : {(sl.get('continuity') or {}).get('lighting_arc', '(not specified)')}",
        f"  Props        : {', '.join((sl.get('continuity') or {}).get('props', [])) or '(none)'}",
        "",
        "  ⚠ IMPORTANT: If a generated clip drifts from the world_description",
        "    (different time of day, wrong lighting, extra people), RE-ROLL it.",
        "    Continuity drift is the #1 failure mode for multi-clip stitching.",
        "",
        "",
        "═" * 60,
        "PER-CLIP PROMPTS",
        "═" * 60,
        "",
    ]

    for i, shot in enumerate(shots):
        sid = shot.get("shot_id", "?")
        dur = shot.get("duration_seconds", 6)
        prompt = shot.get("prompt_universal", "(no prompt)")
        neg = _neg(shot)
        refs = shot.get("reference_images") or []
        is_last = (i == len(shots) - 1)

        mode_note = "IMAGE-TO-VIDEO (upload reference as start frame)" if refs else "TEXT-TO-VIDEO"

        lines.extend([
            f"┌─ CLIP {sid} ─ {dur}s ─ {mode_note} ──────────────────",
            f"│",
            f"│  PROMPT (copy everything between the triple quotes):",
            f"│  ┌──────────────────────────────────────────────────",
            f"│  │",
        ])
        for pline in prompt.split(". "):
            lines.append(f"│  │  {pline.strip()}.")
        lines.extend([
            f"│  │",
            f"│  └──────────────────────────────────────────────────",
            f"│",
            f"│  NEGATIVE PROMPT:",
            f"│  \"{neg}\"",
            f"│",
            f"│  CAMERA MOVEMENT : {shot.get('camera', '(not specified)')}",
            f"│  LIGHTING        : {shot.get('lighting', '(not specified)')}",
            f"│  MOOD / FEEL     : {shot.get('mood', '(not specified)')}",
            f"│  ACTION / MOTION : {shot.get('action', '(not specified)')}",
            f"│  SCENE SETTING   : {shot.get('scene', '(not specified)')}",
            f"│",
            f"│  AUDIO TIMING    : {_audio_timing(shot)}",
            f"│  SPOKEN TEXT     : \"{_audio_text(shot)[:120]}{'...' if len(_audio_text(shot)) > 120 else ''}\"",
            f"│",
            f"│  REFERENCE IMAGES:",
            _ref_images(shot).replace("\n", "\n│  "),
            f"│",
            f"│  CONTINUITY (this clip):",
            f"│    Wardrobe    : {(shot.get('continuity') or {}).get('wardrobe', '(not specified)')}",
            f"│    Props carry : {', '.join((shot.get('continuity') or {}).get('props_carry', [])) or '(none)'}",
            f"│",
        ])

        if not is_last:
            t_out = shot.get("transition_out", "cut")
            lines.extend([
                f"│  TRANSITION → next clip: {t_out}",
                f"│  → {_transition_instruction(t_out, 'seedance')}",
                f"│",
            ])

        lines.extend([
            f"│  ⚠ MANUAL ACTIONS:",
            f"│    1. {'Switch to Image-to-Video mode, upload: ' + refs[0] if refs else 'Use Text-to-Video mode (no reference image)'}",
            f"│    2. Paste the PROMPT above into the prompt field",
            f"│    3. Paste the NEGATIVE PROMPT into the negative field",
            f"│    4. Set duration: {dur}s",
            f"│    5. Set aspect: 9:16",
            f"│    6. Generate → review → download as clip_{sid}.mp4",
            f"│    7. If the clip drifts from the world description → re-roll",
            f"└────────────────────────────────────────────────────────",
            "",
            "",
        ])

    lines.extend([
        "POST-PRODUCTION / STITCHING",
        "=" * 60,
        f"  Total target duration: {sl.get('total_duration_seconds', '?')}s",
        "",
        "  STITCHING ORDER:",
    ])
    for shot in shots:
        sid = shot.get("shot_id", "?")
        dur = shot.get("duration_seconds", 6)
        lines.append(f"    {sid}. clip_{sid}.mp4 ({dur}s) — audio: {_audio_timing(shot)}")
    lines.extend([
        "",
        "  AUDIO ALIGNMENT:",
        "    1. Generate the TTS audio from the SSML script (ElevenLabs or similar)",
        "    2. Import the audio track into your editor",
        "    3. Place each clip at its AUDIO TIMING start position",
        "    4. The audio_slice.end_ms of clip N = audio_slice.start_ms of clip N+1",
        "    5. Check for drift: off-by-one frame is OK, off-by-100ms is not",
        "",
        "  FINAL CHECKLIST:",
        "  □ All clips stitched in shot_id order",
        "  □ Audio track aligned to clip start times",
        "  □ No visual continuity drift between clips",
        "  □ Total duration within ±2s of target",
        "  □ Export at 1080x1920 (9:16) for Instagram",
        "",
    ])

    return "\n".join(lines)


# ─── Kling 3.0 ──────────────────────────────────────────────────────────────

def _kling_doc(job: dict) -> str:
    sl = job.get("shot_list") or {}
    shots = sl.get("shots") or []
    brief = job.get("brief") or {}
    lines = [
        "╔═══════════════════════════════════════════════════════════╗",
        "║          KLING 3.0 — VIDEO PRODUCTION PROMPTS            ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"Episode    : {job.get('episode_id')}",
        f"Friend     : {brief.get('friend')} ({brief.get('city')})",
        f"Format     : {brief.get('format')} ({'~30s story' if brief.get('format') == 'story' else '30-60s reel'})",
        f"Duration   : {brief.get('target_duration_seconds')}s",
        f"Tone       : {brief.get('tone')}",
        f"Total clips: {sl.get('clip_count', len(shots))}",
        f"Score      : {job.get('score')}/10",
        "",
        "",
        "STEP-BY-STEP WORKFLOW",
        "=" * 60,
        "1. Open Kling 3.0 → AI Video → choose generation mode",
        "2. Global settings for ALL clips:",
        "   - Mode       : Professional (better character consistency)",
        "   - Aspect     : 9:16 (portrait)",
        "   - Camera ctrl: ON (use per-clip camera instructions)",
        "   - Creativity : Medium (balance between prompt adherence and quality)",
        "3. For EACH clip below:",
        "   a. Choose Text-to-Video OR Image-to-Video (see per-clip notes)",
        "   b. If Image-to-Video: upload the reference image as START FRAME",
        "   c. Paste the PROMPT text into the prompt field",
        "   d. Paste the NEGATIVE PROMPT into the negative field",
        "   e. Set the CAMERA MOVEMENT using Kling's camera control",
        "   f. Set duration: 5s or 10s (see per-clip duration recommendation)",
        "   g. Generate → preview → if good, download as clip_{shot_id}.mp4",
        "   h. If bad (wrong character, drift, artifacts) → re-roll with same seed",
        "4. After all clips are generated:",
        "   a. Import clips into your editor in shot_id order",
        "   b. Apply transitions (see per-clip notes)",
        "   c. Import TTS audio, align per AUDIO TIMING",
        "   d. Export at 1080x1920 (9:16)",
        "",
        "",
        "WORLD DESCRIPTION (paste as scene context for every clip)",
        "-" * 60,
        sl.get("world_description", "(no world description)"),
        "",
        "GLOBAL CONTINUITY",
        "-" * 60,
        f"  Wardrobe     : {(sl.get('continuity') or {}).get('wardrobe', '(not specified)')}",
        f"  Lighting arc : {(sl.get('continuity') or {}).get('lighting_arc', '(not specified)')}",
        f"  Props        : {', '.join((sl.get('continuity') or {}).get('props', [])) or '(none)'}",
        "",
        "  ⚠ CONTINUITY IS KING: if a clip doesn't match the world_description,",
        "    re-roll it. Use the same seed number across clips for consistency.",
        "    Upload the previous clip's last frame as the next clip's start frame",
        "    to maintain visual flow.",
        "",
        "",
        "═" * 60,
        "PER-CLIP PROMPTS",
        "═" * 60,
        "",
    ]

    for i, shot in enumerate(shots):
        sid = shot.get("shot_id", "?")
        dur = shot.get("duration_seconds", 6)
        prompt = shot.get("prompt_universal", "(no prompt)")
        neg = _neg(shot)
        refs = shot.get("reference_images") or []
        camera = shot.get("camera", "(not specified)")
        is_last = (i == len(shots) - 1)

        kling_dur = "5s" if dur <= 7 else "10s"
        mode_note = "IMAGE-TO-VIDEO (upload start frame)" if refs else "TEXT-TO-VIDEO"

        # Parse camera movement for Kling's camera control
        cam_lower = camera.lower()
        kling_camera_notes = []
        if "push-in" in cam_lower or "dolly in" in cam_lower or "push in" in cam_lower:
            kling_camera_notes.append("Camera control → ZOOM IN (slow)")
        elif "pull-back" in cam_lower or "dolly out" in cam_lower or "pull back" in cam_lower:
            kling_camera_notes.append("Camera control → ZOOM OUT (slow)")
        if "pan" in cam_lower:
            direction = "LEFT" if "left" in cam_lower else "RIGHT" if "right" in cam_lower else "LEFT-TO-RIGHT"
            kling_camera_notes.append(f"Camera control → PAN {direction}")
        if "tilt" in cam_lower:
            direction = "UP" if "up" in cam_lower else "DOWN"
            kling_camera_notes.append(f"Camera control → TILT {direction}")
        if "track" in cam_lower or "follow" in cam_lower:
            kling_camera_notes.append("Camera control → TRACKING SHOT (follow subject)")
        if "static" in cam_lower or "locked" in cam_lower:
            kling_camera_notes.append("Camera control → STATIC (no movement)")
        if "handheld" in cam_lower:
            kling_camera_notes.append("Camera control → slight HANDHELD shake (set jitter low)")
        if not kling_camera_notes:
            kling_camera_notes.append(f"Camera control → match this description: {camera}")

        lines.extend([
            f"┌─ CLIP {sid} ─ {kling_dur} ─ {mode_note} ──────────────────",
            f"│",
            f"│  PROMPT (copy everything between the triple quotes):",
            f"│  ┌──────────────────────────────────────────────────",
            f"│  │",
        ])
        for pline in prompt.split(". "):
            lines.append(f"│  │  {pline.strip()}.")
        lines.extend([
            f"│  │",
            f"│  └──────────────────────────────────────────────────",
            f"│",
            f"│  NEGATIVE PROMPT:",
            f"│  \"{neg}\"",
            f"│",
            f"│  KLING CAMERA CONTROL:",
        ])
        for cn in kling_camera_notes:
            lines.append(f"│    → {cn}")
        lines.extend([
            f"│  Shot type     : {camera}",
            f"│",
            f"│  SCENE SETTING : {shot.get('scene', '(not specified)')}",
            f"│  ACTION/MOTION : {shot.get('action', '(not specified)')}",
            f"│  LIGHTING      : {shot.get('lighting', '(not specified)')}",
            f"│  MOOD / FEEL   : {shot.get('mood', '(not specified)')}",
            f"│",
            f"│  AUDIO TIMING  : {_audio_timing(shot)}",
            f"│  SPOKEN TEXT   : \"{_audio_text(shot)[:120]}{'...' if len(_audio_text(shot)) > 120 else ''}\"",
            f"│",
            f"│  REFERENCE IMAGES (upload as START FRAME for Image-to-Video):",
            _ref_images(shot).replace("\n", "\n│  "),
            f"│",
            f"│  CONTINUITY (this clip):",
            f"│    Wardrobe    : {(shot.get('continuity') or {}).get('wardrobe', '(not specified)')}",
            f"│    Props carry : {', '.join((shot.get('continuity') or {}).get('props_carry', [])) or '(none)'}",
            f"│",
        ])

        if not is_last:
            t_out = shot.get("transition_out", "cut")
            lines.extend([
                f"│  TRANSITION → next clip: {t_out}",
                f"│  → {_transition_instruction(t_out, 'kling')}",
                f"│",
            ])

        lines.extend([
            f"│  ⚠ MANUAL ACTIONS:",
            f"│    1. {'Upload this reference image as START FRAME: ' + refs[0] if refs else 'Use Text-to-Video mode (no start frame needed)'}",
            f"│    2. Paste the PROMPT above into Kling's prompt field",
            f"│    3. Paste the NEGATIVE PROMPT into the negative field",
            f"│    4. Set the CAMERA CONTROL as noted above",
            f"│    5. Set duration: {kling_dur}",
            f"│    6. Set mode: Professional, aspect: 9:16",
            f"│    7. Generate → preview → download as clip_{sid}.mp4",
            f"│    8. If the clip drifts from the world description → re-roll",
            f"│    9. {'Screenshot the LAST FRAME of this clip for the next clip start frame (continuity)' if not is_last else 'This is the final clip — no outgoing continuity needed'}",
            f"└────────────────────────────────────────────────────────",
            "",
            "",
        ])

    lines.extend([
        "POST-PRODUCTION / STITCHING",
        "=" * 60,
        f"  Total target duration: {sl.get('total_duration_seconds', '?')}s",
        "",
        "  STITCHING ORDER:",
    ])
    for shot in shots:
        sid = shot.get("shot_id", "?")
        dur = shot.get("duration_seconds", 6)
        lines.append(f"    {sid}. clip_{sid}.mp4 ({dur}s) — audio: {_audio_timing(shot)}")
    lines.extend([
        "",
        "  AUDIO ALIGNMENT:",
        "    1. Generate TTS audio from the SSML script (ElevenLabs)",
        "    2. Import audio into editor, place each clip at its AUDIO TIMING start",
        "    3. audio_slice.end_ms of clip N = audio_slice.start_ms of clip N+1 (no gaps)",
        "",
        "  CONTINUITY TIPS FOR KLING:",
        "    - Use the same SEED number across all clips for consistency",
        "    - For character clips: upload the friend reference as start frame",
        "    - For scene clips: screenshot the last frame of the previous clip",
        "      and upload as start frame for the next — this chains visual flow",
        "    - If a clip drifts (wrong lighting, extra people, wrong wardrobe),",
        "      re-generate with the same prompt. Do not proceed with a drifted clip.",
        "",
        "  FINAL CHECKLIST:",
        "  □ All clips stitched in shot_id order",
        "  □ Camera movements match the CAMERA CONTROL notes per clip",
        "  □ Audio track aligned to clip start times",
        "  □ No visual continuity drift between clips",
        "  □ Total duration within ±2s of target",
        "  □ Export at 1080x1920 (9:16) for Instagram",
        "",
    ])

    return "\n".join(lines)


# ─── Generator ──────────────────────────────────────────────────────────────

ENGINES = {
    "HEYGEN":   _heygen_doc,
    "SEEDANCE": _seedance_doc,
    "KLING":    _kling_doc,
}


def generate_prompt_docs(job_path: Path) -> list[Path]:
    """
    Read a job JSON file and write 3 engine-specific prompt documents
    alongside it. Returns the list of paths written.
    """
    job = json.loads(job_path.read_text())
    sl = job.get("shot_list") or {}
    shots = sl.get("shots") or []

    if not shots:
        print(f"  [video-prompts] {job_path.name}: no shots in shot_list — skipping")
        return []

    ep = job.get("episode_id", job_path.stem)
    out_dir = job_path.parent
    written: list[Path] = []

    for engine_name, render_fn in ENGINES.items():
        txt = render_fn(job)
        out_path = out_dir / f"{ep}_{engine_name}.txt"
        out_path.write_text(txt)
        written.append(out_path)

    return written


def generate_all() -> int:
    """Walk all Scripts/Day N/ folders and generate prompt docs for every job."""
    count = 0
    for day_dir in sorted(SCRIPTS_DIR.glob("Day */scripts")):
        for jf in sorted(day_dir.glob("*.json")):
            paths = generate_prompt_docs(jf)
            for p in paths:
                print(f"  ✓ {p.relative_to(SCRIPTS_DIR)}")
                count += 1
    return count


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Generate HeyGen / Seedance 2.0 / Kling 3.0 video prompt docs from Bella job files"
    )
    p.add_argument("job_file", nargs="?", help="path to a single job JSON file")
    p.add_argument("--all", action="store_true",
                   help="process all Scripts/Day N/*.json files")
    args = p.parse_args()

    if args.all:
        n = generate_all()
        print(f"\nGenerated {n} prompt documents")
    elif args.job_file:
        paths = generate_prompt_docs(Path(args.job_file))
        if paths:
            for p_out in paths:
                print(f"  ✓ {p_out}")
        else:
            print("  No shots — nothing generated")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
