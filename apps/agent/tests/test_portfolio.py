from datetime import UTC, datetime

from guarded_alpha.execution import TWAKExecutionAdapter
from guarded_alpha.models import MarketAsset
from guarded_alpha.portfolio import TWAKPortfolioProvider


def test_twak_portfolio_parser_extracts_stable_value() -> None:
    provider = TWAKPortfolioProvider(
        TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5"),
        {"USDT", "USDC", "FDUSD"},
    )

    portfolio = provider._parse_portfolio(
        {"holdings": [{"symbol": "USDT", "valueUsd": 70}, {"symbol": "CAKE", "valueUsd": 30}]}
    )

    assert portfolio.total_value_usd == 100
    assert portfolio.stable_value_usd == 70
    assert portfolio.positions["CAKE"] == 30


def test_twak_portfolio_augments_missing_stable_balance(monkeypatch) -> None:
    provider = TWAKPortfolioProvider(
        TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5"),
        {"USDT", "USDC", "FDUSD"},
    )
    monkeypatch.setattr(
        TWAKPortfolioProvider,
        "_wallet_address_from_twak",
        lambda self: "0xBC1CB36c8FE1538E2F19de468B0c3258dF4d32a9",
    )
    monkeypatch.setattr(
        TWAKPortfolioProvider,
        "_direct_stable_balances",
        lambda self, wallet: {"USDC": 22.41},
    )

    rows = provider._augment_stable_rows(
        [{"chain": "bsc", "symbol": "ETH", "address": "", "usdValue": 3.07}]
    )
    portfolio = provider._parse_rows(rows)

    assert portfolio.total_value_usd == 25.48
    assert portfolio.stable_value_usd == 22.41
    assert portfolio.positions["USDC"] == 22.41


def test_twak_portfolio_augments_missing_market_asset_balance(monkeypatch) -> None:
    provider = TWAKPortfolioProvider(
        TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5"),
        {"USDT", "USDC", "USD1"},
    )
    monkeypatch.setattr(
        TWAKPortfolioProvider,
        "_wallet_address_from_twak",
        lambda self: "0xBC1CB36c8FE1538E2F19de468B0c3258dF4d32a9",
    )
    monkeypatch.setattr(
        TWAKPortfolioProvider,
        "_bep20_balance_of",
        lambda self, contract, wallet: 2 * 10**18,
    )

    rows = provider._augment_market_asset_rows(
        [{"chain": "bsc", "symbol": "USDC", "address": "", "usdValue": 6.0}],
        [
            MarketAsset(
                symbol="XRP",
                cmc_id=52,
                chain="bsc",
                contract_address="0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
                price_usd=2.5,
                change_24h_pct=1.0,
                volume_24h_usd=100_000_000,
                volatility_7d_pct=5.0,
                sentiment_score=0.0,
                updated_at=datetime(2026, 6, 22, tzinfo=UTC),
            )
        ],
    )
    portfolio = provider._parse_rows(rows)

    assert portfolio.positions["XRP"] == 5.0
    assert portfolio.total_value_usd == 11.0
