from __future__ import annotations

from pathlib import Path

from guarded_alpha.models import (
    AgentMandate,
    DecisionAction,
    MarketSnapshot,
    PortfolioState,
    RiskStatus,
    RiskVerdict,
    TradeDecision,
    now_utc,
)


def evaluate_risk(
    decision: TradeDecision,
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    mandate: AgentMandate,
    proposed_slippage_bps: int = 50,
) -> RiskVerdict:
    reasons: list[str] = []
    checked_at = now_utc()

    if Path(mandate.kill_switch_path).exists():
        reasons.append("Kill switch file is present.")

    data_age = (checked_at - snapshot.captured_at).total_seconds()
    if data_age > mandate.max_data_age_seconds:
        reasons.append(f"Market data is stale: {int(data_age)}s old.")

    if portfolio.drawdown_pct >= mandate.max_drawdown_pct:
        reasons.append(
            f"Drawdown {portfolio.drawdown_pct:.2f}% exceeds cap {mandate.max_drawdown_pct:.2f}%."
        )

    if portfolio.daily_pnl_pct <= -mandate.daily_loss_limit_pct:
        reasons.append(
            f"Daily loss {portfolio.daily_pnl_pct:.2f}% exceeds cap "
            f"{mandate.daily_loss_limit_pct:.2f}%."
        )

    if decision.action == DecisionAction.HOLD:
        return RiskVerdict(RiskStatus.REJECTED, [decision.reason], checked_at)

    if not decision.symbol or decision.symbol.upper() not in mandate.eligible_symbols:
        reasons.append("Decision token is not in the eligible symbol allowlist.")

    max_trade_notional = portfolio.total_value_usd * (mandate.max_trade_pct / 100.0)
    if decision.notional_usd <= 0:
        reasons.append("Decision notional must be positive.")
    if decision.notional_usd > max_trade_notional:
        reasons.append("Decision notional exceeds max trade cap.")

    stable_after = portfolio.stable_value_usd - decision.notional_usd
    stable_after_pct = (stable_after / portfolio.total_value_usd) * 100.0
    if stable_after_pct < mandate.min_stable_reserve_pct:
        reasons.append(
            f"Stable reserve after trade {stable_after_pct:.2f}% would fall below "
            f"{mandate.min_stable_reserve_pct:.2f}%."
        )

    if proposed_slippage_bps > mandate.max_slippage_bps:
        reasons.append(
            f"Slippage {proposed_slippage_bps} bps exceeds cap {mandate.max_slippage_bps} bps."
        )

    status = RiskStatus.REJECTED if reasons else RiskStatus.APPROVED
    if not reasons:
        reasons.append("Risk gate approved inside mandate.")
    return RiskVerdict(status, reasons, checked_at)
