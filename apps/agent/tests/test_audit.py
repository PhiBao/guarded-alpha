from dataclasses import replace

from guarded_alpha.audit import AuditLog
from guarded_alpha.config import load_config
from guarded_alpha.runner import run_once


def test_audit_reads_recent_and_skips_corrupt_lines(tmp_path) -> None:
    config_path = tmp_path / "audit.jsonl"
    config = replace(load_config(), audit_path=config_path)
    audit = AuditLog(config_path)
    run = run_once(config)

    with config_path.open("a", encoding="utf-8") as handle:
        handle.write("{not-json\n")

    rows = audit.read_recent(limit=10)

    assert len(rows) == 1
    assert rows[0]["run_id"] == run.run_id
