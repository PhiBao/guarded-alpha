from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_portfolio, fixture_snapshot
from guarded_alpha.models import DecisionAction, PortfolioState
from guarded_alpha.strategy import choose_trade


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
