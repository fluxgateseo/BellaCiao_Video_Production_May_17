# Build Guide — Recreating the Script Engine from Scratch

*Last updated: 2026-04-10*

This guide is for someone who has the four design docs
([PROJECT_SCOPE.md](PROJECT_SCOPE.md), [PIPELINE.md](PIPELINE.md),
[BRAND_BIBLE.md](BRAND_BIBLE.md), and this file) and wants to build the
engine in a fresh repo. It assumes Python 3.11+ and basic familiarity with
LLM APIs.

## Prerequisites

- Python 3.11+
- An Anthropic API key (required — Claude Opus is the judge)
- At least one of: OpenAI, Gemini, DeepSeek (for blind multi-model competition)
- Optional: an Apify account + token (for trend signals)

## Step 1 — Repo skeleton

```bash
mkdir script_engine && cd script_engine
mkdir -p data data/jobs docs

python3 -m venv .venv
source .venv/bin/activate
```

Create `requirements.txt`:

```
anthropic>=0.40.0
openai>=1.50.0
google-generativeai>=0.8.0
requests>=2.31.0
python-dotenv>=1.0.0
```

```bash
pip install -r requirements.txt
```

Create `.env.example`:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...

APIFY_TOKEN=apify_api_...
APIFY_YT_ACTOR_ID=h7sDV53CddomktSi5
APIFY_IG_HASHTAG_ACTOR_ID=
APIFY_IG_REEL_ACTOR_ID=
```

Then `cp .env.example .env` and fill in real values.

## Step 2 — Brand bible (`brand.py`)

This is the single source of truth. Build it from
[BRAND_BIBLE.md](BRAND_BIBLE.md). The constants you need:

| Constant | Type | Source in BRAND_BIBLE.md |
|---|---|---|
| `MISSION` | str (multiline) | §1 |
| `BELLA_BRIEF` | str (multiline) | §2 |
| `DISNEY_UNIVERSE` | str (multiline) | §4 |
| `DUAL_FRAMEWORK` | str (multiline) | §5 |
| `SENSORY_ARC` | str (multiline) | §5 (Sensory 3-Act Arc) |
| `PILLARS` | dict[int, dict] | §8 |
| `ENEMIES` | dict[str, str] | §6 |
| `ALLIES` | dict[str, str] | §7 |
| `PILLAR_ENEMIES` | dict[int, list[str]] | §6 (mapping table) |
| `CONTENT_RULES` | str (multiline) | §10 |
| `DURATION_GUIDE` | str (multiline) | §11 |
| `MODEL_ROLES` | dict[str, str] | PIPELINE.md §3.2 (4 voices) |
| `SCORING_WEIGHTS` | dict[str, float] | §14 |
| `PASS_THRESHOLD` | float = 9.5 | §14 |
| `NEAR_PERFECT` | float = 9.6 | §14 |
| `MAX_ROUNDS` | int = 3 | §14 |
| `MAX_TOKENS` | int = 2000 | — |
| `SEVEN_GATES` | str (multiline) | §15 |

**Rule**: every constant in `brand.py` must trace back to a numbered section
in `BRAND_BIBLE.md`. If you add a constant, add the section first.

## Step 3 — Data files

Copy these from the source pipeline (or build fresh from BRAND_BIBLE.md §9
and the calendar event spec in PIPELINE.md):

```bash
data/friends.json   # 8 records, schema in PIPELINE.md "Data contracts"
data/calendar.json  # 40+ events, schema in PIPELINE.md "Data contracts"
```

The friends file is the most labour-intensive part. Each friend needs a
canonical physical description (locked, never varies), a sensory food hook,
an archetype, a story angle, an enemy archetype, a pillar affinity, and an
avatar context. Get these wrong and the writers will produce inconsistent
characters across runs.

## Step 4 — Apify scout (`apify_scout.py`)

Build per [PIPELINE.md §"Stage 1"](PIPELINE.md). Public API:

```python
def run() -> dict             # full scrape + analyse cycle, saves trend_signals.json
def get_trend_context() -> str  # formatted prompt block for strategy.py (24h freshness)
```

Internal helpers you'll need:

- `_run_actor(actor_id, input_data, timeout)` — POST to Apify, poll until
  SUCCEEDED, fetch dataset items
- `scrape_youtube()`, `scrape_instagram_hashtags()`, `scrape_instagram_reels()`
- `_analyze_with_claude(yt, ig, calendar)` — Claude Haiku synthesis with
  strict JSON output (handle markdown fences and brace-balanced fallback)

**Failure tolerance** is critical here. Apify actors fail constantly. Every
function must catch its own exceptions and return `[]` so the rest of the
pipeline keeps moving.

## Step 5 — Strategy (`strategy.py`)

Build per [PIPELINE.md §"Stage 2"](PIPELINE.md). Public API:

```python
def upcoming_events(days_ahead: int = 30) -> list
def generate_brief(format_type: str, pillar: int = None, force_friend: str = None) -> dict
def get_friend(friend_id: str) -> dict
```

The hardest part is the calendar resolver:

```python
def _next_occurrence(event: dict, today: date) -> Optional[date]:
    # handle "fixed", "nth_weekday", "cultural" event types
    # for nth_weekday (e.g. Super Bowl = 2nd Sunday in Feb), use _nth_weekday_of_month
    # for cultural (e.g. recurring weekday), use modulo arithmetic
