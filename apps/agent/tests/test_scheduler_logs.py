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
                    "from_route": "ETH",
                    "to_route": "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe",
                    "expected_edge_bps": 122,
                    "estimated_cost_bps": 35,
                    "candidate_rankings": [
                        {"symbol": "XRP", "score": 0.2622, "confidence": 0.4816},
                        {"symbol": "ETH", "score": 0.2511, "confidence": 0.4722},
                    ],
                },
            },
            "vibe_score": {"confidence": 0.4816},
            "risk": {"status": "approved", "reasons": ["Risk gate approved inside mandate."]},
            "receipt": {"mode": "dry_run", "submitted": False, "tx_hash": None},
            "mandate": {
                "min_signal_score": 0.2,
                "min_expected_edge_bps": 50,
                "max_trade_pct": 20,
                "max_position_pct": 70,
            },
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
    assert (
        "gates: min_score=0.20 min_edge=50bps max_trade=20% "
        "max_position=70% score=weighted_alpha_not_confidence"
    ) in line
    assert "opportunities: XRP 0.2622/0.4816, ETH 0.2511/0.4722" in line
    assert (
        "route: ETH(ETH) -> XRP(0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe)"
    ) in line
    assert "rotation: ETH -> XRP without intermediate USDC parking" in line
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
                "inputs": {
                    "candidate_rankings": [
                        {"symbol": "XRP", "score": 0.2704, "confidence": 0.4781},
                        {"symbol": "ETH", "score": 0.2601, "confidence": 0.4702},
                    ],
                },
            },
            "vibe_score": {"confidence": 0.4781},
            "risk": {"status": "rejected", "reasons": ["Risk rejected execution."]},
            "receipt": {"mode": "live", "submitted": False, "tx_hash": None},
            "mandate": {
                "min_signal_score": 0.3,
                "min_expected_edge_bps": 50,
                "max_trade_pct": 20,
                "max_position_pct": 70,
            },
            "snapshot": {
                "assets": [{"symbol": "ETH"}, {"symbol": "XRP"}],
                "trend_signals": {"market_regime": "defensive"},
                "provenance": {"quote_chunks": 4},
            },
        }
    )

    assert "NO TRADE | candidate=XRP" in line
    assert "HOLD XRP" not in line
    assert "gates: min_score=0.30 min_edge=50bps" in line
    assert "opportunities: XRP 0.2704/0.4781, ETH 0.2601/0.4702" in line
