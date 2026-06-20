from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from guarded_alpha.execution import TWAKExecutionAdapter
from guarded_alpha.fixtures import fixture_portfolio
from guarded_alpha.models import PortfolioState

BSC_RPC_URL = "https://bsc-dataseed.binance.org/"
STABLE_TOKEN_CONTRACTS = {
    "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
    "USDT": "0x55d398326f99059ff775485246999027b3197955",
    "FDUSD": "0xc5f0f7b66764f6ec8c8dff7ba683102295e16409",
}
TOKEN_DECIMALS = 18


class PortfolioProvider(Protocol):
    def portfolio(self) -> PortfolioState: ...


@dataclass(frozen=True)
class FixturePortfolioProvider:
    def portfolio(self) -> PortfolioState:
        return fixture_portfolio()


@dataclass(frozen=True)
class TWAKPortfolioProvider:
    adapter: TWAKExecutionAdapter
    stable_symbols: set[str]

    def portfolio(self) -> PortfolioState:
        payload = self.adapter.wallet_portfolio()
        rows = self._extract_holdings(payload)
        rows = self._augment_stable_rows(rows)
        return self._parse_rows(rows)

    def _parse_portfolio(self, payload: dict[str, Any] | list[dict[str, Any]]) -> PortfolioState:
        rows = self._extract_holdings(payload)
        return self._parse_rows(rows)

    def _parse_rows(self, rows: list[dict[str, Any]]) -> PortfolioState:
        positions: dict[str, float] = {}
        total_value = 0.0
        stable_value = 0.0

        for row in rows:
            symbol = str(row.get("symbol") or row.get("token") or row.get("asset") or "").upper()
            if not symbol:
                continue
            usd_value = self._float_first(
                row,
                ["valueUsd", "value_usd", "usdValue", "usd_value", "value"],
            )
            positions[symbol] = positions.get(symbol, 0.0) + usd_value
            total_value += usd_value
            if symbol in self.stable_symbols:
                stable_value += usd_value

        if total_value <= 0:
            raise ValueError("TWAK portfolio returned no positive BSC holdings")

        return PortfolioState(
            total_value_usd=round(total_value, 2),
            stable_value_usd=round(stable_value, 2),
            daily_pnl_pct=0.0,
            drawdown_pct=0.0,
            positions=positions,
        )

    def _augment_stable_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        wallet_address = self._bsc_wallet_address(rows)
        if not wallet_address:
            wallet_address = self._wallet_address_from_twak()
        if not wallet_address:
            return rows

        augmented = list(rows)
        direct_balances = self._direct_stable_balances(wallet_address)
        for symbol, direct_value in direct_balances.items():
            if direct_value <= 0:
                continue
            current_value = sum(
                self._float_first(row, ["valueUsd", "value_usd", "usdValue", "usd_value", "value"])
                for row in rows
                if str(row.get("symbol") or row.get("token") or row.get("asset") or "").upper()
                == symbol
            )
            if direct_value > current_value:
                augmented.append(
                    {
                        "chain": "bsc",
                        "type": "token",
                        "symbol": symbol,
                        "address": wallet_address,
                        "usdValue": direct_value - current_value,
                        "source": "bsc_rpc_balanceOf",
                    }
                )
        return augmented

    def _bsc_wallet_address(self, rows: list[dict[str, Any]]) -> str | None:
        for row in rows:
            if str(row.get("chain") or "").lower() != "bsc":
                continue
            address = str(row.get("address") or "")
            if address.startswith("0x") and len(address) == 42:
                return address
        return None

    def _wallet_address_from_twak(self) -> str | None:
        try:
            payload = self.adapter.wallet_addresses()
        except (RuntimeError, ValueError):
            return None
        addresses = payload.get("addresses") if isinstance(payload, dict) else None
        if not isinstance(addresses, list):
            return None
        for row in addresses:
            if not isinstance(row, dict):
                continue
            if str(row.get("chainId") or "").lower() != "bsc":
                continue
            address = str(row.get("address") or "")
            if address.startswith("0x") and len(address) == 42:
                return address
        return None

    def _direct_stable_balances(self, wallet_address: str) -> dict[str, float]:
        balances: dict[str, float] = {}
        for symbol in sorted(self.stable_symbols & set(STABLE_TOKEN_CONTRACTS)):
            try:
                raw_balance = self._bep20_balance_of(STABLE_TOKEN_CONTRACTS[symbol], wallet_address)
            except (TimeoutError, URLError, ValueError, OSError, json.JSONDecodeError):
                continue
            balances[symbol] = round(raw_balance / (10**TOKEN_DECIMALS), 6)
        return balances

    def _bep20_balance_of(self, token_contract: str, wallet_address: str) -> int:
        method = "0x70a08231"
        encoded_wallet = wallet_address.removeprefix("0x").lower().rjust(64, "0")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [
                {
                    "to": token_contract,
                    "data": f"{method}{encoded_wallet}",
                },
                "latest",
            ],
        }
        request = Request(
            os.getenv("BSC_RPC_URL", BSC_RPC_URL),
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
        if "error" in result:
            raise ValueError(str(result["error"]))
        value = str(result.get("result") or "0x0")
        return int(value, 16)

    def _extract_holdings(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        data = payload.get("data")
        data_holdings = data.get("holdings") if isinstance(data, dict) else None
        data_tokens = data.get("tokens") if isinstance(data, dict) else None
        candidates = [
            payload.get("holdings"),
            payload.get("tokens"),
            payload.get("balances"),
            payload.get("portfolio"),
            data_holdings,
            data_tokens,
        ]
        for candidate in candidates:
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        raise ValueError("unexpected TWAK portfolio payload shape")

    def _float_first(self, row: dict[str, Any], keys: list[str]) -> float:
        for key in keys:
            if key not in row:
                continue
            try:
                return float(row[key] or 0.0)
            except (TypeError, ValueError):
                return 0.0
        return 0.0
