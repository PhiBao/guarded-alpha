from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from guarded_alpha.config import load_config
from guarded_alpha.models import to_jsonable
from guarded_alpha.runner import run_scheduled_tick


def compact_log_line(payload: object) -> str:
    row = to_jsonable(payload)
    if isinstance(row, dict) and row.get("ran") is False:
        return f"[guarded-alpha] idle | {row.get('reason', 'no scheduled run')}"
    if not isinstance(row, dict):
        return "[guarded-alpha] scheduler produced an unknown payload"

    decision = row.get("decision") or {}
    vibe_score = row.get("vibe_score") or {}
    risk = row.get("risk") or {}
    receipt = row.get("receipt") or {}
    snapshot = row.get("snapshot") or {}
    mandate = row.get("mandate") or {}
    provenance = snapshot.get("provenance") or {}
    inputs = decision.get("inputs") or {}

    raw_action = str(decision.get("action") or "unknown").lower()
    action = raw_action.upper()
    symbol = decision.get("symbol") or "NONE"
    score = _fmt_float(decision.get("score"))
    confidence = _fmt_float(vibe_score.get("confidence"))
    notional = _fmt_usd(decision.get("notional_usd"))
    risk_status = str(risk.get("status") or "unknown").upper()
    mode = str(receipt.get("mode") or "unknown")
    submitted = "submitted" if receipt.get("submitted") else "not submitted"
    market_regime = (snapshot.get("trend_signals") or {}).get("market_regime", "unknown")
    assets_scanned = len(snapshot.get("assets") or [])
    chunks = provenance.get("quote_chunks", "n/a")
    edge_bps = inputs.get("expected_edge_bps")
    cost_bps = inputs.get("estimated_cost_bps")
    opportunities = _fmt_opportunities(inputs.get("candidate_rankings"))
    gates = _fmt_gates(mandate)
    route = _fmt_route(inputs, symbol)

    target_buy = inputs.get("target_buy_symbol")
    if raw_action == "hold":
        headline = (
            f"[guarded-alpha] NO TRADE | candidate={symbol} score={score} "
            f"conf={confidence} risk={risk_status}"
        )
    elif raw_action == "rotate":
        headline = (
            f"[guarded-alpha] ROTATE {inputs.get('from_symbol', 'UNKNOWN')} -> "
            f"{inputs.get('to_symbol', symbol)} | score={score} conf={confidence} "
            f"edge={_fmt_bps(edge_bps)} cost={_fmt_bps(cost_bps)} "
            f"notional={notional} risk={risk_status}"
        )
    elif target_buy:
        headline = (
            f"[guarded-alpha] {action} {symbol} | target={target_buy} score={score} "
            f"conf={confidence} notional={notional} risk={risk_status}"
        )
    else:
        headline = (
            f"[guarded-alpha] {action} {symbol} | score={score} "
            f"conf={confidence} notional={notional} risk={risk_status}"
        )

    lines = [
        headline,
        f"  why: {decision.get('reason', 'no reason recorded')}",
        (
            f"  market: regime={market_regime} scanned={assets_scanned} "
            f"cmc_chunks={chunks}"
        ),
        f"  execution: {mode} / {submitted}",
    ]
    if opportunities:
        lines.insert(2, f"  opportunities: {opportunities}")
    if gates:
        lines.insert(2, f"  gates: {gates}")
    if route and raw_action != "hold":
        lines.insert(2, f"  route: {route}")

    if target_buy:
        lines.insert(
            2,
            f"  funding: sell {symbol} -> {inputs.get('to_symbol', 'USDC')} to fund {target_buy}",
        )
    if raw_action == "rotate":
        lines.insert(
            2,
            (
                f"  rotation: {inputs.get('from_symbol', 'UNKNOWN')} -> "
                f"{inputs.get('to_symbol', symbol)} without intermediate USDC parking"
            ),
        )

    reasons = risk.get("reasons") or []
    if reasons:
        lines.append(f"  risk: {'; '.join(str(reason) for reason in reasons)}")
    receipt_message = str(receipt.get("message") or "")
    if receipt_message and (
        "failed" in receipt_message.lower() or "error" in receipt_message.lower()
    ):
        lines.append(f"  receipt: {receipt_message}")

    tx_hash = receipt.get("tx_hash")
    if tx_hash:
        lines.append(f"  tx: {tx_hash}")

    return "\n".join(lines)


def _fmt_float(value: object) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_usd(value: object) -> str:
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _fmt_bps(value: object) -> str:
    try:
        return f"{int(value)}bps"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_opportunities(value: object) -> str:
    if not isinstance(value, list):
        return ""
    items: list[str] = []
    for row in value[:6]:
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol")
        score = row.get("score")
        confidence = row.get("confidence")
        try:
            items.append(f"{symbol} {float(score):.4f}/{float(confidence):.4f}")
        except (TypeError, ValueError):
            continue
    return ", ".join(items)


def _fmt_gates(mandate: object) -> str:
    if not isinstance(mandate, dict):
        return ""
    min_score = mandate.get("min_signal_score")
    min_edge = mandate.get("min_expected_edge_bps")
    max_trade = mandate.get("max_trade_pct")
    max_position = mandate.get("max_position_pct")
    try:
        return (
            f"min_score={float(min_score):.2f} "
            f"min_edge={int(min_edge)}bps "
            f"max_trade={float(max_trade):.0f}% "
            f"max_position={float(max_position):.0f}% "
            "score=weighted_alpha_not_confidence"
        )
    except (TypeError, ValueError):
        return ""


def _fmt_route(inputs: dict, symbol: object) -> str:
    from_symbol = inputs.get("from_symbol") or "USDC"
    to_symbol = inputs.get("to_symbol") or symbol
    from_route = inputs.get("from_route") or inputs.get("from_address") or from_symbol
    to_route = inputs.get("to_route") or inputs.get("to_address") or to_symbol
    if not from_route and not to_route:
        return ""
    return f"{from_symbol}({from_route}) -> {to_symbol}({to_route})"


def _print_payload(payload: object) -> None:
    if os.getenv("GUARDED_ALPHA_LOG_FORMAT", "").lower() == "compact":
        print(compact_log_line(payload), flush=True)
        return
    print(json.dumps(to_jsonable(payload), sort_keys=True), flush=True)


def tick_main() -> None:
    run = run_scheduled_tick()
    if run is None:
        _print_payload({"ran": False, "reason": "max daily submitted trade cap reached"})
        return
    _print_payload(run)


@contextmanager
def scheduler_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"scheduler already running: {lock_path}") from exc
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)


def scheduler_main() -> None:
    config = load_config()
    with scheduler_lock(config.data_dir / "scheduler.lock"):
        while True:
            try:
                run = run_scheduled_tick(config)
                payload = run if run is not None else {
                    "ran": False,
                    "reason": "max daily submitted trade cap reached",
                }
            except Exception as exc:
                payload = {"ran": False, "reason": f"scheduler tick failed: {exc}"}
            _print_payload(payload)
            time.sleep(config.scheduler_interval_seconds)
