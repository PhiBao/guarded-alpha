from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from guarded_alpha.fixtures import fixture_snapshot
from guarded_alpha.models import MarketAsset, MarketSnapshot


class MarketDataProvider(Protocol):
    def snapshot(self, symbols: set[str]) -> MarketSnapshot: ...


@dataclass(frozen=True)
class FixtureCMCProvider:
    def snapshot(self, symbols: set[str]) -> MarketSnapshot:
        snapshot = fixture_snapshot()
        filtered = [asset for asset in snapshot.assets if asset.symbol.upper() in symbols]
        return MarketSnapshot(snapshot.source, filtered, snapshot.fear_greed, snapshot.captured_at)


@dataclass(frozen=True)
class CMCCommandProvider:
    cmc_bin: str = "cmc"
    timeout_seconds: int = 20

    def snapshot(self, symbols: set[str]) -> MarketSnapshot:
        if not symbols:
            raise ValueError("symbols must not be empty")
        symbol_arg = ",".join(sorted(symbols))
        payload = self._run(["price", "--symbol", symbol_arg, "-o", "json"])
        assets = self._parse_assets(payload)
        return MarketSnapshot(
            source="cmc-cli",
            assets=assets,
            fear_greed=None,
            captured_at=datetime.now(UTC),
        )

    def _run(self, args: list[str]) -> dict:
        command = [self.cmc_bin, *args]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"cmc command failed: {completed.stderr.strip()}")
        return json.loads(completed.stdout)

    def _parse_assets(self, payload: dict) -> list[MarketAsset]:
        rows = payload.get("data")
        if isinstance(rows, dict):
            rows = rows.values()
        if not isinstance(rows, list):
            raise ValueError("unexpected CMC payload shape")

        captured_at = datetime.now(UTC)
        assets: list[MarketAsset] = []
        for row in rows:
            quote = (row.get("quote") or {}).get("USD") or {}
            assets.append(
                MarketAsset(
                    symbol=str(row["symbol"]).upper(),
                    cmc_id=int(row.get("id", 0)),
                    chain="bsc",
                    contract_address=None,
                    price_usd=float(quote.get("price", 0.0)),
                    change_24h_pct=float(quote.get("percent_change_24h", 0.0)),
                    volume_24h_usd=float(quote.get("volume_24h", 0.0)),
                    volatility_7d_pct=float(abs(quote.get("percent_change_7d", 0.0))),
                    sentiment_score=0.0,
                    updated_at=captured_at,
                )
            )
        return assets


@dataclass(frozen=True)
class CMCAPIProvider:
    api_key: str
    timeout_seconds: int = 20
    base_url: str = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

    def snapshot(self, symbols: set[str]) -> MarketSnapshot:
        if not symbols:
            raise ValueError("symbols must not be empty")
        payload = self._fetch(symbols)
        captured_at = datetime.now(UTC)
        assets = self._parse_assets(payload, captured_at)
        return MarketSnapshot(
            source="cmc-api",
            assets=assets,
            fear_greed=None,
            captured_at=captured_at,
        )

    def _fetch(self, symbols: set[str]) -> dict:
        params = urllib.parse.urlencode(
            {
                "symbol": ",".join(sorted(symbols)),
                "convert": "USD",
            }
        )
        request = urllib.request.Request(
            f"{self.base_url}?{params}",
            headers={
                "Accept": "application/json",
                "X-CMC_PRO_API_KEY": self.api_key,
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _parse_assets(self, payload: dict, captured_at: datetime) -> list[MarketAsset]:
        status = payload.get("status") or {}
        if status.get("error_code") not in (None, 0):
            raise RuntimeError(f"CMC API error: {status.get('error_message', 'unknown error')}")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("unexpected CMC API payload shape")

        assets: list[MarketAsset] = []
        for symbol, row in data.items():
            quote = (row.get("quote") or {}).get("USD") or {}
            percent_change_7d = float(quote.get("percent_change_7d") or 0.0)
            assets.append(
                MarketAsset(
                    symbol=str(symbol).upper(),
                    cmc_id=int(row.get("id", 0)),
                    chain="bsc",
                    contract_address=None,
                    price_usd=float(quote.get("price") or 0.0),
                    change_24h_pct=float(quote.get("percent_change_24h") or 0.0),
                    volume_24h_usd=float(quote.get("volume_24h") or 0.0),
                    volatility_7d_pct=abs(percent_change_7d),
                    sentiment_score=0.0,
                    updated_at=captured_at,
                )
            )
        return assets
