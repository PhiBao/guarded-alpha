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

Each tick is one line:

```text
[guarded-alpha] HOLD XPL sc=0.3348 cf=0.6470 r=defensive n=146 | Buy signal cleared...
[guarded-alpha] ROTATE BNB->XPL $1.66 sc=0.4411 cf=0.6401 e=2011bps r=defensive n=146 | Rank decay...
[guarded-alpha] SELL ETH $5.00 -> USDC sc=0.1111 cf=1.0000 r=constructive n=50 | TP: ETH +11.1%...
[guarded-alpha] BUY ETH $198.00 sc=0.3723 cf=0.5865 r=selective n=146 | Vibe Score cleared...
[guarded-alpha] idle | max daily submitted trade cap reached
```

- `sc` = weighted alpha score, `cf` = confidence, `r` = market regime, `n` = assets scanned
- `e` = net edge bps (score edge minus estimated costs), shown on ROTATE lines
- For HOLD, the reason suffix tells what blocked the trade
- Top candidates are shown as `ETH=0.372|CAKE=0.315|LINK=0.286` on BUY lines

## PnL-Chase Tuning

When `CHASE_PNL=true` (default), the agent runs TP/SL exits and rank-decay rotation.

Tune these knobs:

| env var | default | what it does |
|---|---|---|
| `TAKE_PROFIT_PCT` | 8 | Sell when position PnL >= +8% vs cost basis |
| `STOP_LOSS_PCT` | 5 | Sell when position PnL <= -5% vs cost basis |
| `ROTATE_DECAY_BPS` | 150 | Rotate weak held into top candidate if gap > 150bps |
| `BNB_GAS_RESERVE_PCT` | 30 | Keep 30% of BNB value for gas when rotating out of BNB |
| `ROTATE_SOURCE_SYMBOLS` | ETH,BNB,XRP,... | Which held assets may be rotated |
| `MIN_TRADE_NOTIONAL_USD` | 1.0 | Floor trade size so small wallets can still trade |
| `STABLE_SPEND_BUFFER_PCT` | 1 | Buffer on stable spending to absorb slight price moves |

Cost basis is stored in `data/cost_basis.json` and updated after every submitted trade. Delete the file to reset PnL tracking. The file is safe to remove; TP/SL will be disabled until a new position is bought.

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
