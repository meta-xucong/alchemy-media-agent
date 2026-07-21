"""Local HTTP bridge for the explicit V3 MCP materialization contract."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class MaterializedBridgeError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


class V3MaterializedMcpBridge:
    """Call only the localhost V3 handoff endpoints; never a Web Provider."""

    def __init__(self, base_url: str | None = None, *, timeout_seconds: float = 15.0) -> None:
        self.base_url = (base_url or os.getenv("ALCHEMY_V3_BASE_URL") or "http://127.0.0.1:8017").rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise MaterializedBridgeError("mcp_materialization_local_only")
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 60.0))

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
