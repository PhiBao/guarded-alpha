from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from guarded_alpha.models import (
    DecisionAction,
    ExecutionMode,
    ExecutionReceipt,
    RiskStatus,
    RiskVerdict,
    TradeDecision,
    now_utc,
)

SAFE_SYMBOL = re.compile(r"^[A-Z0-9]{2,16}$")
SAFE_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
SAFE_TX_HASH = re.compile(r"^0x[a-fA-F0-9]{64}$")
TX_HASH_IN_TEXT = re.compile(r"0x[a-fA-F0-9]{64}")
BSC_RPC_URL = "https://bsc-dataseed.binance.org/"

BSC_TOKEN_ADDRESSES: dict[str, str] = {
    "AAVE": "0xfb6115445bff7b52feb98650c87f44907e58f802",
    "ADA": "0x3ee2200efb3400fabb9aacf31297cbdd1d435d47",
    "APE": "0x434b7bb1d1521aa7ed8a5f2e33d7e63b3167edb5",
    "AVAX": "0x1ce0c2827e2ef14d5c4f29a091d735a204794041",
    "BCH": "0x8ff795a6f4d97e7887c79bea79aba5cc76444adf",
    "DOT": "0x7083609fce4d1d8dc0c979aab8c869ea2c873402",
    "FET": "0x031b41e504677879370e9dbcf937283a8691fa7f",
    "FIL": "0x0d8ce2a99bb6e3b7db580ed848240e4a0f9ae153",
    "FLOKI": "0x2b3f34e9d4b127797ce6244ea3415f33f75a6926",
    "INJ": "0xa2b726b4565c963b8408e57c46c20a9050d9a5bc",
    "LINK": "0xf8a0bf9cf54bb92f17374df9eed321e7a5a9587b",
    "LTC": "0x4338665cbb7b2485a8855a139b75d5e34ab0db94",
    "PENDLE": "0xb3ed0a426253b81b0ac0be51a3b7b5b3f23bc5da",
    "SFP": "0xd41fdb03ba84762dd66a0af1a6c8540ff1ba5dfb",
    "TRX": "0xce7de646e7208a4ef112cb6ed5038fa6cc6b12e3",
    "TWT": "0x4b0f1812e5df2a09796481ff14017e6005308000",
    "UNI": "0xbf5140a22578168fd562dccf235e5d43a02ce9b1",
    "XRP": "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
    "ZRO": "0x6985884c4392d348587b19cb9eaaf157f13271cd",
}


class ExecutionAdapter(Protocol):
    def execute(self, decision: TradeDecision, risk: RiskVerdict) -> ExecutionReceipt: ...


@dataclass(frozen=True)
class DryRunExecutionAdapter:
    def execute(self, decision: TradeDecision, risk: RiskVerdict) -> ExecutionReceipt:
        return ExecutionReceipt(
            mode=ExecutionMode.DRY_RUN,
            submitted=False,
            tx_hash=None,
            command=[],
            quote={"expected_symbol": decision.symbol, "notional_usd": decision.notional_usd},
            message=f"Dry-run only. Risk status: {risk.status.value}.",
            executed_at=now_utc(),
        )


