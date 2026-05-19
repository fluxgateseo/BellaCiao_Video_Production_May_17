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

The full review tree (folder IDs + all canonical clickable asset URLs) is
now mirrored into the repo at **`renders/REVIEW_DRIVE_INDEX.md`** — that is
the durable map; keep it in sync when finals change.

`Production Renders BellaCiao (REVIEW)` = `1iJnRjhESFdczPqYAftGXeEyRDi84ZbZH` (renamed 2026-05-19, ID stable)
- `Day 1 — Reel 01 (Myth-Buster: La Grotta)` `1KTPHzZZGCDw0ISWULECbHsMyBxWOIeZJ`
  → `Single Videos` `1TG1WKn1-VrKh2ZqiXUDWQCG9qOcQq5UE`,
    `Final Rendered Video` `1hw7-PfBF1Jn8jE2HszXCtsS7ZIKgv-fL`
- `Day 2 — Danny (The Copper Fox, Soho)` `1Xp71aojBshmm3_DCnoEmzKw4tUU1S7G_`
  → STORY/REEL keyframes, `Single Videos`, `Final Rendered Video`
    (canonical doc: "▶▶▶ Day 2 FINAL v4 — CANONICAL")

Canonical finals: Day 1 reel `e02a57f5…`; Day 2 **v4** REEL `acd57fbe…` +
STORY `180b5fc1…` (full URLs in `renders/REVIEW_DRIVE_INDEX.md` and
`renders/ledger.json`). `.mp4`/`.png` binaries are NOT in Drive/git
(web-env Drive tool takes one inline base64 string per call, no
resumable/multipart; 17–45 MB finals untransportable — confirmed at schema
level). To land them in Drive run `scripts/push_renders_to_drive.sh` on a
host with rclone/Drive auth. See `renders/ledger.json` `driveUploadBlocker`.

## Publishing (audited 2026-05-19)

Publishing is a SEPARATE Drive project `Bellaciao Publisher` (legacy
`video_pipeline`): IG via Meta Graph (`Scripts/upload_instagram_reel.py`),
YT via YouTube Data API (`Scripts/upload_youtube.py`), driven by
`publish_metadata.md`. NOT runnable from this env (no MCP publish
connector; creds in Publisher `.env`). Known gap: Meta App may lack
`instagram_content_publish`. Day 1/Day 2 CloudFront URLs are already
public and satisfy the scripts' hosting input (R2 not required). Full
audit in `renders/REVIEW_DRIVE_INDEX.md`.

## QUALITY NOTES FOR FUTURE SESSIONS (user feedback, 2026-05-18)

- **Never tell Kling to "speak faster to fit the duration."** It compresses
  VO and the delivery sounds unnaturally fast/accelerated (hit on Day 2
  STORY shots 4 & 5). Instead: allocate generous shot durations for any
  dialogue line, and prompt "natural unhurried pace, do NOT speed up
  speech." If a rushed take slips through, time-stretch that shot
  (video+audio together, e.g. setpts*1.30 / atempo 0.769) — keeps lip-sync,
  costs no credits.
- **Ciao (Italian Greyhound) scale drift:** in several Day 2 frames Ciao
  rendered too small / wrong proportions. Future: add explicit scale
  anchors ("medium-small sighthound, ~knee-to-mid-thigh height of a
  standing adult, elegant elongated whippet-like body, NOT toy/teacup
  size"), and ideally onboard a real Ciao reference image so identity +
  size lock. Day 2 kept as-is per user.
- **Single-subject guard:** Bella keyframes occasionally spawned a
  duplicate Bella (two women, one at frame bottom — Day 2 REEL S7).
  Always include negative: "exactly one woman, no second woman, no
  duplicate/twin/clone, no extra person in the lower foreground."

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
