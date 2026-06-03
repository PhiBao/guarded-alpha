from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from guarded_alpha.audit import AuditLog
from guarded_alpha.bnb_identity import BNBIdentityAdapter
from guarded_alpha.competition import competition_state
from guarded_alpha.config import load_config
from guarded_alpha.execution import TWAKExecutionAdapter
from guarded_alpha.models import to_jsonable
from guarded_alpha.runner import run_competition_tick, run_once

app = FastAPI(title="Guarded Alpha Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


@app.get("/health")
def health() -> dict:
    config = load_config()
    return {
        "ok": True,
        "live_trading_enabled": config.live_trading_enabled,
        "cmc_use_fixtures": config.cmc_use_fixtures,
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
        "bnb_identity": BNBIdentityAdapter.from_env().status(),
        "competition": to_jsonable(competition_state()),
    }


@app.get("/ledger")
def ledger(limit: int = 25) -> list[dict]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return AuditLog(load_config().audit_path).read_recent(limit)


@app.post("/dry-run")
def dry_run() -> dict:
    run = run_once(load_config())
    return to_jsonable(run)


@app.post("/competition/register")
def register_competition() -> dict:
    config = load_config()
    state = competition_state()
    if not state.is_registration_open:
        raise HTTPException(status_code=409, detail="registration deadline has passed")
    adapter = TWAKExecutionAdapter(config.twak_bin, config.competition_contract)
    return adapter.register_competition()


@app.get("/competition/status")
def get_competition_status() -> dict:
    config = load_config()
    adapter = TWAKExecutionAdapter(config.twak_bin, config.competition_contract)
    return {"local": to_jsonable(competition_state()), "twak": adapter.competition_status()}


@app.post("/competition/tick")
def competition_tick() -> dict:
    run = run_competition_tick(load_config())
    if run is None:
        return {"ran": False, "competition": to_jsonable(competition_state())}
    return {"ran": True, "run": to_jsonable(run)}


def main() -> None:
    import uvicorn

    uvicorn.run("guarded_alpha.app:app", host="127.0.0.1", port=8000, reload=False)
