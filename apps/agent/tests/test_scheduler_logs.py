from guarded_alpha.scheduler import compact_log_line


def test_compact_log_line_rotate() -> None:
    line = compact_log_line(
        {
            "decision": {
                "action": "rotate",
                "symbol": "XRP",
                "score": 0.2622,
                "notional_usd": 5.0,
                "reason": "Rank decay: held BNB score 0.2500 trails best XPL score 0.4400",
                "inputs": {
                    "from_symbol": "BNB",
                    "to_symbol": "XPL",
                    "expected_edge_bps": 2011,
                    "candidate_rankings": [
                        {"symbol": "XPL", "score": 0.4411, "confidence": 0.6401},
                        {"symbol": "CAKE", "score": 0.3148, "confidence": 0.6306},
                    ],
                },
            },
            "vibe_score": {"confidence": 0.6401},
            "risk": {"status": "approved", "reasons": ["Risk gate approved inside mandate."]},
            "receipt": {"mode": "live", "submitted": True, "tx_hash": "0xabcdef1234"},
            "snapshot": {
                "assets": [{} for _ in range(146)],
                "trend_signals": {"market_regime": "defensive"},
            },
        }
    )

    assert "ROTATE BNB->XPL" in line
    assert "$5.00" in line
    assert "sc=0.2622" in line
    assert "r=defensive" in line
    assert "n=146" in line
    assert "live" in line
    assert "tx=0xabcdef12" in line


def test_compact_log_line_hold() -> None:
    line = compact_log_line(
        {
            "decision": {
                "action": "hold",
                "symbol": "XRP",
                "score": 0.2704,
                "notional_usd": 0.0,
                "reason": "Buy signal cleared, but cash buffer left too little USDC.",
                "inputs": {
                    "candidate_rankings": [
                        {"symbol": "XRP", "score": 0.2704, "confidence": 0.4781},
                    ],
                },
            },
            "vibe_score": {"confidence": 0.4781},
            "risk": {"status": "rejected", "reasons": ["Risk rejected execution."]},
            "receipt": {"mode": "live", "submitted": False, "tx_hash": None},
            "snapshot": {
                "assets": [{} for _ in range(146)],
                "trend_signals": {"market_regime": "defensive"},
            },
        }
    )

    assert "HOLD XRP" in line
    assert "cash buffer" in line
    assert "sc=0.2704" in line
    assert "r=defensive" in line
    assert "n=146" in line


def test_compact_log_line_sell() -> None:
    line = compact_log_line(
        {
            "decision": {
                "action": "sell",
                "symbol": "ETH",
                "score": 0.1111,
                "notional_usd": 5.00,
                "reason": "TP: ETH +11.1% exceeds +8.0% target.",
                "inputs": {
                    "from_symbol": "ETH",
                    "to_symbol": "USDC",
                },
            },
            "vibe_score": {"confidence": 1.0},
            "risk": {"status": "approved", "reasons": ["Risk gate approved"]},
            "receipt": {"mode": "live", "submitted": True, "tx_hash": "0xdeadbeef"},
            "snapshot": {
                "assets": [{} for _ in range(50)],
                "trend_signals": {"market_regime": "constructive"},
            },
        }
    )

    assert "SELL ETH" in line
    assert "$5.00" in line
    assert "USDC" in line
    assert "TP" in line
    assert "r=constructive" in line
    assert "n=50" in line
    assert "tx=0xdeadbeef" in line


def test_compact_log_line_execution_failure() -> None:
    line = compact_log_line(
        {
            "decision": {
                "action": "buy",
                "symbol": "ETH",
                "score": 0.2611,
                "notional_usd": 6.15,
                "reason": (
                    "BNB Vibe Score cleared strategy, liquidity, "
                    "regime, and portfolio filters."
                ),
                "inputs": {
                    "from_symbol": "USDC",
                    "to_symbol": "ETH",
                    "candidate_rankings": [
                        {"symbol": "ETH", "score": 0.2611, "confidence": 0.4622},
                    ],
                },
            },
            "vibe_score": {"confidence": 0.4622},
            "risk": {"status": "approved"},
            "receipt": {
                "mode": "live",
                "submitted": False,
                "tx_hash": None,
                "message": "Execution failed; scheduler will continue: approval succeeded",
            },
            "snapshot": {
                "assets": [{} for _ in range(4)],
                "trend_signals": {"market_regime": "selective"},
            },
        }
    )

    assert "BUY ETH" in line
    assert "$6.15" in line
    assert "sc=0.2611" in line
    assert "r=selective" in line
    assert "n=4" in line
    assert "dry" in line


def test_compact_log_line_idle() -> None:
    line = compact_log_line({"ran": False, "reason": "max daily submitted trade cap reached"})
    assert "idle" in line
    assert "max daily" in line
