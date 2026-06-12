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
from guarded_alpha.config import AppConfig, load_config
from guarded_alpha.execution import DryRunExecutionAdapter, ExecutionAdapter, TWAKExecutionAdapter
from guarded_alpha.models import AgentRun, RiskStatus, now_utc, to_jsonable
from guarded_alpha.portfolio import (
    FixturePortfolioProvider,
    PortfolioProvider,
    TWAKPortfolioProvider,
)
from guarded_alpha.risk import evaluate_risk
from guarded_alpha.run_card import build_run_card
from guarded_alpha.strategy import evaluate_strategy


def build_market_provider(config: AppConfig) -> MarketDataProvider:
    if config.cmc_use_fixtures:
        return FixtureCMCProvider()
    if config.cmc_api_key:
        return CMCAPIProvider(config.cmc_api_key)
    return CMCCommandProvider(config.cmc_bin)


def build_execution_adapter(config: AppConfig) -> ExecutionAdapter:
    if config.live_trading_enabled:
        return TWAKExecutionAdapter(
            config.twak_bin,
            config.competition_contract,
            source_symbol=config.trade_source_symbol,
        )
    return DryRunExecutionAdapter()


def build_portfolio_provider(config: AppConfig) -> PortfolioProvider:
    if config.portfolio_use_fixtures:
        return FixturePortfolioProvider()
    return TWAKPortfolioProvider(
        TWAKExecutionAdapter(
            config.twak_bin,
            config.competition_contract,
            source_symbol=config.trade_source_symbol,
        ),
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
    decision, vibe_score = evaluate_strategy(
        snapshot,
        portfolio,
        resolved.mandate,
        strategy_weights=resolved.strategy_weights,
        force_qualification_trade=force_qualification_trade,
        min_trade_usd=resolved.min_daily_trade_usd,
    )
    risk = evaluate_risk(decision, snapshot, portfolio, resolved.mandate)
    receipt = build_execution_adapter(resolved).execute(decision, risk)
    run_id = str(uuid.uuid4())
    run_card = build_run_card(
        run_id=run_id,
        decision=decision,
        vibe_score=vibe_score,
        risk=risk,
        receipt=receipt,
        mandate=resolved.mandate,
    )

    run = AgentRun(
        run_id=run_id,
        snapshot=snapshot,
        portfolio=portfolio,
        mandate=resolved.mandate,
        vibe_score=vibe_score,
        decision=decision,
        risk=risk,
        receipt=receipt if risk.status == RiskStatus.APPROVED else receipt,
        run_card=run_card,
        created_at=now_utc(),
    )
    audit.append(run)
    return run


def run_scheduled_tick(config: AppConfig | None = None) -> AgentRun | None:
    resolved = config or load_config()
    audit = AuditLog(resolved.audit_path)
    today = now_utc().date()
    if resolved.live_trading_enabled:
        already_ran = audit.has_submitted_trade_on(today)
    else:
        already_ran = audit.has_run_on(today)
    if already_ran:
        return None
    return run_once(
        resolved,
        force_qualification_trade=resolved.qualification_trade_enabled,
    )


def run_competition_tick(config: AppConfig | None = None) -> AgentRun | None:
    return run_scheduled_tick(config)


def main() -> None:
    run = run_once()
    print(json.dumps(to_jsonable(run), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
