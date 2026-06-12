"""
brand.py — Bellaciao.ai brand bible distilled into prompt-ready constants.

Extracted from:
  - video_pipeline/MASTER_INSTRUCTIONS.md (Brand Bible v5)
  - video_pipeline/agent_3_content.py (multi-model storytelling engine)
  - video_pipeline/skill.md (Bella persona & voice)

Single source of truth for the script_engine. Update here when the brand bible
changes; do NOT duplicate constants in other modules.
"""

# ─── PROJECT MISSION & GOALS (from MASTER_INSTRUCTIONS §1) ──────────────────
MISSION = """
Bellaciao.ai is an AI receptionist for restaurants and hospitality businesses.
The job of this content engine is to convert restaurant owners in Australia,
the USA, and the UK into leads.

PRIMARY METRIC:   Demo bookings + trial activations per week.
SECONDARY METRIC: DM trigger keywords ("BELLA" / "TRIAL" / "DEMO") per week.

Game: Authority Building (primary) + Explanatory Product (secondary).
Outlier criteria: saves rate >3% OR DM trigger activated — NEVER view count alone.
Markets: Australia · United States · United Kingdom
Cities:  New York · London · Melbourne (no others, ever)
"""

# ─── BELLA — THE MENTOR (non-negotiable character rules) ─────────────────────
BELLA_BRIEF = """
BELLA — THE MENTOR (non-negotiable character rules)
====================================================
Italian father, Irish mother, raised in the US. 25 years old.
ElevenLabs Voice: 9DxYbhovJvj6zRtn0Pvc
Voice: Native American English. Sharp, warm, witty, never robotic.

PHYSICAL APPEARANCE (canonical, never vary):
  - Long dark brown wavy hair with caramel highlights
  - BLUE eyes (non-negotiable)
  - Warm golden-tan olive skin
  - Small gold stud earrings
  - Always looks like a real person, not a model or AI avatar

ARCHETYPE: The Mentor
  She has been on this road. She does not fix things.
  She gives the hero the confidence to fix things themselves.
  She notices what nobody else notices.
  She is never the story. She is the reason the story gets told.
  She NEVER pitches a product, NEVER teases a solution, NEVER sells in the body.
  (Narrative restraint — not a visual rule. Visually she ALWAYS looks into the
  lens and talks to camera per BELLA_MASTER_BIBLE.md §0 Camera Address Mandate.)

CIAO — THE HERALD (Italian Greyhound):
  Appears ONCE per story. Marks the turning point.
  He does NOT speak — he barks externally and thinks out loud (loud dramatic
  inner monologue, big voice in a tiny dog).
  When Ciao is calm — things are okay. When Ciao moves — something matters.
  His appearance must feel inevitable, never inserted.
"""

