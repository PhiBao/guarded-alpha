# Guarded Alpha Skill

Use this skill to turn CMC market data into a backtestable BNB Chain spot-rotation strategy.

## Intent

Find one eligible BSC asset per evaluation cycle that has positive short-term momentum, constructive sentiment, enough liquidity, and tolerable volatility, then pass it through strict mandate checks before any execution.

## Inputs

- Eligible token universe from the BNB Hack rules.
- CMC price, 24h change, 24h volume, 7d movement or volatility proxy.
- CMC social/news/sentiment signal when available.
- Optional Fear & Greed/regime context.
- Current portfolio value, stable balance, daily PnL, and drawdown.

## Strategy

1. Resolve assets to stable CMC IDs before fetching data.
2. Exclude stablecoins from candidate buys.
3. Score each candidate:
   - 45% normalized 24h momentum.
   - 30% sentiment score.
   - 25% volatility penalty.
   - Liquidity bonus capped at high-volume assets.
   - Small regime bonus when market context is neither panic nor extreme greed.
4. Buy only if the best score clears the configured minimum.
5. Size each trade at or below the mandate max trade percentage.
6. If no signal clears the threshold, return HOLD.

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
  "action": "buy | hold",
  "symbol": "CAKE",
  "score": 0.41,
  "notional_usd": 100,
  "reason": "Best eligible asset cleared filters",
  "risk_checks": ["Risk gate approved inside mandate"]
}
```

