# Image prompt template — Higgsfield Soul (start/end keyframe)

Fill the slots, then assemble in the exact order below. Pass the character's
identity reference via `custom_reference_id` (preferred) or
`image_reference_image_url`; do NOT describe a separate full-body reference.

## Slots

- `{CHARACTER_DESCRIPTOR}` — pull `identity_lock` (and wardrobe lock) verbatim
  from `characters/registry.json` for each character in the scene.
- `{WARDROBE_LITERAL}` — explicit wardrobe for this shot.
- `{CAMERA_ADDRESS}` — Bella only: `looking directly into the lens, talking to
  camera, eye-contact with the viewer, head square to camera`.
- `{ACTION}` — what the character is doing.
- `{LOCATION_VISUAL}` — interior described by visual elements ONLY. NO genre
  words (trattoria / restaurant / Italian / osteria / the restaurant name).
- `{LIGHTING}` — scene-specific lighting consistent with the brand grade.
- `{FRAMING}` — e.g. chest-up, mid-table, full-length.

## Assembly order

```
{CHARACTER_DESCRIPTOR}, {WARDROBE_LITERAL}, {CAMERA_ADDRESS}, {ACTION},
{LOCATION_VISUAL}, {LIGHTING}, {FRAMING}.

<Shared DNA — verbatim from characters/shared.md>

ABSOLUTELY NO <relevant subset of Shared Negatives + Bella-specific add from
characters/shared.md>, NO exterior view, NO street, NO sky, NO shop-fronts,
NO painted signage, NO neon, NO restaurant name on any wall.
```

## Higgsfield call (defaults from config/defaults.json)

```
soul.generate(
  prompt            = <assembled prompt above>,
  width_and_height  = "1152x2048",
  quality           = "1080p",
  custom_reference_id        = registry[char].refs.higgsfieldCustomReferenceId,
  custom_reference_strength  = 0.6,   # 0.5 for ciao
  style_strength             = 0.35,
  enhance_prompt             = false,
  batch_size                 = 4,
  seed                       = <fixed per content item for reproducibility>
)
```

Export the chosen frame to 1080×1920, upload to the Drive `renders/` folder,
and record the Drive file ID → producing commit in `manifest.json`.
**Do not generate video until the content item is `storyboard_approved`.**
