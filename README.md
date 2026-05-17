# BellaCiao Video Production (May 17)

Higgsfield-based image + video pipeline for the BellaCiao universe (Bella, Ciao,
and the eleven friends across AU / US / UK markets).

## Architecture

- **GitHub = source of truth for all textual files** (scripts, prompts,
  schemas, config, character registry).
- **Google Drive (account `fluxgate`) = all binaries** (reference images,
  keyframes, renders, audio). Binaries are **never** committed — `.gitignore`
  blocks every binary extension.
- **`manifest.json`** maps every Drive binary file ID → the commit that
  produced it. Drive files are always referenced **by ID, never by path**.
- Plan before scaffolding; **confirm before any destructive or
  Drive-structural change**.

## Engine: Higgsfield (fresh — no Kling/Runway lock)

This is a clean Higgsfield pipeline. The legacy Runway `gen4_image` `@tag` /
3-reference-cap rules and the Kling `CFG` / `MICRO-MOVE` block are **not**
inherited. The re-derived Higgsfield equivalents (Soul `custom_reference_id`
identity lock, `custom_reference_strength` / `style_strength`, Cinema Studio /
`dop` `motion_strength`, no native negative-prompt field) are documented in
[`config/defaults.json`](config/defaults.json) and
[`characters/shared.md`](characters/shared.md).

## Storyboard approval gate

Per content item: generate **script + scene prompts + still keyframe(s)**
(`start.png` / `end.png`). The user manually approves the storyboard. **No
video-generation call is made until the item's status is
`storyboard_approved`.** Nothing spends video-generation budget without
explicit manual approval.

## Repo map

| Path | Purpose |
|---|---|
| `manifest.json` | Drive file ID → producing commit |
| `schemas/` | JSON Schemas for manifest / content-item / config |
| `config/defaults.json` | Higgsfield engine parameters + Kling→Higgsfield mapping |
| `config/drive-folders.json` | Drive folder IDs (root / renders / source-assets / scratch) |
| `characters/registry.json` | Per-character identity + wardrobe locks + Drive ref IDs |
| `characters/shared.md` | Verbatim Shared DNA / Negatives / colour grade / frame conventions |
| `content-queue/queue.json` | Content items moving through the approval gate |
| `prompts/` | Prompt templates |
| `scripts/validate.mjs` | Dependency-free CI integrity check |
| `.github/workflows/validate.yml` | CI |

## Drive folders (account `fluxgate`, do not recreate)

| Folder | ID |
|---|---|
| Project root `Claude/BellaCiao_Video_Production_May_17/` | `1oyYhk9_zAEUgNa9QQ3qa_4hc9OFjy8xT` |
| `renders/` | `16HfGJ-VM7O-vW42aTHSljhbDUpZh4l-C` |
| `source-assets/` | `1tVmZX5bkDGIDsY8MfZ15J4ocbVc-w8B5` |
| `scratch/` | `1NB2QcJbYcdwnQRW3RmTbqzx8VE32XzTU` |

## Validation

```
node scripts/validate.mjs
```

Checks all JSON parses, the manifest/registry/queue/config invariants, and that
no binary files are tracked in git.
