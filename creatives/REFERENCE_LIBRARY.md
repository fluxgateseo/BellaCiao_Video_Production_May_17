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

### For Linh and Kostas (GENERATED 2026-06-12)
Reference assets exist and are locked. Use them exactly as for any other friend:
pass the **close_face** as the identity reference (`media_import`/`media_upload`
→ `media_id`, role `image`), then write the moment in the prompt. The reusable
Higgsfield `media_id` for each close_face is recorded in §3 — pass it straight
into `generate_image` `params.medias[].value` (the friend-equivalent of Bella's
`soul_id`). Procedure that produced them (Higgsfield `soul_2` close_face →
`nano_banana_2` reference shot using the close_face as identity):

1. `Linh_close_face.png` — `soul_2`, cropped clean, visually checked vs the lock.
2. `Linh_reference.png` — `nano_banana_2`, identity = Linh close_face.
3. `Kostas_close_face.png` — `soul_2`, cropped to remove a leaked corner
   signature/avatar artifact, visually checked vs the lock.
4. `Kostas_reference.png` — `nano_banana_2`, identity = Kostas close_face.
5. All four checked against the physical lock in `Avatar_Prompts_Linh_Kostas.md`
   and registered in §3 below.

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

### Owner-confirmed reference (2026-06-14)
The owner designated this photo as the face Bella must match in every frame:

| Asset | Drive location | Drive ID | Higgsfield media_id |
| --- | --- | --- | --- |
| `Bella_trattoria_amicizia.png` (cream knit, holding coffee) | `Creatives/Bella_pictures_avatar/` (folder `1mzcB6s0ATF_fuMQ32R-QqRwmt__c1q_z` → `1RcXoU_ypPGzeLUoYYnmw9AoJpNKPepUJ`) | `1RdThrfA_gVZzV4LrYEjVzH4iNIPoDVgk` | `79382c81-8e15-44fc-bfe3-98f692ce93a9` (uploaded 2026-06-14) |
| `bella_busy_bar.jpeg` (continuity ref; = library `bella_reference.png`, 232,420 bytes) | same folder | `15h_0y-S5qcIFA3oUkdtSx719KrIuBzXH` | — |

> ⚠ There are **two `Creatives/` folders** in this Drive. The owner-reference one
> is `1mzcB6s0ATF…` (parent `1fZttzeQ…`); the v1 asset library catalogued in §2
> above is `1qpMlKgD…`. Don't confuse them. The trained Soul 2.0 already matches
> this owner reference (verified 2026-06-14 across car / café / trattoria scenes).

### ⛔ CONSISTENCY PROTOCOL — why the feed drifted, and the fix
The published feed's faces drift (Bible §17 #8) because those frames were made
from **text prompts alone**, with no identity anchor. THE RULE, no exceptions:

**Every Bella frame MUST be generated from her locked identity — never a
text-only prompt.** Pick ONE anchor per frame:
1. **Preferred — trained Soul 2.0:** `generate_image(model="soul_2",
   soul_id="eeb60f04-a2f5-4a3d-b8d0-88fafca6d8d2", …)`.
2. **Reference-locked:** pass the owner reference as identity media —
   `media_upload`/`media_import_url` → `media_id`, then
   `generate_image(model="nano_banana_2", medias=[{value:<media_id>, role:"image"}],
   prompt="keep this woman's face identical to the reference …")`. The reusable
   media_id for the owner reference is recorded above.

A frame that doesn't pass one of these two paths does not ship. Describing
Bella's face in words is NOT an identity lock and is the cause of the drift.

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
| **Linh** | repo: `creatives/Bella's Friends avatar/Linh_close_face.png` · `Linh_reference.png` | — | Active AU | Sydney · Marrickville · Sông (Vietnamese). **Generated & locked 2026-06-12.** See identity media_id below. |
| **Kostas** | repo: `creatives/Bella's Friends avatar/Kostas_close_face.png` · `Kostas_reference.png` | — | Active AU | Adelaide · Norwood · Thea (Greek taverna). **Generated & locked 2026-06-12.** See identity media_id below. |

**Linh / Kostas — reusable Higgsfield identity refs (pass directly as `params.medias[].value`, role `image`):**

| Asset | Repo path | Higgsfield `media_id` (close_face) / `job_id` (reference) | Source URL |
| --- | --- | --- | --- |
| Linh close_face | `creatives/Bella's Friends avatar/Linh_close_face.png` | media `93d17448-0590-4856-89de-62a63370b5ef` | `…/hf_20260612_135951_a4d8589c-de00-4ccf-bbe6-d6f82271ccfb.png` |
| Linh reference | `creatives/Bella's Friends avatar/Linh_reference.png` | job `1adb1cf6-8717-4d31-9db4-cfeaeb1f81bc` | `…/hf_20260612_140639_1adb1cf6-8717-4d31-9db4-cfeaeb1f81bc.png` |
| Kostas close_face | `creatives/Bella's Friends avatar/Kostas_close_face.png` | media `629e3dce-1f3c-494d-a90d-a7dbf50ddc3c` | uploaded (cropped local; soul_2 source job `030aac70-a4cd-4a62-b22d-9a0dbb0b7747`) |
| Kostas reference | `creatives/Bella's Friends avatar/Kostas_reference.png` | job `0fa58959-1b9f-4fc8-8f4a-e95561aea1cc` | `…/hf_20260612_140714_0fa58959-1b9f-4fc8-8f4a-e95561aea1cc.png` |

> The canonical PNGs are committed to the repo (this folder is not gitignored).
> The close_face is the identity lock; the reference shot is the wardrobe/venue
> continuity frame. Drive-host copies in `Creatives/Bella's Friends avatar/`
> when convenient, then add Drive IDs to the Bytes column to match the other
> friends — owner action (the MCP can't inline-upload the ~8 MB PNGs).

### Bench (return for US/UK launch)

| Character | Drive ID | Bytes | Notes |
| --- | --- | --- | --- |
| Ha-eun | `1ZrBNVCoa3zJX9-5isKc66ET_8QsmhMDC` | 29,939,492 | NYC. Per v1 `friends_db.json` she's "Los Angeles" — that's a stale data correction; she's NYC per the v2 canon. |
| Arun | `1ugAUv3U5MW08q0WkyVWciSmFKqW8uhrU` | 35,795,152 | London. Couples-unit with Priya. |
| Priya | `1cAiNoqtNiuwwvD-ePDQ0TUmGBGv4rgOf` | 30,583,974 | London. Couples-unit with Arun. |

---

## 4 · Deleted characters (owner decision 2026-06-12)

These three are **deleted from the cast**. Never feature them in any frame,
never pull their reference PNGs, never restore them without a new explicit
owner instruction. Tunde was removed from `data/friends_db.json::friends`;
Frank and Diane were never in `friends_db`.

| Character | Drive ID | Status |
| --- | --- | --- |
| Tunde | `1LFixdw9qmvXlVusTLlzZt4wQ0IYpBvtV` | DELETED from cast. Removed from friends_db. |
| Frank | `1Pf2T9a4flG6_wcJ2n8wvvtdrOeRsStBL` | DELETED — never had a profile. |
| Diane | `1egCm2eCCSwJ6hvxZjn7bgljdECB-GQP1` | DELETED — never had a profile. |

> ⚠️ **The Drive PNGs are NOT deleted.** The Google Drive MCP available to this
> project has no delete/trash capability — only read/copy/create. The three
> source PNGs (~94 MB total) still physically exist in
> `Creatives/Bella's Friends avatar/`. **Owner action:** trash them manually in
> Drive if you want them gone. Until then they are flagged here as
> permanently do-not-use.

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
