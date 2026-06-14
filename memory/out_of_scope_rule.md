---
name: Out of scope — do not pollute the engine
description: Hard rule to refuse scope creep into script_engine; capabilities outside script generation belong in video_pipeline or a new project
type: feedback
---

The script_engine project must NEVER absorb capabilities outside script generation. Explicitly out of scope:

- Audio generation, alignment, audio QA
- Video composition, captions, transitions, lipsync
- Image generation (food photos, avatar references)
- Cloudflare R2 / Drive / OAuth uploaders
- Multi-job batch runs (one --stage call = one logical step)
- Cross-session intelligent memory and analytics loops
- A/B testing, performance learning

**Also out of scope for the entire Bellaciao ecosystem (not just script_engine):** publishing of any kind (Instagram, YouTube, anywhere), and any messaging-bot workflow (Telegram, Slack, Discord, etc).

> **2026-06-14 update:** The owner explicitly reversed the publishing ban —
> content scheduling/publishing is now IN scope, built with **direct platform
> APIs** (Metricool was dropped as too expensive). It is kept isolated from the
> script engine in a dedicated `publishers/` package (not inside the engine), so
> the "don't pollute the engine" rule still holds. **YouTube (Shorts) is built
> first** (`publishers/youtube_publisher.py` + `publish_queue.py`, native
> `status.publishAt` scheduling). Instagram/TikTok publishers may follow as
> sibling modules. Messaging-bot approval workflows remain out of scope.

> **2026-04-10 update:** Approval gates were previously listed here as out of scope. The user has explicitly reversed that — Airtable verdict gates (Calendar / ContentCalendar / Briefs) are now the **primary control surface** for the pipeline. Approval workflows that live INSIDE Airtable as user-driven verdict columns are IN scope. Approval workflows that live OUTSIDE Airtable as bot interactions (Telegram approval, Slack approve buttons, email-reply workflows, etc.) remain OUT of scope. The distinction: the user reviews in Airtable, the pipeline reads Airtable. Nothing else mediates.

**Why:** Boundary failures are the most common source of bugs in multi-stage pipelines. Keeping script generation isolated is what lets it stay reliable enough to be revenue-driving. PROJECT_SCOPE.md says: "If any of these creep in, **fork a separate project**. Do not pollute the script engine."

**How to apply:** When the user asks for something on this list, refuse to add it to script_engine and propose forking a new sibling project (e.g. the downstream video creation tool). The only valid extension surface inside script_engine is: new writers, new scoring tweaks, new calendar events, new friends, new scraping sources for apify_scout, **new Airtable verdict gates or fields**. If the user asks for publishing or any external messaging-bot workflow, tell them it's out of scope for the entire ecosystem.
