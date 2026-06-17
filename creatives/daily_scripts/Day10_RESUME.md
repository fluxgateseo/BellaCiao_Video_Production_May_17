# RESUME — Day 10 reel build (voiced, 1080×1920 multi-shot)

> ## ✅ SHIPPED — 2026-06-17
> Final reel: **`creatives/daily_scripts/Day10_Jake_reel.mp4`** — 30.0s, 1080×1920,
> H.264/AAC, 6 shots, burned captions, warm grade.
> - **VO:** ElevenLabs voice `YtOuYjXDObEJdpOIyUu1`, model `eleven_multilingual_v2`
>   (6 lines in `Day10_vo_el/`). Bella narrates throughout; Jake does not speak.
> - **Lip-sync:** S1 + S6 via Higgsfield `wan2_7` (audio-driven), sources in
>   `Day10_lipsync/`. S6 needed audio padded to 3.0s (`s6_pad.mp3`) — wan2_7 rejects
>   sub-~2s audio tracks.
> - **B-roll:** S2–S5 from `Day10_broll/` (kling3_0), VO laid over, captions burned.
> - Placeholder Olivia VO (`Day10_vo_placeholder/`) deleted as superseded.
> - Caption (`day10_caption.txt`) unchanged — on-brand, zero-sell, DM CALL trigger.
> The remaining notes below are the historical build log.

**Status:** ✅ COMPLETE (was: mid-build, paused for ElevenLabs key + session restart).

## Goal
Rebuild Day 10 (Jake · Narrow Lane · `the_missed_call`) to the canonical
aesthetic (`creatives/AESTHETIC_REFERENCE.md`): 9:16 **1080×1920**, voiced,
lip-synced, multi-shot cinematic, held-up-phone device (missed calls, not
Google), Ciao at the turning point. ~31s.

## FINAL VOICE (owner decision)
ElevenLabs voice id **`YtOuYjXDObEJdpOIyUu1`**. Requires env secret
**`ELEVENLABS_API_KEY`** (was NOT set pre-restart — verify it's set now).
Model: `eleven_multilingual_v2`. This SUPERSEDES the Higgsfield "Olivia"
placeholder VO generated pre-restart.

## Shot plan + VO script (speaker: Bella)
| Shot | Visual (keyframe) | Dur | VO line |
|---|---|---|---|
| S1 | Bella + "9 missed calls" phone, to camera | 6.0s | "Nine calls rang out at Jake's before eleven on Saturday. Nine tables — gone." |
| S2 | Jake at espresso machine, phone ringing | 4.9s | "It's not the coffee. Nobody can pull a ristretto and answer the phone at 7:40." |
| S3 | The empty 11am table | 5.0s | "That eleven o'clock table didn't wait. They called the next place that picked up." |
| S4 | Ciao lifts his head (the turn) | 5.5s | "His dead Tuesdays? The bookings had been calling the whole time. Ringing out." |
| S5 | Jake's payoff, pouring a flat white | 6.9s | "Then every call got answered. First Saturday in three years Jake didn't dive for the phone." |
| S6 | Bella close | 2.3s | "I'm Bella — ciao for now." |

Caption (IG, zero-sell on camera): hook + **"DM me CALL and I'll send you 30s of
Bella answering a real restaurant phone."**

## Assets already created (persist server-side / in repo)

### Keyframes — in repo: `creatives/daily_scripts/Day10_keyframes/` (committed)
Also uploaded to Higgsfield as start_image media (ids):
- S1 `23f2f365-845d-485c-9a72-cb702c94ddf6` (Bella locked to bella_reference.png)
- S2 `bae31d39-44e2-41b1-ac26-6274354af91b`
- S3 `c584e865-4d16-49dc-a5aa-6dccdbffe748`
- S4 `01be228d-1943-4289-954b-09fa6bed20cd`
- S5 `28f3c383-3e9d-4a81-a8c7-5b1e14f55ae9`
- S6 `f77f85b8-13d8-4ba3-a253-e62289f278d0`

### Identity reference media (Higgsfield)
- bella_reference.png (accurate, use for Bella): `8ff35cc8-961b-4ad0-8fbc-1206355eb988`
- bella_face_crop.png: `a4b3de65-2e8e-478f-aa92-271962cd6fb2`
- ciao_ref: `4c61275d-1566-4c61-8699-0c7ddea28d13`

### B-roll motion clips — ALREADY RENDERING (kling3_0 pro, silent), job ids:
- S2 `f04c3946-145e-46ab-b033-0f5f9ee93766` (5s)
- S3 `7b2cab9c-8907-4540-a532-7422ebab81be` (5s)
- S4 `15e8541d-6a14-4e42-bc97-e7b335bc2f3a` (6s)
- S5 `ac1f685e-04ac-498d-aa65-4d0d169ed26d` (7s)
Fetch with job_display; download rawUrl. (Re-fetchable any time.)

### Placeholder Olivia VO (Higgsfield) — DISCARD, replaced by ElevenLabs
Audio job ids (wav): S1 `40f78577` S2 `28ada79d` S3 `cfc06155` S4 `9661e82d`
S5 `645e97a6` S6 `2434c516`. Saved in repo at `creatives/daily_scripts/Day10_vo_placeholder/`.

## Post-restart steps
1. `echo $ELEVENLABS_API_KEY | wc -c` → confirm set.
2. Generate ElevenLabs TTS for all 6 lines, voice `YtOuYjXDObEJdpOIyUu1`,
   model `eleven_multilingual_v2`, output mp3/wav → `/tmp/short/vo_el/s{1..6}`.
   `curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/YtOuYjXDObEJdpOIyUu1" -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d '{"text":"...","model_id":"eleven_multilingual_v2"}' -o sN.mp3`
3. Lip-sync the 2 Bella shots: upload s1 & s6 EL audio to Higgsfield (media_upload
   type audio → PUT → confirm), then `wan2_7` start_image=S1/S6 keyframe media,
   audio=EL audio, resolution 1080p, 9:16.
4. Fetch the 4 B-roll clips (job ids above).
5. Assemble (ffmpeg): order S1..S6; lay each shot's EL VO; scale+pad all to
   1080×1920; burn 2-line captions (white, lower third) from the VO; warm grade;
   H.264 + AAC; ~31s. Optional soft cafe ambience bed (low).
6. Write `creatives/daily_scripts/Day10_Jake_reel.mp4` (canonical final). Commit +
   push. Surface to user. Update CONTENT_CALENDAR Day 10 as shipped.

## Notes
- Jake does NOT speak (no cast voice yet). Bella narrates all. Jake-voice casting
  is a separate future decision.
- `job_display` was intermittently blocked by a job_status deny-rule; retry once
  if denied.
- Balance pre-restart: ~278 credits (ultimate).
