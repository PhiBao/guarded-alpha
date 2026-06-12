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


def tick_main() -> None:
    run = run_scheduled_tick()
    if run is None:
        print(json.dumps({"ran": False, "reason": "submitted trade already exists today"}))
        return
    print(json.dumps(to_jsonable(run), indent=2, sort_keys=True))


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
            run = run_scheduled_tick(config)
            payload = run if run is not None else {
                "ran": False,
                "reason": "submitted trade already exists today",
            }
            print(json.dumps(to_jsonable(payload), sort_keys=True), flush=True)
            time.sleep(60 * 60)
