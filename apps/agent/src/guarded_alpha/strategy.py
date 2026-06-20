from __future__ import annotations

import math

from guarded_alpha.models import (
    AgentMandate,
    DecisionAction,
    MarketAsset,
    MarketSnapshot,
    PortfolioState,
    StrategyVote,
    TradeDecision,
    VibeScore,
    VoteDirection,
)

DEFAULT_STRATEGY_WEIGHTS = {
    "momentum": 0.25,
    "mean_reversion": 0.15,
    "liquidity": 0.15,
    "sentiment": 0.20,
    "regime": 0.10,
    "route": 0.10,
    "rebalance": 0.05,
}


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(min(value, high), low)


def _direction(signal: float) -> VoteDirection:
    if signal > 0.12:
        return VoteDirection.LONG
    if signal < -0.12:
        return VoteDirection.SHORT
    return VoteDirection.NEUTRAL


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    merged = dict(DEFAULT_STRATEGY_WEIGHTS)
    merged.update({key: max(value, 0.0) for key, value in weights.items()})
    total = sum(merged.values())
    if total <= 0:
        return DEFAULT_STRATEGY_WEIGHTS
    return {key: value / total for key, value in merged.items()}


def _asset_votes(
    asset: MarketAsset,
    portfolio: PortfolioState,
    mandate: AgentMandate,
    fear_greed: int | None,
    weights: dict[str, float],
) -> list[StrategyVote]:
    stable_pct = (portfolio.stable_value_usd / portfolio.total_value_usd) * 100.0
    momentum = _clamp(asset.change_24h_pct / 10.0)
    mean_reversion = _clamp(-asset.change_24h_pct / 14.0)
    liquidity = _clamp((asset.volume_24h_usd / 500_000_000) - 0.2, 0.0, 1.0)
    sentiment = _clamp(asset.sentiment_score)
    route = _clamp(1.0 - (asset.volatility_7d_pct / 25.0), -1.0, 1.0)
    rebalance = 0.25 if stable_pct > mandate.min_stable_reserve_pct + 15 else -0.35

    if fear_greed is None:
        regime = 0.0
    elif 35 <= fear_greed <= 75:
        regime = 0.35
    elif fear_greed > 85:
        regime = -0.25
    else:
        regime = -0.1

    raw = {
        "momentum": (momentum, f"24h momentum is {asset.change_24h_pct:.2f}%."),
        "mean_reversion": (mean_reversion, "Counter-trend vote from short-term move."),
        "liquidity": (liquidity, f"24h volume is ${asset.volume_24h_usd:,.0f}."),
        "sentiment": (sentiment, f"CMC sentiment proxy is {asset.sentiment_score:.2f}."),
        "regime": (
            regime,
            f"Fear/greed regime is {fear_greed if fear_greed is not None else 'n/a'}.",
        ),
        "route": (route, f"Volatility route proxy is {asset.volatility_7d_pct:.2f}%."),
        "rebalance": (rebalance, f"Stable reserve is {stable_pct:.2f}%."),
    }
    votes: list[StrategyVote] = []
    for name, (signal, reason) in raw.items():
        confidence = min(abs(signal) + 0.2, 1.0)
        votes.append(
            StrategyVote(
                name=name,
                direction=_direction(signal),
                signal=round(signal, 4),
                confidence=round(confidence, 4),
                weight=round(weights.get(name, 0.0), 4),
                reason=reason,
            )
        )
    return votes


def _weighted_score(votes: list[StrategyVote]) -> float:
    return sum(vote.signal * vote.weight for vote in votes)


def _agent_pipeline(
    *,
    symbol: str | None,
    score: float,
    confidence: float,
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    action: DecisionAction,
    reason: str,
) -> list[dict[str, str | float | None]]:
    market_regime = str(snapshot.trend_signals.get("market_regime", "unknown"))
    stable_pct = round((portfolio.stable_value_usd / portfolio.total_value_usd) * 100.0, 2)
    return [
        {
            "agent": "Scout",
            "role": "Find CMC market candidates",
            "output": f"{symbol or 'none'} selected from {snapshot.source}; regime={market_regime}",
        },
        {
            "agent": "Quant",
            "role": "Score momentum, reversion, liquidity, regime, route, and reserve fit",
            "output": f"score={score:.4f}; confidence={confidence:.4f}",
        },
        {
            "agent": "Risk",
            "role": "Preserve bankroll before chasing upside",
            "output": f"stable_reserve={stable_pct:.2f}%; action={action.value}",
        },
        {
            "agent": "Executor",
            "role": "Submit only risk-approved TWAK swaps",
            "output": reason,
        },
        {
            "agent": "Reviewer",
            "role": "Write replayable proof for post-trade review",
            "output": "audit ledger captures thesis, quote, receipt, and mandate",
        },
    ]


