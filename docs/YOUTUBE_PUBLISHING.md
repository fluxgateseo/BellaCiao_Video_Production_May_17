# YouTube publishing routine (`publishers/`)

Direct YouTube (Shorts) publishing with **native scheduling** — no third-party
scheduler. A video is uploaded once as `private` with a future `publishAt`, and
YouTube releases it publicly itself at that time.

## One-time setup
1. **Google Cloud project** → enable **YouTube Data API v3**.
2. Create an **OAuth client** of type **Desktop app**. Note its client ID + secret.
3. **Mint a refresh token** (run locally, needs a browser; sign in as the Bella
   channel owner):
   ```bash
   pip install -r requirements.txt
   YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... python -m publishers.youtube_auth
   # or: python -m publishers.youtube_auth --client-secret client_secret.json
   ```
   It prints `YOUTUBE_REFRESH_TOKEN`.
4. **Set three env secrets** (in this environment's settings, or a local
   `publishers/.env` — both are gitignored): `YOUTUBE_CLIENT_ID`,
   `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
5. **Network policy:** allow outbound to Google APIs
   (`oauth2.googleapis.com`, `youtube.googleapis.com`, `www.googleapis.com`).

## Publish one video
```bash
python -m publishers.youtube_publisher upload \
  --video renders/day10_jake.mp4 \
  --title "Nine calls. Zero tables. #Shorts" \
  --description-file creatives/daily_scripts/day10_caption.txt \
  --tags bella,bellaciao,fitzroy \
  --thumbnail creatives/daily_scripts/Day10_Jake_cover.png \
  --publish-at 2026-06-15T09:00:00+10:00
```
Omit `--publish-at` to go public immediately.

## The scheduling routine (queue)
1. Copy `data/publish_queue.example.json` → `data/publish_queue.json` (gitignored).
2. Add an entry per post (media path, title, caption, tags, `publish_at`).
3. Run the routine whenever new content is queued (or on a cron):
   ```bash
   python -m publishers.publish_queue run            # uploads all pending
   python -m publishers.publish_queue run --dry-run  # preview
   python -m publishers.publish_queue list           # show queue + statuses
   ```
   Because YouTube schedules natively, you do NOT need this running at each
   post's go-live time — uploading with a future `publish_at` is enough.

## Notes / limits
- A Short = vertical video, ≤ 60s, with `#Shorts` in the title or description.
- Title ≤ 100 chars (enforced).
- Uploads require OAuth (an API key cannot upload). Daily quota applies; a video
  insert costs ~1600 quota units, so the default 10k/day quota ≈ a handful of
  uploads/day — request more in Google Cloud if needed.
- IG/TikTok publishers are not built yet; this package is structured to add them
  as sibling modules under `publishers/`.
