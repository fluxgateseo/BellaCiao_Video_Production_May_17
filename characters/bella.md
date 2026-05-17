# Bella — Canonical Character Lock (1000-video pipeline)

**Goal:** every Bella frame across every video is the *same person*. Identity
must not drift over 1000+ generations.

## Identity is enforced by TWO things together (never one alone)

1. **Reference image anchor (primary).** ALWAYS pass Bella's canonical
   reference as a `medias[{role:"image"}]` input to `nano_banana_2`.
   - Drive source: `bella_face_crop.png` → `1Gb36lnd44tqY_XyTg4ioWkcjOiQeIn3S`
     (registry `bella.refs.primary`).
   - Stable Higgsfield media for this reference (uploaded 2026-05-17,
     reusable across jobs): `3dad09f7-f516-40ee-9d4f-24c9346581d5`.
   - The reference image is what actually holds the face. The text below
     reinforces it and must never contradict it.
2. **Frozen Character DNA text block (below).** Prepended *verbatim,
   unchanged* to every Bella prompt. Do not paraphrase, reorder, trim, or
   "improve" it per-video — drift comes from wording changes.

Engine is locked to **`nano_banana_2`** (literal-prompt, holds the reference,
respects locks). `soul_2` only as a verified secondary for cross-shot
continuity — see `config/defaults.json` → `image.engineFindings`.

## Prompt assembly (the only allowed structure)

```
<DNA BLOCK — frozen, verbatim>
SCENE: <one line: location + light + what she is doing>
WARDROBE: <one line from the registry wardrobe rotation; default if unset>
ACTION/EXPRESSION: <one line; must stay inside the EXPRESSION LOCK>
<NEGATIVES BLOCK — frozen, verbatim>
```

Only `SCENE`, `WARDROBE`, `ACTION/EXPRESSION` change between videos.
Resolution `2k` for master keyframes, `aspect_ratio "9:16"`, reference
media always attached.

---

## DNA BLOCK — frozen, paste verbatim

> Bella, the exact same specific woman as the attached reference photograph —
> reproduce her face identically, this is the same real individual every
> time, not a similar-looking person. Italian-American woman, mid-20s. Oval
> face with soft but defined jawline and natural slight left-right asymmetry
> (not a symmetrical model face). High, softly rounded cheekbones. Straight
> nose with a slightly rounded tip. Full, naturally medium-pink lips, the
> lower lip a little fuller than the upper. Clear cornflower-BLUE eyes with a
> visibly darker iris ring and warm catchlights — never green, hazel, brown,
> or grey. Full, well-defined natural dark eyebrows, gently arched, with a
> few stray hairs (not drawn, not microbladed). Warm olive skin with real
> visible pores, faint natural fine lines, subtle natural under-eye softness,
> and a believable matte-to-low-sheen finish — NO freckles anywhere. Long
> dark-brown hair, centre-parted, loosely waved, falling past the shoulders,
> with only SUBTLE warm honey highlights (not blonde, not heavy balayage) and
> a soft flyaway strand at one temple. Small, subtle delicate gold hoop
> earrings (thin hoops, not studs). Light natural makeup or close to bare —
> no heavy contour, no glossy magazine retouching. She has a calm, warm,
> grounded presence: a real working person, not a model in a campaign.

## EXPRESSION LOCK — frozen

> Default expression: relaxed face with a soft CLOSED-LIP half-smile, lips
> gently together, the smile reaching the eyes first (warm eyes, slight
> crease) — absolutely NO visible teeth, NO open mouth, NO wide grin. A full
> open-mouth / teeth smile is used ONLY when the scene explicitly earns it
> (a genuine laugh, the dog Ciao, or a friend's win); if the scene does not
> say so, keep the closed-lip half-smile.

## CAMERA — frozen

> She looks directly into the lens, eyes locked to camera, head square to
> camera. Documentary candid photograph: warm available tungsten light,
> shallow depth of field, slightly imperfect handheld framing, natural
> film-like colour. Averted or off-camera gaze is a failure.

## NEGATIVES BLOCK — frozen, paste verbatim at end

> ABSOLUTELY NO different woman, NO face that merely resembles her, NO
> changed eye colour, NO green/hazel/brown/grey eyes, NO freckles, NO blonde
> or heavy balayage hair, NO stud earrings, NO wide grin, NO visible teeth,
> NO open mouth, NO airbrushed/glossy/plastic skin, NO symmetrical
> fashion-model retouching, NO beauty filter, NO studio lighting, NO heavy
> makeup, NO neon, NO signage, NO text, NO restaurant name, NO window, NO
> street, NO exterior, NO sky.

---

## Notes

- Wardrobe rotation, voice, sign-off and full bible authority live in
  `characters/registry.json` → `characters.bella` and `characters/shared.md`.
- If a future engine change is needed, update `config/defaults.json` first;
  this file's DNA block stays engine-agnostic.
