from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from guarded_alpha.execution import TWAKExecutionAdapter
from guarded_alpha.fixtures import fixture_portfolio
from guarded_alpha.models import PortfolioState


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
        return self._parse_portfolio(payload)

    def _parse_portfolio(self, payload: dict[str, Any]) -> PortfolioState:
        rows = self._extract_holdings(payload)
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

    def _extract_holdings(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
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
