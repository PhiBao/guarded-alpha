from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any


class DecisionAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    ROTATE = "rotate"
    HOLD = "hold"


class RiskStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ExecutionMode(StrEnum):
    DRY_RUN = "dry_run"
    LIVE = "live"


class VoteDirection(StrEnum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class MarketAsset:
    symbol: str
    cmc_id: int
    chain: str
    contract_address: str | None
    price_usd: float
    change_24h_pct: float
    volume_24h_usd: float
    volatility_7d_pct: float
    sentiment_score: float
    updated_at: datetime


@dataclass(frozen=True)
class MarketSnapshot:
    source: str
    assets: list[MarketAsset]
    fear_greed: int | None
    captured_at: datetime
    trend_signals: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioState:
    total_value_usd: float
    stable_value_usd: float
    daily_pnl_pct: float
    drawdown_pct: float
    positions: dict[str, float]


@dataclass(frozen=True)
class AgentMandate:
    eligible_symbols: set[str]
    stable_symbols: set[str]
    max_drawdown_pct: float
    daily_loss_limit_pct: float
    max_trade_pct: float
    max_position_pct: float
    max_slippage_bps: int
    min_stable_reserve_pct: float
    min_cash_buffer_usd: float
    min_expected_edge_bps: int
    min_signal_score: float
    route_disabled_symbols: set[str]
    trade_each_tick: bool
    min_executable_trade_usd: float
    stable_spend_buffer_pct: float
    max_data_age_seconds: int
    kill_switch_path: str


@dataclass(frozen=True)
class StrategyVote:
    name: str
    direction: VoteDirection
    signal: float
    confidence: float
    weight: float
    reason: str


@dataclass(frozen=True)
class VibeScore:
    symbol: str | None
    score: float
    confidence: float
    long_votes: int
    short_votes: int
    neutral_votes: int
    full_consensus: bool
    votes: list[StrategyVote]
    breakdown: dict[str, float]


@dataclass(frozen=True)
class TradeDecision:
    action: DecisionAction
    symbol: str | None
    score: float
    notional_usd: float
    reason: str
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskVerdict:
    status: RiskStatus
    reasons: list[str]
    checked_at: datetime


@dataclass(frozen=True)
class ExecutionReceipt:
    mode: ExecutionMode
    submitted: bool
    tx_hash: str | None
    command: list[str]
    quote: dict[str, Any]
    message: str
    executed_at: datetime


@dataclass(frozen=True)
class RunCard:
    title: str
    summary: str
    bsc_trace_url: str | None
    proof: dict[str, Any]
    markdown: str


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    snapshot: MarketSnapshot
    portfolio: PortfolioState
    mandate: AgentMandate
    vibe_score: VibeScore
    decision: TradeDecision
    risk: RiskVerdict
    receipt: ExecutionReceipt | None
    run_card: RunCard
    created_at: datetime


@dataclass(frozen=True)
class DailyTradeStatus:
    date: date
    required: bool
    submitted: bool
    submitted_count: int
    tx_hashes: list[str]


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    return value
