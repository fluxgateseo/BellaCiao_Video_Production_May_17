# Reference Library — canonical character images

**RULE (non-negotiable):** Look at the reference image **every time** you create
a frame. No frame ships without a canonical reference pulled from this library.
The only acceptable exceptions are explicit `subject: scene` shots (no
character on camera) — the Shot Director already infers this in
`shot_director.py::_infer_subject`.

Authoritative folder in Drive: `Creatives/`
(`id=1qpMlKgDDUvNv52GvQwsAGfH8C4TRyaNT`, owner fluxgateseo@gmail.com).

This file is the **single source of truth** the pipeline and any Claude session
should consult before any image / video generation. Treat the Drive IDs below
as **identity locks** — never substitute, never paraphrase, never regenerate
without the owner's explicit approval.

---

## 1 · How frames must reference these assets

### For Bella (preferred)
She has a **trained Higgsfield Soul 2.0 character**. Use it.

```
generate_image(
  model = "soul_2",
  soul_id = "eeb60f04-a2f5-4a3d-b8d0-88fafca6d8d2",
  prompt = "<your prompt>",
  enhance_prompt = false   # literal prompt preserved per VERIFIED 2026-05-17 job 7f570a35
)
```

The trained character was anchored to `bella_face_crop.png` and trained from a
5-image identity-consistent set (jobs `dd20b0f3`, `54bba9b3`, `20ea10ea`,
`08985c3b`, `39585e50` — nano_banana_2 keyframes).

If `soul_2` is unavailable for a given shot, fall back to:

```
media_import_url(url=<bella_face_crop public URL>)  →  media_id
generate_image(
  model = "nano_banana_2",
  medias = [{ "type": "image", "value": "<media_id>", "role": "identity" }],
  prompt = "<your prompt>"
)
```

`nano_banana_2` remains the **primary keyframe engine** per
`characters/registry.json` in the v1 monorepo.

### For friends, Ciao, and bench characters
No trained Soul characters yet. Always pass the canonical reference PNG:

```
media_import_url(url=<friend_reference public URL>)  →  media_id
generate_image(
  prompt = "<your prompt> — character should match this identity reference",
  medias = [{ "type": "image", "value": "<media_id>", "role": "identity" }]
)
```

Never describe a character's face in words alone. The reference image carries
the identity lock; the prompt carries the moment.

### For Linh and Kostas (NOT YET GENERATED)
**Do not generate any frame featuring Linh or Kostas** until their reference
PNGs are produced and approved. The procedure is in
`HANDOFF_Friends_to_ClaudeCode.md` Task 4:

1. Generate `Linh_close_face.png` (Higgsfield, no model spec — let the MCP choose).
2. Pass that PNG back as the identity reference to generate `Linh_reference.png`.
3. Same sequence for `Kostas_close_face.png` → `Kostas_reference.png`.
4. Visual check against the physical lock in `Avatar_Prompts_Linh_Kostas.md`.
5. Once approved, add the four file IDs to **§3 Friends** below.

---

## 2 · Bella — canonical refs

| Asset | Drive ID | Bytes | Role |
| --- | --- | --- | --- |
| `bella_face_crop.png` | `1Gb36lnd44tqY_XyTg4ioWkcjOiQeIn3S` | 1,043,914 | **PRIMARY** — anchor used to train Soul 2.0 character |
| `bella_face.png` | `1lov6FQOXGMmL4E6kGqffUNdKXL3buK_B` | 1,105,431 | Face detail reference |
| `bella_reference.png` | `1fXbXSCtJzaM3ZlOJGCR20BeVy7GGMhe9` | 232,420 | Cross-shot continuity (note: file is `image/webp` despite `.png` extension) |
| `BELLA_CHARACTER_PROFILE.md` | `1AWaaWL3yyrC1XxTAwG6jeTA6e9V_xDeC` | 32,016 | Identity / behaviour / emotional-state dictionary — read this before writing any Bella shot prompt |

