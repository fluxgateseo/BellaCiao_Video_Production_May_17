# Day 10 — Bella VO (ElevenLabs Eleven v3)

Reproducible build for the 5 Bella voiceover lines in Day 10 — "Bistrot Maison
(No Table to Book)". Generates per-shot WAVs + a stitched full cut, loudness
normalizes, and uploads to the Day 10 creatives Drive folder.

## Inputs

| Field | Value |
|---|---|
| Voice (Bella) | `YtOuYjXDObEJdpOIyUu1` |
| Model | `eleven_v3` |
| Drive folder | `1DpqBx2dUZP9ZA3W9Kfk2HXmY9_t6MaNE` (Day 10 creatives) |
| Scope | **VO only** — does not re-render Kling shots |

The 5 lines, audio-tag scripts, and canonical captions live in
`day10_elevenlabs_vo.py` (`LINES`). Captions match the handoff spec verbatim;
audio tags shape delivery only and never burn on-screen.

## Run

```bash
pip install -r scripts/audio/requirements.txt
export ELEVENLABS_API_KEY=...
export GDRIVE_SA_KEY_FILE=/path/to/service-account.json
python scripts/audio/day10_elevenlabs_vo.py
```

Optional: `BELLA_VOICE_ID`, `ELEVENLABS_MODEL`, `OUTPUT_DIR`, `SKIP_UPLOAD=1`
(local-only — useful when iterating on delivery before pushing to Drive).

## Output

```
out/day10/
  day10_shot1.wav  …  day10_shot5.wav   # 16-bit / 44.1kHz mono, -16 LUFS
  day10_vo_full.wav                      # 5 shots + 250 ms gaps, loudness-normed
  production.json                        # voice id, drive file ids, per-shot text
```

All six files upload (or replace by name) into the Day 10 creatives folder.

## Egress requirement

`api.elevenlabs.io` MUST be on the environment's network egress allowlist.
A blocked call returns `403 Host not in allowlist`. See the network settings
at https://code.claude.com/docs/en/claude-code-on-the-web. Without that fix
the script will fail on the first TTS request — there is no silent fallback
on purpose (brand consistency: Bella's voice or nothing).

## Design choices

- **`pcm_44100`** from ElevenLabs → we wrap raw PCM with stdlib `wave`. No
  decode step, no extra format risk when stitching.
- **`ffmpeg loudnorm`** at -16 LUFS / -1.5 dBTP / 11 LRA matches typical
  IG/TikTok loudness. If `ffmpeg` is missing the script keeps the raw WAV
  and prints a warning instead of failing the whole run.
- **Idempotent Drive upload** by filename inside the target folder, so
  re-runs (e.g. after a delivery tweak) overwrite cleanly without piling
  up `(1)`, `(2)` copies.
