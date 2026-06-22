import pytest
from guarded_alpha.execution import TWAKExecutionAdapter, _approval_tx_hash, _find_tx_hash
from guarded_alpha.models import DecisionAction, RiskStatus, RiskVerdict, TradeDecision, now_utc


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


def test_twak_adapter_routes_rotation_directly_between_assets() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")
    decision = TradeDecision(
        action=DecisionAction.ROTATE,
        symbol="XRP",
        score=0.28,
        notional_usd=10.0,
        reason="test",
        inputs={"from_symbol": "ETH", "to_symbol": "XRP"},
    )

    assert adapter._route(decision) == ("ETH", "XRP")


def test_twak_adapter_routes_buy_to_contract_address() -> None:
    adapter = TWAKExecutionAdapter("twak", "0x212c61b9b72c95d95bf29cf032f5e5635629aed5")
    xrp_bsc = "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe"
    decision = TradeDecision(
        action=DecisionAction.BUY,
        symbol="XRP",
        score=0.28,
        notional_usd=6.0,
        reason="test",
        inputs={"from_symbol": "USDC", "to_symbol": "XRP", "to_address": xrp_bsc},
    )

    assert adapter._route(decision) == ("USDC", xrp_bsc)


def test_twak_adapter_uses_password_env_without_cli_argument() -> None:
    class FakeTWAKExecutionAdapter(TWAKExecutionAdapter):
        calls = []

        def _run_json(self, args):
            self.calls.append(args)
            if "--quote-only" in args:
                return {"quote": True}
            return {"txHash": "0x" + "a" * 64}

    adapter = FakeTWAKExecutionAdapter(
        "twak",
        "0x212c61b9b72c95d95bf29cf032f5e5635629aed5",
        wallet_password="secret-password",
    )
    decision = TradeDecision(
        action=DecisionAction.BUY,
        symbol="ETH",
        score=0.3,
        notional_usd=5.0,
        reason="test",
        inputs={"from_symbol": "USDC", "to_symbol": "ETH"},
    )
    risk = RiskVerdict(RiskStatus.APPROVED, ["ok"], now_utc())

    receipt = adapter.execute(decision, risk)

    assert "--password" not in adapter.calls[-1]
    assert "secret-password" not in receipt.command


def test_twak_adapter_retries_swap_after_approval_tx() -> None:
    approval_hash = "0x" + "b" * 64
    swap_hash = "0x" + "c" * 64

    class FakeTWAKExecutionAdapter(TWAKExecutionAdapter):
        swap_attempts = 0
        waited_for = None

        def _run_json(self, args):
            if "--quote-only" in args:
                return {"quote": True}
            self.swap_attempts += 1
            if self.swap_attempts == 1:
                raise RuntimeError(f"twak command failed: Approval tx: {approval_hash}")
            return {"txHash": swap_hash}

        def _wait_for_tx_receipt(self, tx_hash):
            self.waited_for = tx_hash

    adapter = FakeTWAKExecutionAdapter(
        "twak",
        "0x212c61b9b72c95d95bf29cf032f5e5635629aed5",
        wallet_password="secret-password",
    )
    decision = TradeDecision(
        action=DecisionAction.ROTATE,
        symbol="ETH",
        score=0.3,
        notional_usd=5.0,
        reason="test",
        inputs={"from_symbol": "XRP", "to_symbol": "ETH"},
    )
    risk = RiskVerdict(RiskStatus.APPROVED, ["ok"], now_utc())

    receipt = adapter.execute(decision, risk)

    assert adapter.waited_for == approval_hash
    assert adapter.swap_attempts == 2
    assert receipt.submitted is True
    assert receipt.tx_hash == swap_hash


def test_twak_adapter_finds_nested_tx_hash() -> None:
    tx_hash = "0x" + "a" * 64
    payload = {"data": {"receipt": {"transactionHash": tx_hash}}}

    assert _find_tx_hash(payload) == tx_hash


def test_approval_tx_hash_extracts_only_approval_hash() -> None:
    tx_hash = "0x" + "d" * 64

    assert _approval_tx_hash(f"Approval tx: https://bscscan.com/tx/{tx_hash}") == tx_hash
    assert _approval_tx_hash(f"Swap tx: https://bscscan.com/tx/{tx_hash}") is None
