# Guarded Alpha Terminal

Self-custodial AI trading agent for BNB Chain.

Guarded Alpha turns market data into bounded on-chain execution. It reads CMC market data, scores a constrained token universe, passes every decision through a deterministic risk governor, and executes buy/sell swaps through Trust Wallet Agent Kit with local signing.

## What It Does

- reads market data from CoinMarketCap
- scores opportunities with the BNB Vibe Score strategy engine and an explicit Scout / Quant / Risk / Executor / Reviewer pipeline
- buys or sells through TWAK on BSC
- rotates weaker held assets directly into stronger targets when cash should be preserved
- blocks unsafe actions with a hard risk mandate
- records every run in an append-only proof ledger with market provenance, quote, receipt, risk checks, and explorer links when available
- exposes a local React operator console for portfolio, PnL, readiness, signals, risk, and run cards
- runs a scheduled scanner with a single-instance lock

## Current Agent State

- Agent wallet: `0xBC1CB36c8FE1538E2F19de468B0c3258dF4d32a9`
- Registered wallet tx: `0xa080c1bb8bd59f5fbaf863a0b5fddbf0ed13d87f49500688be52e3b0792fa57c`
- Data mode: CMC API
- Portfolio mode: TWAK BSC wallet
- Live trading: enabled
- Source asset: USDC
- Current live universe: full BNB Hack eligible token universe from CMC; current runs show `scanned=146` and `cmc_chunks=4`

## Strategy

The agent evaluates a constrained in-scope universe using seven voters:

- momentum
- mean reversion
- liquidity
- CMC sentiment/news proxy
- regime
- route/slippage risk
- portfolio rebalance

Votes are weighted, normalized, and converted into a BNB Vibe Score. A trade executes only after the risk governor approves it.

The agent is not a one-way buyer. If a stronger opportunity clears the edge gate but cash is better preserved for operations, the strategy can rotate a weaker held asset directly into the target, for example `ETH -> XRP`, without parking in USDC for a later cycle.

### How To Read The Score

`score` is a weighted alpha score, not a confidence percentage. Each voter emits a signal from `-1` to `1`, then the strategy combines those signals using weights. Because some voters intentionally offset each other, such as momentum versus mean reversion, a score around `0.25` can already be strong in current market conditions.

`confidence` is separate. It measures how decisive the underlying voter signals are. A token can have a decent score with moderate confidence, or high confidence on a risky move that still fails the score or risk gates.

The compact scheduler log prints the active gates:

```text
gates: min_score=0.20 min_edge=50bps max_trade=20% max_position=70% score=weighted_alpha_not_confidence
```

It also prints the top ranked opportunities:

```text
opportunities: XRP 0.2839/0.5075, ETH 0.2722/0.5035, USD1 0.2526/0.4229
```

Each item is `SYMBOL score/confidence`. If `candidate=XRP` appears, that means XRP was the highest-ranked asset after scanning the broader universe; it does not mean the agent only checked XRP.

When TWAK does not support a token symbol on BSC, the execution route uses the CMC BSC contract address:

```text
route: USDC(USDC) -> XRP(0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe)
```

That route line is the value TWAK receives. It prevents a CMC-ranked token such as XRP from failing because the TWAK symbol resolver does not know `XRP` on BSC.

Route support is still execution-provider dependent. XRP is executable through its CMC BSC contract route, but near-full-balance USD sizing can ask TWAK to spend slightly more token units than the wallet holds. The agent applies `STABLE_SPEND_BUFFER_PCT` when spending stable balances and uses buffered sizing for recycle trades, so XRP should stay enabled unless a route repeatedly fails after contract routing and spend-buffer sizing. Use `ROUTE_DISABLED_SYMBOLS` only as an emergency blocklist.

When a buy candidate clears `MIN_SIGNAL_SCORE` and `MIN_EXPECTED_EDGE_BPS`, the agent buys from stable balance first. If stable balance is too low, it can rotate the weakest executable non-target holding directly into that qualified target. It will not sell the target asset just to buy the same asset again.

`TRADE_EACH_TICK=true` is the aggressive competition setting. In that mode the agent still scans and ranks the full market, but it treats the cash buffer as advisory and can spend executable stable balances below `MIN_DAILY_TRADE_USD` as long as they are above `MIN_EXECUTABLE_TRADE_USD`. It does not force below-threshold buys: if no candidate clears the buy gate, the action can be a standalone sell of the weakest held non-stable back to USDC. This is why a wallet with `USD1` but almost no `USDC` can still buy: USD1 is routed by its BSC contract address, not by the unsupported TWAK symbol.

Practical tuning:

- `MIN_SIGNAL_SCORE=0.20` is selective but reachable.
- `MIN_SIGNAL_SCORE=0.30` is very strict for this formula; in recent full-universe scans no token cleared it.
- `MIN_EXPECTED_EDGE_BPS=50` requires the score to clear the threshold by at least 50 bps of modeled edge.
- Use `MAX_DAILY_TRADES` as a brake, not as a target.

