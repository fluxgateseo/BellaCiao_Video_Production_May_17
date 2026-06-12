from pathlib import Path

from pipeline_v3 import package_v3


def test_package_episode_dry_run_does_not_require_triplet_files(tmp_path: Path):
    day_dir = tmp_path / "Day 99"
    result = package_v3.package_episode("bella_test_p1_20260420_1200", day_dir, dry_run=True, force=False)
    assert result.startswith("[dry-run]")


def test_infer_triplets_for_dry_run_uses_v2_day_sources(monkeypatch, tmp_path: Path):
    v2_file = tmp_path / "bella_test_p1_20260420_1200.json"
    v2_file.write_text('{"day": 7}', encoding="utf-8")

    monkeypatch.setattr(package_v3, "iter_day_episodes", lambda day: [v2_file] if day == 7 else [])
    monkeypatch.setattr(package_v3, "SCRIPTS_V3_DIR", tmp_path / "Scripts_v3")

    inferred = package_v3.infer_triplets_for_dry_run(day=7, episode_id=None)
    assert inferred == [("bella_test_p1_20260420_1200", tmp_path / "Scripts_v3" / "Day 7")]