**Higgsfield Soul 2.0:** `soul_id = eeb60f04-a2f5-4a3d-b8d0-88fafca6d8d2`
(model `soul_2`). VERIFIED 2026-05-17 job `7f570a35` — strong reusable identity,
half-smile lock respected. CAVEAT: leaks some background negatives
(neon/exterior) — re-roll any clip where that bleeds through.

**Identity lock (per v1 `characters/registry.json`):** 25, Italian-American
(Italian father, Irish mother), NYC-born, Melbourne home base, London third.
Dark-brown hair centre-parted, long & loosely waved, SUBTLE warm highlights
(NOT blonde, NOT heavy balayage), flyaway at temple. Bright clear cornflower-
BLUE eyes with darker iris ring (NOT hazel/green/brown/grey). Warm olive
skin, visible pores, slight asymmetry. NO FRECKLES. Small subtle gold hoop
earrings (NOT studs). Default: relaxed face, soft half-smile at rest, eyes
smiling before mouth; full open-mouth smile EARNED only.

**Camera Address Mandate:** Bella always looks directly into the lens, eyes
locked, head square to camera. Off-camera/averted gaze = hard re-roll.

**Sign-off:** "I'm Bella — ciao for now." (always)

---

## 3 · Friends, Ciao, bench

All references live in `Creatives/Bella's Friends avatar/`
(`id=1zNr43aNwSA8bBv27em17e7j6e_QCdB43`).

### Active roster (v2)

| Character | Drive ID | Bytes | v2 status | Notes |
| --- | --- | --- | --- | --- |
| Ciao | `1nveroVLIeMQQyJqdfpYeMwd-pCisy8cY` | 28,868,394 | **Herald** — appears at turning point ONCE per video | Italian Greyhound — sleek, fast, dramatic. Never decoration. |
| Jake | `1gyU30QXy85JywQaX5Pb159kElcDff1CG` | 31,139,705 | Active AU | Melbourne · Fitzroy · Narrow Lane (brunch) |
| Naomi | `16IgCS1Ep0vNUz500v1KMeNcH1b4BzIqL` | 26,768,728 | Active INT | New York · Chelsea · The Blue Cove (seafood) |
| Sal | `1Ay77TINt0E-yfMGXCc49-1FXF6Uwv-5N` | 30,936,787 | Active INT | New York · West Village · Casanova's (Italian) |
| Sophie | `1HjTswTs1KZLndOS4IbM2RIVpFuZpxm1v` | 29,874,070 | Active AU | Melbourne · South Yarra · Wren (fine dining) |
| Mei | `1PAPVMCy70yOhyY0x6s7vcrAoYtBzVaA2` | 30,534,204 | Active AU | Melbourne · Chinatown · Golden Plum (Cantonese) |
| Enzo & Maria | `1bYW9owTZuGUde5S6z65E0sq4H6PniXG4` | 30,644,667 | Active AU | Melbourne · Carlton · La Grotta (Italian) — couple = ONE friend unit |
| Yasmin | `15GyZtcI3A0kUPvkXsvlPN86Gi6e4JP2i` | 38,161,480 | Active INT | London · Notting Hill · Cedar Table (Lebanese) |
| Danny | `1yC-vDdHIEmki85tXMW8uNihMzdy6EfR4` | 29,478,694 | Active INT | London · Soho · The Copper Fox (gastropub) |
| **Linh** | — | — | Active AU | **REFERENCE PNGs DO NOT YET EXIST.** Sydney · Marrickville · Sông (Vietnamese). Generate per §1 before any frame. |
| **Kostas** | — | — | Active AU | **REFERENCE PNGs DO NOT YET EXIST.** Adelaide · Norwood · Thea (Greek taverna). Generate per §1 before any frame. |

### Bench (return for US/UK launch)

