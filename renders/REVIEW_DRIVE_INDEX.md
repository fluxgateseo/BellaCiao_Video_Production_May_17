# BellaCiao — Production Renders (REVIEW) — Drive Index

This file mirrors the Google Drive review folder **"Production Renders
BellaCiao (REVIEW)"** (renamed 2026-05-19; folder ID unchanged) into the repo. The `.mp4`/`.png` binaries are NOT in git
or in Drive (in-env Drive tool only accepts inline content; see
`renders/ledger.json` `driveUploadBlocker`). Binaries live on Higgsfield
CloudFront; this index is the durable map. Owner: `fluxgateseo@gmail.com`.

Last synced: 2026-05-19.

## Drive tree (folder IDs)

```
Production Renders BellaCiao (REVIEW)     1iJnRjhESFdczPqYAftGXeEyRDi84ZbZH
├── READ ME — Review Structure (Doc)      18I5pLSFj6AJxUHURtQVGdjD2lqoIYbDPeerEKzyl8TE
├── Day 1 — Reel 01 (Myth-Buster: La Grotta)   1KTPHzZZGCDw0ISWULECbHsMyBxWOIeZJ
│   ├── Single Videos (per-shot)          1TG1WKn1-VrKh2ZqiXUDWQCG9qOcQq5UE
│   └── Final Rendered Video              1hw7-PfBF1Jn8jE2HszXCtsS7ZIKgv-fL
└── Day 2 — Danny (The Copper Fox, Soho)  1Xp71aojBshmm3_DCnoEmzKw4tUU1S7G_
    ├── STORY — Keyframes (5 shots)        1ljnsOdIATpGa1kd8MzH44ZG2xNFl9fMF
    ├── REEL — Keyframes (7 shots)         1G3rjCybx8O7ms6pXpC4vlAkxkG3dl3m3
    ├── Single Videos (per-shot)           10OuEHeqrw3BxNBOV7_QOa8521q1glih2
    └── Final Rendered Video               1UilivuQlt025HgyOx5nD8w0ywb_kTbAY
```

## Binary upload status

The `.mp4` finals are NOT yet in Drive. The web env's Drive tool only takes
one inline base64 string per call (no resumable/multipart); the finals are
17–45 MB each — untransportable from here. Run
`scripts/push_renders_to_drive.sh` on a host with rclone/Drive auth to land
them into the folder IDs below; then move entries from `renders/ledger.json`
into `manifest.json`.

## Canonical deliverables (use these)

### Day 1 — Reel 01 "La Grotta Myth-Buster"
- FINAL (58.2s, 1080x1920), publish-ready, verified HTTP 200:
  `https://d2ol7oe51mr4n9.cloudfront.net/user_3BMADca9yJuLURp1EycoawQ25PG/e02a57f5-9871-4788-88a6-66f52d45e811.mp4`
- Audio = model-generated ambient/narrator (not final brand VO).
- Per-shot links: `renders/ledger.json` → `day1_reel_shots_2_9`.

### Day 2 — "The Copper Fox" (Danny). Two reels.
- **REEL v4 (CANONICAL)** ~44s — opens on Bella; Shot 4 phone flat; Shot 7
  single Bella + full natural sign-off:
  `https://d2ol7oe51mr4n9.cloudfront.net/user_3BMADca9yJuLURp1EycoawQ25PG/acd57fbe-adee-4c32-8d1c-6463758b76e5.mp4`
- **STORY v4 (CANONICAL, 2nd reel)** ~28s — order S2→S3→S4→S5 (establishing
  shot dropped), Bella shots at natural pace:
  `https://d2ol7oe51mr4n9.cloudfront.net/user_3BMADca9yJuLURp1EycoawQ25PG/180b5fc1-cd03-4156-9266-ef869ed5c948.mp4`
- Superseded v1/v3 + 12 per-shot + 24 keyframe links: `renders/ledger.json`
  → `day2_danny_copperfox_keyframes` (keyframes + videoStage + finals).

## Publishing connector audit (2026-05-19)

Publishing lives in the **`Bellaciao Publisher`** Drive project (legacy
`video_pipeline`), NOT in this repo and NOT as MCP connectors here.
- Instagram: Meta Graph API via `Scripts/upload_instagram_reel.py`
  (agent `03_instagram-agent.md`). Needs Meta App perms
  `instagram_content_publish`, `instagram_basic`, `pages_read_engagement`,
  `pages_show_list`; FB Page→IG Business link; Page token; public MP4 URL.
- YouTube: YouTube Data API via `Scripts/upload_youtube.py`
  (agent `04_youtube-agent.md`).
- Driven by `publish_metadata.md`; creds in Publisher `.env` /
  `_credentials/` (not read).
- Known blocker (`TOMORROW.md`/`PLAN.md`): Meta App missing
  `instagram_content_publish` — verify in Meta Developer Portal.
- R2 staging: Cloudflare MCP here exposes bucket CRUD only (no object
  upload). Not required anyway — the CloudFront URLs above are already
  public and satisfy the IG/YouTube scripts' hosting input.
- This Claude environment cannot run the Publisher scripts or post to
  IG/YouTube; that must run where the Publisher `.env` lives.
