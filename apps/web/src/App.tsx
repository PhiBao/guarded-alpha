import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardList,
  Github,
  LineChart,
  Play,
  RefreshCcw,
  Shield,
  Target,
  Wallet
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  fetchCompetitionReadiness,
  fetchCompetitionStatus,
  fetchLedger,
  fetchStatus,
  POLL_MS,
  registerCompetition,
  runCycle
} from "./lib/api";
import type { AgentRun, AgentStatus, CompetitionReadiness, StrategyVote } from "./types";

type Tab = "mission" | "signals" | "risk" | "proof";

const IS_LANDING_ONLY = import.meta.env.VITE_LANDING_ONLY === "true";
const REPO_URL = import.meta.env.VITE_REPO_URL ?? "https://github.com/PhiBao/guarded-alpha";

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatPct(value: number): string {
  return `${value.toFixed(2)}%`;
}

function shortAddress(value?: string): string {
  if (!value) return "Not resolved";
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

function asString(value: unknown, fallback = "n/a"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function agentPipeline(run: AgentRun | null): Array<Record<string, string>> {
  const raw = run?.decision.inputs.agent_pipeline;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      agent: asString(item.agent, "Agent"),
      role: asString(item.role, "Decision role"),
      output: asString(item.output, "")
    }));
}

