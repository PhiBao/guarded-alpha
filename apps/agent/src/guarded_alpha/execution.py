from __future__ import annotations

import json
import re
import shutil
import subprocess
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
        result = self._run_json(swap_command)
        tx_hash = _find_tx_hash(result)
        return ExecutionReceipt(
            mode=ExecutionMode.LIVE,
            submitted=True,
            tx_hash=tx_hash,
            command=[*self._base_command(), *swap_command],
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
            from_symbol = str(decision.inputs.get("from_symbol") or decision.symbol or "").upper()
            to_symbol = str(decision.inputs.get("to_symbol") or self.source_symbol).upper()
        else:
            from_symbol = str(decision.inputs.get("from_symbol") or self.source_symbol).upper()
            to_symbol = str(decision.inputs.get("to_symbol") or decision.symbol or "").upper()
        if not SAFE_SYMBOL.match(from_symbol) or not SAFE_SYMBOL.match(to_symbol):
            raise ValueError("unsafe swap route")
        if from_symbol == to_symbol:
            raise ValueError("swap route must change symbols")
        return from_symbol, to_symbol

    def wallet_status(self) -> dict[str, Any]:
        return self._run_json(["wallet", "status", "--json"])

    def wallet_addresses(self) -> dict[str, Any]:
        return self._run_json(["wallet", "addresses", "--json"])

    def wallet_portfolio(self) -> dict[str, Any]:
        return self._run_json(["wallet", "portfolio", "--chains", "bsc", "--json"])

    def quote_swap(self, amount_usd: float, from_symbol: str, to_symbol: str) -> dict[str, Any]:
        if not SAFE_SYMBOL.match(from_symbol) or not SAFE_SYMBOL.match(to_symbol):
            raise ValueError("unsafe token symbol")
        return self._run_json(
            [
                "swap",
                from_symbol,
                to_symbol,
                "--usd",
                f"{amount_usd:.2f}",
                "--quote-only",
                "--chain",
                "bsc",
                "--json",
            ]
        )

    def competition_status(self) -> dict[str, Any]:
        return self._run_json(["compete", "status", "--json"])

    def register_competition(self) -> dict[str, Any]:
        if not SAFE_ADDRESS.match(self.competition_contract):
            raise ValueError("unsafe competition contract address")
        return self._run_json(["compete", "register", "--json"])

    def _run_json(self, args: list[str]) -> dict[str, Any]:
        self._validate_args(args)
        completed = subprocess.run(
            [*self._base_command(), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
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
        match = SAFE_TX_HASH.search(value)
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
