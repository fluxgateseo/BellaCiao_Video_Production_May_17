"""
assets.py — resolve avatar reference image paths.

The Bellaciao content engine itself never touches images, but every job file
should carry absolute paths to the relevant avatar references so the
downstream video pipeline (Kling / Sync.so) can pick them up
without re-deriving the location.

Sources (relative to ../Creatives/):
  Bella_pictures_avatar/bella_busy_bar.jpeg
  Bella's Friends avatar/{friend_id}_reference.png
  Bella's Friends avatar/ciao_reference.png
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# script_engine/  →  ../Creatives/
CREATIVES_DIR = (Path(__file__).parent.parent / "Creatives").resolve()

BELLA_AVATAR_DIR  = CREATIVES_DIR / "Bella_pictures_avatar"
FRIENDS_AVATAR_DIR = CREATIVES_DIR / "Bella's Friends avatar"

BELLA_DEFAULT      = BELLA_AVATAR_DIR / "bella_busy_bar.jpeg"
CIAO_REFERENCE     = FRIENDS_AVATAR_DIR / "ciao_reference.png"


def _exists_or_none(p: Path) -> Optional[str]:
    return str(p) if p.exists() else None


def bella_avatar() -> Optional[str]:
    """Return the canonical Bella reference image path, or None if missing."""
    return _exists_or_none(BELLA_DEFAULT)


def ciao_avatar() -> Optional[str]:
    return _exists_or_none(CIAO_REFERENCE)


def friend_avatar(friend_id: str) -> Optional[str]:
    """
    Return the absolute path of the friend's reference PNG, or None if missing.
    Naming convention: {friend_id}_reference.png in Bella's Friends avatar/.
    """
    if not friend_id:
        return None
    return _exists_or_none(FRIENDS_AVATAR_DIR / f"{friend_id}_reference.png")


def avatar_bundle(friend_id: str) -> dict:
    """All three references in one dict — convenient for scene_brief enrichment."""
    return {
        "bella_avatar":  bella_avatar(),
        "ciao_avatar":   ciao_avatar(),
        "friend_avatar": friend_avatar(friend_id),
    }


if __name__ == "__main__":
    import json, sys
    fid = sys.argv[1] if len(sys.argv) > 1 else "jake"
    print(json.dumps({
        "creatives_dir": str(CREATIVES_DIR),
        "exists":        CREATIVES_DIR.exists(),
        **avatar_bundle(fid),
    }, indent=2))
