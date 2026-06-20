# Guarded Alpha Runbook

## Current Wallet

- BSC address: `0xBC1CB36c8FE1538E2F19de468B0c3258dF4d32a9`
- Registration tx: `0xa080c1bb8bd59f5fbaf863a0b5fddbf0ed13d87f49500688be52e3b0792fa57c`
- Source asset: USDC
- Live universe: full BNB Hack eligible token universe from CMC; recent runs show `scanned=146`

## Daily Operations

Simple mode:

```bash
./scripts/start-local-agent.sh
```

Leave that terminal open while the machine is online.

Manual checks:

```bash
uv run guarded-alpha-preflight
uv run guarded-alpha-status
```

Wallet creation/unlock is intentionally not exposed through the web app. If a new operator wallet is ever needed, run TWAK wallet commands directly in the shell with the local password, then verify with:

```bash
uv run guarded-alpha-preflight
```

Check the web dashboard after each run:

```bash
uv run guarded-alpha-api
pnpm -C apps/web dev
```

## Reading Scheduler Logs

Use this shape to understand each tick:

```text
[guarded-alpha] NO TRADE | candidate=XRP score=0.2802 conf=0.4985 risk=REJECTED
  why: BNB Vibe Score did not clear the minimum signal threshold.
  gates: min_score=0.30 min_edge=50bps max_trade=20% max_position=70% score=weighted_alpha_not_confidence
  opportunities: XRP 0.2802/0.4985, ETH 0.2701/0.4910, AVAX 0.2390/0.4880
  market: regime=selective scanned=146 cmc_chunks=4
```

- `candidate=XRP` means XRP was the top-ranked candidate, not the only scanned token.
- `opportunities` lists top-ranked tokens as `SYMBOL score/confidence`.
- `score` is a weighted alpha score. It is not a 0-100% confidence metric.
- `conf` is separate vote conviction.
- If the top score is `0.28` and `min_score=0.30`, the agent correctly does not trade.

## Emergency Halt

```bash
mkdir -p data
touch data/KILL_SWITCH
```

Remove the file only after reviewing the cause.

## Safety Checks

```bash
uv run pytest
uv run ruff check
pnpm -C apps/web check
pnpm -C apps/web build
```

## Operating Window

- keep portfolio value above $1
- hold non-zero in-scope assets at the start
- keep scheduler local and review compact logs for score, edge, and risk reasons
- keep the agent process local
- never expose wallet-control endpoints
