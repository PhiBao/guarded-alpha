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

    target_symbol = decision.symbol.upper() if decision.symbol else None
    from_symbol = str(decision.inputs.get("from_symbol") or "").upper()
    if decision.action == DecisionAction.SELL:
        from_symbol = from_symbol or target_symbol or ""

    if not target_symbol or target_symbol not in mandate.eligible_symbols:
        reasons.append("Decision token is not in the eligible symbol allowlist.")
    if decision.action == DecisionAction.ROTATE and from_symbol not in mandate.eligible_symbols:
        reasons.append("Rotation source token is not in the eligible symbol allowlist.")

    max_trade_notional = portfolio.total_value_usd * (mandate.max_trade_pct / 100.0)
    if decision.notional_usd <= 0:
        reasons.append("Decision notional must be positive.")
    if decision.notional_usd > max_trade_notional:
        reasons.append("Decision notional exceeds max trade cap.")

    held_value = portfolio.positions.get(from_symbol, 0.0) if from_symbol else 0.0
    if decision.action == DecisionAction.SELL and decision.notional_usd > held_value:
        reasons.append("Sell notional exceeds held position value.")
    if decision.action == DecisionAction.ROTATE and decision.notional_usd > held_value:
        reasons.append("Rotation notional exceeds held source position value.")

    if decision.action == DecisionAction.SELL:
        stable_after = portfolio.stable_value_usd + decision.notional_usd
    elif decision.action == DecisionAction.BUY:
        stable_after = portfolio.stable_value_usd - decision.notional_usd
    else:
        stable_after = portfolio.stable_value_usd
    if stable_after < mandate.min_cash_buffer_usd:
        reasons.append(
            f"Cash buffer after trade ${stable_after:.2f} would fall below "
            f"${mandate.min_cash_buffer_usd:.2f}."
        )

    if decision.action in {DecisionAction.BUY, DecisionAction.ROTATE} and target_symbol:
        target_after = portfolio.positions.get(target_symbol, 0.0) + decision.notional_usd
        target_after_pct = (target_after / portfolio.total_value_usd) * 100.0
        if target_after_pct > mandate.max_position_pct:
            reasons.append(
                f"Target position after trade {target_after_pct:.2f}% would exceed "
                f"{mandate.max_position_pct:.2f}% cap."
            )

    expected_edge_bps = decision.inputs.get("expected_edge_bps")
    if decision.action in {DecisionAction.BUY, DecisionAction.ROTATE}:
        try:
            edge_bps = int(expected_edge_bps)
        except (TypeError, ValueError):
            edge_bps = 0
        if edge_bps < mandate.min_expected_edge_bps:
            reasons.append(
                f"Expected edge {edge_bps} bps is below "
                f"{mandate.min_expected_edge_bps} bps minimum."
            )

    if proposed_slippage_bps > mandate.max_slippage_bps:
        reasons.append(
            f"Slippage {proposed_slippage_bps} bps exceeds cap {mandate.max_slippage_bps} bps."
        )

    status = RiskStatus.REJECTED if reasons else RiskStatus.APPROVED
    if not reasons:
        reasons.append("Risk gate approved inside mandate.")
    return RiskVerdict(status, reasons, checked_at)
