---
name: Project scope
description: What the script_engine project is and is explicitly not — single-purpose script generator extracted from the larger Bellaciao video pipeline
type: project
---

The script_engine is a standalone, single-purpose Python project that produces **one ≥9.5/10 Bella story script per invocation** — calendar-aware, trend-informed, ready to hand to a video stage. One brief in, one script out.

It deliberately does not handle audio, video, lipsync, captions, or analytics. The downstream video creation tool is a separate project. Publishing and any messaging-bot / approval workflow are out of scope for the entire ecosystem.

**Why:** Boundary failures dominate multi-stage pipelines. A 9.5+ script is the difference between a DM and a scroll-by — it earns its own isolated home.

**How to apply:** Treat this folder as locked-scope. If a request involves audio, video, captions, multi-job orchestration, A/B testing, or cross-session memory/learning, push back and propose forking a separate project rather than expanding script_engine. If the request is publishing or a bot workflow of any kind, refuse outright — it's out of scope ecosystem-wide.