def _decision_inputs(
    *,
    base: dict,
    symbol: str | None,
    score: float,
    confidence: float,
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    action: DecisionAction,
    reason: str,
) -> dict:
    return {
        **base,
        "market_regime": snapshot.trend_signals.get("market_regime", "unknown"),
        "trend_signals": snapshot.trend_signals,
        "market_provenance": snapshot.provenance,
        "agent_pipeline": _agent_pipeline(
            symbol=symbol,
            score=score,
            confidence=confidence,
            snapshot=snapshot,
            portfolio=portfolio,
            action=action,
            reason=reason,
        ),
    }


def _floor_cents(value: float) -> float:
    return math.floor(value * 100) / 100


def _trade_notional(portfolio: PortfolioState, mandate: AgentMandate) -> float:
    return _floor_cents(portfolio.total_value_usd * (mandate.max_trade_pct / 100.0))


def _route_identifier(asset: MarketAsset) -> str:
    return asset.contract_address or asset.symbol


def _expected_edge_bps(score: float, min_signal_score: float) -> int:
    return max(0, round((score - min_signal_score) * 10_000))


def _held_non_stable_positions(
    portfolio: PortfolioState,
    mandate: AgentMandate,
) -> dict[str, float]:
    return {
        symbol.upper(): value
        for symbol, value in portfolio.positions.items()
        if symbol.upper() in mandate.eligible_symbols
        and symbol.upper() not in mandate.stable_symbols
        and value > 0
    }


def _weakest_funding_candidate(
    sell_candidates: list[tuple[MarketAsset, list[StrategyVote], float, float]],
    target_symbol: str,
) -> tuple[MarketAsset, list[StrategyVote], float, float] | None:
    if not sell_candidates:
        return None
    alternatives = [
        item for item in sell_candidates if item[0].symbol.upper() != target_symbol.upper()
    ]
    return min(alternatives or sell_candidates, key=lambda item: item[2])


def _candidate_rankings(
    candidates: list[tuple[MarketAsset, list[StrategyVote], float]],
    *,
    limit: int = 8,
) -> list[dict[str, float | str]]:
    ranked = sorted(candidates, key=lambda item: item[2], reverse=True)
    rows: list[dict[str, float | str]] = []
    for asset, votes, score in ranked[:limit]:
        confidence = sum(vote.confidence * vote.weight for vote in votes)
        rows.append(
            {
                "symbol": asset.symbol,
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "change_24h_pct": round(asset.change_24h_pct, 4),
                "volume_24h_usd": round(asset.volume_24h_usd, 2),
            }
        )
    return rows


def _rotate_decision(
    *,
    from_asset: MarketAsset,
    to_asset: MarketAsset,
    score: float,
    confidence: float,
    notional_usd: float,
    reason: str,
    votes: list[StrategyVote],
    inputs: dict,
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
) -> tuple[TradeDecision, VibeScore]:
    long_votes = sum(1 for vote in votes if vote.direction == VoteDirection.LONG)
    short_votes = sum(1 for vote in votes if vote.direction == VoteDirection.SHORT)
    neutral_votes = sum(1 for vote in votes if vote.direction == VoteDirection.NEUTRAL)
    vibe_score = VibeScore(
        symbol=to_asset.symbol,
        score=round(score, 4),
        confidence=round(confidence, 4),
        long_votes=long_votes,
        short_votes=short_votes,
        neutral_votes=neutral_votes,
        full_consensus=short_votes == 0 and neutral_votes <= 1,
        votes=votes,
        breakdown={vote.name: round(vote.signal * vote.weight, 4) for vote in votes},
    )
    return (
        TradeDecision(
            action=DecisionAction.ROTATE,
            symbol=to_asset.symbol,
            score=round(score, 4),
            notional_usd=round(notional_usd, 2),
            reason=reason,
            inputs=_decision_inputs(
                base={
                    **inputs,
                    "from_symbol": from_asset.symbol,
                    "to_symbol": to_asset.symbol,
                    "from_address": from_asset.contract_address,
                    "to_address": to_asset.contract_address,
                    "from_route": _route_identifier(from_asset),
                    "to_route": _route_identifier(to_asset),
                },
                symbol=to_asset.symbol,
                score=score,
                confidence=confidence,
                snapshot=snapshot,
                portfolio=portfolio,
                action=DecisionAction.ROTATE,
                reason=reason,
            ),
        ),
        vibe_score,
    )


