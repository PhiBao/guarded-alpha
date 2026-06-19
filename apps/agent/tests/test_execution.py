import pytest
from guarded_alpha.execution import TWAKExecutionAdapter, _find_tx_hash
from guarded_alpha.models import DecisionAction, TradeDecision


def test_twak_adapter_rejects_unallowlisted_command() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")

    with pytest.raises(ValueError, match="allowlisted"):
        adapter._validate_args(["danger", "do-anything"])


def test_twak_adapter_rejects_shell_metacharacters() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")

    with pytest.raises(ValueError, match="metacharacter"):
        adapter._validate_args(["swap", "1", "USDT", "ETH;rm", "--chain", "bsc"])


def test_twak_adapter_allows_competition_status_and_register() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")

    adapter._validate_args(["compete", "status", "--json"])
    adapter._validate_args(["compete", "register", "--json"])


def test_twak_adapter_allows_wallet_portfolio() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")

    adapter._validate_args(["wallet", "portfolio", "--chains", "bsc", "--json"])


def test_twak_adapter_allows_wallet_addresses() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")

    adapter._validate_args(["wallet", "addresses", "--json"])


def test_twak_adapter_routes_sell_to_source_symbol() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")
    decision = TradeDecision(
        action=DecisionAction.SELL,
        symbol="ETH",
        score=-0.2,
        notional_usd=5.0,
        reason="test",
        inputs={"from_symbol": "ETH", "to_symbol": "USDC"},
    )

    assert adapter._route(decision) == ("ETH", "USDC")


def test_twak_adapter_finds_nested_tx_hash() -> None:
    tx_hash = "0x" + "a" * 64
    payload = {"data": {"receipt": {"transactionHash": tx_hash}}}

    assert _find_tx_hash(payload) == tx_hash
