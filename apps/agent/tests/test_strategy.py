from dataclasses import replace

from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_portfolio, fixture_snapshot
from guarded_alpha.models import DecisionAction, MarketAsset, MarketSnapshot, PortfolioState
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


def test_strategy_rotates_held_asset_when_cash_buffer_is_low() -> None:
    mandate = replace(load_config().mandate, trade_each_tick=False, min_cash_buffer_usd=5.0)
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

    assert decision.action == DecisionAction.ROTATE
    assert decision.inputs["from_symbol"] in {"ETH", "TWT"}
    assert decision.inputs["to_symbol"] == decision.symbol
    assert decision.inputs["to_symbol"] != decision.inputs["from_symbol"]
    assert decision.notional_usd >= 5.0


def test_strategy_uses_available_cash_for_qualification_trade() -> None:
    mandate = replace(load_config().mandate, trade_each_tick=False)
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


def test_strategy_rotates_weaker_asset_into_strong_buy_when_cash_is_not_enough() -> None:
    mandate = replace(load_config().mandate, trade_each_tick=False)
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
    assert decision.action == DecisionAction.ROTATE
    assert decision.symbol in mandate.eligible_symbols
    assert decision.inputs["from_symbol"] in {"ETH", "TWT"}
    assert decision.inputs["to_symbol"] == decision.symbol
    assert decision.inputs["to_symbol"] != decision.inputs["from_symbol"]
    assert "rotating weaker held" in decision.reason


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


def test_qualification_rotates_to_fund_real_signal() -> None:
    mandate = replace(load_config().mandate, trade_each_tick=False)
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

    assert decision.action == DecisionAction.ROTATE
    assert decision.inputs["to_symbol"] in mandate.eligible_symbols
    assert decision.inputs["to_symbol"] != decision.inputs["from_symbol"]
    assert "rotating weaker held" in decision.reason


def test_trade_each_tick_uses_largest_stable_contract_route() -> None:
    mandate = replace(
        load_config().mandate,
        trade_each_tick=True,
        min_cash_buffer_usd=5.0,
        min_executable_trade_usd=1.0,
        stable_spend_buffer_pct=3.0,
    )
    snapshot = fixture_snapshot()
    usd1 = MarketAsset(
        symbol="USD1",
        cmc_id=36148,
        chain="bsc",
        contract_address="0x8d0d000ee44948fc98c9b98a4fa4921476f08b0d",
        price_usd=1.0,
        change_24h_pct=0.0,
        volume_24h_usd=1_000_000_000.0,
        volatility_7d_pct=0.1,
        sentiment_score=0.0,
        updated_at=snapshot.captured_at,
    )
    snapshot = MarketSnapshot(
        source=snapshot.source,
        assets=[*snapshot.assets, usd1],
        fear_greed=snapshot.fear_greed,
        captured_at=snapshot.captured_at,
        trend_signals=snapshot.trend_signals,
        provenance=snapshot.provenance,
    )
    portfolio = PortfolioState(
        total_value_usd=25.58,
        stable_value_usd=5.01,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 0.02, "USD1": 4.98, "ETH": 14.32, "XRP": 6.25},
    )

    decision, _ = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        min_score_override=0.2,
    )

    assert decision.action == DecisionAction.BUY
    assert decision.inputs["from_symbol"] == "USD1"
    assert decision.inputs["from_route"] == usd1.contract_address
    assert decision.notional_usd == 4.83


def test_trade_each_tick_recycles_held_asset_when_no_stable_can_execute() -> None:
    mandate = replace(
        load_config().mandate,
        trade_each_tick=True,
        min_executable_trade_usd=1.0,
        stable_spend_buffer_pct=3.0,
    )
    portfolio = PortfolioState(
        total_value_usd=25.58,
        stable_value_usd=0.18,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 0.02, "USD1": 0.16, "ETH": 19.15, "XRP": 6.25},
    )

    decision, _ = evaluate_strategy(
        fixture_snapshot(),
        portfolio,
        mandate,
        min_score_override=0.99,
    )

    assert decision.action == DecisionAction.SELL
    assert decision.inputs["from_symbol"] == "ETH"
    assert decision.inputs["to_symbol"] == "USDC"
    assert "No buy candidate cleared" in decision.reason
    assert "target_buy_symbol" not in decision.inputs
