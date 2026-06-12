# Guarded Alpha Runbook

## Current Wallet

- BSC address: `0xBC1CB36c8FE1538E2F19de468B0c3258dF4d32a9`
- Registration tx: `0xa080c1bb8bd59f5fbaf863a0b5fddbf0ed13d87f49500688be52e3b0792fa57c`
- Source asset: USDC
- Live universe: `ETH,TWT,USDC`

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
- submit at least one trade per UTC day
- keep the agent process local
- never expose wallet-control endpoints
