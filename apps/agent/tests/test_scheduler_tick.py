from dataclasses import replace

from guarded_alpha.config import load_config
from guarded_alpha.runner import run_scheduled_tick


def test_scheduled_tick_runs_once_per_utc_day(tmp_path) -> None:
    config = replace(load_config(), audit_path=tmp_path / "audit.jsonl")

    first = run_scheduled_tick(config)
    second = run_scheduled_tick(config)

    assert first is not None
    assert second is None
