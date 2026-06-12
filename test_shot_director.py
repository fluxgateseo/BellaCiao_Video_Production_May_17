from __future__ import annotations

import unittest
from unittest.mock import patch

import shot_director


FULL_SCRIPT = """## SECTION 2 — VIDEO SCRIPT

Tomato sauce simmering since 7am — by noon it's in the whole street.

**ENZO:** Frank's been coming in every Tuesday for eleven years.

Last week he sat down, looked at me, and said —

**FRANK:** "I searched 'Carlton Italian' yesterday. You didn't come up."

I watched Enzo put his hand on the counter and breathe.

## SECTION 3 — INSTAGRAM CAPTION

This should never appear inside the shot list.

## SECTION 4 — SCENE BRIEF

```json
{"city": "Melbourne"}
```
"""


BLEEDING_VIDEO_SCRIPT = """Tomato sauce simmering since 7am — by noon it's in the whole street.

**ENZO:** Frank's been coming in every Tuesday for eleven years.

I watched Enzo put his hand on the counter and breathe.

## SECTION 3 — INSTAGRAM CAPTION

This should never appear inside the shot list.
"""


BRIEF = {
    "friend": "enzo_maria",
    "city": "Melbourne",
    "tone": "warm_and_real",
    "format": "story",
    "target_duration_seconds": 30,
    "avatars": {
        "bella_avatar": "/tmp/bella.jpg",
        "friend_avatar": "/tmp/enzo_maria.png",
        "ciao_avatar": "/tmp/ciao.png",
    },
}


SCENE_BRIEF = {
    "city": "Melbourne",
    "neighbourhood": "Carlton",
    "enemy_visual": "A phone screen showing search results with the restaurant missing.",
    "scene_description": "Frank sits at a corner table while Enzo stands at the pass in an apron.",
    "camera": "static wide to slow push-in on Enzo's hands on the counter",
}


class ShotDirectorFallbackTests(unittest.TestCase):
    def test_offline_fallback_still_emits_structured_shots(self) -> None:
        with patch.object(shot_director, "ANTHROPIC_API_KEY", ""):
            shot_list = shot_director.build_shot_list(
                approved_script=FULL_SCRIPT,
                brief=BRIEF,
                scene_brief=SCENE_BRIEF,
                clip_length=6,
            )

        self.assertGreater(len(shot_list.shots), 0)
        self.assertTrue(all(shot.reference_images for shot in shot_list.shots))
        self.assertTrue(all(shot.prompt_universal for shot in shot_list.shots))
        self.assertEqual(
            shot_list.shots[-1].audio_slice["end_ms"],
            BRIEF["target_duration_seconds"] * 1000,
        )

    def test_fallback_trims_section_bleed_from_existing_video_script_field(self) -> None:
        with patch.object(shot_director, "ANTHROPIC_API_KEY", ""):
            shot_list = shot_director.build_shot_list(
                approved_script=BLEEDING_VIDEO_SCRIPT,
                brief=BRIEF,
                scene_brief=SCENE_BRIEF,
                clip_length=6,
            )

        joined_audio = " ".join(shot.audio_slice["text"] for shot in shot_list.shots)
        self.assertNotIn("INSTAGRAM CAPTION", joined_audio)
        self.assertNotIn("This should never appear", joined_audio)


if __name__ == "__main__":
    unittest.main()