# ─── DISNEY CHARACTER UNIVERSE ───────────────────────────────────────────────
DISNEY_UNIVERSE = """
THE FULL DISNEY CHARACTER UNIVERSE (updated 2026-04-11, revised same day)
==========================================================================
HERO    → The restaurant owner (the Friend from data/friends_db.json)
MENTOR  → Bella — ALWAYS PHYSICALLY ON SCREEN in every video.
          She narrates, she's visible, she has her own avatar shots.
          She gives the hero confidence; she never steals the moment.
HERALD  → Ciao (Italian Greyhound) — REQUIRED by default. Marks the
          turning point ONCE per video. Absence is allowed ONLY when the
          brief sets `ciao_allowed_absent: true`; the Quality Supervisor
          rejects any script missing Ciao without that explicit override.
SHADOW  → The Enemy — a force, never a human in scene.
ALLY    → The Unexpected Support — OPTIONAL, on-camera for high-impact
          moments only. Most videos do NOT use an ally on camera. When
          present, the ally SPEAKS (labelled dialogue). One ally maximum.

CAST PATTERNS — every video uses exactly ONE pattern
======================================================
PATTERN A (1-to-1 base, +ally optional): Bella + 1 solo friend + Ciao (when required)
  Friends: Naomi, Sal, Jake, Yasmin, Danny, Sophie
  Ally on camera is OPTIONAL — add only when the story specifically needs it.

PATTERN B (1-to-2 + kids, +ally optional): Bella + 1 couple + their child(ren) + Ciao (when required)
  The couple counts as ONE friend unit (they finish each other's sentences).
  Children have VISUAL presence only — they NEVER speak.
  Couples: Enzo & Maria (+ Luca, 8), Arun & Priya (+ Anaya, 3)
  Ally on camera is OPTIONAL — same rule as Pattern A.

SPECIAL CASE — Sophie (solo parent):
  Default Pattern A (Sophie alone with Bella).
  Pattern B variant allowed when the brief is about parent-and-child:
  Bella + Sophie + Mia (5). Mia has visual presence only.
  Sophie can also have an ally on camera when the story needs it.

ALLY ON CAMERA — rules (added 2026-04-11)
==========================================
  - OPTIONAL per video. Default is "no ally in scene". Only include when
    the story specifically benefits from the ally's physical presence.
  - ONE ally maximum per video — never two.
  - When in scene, the ally SPEAKS (labelled dialogue, e.g. SOUS_CHEF:).
  - Ally archetype must be drawn from brand.ALLIES — no new inventions.
  - The ally does NOT replace the friend or couple — they augment.

HARD RULES (never violate):
  - NEVER more than one friend (or couple) per video
  - NEVER more than one ally per video
  - NEVER mix friends across videos (no Jake-and-Naomi crossovers)
  - Children NEVER speak — visual presence only
  - The Shadow (enemy) is always a force, never a person in frame

(History: the original session allowed "1 ally + 1 child as optional cast".
 A mid-session rewrite on 2026-04-11 flipped this to "NEVER an ally as a
 third human in scene" — but that flip was reversed the same day. The ally
 is back on the table — as OPTIONAL, high-impact-only, speaking cast when
 physically present. Future sessions: do NOT re-retire the ally rule
 without an explicit user request.)
Restraint is what makes each character feel real.
"""

# ─── DUAL STORY FRAMEWORK (Pixar Spine + Vogler Inner Journey) ───────────────
DUAL_FRAMEWORK = """
ENGINE 1 — PIXAR STORY SPINE (the plot engine — must pass the 8-sentence test)
  Once upon a time...    Who, where, what made it good.
  Every day...           The specific daily routine.
  But one day...         The disruption — ONE specific catalyst.
  Because of that...     First consequence — ONE specific thing.
  Because of that...     Deeper consequence.
  Because of that...     The lowest point.
  Until finally...       The turning point.
  And ever since then... The new world. Small. Specific. Earned.

ENGINE 2 — VOGLER INNER JOURNEY (the character engine)
  Ordinary World → "I am good at this."
  The Call       → "Something is breaking."
  The Ordeal     → "I don't know if I can do this anymore."
  The Elixir     → "I remember why I started."

THE ELIXIR IS NEVER A PRODUCT. NEVER A SYSTEM. NEVER A FEATURE.
It is always: a Sunday off. A staff member who stayed. A father's hands.
"""

# ─── SENSORY 3-ACT ARC (video structure) ─────────────────────────────────────
SENSORY_ARC = """
SENSORY 3-ACT ARC (video structure)
===================================
Act 1 — SENSORY HOOK (0-3s)
  Vivid food detail from the friend's restaurant. Smell, sound, texture.
  ONE sentence. Physical. Immediate. Stops the scroll.

Act 2 — OPERATIONAL CONFLICT (~60% of duration)
  Specific pain point involving the featured friend and the Enemy archetype.
  Recognisable, real, never generic. The audience leans in because they have
  lived it.

Act 3 — BELLA & CIAO PAYOFF
  Bella and Ciao handle the chaos. The friend regains their "Dining Room Focus".
  End on what the friend got back — small, human, earned.
"""

# ─── CONTENT PILLARS ─────────────────────────────────────────────────────────
PILLARS = {
    1: {"theme": "Operational",  "context": "busy/bar",      "summary": "Phone chaos, missed calls, no-shows"},
    2: {"theme": "Empathy",      "context": "kitchen/calm",  "summary": "Owner exhaustion, staff burnout, human cost"},
    3: {"theme": "Business",     "context": "sharp/pro",     "summary": "ROI, P&L, booking economics"},
    4: {"theme": "Customer",     "context": "calm/table",    "summary": "Regulars, walk-ins, the invisible loss"},
    5: {"theme": "Legacy",       "context": "kitchen/table", "summary": "Family transition, tradition vs change, the lease"},
}

