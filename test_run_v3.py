from __future__ import annotations

import sys

import pytest

import run_v3


def test_play_refuses_episode_id(monkeypatch, capsys):
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(run_v3, "_refuse_if_v2_running", lambda: None)
    monkeypatch.setattr(run_v3, "_set_lock", lambda: None)
    monkeypatch.setattr(run_v3, "_clear_lock", lambda: None)
    monkeypatch.setattr(run_v3, "_run_stage", lambda module, extra: calls.append((module, extra)) or 0)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_v3.py", "--stage", "play", "--episode-id", "bella_jake_p1_20260425_1800"],
    )

    with pytest.raises(SystemExit) as exc:
        run_v3.main()

    out = capsys.readouterr().out
    assert exc.value.code == 2
    assert "play does not accept --episode-id" in out
    assert calls == []
