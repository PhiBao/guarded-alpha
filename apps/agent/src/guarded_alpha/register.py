from __future__ import annotations

import json

from guarded_alpha.competition import competition_state
from guarded_alpha.config import load_config
from guarded_alpha.execution import TWAKExecutionAdapter


def status_main() -> None:
    config = load_config()
    adapter = TWAKExecutionAdapter(config.twak_bin, config.competition_contract)
    try:
        twak_status = adapter.competition_status()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        json.dumps(
            {"local": competition_state().__dict__, "twak": twak_status},
            default=str,
            indent=2,
            sort_keys=True,
        )
    )


def register_main() -> None:
    state = competition_state()
    if not state.is_registration_open:
        raise SystemExit("Registration deadline has passed.")
    config = load_config()
    adapter = TWAKExecutionAdapter(config.twak_bin, config.competition_contract)
    try:
        result = adapter.register_competition()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2, sort_keys=True))
