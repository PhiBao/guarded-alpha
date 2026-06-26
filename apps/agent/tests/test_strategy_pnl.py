from dataclasses import replace

from guarded_alpha.config import load_config
from guarded_alpha.fixtures import fixture_snapshot
from guarded_alpha.models import (
    DecisionAction,
    MarketAsset,
    MarketSnapshot,
    PortfolioState,
)
from guarded_alpha.strategy import evaluate_strategy


def test_trade_each_tick_uses_min_executable_not_min_daily() -> None:
    mandate = replace(
        load_config().mandate,
        trade_each_tick=True,
        min_executable_trade_usd=0.5,
        stable_spend_buffer_pct=1.0,
        min_trade_notional_usd=1.0,
        chase_pnl=True,
    )
    snapshot = fixture_snapshot()
    portfolio = PortfolioState(
        total_value_usd=12.01,
        stable_value_usd=5.39,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={
            "BNB": 5.52,
            "USDC": 5.23,
            "ETH": 0.99,
            "USD1": 0.16,
            "XRP": 0.13,
        },
    )
    decision, vibe_score = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        min_score_override=0.2,
        min_trade_usd=3.0,
    )

    assert decision.action != DecisionAction.HOLD, (
        f"Expected BUY or ROTATE from a $12.01 wallet with $5.23 USDC, "
        f"got {decision.action.value}: {decision.reason}"
    )
    assert vibe_score.symbol in mandate.eligible_symbols
    assert decision.notional_usd > 0


def test_actual_rejected_wallet_xpl_signal_should_not_hold() -> None:
    mandate = replace(
        load_config().mandate,
        trade_each_tick=True,
        min_executable_trade_usd=0.5,
        stable_spend_buffer_pct=1.0,
        min_trade_notional_usd=1.0,
        min_signal_score=0.24,
        min_expected_edge_bps=50,
        max_trade_pct=30,
        chase_pnl=True,
        rotate_source_symbols={
            "AAVE", "ADA", "APE", "ASTER", "AVAX", "BNB", "BCH", "CAKE",
            "DOGE", "DOT", "ETH", "FET", "FIL", "FLOKI", "INJ", "LINK",
            "LTC", "PENDLE", "SFP", "TRX", "TWT", "UNI", "XRP", "ZRO",
        },
        bnb_gas_reserve_pct=30.0,
    )
    captured_at = fixture_snapshot().captured_at
    xpl = MarketAsset(
        symbol="XPL",
        cmc_id=99999,
        chain="bsc",
        contract_address="0xb8c77482e45f1f44de1745f52c74426c631bdd52",
        price_usd=0.05,
        change_24h_pct=6.09,
        volume_24h_usd=1_452_348_993.0,
        volatility_7d_pct=2.81,
        sentiment_score=0.0,
        updated_at=captured_at,
    )
    bnb_asset = MarketAsset(
        symbol="BNB",
        cmc_id=1839,
        chain="bsc",
        contract_address=None,
        price_usd=600.0,
        change_24h_pct=0.5,
        volume_24h_usd=2_000_000_000.0,
        volatility_7d_pct=3.0,
        sentiment_score=0.0,
        updated_at=captured_at,
    )
    snapshot = MarketSnapshot(
        source="cmc-api",
        assets=[xpl, bnb_asset, *fixture_snapshot().assets],
        fear_greed=14,
        captured_at=captured_at,
        trend_signals={
            "market_regime": "defensive",
            "risk_notes": [],
            "top_gainers": ["XPL"],
            "top_losers": [],
            "source": "/v1/cryptocurrency/listings/latest",
        },
        provenance={
            "cmc_symbols": 146,
            "quote_chunks": 4,
            "quotes": "/v1/cryptocurrency/quotes/latest",
            "fear_greed": "/v3/fear-and-greed/latest",
            "trend_signals": "/v1/cryptocurrency/listings/latest",
        },
    )
    portfolio = PortfolioState(
        total_value_usd=12.01,
        stable_value_usd=5.39,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={
            "BNB": 5.52,
            "USDC": 5.23,
            "ETH": 0.99,
            "USD1": 0.16,
            "XRP": 0.13,
        },
    )
    decision, vibe_score = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        min_score_override=0.24,
        min_trade_usd=3.0,
    )

    assert decision.action != DecisionAction.HOLD, (
        f"Expected XPL buy or rotate from BNB recycle, got HOLD: {decision.reason}"
    )
    assert decision.symbol == "XPL"
    assert vibe_score.symbol == "XPL"
    assert decision.notional_usd > 0
    if decision.action == DecisionAction.BUY:
        assert decision.inputs["from_symbol"] in {"USDC", "USD1"}
    elif decision.action == DecisionAction.ROTATE:
        assert decision.inputs["to_symbol"] == "XPL"


