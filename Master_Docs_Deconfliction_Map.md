# Bella Ciao — Master Documents Deconfliction Map

**Status:** v1, 4 June 2026. Companion to `Bella_Ciao_Content_Sales_Alignment_Brief.md`.
**Purpose:** Audit the 8 uploaded production docs + the master brand bible against (a) each other and (b) the sales strategy, so the new Claude Code project inherits **one** non-conflicting scope instead of three overlapping ones.
**Inputs audited:** `bella_master_bible.docx` · `Bella_Shorts_Hooks.xlsx` · `CONTENT_PRODUCTION_SYSTEM.md` (v2.1) · `CONTENT_PRODUCTION_SYSTEM_V3.md` (v3.0) · `CONTENT_CADENCE.md` (v1.3) · `CONTENT_CALENDAR.md` · `CONTROL_SURFACE.md` (v1.6) · `DAILY_CHANNEL_OPERATING_MODEL.md` (v1.0) · `FRIENDS_AND_CIAO_PROFILES.md`.

---

## A. The four conflicts that block everything else

These aren't doc-hygiene nits. Each one makes the pipeline generate the wrong thing.

### 1. The content fronts the wrong company
The master bible opens: *"Bella is the face of **SEO For Restaurants** — a specialist agency that helps restaurant owners get found on Google."* The product at bellaciao.ai is an **AI phone receptionist + Ciao booking system**. The entire content engine — every pillar, enemy, hook and friend backstory — is built to sell **Google visibility**, a product you do not sell. All 9 published episodes confirm it (duplicate listings, unclaimed profiles, "Open today, Google disagrees"). This is the root cause of "the code can't see the scope": the scope it was given is a different business.

### 2. Market mismatch — two-thirds of the cast targets markets you can't sell to
The bible runs **three markets (AU/US/UK)** across **NYC, Melbourne, London** — 11 friends, only 4 of them Melbourne. The sales strategy is **Australia only** (AUD pricing, OpenTable AU, the Quandoo-AU shutdown, Sadie as the AU competitor). So ~7 of 11 canonical friends — Naomi, Sal, Ha-eun (NYC), Yasmin, Danny, Arun & Priya (London) — build an audience in markets with **no product to buy**. The published feed is worse: Edinburgh, Bristol, Brisbane episodes are in cities that aren't even canonical (canon is Melbourne/NYC/London only).

### 3. "Never pitch" vs "book a demo"
The bible makes zero-sell **binary**: *"She never says 'book a demo', 'try us', 'sign up.' … Any trace of a pitch = disqualification."* Yet the bible's **own KPI table** lists Primary = *"Demo bookings + trial activations per week"* and DM triggers *BELLA / SEO / DEMO*, and the sales strategy's whole funnel is **discovery call → demo**. The alignment brief's CTA ("hear a sample call → book a demo") **violates the bible's binary rule as written**. These must be reconciled into one model (recommended: authority-led soft CTA — "hear a sample call" as a DM/comment trigger, not an in-video sell).

### 4. The news layer is both mandated and deleted
Bible §3 mandates a *"Real-World Intelligence Layer"* scraping fresh restaurant news every cycle. But `CONTENT_CADENCE.md` v1.2 and `CONTROL_SURFACE.md` v1.5 record the **News layer REMOVED entirely** (`news_scout.py`, `--stage news`, News table all deleted). Meanwhile your own production signal says **news-hook episodes outperform**, and the sales strategy's biggest wedge (**Quandoo shutdown, deadline 30 Sep 2026**) is pure news. The code deleted the exact capability that's working and that the GTM needs.

---

## B. Internal contradictions to fix in code (concrete bugs)

| # | Field | Doc A says | Doc B says | Fix |
|---|-------|-----------|-----------|-----|
| B1 | **Bella ElevenLabs Voice ID** | bible: `M7ya1YbaeFaPXljg9BpK` | `CONTENT_PRODUCTION_SYSTEM.md` (line 380): `9DxYbhovJvj6zRtn0Pvc` — "never change" | Pick one, lock everywhere. Both claim canonical. |
| B2 | **Bella heritage** | bible: "Irish-Italian, Irish mother / Italian father, born NYC" | v3 guardrail: "Italian-Irish-American" | Standardise wording. |
| B3 | **Daily output contract** | v2.1: "60–90 pieces/month" then "1 Reel + 1 Story/day"; v3.0: triplet (Reel/YT Short/Carousel) | `DAILY_CHANNEL_OPERATING_MODEL` v1.0: "1 Reel + 1 Story + YouTube reuse" is canonical, v3 is non-default | Daily model already claims precedence — delete or clearly demote the competing volume claims so only one contract is "default". |
| B4 | **Bella's voice persona** | bible: "100% confident **NY English**" | alignment brief earlier draft: warm Italian-Australian | Canon wins: NY English. (Correcting the brief — see §E.) |
| B5 | **Markets/cities** | bible: AU/US/UK · Melb/NYC/London | sales strategy: AU only | Strategic, not cosmetic — see §A2 and the gating decision. |

