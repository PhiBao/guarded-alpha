from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value

    aliases = {
        "TW_ACCESS_ID": "TWAK_ACCESS_ID",
        "TW_HMAC_SECRET": "TWAK_HMAC_SECRET",
    }
    for source, target in aliases.items():
        if source in os.environ and target not in os.environ:
            os.environ[target] = os.environ[source]
