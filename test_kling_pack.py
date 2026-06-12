from pathlib import Path

from pipeline_v3 import kling_pack


def test_process_episode_dry_run_skips_llm_call(monkeypatch, tmp_path: Path, capsys):
    kling_path = tmp_path / "bella_test_p1_20260420_1200.KLING.md"
    folder = tmp_path / "Story 01 (Day 99)"
    folder.mkdir()

    monkeypatch.setattr(
        kling_pack,
        "parse_kling_md",
        lambda path: [
            {
                "shot_index": 1,
                "title": "Hook",
                "first_frame_prompt": "Bella at the pass",
                "last_frame_prompt": "Bella leans in",
                "character_refs_named": [],
            }
        ],
    )
    monkeypatch.setattr(kling_pack, "_raw_shot_blocks", lambda path: {1: "raw block"})
    monkeypatch.setattr(
        kling_pack,
        "enrich_shot",
        lambda parsed, raw_block, **kwargs: {
            "shot_index": 1,
            "title": parsed["title"],
            "episode_kind": kwargs.get("episode_kind"),
            "day": kwargs.get("day"),
            "episode_id": kwargs.get("episode_id", "stub_episode"),
        },
    )

    def _boom(*args, **kwargs):
        raise AssertionError("call_sonnet should not run during dry-run")

    monkeypatch.setattr(kling_pack, "call_sonnet", _boom)

    result = kling_pack.process_episode(
        {"kling_path": kling_path, "kind": "story", "folders": [folder]},
        day=99,
        friend_id="test_friend",
        dry_run=True,
    )

    assert result["error"] is None
    assert result["written"] == 0
    assert result["shot_count"] == 1
    assert result["staged"] == 1
    assert "would write 3 files" in capsys.readouterr().out