@dataclass(frozen=True)
class TWAKExecutionAdapter:
    twak_bin: str
    competition_contract: str
    source_symbol: str = "USDC"
    timeout_seconds: int = 45
    wallet_password: str | None = None

    def execute(self, decision: TradeDecision, risk: RiskVerdict) -> ExecutionReceipt:
        if risk.status != RiskStatus.APPROVED:
            return ExecutionReceipt(
                mode=ExecutionMode.LIVE,
                submitted=False,
                tx_hash=None,
                command=[],
                quote={},
                message="Risk gate rejected execution.",
                executed_at=now_utc(),
            )
        if not decision.symbol or not SAFE_SYMBOL.match(decision.symbol):
            raise ValueError("unsafe or missing token symbol")
        from_symbol, to_symbol = self._route(decision)

        quote_command = [
            "swap",
            from_symbol,
            to_symbol,
            "--usd",
            f"{decision.notional_usd:.2f}",
            "--quote-only",
            "--chain",
            "bsc",
            "--json",
        ]
        quote = self._run_json(quote_command)

        swap_command = [
            "swap",
            from_symbol,
            to_symbol,
            "--usd",
            f"{decision.notional_usd:.2f}",
            "--chain",
            "bsc",
            "--json",
        ]
        result = self._run_swap_with_approval_retry(swap_command)
        tx_hash = _find_tx_hash(result)
        return ExecutionReceipt(
            mode=ExecutionMode.LIVE,
            submitted=True,
            tx_hash=tx_hash,
            command=_redact_command([*self._base_command(), *swap_command]),
            quote=quote,
            message=(
                "Submitted through TWAK."
                if tx_hash
                else "Submitted through TWAK; tx hash was not present in CLI output."
            ),
            executed_at=now_utc(),
        )

    def _route(self, decision: TradeDecision) -> tuple[str, str]:
        if decision.action in {DecisionAction.SELL, DecisionAction.ROTATE}:
            from_symbol = _safe_route_token(
                decision.inputs.get("from_route")
                or decision.inputs.get("from_address")
                or decision.inputs.get("from_symbol")
                or decision.symbol
                or ""
            )
            to_symbol = _safe_route_token(
                decision.inputs.get("to_route")
                or decision.inputs.get("to_address")
                or decision.inputs.get("to_symbol")
                or self.source_symbol
            )
        else:
            from_symbol = _safe_route_token(
                decision.inputs.get("from_route")
                or decision.inputs.get("from_address")
                or decision.inputs.get("from_symbol")
                or self.source_symbol
            )
            to_symbol = _safe_route_token(
                decision.inputs.get("to_route")
                or decision.inputs.get("to_address")
                or decision.inputs.get("to_symbol")
                or decision.symbol
                or ""
            )
        if from_symbol == to_symbol:
            raise ValueError("swap route must change symbols")
        from_symbol = _resolve_bsc_route(from_symbol)
        to_symbol = _resolve_bsc_route(to_symbol)
        return from_symbol, to_symbol

    def wallet_status(self) -> dict[str, Any]:
        return self._run_json(["wallet", "status", "--json"])

    def wallet_addresses(self) -> dict[str, Any]:
        return self._run_json(["wallet", "addresses", "--json"])

    def wallet_portfolio(self) -> dict[str, Any]:
        return self._run_json(["wallet", "portfolio", "--chains", "bsc", "--json"])

    def quote_swap(self, amount_usd: float, from_symbol: str, to_symbol: str) -> dict[str, Any]:
        from_token = _safe_route_token(from_symbol)
        to_token = _safe_route_token(to_symbol)
        return self._run_json(
            [
                "swap",
                from_token,
                to_token,
                "--usd",
                f"{amount_usd:.2f}",
                "--quote-only",
                "--chain",
                "bsc",
                "--json",
            ]
        )

    def _run_swap_with_approval_retry(self, swap_command: list[str]) -> dict[str, Any]:
        try:
            return self._run_json(swap_command)
        except RuntimeError as exc:
            approval_tx = _approval_tx_hash(str(exc))
            if not approval_tx:
                raise
            self._wait_for_tx_receipt(approval_tx)
            try:
                return self._run_json(swap_command)
            except RuntimeError as retry_exc:
                raise RuntimeError(
                    "twak approval succeeded, but swap retry failed after approval "
                    f"{approval_tx}: {retry_exc}"
                ) from retry_exc

    def competition_status(self) -> dict[str, Any]:
        return self._run_json(["compete", "status", "--json"])

    def register_competition(self) -> dict[str, Any]:
        if not SAFE_ADDRESS.match(self.competition_contract):
            raise ValueError("unsafe competition contract address")
        return self._run_json(["compete", "register", "--json"])

    def _run_json(self, args: list[str]) -> dict[str, Any]:
        self._validate_args(args)
        command = [*self._base_command(), *args]
        env = os.environ.copy()
        if self.wallet_password:
            env["TWAK_WALLET_PASSWORD"] = self.wallet_password
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                env=env,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _decode_timeout_output(exc.stdout)
            stderr = _decode_timeout_output(exc.stderr)
            output = stderr or stdout or "no TWAK output before timeout"
            raise RuntimeError(
                f"twak command timed out after {self.timeout_seconds}s: {output}"
            ) from exc
        if completed.returncode != 0:
            error_text = (
                completed.stderr.strip() or completed.stdout.strip() or "unknown TWAK error"
            )
            raise RuntimeError(f"twak command failed: {error_text}")
        stdout = completed.stdout.strip()
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"raw": stdout}

    def _wait_for_tx_receipt(self, tx_hash: str) -> None:
        deadline = time.monotonic() + float(os.getenv("APPROVAL_WAIT_SECONDS", "45"))
        while time.monotonic() < deadline:
            receipt = self._bsc_rpc(
                "eth_getTransactionReceipt",
                [tx_hash],
                timeout=float(os.getenv("BSC_RPC_TIMEOUT_SECONDS", "4")),
            )
            if isinstance(receipt, dict):
                status = str(receipt.get("status") or "").lower()
                if status == "0x1":
                    return
                if status == "0x0":
                    raise RuntimeError(f"approval transaction failed: {tx_hash}")
            time.sleep(3)
        raise RuntimeError(f"approval transaction was not confirmed in time: {tx_hash}")

    def _bsc_rpc(self, method: str, params: list[Any], timeout: float = 4) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        request = urllib.request.Request(
            os.getenv("BSC_RPC_URL", BSC_RPC_URL),
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        return result.get("result")

    def _validate_args(self, args: list[str]) -> None:
        allowed_prefixes = {
            ("wallet", "status"),
            ("wallet", "addresses"),
            ("wallet", "portfolio"),
            ("swap",),
            ("compete", "register"),
            ("compete", "status"),
        }
        if not any(tuple(args[: len(prefix)]) == prefix for prefix in allowed_prefixes):
            raise ValueError("twak command is not allowlisted")
        for arg in args:
            if any(char in arg for char in [";", "|", "&", "`", "$", "\n", "\r"]):
                raise ValueError("unsafe shell metacharacter in argument")

    def _base_command(self) -> list[str]:
        if self.twak_bin == "twak" and shutil.which("twak") is None:
            return ["pnpm", "exec", "twak"]
        return [self.twak_bin]


def _find_tx_hash(value: Any) -> str | None:
    if isinstance(value, str):
        match = TX_HASH_IN_TEXT.search(value)
        return match.group(0) if match else None
    if isinstance(value, dict):
        for key in ["txHash", "tx_hash", "transactionHash", "transaction_hash", "hash"]:
            candidate = value.get(key)
            if isinstance(candidate, str) and SAFE_TX_HASH.match(candidate):
                return candidate
        for item in value.values():
            found = _find_tx_hash(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_tx_hash(item)
            if found:
                return found
    return None


def _approval_tx_hash(text: str) -> str | None:
    if "approval tx" not in text.lower():
        return None
    return _find_tx_hash(text)


def _safe_route_token(value: object) -> str:
    token = str(value or "").strip()
    if SAFE_ADDRESS.match(token):
        return token.lower()
    symbol = token.upper()
    if SAFE_SYMBOL.match(symbol):
        return symbol
    raise ValueError("unsafe swap route")


def _resolve_bsc_route(token: str) -> str:
    if SAFE_ADDRESS.match(token):
        return token
    upper = token.upper()
    bsc_addr = BSC_TOKEN_ADDRESSES.get(upper)
    if bsc_addr:
        return bsc_addr.lower()
    return token


def _redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    for item in command:
        if skip_next:
            redacted.append("[redacted]")
            skip_next = False
            continue
        redacted.append(item)
        if item == "--password":
            skip_next = True
    return redacted


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return value.strip()
