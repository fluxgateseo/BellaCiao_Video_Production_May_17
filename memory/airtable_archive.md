---
name: Airtable as the staged workflow control surface
description: Airtable schema for the staged approval workflow — Calendar, ContentCalendar, Briefs, Scripts. Each gated table has a verdict/status field that gates the next stage.
type: project
---

> **Note (2026-04-10):** This memory was originally written when Airtable was archive-only. The user has since explicitly requested approval gates as the control surface for the pipeline ("I want to verify main days of the year, story to tell and input before we create scripts"). Approval gates are now IN scope for this project. The Scripts table remains archive-only (`status` = draft/archived), but Calendar, ContentCalendar, and Briefs are now full approval gates.

Airtable is now the **manual control surface** for the staged pipeline. Five tables, three with verdict gates:

**Base**: `Bellaciao Scripts` (base id stored in `.env` as `AIRTABLE_BASE_ID`)
**Tables**: `Calendar`, `ContentCalendar`, `Briefs`, `Scripts` (+ `TrendSignals` for the Apify scout)
**Module**: [airtable_sync.py](../airtable_sync.py) — push/fetch/update helpers per table
**Wired into**: `run.py` via `--stage calendar/plan/brief/write`. Each stage refuses to advance unless the upstream verdict is approved (`--force` to bypass).
**Library**: `pyairtable>=2.3.0` (in requirements.txt)

## The four verdict gates

| Table | Verdict values | Set by | Read by |
|---|---|---|---|
| `Calendar` | unreviewed → scheduled / skip | user manually | brief stage (only scheduled events become event_day/event_eve anchors) |
| `Briefs` | unreviewed → good / reject / rewrite_needed | user manually | write stage (only good briefs become scripts) |
| `Scripts` | draft / archived (no approval — write is final) | pipeline | nobody — archive only |

**Column schema** (names are case-sensitive — a typo = `INVALID_REQUEST_UNKNOWN_FIELD_NAME`):

| Column | Type | Notes |
|---|---|---|
| `episode_id` | Single line text | Primary field |
| `generated_at` | Date (with time ON) | ISO string |
| `day` | Number (Integer) | |
| `friend` | **Single select** | 8 options: `naomi`, `sal`, `jake`, `enzo_maria`, `yasmin`, `danny`, `arun_priya`, `sophie` |
| `pillar` | Number (Integer) | |
| `calendar_event` | **Single line text** | MUST NOT be Single select — see gotcha below |
| `score` | Number (Decimal, 2dp) | |
| `story_spine` | Long text | |
| `video_script` | Long text | |
| `video_script_ssml` | Long text | |
| `caption` | Long text | |
| `scene_brief` | Long text | Pushed as JSON-stringified |
| `status` | **Single select** | ONLY `draft` and `archived`. DO NOT add `pending`/`approved`/`rejected` |
| `notes` | Long text | Free-form |

**Gotcha — `calendar_event` must be Single line text, not Single select.** Airtable's "add column" flow nudges toward Single select, and the existing calendar has 40+ event names — if the column is Single select, pushing a script whose event isn't already a known option raises `INVALID_MULTIPLE_CHOICE_OPTIONS: Insufficient permissions to create new select option`. The fix is to change the column type to Single line text, NOT to grant `schema.bases:write` to the PAT.

**Gotcha — Scripts `status` stays two options.** The Scripts table itself is still archive-only (draft/archived). Approval gating happens UPSTREAM (Calendar/ContentCalendar/Briefs). Once a script is generated, it's final — don't add `approved/rejected` to the Scripts table; that workflow lives in the Briefs table verdict instead.

**PAT scopes**: `data.records:read`, `data.records:write`, `schema.bases:read` (no write). Token is stored in `.env` as `AIRTABLE_PAT`.

**Why:** Airtable is now the user's manual review surface for the entire pipeline. They review Calendar / ContentCalendar / Briefs in Airtable and mark verdicts; the pipeline reads those verdicts and only advances when upstream is approved. The Scripts table remains a searchable archive of finished work.

**How to apply:** When the user asks to add a field, check which table it belongs in. Calendar/ContentCalendar/Briefs accept new fields freely (review surface). Scripts stays slim (archive). Always push via the typed helpers in `airtable_sync.py` — never write direct HTTP calls, never bypass the upsert-by-id logic, and never auto-set verdicts to anything other than `unreviewed` (only the human moves them forward).
