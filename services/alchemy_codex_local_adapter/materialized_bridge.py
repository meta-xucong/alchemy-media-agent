"""Local HTTP bridge for the explicit V3 MCP materialization contract."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOCAL_RUNTIME_DESCRIPTOR_SCHEMA_VERSION = "v3_local_runtime_descriptor_v1"


class MaterializedBridgeError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


class V3MaterializedMcpBridge:
    """Call only the localhost V3 handoff endpoints; never a Web Provider."""

    def __init__(self, base_url: str | None = None, *, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 60.0))
        descriptor: dict | None = None
        configured_base_url = base_url or os.getenv("ALCHEMY_V3_BASE_URL")
        if configured_base_url:
            resolved_base_url = configured_base_url.strip()
        else:
            descriptor = self._load_runtime_descriptor()
            resolved_base_url = str(descriptor.get("base_url") or "").strip()
        if not resolved_base_url:
            raise MaterializedBridgeError(
                "mcp_materialization_v3_runtime_not_discovered",
                "Start the local V3 service so it can write its runtime descriptor, or pass v3_base_url explicitly.",
            )
        self.base_url = resolved_base_url.rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise MaterializedBridgeError("mcp_materialization_local_only")
        if descriptor is not None:
            self._verify_discovered_runtime(descriptor)

    @staticmethod
    def _repository_root() -> Path:
        configured = str(os.getenv("ALCHEMY_CODEX_LOCAL_REPO_ROOT") or "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
        return Path(__file__).resolve().parents[2]

    @classmethod
    def _runtime_descriptor_path(cls) -> Path:
        configured = str(os.getenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR") or "").strip()
        if configured:
            path = Path(os.path.expandvars(configured)).expanduser()
            return path if path.is_absolute() else cls._repository_root() / path
        return cls._repository_root() / ".media_storage" / "v3_runtime" / "local_runtime.json"

    @classmethod
    def _load_runtime_descriptor(cls) -> dict:
        descriptor_path = cls._runtime_descriptor_path()
        if not descriptor_path.is_file():
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_not_discovered")
        try:
            payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_descriptor_invalid") from exc
        if not isinstance(payload, dict):
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_descriptor_invalid")
        if payload.get("schema_version") != LOCAL_RUNTIME_DESCRIPTOR_SCHEMA_VERSION:
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_descriptor_invalid")
        base_url = str(payload.get("base_url") or "").strip()
        runtime_id = str(payload.get("runtime_id") or "").strip()
        if not base_url or not runtime_id:
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_descriptor_invalid")
        return payload

    def _verify_discovered_runtime(self, descriptor: dict) -> None:
        try:
            with urlopen(
                Request(f"{self.base_url}/api/v3/creative-agent/local-runtime", headers={"Accept": "application/json"}),
                timeout=1.0,
            ) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_unavailable", str(exc)) from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_health_invalid") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("ok") is not True
            or payload.get("schema_version") != LOCAL_RUNTIME_DESCRIPTOR_SCHEMA_VERSION
        ):
            raise MaterializedBridgeError("mcp_materialization_v3_runtime_health_invalid")
        for key in ("runtime_id", "visual_asset_catalog_root", "visual_asset_library_root"):
            expected = str(descriptor.get(key) or "").strip()
            actual = str(payload.get(key) or "").strip()
            if expected and actual != expected:
                raise MaterializedBridgeError("mcp_materialization_v3_runtime_mismatch")

    def get_handoff(self, handoff_id: str) -> dict:
        return self._request("GET", f"/api/v3/creative-agent/mcp-materializations/{handoff_id}")

    def submit(
        self,
        *,
        handoff_id: str,
        nonce: str,
        prompt_sha256: str,
        reference_asset_hashes: list[str],
        artifact_path: str | None = None,
        artifact_base64: str | None = None,
    ) -> dict:
        if bool(artifact_path) == bool(artifact_base64):
            raise MaterializedBridgeError("mcp_materialization_single_artifact_required")
        if artifact_path:
            path = Path(artifact_path)
            if not path.is_file():
                raise MaterializedBridgeError("mcp_materialization_artifact_path_unavailable")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        else:
            encoded = str(artifact_base64 or "")
        payload = {
            "nonce": nonce,
            "prompt_sha256": prompt_sha256,
            "reference_asset_hashes": list(reference_asset_hashes),
            "artifact_base64": encoded,
        }
        return self._request(
            "POST",
            f"/api/v3/creative-agent/mcp-materializations/{handoff_id}/submit",
            payload,
        )

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise MaterializedBridgeError("mcp_materialization_v3_unavailable", str(exc)) from exc
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MaterializedBridgeError("mcp_materialization_v3_response_invalid") from exc
        if not isinstance(result, dict):
            raise MaterializedBridgeError("mcp_materialization_v3_response_invalid")
        return result
