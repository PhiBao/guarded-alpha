from guarded_alpha.execution import TWAKExecutionAdapter
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
