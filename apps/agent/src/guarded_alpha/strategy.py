from __future__ import annotations

from guarded_alpha.models import (
    AgentMandate,
    DecisionAction,
    MarketAsset,
    MarketSnapshot,
    PortfolioState,
    TradeDecision,
)


def _score_asset(asset: MarketAsset, fear_greed: int | None) -> float:
    momentum = max(min(asset.change_24h_pct / 10.0, 1.0), -1.0)
    sentiment = max(min(asset.sentiment_score, 1.0), -1.0)
    volatility_penalty = min(asset.volatility_7d_pct / 20.0, 1.0)
    liquidity_bonus = min(asset.volume_24h_usd / 1_000_000_000, 1.0) * 0.15
    regime = 0.05 if fear_greed is not None and 45 <= fear_greed <= 75 else -0.05
    return (
        (0.45 * momentum)
        + (0.3 * sentiment)
        - (0.25 * volatility_penalty)
        + liquidity_bonus
        + regime
    )


def choose_trade(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    mandate: AgentMandate,
    *,
    force_qualification_trade: bool = False,
    min_trade_usd: float = 5.0,
) -> TradeDecision:
    candidates: list[tuple[MarketAsset, float]] = []
    for asset in snapshot.assets:
        symbol = asset.symbol.upper()
        if symbol in mandate.stable_symbols or symbol not in mandate.eligible_symbols:
            continue
        candidates.append((asset, _score_asset(asset, snapshot.fear_greed)))

    if not candidates:
        return TradeDecision(
            action=DecisionAction.HOLD,
            symbol=None,
            score=0.0,
            notional_usd=0.0,
            reason="No eligible non-stable assets were available.",
        )

    best_asset, best_score = max(candidates, key=lambda item: item[1])
    trade_notional = round(portfolio.total_value_usd * (mandate.max_trade_pct / 100.0), 2)

    if best_score < mandate.min_signal_score and not force_qualification_trade:
        return TradeDecision(
            action=DecisionAction.HOLD,
            symbol=best_asset.symbol,
            score=round(best_score, 4),
            notional_usd=0.0,
            reason="Best signal did not clear the minimum score.",
            inputs={"best_symbol": best_asset.symbol},
        )

    notional_usd = trade_notional
    reason = "Best eligible asset cleared momentum, sentiment, volatility, and liquidity filters."
    if force_qualification_trade and best_score < mandate.min_signal_score:
        notional_usd = min(trade_notional, min_trade_usd)
        reason = (
            "Competition qualification trade: best eligible asset selected below normal "
            "signal threshold, still subject to risk gate."
        )

    return TradeDecision(
        action=DecisionAction.BUY,
        symbol=best_asset.symbol,
        score=round(best_score, 4),
        notional_usd=round(notional_usd, 2),
        reason=reason,
        inputs={
            "change_24h_pct": best_asset.change_24h_pct,
            "sentiment_score": best_asset.sentiment_score,
            "volatility_7d_pct": best_asset.volatility_7d_pct,
            "volume_24h_usd": best_asset.volume_24h_usd,
            "fear_greed": snapshot.fear_greed,
        },
    )
