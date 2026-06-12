---
name: Scoring and gates
description: 9-dimension weighted judge scoring, 7 final quality gates, the 9.5 threshold, and the near-perfect override
type: project
---

The Opus blind judge in engine.py scores each candidate on 9 weighted dimensions:

| Dimension | Weight | Notes |
|---|---|---|
| Sensory opening | 20% | First sentence must be smelled/heard/felt |
| Emotional recognition | 25% | "That's me right now" — leans-in moment |
| Story Spine momentum | 15% | Pixar 8-sentence structure holds |
| Enemy presence | 10% | Shadow specific and inevitable |
| Vogler transformation | 10% | Hero changes inside |
| Bella as mentor | 5% | Present but not dominant |
| Ciao turning point | 5% | Once. Inner monologue, never speech |
| The Elixir | 10% | Small, human, earned — never a product |
| Zero-sell integrity | 5% | BINARY 10 or 0. Any pitch = automatic 0 |

**Thresholds**: `PASS_THRESHOLD = 9.5`. **Near-perfect override**: score ≥ 9.6 AND 6/7 gates passing → accept anyway (don't let one picky gate kill an excellent script).

**7 final gates** (run only after 9.5 cleared):
1. Stop the scroll before the second word?
2. So specific it could only be THIS restaurant, THIS night?
3. Ciao marks a real turn, not decoration?
4. Elixir small, human, earned, not a product?
5. 3+ consecutive cuttable words?
6. Runs unchanged on ElevenLabs at natural pace within target duration?
7. Would owner share at 11 PM without writing a caption?

**Rewrite loop**: up to `MAX_ROUNDS = 3` with structured per-dimension feedback (❌ WEAK / ⚠️ THIN / ✓ strong). Surgical instruction — only weak dimensions get pushed. Best score and candidate tracked across all rounds. If still under 9.5 after 3 rounds, polish pass rewrites only the 2 weakest dimensions and re-judges.

**Why:** Weights came from learning that sensory openings and emotional recognition do most of the share-driving work; the binary zero-sell gate exists because any pitch instantly destroys authority-building intent.

**How to apply:** Tuning weights or thresholds means editing `brand.SCORING_WEIGHTS`, `brand.PASS_THRESHOLD`, and the inline weights in `JUDGE_PROMPT` together — they are not derived from one another. Adding a dimension means updating brand.py, the judge prompt, and the rewrite-notes builder. The exit code from run.py is 0 if final ≥ 9.5, otherwise 2 (soft fail = ship best-effort).
