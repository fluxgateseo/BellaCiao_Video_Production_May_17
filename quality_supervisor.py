"""
quality_supervisor.py — Quality Supervisor.

Owns the ship/block decision. Runs the 7-gate check on the winning script,
manages the rewrite feedback loop, and triggers the polish pass when MAX_ROUNDS
are exhausted without approval.

Public API:
  evaluate(verdict, brief)            → SupervisorDecision
  build_rewrite_feedback(verdict, …)  → RewriteFeedback
  polish_pass(best_script, weak, …)   → str   (Claude Opus surgical lift)

Reference: PROJECT_SCOPE.md §5, AGENTS.md "Quality Supervisor".
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

import brand

# Shared .env at the Bellaciao Content/ level — same file every project uses.
load_dotenv(Path(__file__).parent.parent / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

MODEL_OPUS = "claude-opus-4-6"


# ─── Decision types ──────────────────────────────────────────────────────────

class SupervisorStatus(str, Enum):
    APPROVED               = "APPROVED"
    NEAR_PERFECT_OVERRIDE  = "NEAR_PERFECT_OVERRIDE"
    REJECTED               = "REJECTED"


@dataclass
class RewriteFeedback:
    round: int
    failed_gates: list[str]            = field(default_factory=list)
    weak_dimensions: list[str]         = field(default_factory=list)
    specific_notes: dict[str, str]     = field(default_factory=dict)
    preserve: list[str]                = field(default_factory=list)
    director_note: str                 = ""
    forbidden_ending_triggered: bool   = False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_prompt_block(self) -> str:
        lines = [
            f"REWRITE FEEDBACK — Round {self.round}",
            f"  Director note: {self.director_note or '(none)'}",
        ]
        if self.failed_gates:
            lines.append("  Failed gates:")
            for g in self.failed_gates:
                lines.append(f"    - {g}: {self.specific_notes.get(g, '')}")
        if self.weak_dimensions:
            lines.append(f"  Weak dimensions to lift: {', '.join(self.weak_dimensions)}")
        if self.preserve:
            lines.append(f"  PRESERVE (do not touch): {', '.join(self.preserve)}")
        if self.forbidden_ending_triggered:
            lines.append("  ⚠ Forbidden ending detected — rewrite the closing line.")
        return "\n".join(lines)


@dataclass
class SupervisorDecision:
    status: SupervisorStatus
    score: float
    gate_pass_count: int
    gates: dict[str, dict]
    feedback: RewriteFeedback | None = None
    near_perfect_override: bool = False
    hard_blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status":                 self.status.value,
            "score":                  self.score,
            "gate_pass_count":        self.gate_pass_count,
            "gates":                  self.gates,
            "feedback":               self.feedback.to_dict() if self.feedback else None,
            "near_perfect_override":  self.near_perfect_override,
            "hard_blockers":          list(self.hard_blockers),
        }


# ─── Section extraction ──────────────────────────────────────────────────────

def _extract_section(full: str, label: str) -> str:
    if label not in full:
        return full
    lines, in_sec, out = full.split("\n"), False, []
    for line in lines:
        if label in line:
            in_sec = True
            continue
        if in_sec and line.startswith("SECTION ") and label not in line:
            break
        if in_sec:
            out.append(line)
    return "\n".join(out).strip()


# ─── Forbidden ending check (cheap, deterministic) ───────────────────────────

def _check_forbidden_ending(spoken: str) -> tuple[bool, str]:
    """Look for any FORBIDDEN_ENDINGS pattern in the last ~200 chars."""
    tail = spoken[-280:].lower()
    for phrase in brand.FORBIDDEN_ENDINGS:
        if phrase in tail:
            return True, phrase
    return False, ""


# ─── 7-gate check (Opus-driven) ─────────────────────────────────────────────

GATE_KEYS = [
    "scroll_stop",
    "specificity",
    "friend_voice",
    "elixir",
    "real_world_anchor",
    "duration",
    "shareability",
]

_GATE_PROMPT_TEMPLATE = """You are the Quality Supervisor for the Bella content engine.
Run the 7-gate quality check on the SPOKEN VIDEO SCRIPT below.
A gate is binary (pass or fail). Be CHARITABLE — only fail on a clear, named violation.