function StatusPill({ label, tone }: { label: string; tone: "ok" | "warn" | "danger" | "idle" }) {
  return <span className={`pill ${tone}`}>{label}</span>;
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="metric">
      {icon}
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function VoteCard({ vote }: { vote: StrategyVote }) {
  const tone = vote.direction === "long" ? "ok" : vote.direction === "short" ? "danger" : "idle";
  return (
    <article className="voteCard">
      <div className="voteTop">
        <strong>{vote.name.replace("_", " ")}</strong>
        <StatusPill label={vote.direction} tone={tone} />
      </div>
      <div className="voteStats">
        <span>Signal {vote.signal.toFixed(3)}</span>
        <span>Conf {vote.confidence.toFixed(2)}</span>
        <span>Weight {(vote.weight * 100).toFixed(0)}%</span>
      </div>
      <p>{vote.reason}</p>
    </article>
  );
}

function TradeHistory({ runs }: { runs: AgentRun[] }) {
  if (runs.length === 0) {
    return <p className="empty">No trading history yet.</p>;
  }
  return (
    <div className="historyList">
      {runs.slice(0, 8).map((run) => (
        <div className="historyRow" key={run.run_id}>
          <div>
            <strong>
              {run.decision.action.toUpperCase()} {run.decision.symbol ?? "NONE"}
            </strong>
            <span>{new Date(run.created_at).toLocaleString()}</span>
          </div>
          <div>
            <strong>{formatUsd(run.decision.notional_usd)}</strong>
            <span>{run.risk.status}</span>
          </div>
          <div>
            <strong>{formatPct(run.portfolio.daily_pnl_pct)}</strong>
            <span>daily PnL</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function LandingPage() {
  const voters = [
    "momentum",
    "mean reversion",
    "liquidity",
    "sentiment",
    "regime",
    "route risk",
    "rebalance"
  ];

  return (
    <main className="landingShell">
      <section className="landingHero">
        <div className="landingCopy">
          <p className="eyebrow">Self-Custody AI Trading Agent</p>
          <h1>Guarded Alpha Terminal</h1>
          <p>
            A local-first trading agent that turns CMC market data into bounded TWAK execution on
            BSC, with deterministic risk controls, buy/sell rebalancing, and proof logs.
          </p>
          <div className="landingActions">
            <a className="primaryButton" href={REPO_URL} target="_blank" rel="noreferrer">
              <Github size={18} />
              Build Yours
            </a>
          </div>
        </div>
        <div className="landingTerminal" aria-label="Guarded Alpha flow">
          <div>
            <span>signal</span>
            <strong>BNB Vibe Score</strong>
          </div>
          <div>
            <span>risk</span>
            <strong>Drawdown · reserve · slippage</strong>
          </div>
          <div>
            <span>execution</span>
            <strong>TWAK local signing</strong>
          </div>
        </div>
      </section>

      <section className="vibeSection">
        <div>
          <p className="eyebrow">Swarm Logic</p>
          <h2>BNB Vibe Score</h2>
          <p>
            Guarded Alpha does not let one prompt decide trades. A small swarm of deterministic
            voters scores each token from different angles, then combines the weighted votes into a
            single action signal.
          </p>
        </div>
        <div className="voterGrid">
          {voters.map((voter) => (
            <span key={voter}>{voter}</span>
          ))}
        </div>
        <div className="vibeFlow">
          <strong>market data</strong>
          <span>{"->"}</span>
          <strong>voter swarm</strong>
          <span>{"->"}</span>
          <strong>risk gate</strong>
          <span>{"->"}</span>
          <strong>TWAK swap</strong>
        </div>
      </section>

      <section className="landingGrid">
        <article>
          <Bot size={22} />
          <h2>Agentic, not black-box</h2>
          <p>Seven deterministic voters produce every trade decision before execution.</p>
        </article>
        <article>
          <Shield size={22} />
          <h2>Guarded autonomy</h2>
          <p>Risk gates reject stale data, oversized trades, low reserves, and kill-switch events.</p>
        </article>
        <article>
          <Wallet size={22} />
          <h2>Self-custody first</h2>
          <p>Wallet creation, password handling, and signing authority stay on the operator machine.</p>
        </article>
      </section>
    </main>
  );
}

function App() {
  if (IS_LANDING_ONLY) {
    return <LandingPage />;
  }

  const [tab, setTab] = useState<Tab>("mission");
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [latestRun, setLatestRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [ledger, setLedger] = useState<AgentRun[]>([]);
  const [readiness, setReadiness] = useState<CompetitionReadiness | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  async function refresh(options: { silent?: boolean } = {}) {
    if (!options.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const next = await fetchStatus();
      const recent = await fetchLedger();
      const ready = await fetchCompetitionReadiness();
      setStatus(next);
      setLatestRun(next.latest_run);
      setLedger(recent.reverse());
      setReadiness(ready);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent status.");
    } finally {
      setLoading(false);
    }
  }

  async function executeCycle() {
    setRunning(true);
    setError(null);
    try {
      const run = await runCycle();
      setLatestRun(run);
      setResult(run.run_card.markdown);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run cycle failed.");
    } finally {
      setRunning(false);
    }
  }

  async function checkCompetition() {
    setError(null);
    try {
      const next = await fetchCompetitionStatus();
      setResult(
        `Registered: ${Boolean(next.twak.registered)}\nParticipant: ${
          next.twak.participant ?? "unknown"
        }`
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration status failed.");
    }
  }

  async function register() {
    setError(null);
    try {
      const next = await registerCompetition();
      setResult(JSON.stringify(next, null, 2));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    }
  }

  useEffect(() => {
    void refresh();
    const intervalMs = Number.isFinite(POLL_MS) && POLL_MS >= 5000 ? POLL_MS : 15000;
    const interval = window.setInterval(() => {
      void refresh({ silent: true });
    }, intervalMs);
    return () => window.clearInterval(interval);
  }, []);

  const riskTone = useMemo(() => {
    if (!latestRun) return "idle";
    return latestRun.risk.status === "approved" ? "ok" : "danger";
  }, [latestRun]);

  const mode = status?.health.live_trading_enabled ? "Live" : "Dry-run";
  const dataMode = status?.health.cmc_use_fixtures ? "Fixture" : "CMC API";
  const portfolioMode = status?.health.portfolio_use_fixtures ? "Fixture" : "TWAK";
  const registered = Boolean(readiness?.registered);
  const dailyPnl = latestRun?.portfolio.daily_pnl_pct ?? 0;
  const pipeline = agentPipeline(latestRun);
  const marketRegime = asString(latestRun?.snapshot.trend_signals?.market_regime, "unknown");
  const twakDeadline = readiness?.twak_deadline
    ? new Date(readiness.twak_deadline).toLocaleString()
    : "not reported";
  const nextRequiredDay = status?.daily_status.find((day) => !day.submitted);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Self-Custody AI Trading Agent</p>
          <h1>Guarded Alpha Terminal</h1>
          <p className="subtitle">CMC market intelligence to TWAK self-custody execution on BSC.</p>
        </div>
        <div className="actions">
          <button className="iconButton" onClick={() => void refresh()} disabled={loading} title="Refresh status">
            <RefreshCcw size={18} />
            Refresh
          </button>
          <button className="primaryButton" onClick={executeCycle} disabled={running}>
            <Play size={18} />
            {running ? "Running" : mode === "Live" ? "Run Live Cycle" : "Run Dry Cycle"}
          </button>
        </div>
      </header>

      {error ? (
        <section className="notice dangerNotice">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </section>
      ) : null}

      <section className="statusGrid">
        <Metric icon={<Activity size={20} />} label="Execution" value={mode === "Live" ? "Live TWAK" : "Dry-run"} />
        <Metric icon={<Wallet size={20} />} label="Portfolio" value={formatUsd(readiness?.portfolio_value_usd ?? 0)} />
        <Metric icon={<Activity size={20} />} label="Daily PnL" value={formatPct(dailyPnl)} />
        <Metric icon={<Shield size={20} />} label="Readiness" value={readiness?.ready ? "Ready" : "Needs check"} />
        <Metric icon={<LineChart size={20} />} label="Market Regime" value={marketRegime} />
        <Metric
          icon={<CheckCircle2 size={20} />}
          label="Assets Scanned"
          value={latestRun ? String(latestRun.snapshot.assets.length) : "-"}
        />
      </section>
      <p className="syncLine">Auto-refresh {Math.max(POLL_MS, 5000) / 1000}s · last sync {lastUpdated ?? "pending"}</p>

      <nav className="tabs">
        {[
          ["mission", "Mission Control"],
          ["signals", "Signals"],
          ["risk", "Risk Governor"],
          ["proof", "Proof Ledger"]
        ].map(([key, label]) => (
          <button className={tab === key ? "active" : ""} key={key} onClick={() => setTab(key as Tab)}>
            {label}
          </button>
        ))}
      </nav>

      {tab === "mission" ? (
        <section className="panelGrid missionGrid">
          <article className="panel widePanel runtimePanel">
            <div>
              <p className="eyebrow">Track 1 Cockpit</p>
              <h2>Autonomous BSC trading desk with bounded TWAK execution</h2>
              <p className="subtitle compactSubtitle">
                The agent turns CMC market state into a thesis, checks bankroll risk, submits only
                mandate-approved swaps, and writes replayable proof for every cycle.
              </p>
            </div>
            <div className="runtimeStats">
              <div>
                <span>Agent</span>
                <strong>{shortAddress(readiness?.participant)}</strong>
              </div>
              <div>
                <span>Official Window</span>
                <strong>
                  {status
                    ? `${status.competition.trading_window_start} to ${status.competition.trading_window_end}`
                    : "Loading"}
                </strong>
              </div>
              <div>
                <span>Next Duty</span>
                <strong>{nextRequiredDay ? nextRequiredDay.date : "complete"}</strong>
              </div>
            </div>
          </article>

          <article className="panel decisionPanel thesisPanel">
            <div className="panelHeader">
              <h2>Current Thesis</h2>
              <StatusPill label={latestRun?.decision.action ?? "waiting"} tone={riskTone} />
            </div>
            {latestRun ? (
              <div className="thesisBody">
                <div className="decisionSymbol">{latestRun.decision.symbol ?? "HOLD"}</div>
                <div className="decisionStats">
                  <span>{latestRun.decision.action.toUpperCase()}</span>
                  <span>Score {latestRun.vibe_score.score.toFixed(4)}</span>
                  <span>Confidence {latestRun.vibe_score.confidence.toFixed(2)}</span>
                  <span>{formatUsd(latestRun.decision.notional_usd)}</span>
                </div>
                <p>{latestRun.decision.reason}</p>
              </div>
            ) : (
              <p className="empty">Run a cycle to generate the current trading thesis.</p>
            )}
            {result ? <pre className="resultBox">{result}</pre> : null}
          </article>

          <article className="panel">
            <div className="panelHeader">
              <h2>Sponsor Stack Fit</h2>
              <StatusPill label={readiness?.ready ? "ready" : "attention"} tone={readiness?.ready ? "ok" : "warn"} />
            </div>
            <div className="competitionActions">
              <button className="iconButton" onClick={checkCompetition}>
                <RefreshCcw size={18} />
                Check
              </button>
              <button
                className="primaryButton"
                onClick={register}
                disabled={registered || !status?.competition.is_registration_open}
              >
                <Shield size={18} />
                {registered ? "Registered" : "Register"}
              </button>
            </div>
            <div className="stackGrid">
              <div>
                <span>CMC</span>
                <strong>{dataMode}</strong>
              </div>
              <div>
                <span>TWAK</span>
                <strong>{registered ? "registered" : "open"}</strong>
              </div>
              <div>
                <span>BNB Agent SDK</span>
                <strong>{status?.bnb_identity.status ?? "disabled"}</strong>
              </div>
              <div>
                <span>TWAK Deadline</span>
                <strong>{twakDeadline}</strong>
              </div>
            </div>
            <ul className="requirementsList">
              {(readiness?.requirements ?? []).map((item) => (
                <li key={item.label}>
                  <span className={item.ok ? "checkMark okText" : "checkMark warnText"}>
                    {item.ok ? "OK" : "WAIT"}
                  </span>
                  {item.label}
                </li>
              ))}
            </ul>
            <div className="pnlGrid">
              <div>
                <span>Portfolio value</span>
                <strong>{readiness ? formatUsd(readiness.portfolio_value_usd) : "-"}</strong>
              </div>
              <div>
                <span>In-scope value</span>
                <strong>{readiness ? formatUsd(readiness.in_scope_value_usd) : "-"}</strong>
              </div>
              <div>
                <span>Submitted trades</span>
                <strong>{readiness?.submitted_trade_count ?? 0}</strong>
              </div>
              <div>
                <span>Source asset</span>
                <strong>{readiness?.source_symbol ?? "USDC"}</strong>
              </div>
            </div>
            {readiness?.portfolio_error ? <p className="warningText">{readiness.portfolio_error}</p> : null}
            {pipeline.length ? (
              <>
                <h2 className="miniHeading">Agent Pipeline</h2>
                <div className="agentPipeline">
                  {pipeline.map((step) => (
                    <div key={step.agent}>
                      <Target size={16} />
                      <strong>{step.agent}</strong>
                      <span>{step.role}</span>
                      <p>{step.output}</p>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
            <h2 className="miniHeading">Recent Runs</h2>
            <TradeHistory runs={ledger} />
          </article>
        </section>
      ) : null}

      {tab === "signals" ? (
        <section className="panelGrid">
          <article className="panel decisionPanel">
            <div className="panelHeader">
              <h2>BNB Vibe Score</h2>
              <StatusPill label={latestRun?.decision.action ?? "none"} tone={riskTone} />
            </div>
            {latestRun ? (
              <div className="decisionBody">
                <div className="decisionSymbol">{latestRun.decision.symbol ?? "HOLD"}</div>
                <div className="decisionStats">
                  <span>Score {latestRun.vibe_score.score.toFixed(4)}</span>
                  <span>Confidence {latestRun.vibe_score.confidence.toFixed(2)}</span>
                  <span>{formatUsd(latestRun.decision.notional_usd)}</span>
                </div>
                <p>{latestRun.decision.reason}</p>
              </div>
            ) : (
              <p className="empty">Run a cycle to generate a strategy card.</p>
            )}
          </article>

          <article className="panel">
            <div className="panelHeader">
              <h2>Vote Summary</h2>
              <span className="subtle">{latestRun?.snapshot.source ?? "No source"}</span>
            </div>
            {latestRun ? (
              <div className="voteSummary">
                <strong>{latestRun.vibe_score.long_votes} long</strong>
                <strong>{latestRun.vibe_score.short_votes} short</strong>
                <strong>{latestRun.vibe_score.neutral_votes} neutral</strong>
              </div>
            ) : (
              <p className="empty">No vote summary yet.</p>
            )}
          </article>

          <article className="panel widePanel">
            <div className="panelHeader">
              <h2>Strategy Votes</h2>
              <span className="subtle">{latestRun?.snapshot.captured_at ?? "No snapshot"}</span>
            </div>
            <div className="voteGrid">
              {(latestRun?.vibe_score.votes ?? []).map((vote) => (
                <VoteCard vote={vote} key={vote.name} />
              ))}
            </div>
          </article>
        </section>
      ) : null}

      {tab === "risk" ? (
        <section className="panelGrid">
          <article className="panel">
            <div className="panelHeader">
              <h2>Risk Mandate</h2>
              <StatusPill label={latestRun?.risk.status ?? "idle"} tone={riskTone} />
            </div>
            <div className="mandateGrid">
              <span>Max drawdown</span>
              <strong>{status ? formatPct(status.mandate.max_drawdown_pct) : "-"}</strong>
              <span>Daily loss cap</span>
              <strong>{status ? formatPct(status.mandate.daily_loss_limit_pct) : "-"}</strong>
              <span>Max trade</span>
              <strong>{status ? formatPct(status.mandate.max_trade_pct) : "-"}</strong>
              <span>Max position</span>
              <strong>{status ? formatPct(status.mandate.max_position_pct) : "-"}</strong>
              <span>Cash buffer</span>
              <strong>
                {status ? formatUsd(status.mandate.min_cash_buffer_usd) : "-"}
              </strong>
              <span>Min edge</span>
              <strong>{status ? `${status.mandate.min_expected_edge_bps} bps` : "-"}</strong>
              <span>Slippage cap</span>
              <strong>{status ? `${status.mandate.max_slippage_bps} bps` : "-"}</strong>
            </div>
          </article>

          <article className="panel">
            <div className="panelHeader">
              <h2>Risk Checks</h2>
              <span className="subtle">{latestRun?.risk.checked_at ?? "Not checked"}</span>
            </div>
            {latestRun ? (
              <ul className="checks">
                {latestRun.risk.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="empty">Risk checks appear after a run.</p>
            )}
          </article>
        </section>
      ) : null}

      {tab === "proof" ? (
        <section className="panelGrid">
          <article className="panel decisionPanel">
            <div className="panelHeader">
              <h2>Run Card</h2>
              <ClipboardList size={18} />
            </div>
            {latestRun ? (
              <>
                <p className="empty">{latestRun.run_card.summary}</p>
                {latestRun.run_card.bsc_trace_url ? (
                  <a className="traceLink" href={latestRun.run_card.bsc_trace_url} target="_blank" rel="noreferrer">
                    Open explorer proof
                  </a>
                ) : null}
                <pre className="resultBox">{latestRun.run_card.markdown}</pre>
              </>
            ) : (
              <p className="empty">No run card yet.</p>
            )}
          </article>

          <article className="panel">
            <div className="panelHeader">
              <h2>Portfolio And Receipt</h2>
              <span className="subtle">{latestRun?.run_id ?? "No run id"}</span>
            </div>
            {latestRun ? (
              <div className="receiptGrid compactReceipt">
                <div>
                  <span>Total value</span>
                  <strong>{formatUsd(latestRun.portfolio.total_value_usd)}</strong>
                </div>
                <div>
                  <span>Stable reserve</span>
                  <strong>{formatUsd(latestRun.portfolio.stable_value_usd)}</strong>
                </div>
                <div>
                  <span>Daily PnL</span>
                  <strong className={latestRun.portfolio.daily_pnl_pct >= 0 ? "positive" : "negative"}>
                    {formatPct(latestRun.portfolio.daily_pnl_pct)}
                  </strong>
                </div>
                <div>
                  <span>Receipt</span>
                  <strong>{latestRun.receipt?.message ?? "No receipt"}</strong>
                </div>
              </div>
            ) : (
              <p className="empty">No portfolio state yet.</p>
            )}
          </article>
        </section>
      ) : null}
    </main>
  );
}

export default App;
