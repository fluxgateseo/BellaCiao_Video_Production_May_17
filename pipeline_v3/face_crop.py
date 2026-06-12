"""
face_crop.py — Produce a tight identity-lock crop from a canonical reference PNG.

Sibling `Bellaciao/` passes the face crop (`{character}_face.png`) to
Runway Gen-4 Image as the per-character `referenceImages` slot. Runway
caps at 3 reference images per call, so face-only is the policy: it
isolates the identity signal (eyes, bone structure) from competing
pose/background cues, which gives the most consistent cross-day
character lock at the smallest reference budget. Wardrobe and build
continuity come from the Shared DNA prompt language, not a second
reference image. The full `{character}_reference.png` is retained as
authoring source-of-truth and as a fallback when no face crop exists.

Strategy:
  1. Haar frontal-face cascade finds the largest face.
  2. If 0 faces, try profile-face cascade.
  3. If still 0 (e.g. Ciao the dog, odd crop), fall back to a deterministic
     center-top crop — portrait-oriented references have the subject in
     the upper-center by convention.
  4. If ≥2 faces (compound subjects like `enzo_maria`, `arun_priya`),
     take the bounding box around all detected faces.
  5. Pad by 40% on every side, then square it to 1024x1024.

Pure function: takes a path, writes a path, returns metadata. No network,
no Airtable, no side effects beyond the output file.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
from PIL import Image

_FRONTAL_CASCADE = "haarcascade_frontalface_default.xml"
_PROFILE_CASCADE = "haarcascade_profileface.xml"

_OUTPUT_EDGE = 1024        # final square edge
_PADDING_RATIO = 0.40      # 40% of face edge added on every side
_MIN_FACE_FRACTION = 0.08  # ignore detections smaller than 8% of image width (noise)
_SECONDARY_AREA_RATIO = 0.40  # additional faces must be ≥40% of the largest to count (drops Haar false positives)

# Characters whose canonical reference is not a human face — force deterministic
# center-top crop instead of Haar (Haar hallucinates "faces" in fur/fabric).
_NON_HUMAN_CHARACTERS = {"ciao"}


@dataclass
class CropResult:
    source: str
    output: str
    detection_mode: str        # "frontal" | "profile" | "multi" | "fallback_center"
    faces_found: int
    crop_box: tuple[int, int, int, int]  # (left, top, right, bottom) in source pixels


def _load_cascade(name: str) -> cv2.CascadeClassifier:
    path = Path(cv2.data.haarcascades) / name
    return cv2.CascadeClassifier(str(path))


def _detect_faces(gray, cascade: cv2.CascadeClassifier, min_edge: int) -> list[tuple[int, int, int, int]]:
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(min_edge, min_edge),
    )
    if len(faces) == 0:
        return []
    return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]


def _pad_and_square(
    left: int, top: int, right: int, bottom: int,
    img_w: int, img_h: int,
    padding_ratio: float,
) -> tuple[int, int, int, int]:
    """Expand the detection box by padding_ratio on every side, then square it
    by growing the shorter dimension, staying inside the image."""
    box_w = right - left
    box_h = bottom - top
    pad_x = int(box_w * padding_ratio)
    pad_y = int(box_h * padding_ratio)
    l = max(0, left - pad_x)
    t = max(0, top - pad_y)
    r = min(img_w, right + pad_x)
    b = min(img_h, bottom + pad_y)

    # Square it: grow the shorter side, re-centered
    w, h = r - l, b - t
    if w > h:
        delta = w - h
        t_new = max(0, t - delta // 2)
        b_new = min(img_h, t_new + w)
        if b_new - t_new < w:
            t_new = max(0, b_new - w)
        t, b = t_new, b_new
    elif h > w:
        delta = h - w
        l_new = max(0, l - delta // 2)
        r_new = min(img_w, l_new + h)
        if r_new - l_new < h:
            l_new = max(0, r_new - h)
        l, r = l_new, r_new

    return l, t, r, b


def _center_top_fallback(img_w: int, img_h: int) -> tuple[int, int, int, int]:
    """Deterministic crop for no-face cases (Ciao the dog, odd framing).
    Takes a centered square covering the upper 60% of the image — where
    portrait-composed subjects always sit."""
    edge = min(img_w, int(img_h * 0.6))
    l = (img_w - edge) // 2
    t = int(img_h * 0.05)
    r = l + edge
    b = t + edge
    return l, t, min(r, img_w), min(b, img_h)


def crop_face(source: Path, output: Path | None = None, padding_ratio: float = _PADDING_RATIO) -> CropResult:
    """Crop a face-tight identity reference from `source` into `output`.

    If output is None, writes alongside source as `{stem_without_reference}_face.png`
    — e.g. `bella_reference.png` → `bella_face.png`.
    """
    img = cv2.imread(str(source))
    if img is None:
        raise FileNotFoundError(f"cannot read image: {source}")
    img_h, img_w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cv2.equalizeHist(gray, gray)
    min_edge = max(40, int(img_w * _MIN_FACE_FRACTION))

    # Known non-human subjects (Ciao) skip Haar entirely — the detector
    # hallucinates faces on fur/fabric and widens the box to the whole image.
    character_id = source.stem.replace("_reference", "").lower()
    if character_id in _NON_HUMAN_CHARACTERS:
        faces: list[tuple[int, int, int, int]] = []
        mode = "fallback_center"
    else:
        faces = _detect_faces(gray, _load_cascade(_FRONTAL_CASCADE), min_edge)
        mode = "frontal"
        if not faces:
            faces = _detect_faces(gray, _load_cascade(_PROFILE_CASCADE), min_edge)
            mode = "profile" if faces else mode

        # Filter out Haar false positives: keep only faces whose area is at
        # least _SECONDARY_AREA_RATIO of the largest face. A genuine compound
        # subject (enzo_maria, arun_priya) has two faces of similar size; noise
        # detections on fabric/hair are much smaller.
        if len(faces) >= 2:
            faces_by_area = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            biggest_area = faces_by_area[0][2] * faces_by_area[0][3]
            faces = [f for f in faces_by_area if (f[2] * f[3]) >= biggest_area * _SECONDARY_AREA_RATIO]

    if len(faces) >= 2:
        mode = "multi"
        left = min(x for x, _, _, _ in faces)
        top = min(y for _, y, _, _ in faces)
        right = max(x + w for x, _, w, _ in faces)
        bottom = max(y + h for _, y, _, h in faces)
    elif len(faces) == 1:
        x, y, w, h = faces[0]
        left, top, right, bottom = x, y, x + w, y + h
    else:
        mode = "fallback_center"
        left, top, right, bottom = _center_top_fallback(img_w, img_h)

    l, t, r, b = _pad_and_square(left, top, right, bottom, img_w, img_h, padding_ratio)

    if output is None:
        stem = source.stem.replace("_reference", "")
        output = source.with_name(f"{stem}_face.png")

    pil = Image.open(source).convert("RGBA")
    cropped = pil.crop((l, t, r, b))
    cropped = cropped.resize((_OUTPUT_EDGE, _OUTPUT_EDGE), Image.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(output, format="PNG")

    return CropResult(
        source=str(source),
        output=str(output),
        detection_mode=mode,
        faces_found=len(faces),
        crop_box=(l, t, r, b),
    )


def ensure_face_crop(reference_path: Path, *, force: bool = False) -> Path:
    """Convenience: given `{character}_reference.png`, return the path to its
    face crop, generating it if missing (or if force=True)."""
    stem = reference_path.stem.replace("_reference", "")
    face_path = reference_path.with_name(f"{stem}_face.png")
    if face_path.exists() and not force:
        return face_path
    crop_face(reference_path, face_path)
    return face_path


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Generate face crops from canonical reference PNGs")
    p.add_argument("inputs", nargs="+", help="paths to *_reference.png files (or directories to recurse)")
    p.add_argument("--force", action="store_true", help="regenerate even if the face crop already exists")
    args = p.parse_args()

    targets: list[Path] = []
    for raw in args.inputs:
        path = Path(raw)
        if path.is_dir():
            targets.extend(path.rglob("*_reference.png"))
        else:
            targets.append(path)

    results = []
    for target in sorted(set(targets)):
        stem = target.stem.replace("_reference", "")
        out = target.with_name(f"{stem}_face.png")
        if out.exists() and not args.force:
            print(f"[skip] {out.name} already exists")
            continue
        r = crop_face(target, out)
        print(f"[{r.detection_mode}] {target.name} → {out.name} (faces={r.faces_found}, box={r.crop_box})")
        results.append(asdict(r))

    print(json.dumps({"crops": results, "count": len(results)}, indent=2))
