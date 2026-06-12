import os


def pytest_configure() -> None:
    os.environ["LIVE_TRADING_ENABLED"] = "false"
    os.environ["CMC_USE_FIXTURES"] = "true"
    os.environ["PORTFOLIO_USE_FIXTURES"] = "true"