```

Then `generate_brief()` builds the Opus prompt by concatenating:
- `brand.MISSION`
- `brand.DURATION_GUIDE`
- formatted upcoming events (with TIER badge, days_until, content_angles, in-window flag)
- `apify_scout.get_trend_context()`
- formatted friends list (one per line with id, name, location, hook, enemy, angle)
- `brand.ENEMIES`, `brand.ALLIES`, `brand.PILLARS` as JSON
- the brief schema as a strict output format

Use Claude Opus (`claude-opus-4-6`) with `max_tokens=2000`. Parse the JSON
defensively (strip markdown fences, find outermost `{...}` if needed).

## Step 6 — Engine (`engine.py`)

The heart of the project. Build per [PIPELINE.md §"Stage 3"](PIPELINE.md).
Public API:

```python
def write_script(brief: dict, dry_run: bool = False) -> dict
```

Internal building blocks (build them in this order):

### 6.1 — Prompt builder
```python
def build_generation_prompt(brief, rewrite_notes="", round_num=1) -> str
```
Concatenates all the brand bible sections + the cast (HERO/SHADOW/ALLY) +
the SECTION 1/2/3/4 output spec + (optional) rewrite notes.

### 6.2 — Writer functions (one per model)
```python
def _claude(prompt) -> str    # Claude Sonnet 4.6 with restraint role
def _gpt4o(prompt) -> str     # GPT-4o with architect role
def _gemini(prompt) -> str    # Gemini 2.0 Flash with cinematic role
def _deepseek(prompt) -> str  # DeepSeek with inside-angle role
```

Each prepends `brand.MODEL_ROLES[name]` to the system prompt. Each catches
its own errors so a missing API key doesn't kill the parallel run.

### 6.3 — Parallel runner
```python
def generate_scripts_parallel(prompt) -> dict[str, str]
```
Uses `concurrent.futures.ThreadPoolExecutor`. Builds the task list from
whichever clients are configured. Assigns blind labels A/B/C/D in order.
Returns `{label: script}`. Skips failures, raises if all fail.

### 6.4 — Judge
```python
def judge_scripts(scripts) -> dict
```
Concatenates all candidates into a single Opus prompt with the
`JUDGE_PROMPT` (the 9 weighted dimensions). Parses defensive JSON.

### 6.5 — Section extractor
```python
def extract_section(text, label) -> str
```
Walks the script line by line, returns text between SECTION X header and
the next SECTION header.

### 6.6 — 7-gate check
```python
def run_7_gate(script_text) -> tuple[bool, dict]
def gate_pass_count(gates) -> int
```
Runs the 7 gates against SECTION 2 only (not the whole blob — captions
naturally have more prose and would fail gate 5 every time).

### 6.7 — Rewrite feedback builder
```python
def build_rewrite_notes(verdict, prev_score) -> str
```
Per-dimension breakdown with ❌ WEAK / ⚠️ THIN / ✓ strong markers. Names
the weak dimensions explicitly. Surfaces judge's `best`/`improve` notes.
Tells the model "surgical fixes only".

### 6.8 — Polish pass
```python
def polish_script(candidate, verdict, target_duration) -> tuple[str, bool]
```
Surgical Opus pass on the 2 weakest non-binary dimensions. Validates that
the output still has all 4 SECTION headers — reverts to original if not.

### 6.9 — Main pipeline
```python
def write_script(brief, dry_run=False) -> dict
```

The orchestration loop:

```
for round in 1..MAX_ROUNDS:
    prompt = build_generation_prompt(brief, rewrite_notes, round)
    scripts = generate_scripts_parallel(prompt)
    verdict = judge_scripts(scripts)
    if score >= PASS_THRESHOLD and rec in (WINNER, SYNTHESISE):
        gate_pass, gates = run_7_gate(winner_script)
        if gate_pass or near_perfect_override:
            return _build_output(...)
        else:
            rewrite_notes = "fix only these gate failures"
    else:
        rewrite_notes = build_rewrite_notes(verdict, score)
    track best_score, best_candidate, best_verdict, best_round

# Polish pass if no round cleared threshold
if no final_output and best_candidate and best_score < PASS_THRESHOLD:
    polished, ok = polish_script(best_candidate, best_verdict, target_duration)
    if ok:
        v2 = judge_scripts({"A": polished})
        if v2.score > best_score:
            best_candidate, best_score, best_verdict = polished, v2.score, v2
            if v2.score >= PASS_THRESHOLD and run_7_gate(polished)[0]:
                return _build_output(...)