# ─── ENEMY (SHADOW) ARCHETYPES ───────────────────────────────────────────────
# Canonical enemy universe per Master Bible v2 §8. Every story has ONE enemy —
# a force, never a person. The GBP/SEO-era enemies are retired and must never
# return: the_invisible_ranking, the_algorithm, the_social_media_trap.
ENEMIES = {
    "the_missed_call":          "The phone rings out during service. Nobody has a free hand. The table goes elsewhere.",
    "the_after_hours_booking":  "A call or enquiry after close. Booked by no one. Gone by morning.",
    "the_no_show":              "An empty table, two menus open, a booking that took no deposit.",
    "the_cover_fee":            "The OpenTable invoice: base + per-cover + service fee, bleeding the margin monthly.",
    "the_language_gap":         "A guest who speaks Cantonese, Italian, Greek, or Vietnamese — and a line that can't answer them.",
    "the_quandoo_exit":         "The 'Quandoo is closing' email. A booking system disappearing before the busy season.",
    "the_system_failure":       "The booking platform crashes at 7pm Saturday. 120 covers in the system. Gone.",
}

# ─── ALLY ARCHETYPES ─────────────────────────────────────────────────────────
ALLIES = {
    "the_staff_member_who_stayed": "The sous chef who ran the pass when no one else could.",
    "the_regular_who_noticed":     "The guest who knew something was wrong before the owner did.",
    "the_partner_who_held_it":     "The one who stayed calm when the other couldn't.",
    "the_father_who_showed_up":    "Flew across the world. Put on an apron. Said nothing about the books.",
    "ciao_alone":                  "Ciao. Head in a lap. Still. Thinking loudly: 'This one needed me.' That is enough.",
}

# Pillar → suggested enemies (which shadows fit each pillar). Canonical enemies only.
PILLAR_ENEMIES = {
    1: ["the_missed_call", "the_after_hours_booking", "the_no_show", "the_system_failure"],
    2: ["the_missed_call", "the_after_hours_booking"],
    3: ["the_cover_fee", "the_no_show", "the_system_failure"],
    4: ["the_missed_call", "the_language_gap"],
    5: ["the_quandoo_exit", "the_language_gap"],
}

# ─── MARKETS & CITIES ────────────────────────────────────────────────────────
# CITIES maps each market to BELLA's home city in it. Bella's three cities are
# Melbourne (home base — she studied at uni there and lives there now), New York
# City and London; these drive her generic city rotation in logical_gate.py.
# Friend/venue cities are broader: AU venues also include Sydney (Linh) and
# Adelaide (Kostas), scheduled via the content calendar rather than the generic
# rotation. Every venue city's currency lives in CURRENCY_MAP below.
MARKETS = ("AU", "US", "UK")
CITIES  = {"AU": "Melbourne", "US": "New York City", "UK": "London"}

# Authoritative currency map for every venue city (Bella's three + the AU
# friends' cities). Read from friends_db.json[friend].currency at runtime —
# this dict is for validation only.
CURRENCY_MAP = {
    "Melbourne":     "$",
    "Sydney":        "$",
    "Adelaide":      "$",
    "New York City": "$",
    "London":        "£",
}

