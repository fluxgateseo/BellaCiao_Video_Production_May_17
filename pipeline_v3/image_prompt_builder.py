"""
image_prompt_builder.py — Pure functions for character + shot prompt bodies.

This project emits SCENE-BODY prompts only. Sibling Bellaciao project appends
the Shared DNA + Shared Negatives blocks (per Master Documents/IMAGE_GENERATION_SPEC.md)
before calling Runway Gen-4 Image.

No I/O beyond reading static data files (friends_db.json, allies.json, the
target episode's .KLING.md). No network calls. No Airtable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SHOT_BLOCK_RE = re.compile(
    r"^## SHOT (\d+)[^\n]*?\"([^\"]+)\"\s*\n(.*?)(?=^## SHOT \d+|\Z)",
    re.DOTALL | re.MULTILINE,
)
_FIRST_FRAME_RE = re.compile(
    r"\*\*First-frame prompt:\*\*\s*\n>\s*(.+?)(?=\n\n|\n\*\*|\Z)",
    re.DOTALL,
)
_LAST_FRAME_RE = re.compile(
    r"\*\*Last-frame prompt:\*\*\s*\n>\s*(.+?)(?=\n\n|\n\*\*|\Z)",
    re.DOTALL,
)
_CHAR_REF_RE = re.compile(r"\*\*Character reference:\*\*\s*`([^`]+)`")


def parse_kling_md(kling_path: Path) -> list[dict[str, Any]]:
    """Parse a *.KLING.md file into a list of shot dicts.

    Returns: [{"shot_index": int, "title": str,
               "first_frame_prompt": str,
               "last_frame_prompt": str | None,
               "character_refs_named": [str, ...]}, ...]
    """
    text = kling_path.read_text(encoding="utf-8")
    shots = []
    for m in _SHOT_BLOCK_RE.finditer(text):
        idx = int(m.group(1))
        title = m.group(2).strip()
        body = m.group(3)
        ff = _FIRST_FRAME_RE.search(body)
        first_frame = re.sub(r"\n>\s*", " ", ff.group(1)).strip() if ff else ""
        lf = _LAST_FRAME_RE.search(body)
        last_frame = (re.sub(r"\n>\s*", " ", lf.group(1)).strip() or None) if lf else None
        char_refs = [c.strip() for c in _CHAR_REF_RE.findall(body)]
        shots.append({
            "shot_index": idx,
            "title": title,
            "first_frame_prompt": first_frame,
            "last_frame_prompt": last_frame,
            "character_refs_named": char_refs,
        })
    return shots


_DATA = Path(__file__).resolve().parent.parent / "data"
_MASTER = Path(__file__).resolve().parent.parent.parent / "Master Documents"


def _load_friends() -> dict[str, dict]:
    raw = json.loads((_DATA / "friends_db.json").read_text(encoding="utf-8"))
    return {f["id"]: f for f in raw["friends"]}


def _load_allies() -> dict[str, dict]:
    raw = json.loads((_DATA / "allies.json").read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {a["id"]: a for a in raw}
    return {a["id"]: a for a in raw.get("allies", raw)}


# Bella + Ciao bodies — pulled from Master Documents/BELLA_MASTER_BIBLE.md
# and IMAGE_GENERATION_SPEC.md. Locked here so prompts are deterministic.

_BELLA_BODY = (
    "BELLA — 25-year-old Italian-American woman with Irish roots, born and "
    "raised in New York, Melbourne home base. Long dark-brown hair, "
    "centre-parted, loosely waved past her shoulders, subtle warm highlights. "
    "Warm olive-fair skin with visible pores and natural texture, bright "
    "clear BLUE eyes with a darker iris ring (NOT hazel, NOT green, NOT "
    "brown), thick dark eyebrows, full soft lips. Default expression: "
    "relaxed face, soft half-smile at rest, alive eyes that are already "
    "smiling before the mouth does — full smile only when earned. Small "
    "subtle gold earrings. Dark navy-blue fitted V-neck t-shirt with real "
    "fabric wrinkles. Standing at the bar of a modern 2026 hospitality "
    "venue — warm amber tungsten bokeh behind her, softly blurred pendant "
    "lights, brass fixtures, the room alive but out of focus. Mid-shot, "
    "chest-up, eye level, looking directly into the lens, talking to "
    "camera. Real, unstaged, photorealistic documentary. Vertical 9:16."
)

_CIAO_BODY = (
    "CIAO — small sleek smooth-coated ITALIAN GREYHOUND / whippet-type dog, "
    "warm tan-fawn short coat, slender muzzle, long slender legs, folded "
    "floppy ears, large dark expressive eyes, thin dark leather collar with "
    "a small gold heart-shape tag. Sitting calmly on a wooden trattoria "
    "chair, head tilted slightly, alert friendly expression. NEVER a "
    "terrier, NEVER wire-haired, NEVER scruffy, NEVER beige-and-white. "
    "Bar stool and warm brick wall behind. Mid-shot, low eye level, looking "
    "direct to camera. Vertical 9:16."
)


def _ally_location_clause(tied_to_friend_id: str) -> str:
    """Build a modern 2026 restaurant location clause for an ally, matching
    the established Bella/friends avatar style: photorealistic documentary,
    subject chest-up centered, warm amber tungsten bokeh pendants softly
    blurred in the background, natural expression, modern venue.
    """
    friends = _load_friends()
    f = friends.get(tied_to_friend_id, {})
    restaurant = f.get("restaurant_name", "the restaurant")
    city = f.get("city", "Melbourne")
    neighbourhood = f.get("neighbourhood", "")
    locale = f"{neighbourhood}, {city}" if neighbourhood else city
    return (
        f"Seated at a corner table inside {restaurant}, a real present-day "
        f"{city} Italian restaurant in {locale}. Background softly blurred: "
        f"warm amber tungsten bokeh from pendant lights, brass fixtures, "
        f"exposed brick feature wall, wood tones catching the light — the "
        f"room alive but out of focus. Foreground: white linen tablecloth, "
        f"a single espresso cup, a modern smartphone. Subject centred, "
        f"chest-up, natural genuine warm expression — calm, unforced. "
        f"Real human, unstaged, photorealistic documentary — NOT stylized, "
        f"NOT posed, NOT a stock photo. Same style and lighting palette as "
        f"the established Bella cast reference library."
    )


def character_prompt(character_id: str, day_context: dict | None = None) -> str:
    """Build a scene-body prompt for a single character's reference image.

    character_id: stable id (`bella`, `ciao`, friend id like `enzo`, ally id like `frank`).
    day_context: optional dict carrying friend's restaurant context for friend-prompts.
    Returns: scene-body string ≤ 600 chars (sibling project appends DNA + negatives).
    """
    cid = character_id.lower()

    if cid == "bella":
        return _BELLA_BODY
    if cid == "ciao":
        return _CIAO_BODY

    friends = _load_friends()
    if cid in friends:
        f = friends[cid]
        loc = f.get("restaurant_name", "their restaurant")
        city = f.get("city", "")
        cuisine = f.get("cuisine", "")
        return (
            f"{f['name'].upper()} — owner of {loc} ({cuisine}) in {city}. "
            f"Mid-shot at the kitchen pass, eye level, warm trattoria interior, "
            f"copper pots and brick wall behind, soft confident expression, "
            f"looking just off-camera. Wardrobe: cream canvas apron with TAN "
            f"LEATHER neck and waist straps over a black short-sleeve shirt. "
            f"Vertical 9:16."
        )

    allies = _load_allies()
    if cid in allies:
        a = allies[cid]
        age = a.get("age", "60s")
        role = a.get("role", "regular customer")
        tied = a.get("tied_to_friend_id", "")
        loc_clause = _ally_location_clause(tied)
        return (
            f"{a['name'].upper()} — {role}, age {age}. "
            f"{a.get('physical_description', 'Anglo-Australian, warm lined face, grey hair.')} "
            f"{loc_clause} "
            f"Mid-shot, eye level, calm direct expression. "
            f"Photorealistic documentary, 2026 present-day. Vertical 9:16."
        )

    raise KeyError(f"Unknown character_id: {character_id!r}")


def _char_id_from_ref_path(path: str) -> str | None:
    name = Path(path).name
    if name.endswith("_face.png"):
        return name[: -len("_face.png")]
    if name.endswith("_reference.png"):
        return name[: -len("_reference.png")]
    return None


def _build_name_tag_map(char_ids: list[str]) -> dict[str, str]:
    """Map display name -> @tag. Used to rewrite shot prompts for Runway
    Gen-4's @mention syntax. Compound friend IDs (e.g. 'enzo_maria')
    share one tag across the two first-names — the reference PNG shows
    both people together and Runway resolves both mentions to it.
    Character ids missing from friends_db / allies.json fall through
    silently (no mapping, no @tag injected)."""
    mapping: dict[str, str] = {}
    if "bella" in char_ids:
        mapping["Bella"] = "bella"
    if "ciao" in char_ids:
        mapping["Ciao"] = "ciao"
    try:
        friends = _load_friends()
        allies = _load_allies()
    except Exception:
        return mapping
    for cid in char_ids:
        if cid in ("bella", "ciao"):
            continue
        if cid in friends:
            for part in cid.split("_"):
                if part:
                    mapping[part.capitalize()] = cid
        elif cid in allies:
            first = (allies[cid].get("name") or "").split()[0] if allies[cid].get("name") else ""
            if first:
                mapping[first] = cid
    return mapping


def _inject_at_tags(body: str, name_to_tag: dict[str, str]) -> str:
    """Replace first whole-word occurrence of each display name with
    @{tag}, case-insensitive. Subsequent mentions (pronouns, repeated
    names) stay as prose — Runway resolves the reference once per @tag."""
    if not body or not name_to_tag:
        return body
    out = body
    for name, tag in name_to_tag.items():
        out = re.sub(rf"\b{re.escape(name)}\b", f"@{tag}", out,
                     count=1, flags=re.IGNORECASE)
    return out


def shot_prompt(shot: dict, character_refs: list[str]) -> dict[str, str | None]:
    """Build scene-body prompts for a shot's start and end frames.

    shot: dict from parse_kling_md().
    character_refs: list of absolute paths to character face crops
      (`*_face.png`). Caller is expected to priority-order characters
      (Bella > friend > Ciao > ally) so the Runway 3-ref truncation drops
      the lowest-priority character first.

    Returns: {"start_body": str, "end_body": str | None}
      - start_body: first-frame prompt with @tag mentions injected and a
        single REFERENCE IMAGES header listing the face refs to bind to
        Runway Gen-4's `referenceImages` slots (max 3).
      - end_body: None when the writer omitted Last-frame prompt.
    """
    unique_cids: list[str] = []
    seen: set[str] = set()
    for p in character_refs:
        cid = _char_id_from_ref_path(p)
        if cid and cid not in seen:
            unique_cids.append(cid)
            seen.add(cid)
    name_to_tag = _build_name_tag_map(unique_cids)

    # Runway Gen-4 caps referenceImages at 3; caller orders by priority,
    # we truncate the tail when more than 3 characters are present.
    face_lines = [
        f"  - tag={_char_id_from_ref_path(p) or 'unknown'}  {p}"
        for p in character_refs if p.endswith("_face.png")
    ][:3]

    def _wrap(body: str) -> str:
        if not body:
            return body
        body = _inject_at_tags(body, name_to_tag)
        if not face_lines:
            return body
        ref_note = (
            "REFERENCE IMAGES (Runway Gen-4 — pass as `referenceImages`, "
            "max 3; @tags in prompt resolve to these):\n"
            + "\n".join(face_lines)
        )
        return f"{ref_note}\n\n{body}"

    return {
        "start_body": _wrap(shot["first_frame_prompt"].strip()),
        "end_body": _wrap(shot["last_frame_prompt"].strip())
                    if shot.get("last_frame_prompt") else None,
    }


def shot_is_signoff(shot: dict) -> bool:
    """Detect the Bella sign-off shot by title.

    Writer rule: every Bella sign-off shot's title contains the
    substring 'bella sign-off' (case-insensitive). See
    docs/superpowers/specs/2026-04-17-kling-start-end-frames-design.md.
    """
    title = (shot.get("title") or "").lower()
    return "bella sign-off" in title
