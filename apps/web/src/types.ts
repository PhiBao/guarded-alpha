export type RiskStatus = "approved" | "rejected";
export type DecisionAction = "buy" | "sell" | "hold";

export interface Mandate {
  eligible_symbols: string[];
  stable_symbols: string[];
  max_drawdown_pct: number;
  daily_loss_limit_pct: number;
  max_trade_pct: number;
  max_slippage_bps: number;
  min_stable_reserve_pct: number;
  min_signal_score: number;
  max_data_age_seconds: number;
  kill_switch_path: string;
}

export interface TradeDecision {
  action: DecisionAction;
  symbol: string | null;
  score: number;
  notional_usd: number;
  reason: string;
  inputs: Record<string, unknown>;
}

export interface RiskVerdict {
  status: RiskStatus;
  reasons: string[];
  checked_at: string;
}

export interface PortfolioState {
  total_value_usd: number;
  stable_value_usd: number;
  daily_pnl_pct: number;
  drawdown_pct: number;
  positions: Record<string, number>;
}

export interface MarketAsset {
  symbol: string;
  cmc_id: number;
  chain: string;
  contract_address: string | null;
  price_usd: number;
  change_24h_pct: number;
  volume_24h_usd: number;
  volatility_7d_pct: number;
  sentiment_score: number;
  updated_at: string;
}

export interface MarketSnapshot {
  source: string;
  assets: MarketAsset[];
  fear_greed: number | null;
  captured_at: string;
}

export interface ExecutionReceipt {
  mode: "dry_run" | "live";
  submitted: boolean;
  tx_hash: string | null;
  command: string[];
  quote: Record<string, unknown>;
  message: string;
  executed_at: string;
}

export interface AgentRun {
  run_id: string;
  snapshot: MarketSnapshot;
  portfolio: PortfolioState;
  mandate: Mandate;
  decision: TradeDecision;
  risk: RiskVerdict;
  receipt: ExecutionReceipt | null;
  created_at: string;
}

export interface AgentStatus {
  health: {
    ok: boolean;
    live_trading_enabled: boolean;
    cmc_use_fixtures: boolean;
  };
  mandate: Mandate;
  latest_run: AgentRun | null;
  bnb_identity: {
    enabled: boolean;
    status: string;
    next_step?: string;
    network?: string;
  };
  competition: {
    now: string;
    registration_deadline: string;
    trading_window_start: string;
    trading_window_end: string;
    is_registration_open: boolean;
    is_trading_window: boolean;
  };
}

export interface CompetitionStatus {
  local: AgentStatus["competition"];
  twak: Record<string, unknown>;
}