THE 7 GATES
{gate_descriptions}

SLOT (drives gate 6 + structural expectations)
  This piece is a {slot_upper}.
  Slot band: {slot_min}-{slot_max} seconds (target ~{slot_target}s)
  {slot_structural_rule}

CONTEXT FROM THE BRIEF (do NOT score these — they are reference for gate 5)
  Friend       : {friend}
  City         : {city}
  Calendar     : {event}
  Currency     : {currency}
  Target dur   : {duration}s  (≈ {target_words} words at 2.5 wps)

SPOKEN VIDEO SCRIPT
{script}

Return STRICT JSON, no markdown, no commentary:
{{
  "scroll_stop":       {{"pass": true,  "note": "…"}},
  "specificity":       {{"pass": true,  "note": "…"}},
  "friend_voice":      {{"pass": true,  "note": "…"}},
  "elixir":            {{"pass": true,  "note": "…"}},
  "real_world_anchor": {{"pass": true,  "note": "…"}},
  "duration":          {{"pass": true,  "note": "…"}},
  "shareability":      {{"pass": true,  "note": "…"}}
}}
"""

_GATE_DESCRIPTIONS = """\
1. scroll_stop        — Opening hook lands within the first 3 words.
2. specificity        — Problem could only be THIS restaurant on THIS night.
3. friend_voice       — Friend's voice is rhythmically distinct from Bella's.
4. elixir             — Closing is small, human, earned. NOT a product/feature/metric/forbidden phrase.
5. real_world_anchor  — Names a neighbourhood, calendar event, search term, or $/£ figure.
6. duration           — Spoken word count is within ±10% of (slot target × 2.5 wps).
                        Stories: ~75 words. Reels: 75-150 words. A story over 33s fails.
                        A reel under 30s fails — it's a story, not a reel.
