from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from guarded_alpha.audit import AuditLog
from guarded_alpha.bnb_identity import BNBIdentityAdapter
from guarded_alpha.competition import competition_state
from guarded_alpha.config import load_config
from guarded_alpha.daily import daily_trade_status
from guarded_alpha.execution import TWAKExecutionAdapter
from guarded_alpha.models import to_jsonable
from guarded_alpha.portfolio import TWAKPortfolioProvider
from guarded_alpha.runner import run_once, run_scheduled_tick

app = FastAPI(title="Guarded Alpha Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


def _twak_adapter() -> TWAKExecutionAdapter:
    config = load_config()
    return TWAKExecutionAdapter(
        config.twak_bin,
        config.competition_contract,
        source_symbol=config.trade_source_symbol,
    )


@app.get("/health")
def health() -> dict:
    config = load_config()
    return {
        "ok": True,
        "live_trading_enabled": config.live_trading_enabled,
        "cmc_use_fixtures": config.cmc_use_fixtures,
        "portfolio_use_fixtures": config.portfolio_use_fixtures,
    }


@app.get("/mandate")
def mandate() -> dict:
    return to_jsonable(load_config().mandate)


@app.get("/status")
def status() -> dict:
    config = load_config()
    ledger = AuditLog(config.audit_path).read_recent(limit=1)
    return {
        "health": health(),
        "mandate": to_jsonable(config.mandate),
        "latest_run": ledger[0] if ledger else None,
        "daily_status": to_jsonable(daily_trade_status(AuditLog(config.audit_path))),
        "bnb_identity": BNBIdentityAdapter.from_env().status(),
        "competition": to_jsonable(competition_state()),
    }


@app.get("/ledger")
def ledger(limit: int = 25) -> list[dict]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return AuditLog(load_config().audit_path).read_recent(limit)


@app.get("/run-card/{run_id}")
def run_card(run_id: str) -> dict:
    row = AuditLog(load_config().audit_path).find_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return row.get("run_card") or {}


@app.post("/dry-run")
def dry_run() -> dict:
    config = replace(load_config(), live_trading_enabled=False)
    run = run_once(config)
    return to_jsonable(run)


@app.post("/run-cycle")
def run_cycle() -> dict:
    run = run_once(load_config())
    return to_jsonable(run)


@app.post("/competition/register")
def register_competition() -> dict:
    state = competition_state()
    if not state.is_registration_open:
        raise HTTPException(status_code=409, detail="registration deadline has passed")
    adapter = _twak_adapter()
    try:
        return adapter.register_competition()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/competition/status")
def get_competition_status() -> dict:
    adapter = _twak_adapter()
    try:
        twak_status = adapter.competition_status()
    except RuntimeError as exc:
        twak_status = {"ok": False, "error": str(exc)}
    return {"local": to_jsonable(competition_state()), "twak": twak_status}


@app.get("/registration/status")
def get_registration_status() -> dict:
    return get_competition_status()


@app.get("/competition/daily-status")
def get_daily_status() -> list[dict]:
    return to_jsonable(daily_trade_status(AuditLog(load_config().audit_path)))


@app.get("/competition/readiness")
def get_competition_readiness() -> dict:
    config = load_config()
    adapter = _twak_adapter()
    audit = AuditLog(config.audit_path)

    try:
        twak_status = adapter.competition_status()
    except RuntimeError as exc:
        twak_status = {"registered": False, "error": str(exc)}

    try:
        portfolio_payload = adapter.wallet_portfolio()
        portfolio = TWAKPortfolioProvider(adapter, config.mandate.stable_symbols)._parse_portfolio(
            portfolio_payload
        )
        holdings = portfolio.positions
    except Exception as exc:
        portfolio = None
        holdings = {}
        portfolio_error = str(exc)
    else:
        portfolio_error = None

    eligible_holdings = {
        symbol: value
        for symbol, value in holdings.items()
        if symbol.upper() in config.mandate.eligible_symbols and value > 0
    }
    in_scope_value = round(sum(eligible_holdings.values()), 2)
    submitted_runs = [
        row for row in audit.read_recent(limit=1000) if (row.get("receipt") or {}).get("submitted")
    ]

    registered = bool(twak_status.get("registered"))
    has_in_scope_assets = in_scope_value > 1.0
    live_ready = bool(
        registered
        and has_in_scope_assets
        and config.live_trading_enabled
        and portfolio is not None
        and not portfolio_error
    )

    return {
        "registered": registered,
        "participant": twak_status.get("participant"),
        "registration_status": twak_status,
        "bnb_identity": BNBIdentityAdapter.from_env().status(),
        "official_timeline": to_jsonable(competition_state()),
        "twak_deadline": twak_status.get("deadline"),
        "live_trading_enabled": config.live_trading_enabled,
        "source_symbol": config.trade_source_symbol,
        "eligible_symbols": sorted(config.mandate.eligible_symbols),
        "in_scope_value_usd": in_scope_value,
        "eligible_holdings": eligible_holdings,
        "portfolio_value_usd": portfolio.total_value_usd if portfolio else 0,
        "portfolio_error": portfolio_error,
        "submitted_trade_count": len(submitted_runs),
        "latest_submitted_run": submitted_runs[-1] if submitted_runs else None,
        "requirements": [
            {
                "label": "Agent registered on BSC competition contract",
                "ok": registered,
            },
            {
                "label": "Wallet holds more than $1 of in-scope assets",
                "ok": has_in_scope_assets,
            },
            {
                "label": "Live trading mode enabled",
                "ok": config.live_trading_enabled,
            },
            {
                "label": "At least one live submitted trade recorded locally",
                "ok": bool(submitted_runs),
            },
        ],
        "ready": live_ready,
    }


@app.get("/readiness")
def get_readiness() -> dict:
    return get_competition_readiness()


@app.post("/competition/tick")
def competition_tick() -> dict:
    run = run_scheduled_tick(load_config())
    if run is None:
        return {"ran": False, "reason": "max daily submitted trade cap reached"}
    return {"ran": True, "run": to_jsonable(run)}


@app.post("/scheduler/tick")
def scheduler_tick() -> dict:
    return competition_tick()


@app.get("/wallet/status")
def wallet_status() -> dict:
    adapter = _twak_adapter()
    try:
        return adapter.wallet_status()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/wallet/addresses")
def wallet_addresses() -> dict:
    adapter = _twak_adapter()
    try:
        return adapter.wallet_addresses()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/wallet/quote")
def wallet_quote(
    amount_usd: float = 5.0,
    from_symbol: str = "USDT",
    to_symbol: str = "CAKE",
) -> dict:
    if amount_usd <= 0 or amount_usd > 100:
        raise HTTPException(status_code=400, detail="amount_usd must be between 0 and 100")
    adapter = _twak_adapter()
    try:
        return adapter.quote_swap(amount_usd, from_symbol.upper(), to_symbol.upper())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run("guarded_alpha.app:app", host="127.0.0.1", port=8000, reload=False)
