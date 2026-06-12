from guarded_alpha.audit import AuditLog
from guarded_alpha.daily import daily_trade_status


def test_daily_trade_status_counts_submitted_trades(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text(
        '{"created_at":"2026-06-22T10:00:00+00:00","receipt":{"submitted":true,"tx_hash":"0xabc"}}\n',
        encoding="utf-8",
    )

    statuses = daily_trade_status(AuditLog(audit_path))

    assert len(statuses) == 7
    assert statuses[0].submitted is True
    assert statuses[0].submitted_count == 1
    assert statuses[0].tx_hashes == ["0xabc"]