# Best-effort fallback
if no final_output and best_candidate:
    return _build_output with score < PASS_THRESHOLD

return {"status": "ESCALATED"}
```

### 6.10 — Output assembler
```python
def _build_output(episode_id, brief, candidate, verdict, score, round_label, gates,
                  near_perfect_override=False) -> dict
```
Builds the job dict and runs `extract_section` four times to populate
`story_spine`, `video_script`, `caption`, `scene_brief`. Saves to
`data/jobs/{episode_id}.json`.

## Step 7 — CLI (`run.py`)

Single entry point that ties the three stages together:

```python
def main():
    parse args (--format, --pillar, --friend, --no-scout, --scout-only,
                --brief-only, --dry)

    if not args.no_scout:
        try:
            apify_scout.run()
        except Exception as e:
            print warning, continue
    if args.scout_only: return

    brief = strategy.generate_brief(args.format, args.pillar, args.friend)
    if args.brief_only: print and return

    out = engine.write_script(brief, dry_run=args.dry)
    if args.dry: return

    print final score + spoken script + job path
    sys.exit(0 if score >= 9.5 else 2)
```

## Step 8 — Verify

```bash
# Syntax check
python3 -m py_compile brand.py apify_scout.py strategy.py engine.py run.py

# Dry run (no API calls — just builds the prompt and prints it)
python3 run.py --no-scout --dry --pillar 1 --friend jake

# Brief only (1 Opus call, no writers)
python3 run.py --no-scout --brief-only --pillar 2 --friend yasmin

# Full run with no Apify
python3 run.py --no-scout --pillar 1 --friend jake

# Full auto
python3 run.py
```

A successful full run should produce:
1. `data/trend_signals.json` (if Apify is configured)
2. `data/strategy_brief.json`
3. `data/jobs/bella_<friend>_p<pillar>_<timestamp>.json`
4. A console score line: `FINAL SCORE: 9.6X/10`
5. The spoken video script printed to stdout

## Step 9 — Test the failure modes

| Force this | Expected behaviour |
|---|---|
| Unset all writer keys except Anthropic | One writer (Claude Sonnet) runs, judge still works |
| Unset Apify token | Scout returns empty, strategy uses calendar only |
| Empty `data/calendar.json` | Strategy returns evergreen brief |
| Force a banned word in the prompt | Judge marks zero-sell binary as 0, recommendation = REWRITE |
| Force a 60s duration | Word count target = 150, writers must produce a longer script |

## Step 10 — Add to CLAUDE.md (or your project's instruction file)

Tell future operators (and Claude Code) where the source of truth lives:

```markdown
## Script Engine
- Brand bible (machine): script_engine/brand.py
- Brand bible (human): script_engine/docs/BRAND_BIBLE.md
- Pipeline spec: script_engine/docs/PIPELINE.md
- Project scope: script_engine/docs/PROJECT_SCOPE.md
- CLI: python3 script_engine/run.py
- Outputs: script_engine/data/jobs/{episode_id}.json
```

## Build checklist

- [ ] `brand.py` builds without errors and every constant traces to a section in `BRAND_BIBLE.md`
- [ ] `data/friends.json` has 8 friends with all required fields
- [ ] `data/calendar.json` has at least 20 events covering all 12 months
- [ ] `apify_scout.py` runs without crashing even with no Apify token
- [ ] `strategy.py` produces a valid brief from any in-window event
- [ ] `engine.py --dry` prints a complete prompt without calling any API
- [ ] `engine.py` runs end-to-end with at least 1 writer + Opus judge configured
- [ ] A full `run.py` invocation produces a `data/jobs/{id}.json` with score ≥ 9.5
- [ ] All 7 gates execute and return JSON
- [ ] The polish pass triggers when score is < 9.5 after 3 rounds
- [ ] `near_perfect_override` triggers when score ≥ 9.6 and gates are 6/7
- [ ] Best-effort fallback ships a sub-9.5 script when nothing better exists
- [ ] Hard failure produces `{"status": "ESCALATED"}` and exit code 2

## Anti-patterns (do NOT do these)

- ❌ Adding video or audio code to this project. Fork instead.
- ❌ Caching scripts across runs by brief hash. Each run is fresh — let the
  judge re-evaluate every time. (The full pipeline has a script cache; this
  engine deliberately does not.)
- ❌ Mocking the Opus judge in production. The judge IS the quality bar.
- ❌ Hardcoding a duration. The strategy stage chooses per brief.
- ❌ Adding a new character outside the 8-friend roster without updating
  `BRAND_BIBLE.md` §9 first.
- ❌ Lowering `PASS_THRESHOLD` to make CI pass. The threshold is the
  product, not the test.
- ❌ Putting Italian words in scripts. Bella is American English.
- ❌ Letting Bella pitch. Even once. Even subtly. Zero-sell is binary.
