# Handoff — instructions to paste into the BellaCiao_Video_Production_May_17 Claude Code session

**How to use this:** Upload these files into the repo first → `CLAUDE.md`, `BellaCiao_Master_Bible_v2.md`, `BellaCiao_Master_Bible_v2.docx`, `CONTENT_CALENDAR_June.md`, `premise-guard.md`, `friends_db_additions_Linh_Kostas.json`. Then open Claude Code in the repo and paste the block below as a single message. It tells the project to do the whole migration itself, review-gated.

---

## ⤵️ PASTE THIS INTO CLAUDE CODE

```
You are updating this project from the retired "SEO / Google" premise to the new
"Bella Ciao — AI phone receptionist + booking system" premise. The new canon has been
added to the repo: read these FIRST and treat them as source of truth, in this order:
  1. CLAUDE.md
  2. BellaCiao_Master_Bible_v2.md   (esp. §5 pillars, §7 cast, §8 enemies, §13 hard rules, §17 conflict log)
  3. CONTENT_CALENDAR_June.md
  4. friends_db_additions_Linh_Kostas.json

Work on a branch (premise-pivot-v2). Do the tasks below IN ORDER. After each task, show me
the diff and STOP for my approval before the next. Do not touch face/identity/avatar locks,
the ElevenLabs slider calibrations, or any approval-gate logic. Ask if anything is ambiguous
rather than guessing.

TASK 1 — friends_db.json: add the two new Australian friends.
  Open an existing entry (e.g. `mei` or `jake`) to learn the EXACT schema/key names.
  Insert `linh` and `kostas` using the content in friends_db_additions_Linh_Kostas.json,
  conformed to that exact schema. Active roster must end up 6 AU (jake, enzo_maria, sophie,
  mei, linh, kostas) + 4 international (naomi, sal, yasmin, danny) = 60/40. Mark haeun and
  arun_priya as bench/inactive (do not delete). Show the diff.

TASK 2 — friends_db.json: reframe every before/after arc from "invisible on Google" to the
  calls/bookings premise per bible §7, and set each friend's `enemy` to one of the allowed
  enemies (the_missed_call, the_after_hours_booking, the_no_show, the_cover_fee,
  the_language_gap, the_quandoo_exit, the_system_failure).

TASK 3 — Retire the GBP enemies everywhere in code: find all references to
  `the_invisible_ranking`, `the_algorithm`, `the_social_media_trap` (enums, brand.py,
  logical_gate.py, prompts, validators) and replace with the allowed set above; update any
  branching logic. List every file changed.

TASK 4 — Lock the ElevenLabs voice ID to `9DxYbhovJvj6zRtn0Pvc` everywhere it appears
  (brand.py, video_prompts.py, ssml_tagger.py, configs). Flag any remaining `M7ya1YbaeFaPXljg9BpK`.
  ⚠ Do not assume — surface every occurrence so the owner can confirm against the live voice.

TASK 5 — Hooks: reword the 20 hooks in Master Documents/Bella_Shorts_Hooks.xlsx from
  Google/SEO angles to the calls/bookings/Quandoo angles in bible §4 (keep the 7 doctrine
  types and friend tags). Add 2–4 friend-specific hooks each for linh and kostas (and fill
  any known gaps for arun_priya/sophie). Then run `python3 hooks_sync.py` and confirm
  data/bella_hooks.json regenerated.

TASK 6 — Daily output contract: confirm run.py defaults to 1 Reel + 1 Story + YouTube reuse
  (DAILY_CHANNEL_OPERATING_MODEL). Demote the "60–90 pieces/month" language in
  CONTENT_PRODUCTION_SYSTEM.md; keep run_v3.py (triplet) explicitly non-default. Docs/defaults
  only — no behaviour change to v3.

TASK 7 — News layer (scoped): reintroduce a news/trend mode gated by the news-preempt rule in
  bible §3 (preempt only if AU-ecosystem relevant AND tied to the demo CTA), with the Quandoo
  countdown (deadline 30 Sep 2026) as a standing beat. Reuse the old news_scout from git
  history if present, but keep it gated. No unbounded scraping.

TASK 8 — CTA / zero-sell: ensure the spoken video_script never pitches (no "book a demo",
  "sign up", "DM me", or product-as-sell) and the CTA lives only in the caption as a DM
  trigger ("DM CALL → hear a sample call"), per bible §10. Update quality_supervisor.py if it
  checks CTA placement.

TASK 9 — Fix the audit skill: ~/.claude/skills/bella-coherence-strategist still enforces the
  SEO "Hospitality North Star". Rewrite its checks to the receptionist/booking premise per the
  bible (calls, bookings, cover fees, Quandoo; zero-sell = caption-only; Bella international;
  60/40 cast). Leave bella-retention-architect unless it references Google.

TASK 10 — Install the guard agent: move premise-guard.md to .claude/agents/premise-guard.md.

VERIFY before you report done:
  - python3 run.py --stage plan --plan-start 2026-06-04 --plan-days 14
  - python3 run.py --stage brief --target-date 2026-06-04 --slot both --force
  - Run the premise-guard subagent on the generated Day 10 brief/script — it MUST return PASS.
  - Confirm: no "google/GBP/ranking/algorithm" in output; plan rotation ≈60% AU; currency
    correct ($ AU/NYC, £ London); Bella not localised as Australian; the 7 quality gates pass;
    the Elixir is human, not the product.
  Then summarise every file you changed and anything you skipped or need confirmed.
```

---

## Notes for you (not for the paste)
- The only thing the other project can't decide for itself is the **voice ID** — it'll surface both; you confirm which matches your live ElevenLabs voice.
- `linh` and `kostas` will also need **avatar reference PNGs** generated to your `IMAGE_GENERATION_SPEC` before they can appear in video, and a profile block in `FRIENDS_AND_CIAO_PROFILES.md`. The handoff covers the data; the images are a separate generation pass — tell me if you want me to draft those image prompts.