# ─── CONTENT RULES (BANNED WORDS + HARD RULES) ──────────────────────────────
CONTENT_RULES = """
CONTENT RULES (non-negotiable)
- English only. No Italian, Arabic, or any other language in scripts.
- Currency must match the friend's city: $ for Australian cities (Melbourne,
  Sydney, Adelaide) and New York, £ for London.
  NEVER apply a different currency than the one passed in the brief.
- Venue locations: Melbourne, Sydney, Adelaide (AU), New York City (US),
  London (UK) — specific neighbourhoods always. Bella's own three cities are
  Melbourne (home base), New York City and London; Sydney and Adelaide are
  friends' cities (Linh, Kostas), never Bella's.
- Bella speaks in first person when narrating.
- Bella is a human character in the content universe — 25, NYC-born
  Irish-Italian, internationally raised, now Melbourne home-base (she
  studied at uni there; Ciao is her dog). She is the friend who figured
  out the missed-calls-and-lost-bookings problem and can't shut up about
  it. International by design — never localised as Australian.
  She never references being AI in scripts.
- In the BODY and at the ELIXIR, Bella returns to observational first-person
  narration. She NEVER pitches the product, NEVER teases a feature solution,
  and NEVER sells outside the hook zone.
- VISUAL RULE (separate axis, ALWAYS on): Bella looks directly into the lens and
  talks to camera in every shot she appears in — hook, body, elixir, close.
  This is the Camera Address Mandate per BELLA_MASTER_BIBLE.md §0. Her gaze is
  to-camera throughout; the narrative restraint above is about WHAT she says,
  not WHERE she looks.
- The Elixir is always human. Never a product. Never a feature.
- Friend and restaurant names are ALWAYS fictional.
- The sensory_hook (spoken by Bella) MUST open every piece. One sentence.
  Insider tone. Restaurateur-pain-specific.
- The sensory_hook MUST come from the friend's `sensory_hooks` array in
  friends_db.json — never invent a new one.
- Every script must name a friend with restaurant type + city in the hook.
- Every script must reference the driving calendar event by name or context.
- Hashtags: exactly 5, woven into the closing line — never listed separately.
  Always include #bella #bellaciao #ciaobella.

BANNED WORDS (instant rewrite):
  game-changer, seamless, fast-paced, revolutionise, leverage, empower,
  transform, unlock, journey (as metaphor), passionate, curated, innovative,
  cutting-edge, state-of-the-art, algorithm, "in today's fast-paced world",
  "the future of", "as a restaurant owner", "at the end of the day"
- RETIRED PREMISE (instant rewrite): never frame the problem as SEO, Google
  ranking, Google Business Profile, reviews, or "getting found on Google".
  The channel is about missed calls and lost bookings, never visibility.
- No corporate language. No startup language. Restaurant language only.
"""

# ─── FORBIDDEN ENDINGS ───────────────────────────────────────────────────────
# The closing line must be human, small, earned. These patterns are auto-fail
# in the Quality Supervisor's gate 4 (elixir) check.
FORBIDDEN_ENDINGS = [
    "and that's why",
    "and that's the difference",
    "the answer was",
    "the secret is",
    "if you want",
    "you need to",
    "imagine if",
    "what if",
    "this is how",
    "and so",
    "in conclusion",
    "the takeaway",
    "the lesson",
    "remember,",
    "remember:",
    "never forget",
    "ultimately,",
    "at the end of the day",
]

# ─── SSML GUIDE (used by Agent 7 — ssml_tagger.py) ───────────────────────────
# Voice ID: 9DxYbhovJvj6zRtn0Pvc (ElevenLabs)
SSML_GUIDE = {
    "voice_id": "9DxYbhovJvj6zRtn0Pvc",
    "rules": [
        # (pattern_description, tag_template, when_to_apply)
        ("punchy_fragment_break", '<break time="200ms"/>',
            "after a 1-3 word emphatic fragment"),
        ("rapid_knowledge_drop", '<prosody rate="fast">{}</prosody>',
            "wrap rapid factual sentences"),
        ("key_emphasis", '<emphasis level="strong">{}</emphasis>',
            "wrap a single insight word or key number"),
        ("conspiratorial_lean_in", '<prosody rate="medium" pitch="-5%">{}</prosody>',
            "wrap a confidential aside"),
        ("friend_voice_line", '<prosody rate="medium" pitch="+10%">{}</prosody>',
            "wrap any line spoken by a named friend"),
        ("elixir_payoff", '<prosody rate="slow">{}</prosody>',
            "ALWAYS wrap the elixir / payoff sentence — no exceptions"),
        ("sign_off", '<break time="300ms"/><prosody rate="medium">{}</prosody>',
            "ALWAYS prepend break + medium prosody to the sign-off (final sentence)"),
    ],
}

