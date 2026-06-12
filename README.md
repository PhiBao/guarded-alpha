# Guarded Alpha Terminal

Self-custodial AI trading agent for BNB Chain.

Guarded Alpha turns market data into bounded on-chain execution. It reads CMC market data, scores a constrained token universe, passes every decision through a deterministic risk governor, and executes buy/sell swaps through Trust Wallet Agent Kit with local signing.

## What It Does

- reads market data from CoinMarketCap
- scores opportunities with the BNB Vibe Score strategy engine
- buys or sells through TWAK on BSC
- recycles held assets back into USDC when reserves get low
- blocks unsafe actions with a hard risk mandate
- records every run in an append-only proof ledger
- exposes a local React operator console for portfolio, PnL, readiness, signals, risk, and run cards
- runs an hourly scheduler with a single-instance lock

## Current Agent State

- Agent wallet: `0xBC1CB36c8FE1538E2F19de468B0c3258dF4d32a9`
- Registered wallet tx: `0xa080c1bb8bd59f5fbaf863a0b5fddbf0ed13d87f49500688be52e3b0792fa57c`
- Data mode: CMC API
- Portfolio mode: TWAK BSC wallet
- Live trading: enabled
- Source asset: USDC
- Current live universe: `ETH,TWT,USDC`

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

The agent is not a one-way buyer. If USDC reserve gets too low, or a held risk asset becomes the weakest scored position, the strategy can sell that asset back to USDC. This keeps a small wallet operational instead of exhausting source balance.

## Risk Governor

- token allowlist
- max drawdown
- daily loss cap
- max trade size
- stable reserve minimum
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

It runs preflight, starts the API, starts the hourly scheduler, and opens the local web console process.

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
- **Proof Ledger**: run card, portfolio state, quote, receipt, and transaction proof when available

## Trading Commands

Manual live cycle:

```bash
uv run guarded-alpha-run-once
```

Hourly scheduler:

```bash
uv run guarded-alpha-scheduler
```

The scheduler wakes hourly, checks whether a submitted trade already exists for the current UTC date, and runs one cycle if needed. A process lock prevents duplicate schedulers.

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
