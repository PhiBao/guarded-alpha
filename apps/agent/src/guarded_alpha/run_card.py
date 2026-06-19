from __future__ import annotations

from guarded_alpha.models import (
    AgentMandate,
    ExecutionReceipt,
    MarketSnapshot,
    PortfolioState,
    RiskVerdict,
    RunCard,
    TradeDecision,
    VibeScore,
    to_jsonable,
)


def bsc_trace_url(tx_hash: str | None) -> str | None:
    if not tx_hash:
        return None
    return f"https://bsctrace.com/tx/{tx_hash}"


def bscscan_url(tx_hash: str | None) -> str | None:
    if not tx_hash:
        return None
    return f"https://bscscan.com/tx/{tx_hash}"


def build_run_card(
    *,
    run_id: str,
    decision: TradeDecision,
    vibe_score: VibeScore,
    risk: RiskVerdict,
    receipt: ExecutionReceipt | None,
    mandate: AgentMandate,
    snapshot: MarketSnapshot,
    portfolio_before: PortfolioState,
    portfolio_after: PortfolioState | None = None,
) -> RunCard:
    tx_hash = receipt.tx_hash if receipt else None
    explorer_url = bscscan_url(tx_hash) or bsc_trace_url(tx_hash)
    title = f"Guarded Alpha Run {run_id[:8]}"
    summary = (
        f"{decision.action.value.upper()} {decision.symbol or 'NONE'} "
        f"score={decision.score:.4f} risk={risk.status.value}"
    )
    proof = {
        "run_id": run_id,
        "decision": to_jsonable(decision),
        "vibe_score": to_jsonable(vibe_score),
        "risk": to_jsonable(risk),
        "receipt": to_jsonable(receipt),
        "market": {
            "source": snapshot.source,
            "captured_at": snapshot.captured_at,
            "fear_greed": snapshot.fear_greed,
            "trend_signals": snapshot.trend_signals,
            "provenance": snapshot.provenance,
        },
        "portfolio_before": to_jsonable(portfolio_before),
        "portfolio_after": to_jsonable(portfolio_after),
        "explorer": {
            "bscscan": bscscan_url(tx_hash),
            "bsctrace": bsc_trace_url(tx_hash),
        },
        "mandate": {
            "max_drawdown_pct": mandate.max_drawdown_pct,
            "daily_loss_limit_pct": mandate.daily_loss_limit_pct,
            "max_trade_pct": mandate.max_trade_pct,
            "max_slippage_bps": mandate.max_slippage_bps,
            "min_stable_reserve_pct": mandate.min_stable_reserve_pct,
        },
    }
    markdown = "\n".join(
        [
            f"# {title}",
            "",
            f"- Summary: {summary}",
            f"- BNB Vibe Score: {vibe_score.score:.4f}",
            f"- Confidence: {vibe_score.confidence:.4f}",
            f"- Market regime: {snapshot.trend_signals.get('market_regime', 'unknown')}",
            f"- Source: {snapshot.source}",
            f"- Risk: {risk.status.value}",
            f"- Receipt: {receipt.message if receipt else 'none'}",
            f"- Tx: {tx_hash or 'n/a'}",
            f"- Explorer: {explorer_url or 'n/a'}",
        ]
    )
    return RunCard(title, summary, explorer_url, proof, markdown)
