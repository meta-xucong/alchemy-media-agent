"""Deterministic HTTP routing tests; no real provider, credentials or jobs."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
import json
import time

import httpx
import pytest
from pydantic import ValidationError

from app.integrations.render_bridge.client import BridgeError
from app.integrations.render_bridge.native_service import NativeTaskCreate
from app.integrations.render_bridge.routing_policy import observe_availability, routing_decision
from app.integrations.render_bridge.service import digest
from test_render_bridge_native_coordinator import NativeGatewayDouble, NativeMockBridge, make_service, request
from test_render_bridge_preview import run, due


def capabilities(now=100, revision=1, health="available", capacity="idle"):
    stamp = lambda n: datetime.fromtimestamp(n, timezone.utc).isoformat()
    return {"admission": {"accepting_new_tasks": True, "mode": "enabled"},
            "node_status": {"authorization": "active"},
            "routing_availability_v1": {"schema_version": "1", "revision": revision, "profiles": [{
                "profile_id": "fake-image", "profile_revision": "1", "health": health, "capacity": capacity,
                "reason_code": "ready" if health == "available" else "tool_missing", "evidence_kind": "local_probe",
                "observed_at": stamp(now), "valid_until": stamp(now + 90)}]}}


class RoutingBridge(NativeMockBridge):
    def __init__(self):
        super().__init__()
        self.health, self.revision, self.admission, self.authorization = "available", 1, True, "active"
        self.supported, self.proofs, self.lose_withdrawal, self.withdraw_unsafe = True, {}, False, False
        self.hide_origin = False
        self.clock = time.time
        self.auth_denied = False

    async def __call__(self, request):
        path = request.url.path.removeprefix("/bridge/v1/")
        if path == "capabilities" and self.auth_denied:
            return httpx.Response(403, json={"error": {"code": "source_denied"}})
        if "withdraw-before-start" in path:
            self.calls.append((request.method, path))
            task_id = path.split("/")[1]
            if request.method == "GET":
                proof = self.proofs.get(path.split("/")[-1])
                return httpx.Response(200, json=proof) if proof else httpx.Response(404, json={"error": {"code": "not_found"}})
            payload = json.loads(request.content)
            if self.withdraw_unsafe:
                return httpx.Response(409, json={"error": {"code": "withdrawal_not_safe"}})
            proof = {**payload, "status": "withdrawn_before_start", "task_id": task_id, "withdrawal_ref": "proof_1"}
            self.proofs[payload["withdrawal_key"]] = proof
            next(t for t in self.tasks.values() if t["remote_task_id"] == task_id)["state"] = "canceled"
            if self.lose_withdrawal:
                self.lose_withdrawal = False
                raise httpx.ReadError("response lost", request=request)
            return httpx.Response(200, json=proof)
        if path.startswith("tasks/by-origin/") and self.hide_origin:
            self.calls.append((request.method, path))
            return httpx.Response(404, json={"error": {"code": "not_found"}})
        response = await super().__call__(request)
        if path == "capabilities" and self.supported:
            value = response.json()
            extra = capabilities(self.clock(), self.revision, self.health)
            extra["admission"].update(accepting_new_tasks=self.admission, mode="enabled" if self.admission else "draining")
            extra["node_status"]["authorization"] = self.authorization
            return httpx.Response(200, json={**value, **extra})
        if path == "tasks" or path.startswith("tasks/"):
            value = response.json()
            if "request" in value:
                value["task_digest"] = digest(value["request"])
                return httpx.Response(response.status_code, json=value)
        return response


class CloudGateway(NativeGatewayDouble):
    def __init__(self):
        super().__init__()
        self.cloud_calls = 0
        self.cloud_outcome = None
        self.lose_cloud = False
        self.unknown_cloud = False
        self.admitted = True

    def cloud_admission(self, actor, target, **kwargs):
        assert kwargs["frozen_request_id"] == self.revision
        return {"status": "ready" if self.admitted else "blocked", "reason_code": "cloud_not_configured"}

    def cloud_status(self, actor, target, **kwargs):
        return self.cloud_outcome or {"status": "not_started"}

    def cloud_execute(self, actor, target, **kwargs):
        self.cloud_calls += 1
        assert kwargs["frozen_request_id"] == self.revision
        if self.unknown_cloud:
            raise RuntimeError("uncertain upstream")
        self.cloud_outcome = {"status": "registered", "native_registration_ref": "cloud_output_1",
                              "review_status": "test_review_only", "review_pending": False, "formal_delivery": False}
        if self.lose_cloud:
            self.lose_cloud = False
            raise RuntimeError("lost committed result")
        return self.cloud_outcome


def create_service(path, bridge=None, gateway=None):
    svc, gateway, bridge = make_service(path, gateway or CloudGateway(), bridge or RoutingBridge())
    svc.settings = replace(svc.settings, auto_fallback_enabled=True, queue_wait_seconds=30)
    return svc, gateway, bridge


def preferred(**kwargs):
    return request(routing_strategy="prefer_bridge", acknowledge_cloud_fallback=True, **kwargs)


def test_contract_explicit_default_off_and_consented(tmp_path):
    assert request().routing_strategy == "bridge_only"
    with pytest.raises(ValidationError):
        request(routing_strategy="prefer_bridge")
    async def case():
        svc, _, _ = make_service(tmp_path)
        try:
            with pytest.raises(BridgeError, match="auto_fallback_disabled"):
                await svc.create("101", preferred())
        finally:
            await svc.close()
    run(case())


def test_policy_revision_ttl_recovery_and_admin_authority():
    obs, supported = observe_availability({}, capabilities(100, health="unavailable"), "fake-image", 100)
    assert supported and obs["impaired"]
    obs, _ = observe_availability(obs, capabilities(110, 2), "fake-image", 110)
    assert obs["impaired"]
    again, _ = observe_availability(obs, capabilities(170, 2), "fake-image", 170)
    assert again == obs  # equal revision cannot renew receipt TTL or count
    stale, _ = observe_availability(obs, capabilities(180, 1), "fake-image", 180)
    assert stale == obs
    obs, _ = observe_availability(obs, capabilities(170, 3), "fake-image", 170)
    assert not obs["impaired"] and obs["healthy_reports"] == 2
    args = dict(observation=obs, capabilities=capabilities(170, 3), enabled=True, local_only=False,
                submitted=False, queue_elapsed=None, queue_wait_seconds=30, now=171)
    assert routing_decision(**args)[0] == "bridge"
    assert routing_decision(**{**args, "now": 261})[0] == "cloud"
    assert routing_decision(**{**args, "submitted": True, "queue_elapsed": 30})[0] == "withdraw"
    args["capabilities"]["admission"]["accepting_new_tasks"] = False
    assert routing_decision(**args)[0] == "wait"
    assert routing_decision(**{**args, "local_only": True})[0] == "bridge"


@pytest.mark.parametrize("health", ["unavailable", "unknown"])
def test_unavailable_chooses_cloud_before_bridge_post(tmp_path, health):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.health = health
        try:
            job = await svc.create("101", preferred())
            final = await due(svc, job)
            assert final["state"] == "registered", final
            assert final["selected_route"] == "cloud"
            assert gateway.cloud_calls == gateway.create_calls == 1
            assert not bridge.tasks and not bridge.acks
            assert svc.public(final)["test_fixture"] is False
            assert svc.public(final)["formal_delivery"] is False
            assert svc.public(final)["cloud_upstream_cost_possible"] is True
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize("variant", ["local_only", "old_server", "bridge_only"])
def test_legacy_and_local_only_never_fallback(tmp_path, variant):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.health = "unavailable"
        bridge.supported = variant != "old_server"
        try:
            payload = request() if variant == "bridge_only" else preferred(local_only=variant == "local_only")
            final = await due(svc, await svc.create("101", payload))
            assert final["state"] == "registered", final
            assert gateway.cloud_calls == 0 and len(bridge.tasks) == 1
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize("paused", ["admission", "authorization"])
def test_admin_pause_and_revocation_never_fallback(tmp_path, paused):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.health = "unavailable"
        if paused == "admission": bridge.admission = False
        else: bridge.authorization = "revoked"
        try:
            final = await due(svc, await svc.create("101", preferred()))
            assert final["state"] == "routing_wait"
            assert gateway.cloud_calls == gateway.create_calls == 0
            assert not bridge.tasks
        finally:
            await svc.close()
    run(case())


def test_queue_withdrawal_response_loss_reconciles_proof_once(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.ready = False
        try:
            job = await svc.create("101", preferred())
            queued = await due(svc, job)
            assert queued["state"] == "queued" and gateway.cloud_calls == 0
            await svc.local(svc.store.patch, job["id"], {"queue_elapsed": 31})
            bridge.lose_withdrawal = True
            uncertain = await due(svc, job)
            assert uncertain.get("withdrawal_request") and gateway.cloud_calls == 0
            final = await due(svc, job)
            assert final["state"] == "registered" and gateway.cloud_calls == 1, final
            assert final["withdrawal_proof"]["status"] == "withdrawn_before_start"
            assert len([c for c in bridge.calls if c[0] == "POST" and c[1].endswith("withdraw-before-start")]) == 1
        finally:
            await svc.close()
    run(case())


def test_start_wins_withdrawal_race_never_fallback(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.ready, bridge.withdraw_unsafe = False, True
        try:
            job = await svc.create("101", preferred())
            await due(svc, job)
            await svc.local(svc.store.patch, job["id"], {"queue_elapsed": 31})
            final = await due(svc, job)
            assert final["fallback_fenced"] and gateway.cloud_calls == 0
            await due(svc, job)
            assert len([c for c in bridge.calls if c[0] == "POST" and c[1].endswith("withdraw-before-start")]) == 1
        finally:
            await svc.close()
    run(case())


def test_lost_create_404_never_reposts_or_switches(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.lose_create, bridge.ready = True, False
        try:
            job = await svc.create("101", preferred())
            await due(svc, job)
            bridge.health, bridge.revision, bridge.hide_origin = "unavailable", 2, True
            final = await due(svc, job)
            assert final["state"] == "creating_unknown", final
            assert gateway.cloud_calls == 0
            assert len([c for c in bridge.calls if c == ("POST", "tasks")]) == 1
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize("committed", [True, False])
def test_cloud_response_loss_never_reexecutes_across_restart(tmp_path, committed):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.health = "unavailable"
        gateway.lose_cloud, gateway.unknown_cloud = committed, not committed
        job = await svc.create("101", preferred())
        await due(svc, job)
        await svc.close()
        svc, _, _ = create_service(tmp_path, bridge, gateway)
        svc.settings = replace(svc.settings, auto_fallback_enabled=False)
        try:
            final = await due(svc, job)
            assert final["state"] == ("registered" if committed else "cloud_unknown"), final
            assert gateway.cloud_calls == 1
            assert not bridge.tasks
        finally:
            await svc.close()
    run(case())


def test_offline_new_request_needs_prior_negotiation(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        try:
            bridge.outage = True
            job = await svc.create("101", preferred())
            first = await due(svc, job)
            assert first["state"] == "remote_unavailable" and gateway.cloud_calls == 0
            bridge.outage = False
            await svc._routing_context(first)
            bridge.outage = True
            final = await due(svc, job)
            assert final["state"] == "registered" and gateway.cloud_calls == 1, final
            assert not bridge.tasks
        finally:
            await svc.close()
    run(case())


def test_cloud_unconfigured_keeps_same_intent_waiting(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.health, gateway.admitted = "unavailable", False
        try:
            final = await due(svc, await svc.create("101", preferred()))
            assert final["state"] == "routing_wait" and gateway.cloud_calls == 0
            assert final["routing_reason"] == "cloud_not_configured"
            assert not bridge.tasks
        finally:
            await svc.close()
    run(case())


def test_route_cas_single_winner(tmp_path):
    async def case():
        svc, _, _ = create_service(tmp_path)
        try:
            job = await svc.create("101", preferred())
            def claim(_):
                return svc.store.compare_patch(job["id"], {"route_generation": 0},
                    {"route_generation": 1, "selected_route": "cloud", "cloud_execution_attempted": True})
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(claim, range(8)))
            assert sum(result is not None for result in results) == 1
        finally:
            await svc.close()
    run(case())


def test_another_profile_revision_does_not_refresh_healthy_evidence():
    obs, _ = observe_availability({}, capabilities(100, 1, "unavailable"), "fake-image", 100)
    obs, _ = observe_availability(obs, capabilities(110, 2), "fake-image", 110)
    unrelated = capabilities(110, 3)
    updated, _ = observe_availability(obs, unrelated, "fake-image", 180)
    assert updated["received_at"] == 110 and updated["healthy_reports"] == 1
    assert updated["impaired"] is True
    expired, _ = observe_availability(updated, capabilities(110, 4), "fake-image", 201)
    assert expired["health"] == "unknown" and expired["received_at"] == 110


def test_drain_does_not_block_existing_bridge_receipt(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.ready = False
        try:
            job = await svc.create("101", preferred())
            await due(svc, job)
            bridge.admission, bridge.ready = False, True
            final = await due(svc, job)
            assert final["state"] == "registered" and gateway.cloud_calls == 0, final
        finally:
            await svc.close()
    run(case())


def test_queue_budget_survives_process_restart(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.ready = False
        job = await svc.create("101", preferred())
        await due(svc, job)
        await svc.local(svc.store.patch, job["id"], {"queue_elapsed": 20,
            "queue_observed_monotonic": time.monotonic() - 15, "queue_clock_epoch": time.time() - time.monotonic()})
        await svc.close()
        svc, _, _ = create_service(tmp_path, bridge, gateway)
        try:
            final = await due(svc, job)
            assert final["state"] == "registered" and gateway.cloud_calls == 1, final
            assert final["queue_elapsed"] >= 35
        finally:
            await svc.close()
    run(case())


def test_recovery_only_routes_future_requests_and_preserves_cloud_unknown(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.health, gateway.unknown_cloud = "unavailable", True
        try:
            old = await svc.create("101", preferred())
            await due(svc, old)
            assert gateway.cloud_calls == 1
            bridge.health, bridge.revision = "available", 2
            newer = await svc.create("101", preferred(client_request_id="second"))
            context = await svc._routing_context(newer)
            assert context["observation"]["impaired"] is True
            key = digest([newer["endpoint_fingerprint"], newer["workspace"], "fake-image"])
            context["observation"]["healthy_since"] -= 61
            context["observation"]["healthy_since_monotonic"] -= 61
            # Deterministic passage of the recovery interval, not a health override.
            with svc.store.connection() as db:
                db.execute("UPDATE routing_observations SET record=? WHERE key=?", (json.dumps(context), key))
            bridge.revision = 3
            final = await due(svc, newer)
            assert final["selected_route"] == "bridge" and final["state"] == "registered", final
            old_final = await due(svc, old)
            assert old_final["selected_route"] == "cloud" and old_final["state"] == "cloud_unknown", old_final
            assert gateway.cloud_calls == 1 and len(bridge.tasks) == 1
        finally:
            await svc.close()
    run(case())


def test_cloud_cancel_uncertain_execution_never_creates_other_route(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.health, gateway.unknown_cloud = "unavailable", True
        try:
            job = await svc.create("101", preferred())
            await due(svc, job)
            await svc.cancel("101", job["id"])
            final = await due(svc, job)
            assert final["cancel_requested"] is True
            assert final["selected_route"] == "cloud" and gateway.cloud_calls == 1
            assert not bridge.tasks and gateway.cancel_calls == 1
        finally:
            await svc.close()
    run(case())


def test_unknown_null_timestamps_can_recover_with_distinct_reports():
    empty = capabilities()
    empty["routing_availability_v1"]["profiles"][0].update(health="unknown", observed_at=None, valid_until=None)
    obs, _ = observe_availability({}, empty, "fake-image", 100)
    obs, _ = observe_availability(obs, capabilities(110, 2), "fake-image", 110)
    assert obs["healthy_reports"] == 1 and obs["impaired"]
    obs, _ = observe_availability(obs, capabilities(171, 3), "fake-image", 171)
    assert not obs["impaired"]


@pytest.mark.parametrize("mutation", ["reason", "evidence", "missing_time", "too_long", "duplicate", "null_descriptor"])
def test_malformed_availability_does_not_negotiate(mutation):
    caps = capabilities()
    profile = caps["routing_availability_v1"]["profiles"][0]
    if mutation == "reason": profile.pop("reason_code")
    elif mutation == "evidence": profile["evidence_kind"] = "invented"
    elif mutation == "missing_time": profile.pop("valid_until")
    elif mutation == "too_long": profile["valid_until"] = datetime.fromtimestamp(10000, timezone.utc).isoformat()
    elif mutation == "duplicate": caps["routing_availability_v1"]["profiles"].append(dict(profile))
    else: caps["routing_availability_v1"] = None
    assert observe_availability({}, caps, "fake-image", 100) == ({}, False)


def test_clock_jump_cannot_accelerate_recovery_or_refresh_ttl():
    obs, _ = observe_availability({}, capabilities(100, 1, "unavailable"), "fake-image", 100, 10)
    obs, _ = observe_availability(obs, capabilities(110, 2), "fake-image", 110, 20)
    jumped, _ = observe_availability(obs, capabilities(180, 3), "fake-image", 180, 21)
    assert jumped["impaired"] and jumped["healthy_reports"] == 1


def test_quiet_background_health_restores_future_bridge_requests(tmp_path, monkeypatch):
    import app.integrations.render_bridge.native_service as native_module
    import app.integrations.render_bridge.store as store_module
    # Exact synthetic clock: the policy separately tests clock-jump boundaries.
    # Avoid arbitrary wall/monotonic fractions at the exact 60-second threshold.
    wall, mono = [1_800_000_000.0], [1000.0]
    clock = SimpleNamespace(time=lambda: wall[0], monotonic=lambda: mono[0])
    monkeypatch.setattr(native_module, "time", clock)
    monkeypatch.setattr(store_module, "time", clock)
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        bridge.clock, bridge.health = clock.time, "unavailable"
        try:
            first = await due(svc, await svc.create("101", preferred()))
            assert first["state"] == "registered" and first["selected_route"] == "cloud"
            wall[0] += 5; mono[0] += 5
            bridge.health, bridge.revision = "available", 2
            await svc.tick()  # no unfinished jobs; first recovery observation
            count = len(bridge.calls)
            await svc.tick()
            assert len(bridge.calls) == count  # bounded poll, not every tick
            wall[0] += 60; mono[0] += 60
            bridge.revision = 3
            await svc.tick()  # no user request; stability threshold now met
            final = await due(svc, await svc.create("101", preferred(client_request_id="after_recovery")))
            assert final["selected_route"] == "bridge" and final["state"] == "registered", final
            assert gateway.cloud_calls == 1 and len(bridge.tasks) == 1
        finally:
            await svc.close()
    run(case())


def test_background_retry_after_survives_restart(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        key = svc._health_key()
        deadline = time.time() + 60
        await svc.local(svc.store.health_poll, key, time.time(), defer_until=deadline)
        await svc.close()
        svc, _, _ = create_service(tmp_path, bridge, gateway)
        try:
            final = await due(svc, await svc.create("101", preferred()))
            assert final["state"] == "remote_unavailable" and not bridge.calls
            assert final["retry_not_before"] == deadline
            assert gateway.cloud_calls == 0
        finally:
            await svc.close()
    run(case())


def test_official_account_status_evidence_is_supported():
    caps = capabilities()
    caps["routing_availability_v1"]["profiles"][0]["evidence_kind"] = "account_status"
    observation, supported = observe_availability({}, caps, "fake-image", 100)
    assert supported and observation["health"] == "available"


def test_failed_background_probe_resets_recovery_window(tmp_path, monkeypatch):
    import app.integrations.render_bridge.native_service as native_module
    import app.integrations.render_bridge.store as store_module
    # Exact synthetic clock: the policy separately tests clock-jump boundaries.
    # Avoid arbitrary wall/monotonic fractions at the exact 60-second threshold.
    wall, mono = [1_800_000_000.0], [1000.0]
    clock = SimpleNamespace(time=lambda: wall[0], monotonic=lambda: mono[0])
    monkeypatch.setattr(native_module, "time", clock)
    monkeypatch.setattr(store_module, "time", clock)
    async def case():
        svc, _, bridge = create_service(tmp_path)
        bridge.clock, bridge.health = clock.time, "unavailable"
        key = digest([digest(svc.settings.base_url), svc.settings.workspace, "fake-image"])
        try:
            await svc.tick()
            wall[0] += 5; mono[0] += 5
            bridge.health, bridge.revision = "available", 2
            await svc.tick()
            wall[0] += 30; mono[0] += 30
            bridge.outage = True
            await svc.tick()
            interrupted = await svc.local(svc.store.routing_observation, key)
            assert interrupted["observation"]["healthy_since"] is None
            wall[0] += 30; mono[0] += 30
            bridge.outage, bridge.revision = False, 3
            await svc.tick()
            fresh = await svc.local(svc.store.routing_observation, key)
            assert fresh["observation"]["impaired"] is True and fresh["observation"]["healthy_reports"] == 1
        finally:
            await svc.close()
    run(case())


def test_known_auth_denial_invalidates_cache_before_later_outage(tmp_path):
    async def case():
        svc, gateway, bridge = create_service(tmp_path)
        try:
            job = await svc.create("101", preferred())
            await svc._routing_context(job)
            bridge.auth_denied = True
            with pytest.raises(BridgeError):
                await svc._routing_context(job)
            bridge.auth_denied, bridge.outage = False, True
            with pytest.raises(BridgeError):
                await svc._routing_context(job)
            assert gateway.cloud_calls == 0
        finally:
            await svc.close()
    run(case())


def test_unknown_attempt_receipt_reconciles_after_restart_without_fallback(tmp_path):
    """Bridge aborted-turn reconciliation may publish the original attempt later."""
    async def case():
        gateway, bridge = CloudGateway(), RoutingBridge()
        bridge.ready = False
        svc, _, _ = make_service(tmp_path, gateway, bridge)
        svc.settings = replace(svc.settings, auto_fallback_enabled=True, queue_wait_seconds=30)
        job = await svc.create("101", preferred())
        await svc.tick()
        remote = next(iter(bridge.tasks.values()))
        remote.update(state="execution_unknown")
        first = await due(svc, job)
        assert first["state"] == "execution_unknown"
        identity = (remote["remote_task_id"], remote["attempt_id"], remote["origin_key"])
        bridge.health = "unavailable"
        for _ in range(3):
            assert (await due(svc, job))["state"] == "execution_unknown"
        assert gateway.cloud_calls == gateway.register_calls == 0
        assert not bridge.acks
        await svc.close()
        svc, _, _ = make_service(tmp_path, gateway, bridge)
        svc.settings = replace(svc.settings, auto_fallback_enabled=True, queue_wait_seconds=30)
        try:
            bridge.ready = True  # Original attempt reconciled, not a new generation.
            final = await due(svc, job)
            assert final["state"] == "registered"
            assert (remote["remote_task_id"], remote["attempt_id"], remote["origin_key"]) == identity
            for _ in range(3):
                await svc.tick()
            assert gateway.create_calls == gateway.register_calls == 1
            assert gateway.cloud_calls == 0
            assert len(bridge.tasks) == len(bridge.acks) == 1
            assert sum(method == "POST" and path == "tasks" for method, path in bridge.calls) == 1
        finally:
            await svc.close()
    run(case())
