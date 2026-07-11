from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..contracts import BackendCapabilities, BackendGenerationResult, IdentityGenerationManifest


class SidecarBackendError(RuntimeError):
    retryable = False

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.detail = detail or {}


class SidecarBackendUnavailable(SidecarBackendError):
    retryable = True


class IdentityBackend(Protocol):
    async def capabilities(self) -> BackendCapabilities: ...

    async def generate(
        self,
        manifest: IdentityGenerationManifest,
        references: list[Path],
        *,
        canvas: Path | None = None,
        mask: Path | None = None,
    ) -> BackendGenerationResult: ...
