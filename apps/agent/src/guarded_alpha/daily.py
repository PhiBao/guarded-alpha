from __future__ import annotations

from datetime import timedelta

from guarded_alpha.audit import AuditLog
from guarded_alpha.competition import TRADING_WINDOW_END, TRADING_WINDOW_START
from guarded_alpha.models import DailyTradeStatus


def daily_trade_status(audit: AuditLog) -> list[DailyTradeStatus]:
    rows = audit.read_recent(limit=1000)
    statuses: list[DailyTradeStatus] = []
    current = TRADING_WINDOW_START
    while current <= TRADING_WINDOW_END:
        day_rows = [
            row for row in rows if str(row.get("created_at", "")).startswith(current.isoformat())
        ]
        submitted_rows = [
            row
            for row in day_rows
            if isinstance(row.get("receipt"), dict) and row["receipt"].get("submitted")
        ]
        tx_hashes = [
            str(row["receipt"]["tx_hash"])
            for row in submitted_rows
            if row.get("receipt", {}).get("tx_hash")
        ]
        statuses.append(
            DailyTradeStatus(
                date=current,
                required=True,
                submitted=bool(submitted_rows),
                submitted_count=len(submitted_rows),
                tx_hashes=tx_hashes,
            )
        )
        current = current + timedelta(days=1)
    return statuses