# ─── DURATION STRATEGY (Agent 1 chooses per video) ───────────────────────────
DURATION_GUIDE = """
DURATION STRATEGY — TWO CONTENT TYPES, TWO BANDS
=================================================
Bella publishes ONE story + ONE reel per day on Instagram. Each has its
own duration band. Strategy director picks the exact length within the
band based on the brief — never default.

STORIES — target ~30 seconds (soft ceiling, max ~33s)
  One beat, told well. ONE Bella-spoken hook (archetype: Pain / Insider /
  Myth-Buster) + ONE emotional reveal + ONE Bella observational close.
  NOT a stripped-down reel — stories are the moment a reel would build
  toward, isolated.
  No full Pixar arc. No Vogler journey. Ciao MAY appear briefly.
  Pacing: ~75 spoken words at 2.5 wps.

REELS — 30 to 60 seconds
  Full Pixar 8-sentence spine + Vogler inner journey + Ciao turning
  point + earned Elixir. At 30s the arc is tight; at 60s it has
  breathing room.
  Reels are NEVER under 30 seconds. If a "reel" comes in under 30s,
  it's miscategorised — promote it to a story.
  Pacing: 75–150 spoken words at 2.5 wps.

ElevenLabs natural pace: ~2.5 spoken words per second.
Word-count target = duration_seconds × 2.5 (±5).
"""

# ─── STORY SLOT SPEC (Instagram Story, ~30s) ─────────────────────────────────
STORY_SPEC = """
STORY SLOT — INSTAGRAM STORY
============================
Length: target ~30 seconds, hard ceiling 33 seconds.
Word count: ~75 spoken words at 2.5 wps.

A story is ONE beat, told well. It is the moment a reel would build
TOWARD, extracted and isolated. Think: the late-night realisation, the
single look exchanged across a kitchen, the one specific number that
lands with a thud.

REQUIRED:
  - ONE Bella-spoken hook in 0-3s (BELLA: direct-to-camera, archetype-aligned
    per the v1.8 doctrine: Pain / Insider / Myth-Buster; may acknowledge AI
    and name automation Bella owns)
  - ONE emotional reveal (the "that's me" moment) — BODY, observational
  - ONE Bella observational close — single sentence, NEVER a pitch outside
    the hook zone; ends with mandatory sign-off "I'm Bella — ciao for now."

OPTIONAL:
  - Ciao MAY appear, but only as a brief presence — no inner-monologue
    set-piece. If Ciao would dominate a 30s slot, save the moment for a reel.

FORBIDDEN:
  - Full Pixar 8-sentence spine (it doesn't fit in 30s without rushing)
  - Multi-scene structure
  - Before/after comparisons
  - Numbered lists or "3 things" framing
  - Any pitch, CTA, or feature-tease OUTSIDE the hook zone (the 0-3s Bella
    hook may name automation Bella owns; the body and close must not)

OUTPUT SECTIONS:
  SECTION 1 — Story beat (3-4 sentences max, internal only — not spoken)
  SECTION 2 — Spoken text (Bella's lines + any friend dialogue)
  SECTION 3 — Caption (single line + 3 woven hashtags)
  SECTION 4 — Scene brief JSON (1-2 clips max)
"""

# ─── REEL SLOT SPEC (Instagram Reel, 30-60s) ─────────────────────────────────
REEL_SPEC = """
REEL SLOT — INSTAGRAM REEL
==========================
Length: 30 to 60 seconds. NEVER under 30 seconds.
Word count: 75 to 150 spoken words at 2.5 wps.

A reel is the production-grade piece. It carries the full Bella
storytelling architecture and earns the saves, shares, comments, and
DMs that drive demo bookings.

REQUIRED:
  - Full Pixar 8-sentence story spine (Once upon a time → Every day →
    But one day → Because of that ×3 → Until finally → And ever since then)
  - Complete Vogler inner journey (Ordinary World → Call → Ordeal → Elixir)
  - Ciao turning point (appears ONCE, marks the turn, inner monologue)
  - Earned Elixir — small, human, never a product
  - Bella-spoken hook in 0-3s that stops the scroll before the second word
    (archetype: Pain / Insider / Myth-Buster; hook zone may acknowledge AI)

DURATION GUIDANCE:
  30-40s: tight arc, one specific ordeal, single Ciao beat
  40-50s: standard arc with breathing room, one ally moment
  50-60s: rich arc with reversal, deeper ordeal, earned elixir lands harder

OUTPUT SECTIONS:
  SECTION 1 — Full Pixar 8-sentence spine (internal only)
  SECTION 2 — Spoken video script (Bella + friend + Ciao internal monologue)
  SECTION 3 — Caption with 5 woven hashtags
  SECTION 4 — Scene brief JSON (3-6 clips depending on duration)
"""

