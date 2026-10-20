"""Version-1 HTTP only. No Bridge package, storage or executor imports."""
from __future__ import annotations

import re
from urllib.parse import quote
import httpx


class BridgeError(Exception):
    def __init__(self, code: str, *, status: int = 502, retryable: bool = True):
        super().__init__(code)
        self.code, self.status, self.retryable = code, status, retryable


class BridgeClient:
    def __init__(self, base_url: str, token: str, *, transport=None):
        self.http = httpx.AsyncClient(
            base_url=base_url + "/bridge/v1/", headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(5.0, connect=3.0, pool=1.0),
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
            follow_redirects=False, trust_env=False, transport=transport,
        )

    async def close(self):
        await self.http.aclose()

    async def _request(self, method, path, *, limit=65536, **kwargs):
        try:
            async with self.http.stream(method, path, **kwargs) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise BridgeError("bridge_response_too_large", retryable=False)
                if response.status_code >= 300:
                    code = "bridge_request_failed"
                    try:
                        import json
                        candidate = json.loads(body).get("error", {}).get("code", "")
                        if isinstance(candidate, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", candidate):
                            code = candidate
                    except (ValueError, AttributeError, TypeError):
                        pass
                    raise BridgeError(code, status=response.status_code,
                                      retryable=response.status_code in {408, 429} or response.status_code >= 500)
                return bytes(body), response.headers
        except (httpx.HTTPError, OSError):
            # Never expose credentials, upstream URLs, paths, or response bodies.
            raise BridgeError("bridge_unreachable") from None

    async def _json(self, method, path, **kwargs):
        import json
        body, _ = await self._request(method, path, **kwargs)
        try:
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except ValueError:
            raise BridgeError("invalid_bridge_response", retryable=False) from None

    @staticmethod
    def _key(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise BridgeError("invalid_bridge_identifier", retryable=False)
        return quote(value, safe="")

    async def capabilities(self):
        return await self._json("GET", "capabilities")

    async def create_input(self, payload):
        return await self._json("POST", "inputs", json=payload)

    async def upload_input(self, input_id, content, mime):
        return await self._json("PUT", f"inputs/{self._key(input_id)}/content",
                                content=content, headers={"Content-Type": mime})

    async def create_task(self, payload):
        return await self._json("POST", "tasks", json=payload)

    async def by_origin(self, origin_key):
        return await self._json("GET", f"tasks/by-origin/{self._key(origin_key)}")

    async def task(self, task_id):
        return await self._json("GET", f"tasks/{self._key(task_id)}")

    async def cancel(self, task_id):
        return await self._json("POST", f"tasks/{self._key(task_id)}/cancel")

    async def receipt(self, receipt_id):
        return await self._json("GET", f"receipts/{self._key(receipt_id)}")

    async def artifact(self, artifact_id, limit):
        return await self._request("GET", f"artifacts/{self._key(artifact_id)}/content", limit=limit)

    async def reject_receipt(self, receipt_id, *, client_receipt_id, original_hash, reason_code):
        # This preview module deliberately has NO accepted-ack operation. Add one
        # only alongside an approved, confirmed native-registration facade.
        return await self._json("POST", f"receipts/{self._key(receipt_id)}/ack", json={
            "client_receipt_id": client_receipt_id, "decision": "rejected",
            "reason_code": reason_code, "original_hash": original_hash,
        })
