"""Periodic, read-only reachability checks for the configured primary Bridge."""
from __future__ import annotations

import asyncio
import logging

from .core import PrimarySettings
from .http import BridgeClient, BridgeError

logger = logging.getLogger(__name__)


class PrimaryHealthMonitor:
    """Probe Bridge capabilities on startup and retry at a short fixed interval."""

    def __init__(self, product: str, *, interval_seconds: float = 5.0,
                 settings_factory=PrimarySettings.from_env, client_factory=BridgeClient):
        self.product = product
        self.interval_seconds = interval_seconds
        self.settings_factory = settings_factory
        self.client_factory = client_factory
        self.connected: bool | None = None
        self.last_error_code: str | None = None

    def _record(self, connected: bool | None, error_code: str | None = None) -> None:
        previous = self.connected
        self.connected = connected
        self.last_error_code = error_code
        if connected is True and previous is not True:
            logger.info("Render Bridge is reachable for product=%s", self.product)
        elif connected is False and previous is not False:
            logger.warning("Render Bridge is unavailable for product=%s code=%s",
                           self.product, error_code or "bridge_probe_failed")

    async def probe_once(self) -> None:
        client = None
        try:
            config = self.settings_factory(product=self.product)
            if not config.enabled:
                self._record(None)
                return
            if not (config.base_url and config.workspace and config.token):
                self._record(False, "bridge_configuration_missing")
                return
            client = self.client_factory(config.base_url, config.token)
            await client.capabilities()
            self._record(True)
        except asyncio.CancelledError:
            raise
        except BridgeError as exc:
            self._record(False, exc.code)
        except Exception:
            self._record(False, "bridge_probe_failed")
        finally:
            if client is not None:
                try:
                    await client.close()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

    async def run_forever(self) -> None:
        loop = asyncio.get_running_loop()
        next_probe_at = loop.time()
        while True:
            await self.probe_once()
            next_probe_at += self.interval_seconds
            now = loop.time()
            if next_probe_at < now:
                next_probe_at = now
            await asyncio.sleep(max(0.0, next_probe_at - now))