| Character | Drive ID | Bytes | Notes |
| --- | --- | --- | --- |
| Ha-eun | `1ZrBNVCoa3zJX9-5isKc66ET_8QsmhMDC` | 29,939,492 | NYC. Per v1 `friends_db.json` she's "Los Angeles" — that's a stale data correction; she's NYC per the v2 canon. |
| Arun | `1ugAUv3U5MW08q0WkyVWciSmFKqW8uhrU` | 35,795,152 | London. Couples-unit with Priya. |
| Priya | `1cAiNoqtNiuwwvD-ePDQ0TUmGBGv4rgOf` | 30,583,974 | London. Couples-unit with Arun. |

---

## 4 · Orphans — references exist but character is not in v2 cast

⚠️ **Decision needed from the owner.** These three reference images exist in
the Drive folder but are not in the v2 Master Bible §7 cast list. Holding them
in `legacy_pending_review` in `data/friends_db.json::roster` until you tell me
to delete, bench, or restore.

| Character | Drive ID | Bytes | Current status |
| --- | --- | --- | --- |
| Tunde | `1LFixdw9qmvXlVusTLlzZt4wQ0IYpBvtV` | 34,297,991 | Still in `friends_db.json::friends` (legacy v1 entry). Parked in `roster.legacy_pending_review`. |
| Frank | `1Pf2T9a4flG6_wcJ2n8wvvtdrOeRsStBL` | 30,174,897 | NOT in `friends_db.json`. Asset has no profile. |
| Diane | `1egCm2eCCSwJ6hvxZjn7bgljdECB-GQP1` | 29,063,997 | NOT in `friends_db.json`. Asset has no profile. |

**Until decided:** do not feature these three in any new frame. The reference
PNGs exist as historical assets only.

---

## 5 · Explicit DO-NOT-USE folders

These subfolders are flagged "do not use" by the owner. Never pull a reference
from inside them.

- `Creatives/Bella's Friends avatar/Old references (do not use)/` (`id=1Is61xuuZBMZgZQOgo1Yanhrc61fNN6LH`)
- `Creatives/Bella_pictures_avatar/Old reference (do not use)/` (`id=1bCsWI5CVH26CV9uyY-JofP8svxnhJ5f6`)

---

## 6 · Workflow — what happens before any `generate_image` / `generate_video` call

1. **Identify the subject** of the frame (Bella / friend / Ciao / scene-only).
2. **Look up the canonical ref** in this file. If the character is in §4
   (orphan) or has no ref in §3 (Linh, Kostas), STOP — refuse to generate
   until the owner approves a path.
3. **Pull the reference into Higgsfield context** via `media_import_url` →
   `media_id`, OR use `soul_id` for Bella.
4. **Write the prompt** referring to the moment, the lighting, the action —
   never describing identity in words alone.
5. **Pass the ref** in `params.medias[].value` (file IDs) or `params.soul_id`
   (Bella).
6. **Verify before shipping** — does the output match the identity lock in
   §2 / §3? If not, re-roll. Do not accept "close enough."

The Shot Director (`shot_director.py`) and Image Prompt Builder
(`pipeline_v3/image_prompt_builder.py`) already pull avatar references from
`assets.py::avatar_bundle()`. After this commit lands, those modules' lookup
needs to resolve against the IDs in this file — track in a follow-up.

---

## 7 · Maintenance

- **Adding a new character:** generate close_face first, then full reference
  using close_face as identity ref. Add file IDs to §3. Add to
  `data/friends_db.json::roster::active_au` or `active_international`.
- **Retiring a character:** move to `bench` in `roster`, keep refs in §3,
  add a retirement note.
- **Adding a reference variant (different lighting/wardrobe):** record under
  the character's row with a clearly distinguishing label. Never replace
  the canonical reference silently.
- **The trained Bella Soul 2.0 character is sacred.** Do not retrain without
  the owner's explicit instruction; the lock survives forever otherwise.

---

*Last updated: 2026-06-12 · Source folder: `Creatives/`
(`1qpMlKgDDUvNv52GvQwsAGfH8C4TRyaNT`)*
