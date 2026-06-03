import { Activity, AlertTriangle, CheckCircle2, Play, RefreshCcw, Shield, Wallet } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchCompetitionStatus, fetchStatus, registerCompetition, runDryRun } from "./lib/api";
import type { AgentRun, AgentStatus, MarketAsset } from "./types";

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatPct(value: number): string {
  return `${value.toFixed(2)}%`;
}

function StatusPill({ label, tone }: { label: string; tone: "ok" | "warn" | "danger" | "idle" }) {
  return <span className={`pill ${tone}`}>{label}</span>;
}

function SignalRow({ asset }: { asset: MarketAsset }) {
  return (
    <tr>
      <td>{asset.symbol}</td>
      <td>{formatUsd(asset.price_usd)}</td>
      <td className={asset.change_24h_pct >= 0 ? "positive" : "negative"}>{formatPct(asset.change_24h_pct)}</td>
      <td>{formatPct(asset.volatility_7d_pct)}</td>
      <td>{asset.sentiment_score.toFixed(2)}</td>
    </tr>
  );
}

function App() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [latestRun, setLatestRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registrationResult, setRegistrationResult] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchStatus();
      setStatus(next);
      setLatestRun(next.latest_run);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agent status.");
    } finally {
      setLoading(false);
    }
  }

  async function executeDryRun() {
    setRunning(true);
    setError(null);
    try {
      const run = await runDryRun();
      setLatestRun(run);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dry run failed.");
    } finally {
      setRunning(false);
    }
  }

  async function checkCompetition() {
    setError(null);
    try {
      const result = await fetchCompetitionStatus();
      setRegistrationResult(JSON.stringify(result.twak, null, 2));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Competition status check failed.");
    }
  }

  async function register() {
    setError(null);
    try {
      const result = await registerCompetition();
      setRegistrationResult(JSON.stringify(result, null, 2));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Competition registration failed.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const riskTone = useMemo(() => {
    if (!latestRun) return "idle";
    return latestRun.risk.status === "approved" ? "ok" : "danger";
  }, [latestRun]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">BNB Hack Track 1 Console</p>
          <h1>Guarded Alpha Agent</h1>
        </div>
        <div className="actions">
          <button className="iconButton" onClick={refresh} disabled={loading} title="Refresh status">
            <RefreshCcw size={18} />
            Refresh
          </button>
          <button className="primaryButton" onClick={executeDryRun} disabled={running}>
            <Play size={18} />
            {running ? "Running" : "Dry Run"}
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
        <div className="metric">
          <Activity size={20} />
          <div>
            <span>Mode</span>
            <strong>{status?.health.live_trading_enabled ? "Live" : "Dry-run"}</strong>
          </div>
        </div>
        <div className="metric">
          <Shield size={20} />
          <div>
            <span>Risk Gate</span>
            <strong>{latestRun ? latestRun.risk.status : "Waiting"}</strong>
          </div>
        </div>
        <div className="metric">
          <Wallet size={20} />
          <div>
            <span>BNB Identity</span>
            <strong>{status?.bnb_identity.status ?? "Unknown"}</strong>
          </div>
        </div>
        <div className="metric">
          <CheckCircle2 size={20} />
          <div>
            <span>Data Source</span>
            <strong>{latestRun?.snapshot.source ?? (status?.health.cmc_use_fixtures ? "fixture" : "cmc")}</strong>
          </div>
        </div>
      </section>

      <section className="panel competitionPanel">
        <div className="panelHeader">
          <h2>Competition Registration</h2>
          <StatusPill
            label={status?.competition.is_registration_open ? "open" : "closed"}
            tone={status?.competition.is_registration_open ? "ok" : "danger"}
          />
        </div>
        <div className="competitionActions">
          <div>
            <span className="subtle">Registration deadline</span>
            <strong>{status?.competition.registration_deadline ?? "Unknown"}</strong>
          </div>
          <div>
            <span className="subtle">Trading window</span>
            <strong>
              {status
                ? `${status.competition.trading_window_start} to ${status.competition.trading_window_end}`
                : "Unknown"}
            </strong>
          </div>
          <button className="iconButton" onClick={checkCompetition}>
            <RefreshCcw size={18} />
            Check
          </button>
          <button className="primaryButton" onClick={register} disabled={!status?.competition.is_registration_open}>
            <Wallet size={18} />
            Register
          </button>
        </div>
        {registrationResult ? <pre className="resultBox">{registrationResult}</pre> : null}
      </section>

      <section className="panelGrid">
        <article className="panel decisionPanel">
          <div className="panelHeader">
            <h2>Latest Decision</h2>
            <StatusPill label={latestRun?.decision.action ?? "none"} tone={riskTone} />
          </div>
          {latestRun ? (
            <div className="decisionBody">
              <div className="decisionSymbol">{latestRun.decision.symbol ?? "HOLD"}</div>
              <div className="decisionStats">
                <span>Score {latestRun.decision.score.toFixed(4)}</span>
                <span>{formatUsd(latestRun.decision.notional_usd)}</span>
              </div>
              <p>{latestRun.decision.reason}</p>
            </div>
          ) : (
            <p className="empty">Run a dry-run cycle to generate the first decision.</p>
          )}
        </article>

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
            <span>Slippage cap</span>
            <strong>{status ? `${status.mandate.max_slippage_bps} bps` : "-"}</strong>
          </div>
        </article>
      </section>

      <section className="panelGrid">
        <article className="panel">
          <div className="panelHeader">
            <h2>Signals</h2>
            <span className="subtle">{latestRun?.snapshot.captured_at ?? "No snapshot"}</span>
          </div>
          {latestRun ? (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Price</th>
                    <th>24h</th>
                    <th>Vol 7d</th>
                    <th>Sentiment</th>
                  </tr>
                </thead>
                <tbody>
                  {latestRun.snapshot.assets.map((asset) => (
                    <SignalRow asset={asset} key={asset.symbol} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty">No market snapshot yet.</p>
          )}
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

      <section className="panel">
        <div className="panelHeader">
          <h2>Portfolio And Receipt</h2>
          <span className="subtle">{latestRun?.run_id ?? "No run id"}</span>
        </div>
        {latestRun ? (
          <div className="receiptGrid">
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
              <span>Drawdown</span>
              <strong>{formatPct(latestRun.portfolio.drawdown_pct)}</strong>
            </div>
            <div className="wide">
              <span>Receipt</span>
              <strong>{latestRun.receipt?.message ?? "No receipt"}</strong>
            </div>
          </div>
        ) : (
          <p className="empty">No portfolio state yet.</p>
        )}
      </section>
    </main>
  );
}

export default App;
