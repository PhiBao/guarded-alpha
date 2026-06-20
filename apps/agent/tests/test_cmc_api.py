from datetime import UTC, datetime

from guarded_alpha.cmc import CMCAPIProvider, _chunks, _cmc_safe_symbols


def test_cmc_api_parser_extracts_assets() -> None:
    provider = CMCAPIProvider("test-key")
    payload = {
        "status": {"error_code": 0},
        "data": {
            "CAKE": {
                "id": 7186,
                "quote": {
                    "USD": {
                        "price": 2.9,
                        "percent_change_24h": 5.4,
                        "percent_change_7d": -7.2,
                        "volume_24h": 110000000,
                    }
                },
            }
        },
    }

    assets = provider._parse_assets(payload, datetime(2026, 6, 3, tzinfo=UTC))

    assert len(assets) == 1
    assert assets[0].symbol == "CAKE"
    assert assets[0].volatility_7d_pct == 7.2


def test_cmc_symbol_filter_skips_non_api_symbols() -> None:
    safe, skipped = _cmc_safe_symbols({"ETH", "BabyDoge", "币安人生", "lisUSD", "1INCH"})

    assert safe == ["1INCH", "BABYDOGE", "ETH", "LISUSD"]
    assert skipped == ["币安人生"]


def test_cmc_chunks_quote_symbols() -> None:
    assert _chunks(["A", "B", "C", "D", "E"], 2) == [["A", "B"], ["C", "D"], ["E"]]
