from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BNBIdentityAdapter:
    """Optional BNBAgent SDK adapter.

    The MVP keeps this lazy so ordinary dry-run development does not pull the heavier BNB SDK
    stack unless the operator opts in with `uv sync --extra bnb`.
    """

    enabled: bool
    network: str = "bsc-testnet"

    @classmethod
    def from_env(cls) -> BNBIdentityAdapter:
        enabled = os.getenv("ENABLE_BNB_IDENTITY", "false").lower() in {"1", "true", "yes", "on"}
        return cls(enabled=enabled, network=os.getenv("BNBAGENT_NETWORK", "bsc-testnet"))

    def status(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "status": "disabled",
                "role": "optional BNB Agent SDK identity proof",
            }
        try:
            import bnbagent  # type: ignore[import-not-found]
        except ImportError:
            return {
                "enabled": True,
                "status": "missing_dependency",
                "next_step": "Run `uv sync --extra bnb` and configure wallet env vars.",
                "role": "optional BNB Agent SDK identity proof",
            }
        return {
            "enabled": True,
            "status": "available",
            "network": self.network,
            "package": getattr(bnbagent, "__name__", "bnbagent"),
            "role": "optional BNB Agent SDK identity proof",
        }