---

## C. Per-document disposition (target: no overlap)

| Document | Governs | Overlaps / conflicts with | Recommended action |
|----------|---------|---------------------------|--------------------|
| `bella_master_bible.docx` | Character, voice, pillars, hooks, enemies, quality gates | Source of A1/A3/A4; voice-ID conflict B1 | **REWRITE → "Bella Ciao Master Bible v2"** — keep character/voice/format/friends/Ciao/quality gates; replace the SEO-agency premise, pillars and enemies with the receptionist/booking universe from the alignment brief. Becomes the single canonical character doc. |
| `Bella_Shorts_Hooks.xlsx` | 20 hooks × 7 doctrine types | Hooks are GBP/SEO-worded | **REWRITE hook copy** to missed-call/booking/Quandoo angles; keep the 7-doctrine structure + rotation engine. Re-run `hooks_sync.py`. |
| `CONTENT_PRODUCTION_SYSTEM.md` v2.1 | 7-skill pipeline, voice/SSML, modules | B1, B3; News (A4) | **KEEP as engine spec**; fix voice ID; defer to Daily Operating Model on output contract. |
| `CONTENT_PRODUCTION_SYSTEM_V3.md` v3.0 | Additive triplet flow | B3 (competes with daily model) | **KEEP but explicitly NON-DEFAULT** (it already says so). Don't let it read as the daily contract. |
| `CONTENT_CADENCE.md` v1.3 | Slot/mode/hook-rotation rules | A4 (removed news); pairs with Control Surface | **KEEP**; re-add a scoped news/trend mode (see §D). |
| `CONTENT_CALENDAR.md` | The actual dated plan | Dated 13–14 Apr 2026; pre-pivot premise | **REGENERATE** → realigned to 4 June (separate deliverable). |
| `CONTROL_SURFACE.md` v1.6 | Airtable tables + staged CLI gates | A4; version stamp mismatch (header v1.6, footer v1.5, table tops out at 1.5) | **KEEP**; reconcile its own version number; re-add news gate if news mode returns. |
| `DAILY_CHANNEL_OPERATING_MODEL.md` v1.0 | The canonical daily contract | Supersedes B3 competitors | **KEEP as the canonical output contract**; everything else defers to it. |
| `FRIENDS_AND_CIAO_PROFILES.md` | 11 friend profiles + Ciao | Every backstory is "invisible on Google" (A1); 7/11 non-AU (A2) | **REWRITE before/after arcs** from GBP → missed-calls/bookings; decide cast roster per the market decision. |

**Resulting canonical set (no overlap):** one Master Bible v2 (who/voice/pillars/enemies/format) · one Daily Operating Model (output contract) · Cadence + Control Surface (how the pipeline schedules & gates) · v2.1 system spec (engine internals) · v3.0 (optional triplet) · Friends v2 (rewritten arcs) · Hooks v2 (rewritten copy) · a regenerated Calendar · the Alignment Brief sitting above all of them as the strategy source of truth.

---

## D. The news layer should come back (scoped)
Re-add a **trend/news mode** governed by the alignment brief's news-preempt rule: a story preempts only if (a) it's in the AU restaurant ecosystem and (b) it ties to the demo CTA in-episode. The standing beat is the **Quandoo countdown** to 30 Sep 2026. This restores the capability the data says works, without reopening the unbounded news scraping the bible originally specified.

---

## E. Correction to the Alignment Brief
The brief's §9 creative scaffold proposed Bella as "29, Adelaide, Italian-Australian." **Canon overrides this:** Bella is **25, NYC-born Irish-Italian, blue eyes, gold studs, fast NY English**, moving between NYC/Melbourne/London, with Ciao the Italian Greyhound and an 11-friend universe. I'll fold this correction (and the market decision below) into a brief v2 once you've decided §F.

---

## F. The one decision that gates the calendar
The product is AU-only; the cast is two-thirds non-AU. The realigned calendar's friend roster and per-episode premise both depend on how you want to resolve that — see the question in chat.
