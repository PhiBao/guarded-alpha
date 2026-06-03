from __future__ import annotations

from guarded_alpha.models import MarketAsset, MarketSnapshot, PortfolioState, now_utc


def fixture_snapshot() -> MarketSnapshot:
    captured_at = now_utc()
    assets = [
        MarketAsset("ETH", 1027, "bsc", None, 3500.0, 2.1, 3_200_000_000, 4.8, 0.32, captured_at),
        MarketAsset("CAKE", 7186, "bsc", None, 2.9, 5.4, 110_000_000, 7.2, 0.58, captured_at),
        MarketAsset("TWT", 5964, "bsc", None, 1.2, 1.8, 42_000_000, 5.5, 0.44, captured_at),
        MarketAsset("LINK", 1975, "bsc", None, 18.5, -0.8, 840_000_000, 6.1, 0.12, captured_at),
        MarketAsset("PENDLE", 9481, "bsc", None, 4.6, 3.3, 170_000_000, 8.4, 0.51, captured_at),
        MarketAsset("USDT", 825, "bsc", None, 1.0, 0.0, 77_000_000_000, 0.1, 0.0, captured_at),
    ]
    return MarketSnapshot(source="fixture", assets=assets, fear_greed=62, captured_at=captured_at)


def fixture_portfolio() -> PortfolioState:
    return PortfolioState(
        total_value_usd=1_000.0,
        stable_value_usd=650.0,
        daily_pnl_pct=0.6,
        drawdown_pct=3.2,
        positions={"USDT": 650.0, "ETH": 180.0, "CAKE": 90.0, "TWT": 80.0},
    )

