---
name: Brand non-negotiables
description: Hard, never-violate brand bible rules for Bella, Ciao, the Elixir, the cast, and the cities
type: feedback
---

Bella brand bible has rules that are NOT negotiable. brand.py is the single source of truth — do not duplicate these constants in other modules.

- **Bella** is the Mentor archetype. She NEVER pitches a product, NEVER teases a solution, NEVER sells in the body. She is present but never dominant. She is the reason the story gets told, never the story herself. Canonical appearance: long dark brown wavy hair with caramel highlights, BLUE eyes, golden-tan olive skin, small gold stud earrings. **VISUAL RULE (separate axis):** Bella always looks directly into the lens and talks to camera per BELLA_MASTER_BIBLE.md §0 Camera Address Mandate — the Mentor restraint governs WHAT she says, not WHERE she looks. Added 2026-04-23.
- **Bella is ALWAYS physically on screen in every video** — narrates, visible, own avatar shots. She is no longer optional. (Updated 2026-04-11.)
- **Cast patterns (one per video, updated 2026-04-11)**:
  - **Pattern A (1-to-1)**: Bella + 1 solo friend + Ciao when required. Solo friends: Naomi, Sal, Jake, Yasmin, Danny, Sophie.
  - **Pattern B (1-to-2 + kids)**: Bella + 1 couple (counted as one friend unit) + their child(ren) on screen + Ciao when required. Couples: Enzo & Maria (+ Luca 8), Arun & Priya (+ Anaya 3).
  - **Sophie special case**: default Pattern A; Pattern B variant allowed for parent-and-child stories (Bella + Sophie + Mia 5).
- **Ally on camera (revised 2026-04-11, reversed same day)**: an ally MAY appear on camera in either pattern when the story specifically benefits from their physical presence. Default is "no ally in scene" — most videos don't use it. When present, the ally SPEAKS (labelled dialogue like `SOUS_CHEF:`). ONE ally max per video. Ally archetype must be drawn from `brand.ALLIES`. An earlier 2026-04-11 version of this rule that said "NEVER an ally as third human in scene" is RETIRED — that flip was reversed the same day. Future sessions: do NOT re-retire the ally rule without an explicit user request.
- **No multi-friend videos**: never mix Jake with Naomi, never put two friends in the same video. The previous "2-3 friends can appear per video" rule from bible §7 is RETIRED.
- **Ciao** (Italian Greyhound, Herald) appears in MOST videos but not all (updated 2026-04-11). Strategy director picks per brief based on whether the turn is sharp enough to need a Herald. When absent, the Ciao gate auto-passes. The "ONCE per story, marks the turning point, big-voice-tiny-dog inner monologue" rule still applies WHEN present.
- **The Elixir is NEVER a product. NEVER a system. NEVER a feature.** It is small, human, earned. Violating this is a binary 0 on the zero-sell dimension and an automatic gate failure.
- **Cities**: New York · London · Melbourne ONLY. No other cities, ever.
- **Children** (Anaya 3, Luca 8, Mia 5) are visual presence only — they NEVER speak.

**Slot duration contract (added 2026-04-11):**
- **Stories**: target ~30s, hard ceiling ~33s. ONE sensory opener + ONE emotional reveal + ONE Bella witnessing line. NO full Pixar 8-spine, NO Vogler journey, NO multi-scene structure. Ciao MAY appear briefly, never as a set-piece. ~75 spoken words at 2.5 wps.
- **Reels**: 30 to 60 seconds. NEVER under 30s. Full Pixar 8-sentence spine + complete Vogler arc + Ciao turning point + earned Elixir. 75–150 spoken words at 2.5 wps. Reels under 30s are miscategorised stories — promote/regenerate.
- The strategy director picks the exact length within the slot's band based on the brief — never default. The quality_supervisor's pacing gate uses `brand.SLOT_DURATION` (story 8/30/33, reel 30/45/60) and runs a deterministic structural pre-check that fails reels under ~65 words and stories over ~95 words.
- Authoritative source: `Master Documents/BELLA_MASTER_BIBLE.md` §14. Mirror in `script_engine/brand.py` (`DURATION_GUIDE`, `STORY_SPEC`, `REEL_SPEC`, `SLOT_SPEC`, `SLOT_DURATION`). Both must stay in lockstep — if you change one, change the other in the same commit.

**Why:** These rules came from the original MASTER_INSTRUCTIONS Brand Bible v5 and the Bella skill.md. Every violation has historically tanked scripts in the blind Opus judge or triggered the zero-sell gate, which is binary (10 or 0). The slot duration contract was added on 2026-04-11 when the user moved to a daily 1 story + 1 reel cadence on Instagram and required different structural rules per slot.

**How to apply:** When writing or reviewing prompt changes, scoring dimensions, or example scripts, check against this list first. If a request would soften any of these (e.g. "have Bella mention the trial", "let Ciao bark twice", "set it in Sydney", "let a story have a full Pixar arc"), refuse and cite brand.py + the Master Bible. brand.py and `Master Documents/BELLA_MASTER_BIBLE.md` must stay in lockstep — `docs/BRAND_BIBLE.md` is the v1.0 legacy doc and is NOT the source of truth.
