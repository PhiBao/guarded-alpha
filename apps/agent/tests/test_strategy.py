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


def test_strategy_recycles_held_asset_when_cash_buffer_is_low() -> None:
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
    assert decision.inputs["from_symbol"] in {"ETH", "TWT"}
    assert decision.inputs["to_symbol"] == "USDC"
    assert decision.inputs["target_buy_symbol"] in mandate.eligible_symbols
    assert decision.inputs["target_buy_symbol"] != decision.inputs["from_symbol"]
    assert decision.notional_usd >= 5.0


def test_strategy_uses_available_cash_for_qualification_trade() -> None:
    mandate = load_config().mandate
    healthy_stable_portfolio = PortfolioState(
        total_value_usd=30.0,
        stable_value_usd=16.7,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 16.7, "ETH": 7.0, "TWT": 6.3},
    )

    decision, _ = evaluate_strategy(
        fixture_snapshot(),
        healthy_stable_portfolio,
        mandate,
        force_qualification_trade=True,
        min_trade_usd=5.0,
        min_score_override=0.99,
    )

    assert decision.action == DecisionAction.BUY
    assert decision.notional_usd == 5.0


def test_strategy_can_apply_explicit_confidence_gate() -> None:
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


def test_strategy_recycles_weaker_asset_into_stable_when_cash_is_not_enough() -> None:
    mandate = load_config().mandate
    portfolio = PortfolioState(
        total_value_usd=100.0,
        stable_value_usd=4.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 4.0, "ETH": 48.0, "TWT": 48.0},
    )

    decision, vibe_score = evaluate_strategy(
        fixture_snapshot(),
        portfolio,
        mandate,
        min_score_override=0.2,
    )

    assert vibe_score.symbol in mandate.eligible_symbols
    assert decision.action == DecisionAction.SELL
    assert decision.symbol in mandate.eligible_symbols
    assert decision.inputs["from_symbol"] in {"ETH", "TWT"}
    assert decision.inputs["to_symbol"] == "USDC"
    assert decision.inputs["target_buy_symbol"] in mandate.eligible_symbols
    assert decision.inputs["target_buy_symbol"] != decision.inputs["from_symbol"]
    assert "recycling weaker held" in decision.reason


def test_strategy_prefers_partial_usdc_buy_before_rotation() -> None:
    mandate = load_config().mandate
    portfolio = PortfolioState(
        total_value_usd=100.0,
        stable_value_usd=12.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 6.2, "USD1": 5.8, "ETH": 44.0, "TWT": 44.0},
    )

    decision, vibe_score = evaluate_strategy(
        fixture_snapshot(),
        portfolio,
        mandate,
        min_score_override=0.2,
    )

    assert vibe_score.symbol in mandate.eligible_symbols
    assert decision.action == DecisionAction.BUY
    assert decision.inputs["from_symbol"] == "USDC"
    assert decision.notional_usd >= 5.0


def test_qualification_recycles_to_fund_real_signal() -> None:
    mandate = load_config().mandate
    portfolio = PortfolioState(
        total_value_usd=100.0,
        stable_value_usd=4.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 4.0, "ETH": 48.0, "TWT": 48.0},
    )

    decision, _ = evaluate_strategy(
        fixture_snapshot(),
        portfolio,
        mandate,
        force_qualification_trade=True,
        min_trade_usd=5.0,
        min_score_override=0.2,
    )

    assert decision.action == DecisionAction.SELL
    assert decision.inputs["to_symbol"] == "USDC"
    assert decision.inputs["target_buy_symbol"] in mandate.eligible_symbols
    assert "recycling weaker held" in decision.reason
