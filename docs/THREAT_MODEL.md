# Guarded Alpha Threat Model

## Trust Boundaries

- CMC data is untrusted market input. It can inform signals but cannot directly trigger execution.
- LLM output is advisory only. It must never bypass deterministic strategy code or the risk gate.
- TWAK is the only live execution surface. The app must not import or store private keys.
- The frontend is an operator console. It must not receive secrets or signing authority.
- Audit logs are local evidence, not a source of trading truth; balances must be reconciled through TWAK/on-chain state.

## Highest Impact Failures

- Private key or TWAK credential leakage.
- Prompt-injected news/social input causing a trade.
- Token spoofing through ambiguous symbols or wrong BSC contracts.
- Duplicate scheduler runs creating extra trades.
- Stale CMC data, bad quote parsing, or slippage underestimation.
- x402 payment challenge abuse if paid data access is added without independent payee and budget checks.
- Drawdown accounting drift between local portfolio state and actual wallet balances.

## Mitigations In MVP

- Live mode is disabled unless `LIVE_TRADING_ENABLED=true`.
- TWAK subprocess calls use argument arrays and an allowlist.
- Risk gate rejects stale data, kill switch, drawdown breach, daily loss breach, unsupported token, excessive notional, low stable reserve, and excessive slippage.
- Strategy is deterministic; LLM explanations cannot approve trades.
- Audit writes are append-only JSONL with `fsync`.
- BNB Agent SDK integration is lazy and disabled until explicitly configured.

## Live-Mode Requirements

- Resolve every eligible symbol to a CMC ID and verified BSC contract address.
- Replace fixture portfolio with TWAK wallet balance reconciliation.
- Run quote-only TWAK swaps for the full token universe.
- Execute one tiny BSC smoke trade and verify the tx hash on BscTrace.
- Run one scheduler instance only, with a process lock and kill switch monitored.
- Provide `TWAK_WALLET_PASSWORD` through an operator secret store or TWAK keychain; do not commit it.

## Exposure

Do not expose wallet-control endpoints outside the local operator machine. The agent is designed for local TWAK signing and local audit logs.
