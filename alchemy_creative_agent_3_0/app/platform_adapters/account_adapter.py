"""V3-owned account boundary adapter stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class V3AccountSnapshot:
    account_id: str | None
    is_authenticated: bool
    metadata: dict


class V3AccountAdapter:
    adapter_name = "v3_account_adapter"

    def current_account(self) -> V3AccountSnapshot:
        return V3AccountSnapshot(account_id=None, is_authenticated=False, metadata={"runtime_mode": "mock_boundary"})

