from __future__ import annotations

from guarded_alpha.models import (
    AgentMandate,
    ExecutionReceipt,
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


def build_run_card(
    *,
    run_id: str,
    decision: TradeDecision,
    vibe_score: VibeScore,
    risk: RiskVerdict,
    receipt: ExecutionReceipt | None,
    mandate: AgentMandate,
) -> RunCard:
    tx_hash = receipt.tx_hash if receipt else None
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
            f"- Risk: {risk.status.value}",
            f"- Receipt: {receipt.message if receipt else 'none'}",
            f"- BscTrace: {bsc_trace_url(tx_hash) or 'n/a'}",
        ]
    )
    return RunCard(title, summary, bsc_trace_url(tx_hash), proof, markdown)
