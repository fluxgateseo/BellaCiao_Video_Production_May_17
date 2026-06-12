"""kling_pack — author distinct per-shot frame prompts and write per-video folder text files.

Reads day N's KLING.md files (read-only), calls Claude Sonnet 4.6 once per episode,
writes PROMPT.txt + start_frame_description.txt + end_frame_description.txt into
each Reel NN (Day N)/ and Story NN (Day N)/ folder. Never touches PNGs. Never
mutates KLING.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT))

from pipeline_v3.image_prompt_builder import parse_kling_md, character_prompt  # noqa: E402
from anthropic import Anthropic  # noqa: E402

CONTENT_ROOT = _PKG_ROOT.parent
DAILY_ASSETS = CONTENT_ROOT / "Creatives" / "Daily assets"

# Whole-word forbidden tokens — schema validator rejects any prompt containing these
FORBIDDEN_TOKENS = ("cat", "cats", "kitten", "kittens", "feline")


def validate_llm_output(payload: dict, expected_indices: list[int]) -> None:
    """Raise ValueError if the LLM payload doesn't match the schema:
       - 'shots' is a list with one entry per expected_index, no extras
       - each entry has non-empty first_frame_prompt + last_frame_prompt
       - no whole-word FORBIDDEN_TOKENS appear in either prompt
    """
    shots = payload.get("shots")
    if not isinstance(shots, list):
        raise ValueError("payload missing 'shots' list")
    seen = {s.get("shot_index") for s in shots}
    expected = set(expected_indices)
    for idx in expected - seen:
        raise ValueError(f"shot_index {idx} missing from LLM output")
    for idx in seen - expected:
        raise ValueError(f"unexpected shot_index {idx} in LLM output")
    forbidden_re = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in FORBIDDEN_TOKENS) + r")\b",
        re.IGNORECASE,
    )
    for s in shots:
        for field in ("first_frame_prompt", "last_frame_prompt"):
            value = (s.get(field) or "").strip()
            if not value:
                raise ValueError(f"shot {s.get('shot_index')}: {field} is empty")
            m = forbidden_re.search(value)
            if m:
                raise ValueError(
                    f"shot {s.get('shot_index')}: {field} contains forbidden token {m.group(1)!r}"
                )


_KLING_FILE_RE = re.compile(r"^bella_[a-z_]+_p(\d+)_\d{8}_\d{4}\.KLING\.md$")


def discover_episodes(day: int) -> list[dict]:
    """Return episodes for Day N as a list of dicts:
       [{"kind": "story"|"reel", "kling_path": Path, "folders": [Path, ...]}, ...]
       'kind' = story when filename suffix is _p1_, reel when _p2_.
       'folders' are sorted by shot index.
    """
    day_root = DAILY_ASSETS / f"Day {day}"
    if not day_root.is_dir():
        return []
    full_scripts = day_root / "full scripts"
    out: list[dict] = []
    for kling_path in sorted(full_scripts.glob("*.KLING.md")) if full_scripts.is_dir() else []:
        m = _KLING_FILE_RE.match(kling_path.name)
        if not m:
            continue
        kind = "story" if m.group(1) == "1" else "reel" if m.group(1) == "2" else None
        if kind is None:
            continue
        prefix = "Story " if kind == "story" else "Reel "
        folders = sorted(
            [p for p in day_root.iterdir() if p.is_dir() and p.name.startswith(prefix)],
            key=lambda p: p.name,
        )
        out.append({"kind": kind, "kling_path": kling_path, "folders": folders})
    return out


# Canonical anti-signal tail — short list of the negatives Kling would otherwise
# default to. Cat ban per feedback_no_cats_in_videos. Kept tight so motion_prompt
# stays under Kling's 2500-char hard cap; the rich realism vocabulary lives in
# the LLM-authored scene body, not here.
ANTI_SIGNALS_TAIL = (
    "no cartoon, no anime, no 3d render, no CGI, no plastic skin, no airbrush, "
    "no beauty filter, no flawless skin, no perfect symmetry, no wax-figure look, "
    "no HDR glow, no oversaturated colors, no chef hat, no neon signs, no on-screen text, "
    "no watermark, no distorted faces, no extra fingers, no cat, no cats, no kitten, "
    "no feline, no pets other than ciao the italian greyhound."
)

# Photoreal tail — bare essentials only. Camera + format + the explicit photoreal
# anchor. The LLM-authored body carries the rich texture (mixed lighting, wear,
# skin imperfections, handheld, weighted motion) per build_system_prompt rules.
PHOTOREAL_TAIL = (
    "shot on ARRI Alexa, 35mm anamorphic, shallow depth of field, ISO 400-800 organic "
    "film grain, photoreal documentary-realism, vertical 9:16."
)

# Negative prompt block — adjective-only form for frame description files
# (Runway has a separate negative_prompt slot). Mirrors ANTI_SIGNALS_TAIL minus
# the leading "no " prefixes.
NEGATIVE_PROMPT_BLOCK = (
    "3d render, unreal engine, pixar, CGI, rendered look, plastic skin, "
    "over-smoothed textures, airbrush, beauty filter, flawless skin, perfect symmetry, "
    "wax-figure look, digital avatar, anime, cartoon, stylised animation, HDR glow, "
    "oversaturated colors, hyperreal, epic, cinematic-masterpiece look, stock-footage look, "
    "modern minimalist restaurant, american diner, asian restaurant, sushi, neon signs, "
    "chef hat, on-screen text, captions, watermark, logo, subtitles, distorted faces, "
    "extra fingers, cat, cats, kitten, kittens, feline"
)

# Friend character_id -> set of all-caps speaker tags that resolve to that friend.
# Compound friends (a couple) map multiple tags to one character_id because the
# downstream voice registry keys on the compound id.
FRIEND_SPEAKER_TAGS: dict[str, set[str]] = {
    "enzo_maria": {"ENZO", "MARIA"},
    "danny": {"DANNY"},
    "sophie": {"SOPHIE"},
    "arun_priya": {"ARUN", "PRIYA"},
}

_SPEAKER_PREFIX_RE = re.compile(r'[A-Z][A-Z_]+:\s*(?:\([^)]*\)\s*)?')
_SPEAKER_TAG_RE = re.compile(r'\b([A-Z][A-Z_]+):')
_WORD_COUNT_TAIL_RE = re.compile(r'\s*WORD COUNT:\s*\d+\s*$')


def clean_vo_text(text: str) -> str:
    """Strip inline speaker prefixes ("BELLA:"), stage directions in parens,
    trailing "WORD COUNT: N" tags, and ** markdown markers. Collapse whitespace.
    Kling voices the literal string, so any residue gets spoken verbatim."""
    t = text.replace('**', '')
    t = _WORD_COUNT_TAIL_RE.sub('', t).strip()
    t = _SPEAKER_PREFIX_RE.sub('', t)
    return re.sub(r'\s+', ' ', t).strip()


def resolve_vo(raw_text: str, subject: str, friend_id: str) -> tuple[str, str, str]:
    """Return (vo_speaker_character_id, cleaned_vo_text, lip_sync_flag).

    Rules:
      1. subject == "ciao"           -> bella narrates, Lip Sync OFF  (dog can't lip-sync)
      2. "**" in raw text            -> implicit voice break -> bella narrates, OFF
      3. 2+ distinct speaker tags    -> collapse to bella, OFF
      4. exactly 1 tag matching the on-screen subject -> that speaker, ON
      5. otherwise (no tag, tag≠subject) -> bella narrates, OFF
    """
    cleaned = clean_vo_text(raw_text)
    if subject == "ciao":
        return "bella", cleaned, "OFF"
    if "**" in raw_text:
        return "bella", cleaned, "OFF"
    tags = set(_SPEAKER_TAG_RE.findall(raw_text)) - {"CIAO"}
    if len(tags) >= 2:
        return "bella", cleaned, "OFF"
    if len(tags) == 1:
        tag = next(iter(tags))
        if subject == "bella" and tag == "BELLA":
            return "bella", cleaned, "ON"
        if subject == "friend" and tag in FRIEND_SPEAKER_TAGS.get(friend_id, set()):
            return friend_id, cleaned, "ON"
    return "bella", cleaned, "OFF"


def compose_files(shot: dict) -> dict[str, str]:
    """Build the 3 text files for one per-video folder. Returns a dict
    {filename: contents}; caller writes to disk after all-or-nothing validation.
    """
    sid = shot["shot_index"]
    kind_word = "REEL" if shot["episode_kind"] == "reel" else "STORY"
    full_refs = "\n".join(
        f"  {tag} ref : {path}"
        for tag, path in shot["character_refs"]
    )
    paste_refs = "\n".join(
        f"  [{tag}] {path}"
        for tag, path in shot["character_refs"]
    )

    vo_speaker = shot.get("vo_speaker") or "bella"
    vo_text = shot.get("vo_text") or ""
    lip_sync = shot.get("lip_sync") or "OFF"
    # Kling only accepts Duration 5 or 10. Any shot with VO gets 10 (headroom for
    # the full line + tail); pure B-roll with no VO gets 5.
    duration = 10 if vo_text else 5
    episode_id = shot["episode_id"]
    vo_text_escaped = vo_text.replace('"', '\\"')

    # Kling image2video has a HARD 2500-char cap on the prompt block (the text
    # between the PASTE INTO KLING banner and the REJECT IF marker). Pre-cap the
    # LLM-authored visual body so the assembled motion_prompt always fits, even
    # when Sonnet ignores its STRICT MAX in build_system_prompt. We budget for
    # the 3 header lines + 2 tails + newlines and reserve the rest for the body.
    KLING_PROMPT_CAP = 2500
    HEADER_LINES = (
        f"MOTION INTENT: {shot['motion_intent']}\n"
        f"CONTINUITY LINK: {shot['continuity_link']}\n"
        f"CAMERA DIRECTIVE: {shot['camera_directive']}\n\n"
    )
    fixed_overhead = len(HEADER_LINES) + len(PHOTOREAL_TAIL) + len(ANTI_SIGNALS_TAIL) + 4  # spaces+newlines
    body_budget = KLING_PROMPT_CAP - fixed_overhead - 50  # 50-char safety margin
    visual_body = shot["first_frame_prompt"]
    if len(visual_body) > body_budget:
        # Trim at last sentence boundary within budget so we don't cut mid-clause.
        truncated = visual_body[:body_budget]
        last_dot = max(truncated.rfind(". "), truncated.rfind(".\n"))
        if last_dot > body_budget // 2:
            visual_body = truncated[:last_dot + 1]
        else:
            visual_body = truncated.rstrip().rstrip(",").rstrip(".") + "."

    prompt_txt = f"""========================================================================
DAY {shot['day']} · {kind_word} · SHOT {sid:02d} — "{shot['title'][:60]}"
========================================================================

╔════════════════════════════════════════════════════════════════════════╗
║  KLING PROMPT — PASTE INTO KLING (prompt box)                        ║
╚═════════════════════════════════════════════════════════════════════╝

MOTION INTENT: {shot['motion_intent']}
CONTINUITY LINK: {shot['continuity_link']}
CAMERA DIRECTIVE: {shot['camera_directive']}

{visual_body} {PHOTOREAL_TAIL} {ANTI_SIGNALS_TAIL}

------------------------------------------------------------------------

VO (paste into Kling voice + script fields)
-------------------------------------------
VO SPEAKER: {vo_speaker}
VO TEXT: "{vo_text_escaped}"

(VO VOICE resolves at render time from script_engine/data/character_voices.json via VO SPEAKER.)

KLING SETTINGS
--------------
Model         : Kling 3.0 (or latest)
Mode          : Image-to-Video (image_head + image_tail)
Aspect ratio  : 9:16 (vertical)
Duration      : {duration}
CFG / prompt adherence : 0.5
Lip Sync      : {lip_sync}
Multi-Shot    : OFF (preserves start+end interpolation)

VISUAL SUBJECTS IN FRAME
------------------------
  {shot['character_id']}
{full_refs}

START FRAME   : start.png   (in this folder)
END FRAME     : end.png     (in this folder)

REJECT IF (re-roll on any of these)
-----------------------------------
- Identity drift (face / hair / eye colour / wardrobe) for any named character
- Lip sync does not match spoken text (lip-sync shots only)
- Cartoon / 3D / oversaturated look
- Bella not looking into the lens / not talking to camera (Camera Address Mandate — every Bella shot)
- Bella pitches / teases product / sells in body (acceptable ONLY if shot is 0–5s hook)

SAVE BEST TAKE
--------------
renders/{episode_id}_shot{sid:02d}.mp4
"""

    def _frame_desc(which: str, body: str) -> str:
        return f"""================================================================
{which.upper()} FRAME DESCRIPTION — DAY {shot['day']} · SHOT {sid:02d}
================================================================

Use this prompt to generate the {which}.png for this folder.

Pass to Runway Gen-4 Image WITH these reference PNGs:
{paste_refs}

Output: {which}.png in this folder.

================================================================
PROMPT
================================================================

{body} {PHOTOREAL_TAIL}

================================================================
NEGATIVE PROMPT
================================================================

{NEGATIVE_PROMPT_BLOCK}
"""

    return {
        "PROMPT.txt": prompt_txt,
        "start_frame_description.txt": _frame_desc("start", shot["first_frame_prompt"]),
        "end_frame_description.txt": _frame_desc("end", shot["last_frame_prompt"]),
    }


def build_system_prompt() -> str:
    """Static system prompt: identity locks, anti-signals, distinctness rule,
    motion-delta rule, and the JSON schema. Built once per process."""
    bella = character_prompt("bella")
    ciao = character_prompt("ciao")
    return f"""You are a cinematographer authoring per-shot frame prompts for a Bella reel/story episode.

Bella's restaurant universe is photorealistic documentary cinema — ARRI Alexa, 35mm anamorphic, warm Italian-trattoria palette. NEVER cartoon, anime, 3D render, plastic skin, or wax-figure look.

CHARACTER IDENTITY LOCKS (use these as identity anchors when these characters appear in a scene; do NOT paste verbatim into your output):

{bella}

{ciao}

(For other characters — friend, ally — defer to the character_id given in the user message; the renderer pulls the correct reference image at render time.)

HARD RULES:
1. Never include cat, cats, kitten, kittens, or feline in any prompt. The only allowed animal in any scene is Ciao the Italian Greyhound.
2. Each shot's `first_frame_prompt` MUST be visually distinct from every other shot's first_frame_prompt in the same episode. No two shots share the same scene composition.
3. Each shot's `last_frame_prompt` MUST start with a NAMED MICRO-CHANGE (Motion Delta rule): a small, observable difference from the first frame — a hand lifts an inch, steam drifts to the right, a phone screen has just re-rendered. Never just "Same composition" or copy of the first frame.
4. Stay grounded in the shot's title + dialogue. The visual must serve the spoken line.
5. Photoreal language is appended automatically downstream — focus your output on scene composition, blocking, lighting cues, and the named micro-change for end frames.

REAL-WORLD GROUNDING (most important — author every scene like documentary, not like advertising):
6. Locations are working restaurants in real cities — describe them with WEAR-AND-TEAR specifics: chipped paint at the host stand, water rings on a wooden table, a slightly lifted floor tile by the door, fingerprints on the wine fridge glass, flour dust in a cloth, a half-empty bread basket, a crumpled receipt left on the counter. NEVER say "pristine," "spotless," "flawless," "perfect," "epic," "cinematic-masterpiece" — those words are banned.
7. Lighting is always MIXED-SOURCE — warm tungsten pendants from above, cooler window daylight from one side, the cool blue glow of any phone/tablet screen in frame, sometimes a single bare bulb at the back. Never describe single-source lighting, never "flat lighting," never "evenly lit."
8. Show signs of LIFE — a server walking past in soft focus at the edge of frame, the back of someone's head at the next table, a passing bus reflected in the front window, a hand entering frame from the left to set down a glass. The world keeps moving around the subject.
9. People are HUMAN — visible skin pores in the T-zone, a stray flyaway hair at the temple, faint freckles across the nose, fabric wrinkles where the shirt pulls at the shoulder, a wedding ring or its absence respected, slight redness in the sclera if it's late in service. Never say "smooth skin," "flawless," "beauty-shot," "perfect features."
10. Motion has WEIGHT and FRICTION — describe HOW someone moves, not that they "walk" or "jump." A hand pushes the plate forward and the plate scrapes a quarter-inch on the wood. Maria's left shoulder lifts a beat before her right. The tablet's weight pulls the host stand forward half an inch.
11. Camera is HANDHELD — micro-jitter, the operator's breath, a tiny re-frame mid-take. Never tripod-locked, never gimbal-smooth.

LENGTH BUDGET (HARD): Kling rejects prompts over 2500 chars. Pick 2-3 SPECIFIC concrete details per realism category — do NOT exhaustively list every cue from rules 6-11. Better to land 3 vivid wear-and-tear details than 8 generic ones.

OUTPUT: Reply with a single JSON object, no prose, in exactly this shape. STRICT character limits — exceeding them fails the render:
{{
  "shots": [
    {{
      "shot_index": <int matching the shot in the user message>,
      "first_frame_prompt": "<scene body, STRICT MAX 1400 chars>",
      "last_frame_prompt": "<motion-delta variant, STRICT MAX 600 chars, leads with the named micro-change>"
    }}
  ]
}}
"""


def build_user_message(shots: list[dict], episode_kind: str, day: int, friend_id: str) -> str:
    """Per-episode user message: shot list with title + dialogue + reference cues
    + writer's prior prompt (as steering, NOT as ground truth — the model is
    asked to re-author for distinctness)."""
    lines = [
        f"Day {day} {episode_kind.upper()} episode (friend: {friend_id}).",
        f"Author distinct first_frame_prompt + last_frame_prompt for each of the {len(shots)} shots below.",
        "",
        "SHOTS:",
    ]
    for s in shots:
        lines.append("")
        lines.append(f"SHOT {s['shot_index']} — \"{s['title']}\"")
        if s.get("spoken_text"):
            lines.append(f"  Dialogue: \"{s['spoken_text']}\"")
        if s.get("first_frame_prompt"):
            lines.append(f"  Writer's prior first-frame (for context, do NOT copy verbatim): {s['first_frame_prompt'][:200]}…")
        if s.get("last_frame_prompt"):
            lines.append(f"  Writer's prior last-frame (for context, do NOT copy verbatim): {s['last_frame_prompt'][:200]}…")
    lines.append("")
    lines.append("Return JSON only. Every shot_index above must appear exactly once in your `shots` array.")
    return "\n".join(lines)


def call_sonnet(system: str, user: str) -> dict:
    """Single Anthropic call to claude-sonnet-4-6. Returns parsed JSON dict.
    One retry with 5s backoff on any exception; second failure re-raises."""
    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = msg.content[0].text
            # Sonnet sometimes wraps JSON in ```json … ``` fences; strip them.
            text = re.sub(r"^```(?:json)?\s*", "", text.strip())
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except Exception as e:
            last_err = e
            if attempt == 1:
                time.sleep(5)
                continue
            raise
    raise RuntimeError(f"unreachable; last_err={last_err}")  # pragma: no cover


_SHOT_BLOCK_RE = re.compile(
    r"^## SHOT (\d+)[^\n]*?\n(.*?)(?=^## SHOT \d+|\Z)",
    re.DOTALL | re.MULTILINE,
)
_SPOKEN_RE = re.compile(r"\*\*Spoken text:\*\*\s*\n>\s*\"?(.+?)\"?\s*(?=\n\*\*|\Z)", re.DOTALL)
_MOTION_RE = re.compile(r"\*\*Motion intent:\*\*\s*(.+?)(?=\n|$)")
_CONTINUITY_RE = re.compile(r"\*\*Continuity link:\*\*\s*(.+?)(?=\n|$)")
_CAMERA_RE = re.compile(r"\*\*Camera directive:\*\*\s*(.+?)(?=\n|$)")


def _raw_shot_blocks(kling_path: Path) -> dict[int, str]:
    """Return {shot_index: raw_block_text} parsed straight from KLING.md."""
    text = kling_path.read_text(encoding="utf-8")
    out = {}
    for m in _SHOT_BLOCK_RE.finditer(text):
        out[int(m.group(1))] = m.group(2)
    return out


def _char_id_from_ref_path(path: str) -> str:
    name = Path(path).name
    if name.endswith("_face.png"):
        return name[: -len("_face.png")]
    if name.endswith("_reference.png"):
        return name[: -len("_reference.png")]
    return Path(path).stem


def enrich_shot(
    parsed: dict,
    raw_block: str,
    *,
    episode_kind: str,
    day: int,
    episode_id: str,
    friend_id: str,
    json_shot: dict | None = None,
) -> dict:
    """Decorate the parser's output dict with the extra fields compose_files needs.
    If json_shot (the matching shot dict from full scripts/<episode>.json) is supplied,
    its audio_slice.text + subject drive VO resolution (authoritative source).
    """
    refs = parsed.get("character_refs_named") or []
    character_id = _char_id_from_ref_path(refs[0]) if refs else "bella"
    full_face: list[tuple[str, str]] = []
    for ref in refs:
        full_face.append(("FULL", ref))
        face_candidate = Path(ref).with_name(Path(ref).stem.replace("_reference", "") + "_face.png")
        if face_candidate.is_file():
            full_face.append(("FACE", str(face_candidate)))

    def _grab(rgx, default):
        mm = rgx.search(raw_block)
        return mm.group(1).strip() if mm else default

    raw_vo = ""
    subject = "bella"
    if json_shot is not None:
        raw_vo = (json_shot.get("audio_slice") or {}).get("text") or ""
        subject = json_shot.get("subject") or "bella"
    else:
        m = _SPOKEN_RE.search(raw_block)
        if m:
            raw_vo = m.group(1).strip().strip('"').strip()

    vo_speaker, vo_text, lip_sync = resolve_vo(raw_vo, subject, friend_id)

    return {
        **parsed,
        "spoken_text": vo_text,        # kept for backwards compatibility
        "vo_speaker": vo_speaker,
        "vo_text": vo_text,
        "lip_sync": lip_sync,
        "subject": subject,
        "character_id": character_id,
        "character_refs": full_face,
        "motion_intent": _grab(_MOTION_RE, "establishing wide, 35mm, gentle push-in"),
        "continuity_link": _grab(_CONTINUITY_RE, "wardrobe = continuity, lighting = warm tungsten"),
        "camera_directive": _grab(_CAMERA_RE, "Hold the frame; let the moment land."),
        "episode_kind": episode_kind,
        "episode_id": episode_id,
        "day": day,
    }


def _match_folder(shot_index: int, folders: list[Path], episode_kind: str) -> Path | None:
    """Find the per-video folder for this shot — name pattern: 'Reel NN' or 'Story NN'."""
    prefix = "Reel" if episode_kind == "reel" else "Story"
    target = f"{prefix} {shot_index:02d} "
    for f in folders:
        if f.name.startswith(target):
            return f
    return None


def process_episode(episode: dict, *, day: int, friend_id: str, dry_run: bool) -> dict:
    """Drive one episode through: parse → enrich → call LLM → validate → stage → write.
    Returns {'written': int, 'error': str|None, 'shot_count': int}."""
    kling_path: Path = episode["kling_path"]
    kind: str = episode["kind"]
    folders: list[Path] = episode["folders"]
    episode_id = kling_path.name[: -len(".KLING.md")]

    # Load the sibling JSON (authoritative source for VO text + subject). The
    # KLING.md parser historically left spoken text empty, so fall back to None
    # if the JSON is missing — resolve_vo will treat missing VO as silent B-roll.
    json_path = kling_path.with_name(f"{episode_id}.json")
    json_shots: dict[int, dict] = {}
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            for s in (data.get("shot_list") or {}).get("shots") or []:
                json_shots[int(s["shot_id"])] = s
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"  WARN could not load {json_path.name}: {e}")

    parsed = parse_kling_md(kling_path)
    raw_blocks = _raw_shot_blocks(kling_path)
    enriched = [enrich_shot(p, raw_blocks.get(p["shot_index"], ""),
                             episode_kind=kind,
                             day=day,
                             episode_id=episode_id,
                             friend_id=friend_id,
                             json_shot=json_shots.get(p["shot_index"]))
                for p in parsed]
    expected_indices = [s["shot_index"] for s in enriched]

    # Pre-LLM: warn for shots without a folder, but don't fail
    skipped: list[int] = []
    for s in enriched:
        if _match_folder(s["shot_index"], folders, kind) is None:
            skipped.append(s["shot_index"])
    if skipped:
        print(f"  WARN missing folders for SHOT {skipped} — those shots will be skipped on write")

    if dry_run:
        staged_count = 0
        for s in enriched:
            folder = _match_folder(s["shot_index"], folders, kind)
            if folder is None:
                continue
            staged_count += 1
            print(f"  [dry-run] would write 3 files to {folder.name}")
        return {"written": 0, "error": None, "shot_count": len(enriched), "staged": staged_count}

    sysp = build_system_prompt()
    user = build_user_message(enriched, episode_kind=kind, day=day, friend_id=friend_id)
    try:
        llm_out = call_sonnet(sysp, user)
        validate_llm_output(llm_out, expected_indices)
    except Exception as e:
        msg = f"  FAIL episode {kling_path.name}: {e}"
        print(msg)
        return {"written": 0, "error": str(e), "shot_count": len(enriched)}

    # Build LLM-output index for quick lookup
    by_idx = {s["shot_index"]: s for s in llm_out["shots"]}

    # Stage all writes in memory first (all-or-nothing)
    staged: list[tuple[Path, dict[str, str]]] = []
    for s in enriched:
        folder = _match_folder(s["shot_index"], folders, kind)
        if folder is None:
            continue
        # Overlay the LLM's distinct prompts onto the enriched shot
        s_for_compose = {**s,
                         "first_frame_prompt": by_idx[s["shot_index"]]["first_frame_prompt"],
                         "last_frame_prompt": by_idx[s["shot_index"]]["last_frame_prompt"]}
        staged.append((folder, compose_files(s_for_compose)))

    written = 0
    for folder, files in staged:
        for fname, contents in files.items():
            (folder / fname).write_text(contents, encoding="utf-8")
            written += 1
    print(f"  + wrote {written} files across {len(staged)} folder(s) for {kling_path.name}")
    return {"written": written, "error": None, "shot_count": len(enriched)}


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(CONTENT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="kling_pack — author per-video folder text files")
    parser.add_argument("--day", type=int, required=True)
    parser.add_argument("--episode", choices=("story", "reel"), default=None,
                        help="filter to one episode kind")
    parser.add_argument("--friend", default="auto",
                        help="friend_id for the LLM context (default: auto-detect from filename)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    episodes = discover_episodes(args.day)
    if not episodes:
        print(f"No episodes found for Day {args.day}", file=sys.stderr)
        return 2

    if args.episode:
        episodes = [e for e in episodes if e["kind"] == args.episode]

    print(f"=== kling_pack — Day {args.day} ({'DRY-RUN' if args.dry_run else 'WRITE'}) ===")
    print(f"  episodes: {len(episodes)}  (kinds: {[e['kind'] for e in episodes]})")

    overall_ok = True
    for ep in episodes:
        # Auto-detect friend from filename (between 'bella_' and '_p')
        friend = args.friend
        if friend == "auto":
            m = re.match(r"^bella_([a-z_]+?)_p\d+_", ep["kling_path"].name)
            friend = m.group(1) if m else "unknown"
        print(f"\n[{ep['kind']}] {ep['kling_path'].name} (friend={friend})")
        result = process_episode(ep, day=args.day, friend_id=friend, dry_run=args.dry_run)
        if result["error"]:
            overall_ok = False

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
