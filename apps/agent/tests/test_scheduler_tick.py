import json
from dataclasses import replace

from guarded_alpha.config import load_config
from guarded_alpha.models import now_utc
from guarded_alpha.runner import run_scheduled_tick


def test_scheduled_tick_keeps_scanning_without_daily_run_block(tmp_path) -> None:
    config = replace(load_config(), audit_path=tmp_path / "audit.jsonl")

    first = run_scheduled_tick(config)
    second = run_scheduled_tick(config)

    assert first is not None
    assert second is not None


def test_live_scheduled_tick_respects_max_daily_submitted_trades(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text(
        json.dumps({"created_at": now_utc().isoformat(), "receipt": {"submitted": True}})
        + "\n",
        encoding="utf-8",
    )
    config = replace(
        load_config(),
        audit_path=audit_path,
        live_trading_enabled=True,
        max_daily_trades=1,
    )

    assert run_scheduled_tick(config) is None


def test_live_scheduled_tick_keeps_normal_gate_after_submitted_trade(
    tmp_path,
    monkeypatch,
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text(
        json.dumps({"created_at": now_utc().isoformat(), "receipt": {"submitted": True}})
        + "\n",
        encoding="utf-8",
    )
    config = replace(
        load_config(),
        audit_path=audit_path,
        live_trading_enabled=True,
        max_daily_trades=2,
    )
    captured = {}

    def fake_run_once(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    from guarded_alpha import runner

    monkeypatch.setattr(runner, "run_once", fake_run_once)

    assert run_scheduled_tick(config) is not None
    assert captured["kwargs"] == {
        "force_qualification_trade": False,
    }


def test_live_scheduled_tick_never_forces_qualification_trade(
    tmp_path,
    monkeypatch,
) -> None:
    config = replace(
        load_config(),
        audit_path=tmp_path / "audit.jsonl",
        live_trading_enabled=True,
    )
    captured = {}

    def fake_run_once(*args, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    from guarded_alpha import runner

    monkeypatch.setattr(runner, "run_once", fake_run_once)

    assert run_scheduled_tick(config) is not None
    assert captured["kwargs"] == {
        "force_qualification_trade": False,
    }
