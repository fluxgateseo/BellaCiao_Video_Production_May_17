from __future__ import annotations

import argparse
import sys
import types

import run


class _FakeGate:
    mode = "event_day"
    city = "Melbourne"
    friend_id = "jake"
    currency = "$"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "city": self.city,
            "friend_id": self.friend_id,
            "currency": self.currency,
        }


def test_stage_auto_reports_strategy_network_failure_cleanly(monkeypatch, capsys):
    logical_gate_mod = types.ModuleType("logical_gate")
    logical_gate_mod.GateFailure = RuntimeError
    logical_gate_mod.run_gate = lambda *_args, **_kwargs: _FakeGate()

    strategy_mod = types.ModuleType("strategy")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("Anthropic unavailable: cannot resolve api.anthropic.com")

    strategy_mod.generate_brief = _boom

    monkeypatch.setitem(sys.modules, "logical_gate", logical_gate_mod)
    monkeypatch.setitem(sys.modules, "strategy", strategy_mod)

    args = argparse.Namespace(
        no_scout=True,
        target_date="2026-04-25",
        format="reel",
        pillar=None,
        friend=None,
    )

    rc = run.stage_auto(args)
    out = capsys.readouterr().out

    assert rc == 1
    assert "strategy director failed" in out
    assert "live model access" in out
    assert "ANTHROPIC_API_KEY" in out
