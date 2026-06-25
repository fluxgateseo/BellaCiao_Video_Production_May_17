> **⚠ RETIRED — do not run.** This handoff was authored under the now-superseded
> SEO/Google-Business-Profile premise (Bella as on-camera host pitching a fix for
> "no Reserve button"). The Bella Ciao v2 canon (`BellaCiao_Master_Bible_v2.md`,
> conflict log §17 #1) retires that framing. The destination Drive folder named
> below also belongs to a separate project (`destinybydao` — the "Day 10" sage
> video about the Five Element Generation Cycle) and is NOT the Bella Ciao Day 10
> output. See `RESUME.md` for the live state and the actual Day 10 angle
> (Jake / Narrow Lane / Pillar A `the_missed_call`).
>
> Kept here as a reference for what NOT to ship.

---

# Day 10 Redo — ElevenLabs Voiceover (Session Handoff)

This is a handoff for a **fresh Claude Code web session**. The previous session
could not reach ElevenLabs (see Blockers) so no audio was produced yet. Everything
needed to finish is captured below.

## Goal

Redo **Day 10 — "Bistrot Maison" (No Table to Book)** using the new ElevenLabs
features (Eleven v3 expressive TTS / audio tags). Previously this episode used
Kling 3.0 pro native "sound on". We are replacing/adding an ElevenLabs voiceover.

## Blockers that MUST be cleared before starting the new session

1. **Network egress** — `api.elevenlabs.io` is NOT in the environment's egress
   allowlist. Calls return `403 Host not in allowlist`. Add `api.elevenlabs.io`
   in the environment's network settings.
   Docs: https://code.claude.com/docs/en/claude-code-on-the-web
2. **MCP connector** — The ElevenLabs MCP connector must be installed AND the
   session restarted so its tools register. A running session does not pick up a
   newly-installed connector mid-flight.
3. **API key** — `ELEVENLABS_API_KEY` is already present in the environment.
   (Direct REST calls work once egress #1 is open, even without the MCP connector.)

You only strictly need **(1) + (3)** for the REST path, or **(1) + (2)** for the
MCP path. Either works.

## Branch

Develop on: `claude/nifty-wozniak-83k8ed`

## Source assets (Google Drive)

- Script doc: `Day 10 — Bistrot Maison — SCRIPT FOR REVIEW`
  - id: `1FQBGnObkN4GO71DbhKSE-B2hokfYyoXi0DsHwEHo_3g`
- Day 10 creatives folder (output destination):
  - id: `1DpqBx2dUZP9ZA3W9Kfk2HXmY9_t6MaNE`
- Bella reference image (topknot): `Dao_reference_topknot_day_10.png`
  - id: `1rvcKigdEFuSw_7ILhA9k22zTWI3CaXvU`

## The 5 Bella VO lines (spoken line = burned caption)

1. Shot 1 (HOOK): "This London bistro is fully booked tonight, yet Google has no way to book it."
2. Shot 2 (PROBLEM): "Their profile shows a phone number but no Reserve button at all."
3. Shot 3 (CONSEQUENCE): "New diners glance, see no link, then quietly tap somewhere easier."
4. Shot 4 (FIX): "One change: connect your booking platform so a Reserve button appears."
5. Shot 5 (PAYOFF): "Now tables fill straight from the listing — go add yours today."

Speaker: **Bella** (host, front-facing, hair down) for all 5 lines.

## Production plan

1. Generate each line with **Eleven v3** (`eleven_v3`), using light audio tags for
   delivery (e.g. confident, warm; a brief `[sighs]`/concern beat on Shot 3,
   upbeat CTA on Shot 5). Keep tags subtle — these are 6s shots.
2. Output: one WAV per shot (`day10_shot1.wav` … `day10_shot5.wav`) + a stitched
   `day10_vo_full.wav`. Normalize loudness.
3. Upload audio to the Day 10 creatives Drive folder (id above).
4. Commit a reproducible production script (see below) to the branch.

## OPEN DECISIONS (confirm with user before generating)

- **Bella voice**: Is there an established ElevenLabs voice_id for Bella? If not,
  pick a female English voice or design/clone one. Brand consistency matters —
  do not guess silently.
- **Scope**: VO only, OR also re-render the 5 Kling pro shots to sync to the new
  VO (spends Higgsfield credits; per the script doc a full render needs an
  explicit "approve day10").

## REST reference (once egress is open)

```bash
# List models / confirm v3 access
curl -s -H "xi-api-key: $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/models

# List voices (find Bella's voice_id)
curl -s -H "xi-api-key: $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/voices

# Text-to-speech for one line
curl -s -X POST \
  "https://api.elevenlabs.io/v1/text-to-speech/<VOICE_ID>" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"This London bistro is fully booked tonight, yet Google has no way to book it.","model_id":"eleven_v3"}' \
  --output day10_shot1.mp3
```

## Production standards (from the script doc, applied on any re-render)

- Kling 3.0 pro, all 5 shots rendered together for voice consistency
- Bella front-facing, hair DOWN, from reference photo
- Ciao = canonical element `9d7e6cea` (Ciao-1) in shots 3 & 5
- Trimmed lead-ins; 0.4s dissolves + audio cross-fades; loudness normalized
- Captions = the spoken dialogue, timed per shot, per-shot placement (heroes
  lower, wides top) so they never cover Bella's face or Ciao

---

## Session 2 status (2026-06-17)

**Resolved decisions (from user):**
- Bella voice id: `YtOuYjXDObEJdpOIyUu1`
- Scope: **VO only** — do not re-render Kling shots in this pass.

**Done this session:**
- Reproducible production script committed:
  - `scripts/audio/day10_elevenlabs_vo.py` (gen → stitch → loudnorm → Drive upload)
  - `scripts/audio/requirements.txt`
  - `scripts/audio/README.md`
- TTS texts in the script use subtle Eleven v3 audio tags per the brief
  (`[confident]` shot 1, `[sighs]` shot 3 concern beat, `[warm]` shot 4 turn,
  `[excited]` shot 5 CTA). Captions stay verbatim with the spec — tags affect
  delivery only.

**Still blocked:**
- Egress to `api.elevenlabs.io` still returns `403 Host not in allowlist` in
  this environment. Audio was NOT generated, stitched, or uploaded to Drive in
  this session. Open the egress (or attach the ElevenLabs MCP connector and
  restart) and re-run `python scripts/audio/day10_elevenlabs_vo.py` from a
  shell that has `ELEVENLABS_API_KEY` and `GDRIVE_SA_KEY_FILE` set — the
  artifacts will drop into `out/day10/` and into Drive folder
  `1DpqBx2dUZP9ZA3W9Kfk2HXmY9_t6MaNE` in one pass.

---

## Session 3 status (2026-06-25) — RETIRED

This handoff was identified as off-canon when the v2 premise pivot was applied.
See top-of-file notice and `RESUME.md`. Day 10 will be re-done from scratch under
the Jake / Narrow Lane / `the_missed_call` angle per `CONTENT_CALENDAR_June.md`.
