# Guarded Alpha Agent

Security-first AI trading agent MVP for **BNB Hack: AI Trading Agent Edition**.

The product is a self-custodial BNB Chain trading agent with deterministic strategy scoring, hard risk mandates, TWAK execution adapters, CMC data adapters, and an operator console.

## What Exists

- `apps/agent`: Python backend and CLI-safe agent core.
- `apps/web`: pnpm-managed React operator console.
- `skills/guarded-alpha`: CMC Skill-style strategy spec for the same trading logic.

The default mode is dry-run with fixture data. Live trading is fail-closed until explicitly enabled through env config and TWAK credentials.

## Backend

```bash
uv sync --extra dev
uv run guarded-alpha-api
uv run guarded-alpha-run-once
uv run guarded-alpha-competition-status
uv run guarded-alpha-preflight
uv run guarded-alpha-register
uv run guarded-alpha-competition-tick
uv run pytest
uv run ruff check
```

## Frontend

```bash
pnpm install
pnpm -C apps/web dev
pnpm -C apps/web check
pnpm -C apps/web build
```

## Safety Defaults

- No private keys in this repo.
- TWAK is the only live execution adapter.
- Subprocess integrations use argument arrays and command allowlists.
- Risk gate rejects stale data, unsupported tokens, oversized trades, excessive slippage, drawdown breaches, daily loss breaches, and stable-reserve violations.
- Audit logs are append-only JSONL.

## Track 1 Operations

- Register before `2026-06-22T00:00:00Z` with `uv run guarded-alpha-register`.
- TWAK requires `TWAK_ACCESS_ID`, `TWAK_HMAC_SECRET`, and either `TWAK_WALLET_PASSWORD` or a saved TWAK keychain password.
- During the June 22-28 live window, run `uv run guarded-alpha-competition-tick` at least daily, or run `uv run guarded-alpha-competition-scheduler`.
- The competition tick refuses to trade outside the live window and skips a UTC day after a submitted trade is already logged.
