from dataclasses import replace

from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_portfolio, fixture_snapshot
from guarded_alpha.models import RiskStatus
from guarded_alpha.risk import evaluate_risk
from guarded_alpha.strategy import choose_trade


def test_risk_approves_fixture_trade(tmp_path) -> None:
    mandate = replace(load_config().mandate, kill_switch_path=str(tmp_path / "KILL_SWITCH"))
    snapshot = fixture_snapshot()
    portfolio = fixture_portfolio()
    decision = choose_trade(snapshot, portfolio, mandate)

    verdict = evaluate_risk(decision, snapshot, portfolio, mandate)

    assert verdict.status == RiskStatus.APPROVED


def test_risk_rejects_kill_switch(tmp_path) -> None:
    kill_switch = tmp_path / "KILL_SWITCH"
    kill_switch.write_text("halt", encoding="utf-8")
    mandate = replace(load_config().mandate, kill_switch_path=str(kill_switch))
    snapshot = fixture_snapshot()
    portfolio = fixture_portfolio()
    decision = choose_trade(snapshot, portfolio, mandate)

    verdict = evaluate_risk(decision, snapshot, portfolio, mandate)

    assert verdict.status == RiskStatus.REJECTED
    assert any("Kill switch" in reason for reason in verdict.reasons)


def test_risk_rejects_excessive_slippage(tmp_path) -> None:
    mandate = replace(load_config().mandate, kill_switch_path=str(tmp_path / "KILL_SWITCH"))
    snapshot = fixture_snapshot()
    portfolio = fixture_portfolio()
    decision = choose_trade(snapshot, portfolio, mandate)

    verdict = evaluate_risk(
        decision,
        snapshot,
        portfolio,
        mandate,
        proposed_slippage_bps=mandate.max_slippage_bps + 1,
    )

    assert verdict.status == RiskStatus.REJECTED
    assert any("Slippage" in reason for reason in verdict.reasons)