def _sell_decision(
    *,
    symbol: str,
    score: float,
    notional_usd: float,
    reason: str,
    votes: list[StrategyVote],
    inputs: dict,
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
) -> tuple[TradeDecision, VibeScore]:
    stable_symbols = inputs.get("stable_symbols", {"USDC"})
    to_symbol = "USDC" if "USDC" in stable_symbols else next(iter(sorted(stable_symbols)), "USDC")
    long_votes = sum(1 for vote in votes if vote.direction == VoteDirection.LONG)
    short_votes = sum(1 for vote in votes if vote.direction == VoteDirection.SHORT)
    neutral_votes = sum(1 for vote in votes if vote.direction == VoteDirection.NEUTRAL)
    confidence = sum(vote.confidence * vote.weight for vote in votes)
    pipeline_symbol = str(inputs.get("target_buy_symbol") or symbol)
    pipeline_score = float(inputs.get("target_buy_score") or score)
    pipeline_confidence = float(inputs.get("target_buy_confidence") or confidence)
    vibe_score = VibeScore(
        symbol=symbol,
        score=round(score, 4),
        confidence=round(confidence, 4),
        long_votes=long_votes,
        short_votes=short_votes,
        neutral_votes=neutral_votes,
        full_consensus=False,
        votes=votes,
        breakdown={vote.name: round(vote.signal * vote.weight, 4) for vote in votes},
    )
    return (
        TradeDecision(
            action=DecisionAction.SELL,
            symbol=symbol,
            score=round(score, 4),
            notional_usd=round(notional_usd, 2),
            reason=reason,
            inputs=_decision_inputs(
                base={
                    **inputs,
                    "from_symbol": symbol,
                    "to_symbol": to_symbol,
                },
                symbol=pipeline_symbol,
                score=pipeline_score,
                confidence=pipeline_confidence,
                snapshot=snapshot,
                portfolio=portfolio,
                action=DecisionAction.SELL,
                reason=reason,
            ),
        ),
        vibe_score,
    )


