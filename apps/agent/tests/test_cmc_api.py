from datetime import UTC, datetime

from guarded_alpha.cmc import CMCAPIProvider, _bsc_contract_address, _chunks, _cmc_safe_symbols


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


def test_cmc_bsc_contract_address_selects_bep20_address() -> None:
    contracts = [
        {
            "contract_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "platform": {"name": "Ethereum", "coin": {"symbol": "ETH"}},
        },
        {
            "contract_address": "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
            "platform": {"name": "BNB Smart Chain (BEP20)", "coin": {"symbol": "BNB"}},
        },
    ]

    assert _bsc_contract_address(contracts) == "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe"
