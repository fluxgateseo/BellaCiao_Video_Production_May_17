"""Unit tests for image_prompt_builder parser + sign-off detection."""
from pathlib import Path
import pytest

from pipeline_v3.image_prompt_builder import (
    parse_kling_md,
    shot_prompt,
    shot_is_signoff,
)
from pipeline_v3 import visualize_v3

FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "sample_KLING.md"


def test_parse_extracts_first_frame_for_every_shot():
    shots = parse_kling_md(FIXTURE)
    assert len(shots) == 4
    assert all(s["first_frame_prompt"] for s in shots)


def test_parse_extracts_last_frame_only_when_authored():
    shots = parse_kling_md(FIXTURE)
    by_idx = {s["shot_index"]: s for s in shots}
    assert by_idx[1]["last_frame_prompt"] is None
    assert by_idx[2]["last_frame_prompt"] is not None
    assert "pushed in" in by_idx[2]["last_frame_prompt"].lower()
    assert by_idx[3]["last_frame_prompt"] is None
    assert by_idx[4]["last_frame_prompt"] is not None


def test_shot_prompt_returns_dict_with_start_and_end():
    shots = parse_kling_md(FIXTURE)
    by_idx = {s["shot_index"]: s for s in shots}

    shared = shot_prompt(by_idx[1], character_refs=[])
    assert isinstance(shared, dict)
    assert shared["start_body"]
    assert shared["end_body"] is None

    distinct = shot_prompt(by_idx[2], character_refs=[])
    assert distinct["start_body"]
    assert distinct["end_body"]
    assert distinct["start_body"] != distinct["end_body"]


def test_shot_is_signoff_detects_title():
    shots = parse_kling_md(FIXTURE)
    by_idx = {s["shot_index"]: s for s in shots}
    assert shot_is_signoff(by_idx[1]) is False
    assert shot_is_signoff(by_idx[2]) is False
    assert shot_is_signoff(by_idx[3]) is True


def test_shot_is_signoff_case_insensitive():
    assert shot_is_signoff({"title": "Bella SIGN-OFF (mandatory)"}) is True
    assert shot_is_signoff({"title": "bella sign-off"}) is True
    assert shot_is_signoff({"title": "the signing-off ceremony"}) is False


def test_shot_is_signoff_handles_missing_title():
    assert shot_is_signoff({}) is False
    assert shot_is_signoff({"title": None}) is False


def test_shot_prompt_prefixes_reference_images_on_both_bodies():
    shots = parse_kling_md(FIXTURE)
    by_idx = {s["shot_index"]: s for s in shots}
    refs = ["/abs/enzo_maria_reference.png", "/abs/enzo_maria_face.png"]
    distinct = shot_prompt(by_idx[2], character_refs=refs)
    assert distinct["start_body"].startswith("REFERENCE IMAGES")
    assert distinct["end_body"].startswith("REFERENCE IMAGES")


def test_parse_strips_blockquote_continuations_on_both_frames():
    shots = parse_kling_md(FIXTURE)
    by_idx = {s["shot_index"]: s for s in shots}
    shot4 = by_idx[4]
    # No '> ' continuation characters should survive in either body.
    assert "\n>" not in shot4["first_frame_prompt"]
    assert "\n>" not in shot4["last_frame_prompt"]
    # Continuation text should be joined by a single space into one line.
    assert "window light catches the steam" in shot4["first_frame_prompt"]
    assert "shoulders have dropped" in shot4["last_frame_prompt"]


def test_visualize_airtable_query_skips_network_in_dry_run(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("requests.get should not be called in dry-run mode")

    monkeypatch.setattr(visualize_v3.requests, "get", _boom)
    assert visualize_v3._at_query("{scene_id}='demo'", dry_run=True) == []


def test_brief_v3_dry_run_does_not_hit_airtable(monkeypatch, capsys):
    """brief_v3 main() must not query Airtable in --dry-run mode and must
    succeed even when AIRTABLE_PAT/BASE_ID are unset (matches the visualize_v3
    dry-run contract). Regression: prior versions called _briefs_table().all()
    before any dry-run guard."""
    import sys as _sys
    from pipeline_v3 import brief_v3

    def _boom(*args, **kwargs):
        raise AssertionError("Airtable should not be touched in brief_v3 dry-run")

    monkeypatch.setattr(brief_v3, "_briefs_table", _boom)
    monkeypatch.setattr(brief_v3, "_content_calendar_table", _boom)
    monkeypatch.setattr(brief_v3, "_api", _boom)
    # Strip creds to prove they aren't required in dry-run
    monkeypatch.setattr(brief_v3, "AIRTABLE_PAT", "")
    monkeypatch.setattr(brief_v3, "AIRTABLE_BASE_ID", "")
    monkeypatch.setattr(_sys, "argv", ["brief_v3", "--day", "2026-04-25", "--dry-run"])

    rc = brief_v3.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()


def test_calendar_v3_dry_run_does_not_hit_airtable(monkeypatch, capsys):
    """calendar_v3 main() must not query Airtable in --dry-run mode and must
    succeed even when AIRTABLE_PAT/BASE_ID are unset. Regression: prior versions
    called _content_calendar() (which probes the network) before any dry-run guard."""
    import sys as _sys
    from pipeline_v3 import calendar_v3

    def _boom(*args, **kwargs):
        raise AssertionError("Airtable should not be touched in calendar_v3 dry-run")

    monkeypatch.setattr(calendar_v3, "_content_calendar", _boom)
    monkeypatch.setattr(calendar_v3, "_trend_signals", _boom)
    monkeypatch.setattr(calendar_v3, "_api", _boom)
    monkeypatch.setattr(calendar_v3, "AIRTABLE_PAT", "")
    monkeypatch.setattr(calendar_v3, "AIRTABLE_BASE_ID", "")
    monkeypatch.setattr(_sys, "argv", ["calendar_v3", "--day", "2", "--dry-run"])

    rc = calendar_v3.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()
