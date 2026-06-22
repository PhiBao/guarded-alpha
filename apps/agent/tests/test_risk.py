from dataclasses import replace

from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_portfolio, fixture_snapshot
from guarded_alpha.models import DecisionAction, PortfolioState, RiskStatus, TradeDecision
from guarded_alpha.risk import evaluate_risk
from guarded_alpha.strategy import choose_trade


def test_risk_approves_fixture_trade(tmp_path) -> None:
    mandate = replace(
        load_config().mandate,
        kill_switch_path=str(tmp_path / "KILL_SWITCH"),
        max_trade_pct=20.0,
    )
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


def test_risk_allows_sell_that_restores_stable_reserve(tmp_path) -> None:
    mandate = replace(load_config().mandate, kill_switch_path=str(tmp_path / "KILL_SWITCH"))
    snapshot = fixture_snapshot()
    portfolio = PortfolioState(
        total_value_usd=30.0,
        stable_value_usd=8.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 8.0, "ETH": 12.0},
    )
    decision = TradeDecision(
        action=DecisionAction.SELL,
        symbol="ETH",
        score=-0.1,
        notional_usd=5.0,
        reason="rebalance",
        inputs={"from_symbol": "ETH", "to_symbol": "USDC"},
    )

    verdict = evaluate_risk(decision, snapshot, portfolio, mandate)

    assert verdict.status == RiskStatus.APPROVED


def test_risk_allows_direct_rotation_without_stable_reserve_gate(tmp_path) -> None:
    mandate = replace(
        load_config().mandate,
        kill_switch_path=str(tmp_path / "KILL_SWITCH"),
        min_cash_buffer_usd=3.0,
    )
    snapshot = fixture_snapshot()
    portfolio = PortfolioState(
        total_value_usd=100.0,
        stable_value_usd=4.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 4.0, "ETH": 40.0, "TWT": 56.0},
    )
    decision = TradeDecision(
        action=DecisionAction.ROTATE,
        symbol="CAKE",
        score=0.31,
        notional_usd=20.0,
        reason="rotate into best signal",
        inputs={
            "from_symbol": "ETH",
            "to_symbol": "CAKE",
            "expected_edge_bps": mandate.min_expected_edge_bps,
        },
    )

    verdict = evaluate_risk(decision, snapshot, portfolio, mandate)

    assert verdict.status == RiskStatus.APPROVED


def test_risk_rejects_rotation_that_exceeds_position_cap(tmp_path) -> None:
    mandate = replace(
        load_config().mandate,
        kill_switch_path=str(tmp_path / "KILL_SWITCH"),
        max_position_pct=30.0,
        trade_each_tick=False,
    )
    snapshot = fixture_snapshot()
    portfolio = PortfolioState(
        total_value_usd=100.0,
        stable_value_usd=5.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 5.0, "ETH": 40.0, "CAKE": 25.0, "TWT": 30.0},
    )
    decision = TradeDecision(
        action=DecisionAction.ROTATE,
        symbol="CAKE",
        score=0.31,
        notional_usd=10.0,
        reason="rotate into best signal",
        inputs={
            "from_symbol": "ETH",
            "to_symbol": "CAKE",
            "expected_edge_bps": mandate.min_expected_edge_bps,
        },
    )

    verdict = evaluate_risk(decision, snapshot, portfolio, mandate)

    assert verdict.status == RiskStatus.REJECTED
    assert any("Target position" in reason for reason in verdict.reasons)
