# CLAUDE.md — BellaCiao_Video_Production

Operating guardrails for this content-production project. Read this before any `--stage` run. The canon lives in **`BellaCiao_Master_Bible_v2.md`** (machine-readable twin; `BellaCiao_Master_Bible_v2.docx` is the human reference); the schedule lives in **`CONTENT_CALENDAR_June.md`**; the strategy rationale lives in **`Bella_Ciao_Content_Sales_Alignment_Brief.md`**. Where code, `friends_db.json`, or `Bella_Shorts_Hooks.xlsx` disagree with the bible, **the bible wins**.

## Canonical references (auto-loaded)

@BellaCiao_Master_Bible_v2.md
@CONTENT_CALENDAR_June.md

> These `@`-imports pull the full canon + current calendar into context every session. The bible is large; if context cost matters, delete its import line and instead instruct: "Read `BellaCiao_Master_Bible_v2.md` before `--stage brief`/`write`." The `.docx` is never imported (binary).

## What this channel is for
Top-of-funnel for **Bella Ciao** — a 24/7 **AI phone receptionist + Ciao commission-free booking system** for restaurants. Every episode dramatises the pain the product solves: **missed calls, lost after-hours bookings, OpenTable cover fees, no-shows, the Quandoo shutdown.** It is **NOT** an SEO / Google-Business-Profile channel. That premise is retired.

## Non-negotiables (resolved conflicts — do not reopen)
- **Premise:** calls & bookings, never "get found on Google." Retired enemies: `the_invisible_ranking`, `the_algorithm`, `the_social_media_trap`. Banned: framing the problem as SEO/ranking; the word "algorithm".
- **Bella is international:** 25, NYC-born Irish-Italian, blue eyes, gold studs, fast NY English. Never localise her as Australian.
- **Voice ID:** `9DxYbhovJvj6zRtn0Pvc` (ElevenLabs). ⚠ Confirm once against the live voice — the old bible and the pipeline disagreed (`M7ya1YbaeFaPXljg9BpK` vs this). Lock it everywhere after confirming.
- **Daily output contract (canonical):** 1 Reel (30–60s) + 1 Story (~30s, same friend) + 1 YouTube reuse package. The "60–90/month" and v3 triplet models are **non-default**.
- **CTA:** Bella never pitches on camera (zero-sell is binary). The action is a **caption DM trigger** — "DM CALL → 30s of Bella answering a real restaurant phone → demo." International episodes use a softer follow/await-launch trigger.
- **News layer:** restored but scoped. A news story preempts the schedule only if (a) it's in a focus-market restaurant ecosystem and (b) ties to the CTA in-episode. **Standing beat: Quandoo** (migration 30 Sep 2026 / shutdown 31 Dec 2026).

## Market & cast (60 / 40)
- **Commercial focus: Australia now**; US/UK launch in a few months. International content builds the brand/audience for that launch.
- **Active roster — 6 AU / 4 international = 60/40:**
  - AU (conversion): Jake (Melb·Fitzroy), Enzo & Maria (Melb·Carlton, IT), Sophie (Melb·South Yarra), Mei (Melb·Chinatown, ZH), **Linh (Sydney·Marrickville, VI)**, **Kostas (Adelaide·Norwood, EL)**.
  - International (brand): Naomi (NYC), Sal (NYC), Yasmin (London), Danny (London).
  - **Bench (return for US/UK launch):** Ha-eun (NYC), Arun & Priya (London).
- **Cities:** Melbourne, Sydney, Adelaide, New York, London — specific neighbourhoods always. Friend/venue names fictional; neighbourhoods/events real.
- **Currency:** `$` for AU & NYC, `£` for London. Never mix in one script.

## Pillars & target mix
- **A — Never miss a booking** 40% · **B — Stop paying to be booked** (OpenTable fees / commission-free Ciao) 25% · **C — Built for hospitality** (EN/ZH/IT/EL/VI) 15% · **D — News / Quandoo** 20%.
- **Pillar 5 — Life & Friendship** is the emotional overlay across all, and the home for the 40% international/brand episodes.
- Languages covered by the AU cast: Mei ZH · Enzo & Maria IT · Linh VI · Kostas EL · all + EN.

## Primary KPI
Qualified **demo bookings / "hear a sample call" DM triggers per week**. Saves (>3%) and follows are leading indicators only — never optimise for reach that can't convert AU operators.

## Pipeline reminders
- Approval gates unchanged (Airtable: Calendar → ContentCalendar → Briefs → Scripts). Three-gate rule still applies before `--stage write`.
- Before shipping: rewrite `friends_db.json` before/after arcs (GBP → calls/bookings) and `Bella_Shorts_Hooks.xlsx` copy to match this premise, then `python3 hooks_sync.py`.
- Quality gates and the Elixir rule (resolution is human, never the product) are unchanged.
