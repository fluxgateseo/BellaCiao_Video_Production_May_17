# Shared Visual DNA — BellaCiao (Higgsfield)

Source of truth for the brand colour grade, the Shared DNA language and the
Shared Negatives that every BellaCiao still / keyframe must carry so every
content item looks like one universe. Per-character identity and wardrobe locks
live in `characters/registry.json`. Engine parameters live in
`config/defaults.json`.

> **Engine note (tested 2026-05-17).** Generation runs through the connected
> **Higgsfield MCP**, not the public REST API. **`nano_banana_2` is the
> keyframe engine** — it executes the literal prompt verbatim, holds the
> single reference-image identity, and respects the locks. **Higgsfield
> `soul_2` is REJECTED for locked characters**: this MCP force-enables a
> prompt-enhancer that cannot be disabled, which paraphrases the prompt and
> reintroduces every forbidden failure mode (wide toothy grin, model
> symmetry, airbrushed skin, neon signage/text). Neither model exposes a
> negative-prompt field, so the Shared Negatives below MUST be folded into
> the prompt body as a trailing `ABSOLUTELY NO ...` clause (honoured by
> `nano_banana_2`). A trained Soul (`soul_id`) for each character is under
> evaluation as a possible way to use `soul_2` despite the enhancer — see
> `config/defaults.json` → `image.engineFindings`. The legacy Runway `@tag` /
> 3-reference-cap and Kling CFG/MICRO-MOVE rules are **not** inherited.

## Shared DNA (verbatim — append to every image prompt)

> Shot on ARRI Alexa, 35mm anamorphic, shallow depth of field, ISO 400-800 organic film grain. BRAND COLOUR PALETTE — must match reference exactly: warm terracotta brick walls, glowing copper pots with orange/amber highlights, golden tungsten ambient light, honey-amber afternoon window light, rich warm-amber overall colour grade, BRIGHT AND LUMINOUS (NOT dim/moody/underexposed/cool/grey/desaturated), cream apron canvas with TAN LEATHER neck and waist straps, warm olive-toned skin, deep blacks in wardrobe, brass and copper accents, wood-tone shelving. Visible skin texture (pores, stray hairs at hairline, natural lip chap). Hair with individual strand detail and flyaways. Handheld micro-jitter. Documentary realism, vertical 9:16. Match the colour temperature, saturation and warmth of the reference image exactly.

## Shared Negatives (verbatim — fold into prompt body as `ABSOLUTELY NO ...`)

> no cartoon, no anime, no 3D render, no CGI, no Pixar, no Unreal Engine, no illustration, no painting, no digital art, no stylised animation, no plastic skin, no waxy skin, no airbrushed, no beauty filter, no porcelain skin, no doll eyes, no wax figure, no mannequin, no AI-smooth, no oversized eyes, no uncanny symmetry, no HDR glow, no halo lighting, no oversaturated neon, no flat lighting, no cool tones, no grey/slate counters, no fisheye, no dutch tilt, no music-video aesthetic, no stock-footage look, no modern minimalist restaurant, no american diner, no neon signs, no chef hat, no wide toothy smile, no text/logos/captions/watermarks/subtitles, no extra fingers, no mangled hands, no distorted faces, no elongated necks, no cat/kitten/feline, no pets other than Ciao the Italian Greyhound.

### Bella-specific negatives add (verbatim)

> no hazel/green/brown/grey eyes, no blonde hair, no heavy balayage, no freckles, no stud earrings, no looking away, no averted gaze, no profile of Bella's face, no back-of-head of Bella, no held wide-open-mouth smile as default.

## Brand colour palette (all scenes)

Must match the canonical reference tone exactly — bright, luminous, warm-amber:

- Terracotta brick walls
- Glowing copper pots with orange/amber highlights
- Golden tungsten ambient light + honey-amber afternoon window light
- Cream canvas apron with **TAN LEATHER neck + waist straps**
- Warm olive-toned skin
- Deep blacks in wardrobe
- Brass and copper accents catching light
- Wood-tone shelving in background
- Grade: rich warm amber, BRIGHT AND LUMINOUS — NOT dim, NOT moody, NOT
  underexposed, NOT cool, NOT grey, NOT desaturated. One stop brighter than
  low-key.

## Frame conventions (Higgsfield, re-derived)

- Start/end frames: **1080×1920 vertical 9:16**. Higgsfield Soul has no native
  1080×1920 enum; generate at `1152x2048` (exact 9:16) at `1080p` quality and
  downscale on export.
- Per content item produce: `start.png`, `end.png`,
  `start_frame_description.txt`, `end_frame_description.txt`.
- One identity reference per character drives the face lock (Higgsfield
  `custom_reference_id`, or `image_reference_image_url` until a Soul character
  is trained). Wardrobe and colour grade are carried by prompt language, not by
  a full-body reference.
- **Restaurant name NEVER appears in the visual.** Strip genre words
  (`trattoria`, `restaurant`, `Italian`, `osteria`, and the specific restaurant
  name) from image prompts. Describe interiors purely by visual elements
  (e.g. "a warm dimly-lit family-run dining room with dark timber walls").
  Restaurant identity is carried in the script / VO only.
- Always append the anti-exterior anchor clause to image prompts:

  > ABSOLUTELY NO exterior view, NO street, NO sky, NO shop-fronts, NO painted signage, NO neon, NO restaurant name on any wall.

- For Bella, always append the camera-address clause inline after the wardrobe
  literal:

  > looking directly into the lens, talking to camera, eye-contact with the viewer, head square to camera

## Kling → Higgsfield control mapping

| Legacy (Kling/Runway) | Higgsfield MCP equivalent (tested) |
|---|---|
| Runway `@tag` face-crop ref | single reference image via `generate_image` `medias[{role:'image'}]`; trained `soul_id` once verified |
| Runway 3-reference cap | one reference image per generation; multi-char sequential / combined ref |
| Kling CFG (identity adherence) | not tunable — identity = reference image + literal prompt on `nano_banana_2` |
| Kling CFG 0.3 for Ciao stillness | video motion control (untested) |
| Kling MICRO-MOVE | video motion control (untested) |
| Negative-prompt block | no native field — inline `ABSOLUTELY NO ...` clause (honoured by `nano_banana_2`) |

## Storyboard approval gate

Per content item: generate script + scene prompts + still keyframe(s)
(`start.png` / `end.png`). The user manually approves the storyboard. **No
video-generation call (dop / Cinema Studio) is made until the content item's
status is `storyboard_approved`.** Nothing spends video-generation budget
without explicit manual approval.
