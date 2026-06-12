---
name: Versioning rule — what changes vs what stays stable
description: Only brand.py and data files should change frequently; pipeline modules require a doc update first
type: feedback
---

The script_engine has an explicit stability contract:

- **Frequently editable**: `brand.py`, `data/friends.json`, `data/calendar.json`. These are the brand bible and the inputs.
- **Stable**: `apify_scout.py`, `strategy.py`, `engine.py`, `run.py`. These are the pipeline. If they need to change, the change goes through a **pipeline doc update first** (`docs/PIPELINE.md`).

**Why:** This is explicitly stated in [docs/PROJECT_SCOPE.md](../docs/PROJECT_SCOPE.md) §"Versioning rule". The pipeline modules carry the contract between stages and the scoring logic — silent changes there break the on-disk handoff or move the quality bar without anyone noticing. The brand bible and data are designed to be the live tuning surface.

**How to apply:** When the user asks for a brand tweak, new friend, new calendar event, or new scoring weight → edit brand.py / data/*.json directly. When the user asks for a pipeline change (new writer, new stage, contract change, new gate, threshold change) → update `docs/PIPELINE.md` first (or in the same change), then the module. brand.py and `docs/BRAND_BIBLE.md` must stay in lockstep.