# Convenience map so callers can do brand.SLOT_SPEC[slot]
SLOT_SPEC = {
    "story": STORY_SPEC,
    "reel":  REEL_SPEC,
}

# Duration bands per slot (used for default brief duration + pacing gate tolerance)
SLOT_DURATION = {
    "story": {"min": 8,  "target": 30, "max": 33},
    "reel":  {"min": 30, "target": 45, "max": 60},
}

# ─── MODEL ROLE INJECTIONS (per writer model — they each have a voice) ──────
MODEL_ROLES = {
    "claude":   "You write with restraint and precision. Every word earns its place. Less is always more.",
    "gpt4o":    "You are a narrative architect. You build stories with momentum and inevitability. You think in scenes, not sentences.",
    "deepseek": "You write from the inside. You find the angle nobody else would take. Truth written precisely is always more powerful than beauty.",
    "gemini":   "You see the cinematic frame before the sentence. Every line must imply a shot a director could light.",
}

# ─── JUDGE — WEIGHTED SCORING DIMENSIONS ─────────────────────────────────────
# v1.8+ retention-first rebalance: "sensory" key now scores SCROLL-STOP hook
# strength (Bella-spoken verbal hook + archetype coherence across the 5-surface
# hook stack). The internal key stays "sensory" for backward-compat with
# engine.py, quality_supervisor.py, hooks_library.py. Key semantics changed,
# schema did not.
SCORING_WEIGHTS = {
    "sensory":        0.25,  # Scroll-stop / Bella-spoken hook strength (was 0.20 sensory opening)
    "recognition":    0.20,  # Emotional recognition (was 0.25 — ceded 5pts to scroll-stop)
    "spine":          0.15,  # Pixar Spine momentum
    "enemy":          0.10,  # Enemy presence
    "transformation": 0.10,  # Vogler inner transformation
    "bella":          0.05,  # Bella as mentor (not dominant)
    "ciao":           0.05,  # Ciao turning point
    "elixir":         0.10,  # The Elixir (small, human, earned)
    "zero_sell":      0.05,  # BINARY — any pitch in BODY/Elixir = automatic 0 (hook zone exempt)
}

# ─── PASS THRESHOLDS ─────────────────────────────────────────────────────────
PASS_THRESHOLD = 9.5     # weighted total required to ship
NEAR_PERFECT = 9.6       # score above which we override single picky gate failures
MAX_ROUNDS = 3           # rewrite rounds before polish pass
MAX_TOKENS = 2000

# ─── 7-GATE FINAL CHECK ──────────────────────────────────────────────────────
SEVEN_GATES = """
FINAL 7-GATE CHECK (run on SECTION 2 — the spoken video script)
Each gate is a quality check, not a perfectionism trap. PASS unless there is a CLEAR failure.

1. Does the first sentence stop the scroll before the second word?
2. Is the ordeal so specific it could only be THIS restaurant, THIS night?
3. Does Ciao's appearance mark a real turning point — not decoration?
   (He barks + thinks out loud, never speaks to characters.)
   FAIL if Ciao is absent unless the brief sets `ciao_allowed_absent: true`.
4. Is the Elixir small, human, earned — not a product or a fix?
5. Are there 3+ consecutive words that could be cut without losing meaning?
   (PASS = no obvious bloat. A single arguable trim is fine — fail only on real fluff.)
6. Can this run unchanged on ElevenLabs at natural pace within the target duration?
7. Would a restaurant owner share this at 11 PM without writing a caption?
"""
