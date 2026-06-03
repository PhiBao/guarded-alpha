from __future__ import annotations

import json
import uuid

from guarded_alpha.audit import AuditLog
from guarded_alpha.cmc import (
    CMCAPIProvider,
    CMCCommandProvider,
    FixtureCMCProvider,
    MarketDataProvider,
)
from guarded_alpha.competition import competition_state
from guarded_alpha.config import AppConfig, load_config
from guarded_alpha.execution import DryRunExecutionAdapter, ExecutionAdapter, TWAKExecutionAdapter
from guarded_alpha.models import AgentRun, RiskStatus, now_utc, to_jsonable
from guarded_alpha.portfolio import (
    FixturePortfolioProvider,
    PortfolioProvider,
    TWAKPortfolioProvider,
)
from guarded_alpha.risk import evaluate_risk
from guarded_alpha.strategy import choose_trade


def build_market_provider(config: AppConfig) -> MarketDataProvider:
    if config.cmc_use_fixtures:
        return FixtureCMCProvider()
    if config.cmc_api_key:
        return CMCAPIProvider(config.cmc_api_key)
    return CMCCommandProvider(config.cmc_bin)


def build_execution_adapter(config: AppConfig) -> ExecutionAdapter:
    if config.live_trading_enabled:
        return TWAKExecutionAdapter(config.twak_bin, config.competition_contract)
    return DryRunExecutionAdapter()


def build_portfolio_provider(config: AppConfig) -> PortfolioProvider:
    if config.portfolio_use_fixtures:
        return FixturePortfolioProvider()
    return TWAKPortfolioProvider(
        TWAKExecutionAdapter(config.twak_bin, config.competition_contract),
        config.mandate.stable_symbols,
    )


def run_once(
    config: AppConfig | None = None,
    *,
    force_qualification_trade: bool = False,
) -> AgentRun:
    resolved = config or load_config()
    audit = AuditLog(resolved.audit_path)
    snapshot = build_market_provider(resolved).snapshot(resolved.mandate.eligible_symbols)
    portfolio = build_portfolio_provider(resolved).portfolio()
    decision = choose_trade(
        snapshot,
        portfolio,
        resolved.mandate,
        force_qualification_trade=force_qualification_trade,
        min_trade_usd=resolved.min_daily_trade_usd,
    )
    risk = evaluate_risk(decision, snapshot, portfolio, resolved.mandate)
    receipt = build_execution_adapter(resolved).execute(decision, risk)

    run = AgentRun(
        run_id=str(uuid.uuid4()),
        snapshot=snapshot,
        portfolio=portfolio,
        mandate=resolved.mandate,
        decision=decision,
        risk=risk,
        receipt=receipt if risk.status == RiskStatus.APPROVED else receipt,
        created_at=now_utc(),
    )
    audit.append(run)
    return run


def run_competition_tick(config: AppConfig | None = None) -> AgentRun | None:
    resolved = config or load_config()
    state = competition_state()
    if not state.is_trading_window:
        return None
    audit = AuditLog(resolved.audit_path)
    if audit.has_submitted_trade_on(state.now.date()):
        return None
    return run_once(
        resolved,
        force_qualification_trade=resolved.qualification_trade_enabled,
    )


def main() -> None:
    run = run_once()
    print(json.dumps(to_jsonable(run), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
