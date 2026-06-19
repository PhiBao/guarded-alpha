from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_portfolio, fixture_snapshot
from guarded_alpha.models import DecisionAction, PortfolioState
from guarded_alpha.strategy import choose_trade, evaluate_strategy


def test_choose_trade_selects_best_fixture_candidate() -> None:
    mandate = load_config().mandate
    decision = choose_trade(fixture_snapshot(), fixture_portfolio(), mandate)

    assert decision.action == DecisionAction.BUY
    assert decision.symbol in mandate.eligible_symbols
    assert decision.notional_usd <= fixture_portfolio().total_value_usd * (
        mandate.max_trade_pct / 100.0
    )
    assert decision.score >= mandate.min_signal_score


def test_strategy_recycles_held_asset_when_stable_reserve_is_low() -> None:
    mandate = load_config().mandate
    low_stable_portfolio = PortfolioState(
        total_value_usd=30.0,
        stable_value_usd=6.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 6.0, "ETH": 12.0, "TWT": 12.0},
    )

    decision = choose_trade(
        fixture_snapshot(),
        low_stable_portfolio,
        mandate,
        force_qualification_trade=True,
        min_trade_usd=5.0,
    )

    assert decision.action == DecisionAction.SELL
    assert decision.inputs["to_symbol"] == "USDC"
    assert decision.notional_usd >= 5.0


def test_strategy_does_not_sell_non_bearish_asset_for_qualification_churn() -> None:
    mandate = load_config().mandate
    healthy_stable_portfolio = PortfolioState(
        total_value_usd=30.0,
        stable_value_usd=16.7,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 16.7, "ETH": 7.0, "TWT": 6.3},
    )

    decision = choose_trade(
        fixture_snapshot(),
        healthy_stable_portfolio,
        mandate,
        force_qualification_trade=True,
        min_trade_usd=5.0,
    )

    assert decision.action == DecisionAction.HOLD
    assert "no held asset has a bearish sell signal" in decision.reason


def test_strategy_requires_high_confidence_for_extra_trade() -> None:
    mandate = load_config().mandate
    decision, vibe_score = evaluate_strategy(
        fixture_snapshot(),
        fixture_portfolio(),
        mandate,
        min_score_override=0.1,
        min_confidence=0.99,
    )

    assert decision.action == DecisionAction.HOLD
    assert vibe_score.confidence < 0.99
    assert "high-confidence execution gate" in decision.reason
