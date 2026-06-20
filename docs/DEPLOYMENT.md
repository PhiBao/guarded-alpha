# Runtime Guide

Guarded Alpha should run on a private machine that can keep TWAK local signing available. Wallet creation, password handling, and signing authority stay on the operator machine.

## Recommended Runtime

- Small VPS or always-on private machine
- Ubuntu with `systemd --user`
- Repo checked out anywhere on the operator machine
- `.env` present on the machine, never committed
- TWAK wallet created/unlocked locally
- CMC and TWAK credentials configured

## One-Time Setup

```bash
cd /path/to/guarded-alpha
uv sync --extra dev
pnpm install
uv run guarded-alpha-preflight
uv run guarded-alpha-status
```

## Simple Local Startup

Run this when the machine starts and leave the terminal open:

```bash
./scripts/start-local-agent.sh
```

This starts:

- FastAPI on `http://127.0.0.1:8000`
- scheduled scanner
- Vite console on `http://127.0.0.1:5173`

The scheduler has a process lock, scans every `SCHEDULER_INTERVAL_SECONDS`, and submits only when normal score, edge, and risk gates pass. `MAX_DAILY_TRADES` is a safety brake, not a target.

Expected preflight state:

- `live_mode.ok = true`
- `cmc_api.ok = true`
- `twak_wallet_status.ok = true`
- TWAK wallet status is configured
- portfolio mode is using the TWAK wallet

## Install Services

Use this only if you want the machine/VPS to keep running without an open terminal.

```bash
./scripts/install-systemd-user.sh
loginctl enable-linger "$USER"
```

The installer renders `ops/systemd/*.service.template` into `~/.config/systemd/user/` with the current repo path, current `uv` path, and current `PATH`.

The scheduler wakes every `SCHEDULER_INTERVAL_SECONDS`, scans the eligible CMC universe, and may submit multiple approved trades per day up to `MAX_DAILY_TRADES`.

## Reading Scheduler Logs

Compact scheduler logs show both the selected candidate and the broader opportunity scan:

```text
gates: min_score=0.20 min_edge=50bps max_trade=20% max_position=70% score=weighted_alpha_not_confidence
opportunities: XRP 0.2839/0.5075, ETH 0.2722/0.5035, USD1 0.2526/0.4229
market: regime=selective scanned=146 cmc_chunks=4
```

`score` is a weighted alpha score, not a confidence percentage. `conf` is separate vote conviction. `scanned=146` means the agent evaluated the broad CMC universe and selected the highest-ranked candidate.

## Verify Services

```bash
systemctl --user status guarded-alpha-api.service
systemctl --user status guarded-alpha-scheduler.service
journalctl --user -u guarded-alpha-scheduler.service -n 80 --no-pager
curl http://127.0.0.1:8000/readiness
```

## Web Console

For local operation:

```bash
pnpm -C apps/web dev
```

## Emergency Halt

```bash
touch data/KILL_SWITCH
systemctl --user stop guarded-alpha-scheduler.service
```

Remove the kill switch only after reviewing the last run card and wallet state.