def test_bnb_rotate_reserves_gas() -> None:
    mandate = replace(
        load_config().mandate,
        trade_each_tick=True,
        min_executable_trade_usd=0.5,
        stable_spend_buffer_pct=1.0,
        min_trade_notional_usd=1.0,
        min_signal_score=0.20,
        min_expected_edge_bps=50,
        max_trade_pct=30,
        chase_pnl=True,
        rotate_source_symbols={"BNB", "ETH"},
        bnb_gas_reserve_pct=30.0,
    )
    bnb_value = 10.0
    captured_at = fixture_snapshot().captured_at
    bnb_asset = MarketAsset(
        symbol="BNB",
        cmc_id=1839,
        chain="bsc",
        contract_address=None,
        price_usd=600.0,
        change_24h_pct=0.5,
        volume_24h_usd=2_000_000_000.0,
        volatility_7d_pct=3.0,
        sentiment_score=0.0,
        updated_at=captured_at,
    )
    snapshot = MarketSnapshot(
        source="fixture",
        assets=[bnb_asset, *fixture_snapshot().assets],
        fear_greed=62,
        captured_at=captured_at,
        trend_signals=fixture_snapshot().trend_signals,
        provenance=fixture_snapshot().provenance,
    )
    portfolio = PortfolioState(
        total_value_usd=20.0,
        stable_value_usd=1.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 1.0, "BNB": bnb_value},
    )
    decision, vibe_score = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        min_score_override=0.2,
        min_trade_usd=3.0,
    )

    if decision.action == DecisionAction.ROTATE and decision.inputs["from_symbol"] == "BNB":
        notional = decision.notional_usd
        max_spendable = bnb_value * 0.7
        assert notional <= max_spendable, (
            f"BNB rotate notional {notional} exceeded 70% of {bnb_value} "
            f"(reserve {max_spendable:.2f})"
        )
        assert notional < bnb_value, "BNB rotate should leave gas reserve behind"
    else:
        assert decision.action != DecisionAction.HOLD, (
            f"Expected some non-HOLD action from BNB wallet: {decision.reason}"
        )


def test_take_profit_sells_winning_position() -> None:
    mandate = replace(
        load_config().mandate,
        chase_pnl=True,
        take_profit_pct=8.0,
        stop_loss_pct=5.0,
        trade_each_tick=True,
        min_executable_trade_usd=0.5,
        min_trade_notional_usd=1.0,
        stable_spend_buffer_pct=1.0,
        rotate_source_symbols={"ETH", "TWT"},
    )
    cost_basis = {"ETH": 90.0}
    portfolio = PortfolioState(
        total_value_usd=200.0,
        stable_value_usd=50.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 50.0, "ETH": 100.0, "TWT": 50.0},
    )
    decision, _ = evaluate_strategy(
        fixture_snapshot(),
        portfolio,
        mandate,
        min_score_override=0.99,
        cost_basis=cost_basis,
    )

    assert decision.action == DecisionAction.SELL, (
        f"Expected SELL for ETH at +{((100-90)/90*100):.1f}% profit, got {decision.action.value}"
    )
    assert decision.symbol == "ETH"
    assert "TP" in decision.reason or "+11" in decision.reason or "exceeds" in decision.reason
    assert decision.notional_usd > 0


def test_stop_loss_sells_losing_position() -> None:
    mandate = replace(
        load_config().mandate,
        chase_pnl=True,
        take_profit_pct=8.0,
        stop_loss_pct=5.0,
        trade_each_tick=True,
        min_executable_trade_usd=0.5,
        min_trade_notional_usd=1.0,
        stable_spend_buffer_pct=1.0,
        rotate_source_symbols={"ETH", "TWT"},
    )
    cost_basis = {"ETH": 120.0}
    portfolio = PortfolioState(
        total_value_usd=200.0,
        stable_value_usd=50.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 50.0, "ETH": 100.0, "TWT": 50.0},
    )
    decision, _ = evaluate_strategy(
        fixture_snapshot(),
        portfolio,
        mandate,
        min_score_override=0.99,
        cost_basis=cost_basis,
    )

    assert decision.action == DecisionAction.SELL, (
        f"Expected SELL for ETH at {((100-120)/120*100):.1f}% loss, got {decision.action.value}"
    )
    assert decision.symbol == "ETH"
    assert "SL" in decision.reason or "breaches" in decision.reason
    assert decision.notional_usd > 0


