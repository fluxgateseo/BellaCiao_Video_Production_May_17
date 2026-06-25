# RETIRED — do not run.
#
# This script targets the now-retired SEO/GBP "Bistrot Maison" premise and
# would fail .claude/agents/premise-guard.md on rules 1, 3, and 4 (SEO drift,
# on-camera pitch, retired enemies). Its hard-coded Drive folder belongs to a
# separate project (destinybydao Day 10). See RESUME.md for the canonical
# Day 10 angle (Jake / Narrow Lane / the_missed_call) and scripts/audio/README.md
# for context. The gen -> stitch -> loudnorm -> Drive-upload shape is reusable
# once the on-canon Day 10 script lands.

raise SystemExit(
    "day10_elevenlabs_vo.py is retired. See RESUME.md and scripts/audio/README.md."
)

"""Day 10 — Bistrot Maison: Bella VO production (ElevenLabs Eleven v3).

Generates 5 per-shot WAVs + a stitched full VO, loudness-normalizes to -16
LUFS (IG/TikTok-friendly), and uploads to the Day 10 creatives Drive folder.
Idempotent — re-running replaces files of the same name in the destination.

Usage:
    pip install -r scripts/audio/requirements.txt
    export ELEVENLABS_API_KEY=...
    export GDRIVE_SA_KEY_FILE=/path/to/service-account.json
    python scripts/audio/day10_elevenlabs_vo.py

Env:
    ELEVENLABS_API_KEY   ElevenLabs API key (required)
    BELLA_VOICE_ID       Override Bella voice id (default: YtOuYjXDObEJdpOIyUu1)
    ELEVENLABS_MODEL     TTS model id (default: eleven_v3)
    GDRIVE_SA_KEY_FILE   Path to Drive service-account JSON (for upload)
    GDRIVE_SA_KEY        Alternative: inline service-account JSON content
    SKIP_UPLOAD=1        Skip Drive upload (local-only dry run)
    OUTPUT_DIR           Local output dir (default: ./out/day10)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import requests

ELEVEN_BASE = "https://api.elevenlabs.io/v1"
BELLA_VOICE_ID_DEFAULT = "YtOuYjXDObEJdpOIyUu1"
MODEL_ID_DEFAULT = "eleven_v3"
DRIVE_FOLDER_ID = "1DpqBx2dUZP9ZA3W9Kfk2HXmY9_t6MaNE"  # Day 10 creatives

SAMPLE_RATE = 44100
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1
GAP_MS = 250  # breathing gap between shots in the stitched cut
LUFS_TARGET = -16.0
LUFS_TP = -1.5
LUFS_LRA = 11.0


@dataclass(frozen=True)
class Line:
    shot: int
    label: str
    text: str     # what we send to ElevenLabs (audio tags allowed)
    caption: str  # canonical spoken line = burned on-screen caption


# Captions match the day10-elevenlabs-redo.md spec verbatim. Audio tags
# stay light per the brief ("these are 6s shots") — they shape delivery,
# never bleed into the caption.
LINES: list[Line] = [
    Line(
        shot=1,
        label="HOOK",
        text="[confident] This London bistro is fully booked tonight, yet Google has no way to book it.",
        caption="This London bistro is fully booked tonight, yet Google has no way to book it.",
    ),
    Line(
        shot=2,
        label="PROBLEM",
        text="Their profile shows a phone number, but no Reserve button at all.",
        caption="Their profile shows a phone number but no Reserve button at all.",
    ),
    Line(
        shot=3,
        label="CONSEQUENCE",
        text="[sighs] New diners glance, see no link, then quietly tap somewhere easier.",
        caption="New diners glance, see no link, then quietly tap somewhere easier.",
    ),
    Line(
        shot=4,
        label="FIX",
        text="[warm] One change: connect your booking platform so a Reserve button appears.",
        caption="One change: connect your booking platform so a Reserve button appears.",
    ),
    Line(
        shot=5,
        label="PAYOFF",
        text="[excited] Now tables fill straight from the listing — go add yours today.",
        caption="Now tables fill straight from the listing — go add yours today.",
    ),
]


def tts(api_key: str, voice_id: str, model_id: str, text: str) -> bytes:
    """Eleven v3 → raw PCM 16-bit 44.1kHz mono bytes."""
    url = f"{ELEVEN_BASE}/text-to-speech/{voice_id}"
    params = {"output_format": "pcm_44100"}
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/pcm",
    }
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.35,
            "use_speaker_boost": True,
        },
    }
    r = requests.post(url, params=params, headers=headers, json=body, timeout=120)
    if not r.ok:
        raise RuntimeError(
            f"ElevenLabs TTS failed ({r.status_code}) for shot text "
            f"{text[:60]!r}: {r.text[:500]}"
        )
    return r.content


def write_wav(path: Path, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


def silence_bytes(ms: int) -> bytes:
    samples = int(SAMPLE_RATE * ms / 1000)
    return b"\x00" * (samples * SAMPLE_WIDTH * CHANNELS)


def stitch(paths: list[Path], out: Path, gap_ms: int = GAP_MS) -> None:
    pad = silence_bytes(gap_ms)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        for i, p in enumerate(paths):
            with wave.open(str(p), "rb") as r:
                if (r.getnchannels(), r.getsampwidth(), r.getframerate()) != (
                    CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE,
                ):
                    raise RuntimeError(f"format mismatch in {p}")
                w.writeframes(r.readframes(r.getnframes()))
            if i != len(paths) - 1:
                w.writeframes(pad)


def loudnorm(src: Path) -> None:
    """Replace src with an EBU R128 loudness-normalized copy.

    -16 LUFS / -1.5 dBTP / 11 LRA matches typical short-form social loudness.
    If ffmpeg isn't installed we leave the raw WAV in place and warn — the
    pipeline still produces something usable for review.
    """
    tmp = src.with_suffix(".norm.wav")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-af", f"loudnorm=I={LUFS_TARGET}:TP={LUFS_TP}:LRA={LUFS_LRA}",
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS), "-sample_fmt", "s16",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("warn: ffmpeg not on PATH; skipping loudness norm", file=sys.stderr)
        return
    except subprocess.CalledProcessError as e:
        print(f"warn: ffmpeg loudnorm failed on {src.name}: {e}", file=sys.stderr)
        return
    tmp.replace(src)


def drive_client():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    scopes = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    key_file = os.environ.get("GDRIVE_SA_KEY_FILE")
    key_json = os.environ.get("GDRIVE_SA_KEY")
    if key_file:
        creds = service_account.Credentials.from_service_account_file(key_file, scopes=scopes)
    elif key_json:
        creds = service_account.Credentials.from_service_account_info(json.loads(key_json), scopes=scopes)
    else:
        raise RuntimeError(
            "Drive upload needs GDRIVE_SA_KEY_FILE or GDRIVE_SA_KEY "
            "(or set SKIP_UPLOAD=1 for a local-only run)"
        )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_or_replace(service, folder_id: str, local: Path) -> str:
    from googleapiclient.http import MediaFileUpload

    safe_name = local.name.replace("'", "\\'")
    q = (
        f"name = '{safe_name}' and '{folder_id}' in parents "
        "and trashed = false"
    )
    res = service.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    media = MediaFileUpload(str(local), mimetype="audio/wav", resumable=False)
    if res.get("files"):
        fid = res["files"][0]["id"]
        service.files().update(fileId=fid, media_body=media).execute()
        return fid
    meta = {"name": local.name, "parents": [folder_id]}
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    return f["id"]


def main() -> int:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("error: ELEVENLABS_API_KEY not set", file=sys.stderr)
        return 2
    voice_id = os.environ.get("BELLA_VOICE_ID", BELLA_VOICE_ID_DEFAULT)
    model_id = os.environ.get("ELEVENLABS_MODEL", MODEL_ID_DEFAULT)
    out_dir = Path(os.environ.get("OUTPUT_DIR", "out/day10"))
    skip_upload = os.environ.get("SKIP_UPLOAD") == "1"

    print(f"voice_id={voice_id}  model={model_id}  out={out_dir}")

    per_shot: list[Path] = []
    for line in LINES:
        path = out_dir / f"day10_shot{line.shot}.wav"
        print(f"[shot {line.shot} {line.label}] {line.caption}")
        pcm = tts(api_key, voice_id, model_id, line.text)
        write_wav(path, pcm)
        loudnorm(path)
        per_shot.append(path)
        time.sleep(0.5)  # gentle pacing under rate limits

    stitched = out_dir / "day10_vo_full.wav"
    stitch(per_shot, stitched)
    loudnorm(stitched)

    summary: dict = {
        "voice_id": voice_id,
        "model_id": model_id,
        "drive_folder_id": DRIVE_FOLDER_ID,
        "shots": [
            {
                "shot": l.shot,
                "label": l.label,
                "caption": l.caption,
                "tts_text": l.text,
                "file": str(p),
            }
            for l, p in zip(LINES, per_shot)
        ],
        "stitched": str(stitched),
    }

    if skip_upload:
        print("SKIP_UPLOAD=1; not uploading to Drive")
        (out_dir / "production.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return 0

    service = drive_client()
    uploaded: dict[str, str] = {}
    for p in per_shot + [stitched]:
        fid = upload_or_replace(service, DRIVE_FOLDER_ID, p)
        uploaded[p.name] = fid
        print(f"uploaded {p.name} -> {fid}")
    summary["drive_file_ids"] = uploaded
    (out_dir / "production.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
