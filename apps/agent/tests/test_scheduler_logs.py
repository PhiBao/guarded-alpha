from guarded_alpha.scheduler import compact_log_line


def test_compact_log_line_summarizes_decision() -> None:
    line = compact_log_line(
        {
            "decision": {
                "action": "rotate",
                "symbol": "XRP",
                "score": 0.2622,
                "notional_usd": 5.0,
                "reason": "XRP cleared the buy gate.",
                "inputs": {
                    "from_symbol": "ETH",
                    "to_symbol": "XRP",
                    "expected_edge_bps": 122,
                    "estimated_cost_bps": 35,
                },
            },
            "vibe_score": {"confidence": 0.4816},
            "risk": {"status": "approved", "reasons": ["Risk gate approved inside mandate."]},
            "receipt": {"mode": "dry_run", "submitted": False, "tx_hash": None},
            "snapshot": {
                "assets": [{"symbol": "ETH"}, {"symbol": "XRP"}],
                "trend_signals": {"market_regime": "selective"},
                "provenance": {"quote_chunks": 4},
            },
        }
    )

    assert "ROTATE ETH -> XRP" in line
    assert "edge=122bps cost=35bps" in line
    assert "why: XRP cleared the buy gate." in line
    assert "route: ETH -> XRP without intermediate USDC parking" in line
    assert "scanned=2" in line


def test_compact_log_line_labels_hold_as_no_trade_candidate() -> None:
    line = compact_log_line(
        {
            "decision": {
                "action": "hold",
                "symbol": "XRP",
                "score": 0.2704,
                "notional_usd": 0.0,
                "reason": "Risk rejected execution.",
                "inputs": {},
            },
            "vibe_score": {"confidence": 0.4781},
            "risk": {"status": "rejected", "reasons": ["Risk rejected execution."]},
            "receipt": {"mode": "live", "submitted": False, "tx_hash": None},
            "snapshot": {
                "assets": [{"symbol": "ETH"}, {"symbol": "XRP"}],
                "trend_signals": {"market_regime": "defensive"},
                "provenance": {"quote_chunks": 4},
            },
        }
    )

    assert "NO TRADE | candidate=XRP" in line
    assert "HOLD XRP" not in line
