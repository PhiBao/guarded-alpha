# Guarded Alpha Skill

Use this skill to turn CMC market data into a replayable BNB Chain spot-rotation strategy.

## Intent

Find one eligible BSC asset per evaluation cycle that has positive short-term momentum, constructive sentiment, enough liquidity, and tolerable volatility, or recycle a held asset back into stable reserves when the portfolio mandate requires it. Every execution must pass strict mandate checks before TWAK submission.

## Inputs

- Configured eligible token universe.
- CMC price, 24h change, 24h volume, 7d movement or volatility proxy.
- CMC trend regime, optional fear/greed context, and source provenance when available.
- CMC social/news/sentiment signal when available.
- Optional Fear & Greed/regime context.
- Current portfolio value, stable balance, daily PnL, and drawdown.

## Strategy

1. Resolve assets to stable CMC IDs before fetching data.
2. Exclude stablecoins from candidate buys.
3. Score each candidate with BNB Vibe Score voters:
   - momentum
   - mean reversion
   - liquidity
   - CMC sentiment/news proxy
   - regime
   - route/slippage risk
   - portfolio rebalance
4. Normalize configured weights before aggregation.
5. Buy only if the best score clears the configured minimum.
6. Size each trade at or below the mandate max trade percentage.
7. If no signal clears the threshold, return HOLD unless the scheduled qualification lane is explicitly active.
8. Add a Scout / Quant / Risk / Executor / Reviewer explanation so humans can replay the decision without trusting a black box.

## Mandatory Risk Gate

Reject when any condition is true:

- Kill switch exists.
- CMC data is stale.
- Token is not in the allowlist.
- Drawdown or daily loss breaches mandate.
- Trade size exceeds cap.
- Stable reserve after trade falls below mandate.
- Slippage exceeds mandate.

## Output

Return a JSON-compatible strategy decision:

```json
{
  "action": "buy | sell | hold",
  "symbol": "CAKE",
  "score": 0.41,
  "notional_usd": 100,
  "reason": "Best eligible asset cleared filters",
  "agent_pipeline": [{"agent": "Risk", "output": "stable_reserve=62.00%; action=buy"}],
  "votes": [{"name": "momentum", "direction": "long", "signal": 0.4}],
  "risk_checks": ["Risk gate approved inside mandate"]
}
```