Each decision is also annotated by a small agent pipeline:

- **Scout** finds CMC candidates and current market regime.
- **Quant** scores momentum, mean reversion, liquidity, sentiment, regime, route risk, and reserve fit.
- **Risk** checks bankroll preservation before upside.
- **Executor** submits only TWAK swaps that passed the deterministic mandate.
- **Reviewer** writes the proof card for replay and post-trade review.

## Risk Governor

- token allowlist
- max drawdown
- daily loss cap
- max trade size
- max position concentration
- cash buffer minimum
- expected edge minimum
- stale data rejection
- slippage cap
- kill switch
- local audit ledger
- single scheduler lock

## Architecture

```text
CoinMarketCap API
       |
       v
Market Snapshot
       |
       v
BNB Vibe Score
       |
       v
Risk Governor
       |
       v
TWAK local signing -> BSC swap
       |
       v
Audit ledger + run card + operator console
```

## Repo Layout

- `apps/agent`: Python trading core, FastAPI API, CLIs, scheduler
- `apps/web`: pnpm-managed React operator console
- `skills/guarded-alpha`: strategy spec
- `ops/systemd`: optional user services for API and scheduler
- `docs/DEPLOYMENT.md`: runtime guide
- `docs/RUNBOOK.md`: operator runbook
- `docs/THREAT_MODEL.md`: security and attack surface notes
- `HACKATHON_SUBMISSION.md`: judge-facing Track 1 fit and demo path

## Setup

```bash
uv sync --extra dev
pnpm install
```

Create `.env` from `.env.example`, then set real CMC/TWAK values locally. Never commit `.env`.

Core checks:

```bash
uv run guarded-alpha-preflight
uv run guarded-alpha-status
uv run pytest
uv run ruff check
pnpm -C apps/web check
pnpm -C apps/web build
```

## Easiest Local Run

When you open the machine, run one script and leave the terminal open:

```bash
./scripts/start-local-agent.sh
```

It runs preflight, starts the API, starts the scheduled scanner, and opens the local web console process.

## Manual Local Run

Backend:

```bash
uv run guarded-alpha-api
```

Frontend:

```bash
pnpm -C apps/web dev
```

Open `http://127.0.0.1:5173`.

## Dashboard

- **Mission Control**: wallet, registration status, readiness, portfolio value, submitted trades
- **Signals**: BNB Vibe Score and strategy voters
- **Risk Governor**: active mandate and latest risk checks
- **Proof Ledger**: run card, CMC provenance, portfolio state, quote, receipt, and transaction proof when available

## Trading Commands

Manual live cycle:

```bash
uv run guarded-alpha-run-once
```

Scheduled scanner:

```bash
uv run guarded-alpha-scheduler
```

The scheduler wakes every `SCHEDULER_INTERVAL_SECONDS` and keeps scanning for approved edge. It does not stop after one UTC-day trade, but it can submit at most `MAX_DAILY_TRADES` live trades per day.

The default policy is PnL-first: `MIN_SIGNAL_SCORE=0.20`, `MIN_EXPECTED_EDGE_BPS=50`, `MAX_DAILY_TRADES=8`, and `SCHEDULER_INTERVAL_SECONDS=900`. That keeps the agent responsive without trading every weak fluctuation. A process lock prevents duplicate schedulers.

## Runtime

For TWAK local signing, keep wallet creation, password handling, and signing authority on the operator machine.

Optional user services:

```bash
./scripts/install-systemd-user.sh
loginctl enable-linger "$USER"
```

The installer renders `ops/systemd/*.service.template` with the current repo path, current `uv` path, and current `PATH`.

Verify:

```bash
systemctl --user status guarded-alpha-api.service
systemctl --user status guarded-alpha-scheduler.service
journalctl --user -u guarded-alpha-scheduler.service -n 80 --no-pager
curl http://127.0.0.1:8000/readiness
```

## Wallet Boundary

The web app does not create, import, or unlock TWAK wallets. TWAK wallet operations require a local password and must stay in the operator shell or TWAK keychain. The browser console can read status and trigger bounded local actions, but it must not receive secrets or raw signing authority.

## Emergency Halt

```bash
touch data/KILL_SWITCH
systemctl --user stop guarded-alpha-scheduler.service
```

Remove the kill switch only after reviewing wallet state, the latest run card, and scheduler logs.

For the local script runner, the scheduler lock means another process is already active:

```bash
pgrep -af guarded-alpha-scheduler
tail -n 80 data/local-agent.log
```

To intentionally replace the local scheduler and clear the emergency halt:

```bash
./scripts/start-local-agent.sh --force
```

`--force` kills existing local scheduler processes, removes `data/scheduler.lock`, and removes `data/KILL_SWITCH` before preflight.