def evaluate_strategy(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    mandate: AgentMandate,
    *,
    strategy_weights: dict[str, float] | None = None,
    force_qualification_trade: bool = False,
    min_trade_usd: float = 5.0,
    min_score_override: float | None = None,
    min_confidence: float | None = None,
) -> tuple[TradeDecision, VibeScore]:
    weights = _normalize_weights(strategy_weights or DEFAULT_STRATEGY_WEIGHTS)
    candidates: list[tuple[MarketAsset, list[StrategyVote], float]] = []
    for asset in snapshot.assets:
        symbol = asset.symbol.upper()
        if symbol in mandate.stable_symbols or symbol not in mandate.eligible_symbols:
            continue
        votes = _asset_votes(asset, portfolio, mandate, snapshot.fear_greed, weights)
        candidates.append((asset, votes, _weighted_score(votes)))

    if not candidates:
        vibe_score = VibeScore(None, 0.0, 0.0, 0, 0, 0, False, [], {})
        return (
            TradeDecision(
                action=DecisionAction.HOLD,
                symbol=None,
                score=0.0,
                notional_usd=0.0,
                reason="No eligible non-stable assets were available.",
                inputs=_decision_inputs(
                    base={},
                    symbol=None,
                    score=0.0,
                    confidence=0.0,
                    snapshot=snapshot,
                    portfolio=portfolio,
                    action=DecisionAction.HOLD,
                    reason="No eligible non-stable assets were available.",
                ),
            ),
            vibe_score,
        )

    trade_notional = _trade_notional(portfolio, mandate)
    held_positions = _held_non_stable_positions(portfolio, mandate)
    stable_pct = (portfolio.stable_value_usd / portfolio.total_value_usd) * 100.0
    candidate_rankings = _candidate_rankings(candidates)
    min_sell_notional = min(trade_notional, min_trade_usd)
    sell_candidates = [
        (asset, votes, score, held_positions.get(asset.symbol.upper(), 0.0))
        for asset, votes, score in candidates
        if held_positions.get(asset.symbol.upper(), 0.0) >= min_sell_notional
    ]

    best_asset, votes, best_score = max(candidates, key=lambda item: item[2])
    long_votes = sum(1 for vote in votes if vote.direction == VoteDirection.LONG)
    short_votes = sum(1 for vote in votes if vote.direction == VoteDirection.SHORT)
    neutral_votes = sum(1 for vote in votes if vote.direction == VoteDirection.NEUTRAL)
    confidence = sum(vote.confidence * vote.weight for vote in votes)
    vibe_score = VibeScore(
        symbol=best_asset.symbol,
        score=round(best_score, 4),
        confidence=round(confidence, 4),
        long_votes=long_votes,
        short_votes=short_votes,
        neutral_votes=neutral_votes,
        full_consensus=short_votes == 0 and neutral_votes <= 1,
        votes=votes,
        breakdown={vote.name: round(vote.signal * vote.weight, 4) for vote in votes},
    )
    min_signal_score = (
        mandate.min_signal_score if min_score_override is None else min_score_override
    )
    expected_edge_bps = _expected_edge_bps(best_score, min_signal_score)
    estimated_cost_bps = 35

    if min_confidence is not None and confidence < min_confidence:
        return (
            TradeDecision(
                action=DecisionAction.HOLD,
                symbol=best_asset.symbol,
                score=round(best_score, 4),
                notional_usd=0.0,
                reason=(
                    "BNB Vibe confidence did not clear the high-confidence execution gate."
                ),
                inputs=_decision_inputs(
                    base={
                        "best_symbol": best_asset.symbol,
                        "confidence": round(confidence, 4),
                        "min_confidence": min_confidence,
                        "expected_edge_bps": expected_edge_bps,
                        "estimated_cost_bps": estimated_cost_bps,
                        "candidate_rankings": candidate_rankings,
                    },
                    symbol=best_asset.symbol,
                    score=best_score,
                    confidence=confidence,
                    snapshot=snapshot,
                    portfolio=portfolio,
                    action=DecisionAction.HOLD,
                    reason="BNB Vibe confidence did not clear the high-confidence execution gate.",
                ),
            ),
            vibe_score,
        )

    if best_score < min_signal_score and not force_qualification_trade:
        if sell_candidates:
            weakest_asset, weakest_votes, weakest_score, position_value = min(
                sell_candidates, key=lambda item: item[2]
            )
            if weakest_score < 0:
                return _sell_decision(
                    symbol=weakest_asset.symbol,
                    score=weakest_score,
                    notional_usd=min(trade_notional, position_value, max(min_trade_usd, 1.0)),
                    reason="Weakest held asset has negative BNB Vibe Score; reducing exposure.",
                    votes=weakest_votes,
                    inputs={
                        "stable_pct": stable_pct,
                        "position_value_usd": position_value,
                        "stable_symbols": mandate.stable_symbols,
                    },
                    snapshot=snapshot,
                    portfolio=portfolio,
                )
        return (
            TradeDecision(
                action=DecisionAction.HOLD,
                symbol=best_asset.symbol,
                score=round(best_score, 4),
                notional_usd=0.0,
                reason="BNB Vibe Score did not clear the minimum signal threshold.",
                inputs=_decision_inputs(
                    base={
                        "best_symbol": best_asset.symbol,
                        "min_signal_score": min_signal_score,
                        "expected_edge_bps": expected_edge_bps,
                        "estimated_cost_bps": estimated_cost_bps,
                        "candidate_rankings": candidate_rankings,
                    },
                    symbol=best_asset.symbol,
                    score=best_score,
                    confidence=confidence,
                    snapshot=snapshot,
                    portfolio=portfolio,
                    action=DecisionAction.HOLD,
                    reason="BNB Vibe Score did not clear the minimum signal threshold.",
                ),
            ),
            vibe_score,
        )

    notional_usd = trade_notional
    reason = "BNB Vibe Score cleared strategy, liquidity, regime, and portfolio filters."
    if force_qualification_trade and best_score < min_signal_score:
        notional_usd = min(trade_notional, min_trade_usd)
        reason = (
            "Daily qualification trade selected below normal threshold, "
            "still subject to risk gate."
        )

    if expected_edge_bps < mandate.min_expected_edge_bps and not force_qualification_trade:
        return (
            TradeDecision(
                action=DecisionAction.HOLD,
                symbol=best_asset.symbol,
                score=round(best_score, 4),
                notional_usd=0.0,
                reason=(
                    "Expected edge did not clear estimated transaction cost and "
                    "minimum edge buffer."
                ),
                inputs=_decision_inputs(
                    base={
                        "best_symbol": best_asset.symbol,
                        "expected_edge_bps": expected_edge_bps,
                        "estimated_cost_bps": estimated_cost_bps,
                        "min_expected_edge_bps": mandate.min_expected_edge_bps,
                        "candidate_rankings": candidate_rankings,
                    },
                    symbol=best_asset.symbol,
                    score=best_score,
                    confidence=confidence,
                    snapshot=snapshot,
                    portfolio=portfolio,
                    action=DecisionAction.HOLD,
                    reason=(
                        "Expected edge did not clear estimated transaction cost and "
                        "minimum edge buffer."
                    ),
                ),
            ),
            vibe_score,
        )

    cash_available = max(portfolio.stable_value_usd - mandate.min_cash_buffer_usd, 0.0)
    buy_notional = min(notional_usd, cash_available)
    can_buy_from_stable = buy_notional >= min_trade_usd
    if buy_notional < notional_usd:
        funding_candidate = _weakest_funding_candidate(sell_candidates, best_asset.symbol)
        if funding_candidate is not None:
            weakest_asset, _weakest_votes, weakest_score, position_value = funding_candidate
            rotation_notional = min(notional_usd, position_value)
            if rotation_notional >= min_trade_usd:
                return _rotate_decision(
                    from_asset=weakest_asset,
                    to_asset=best_asset,
                    score=best_score,
                    confidence=confidence,
                    notional_usd=rotation_notional,
                    reason=(
                        f"{best_asset.symbol} has the strongest current edge; rotating "
                        f"from weaker held {weakest_asset.symbol} instead of spending "
                        "the cash buffer."
                    ),
                    votes=votes,
                    inputs={
                        "stable_pct": stable_pct,
                        "from_position_value_usd": position_value,
                        "from_score": round(weakest_score, 4),
                        "expected_edge_bps": expected_edge_bps,
                        "estimated_cost_bps": estimated_cost_bps,
                        "candidate_rankings": candidate_rankings,
                    },
                    snapshot=snapshot,
                    portfolio=portfolio,
                )
    if not can_buy_from_stable:
        return (
            TradeDecision(
                action=DecisionAction.HOLD,
                symbol=best_asset.symbol,
                score=round(best_score, 4),
                notional_usd=0.0,
                reason=(
                    "Buy signal cleared, but cash buffer left too little USDC and no "
                    "held asset could be rotated into the target."
                ),
                inputs=_decision_inputs(
                    base={
                        "best_symbol": best_asset.symbol,
                        "stable_pct": stable_pct,
                        "cash_available_usd": round(cash_available, 2),
                        "min_cash_buffer_usd": mandate.min_cash_buffer_usd,
                        "expected_edge_bps": expected_edge_bps,
                        "estimated_cost_bps": estimated_cost_bps,
                        "candidate_rankings": candidate_rankings,
                    },
                    symbol=best_asset.symbol,
                    score=best_score,
                    confidence=confidence,
                    snapshot=snapshot,
                    portfolio=portfolio,
                    action=DecisionAction.HOLD,
                    reason=(
                        "Buy signal cleared, but cash buffer left too little USDC and no "
                        "held asset could be rotated into the target."
                    ),
                ),
            ),
            vibe_score,
        )

    stable_source_symbol = next(
        iter(sorted(mandate.stable_symbols & set(portfolio.positions))),
        "USDC",
    )
    return (
        TradeDecision(
            action=DecisionAction.BUY,
            symbol=best_asset.symbol,
            score=round(best_score, 4),
            notional_usd=round(buy_notional, 2),
            reason=reason,
            inputs=_decision_inputs(
                base={
                    "change_24h_pct": best_asset.change_24h_pct,
                    "sentiment_score": best_asset.sentiment_score,
                    "volatility_7d_pct": best_asset.volatility_7d_pct,
                    "volume_24h_usd": best_asset.volume_24h_usd,
                    "fear_greed": snapshot.fear_greed,
                    "long_votes": long_votes,
                    "short_votes": short_votes,
                    "neutral_votes": neutral_votes,
                    "from_symbol": stable_source_symbol,
                    "to_symbol": best_asset.symbol,
                    "to_address": best_asset.contract_address,
                    "to_route": _route_identifier(best_asset),
                    "cash_available_usd": round(cash_available, 2),
                    "min_cash_buffer_usd": mandate.min_cash_buffer_usd,
                    "expected_edge_bps": expected_edge_bps,
                    "estimated_cost_bps": estimated_cost_bps,
                    "candidate_rankings": candidate_rankings,
                },
                symbol=best_asset.symbol,
                score=best_score,
                confidence=confidence,
                snapshot=snapshot,
                portfolio=portfolio,
                action=DecisionAction.BUY,
                reason=reason,
            ),
        ),
        vibe_score,
    )


def choose_trade(
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    mandate: AgentMandate,
    *,
    force_qualification_trade: bool = False,
    min_trade_usd: float = 5.0,
) -> TradeDecision:
    decision, _ = evaluate_strategy(
        snapshot,
        portfolio,
        mandate,
        force_qualification_trade=force_qualification_trade,
        min_trade_usd=min_trade_usd,
    )
    return decision
