import asyncio
from types import SimpleNamespace

import anyio
import pytest

from render_bridge_primary.health import PrimaryHealthMonitor
from render_bridge_primary.http import BridgeError


class Client:
    def __init__(self, outcomes, recovered):
        self.outcomes = outcomes
        self.recovered = recovered
        self.closed = 0

    async def capabilities(self):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome == "recovered":
            self.recovered.set()
        return {"schema_version": 1}

    async def close(self):
        self.closed += 1


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_monitor_retries_after_bridge_outage_and_detects_recovery():
    recovered = asyncio.Event()
    outcomes = [BridgeError("bridge_unreachable"), "recovered"]
    clients = []

    def client_factory(_url, _token):
        client = Client(outcomes, recovered)
        clients.append(client)
        return client

    monitor = PrimaryHealthMonitor(
        "v1",
        interval_seconds=0.1,
        settings_factory=lambda **_: SimpleNamespace(
            enabled=True, base_url="http://127.0.0.1:8787", workspace="test", token="test-token"
        ),
        client_factory=client_factory,
    )
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(monitor.run_forever)
        with anyio.fail_after(2):
            await recovered.wait()
        tasks.cancel_scope.cancel()

    assert monitor.connected is True
    assert monitor.last_error_code is None
    assert len(clients) == 2
    assert all(client.closed == 1 for client in clients)


@pytest.mark.anyio
async def test_slow_probe_does_not_add_an_extra_retry_interval():
    recovered = asyncio.Event()
    starts = []
    first_finished = []
    calls = 0

    class SlowClient:
        async def capabilities(self):
            nonlocal calls
            calls += 1
            starts.append(asyncio.get_running_loop().time())
            if calls == 1:
                await asyncio.sleep(0.55)
                first_finished.append(asyncio.get_running_loop().time())
                raise BridgeError("bridge_unreachable")
            recovered.set()
            return {"schema_version": 1}

        async def close(self):
            return None

    monitor = PrimaryHealthMonitor(
        "v1",
        interval_seconds=0.5,
        settings_factory=lambda **_: SimpleNamespace(
            enabled=True, base_url="http://127.0.0.1:8787", workspace="test", token="test-token"
        ),
        client_factory=lambda *_: SlowClient(),
    )
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(monitor.run_forever)
        with anyio.fail_after(2):
            await recovered.wait()
        tasks.cancel_scope.cancel()

    assert calls == 2
    assert monitor.connected is True
    assert starts[1] - first_finished[0] < 0.3


@pytest.mark.anyio
async def test_health_monitor_does_not_probe_when_primary_is_disabled():
    def unexpected_client(*_args):
        raise AssertionError("disabled Bridge must not be probed")

    monitor = PrimaryHealthMonitor(
        "v2",
        settings_factory=lambda **_: SimpleNamespace(enabled=False),
        client_factory=unexpected_client,
    )

    await monitor.probe_once()

    assert monitor.connected is None
    assert monitor.last_error_code is None
