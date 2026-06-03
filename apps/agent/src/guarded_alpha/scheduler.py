from __future__ import annotations

import json
import time

from guarded_alpha.competition import competition_state
from guarded_alpha.models import to_jsonable
from guarded_alpha.runner import run_competition_tick


def tick_main() -> None:
    run = run_competition_tick()
    if run is None:
        print(json.dumps(to_jsonable(competition_state()), indent=2, sort_keys=True))
        return
    print(json.dumps(to_jsonable(run), indent=2, sort_keys=True))


def scheduler_main() -> None:
    while True:
        run = run_competition_tick()
        payload = run if run is not None else competition_state()
        print(json.dumps(to_jsonable(payload), sort_keys=True), flush=True)
        time.sleep(60 * 60)
