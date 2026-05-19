#!/usr/bin/env bash
# Push the canonical BellaCiao render finals from Higgsfield CloudFront into
# the Drive "BellaCiao — Production Renders (REVIEW)" tree.
#
# WHY THIS SCRIPT EXISTS:
#   The Claude web environment's Drive tool only accepts a file as one inline
#   base64 string per call (no resumable/multipart upload). The finals are
#   17-45 MB each, far over any tool-call payload limit, so they cannot be
#   uploaded from inside that environment. Run this on a machine that has
#   Drive auth (rclone remote, or swap in `gdrive`/Drive API).
#
# PREREQ: rclone configured with a remote that can write to the target Drive
#   account (fluxgateseo@gmail.com). Set RCLONE_REMOTE below (e.g. "gdrive:").
#   rclone supports upload straight to a folder ID via --drive-root-folder-id.
set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:}"
CDN="https://d2ol7oe51mr4n9.cloudfront.net/user_3BMADca9yJuLURp1EycoawQ25PG"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# file_basename | drive_folder_id | destination filename
MAP=(
  "e02a57f5-9871-4788-88a6-66f52d45e811.mp4|1hw7-PfBF1Jn8jE2HszXCtsS7ZIKgv-fL|Day1_Reel01_LaGrotta_FINAL.mp4"
  "acd57fbe-adee-4c32-8d1c-6463758b76e5.mp4|1UilivuQlt025HgyOx5nD8w0ywb_kTbAY|Day2_CopperFox_REEL_v4_CANONICAL.mp4"
  "180b5fc1-cd03-4156-9266-ef869ed5c948.mp4|1UilivuQlt025HgyOx5nD8w0ywb_kTbAY|Day2_CopperFox_STORY_v4_CANONICAL.mp4"
)

for row in "${MAP[@]}"; do
  IFS='|' read -r src folder dest <<<"$row"
  echo ">>> $dest"
  curl -fSL --retry 4 -o "$TMP/$dest" "$CDN/$src"
  rclone copyto "$TMP/$dest" "${RCLONE_REMOTE}$dest" \
    --drive-root-folder-id "$folder" --progress
done

echo "Done. Verify in Drive, then move uploaded entries from"
echo "renders/ledger.json into manifest.json artifacts[] with real driveFileId."
