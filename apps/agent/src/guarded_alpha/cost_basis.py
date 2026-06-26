from __future__ import annotations

import json
from pathlib import Path


def load_cost_basis(path: str | Path) -> dict[str, float]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, (int, float)):
            continue
        result[key.upper()] = float(value)
    return result


def save_cost_basis(path: str | Path, basis: dict[str, float]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {k: round(v, 4) for k, v in basis.items() if v > 0}
    p.write_text(json.dumps(cleaned, indent=2, sort_keys=True), encoding="utf-8")


def update_cost_basis(
    basis: dict[str, float],
    symbol: str,
    notional_usd: float,
    action: str,
) -> dict[str, float]:
    updated = dict(basis)
    key = symbol.upper()
    if action == "buy" or action == "rotate_in":
        if key in updated:
            total_spent = updated[key] + notional_usd
            updated[key] = total_spent
        else:
            updated[key] = notional_usd
    elif action in {"sell", "rotate_out"}:
        if key in updated:
            remaining = max(updated[key] - notional_usd, 0.0)
            if remaining <= 0.01:
                updated.pop(key, None)
            else:
                updated[key] = remaining
    return updated
