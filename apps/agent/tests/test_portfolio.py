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
