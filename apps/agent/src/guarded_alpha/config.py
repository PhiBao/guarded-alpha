from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from guarded_alpha.competition import COMPETITION_CONTRACT, ELIGIBLE_TOKENS
from guarded_alpha.env import load_dotenv
from guarded_alpha.models import AgentMandate

DEFAULT_ELIGIBLE_SYMBOLS = {
    "AAVE",
    "ADA",
    "APE",
    "ASTER",
    "AVAX",
    "BCH",
    "CAKE",
    "DOGE",
    "DOT",
    "ETH",
    "FDUSD",
    "FET",
    "FIL",
    "FLOKI",
    "INJ",
    "LINK",
    "LTC",
    "PENDLE",
    "SFP",
    "TWT",
    "UNI",
    "USDC",
    "USDT",
    "XRP",
    "ZRO",
}

DEFAULT_STABLE_SYMBOLS = {
    "DAI",
    "DUSD",
    "EURI",
    "FDUSD",
    "FRAX",
    "FRXUSD",
    "LISUSD",
    "TUSD",
    "USDC",
    "USDD",
    "USDE",
    "USDF",
    "USD1",
    "USDT",
    "XUSD",
}

DEFAULT_ROUTE_DISABLED_SYMBOLS = {
    # Live TWAK/LiquidMesh verification on BSC reverted for XRP contract routes.
    "XRP",
}


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    audit_path: Path
    live_trading_enabled: bool
    twak_bin: str
    cmc_bin: str
    cmc_api_key: str | None
    cmc_use_fixtures: bool
    portfolio_use_fixtures: bool
    competition_contract: str
    trade_source_symbol: str
    min_daily_trade_usd: float
    scan_full_competition_universe: bool
    max_daily_trades: int
    scheduler_interval_seconds: int
    strategy_weights: dict[str, float]
    mandate: AgentMandate


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _symbols_env(name: str, default: set[str]) -> set[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return set(default)
    return {item.strip().upper() for item in raw.split(",") if item.strip()}


def load_config() -> AppConfig:
    load_dotenv()
    data_dir = Path(os.getenv("GUARDED_ALPHA_DATA_DIR", "data"))
    audit_path = data_dir / "audit.jsonl"
    kill_switch_path = os.getenv("GUARDED_ALPHA_KILL_SWITCH_PATH", str(data_dir / "KILL_SWITCH"))
    scan_full_competition_universe = _bool_env("SCAN_FULL_COMPETITION_UNIVERSE", False)
    eligible_symbols = (
        competition_eligible_symbols()
        if scan_full_competition_universe
        else _symbols_env("ELIGIBLE_SYMBOLS", DEFAULT_ELIGIBLE_SYMBOLS)
    )

    mandate = AgentMandate(
        eligible_symbols=eligible_symbols,
        stable_symbols=_symbols_env("STABLE_SYMBOLS", DEFAULT_STABLE_SYMBOLS),
        max_drawdown_pct=_float_env("MAX_DRAWDOWN_PCT", 15.0),
        daily_loss_limit_pct=_float_env("DAILY_LOSS_LIMIT_PCT", 4.0),
        max_trade_pct=_float_env("MAX_TRADE_PCT", 10.0),
        max_position_pct=_float_env("MAX_POSITION_PCT", 70.0),
        max_slippage_bps=_int_env("MAX_SLIPPAGE_BPS", 80),
        min_stable_reserve_pct=_float_env("MIN_STABLE_RESERVE_PCT", 0.0),
        min_cash_buffer_usd=_float_env("MIN_CASH_BUFFER_USD", 3.0),
        min_expected_edge_bps=_int_env("MIN_EXPECTED_EDGE_BPS", 50),
        min_signal_score=_float_env("MIN_SIGNAL_SCORE", 0.20),
        route_disabled_symbols=_symbols_env(
            "ROUTE_DISABLED_SYMBOLS",
            DEFAULT_ROUTE_DISABLED_SYMBOLS,
        ),
        max_data_age_seconds=_int_env("MAX_DATA_AGE_SECONDS", 600),
        kill_switch_path=kill_switch_path,
    )

    return AppConfig(
        data_dir=data_dir,
        audit_path=audit_path,
        live_trading_enabled=_bool_env("LIVE_TRADING_ENABLED", False),
        twak_bin=os.getenv("TWAK_BIN", "twak"),
        cmc_bin=os.getenv("CMC_BIN", "cmc"),
        cmc_api_key=os.getenv("CMC_API_KEY"),
        cmc_use_fixtures=_bool_env("CMC_USE_FIXTURES", True),
        portfolio_use_fixtures=_bool_env("PORTFOLIO_USE_FIXTURES", True),
        competition_contract=os.getenv("COMPETITION_CONTRACT", COMPETITION_CONTRACT),
        trade_source_symbol=os.getenv("TRADE_SOURCE_SYMBOL", "USDC").upper(),
        min_daily_trade_usd=_float_env("MIN_DAILY_TRADE_USD", 5.0),
        scan_full_competition_universe=scan_full_competition_universe,
        max_daily_trades=max(_int_env("MAX_DAILY_TRADES", 8), 1),
        scheduler_interval_seconds=max(_int_env("SCHEDULER_INTERVAL_SECONDS", 900), 60),
        strategy_weights=_strategy_weights_env(),
        mandate=mandate,
    )


def competition_eligible_symbols() -> set[str]:
    return set(ELIGIBLE_TOKENS)


def _strategy_weights_env() -> dict[str, float]:
    defaults = {
        "momentum": 0.25,
        "mean_reversion": 0.15,
        "liquidity": 0.15,
        "sentiment": 0.20,
        "regime": 0.10,
        "route": 0.10,
        "rebalance": 0.05,
    }
    raw = os.getenv("STRATEGY_WEIGHTS")
    if not raw:
        return defaults
    weights = dict(defaults)
    for item in raw.split(","):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip()
        if key in weights:
            weights[key] = float(value)
    return weights