7. shareability       — Reads like recognition of a lived experience, not advice."""

_STORY_STRUCTURAL_RULE = (
    "Story slot rules: ONE Bella-spoken hook (BELLA: direct-to-camera, archetype-aligned Pain/Insider/Myth-Buster, "
    "hook zone may acknowledge AI) + ONE emotional reveal (observational body) + ONE Bella observational close ending "
    "with \"I'm Bella — ciao for now.\" FAIL if it tries to fit a full Pixar 8-sentence spine (UNTIL FINALLY / "
    "AND EVER SINCE THEN) — that's a miscategorised reel. FAIL if Ciao gets a set-piece (he may appear briefly, "
    "never dominate). FAIL if the BODY pitches the product or sells a solution (hook zone exempt). "
    "NOTE: Bella's visual gaze is ALWAYS into-the-lens per BELLA_MASTER_BIBLE.md §0 Camera Address Mandate — "
    "this QS rule covers WHAT she says (narrative restraint), not WHERE she looks (always to-camera)."
)

_REEL_STRUCTURAL_RULE = (
    "Reel slot rules: MUST contain a full Pixar 8-sentence spine (or its rhythm) + Vogler arc + "
    "Ciao turning point + earned Elixir. FAIL if it reads like a single-beat story without an arc."
)


def _extract_json_block(raw: str) -> dict:
    raw = raw.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0]
    elif raw.startswith("```"):
        raw = raw.split("```", 2)[1].split("```", 1)[0]
    raw = raw.strip()
    # Find outermost {...}
    start = raw.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start:i + 1])
    raise ValueError("unbalanced braces in JSON response")


# ─── Hard blockers — Bella non-negotiables (memory: feedback_bella_and_ciao_mandatory) ───
#
# These sit *outside* the 7-gate LLM scoring. They are deterministic, cheap,
# and can never be overridden by a near-perfect score: if any fires, the
# supervisor REJECTS and caps the reported score so downstream polish runs
# instead of shipping the script.

HARD_BLOCKER_SCORE_CAP = 7.0

HARD_BLOCKER_KEYS = [
    "bella_labelled_dialogue",
    "bella_signoff_present",
    "ciao_herald_present",
]

_BELLA_TAG_RE = re.compile(r"(?mi)^\s*BELLA\s*:")
_MANDATORY_SIGNOFF_RE = re.compile(
    r"i\s*['’\u2018\u2019]?\s*m\s+bella\s*[\-\u2013\u2014]\s*ciao\s+for\s+now",
    re.IGNORECASE,
)
# Ciao presence in the spoken script: either CIAO: speaker tag (case-sensitive)
# or an all-caps CIAO action token (e.g. "[CIAO lifts his head]"). We
# intentionally do NOT match lowercase "ciao" so the sign-off word doesn't
# satisfy the herald check.
_CIAO_IN_SCRIPT_RE = re.compile(r"\bCIAO\b")

_CIAO_EMPTY_MOMENTS = {"", "none", "null", "n/a", "na", "-", "(none)"}


def _extract_scene_brief_json(script_text: str) -> dict:
    """Pull the SECTION 4 JSON block out of a full 4-section script.

    Returns {} on anything unparseable — callers treat empty as "no scene_brief
    hint available", which is the safe default for the Ciao herald check.
    """
    section = _extract_section(script_text, "SECTION 4")
    if not section:
        return {}
    start = section.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(section)):
        ch = section[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(section[start:i + 1])
                except (json.JSONDecodeError, ValueError):
                    return {}
    return {}


def run_hard_blockers(script_text: str, brief: dict) -> dict[str, dict]:
    """Deterministic non-negotiable checks; always runs, never calls the LLM."""
    spoken = _extract_section(script_text, "SECTION 2") or script_text
    scene_brief = _extract_scene_brief_json(script_text)

    results: dict[str, dict] = {}

    bella_tagged = bool(_BELLA_TAG_RE.search(spoken))
    results["bella_labelled_dialogue"] = {
        "pass": bella_tagged,
        "note": (
            "BELLA: labelled dialogue line present."
            if bella_tagged
            else "No BELLA: speaker tag — Bella must speak on-camera with a "
                 "'BELLA:' prefix on at least one line."
        ),
    }

    signoff_ok = bool(_MANDATORY_SIGNOFF_RE.search(spoken))
    results["bella_signoff_present"] = {
        "pass": signoff_ok,
        "note": (
            "Mandatory sign-off present."
            if signoff_ok
            else "Missing mandatory sign-off — final line must be "
                 "\"I'm Bella — ciao for now.\" verbatim."
        ),
    }

    if bool(brief.get("ciao_allowed_absent")):
        results["ciao_herald_present"] = {
            "pass": True,
            "note": "Ciao absence explicitly allowed via brief.ciao_allowed_absent.",
        }
    else:
        moment = str(scene_brief.get("ciao_moment") or "").strip().lower()
        moment_valid = moment not in _CIAO_EMPTY_MOMENTS
        script_ciao = bool(_CIAO_IN_SCRIPT_RE.search(spoken))
        ciao_ok = script_ciao or moment_valid
        results["ciao_herald_present"] = {
            "pass": ciao_ok,
            "note": (
                "Ciao herald present."
                if ciao_ok
                else "Missing Ciao herald — Ciao must appear at the turning "
                     "point. Override with brief.ciao_allowed_absent=true if "
                     "truly intentional."
            ),
        }

    return results


def hard_blocker_failures(blockers: dict[str, dict]) -> list[str]:
    """Return the subset of HARD_BLOCKER_KEYS that failed, in canonical order."""
    return [k for k in HARD_BLOCKER_KEYS if not blockers.get(k, {}).get("pass", False)]


def _slot_structural_precheck(spoken: str, slot: str) -> tuple[bool, str]:
    """
    Cheap deterministic check for slot miscategorisation. Runs BEFORE the
    LLM gate call so we can short-circuit obvious miscategorisations.

    Returns (passes, reason). passes=True means "no obvious problem".
    """
    word_count = len(spoken.split())
    if slot == "story":
        # Story budget: ~75 words at 2.5 wps. 33s ceiling = ~83 words ceiling.
        if word_count > 95:
            return False, (
                f"story slot but {word_count} words (~{word_count/2.5:.0f}s) — "
                f"exceeds 33s ceiling, miscategorised reel"
            )
        # Pixar full-spine markers — if we see UNTIL FINALLY *and* AND EVER SINCE,
        # this is reel structure compressed into a story slot.
        upper = spoken.upper()
        if "UNTIL FINALLY" in upper and "EVER SINCE" in upper:
            return False, "story has full Pixar 8-spine — that's a reel structure"
    elif slot == "reel":
        # Reel floor: 30s × 2.5 = 75 words. Anything noticeably under is a story.
        if word_count < 65:
            return False, (
                f"reel slot but only {word_count} words (~{word_count/2.5:.0f}s) — "
                f"below 30s floor, miscategorised story"
            )
    return True, ""


def run_seven_gates(script_text: str, brief: dict) -> dict[str, dict]:
    """Returns {gate_key: {"pass": bool, "note": str}}. Never raises."""
    spoken = _extract_section(script_text, "SECTION 2") or script_text

    # Slot-aware: pull the band from brand.SLOT_DURATION
    slot      = (brief.get("format") or "reel").lower()
    slot_band = brand.SLOT_DURATION.get(slot, brand.SLOT_DURATION["reel"])
    slot_rule = _STORY_STRUCTURAL_RULE if slot == "story" else _REEL_STRUCTURAL_RULE

    target_dur   = int(brief.get("target_duration_seconds") or slot_band["target"])
    target_words = int(target_dur * 2.5)

    prompt = _GATE_PROMPT_TEMPLATE.format(
        gate_descriptions    = _GATE_DESCRIPTIONS,
        slot_upper           = slot.upper(),
        slot_min             = slot_band["min"],
        slot_max             = slot_band["max"],
        slot_target          = slot_band["target"],
        slot_structural_rule = slot_rule,
        friend               = brief.get("friend", "?"),
        city                 = brief.get("city", brief.get("market", "?")),
        event                = brief.get("calendar_event", "(none)"),
        currency             = brief.get("currency", "$"),
        duration             = target_dur,
        target_words         = target_words,
        script               = spoken,
    )

    if _client is None:
        # Fail-soft: pass everything but flag in notes — keeps the pipeline
        # runnable in the offline-key configuration described in PROJECT_SCOPE.md.
        return {k: {"pass": True, "note": "skipped (no anthropic key)"} for k in GATE_KEYS}

    try:
        r = _client.messages.create(
            model=MODEL_OPUS,
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        gates = _extract_json_block(r.content[0].text)
    except Exception as e:
        print(f"[supervisor] gate check failed ({e}) — defaulting to half-pass")
        return {k: {"pass": False, "note": f"gate-check error: {e}"} for k in GATE_KEYS}

    # Normalise: ensure every key exists.
    for k in GATE_KEYS:
        gates.setdefault(k, {"pass": False, "note": "missing in response"})

    # Deterministic override #1: forbidden-ending check overrides Opus on gate 4.
    triggered, phrase = _check_forbidden_ending(spoken)
    if triggered:
        gates["elixir"] = {
            "pass": False,
            "note": f"forbidden ending phrase: '{phrase}'",
        }

    # Deterministic override #2: slot structural pre-check overrides Opus on gate 6.
    # This catches the obvious "wrong slot" mistakes the LLM might forgive.
    structural_ok, structural_reason = _slot_structural_precheck(spoken, slot)
    if not structural_ok:
        gates["duration"] = {
            "pass": False,
            "note": structural_reason,
        }

    return gates


def gate_pass_count(gates: dict[str, dict]) -> int:
    return sum(1 for v in gates.values() if isinstance(v, dict) and v.get("pass", False))


# ─── Decision logic ───────────────────────────────────────────────────────

DIMENSION_KEYS = [
    "sensory", "recognition", "spine", "enemy", "transformation",
    "bella", "ciao", "elixir", "zero_sell",
]


def _winner_scores(verdict: dict) -> dict[str, Any]:
    winner = verdict.get("winner") or "A"
    return verdict.get("scores", {}).get(winner, {}) or {}


def _weak_and_strong(scores: dict[str, Any]) -> tuple[list[str], list[str]]:
    weak, strong = [], []
    for k in DIMENSION_KEYS:
        v = scores.get(k)
        if not isinstance(v, (int, float)):
            continue
        if v >= 9.5:
            strong.append(k)
        elif v < 9.0:
            weak.insert(0, k)   # weakest first
        else:
            weak.append(k)
    return weak, strong


def build_rewrite_feedback(
    verdict: dict,
    gates: dict[str, dict],
    round_num: int,
    hard_blocker_keys: list[str] | None = None,
) -> RewriteFeedback:
    scores = _winner_scores(verdict)
    weak, strong = _weak_and_strong(scores)

    failed_gates = [k for k, v in gates.items() if not v.get("pass", False)]
    notes        = {k: gates[k].get("note", "") for k in failed_gates}

    blockers = list(hard_blocker_keys or [])

    # Director note: hard blockers come first — they always beat weak dimensions.
    if blockers:
        lines = ["HARD BLOCKERS — non-negotiable Bella rules:"]
        for k in blockers:
            note = gates.get(k, {}).get("note") or ""
            lines.append(f"  - {k}: {note}")
        director_note = "\n".join(lines)
    elif "elixir" in failed_gates:
        director_note = "Rewrite the closing line — it must be small, human, earned. Cut any 'and that's…' / 'the secret is…' framing."
    elif "scroll_stop" in failed_gates:
        director_note = "The first 3 words must land the hook. Cut everything before."
    elif "specificity" in failed_gates:
        director_note = "Anchor the ordeal to one neighbourhood, one night, one named detail."
    elif weak:
        director_note = f"Lift {weak[0]} above 9.5 without touching anything in {strong[:3]}."
    else:
        director_note = "Tighten the weakest line. Do not over-rewrite."

    triggered = "elixir" in failed_gates and "forbidden ending" in (notes.get("elixir") or "").lower()

    return RewriteFeedback(
        round                       = round_num,
        failed_gates                = failed_gates,
        weak_dimensions             = weak[:3],
        specific_notes              = notes,
        preserve                    = strong,
        director_note               = director_note,
        forbidden_ending_triggered  = triggered,
    )


def evaluate(
    verdict: dict,
    brief: dict,
    round_num: int = 1,
) -> SupervisorDecision:
    """
    Run the 7-gate check and decide APPROVED / NEAR_PERFECT_OVERRIDE / REJECTED.

      score >= 9.5 AND all 7 gates pass    → APPROVED
      score >= 9.6 AND >= 6 gates pass     → NEAR_PERFECT_OVERRIDE
      otherwise                            → REJECTED + RewriteFeedback
    """
    score    = float(verdict.get("best_weighted_score", 0) or 0)
    winner   = verdict.get("winner") or "A"
    script   = verdict.get("scripts", {}).get(winner) or verdict.get("best_script", "")
    if not script:
        # Some callers pass the script via the verdict dict, others via the
        # winning entry in scripts. Fall back gracefully.
        script = ""

    gates    = run_seven_gates(script, brief)
    passed   = gate_pass_count(gates)
    all_pass = passed == len(GATE_KEYS)

    # Hard blockers run outside the 7 gates: they cap the score and force
    # REJECTED regardless of how highly the judge scored the script.
    blockers = run_hard_blockers(script, brief)
    merged_gates = {**gates, **blockers}
    blocker_failures = hard_blocker_failures(blockers)

    if blocker_failures:
        capped = min(score, HARD_BLOCKER_SCORE_CAP)
        feedback = build_rewrite_feedback(
            verdict, merged_gates, round_num, hard_blocker_keys=blocker_failures
        )
        return SupervisorDecision(
            status           = SupervisorStatus.REJECTED,
            score            = capped,
            gate_pass_count  = passed,
            gates            = merged_gates,
            feedback         = feedback,
            hard_blockers    = blocker_failures,
        )

    if score >= brand.PASS_THRESHOLD and all_pass:
        return SupervisorDecision(
            status           = SupervisorStatus.APPROVED,
            score            = score,
            gate_pass_count  = passed,
            gates            = merged_gates,
        )

    if score >= brand.NEAR_PERFECT and passed >= 6:
        return SupervisorDecision(
            status                = SupervisorStatus.NEAR_PERFECT_OVERRIDE,
            score                 = score,
            gate_pass_count       = passed,
            gates                 = merged_gates,
            near_perfect_override = True,
        )

    feedback = build_rewrite_feedback(verdict, merged_gates, round_num)
    return SupervisorDecision(
        status           = SupervisorStatus.REJECTED,
        score            = score,
        gate_pass_count  = passed,
        gates            = merged_gates,
        feedback         = feedback,
    )


# ─── Polish pass ─────────────────────────────────────────────────────────────

POLISH_PROMPT = """You are doing a SURGICAL POLISH PASS on a Bella story script.

