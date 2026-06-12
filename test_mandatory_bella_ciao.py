"""Hard-blocker gates: Bella labelled dialogue, mandatory sign-off, Ciao herald.

These are the non-negotiables from feedback_bella_and_ciao_mandatory + the
Day 2 Danny-story rubric gap. The supervisor must REJECT (and cap the score)
when any of the three are missing — no Opus override, no self-grade bypass.
"""
from __future__ import annotations

import pytest

import quality_supervisor as qs


SIGNOFF_LINE = "BELLA: I'm Bella — ciao for now."
BELLA_LINE_OPEN = "BELLA: [direct-to-camera] Every Tuesday, same song — empty dining room."
BELLA_LINE_CLOSE = "BELLA: That was the pivot."
CIAO_LINE = "CIAO: [small bark, thinking loudly] This one needed me."


def _wrap(spoken: str, ciao_moment: str = "Ciao lifts his head at the hostess stand and holds the beat.") -> str:
    """Wrap a spoken block into a minimal 4-section script the supervisor can parse."""
    scene_brief = (
        "{\n"
        '  "friend_id": "enzo_maria",\n'
        f'  "ciao_moment": "{ciao_moment}",\n'
        '  "camera": "push in"\n'
        "}"
    )
    return (
        "SECTION 1: STORY SPINE (internal)\n"
        "  ONCE UPON A TIME: nothing.\n\n"
        "SECTION 2: VIDEO SCRIPT\n"
        f"{spoken}\n\n"
        "SECTION 3: INSTAGRAM CAPTION\n"
        "  Some caption text.\n\n"
        "SECTION 4: SCENE BRIEF\n"
        f"{scene_brief}\n"
    )


def _verdict(script: str, score: float = 9.7) -> dict:
    return {
        "winner": "A",
        "best_weighted_score": score,
        "scripts": {"A": script},
        "scores": {
            "A": {
                "sensory": 9.5, "recognition": 9.6, "spine": 9.5,
                "enemy": 9.5, "transformation": 9.5, "bella": 9.5,
                "ciao": 9.5, "elixir": 9.6, "zero_sell": 10,
            }
        },
    }


BRIEF: dict = {
    "format": "reel",
    "friend": "enzo_maria",
    "target_duration_seconds": 45,
    "currency": "$",
}


@pytest.fixture(autouse=True)
def _stub_opus_gates(monkeypatch):
    """Short-circuit the Opus gate LLM call so tests stay offline + deterministic."""
    monkeypatch.setattr(
        qs,
        "run_seven_gates",
        lambda *_a, **_k: {k: {"pass": True, "note": "stubbed"} for k in qs.GATE_KEYS},
    )


# ─── Hard-blocker rejection behaviour ────────────────────────────────────────

def test_missing_signoff_is_hard_blocker():
    spoken = "\n".join([BELLA_LINE_OPEN, CIAO_LINE, BELLA_LINE_CLOSE])
    decision = qs.evaluate(_verdict(_wrap(spoken)), BRIEF)
    assert decision.status == qs.SupervisorStatus.REJECTED
    assert "bella_signoff_present" in decision.hard_blockers
    assert decision.score <= qs.HARD_BLOCKER_SCORE_CAP


def test_missing_bella_labelled_dialogue_is_hard_blocker():
    # Unlabelled narration — the sign-off line is present but carries no
    # BELLA: speaker tag, so the writer never makes Bella an on-camera voice.
    spoken = "\n".join([
        "[Cold open, observational, no speaker label.]",
        "Every Tuesday, same song — empty dining room.",
        CIAO_LINE,
        "I'm Bella — ciao for now.",
    ])
    decision = qs.evaluate(_verdict(_wrap(spoken)), BRIEF)
    assert decision.status == qs.SupervisorStatus.REJECTED
    assert "bella_labelled_dialogue" in decision.hard_blockers
    assert decision.score <= qs.HARD_BLOCKER_SCORE_CAP


def test_missing_ciao_is_hard_blocker_without_override():
    spoken = "\n".join([BELLA_LINE_OPEN, BELLA_LINE_CLOSE, SIGNOFF_LINE])
    decision = qs.evaluate(_verdict(_wrap(spoken, ciao_moment="none")), BRIEF)
    assert decision.status == qs.SupervisorStatus.REJECTED
    assert "ciao_herald_present" in decision.hard_blockers
    assert decision.score <= qs.HARD_BLOCKER_SCORE_CAP


def test_ciao_absent_passes_when_brief_opts_out():
    spoken = "\n".join([BELLA_LINE_OPEN, BELLA_LINE_CLOSE, SIGNOFF_LINE])
    override_brief = dict(BRIEF, ciao_allowed_absent=True)
    decision = qs.evaluate(_verdict(_wrap(spoken, ciao_moment="none")), override_brief)
    assert "ciao_herald_present" not in decision.hard_blockers
    assert decision.hard_blockers == []
    # With all opus gates stubbed pass + score 9.7 + no blockers → APPROVED path.
    assert decision.status == qs.SupervisorStatus.APPROVED


def test_ciao_in_scene_brief_only_counts_as_present():
    """Ciao doesn't need a CIAO: speaker label; scene_brief.ciao_moment suffices."""
    spoken = "\n".join([
        BELLA_LINE_OPEN,
        "BELLA: [observational] And then the grey dog lifts his head.",
        BELLA_LINE_CLOSE,
        SIGNOFF_LINE,
    ])
    decision = qs.evaluate(
        _verdict(_wrap(spoken, ciao_moment="Ciao lifts his head at the hostess stand.")),
        BRIEF,
    )
    assert "ciao_herald_present" not in decision.hard_blockers


def test_all_three_non_negotiables_met_clears_hard_blockers():
    spoken = "\n".join([BELLA_LINE_OPEN, CIAO_LINE, BELLA_LINE_CLOSE, SIGNOFF_LINE])
    decision = qs.evaluate(_verdict(_wrap(spoken)), BRIEF)
    assert decision.hard_blockers == []
    assert decision.status == qs.SupervisorStatus.APPROVED


def test_hard_blocker_beats_near_perfect_score():
    """9.7 alone used to APPROVE / OVERRIDE — now it must REJECT on missing signoff."""
    spoken = "\n".join([BELLA_LINE_OPEN, CIAO_LINE, BELLA_LINE_CLOSE])  # no sign-off
    decision = qs.evaluate(_verdict(_wrap(spoken), score=9.8), BRIEF)
    assert decision.status == qs.SupervisorStatus.REJECTED
    assert decision.near_perfect_override is False
    assert decision.score <= qs.HARD_BLOCKER_SCORE_CAP


def test_rewrite_feedback_lists_hard_blockers():
    spoken = "\n".join([BELLA_LINE_OPEN, CIAO_LINE, BELLA_LINE_CLOSE])  # no sign-off
    decision = qs.evaluate(_verdict(_wrap(spoken)), BRIEF)
    assert decision.feedback is not None
    prompt_block = decision.feedback.to_prompt_block()
    assert "HARD BLOCKER" in prompt_block.upper()
    assert "sign-off" in prompt_block.lower() or "signoff" in prompt_block.lower()
