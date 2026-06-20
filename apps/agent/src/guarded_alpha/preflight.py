from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from guarded_alpha.cmc import CMCAPIProvider
from guarded_alpha.competition import competition_state
from guarded_alpha.config import load_config
from guarded_alpha.execution import TWAKExecutionAdapter
from guarded_alpha.models import to_jsonable


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] | None = None


def run_preflight() -> list[CheckResult]:
    config = load_config()
    checks: list[CheckResult] = []

    checks.append(
        CheckResult(
            "competition_window",
            True,
            "Registration/trading timeline loaded.",
            to_jsonable(competition_state()),
        )
    )
    checks.append(
        CheckResult(
            "live_mode",
            True,
            (
                "Live execution is enabled."
                if config.live_trading_enabled
                else "Live execution is disabled."
            ),
            {
                "live_trading_enabled": config.live_trading_enabled,
            },
        )
    )

    if config.cmc_api_key:
        try:
            snapshot = CMCAPIProvider(config.cmc_api_key).snapshot({"ETH", "CAKE", "TWT", "USDT"})
            checks.append(
                CheckResult(
                    "cmc_api",
                    True,
                    f"Fetched {len(snapshot.assets)} CMC assets.",
                    {"source": snapshot.source},
                )
            )
        except Exception as exc:
            checks.append(CheckResult("cmc_api", False, str(exc)))
    else:
        checks.append(CheckResult("cmc_api", False, "CMC_API_KEY is missing."))

    adapter = TWAKExecutionAdapter(
        config.twak_bin,
        config.competition_contract,
        source_symbol=config.trade_source_symbol,
    )
    for name, fn in [
        ("twak_wallet_status", adapter.wallet_status),
        ("competition_status", adapter.competition_status),
    ]:
        try:
            checks.append(CheckResult(name, True, "TWAK command succeeded.", fn()))
        except Exception as exc:
            checks.append(CheckResult(name, False, str(exc)))

    return checks


def main() -> None:
    print(json.dumps(to_jsonable(run_preflight()), indent=2, sort_keys=True))