The script below scored {score:.2f}/10. Target: {target:.2f}+.

THE TWO WEAKEST DIMENSIONS:
{weak_summary}

JUDGE'S NOTES:
{judge_notes}

YOUR JOB
Rewrite ONLY the lines that fix the weak dimensions. Keep everything else
IDENTICAL — same SECTION 1/2/3/4 headers, same hero, enemy, ally, target
duration ({duration}s), same beats. If a sentence is fine, leave it alone.

OUTPUT: full polished script with all 4 SECTION headers intact. No commentary.

ORIGINAL SCRIPT
{candidate}
"""


def polish_pass(
    best_script: str,
    weak_dims: list[str],
    brief: dict,
    score: float = 0.0,
    judge_notes: str = "",
) -> str:
    """
    Claude Opus surgical lift on the 2 weakest dimensions. Approved
    unconditionally — the orchestrator must accept whatever this returns.
    Returns the original script if Opus is unavailable or output is malformed.
    """
    if _client is None:
        print("[supervisor] polish pass skipped (no anthropic key)")
        return best_script

    slot      = (brief.get("format") or "reel").lower()
    slot_band = brand.SLOT_DURATION.get(slot, brand.SLOT_DURATION["reel"])
    duration  = int(brief.get("target_duration_seconds") or slot_band["target"])
    weak_summary = "\n".join(f"  - {d}" for d in (weak_dims[:2] or ["(none specified)"]))

    prompt = POLISH_PROMPT.format(
        score        = score,
        target       = brand.NEAR_PERFECT,
        weak_summary = weak_summary,
        judge_notes  = (judge_notes or "(focus on the dimensions above)")[:500],
        duration     = duration,
        candidate    = best_script,
    )

    try:
        r = _client.messages.create(
            model=MODEL_OPUS,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        polished = r.content[0].text.strip()
        if all(f"SECTION {n}" in polished for n in (1, 2, 3, 4)):
            return polished
        print("[supervisor] polish output missing SECTION headers — keeping original")
    except Exception as e:
        print(f"[supervisor] polish failed: {e} — keeping original")
    return best_script
