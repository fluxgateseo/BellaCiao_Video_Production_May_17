# Session Handoff — 2026-05-18

Branch: `claude/resume-project-VYWgC`

## State: Day 1 / Reel 01 (La Grotta Myth-Buster) — FINAL rendered

- Final reel: `day1_reel_FINAL.mp4` — 58.2s, 1080x1920, 45.5MB. Built locally
  via ffmpeg: Shot 1 locked (`c031855f`) + Veo 3.1 voiced Shots 2–9, with a
  Maria identity-fix pass on S4/S7/S8/S9 (jobs ae09f2f9 / 5340437a /
  8c0082ee / c8ae9ee4).
- **Watchable FINAL link (verified HTTP 200):**
  `https://d2ol7oe51mr4n9.cloudfront.net/user_3BMADca9yJuLURp1EycoawQ25PG/e02a57f5-9871-4788-88a6-66f52d45e811.mp4`
  Uploaded via video-MCP `media_upload`/`media_confirm` (media_id
  `e02a57f5-9871-4788-88a6-66f52d45e811`). Recorded in
  `renders/ledger.json` under `day1_reel_shots_2_9.sourceUrls`.
- Per-shot CloudFront links: see `renders/ledger.json` `sourceUrls` and the
  Drive review folder below.

## Drive review structure (account fluxgateseo)

`BellaCiao — Production Renders (REVIEW)` (folder `1iJnRjhESFdczPqYAftGXeEyRDi84ZbZH`)
- `Day 1 — Reel 01 (...)`
  - `Single Videos (per-shot)` — clickable per-shot index docs
  - `Final Rendered Video` — `▶ Day 1 — FINAL Reel (CLICKABLE LINK)`

Note: earlier plain-text Drive docs rendered URLs as non-clickable text;
HTML-sourced docs were added with real hyperlinks. The `.mp4` binaries are
NOT in Drive (in-env Drive tool only accepts inline content; no
service-account creds). See `renders/ledger.json` `driveUploadBlocker`.

## STANDING RULE (user, 2026-05-18) — applies to ALL future days

- Produce **ONE short/reel per day only** — NOT a video + a story. One
  9:16 reel per day going forward.
- Day 2 exception: the Day 2 STORY is being rendered as a second reel
  video (this day only, since both scripts already existed).
- Video model default: **Kling 3.0 std** (2 cr/s) — script-native and
  ~4.5x cheaper than Seedance 2.0 1080p (9 cr/s). Use Kling unless told
  otherwise.
- Bella is the lead/narrator and must carry every reel (on-camera at
  anchor + mandatory "I'm Bella — ciao for now" sign-off). Script-faithful
  structure approved (she is not forced into every single shot).

## Day 2 (Danny / The Copper Fox, Soho) — keyframes DONE

- Source: April "Day 2 test" tree `full scripts` (user-chosen). It's ONE
  Story (`bella_danny_p2_20260418_2323`, 5 shots) + ONE Reel
  (`bella_danny_p2_20260418_2355`, 7 shots) = 12 shots.
- **All 24 start/end keyframes generated** — Nano Banana Pro (`nano_banana_2`)
  2K 9:16. Bella locked via ref `3dad09f7`; Danny/Ciao via script
  descriptors (refs un-onboardable in-env). 48 cr spent, balance 167.4.
- URLs + Drive review folder recorded in `renders/ledger.json`
  (`day2_danny_copperfox_keyframes`). Drive: review root >
  "Day 2 — Danny (The Copper Fox, Soho)" `1Xp71aojBshmm3_DCnoEmzKw4tUU1S7G_`
  with clickable STORY/REEL keyframe HTML indexes.
- **Video stage NOT done — blocked on credits.** 12 Seedance 2.0 1080p
  shots ≈ 700–900 cr single-pass; only 167.4 available. The 2,146-credit
  Flux dashboard account is a DIFFERENT identity than this MCP connector
  (private workspace `5e2a6273`); reconnect never took effect.

## Constraints learned this session

- Drive MCP `create_file`: inline content only — cannot upload multi-MB video.
- Cloudflare MCP: bucket management only — no R2 object upload; no S3/CLI
  creds in env. R2 path is a dead end for binaries here.
- Working binary-hosting path: video-MCP `media_upload` → `media_confirm`
  → public CloudFront URL on `d2ol7oe51mr4n9.cloudfront.net`.

## Open / next

- **Pending (interrupted, not started):** user uploaded
  `elitepipelineworkflowmain.zip` and asked to "read and update the
  dashboard" — not yet read or actioned.
- Downstream polish (not done): brand voice swap Kling
  `commercial_lady_en_f-v1` (current audio = Veo narrator stand-in);
  CapCut overlays "Not the food." / "It's Google."
- Photo-exact Maria/Enzo identity lock pending Drive serving the 30MB
  Enzo&Maria reference (Drive MCP drops the large download).
- Persist renders to Drive when a real upload path exists; then migrate
  ledger entries to `manifest.json` artifacts.