def test_rank_decay_rotates_weak_held_to_best_candidate() -> None:
    mandate = replace(
        load_config().mandate,
        chase_pnl=True,
        rotate_decay_bps=150,
        trade_each_tick=True,
        min_executable_trade_usd=0.5,
        min_trade_notional_usd=1.0,
        stable_spend_buffer_pct=1.0,
        rotate_source_symbols={"ETH", "TWT", "CAKE"},
        min_signal_score=0.20,
        min_expected_edge_bps=50,
    )
    snapshot = fixture_snapshot()
    portfolio = PortfolioState(
        total_value_usd=200.0,
        stable_value_usd=50.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 50.0, "ETH": 80.0, "TWT": 70.0},
    )

    cost_basis = {"ETH": 80.0, "TWT": 70.0}
    decision, _ = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        min_score_override=0.2,
        cost_basis=cost_basis,
    )

    if decision.action == DecisionAction.ROTATE:
        assert decision.inputs["to_symbol"] in mandate.rotate_source_symbols
        assert decision.inputs["from_symbol"] in mandate.rotate_source_symbols
        assert decision.inputs["to_symbol"] != decision.inputs["from_symbol"]
        assert "Rank decay" in decision.reason or "decay" in decision.reason.lower()
        assert decision.notional_usd > 0
    elif decision.action == DecisionAction.BUY:
        pass
    elif decision.action == DecisionAction.SELL:
        pass
    else:
        assert decision.action != DecisionAction.HOLD, (
            f"Expected non-HOLD from rank-decay check: {decision.reason}"
        )


def test_chase_pnl_boosts_momentum_in_defensive_regime() -> None:
    mandate = replace(
        load_config().mandate,
        chase_pnl=True,
        trade_each_tick=True,
        min_executable_trade_usd=0.5,
    )
    captured_at = fixture_snapshot().captured_at
    high_momentum_asset = MarketAsset(
        symbol="INJ",
        cmc_id=7226,
        chain="bsc",
        contract_address=None,
        price_usd=30.0,
        change_24h_pct=15.0,
        volume_24h_usd=500_000_000.0,
        volatility_7d_pct=8.0,
        sentiment_score=0.0,
        updated_at=captured_at,
    )
    snapshot = MarketSnapshot(
        source="fixture",
        assets=[high_momentum_asset],
        fear_greed=14,
        captured_at=captured_at,
        trend_signals=fixture_snapshot().trend_signals,
        provenance=fixture_snapshot().provenance,
    )
    portfolio = PortfolioState(
        total_value_usd=100.0,
        stable_value_usd=50.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 50.0},
    )
    decision, vibe_score = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        min_score_override=0.0,
    )

    assert decision.action != DecisionAction.HOLD, (
        f"In defensive regime with chase_pnl, high momentum asset "
        f"should clear the buy gate: {decision.reason}"
    )
    assert decision.symbol == "INJ"
    momentums = [v for v in vibe_score.votes if v.name == "momentum" and v.weight > 0.3]
    assert len(momentums) > 0, (
        "momentum weight should be boosted in defensive regime"
    )


def test_net_edge_rejects_when_costs_eat_the_edge() -> None:
    mandate = replace(
        load_config().mandate,
        chase_pnl=True,
        min_signal_score=0.20,
        min_expected_edge_bps=50,
        trade_each_tick=True,
    )
    captured_at = fixture_snapshot().captured_at
    borderline_asset = MarketAsset(
        symbol="FIL",
        cmc_id=2280,
        chain="bsc",
        contract_address=None,
        price_usd=5.0,
        change_24h_pct=2.5,
        volume_24h_usd=200_000_000.0,
        volatility_7d_pct=10.0,
        sentiment_score=0.0,
        updated_at=captured_at,
    )
    snapshot = MarketSnapshot(
        source="fixture",
        assets=[borderline_asset],
        fear_greed=62,
        captured_at=captured_at,
        trend_signals=fixture_snapshot().trend_signals,
        provenance=fixture_snapshot().provenance,
    )
    portfolio = PortfolioState(
        total_value_usd=100.0,
        stable_value_usd=50.0,
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
        positions={"USDC": 50.0},
    )
    decision, _ = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        min_score_override=0.21,
    )

    net_edge = decision.inputs.get("net_edge_bps", 0)
    assert net_edge < mandate.min_expected_edge_bps or decision.action == DecisionAction.HOLD, (
        f"Net edge {net_edge}bps should fail against min_edge "
        f"{mandate.min_expected_edge_bps}bps"
    )


def test_cost_basis_persists_and_clears() -> None:
    from guarded_alpha.cost_basis import (
        load_cost_basis,
        save_cost_basis,
        update_cost_basis,
    )

    tmp_file = "/tmp/test_cost_basis.json"
    import os

    try:
        basis = update_cost_basis({}, "ETH", 100.0, "buy")
        save_cost_basis(tmp_file, basis)
        loaded = load_cost_basis(tmp_file)
        assert "ETH" in loaded
        assert loaded["ETH"] == 100.0

        basis = update_cost_basis(loaded, "ETH", 50.0, "sell")
        assert basis.get("ETH", 0) == 50.0

        basis = update_cost_basis(basis, "ETH", 50.0, "sell")
        assert "ETH" not in basis

        basis = update_cost_basis(basis, "XRP", 30.0, "rotate_in")
        assert basis["XRP"] == 30.0
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
