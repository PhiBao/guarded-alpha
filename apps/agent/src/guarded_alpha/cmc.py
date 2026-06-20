from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from guarded_alpha.fixtures import fixture_snapshot
from guarded_alpha.models import MarketAsset, MarketSnapshot

CMC_SYMBOL = re.compile(r"^[0-9A-Z$@-]{1,32}$")
DEFAULT_QUOTE_CHUNK_SIZE = 40


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
            trend_signals=_trend_from_assets(assets),
            provenance={
                "quotes": "cmc-cli price",
                "fear_greed": "unavailable",
                "trend_signals": "derived from returned quotes",
            },
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
    base_url: str = "https://pro-api.coinmarketcap.com"

    def snapshot(self, symbols: set[str]) -> MarketSnapshot:
        safe_symbols, skipped_symbols = _cmc_safe_symbols(symbols)
        if not safe_symbols:
            raise ValueError("symbols must not be empty")
        captured_at = datetime.now(UTC)
        assets: list[MarketAsset] = []
        for chunk in _chunks(safe_symbols, DEFAULT_QUOTE_CHUNK_SIZE):
            payload = self._fetch_quotes(set(chunk))
            assets.extend(self._parse_assets(payload, captured_at))
        fear_greed = self._fetch_fear_greed()
        trend_signals = self._fetch_trend_signals(set(safe_symbols), assets)
        return MarketSnapshot(
            source="cmc-api",
            assets=assets,
            fear_greed=fear_greed,
            captured_at=captured_at,
            trend_signals=trend_signals,
            provenance={
                "quotes": "/v1/cryptocurrency/quotes/latest",
                "fear_greed": (
                    "/v3/fear-and-greed/latest" if fear_greed is not None else "unavailable"
                ),
                "trend_signals": trend_signals.get("source", "derived from quotes"),
                "requested_symbols": len(symbols),
                "cmc_symbols": len(safe_symbols),
                "quote_chunks": (len(safe_symbols) + DEFAULT_QUOTE_CHUNK_SIZE - 1)
                // DEFAULT_QUOTE_CHUNK_SIZE,
                "skipped_symbols": skipped_symbols,
            },
        )

    def _fetch_quotes(self, symbols: set[str]) -> dict:
        params = urllib.parse.urlencode(
            {
                "symbol": ",".join(sorted(symbols)),
                "convert": "USD",
            }
        )
        return self._fetch_path(f"/v1/cryptocurrency/quotes/latest?{params}")

    def _fetch_path(self, path: str) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers={
                "Accept": "application/json",
                "X-CMC_PRO_API_KEY": self.api_key,
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_optional_path(self, path: str) -> dict | None:
        try:
            return self._fetch_path(path)
        except Exception:
            return None

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

    def _fetch_fear_greed(self) -> int | None:
        payload = self._fetch_optional_path("/v3/fear-and-greed/latest")
        if not payload:
            return None
        data = payload.get("data") or {}
        value = data.get("value")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _fetch_trend_signals(self, symbols: set[str], assets: list[MarketAsset]) -> dict:
        listings = self._fetch_optional_path(
            "/v1/cryptocurrency/listings/latest?limit=80&convert=USD&sort=percent_change_24h"
        )
        if listings and isinstance(listings.get("data"), list):
            rows = listings["data"]
            gainers: list[str] = []
            losers: list[str] = []
            symbol_set = {symbol.upper() for symbol in symbols}
            for row in rows:
                symbol = str(row.get("symbol") or "").upper()
                if not symbol or symbol not in symbol_set:
                    continue
                quote = (row.get("quote") or {}).get("USD") or {}
                change = float(quote.get("percent_change_24h") or 0.0)
                if change >= 0:
                    gainers.append(symbol)
                else:
                    losers.append(symbol)
            return {
                "source": "/v1/cryptocurrency/listings/latest",
                "top_gainers": gainers[:5],
                "top_losers": losers[:5],
                "market_regime": _market_regime_from_assets(assets),
                "risk_notes": _risk_notes_from_assets(assets),
            }
        return _trend_from_assets(assets)


def _market_regime_from_assets(assets: list[MarketAsset]) -> str:
    non_stables = [
        asset
        for asset in assets
        if asset.symbol.upper() not in {"USDT", "USDC", "FDUSD", "DAI", "USD1", "USDE"}
    ]
    if not non_stables:
        return "unknown"
    avg_change = sum(asset.change_24h_pct for asset in non_stables) / len(non_stables)
    avg_volatility = sum(asset.volatility_7d_pct for asset in non_stables) / len(non_stables)
    if avg_change > 2.0 and avg_volatility < 12:
        return "risk-on"
    if avg_change < -2.0 or avg_volatility > 18:
        return "defensive"
    return "selective"


def _risk_notes_from_assets(assets: list[MarketAsset]) -> list[str]:
    notes: list[str] = []
    for asset in assets:
        if asset.volatility_7d_pct > 18:
            notes.append(f"{asset.symbol} high 7d volatility")
        if asset.volume_24h_usd < 5_000_000 and asset.symbol.upper() not in {"USDT", "USDC"}:
            notes.append(f"{asset.symbol} thin 24h liquidity")
    return notes[:5]


def _trend_from_assets(assets: list[MarketAsset]) -> dict:
    ranked = sorted(assets, key=lambda asset: asset.change_24h_pct, reverse=True)
    return {
        "source": "derived from quotes",
        "top_gainers": [asset.symbol for asset in ranked[:5] if asset.change_24h_pct >= 0],
        "top_losers": [asset.symbol for asset in ranked[-5:] if asset.change_24h_pct < 0],
        "market_regime": _market_regime_from_assets(assets),
        "risk_notes": _risk_notes_from_assets(assets),
    }


def _cmc_safe_symbols(symbols: set[str]) -> tuple[list[str], list[str]]:
    safe: list[str] = []
    skipped: list[str] = []
    for symbol in sorted({item.upper() for item in symbols}):
        if CMC_SYMBOL.match(symbol):
            safe.append(symbol)
        else:
            skipped.append(symbol)
    return safe, skipped


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]
