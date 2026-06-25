# Avatar Image Prompts — Linh & Kostas

Drop-in prompt bodies for the two new AU friends, in the house style of the existing `IMAGE_GENERATION_SPEC.md` locks. Generation runs through the **Higgsfield MCP** — do not specify a model; the MCP selects it based on output quality. For each friend: a **canonical physical lock** (paste into `IMAGE_GENERATION_SPEC.md` + `FRIENDS_AND_CIAO_PROFILES.md`), a **`_reference.png`** prompt (establishing/medium shot), and a **`_close_face.png`** prompt (tight identity crop used as the character reference for subsequent generations).

> These are **proposed locks** — there are no PNGs on disk yet. Confirm/adjust the physical details once, then they are canonical and never change. House realism rule (from the Bella spec): a real person caught mid-thought — **not a model, not an avatar.**

---

## LINH — Sông · Marrickville, Sydney

**Canonical physical lock**
> Linh — Vietnamese-Australian woman, early-to-mid 30s. Warm light-tan skin, dark brown (near-black) hair worn long, clipped back for service with a few loose strands at the temple. Dark brown eyes, quick and warm. Small, fast-moving frame; capable hands. A thin gold chain with a small jade pendant from her mother at the collar — never removed. Minimal makeup. A faint, realistic burn-scar on the inside of the left forearm (kitchen life). Default expression: bright, busy warmth — a half-smile already there, eyes alert and kind, mid-conversation. NOT glamorous, NOT posed, NOT tired.

**`linh_reference.png`** (3:4 portrait, medium shot, waist-up)
```
Photoreal documentary portrait of Linh — a Vietnamese-Australian woman in her early-30s, warm light-tan skin, near-black hair clipped back with loose strands at the temple, dark brown eyes, small thin gold chain with a jade pendant at the collar, faint burn-scar inside the left forearm. Dark fitted tee under a dark apron, sleeves pushed up. Standing at the pass of a small Vietnamese eatery on Illawarra Road, Marrickville — steam rising off a phở pot, a laminated handwritten specials board softly out of focus behind her, warm practical kitchen light, late morning. Half-smile, mid-conversation, looking just off-lens. Real person caught mid-thought, natural skin texture, 50mm lens, shallow depth of field, soft daylight mixed with warm interior light. No text, no logos, no watermark, no beauty retouch, no stock-photo gloss.
```

**`linh_close_face.png`** (1:1 or 3:4, tight head-and-shoulders — identity lock)
```
Tight head-and-shoulders identity portrait of Linh — Vietnamese-Australian woman, early-30s, warm light-tan skin, near-black hair clipped back, dark brown warm eyes, jade pendant on a thin gold chain just visible at the collar, minimal makeup, natural skin texture and fine flyaway hairs. Calm bright expression, faint half-smile, looking directly into the lens. Even soft frontal light, neutral catchlights, plain softly-blurred warm kitchen background, 85mm lens. Photoreal, real person, consistent face. No text, no logos, no watermark, no over-smoothing.
```

---

## KOSTAS — Thea · Norwood, Adelaide

**Canonical physical lock**
> Kostas — Greek-Australian man, late 40s. Solid, broad build. Olive skin, short dark hair greying at the temples, close-trimmed salt-and-pepper beard. Warm dark eyes under a heavy brow that lifts when he laughs. Big hands; a worn silver wedding band; often a string of amber worry beads (komboloi) in one hand. Default expression: big warm host energy — broad closed-mouth smile or mid-laugh, generous and present. NOT stern, NOT a model, NOT a wide forced grin.

**`kostas_reference.png`** (3:4 portrait, medium shot, waist-up)
```
Photoreal documentary portrait of Kostas — a Greek-Australian man in his late-40s, solid broad build, olive skin, short dark hair greying at the temples, close-trimmed salt-and-pepper beard, warm dark eyes, big hands, worn silver wedding band, amber worry beads in one hand. Dark short-sleeve shirt under a long dark apron, sleeves rolled. Standing on the floor of a Greek taverna on The Parade, Norwood — a lamb spit turning softly out of focus behind him, worn timber, white tablecloths, warm amber taverna light, early evening. Broad warm closed-mouth smile, looking just off-lens. Real person caught mid-thought, natural skin texture, 50mm lens, shallow depth of field, warm practical light. No text, no logos, no watermark, no beauty retouch, no stock-photo gloss.
```

**`kostas_close_face.png`** (1:1 or 3:4, tight head-and-shoulders — identity lock)
```
Tight head-and-shoulders identity portrait of Kostas — Greek-Australian man, late-40s, olive skin, short dark hair greying at the temples, close-trimmed salt-and-pepper beard, warm dark eyes under a heavy brow, natural skin texture and pores. Warm, generous expression, faint smile, looking directly into the lens. Even soft frontal light, neutral catchlights, plain softly-blurred warm taverna background, 85mm lens. Photoreal, real person, consistent face. No text, no logos, no watermark, no over-smoothing.
```

---

## Shared generation notes
- **Aspect:** reference at 3:4 (or 9:16 if you want a Reel-native plate); close-face at 1:1 or 3:4.
- **Consistency:** generate the `_close_face` first, then pass it back into the Higgsfield MCP as the character/identity reference for the `_reference` shot and all downstream ShotApproval frames, so the face stays locked across generations.
- **Model:** never named — the Higgsfield MCP chooses and manages it based on output quality.
- **Negative (all frames):** text, captions, logos, watermark, distorted hands, extra fingers, over-smoothed skin, plastic/CGI look, exaggerated beauty retouch, duplicate faces.
- **Placement in repo:** `Creatives/Bella's Friends avatar/Linh_reference.png`, `Linh_close_face.png`, `Kostas_reference.png`, `Kostas_close_face.png`; prompt bodies → `avatars/linh_prompt.txt`, `avatars/kostas_prompt.txt` per the v3 file convention.
