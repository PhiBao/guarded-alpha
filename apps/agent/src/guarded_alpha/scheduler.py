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
    receipt = row.get("receipt") or {}
    snapshot = row.get("snapshot") or {}
    inputs = decision.get("inputs") or {}

    raw_action = str(decision.get("action") or "unknown").lower()
    action = raw_action.upper()
    symbol = decision.get("symbol") or "NONE"
    score = _fmt_float(decision.get("score"))
    confidence = _fmt_float(vibe_score.get("confidence"))
    submitted = "live" if receipt.get("submitted") else "dry"
    regime = (snapshot.get("trend_signals") or {}).get("market_regime", "?")
    scanned = len(snapshot.get("assets") or [])
    edge_bps = inputs.get("expected_edge_bps")
    net_edge_bps = inputs.get("net_edge_bps")
    from_sym = inputs.get("from_symbol", "")
    to_sym = inputs.get("to_symbol", "")
    top_opps = _fmt_top_opp(inputs.get("candidate_rankings"))
    tx_hash = receipt.get("tx_hash")
    tx = f" tx={tx_hash[:10]}" if tx_hash else ""

    if raw_action == "hold":
        reason_short = _reason_short(str(decision.get("reason", "")))
        return (
            f"[guarded-alpha] HOLD {symbol} | {action} sc={score} cf={confidence} "
            f"r={regime} n={scanned} | {reason_short} | {submitted}{tx}"
        )
    if raw_action == "rotate":
        reason_short = _reason_short(str(decision.get("reason", "")))
        edge_str = f" e={_fmt_bps(net_edge_bps or edge_bps)}" if net_edge_bps or edge_bps else ""
        return (
            f"[guarded-alpha] ROTATE {from_sym}->{to_sym or symbol} "
            f"${decision.get('notional_usd', 0):.2f} "
            f"sc={score} cf={confidence}{edge_str} "
            f"r={regime} n={scanned} | {reason_short} | {submitted}{tx}"
        )
    if raw_action == "sell":
        reason_short = _reason_short(str(decision.get("reason", "")))
        return (
            f"[guarded-alpha] SELL {symbol} ${decision.get('notional_usd', 0):.2f} "
            f"-> {to_sym or 'USDC'} sc={score} cf={confidence} "
            f"r={regime} n={scanned} | {reason_short} | {submitted}{tx}"
        )

    reason_short = _reason_short(str(decision.get("reason", "")))
    return (
        f"[guarded-alpha] {action} {symbol} ${decision.get('notional_usd', 0):.2f} "
        f"sc={score} cf={confidence} r={regime} n={scanned} "
        f"{top_opps} | {reason_short} | {submitted}{tx}"
    )


def _reason_short(reason: str) -> str:
    if not reason or len(reason) <= 40:
        return reason
    return reason[:37] + "..."


def _fmt_top_opp(value: object) -> str:
    if not isinstance(value, list) or not value:
        return ""
    items = []
    for row in value[:3]:
        if not isinstance(row, dict):
            continue
        sym = row.get("symbol", "")
        s = row.get("score")
        try:
            items.append(f"{sym}={float(s):.3f}")
        except (TypeError, ValueError):
            continue
    return "|".join(items) if items else ""


def _fmt_float(value: object) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_bps(value: object) -> str:
    try:
        return f"{int(value)}bps"
    except (TypeError, ValueError):
        return "n/a"


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
