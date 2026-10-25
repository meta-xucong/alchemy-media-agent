"""Synthetic cross-process HTTP check; never starts Codex or a paid provider.

Run with the companion Bridge's locked test dependencies. Only loopback sockets,
temporary databases, public fixture tokens and synthetic pixels are used. This
checks actual TCP serialization/recovery, not TLS, NAT, WAN or live billing.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-checkout", type=Path, required=True)
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--state-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = args.bridge_checkout.resolve() / "src"
    if not (source / "render_bridge" / "api.py").is_file():
        parser.error("Bridge checkout has no src/render_bridge/api.py")
    if args.serve and (args.state_root is None or not args.port):
        parser.error("internal server requires state root and port")
    sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(source)]
    return args


def unused_loopback_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class BridgeProcess:
    """Bounded child lifetime; no pipes that could fill while the test runs."""

    def __init__(self, checkout, root):
        self.checkout, self.root = checkout, root
        self.port = unused_loopback_port()
        self.process = None
        self.log = None

    def start(self):
        assert self.process is None
        self.log = (self.root / "server.log").open("ab")
        # Do not forward account/CLI/provider secrets into the fixture process.
        environment = {key: value for key, value in os.environ.items()
                       if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG"}}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--bridge-checkout",
             str(self.checkout.resolve()), "--serve", "--state-root", str(self.root),
             "--port", str(self.port)],
            stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log, env=environment,
        )

    def stop(self):
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            finally:
                self.process = None
                self.log.close()
                self.log = None

    async def ready(self):
        import httpx
        deadline = time.monotonic() + 15
        async with httpx.AsyncClient(timeout=0.5, trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError("Fixture server exited before readiness: " +
                                       (self.root / "server.log").read_text(encoding="utf-8", errors="replace")[-4000:])
                try:
                    response = await client.get(
                        f"http://127.0.0.1:{self.port}/bridge/v1/capabilities",
                        headers={"Authorization": "Bearer fixture-token"})
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.05)
        raise TimeoutError("Fixture server readiness exceeded 15 seconds")


class ResponseLossProxy:
    """Test-only small HTTP proxy, not a production reverse-proxy implementation.

    Requests in this fixture have Content-Length. Every response is buffered
    only so a successful durable server operation can lose its TCP reply.
    """

    def __init__(self, upstream_port):
        self.upstream_port = upstream_port
        self.calls = []
        self.losses = []
        self.target = None
        self.handlers = set()
        self.server = None
        self.errors = []

    async def start(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        return f"http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"

    def lose_next(self, method, path):
        assert self.target is None, "Previous response-loss target was not exercised"
        self.target = (method, path)

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        upstream = None
        try:
            async with asyncio.timeout(10):
                header = await reader.readuntil(b"\r\n\r\n")
                lines = header.split(b"\r\n")
                length = next((int(line.split(b":", 1)[1].strip()) for line in lines
                               if line.lower().startswith(b"content-length:")), 0)
                if length > 2 * 1024 * 1024:
                    raise ValueError("Synthetic request unexpectedly large")
                body = await reader.readexactly(length) if length else b""
                method, path, _ = lines[0].decode("ascii").split(" ")
                self.calls.append((method, path))
                headers = [line for line in lines[:-2]
                           if not line.lower().startswith(b"connection:")]
                request = b"\r\n".join(headers + [b"Connection: close", b"", b""]) + body
                remote, upstream = await asyncio.open_connection("127.0.0.1", self.upstream_port)
                upstream.write(request)
                await upstream.drain()
                response = await remote.read()
                if self.target == (method, path):
                    if not response.startswith(b"HTTP/1.1 200"):
                        raise AssertionError("Fault injection did not follow a successful response")
                    self.losses.append(self.target)
                    self.target = None
                else:
                    writer.write(response)
                    await writer.drain()
        except (OSError, asyncio.IncompleteReadError):
            # Expected during deliberate Bridge shutdown/client disconnect.
            pass
        except Exception as error:
            self.errors.append(type(error).__name__)
        finally:
            if upstream:
                upstream.close()
            writer.close()
            self.handlers.discard(task)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for task in list(self.handlers):
            task.cancel()
        if self.handlers:
            await asyncio.gather(*list(self.handlers), return_exceptions=True)


def fixture_store(root):
    from render_bridge.domain import BridgeStore
    return BridgeStore(root / "bridge.sqlite3", root / "artifacts",
                       enabled_profiles=("codex-image",))


def fixture_scope():
    from render_bridge.domain import SourceScope
    return SourceScope("fixture-source", "fixture-workspace")


def serve(args):
    import uvicorn
    from render_bridge.api import create_app
    from render_bridge.domain import SourceScope
    store = fixture_store(args.state_root)
    try:
        app = create_app(store=store, source_tokens={
            "fixture-token": fixture_scope(),
            "other-token": SourceScope("other-source", "other-workspace"),
        })
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="error")
    finally:
        store.close()


async def verify(checkout):
    from render_bridge_primary import PrimarySettings, PrimaryRequest, PrimaryTransport
    from render_bridge_primary.core import Reference
    from render_bridge_primary.http import BridgeClient, BridgeError
    from render_bridge.fake import fixture_png

    with tempfile.TemporaryDirectory(prefix="bridge-tcp-contract-") as temporary:
        root = Path(temporary)
        store = fixture_store(root)
        scope = fixture_scope()
        process = BridgeProcess(checkout, root)
        proxy = ResponseLossProxy(process.port)
        client = None
        try:
            store.provision_node(scope, "node", "instance")
            store.report_heartbeat(scope, "node", "instance", "available", ["codex-image"], [dict(
                profile_id="codex-image", profile_revision="1", report_revision=1,
                health="available", reason_code="ready", evidence_kind="local_probe",
                revalidation_generation=0)])
            process.start()
            await process.ready()
            url = await proxy.start()
            client = BridgeClient(url, "fixture-token")
            settings = PrimarySettings(enabled=True, base_url=url, token="fixture-token",
                workspace="fixture-workspace", profile="codex-image", state_dir=root / "ledger")
            transport = PrimaryTransport(settings, client=client)
            reference = fixture_png(40, 30)

            def request(key):
                return PrimaryRequest("v2", "owner", key, "Synthetic reference fixture", {
                    "codex_adapter": "codex_cli_imagegen_v1",
                    "image_options": {"schema_version": "1"}},
                    references=(Reference(reference, "image/png"),))

            bad = BridgeClient(url, "bad-token")
            try:
                try:
                    await bad.capabilities()
                    raise AssertionError("Bad bearer was accepted")
                except BridgeError as error:
                    assert error.status == 401
            finally:
                await bad.close()

            first = await transport.resolve(request("normal"))
            assert (first.route, first.state) == ("bridge", "queued")
            assert (await transport.resolve(request("normal"))).task_id == first.task_id
            remote = store.get_task(scope, first.task_id)
            input_id = remote["request"]["references"][0]["input_ref"]
            assert store.get_input(scope, input_id)["state"] == "ready"
            # Synthetic executor fixture mutates only its own temporary Bridge DB.
            # Source traffic above/below always uses the real HTTP client/server.
            claim = store.claim_task(scope, first.task_id, node_id="node", executor_instance="instance")
            assert store.start_execution(scope, first.task_id, claim["claim_id"])["may_execute"]
            assert not store.start_execution(scope, first.task_id, claim["claim_id"])["may_execute"]
            content = fixture_png(32, 24)
            digest = hashlib.sha256(content).hexdigest()
            upload = store.create_upload(scope, first.task_id, claim["claim_id"], dict(
                attempt_id=claim["attempt_id"], slot_id="primary", original_sha256=digest,
                size=len(content), mime_type="image/png"))
            store.put_upload_content(scope, upload["upload_id"], claim["claim_id"], content)
            receipt = store.commit_upload(scope, upload["upload_id"], claim["claim_id"])
            artifact_path = f'/bridge/v1/artifacts/{receipt["artifact_id"]}/content'
            proxy.lose_next("GET", artifact_path)
            interrupted = await transport.resolve(request("normal"))
            assert interrupted.route == "bridge" and interrupted.image is None
            result = await transport.resolve(request("normal"))
            assert result.image.content == content and result.image.sha256 == digest
            assert result.image.mime_type == "image/png"
            assert (result.image.width, result.image.height) == (32, 24)

            other = BridgeClient(url, "other-token")
            try:
                try:
                    await other.task(first.task_id)
                    raise AssertionError("Cross-source task was exposed")
                except BridgeError as error:
                    assert error.status == 404
            finally:
                await other.close()

            proxy.lose_next("POST", f'/bridge/v1/receipts/{result.receipt_id}/ack')
            try:
                await transport.acknowledge(request("normal"), "fixture-output")
                raise AssertionError("ACK response was not dropped")
            except BridgeError:
                pass
            assert store.get_task(scope, first.task_id)["delivery_ack"] == "accepted"
            assert (await transport.reconcile_pending())["acked"] == 1

            proxy.lose_next("POST", "/bridge/v1/tasks")
            lost = await transport.resolve(request("lost"))
            assert (lost.route, lost.state) == ("bridge", "bridge_submission_unknown")
            admitted = store.get_task_by_origin(scope, lost.origin_key)
            recovered = await PrimaryTransport(settings, client=client).resolve(request("lost"))
            assert recovered.task_id == admitted["remote_task_id"] and recovered.route == "bridge"

            process.stop()
            existing = await transport.resolve(request("lost"))
            assert existing.route == "bridge" and existing.task_id == recovered.task_id
            fresh = await transport.resolve(request("offline-new"))
            assert (fresh.route, fresh.reason) == ("api", "bridge_unavailable")
            process.start()
            await process.ready()
            restarted = await PrimaryTransport(settings, client=client).resolve(request("lost"))
            assert restarted.route == "bridge" and restarted.task_id == recovered.task_id
            assert proxy.calls.count(("POST", "/bridge/v1/tasks")) == 2
            assert len(proxy.losses) == 3 and proxy.target is None
            assert not proxy.errors, proxy.errors
            return {
                "result": "PASS", "transport": "separate-process loopback TCP",
                "checks": ["bearer rejection", "reference upload", "same-task replay",
                    "single synthetic start", "original SHA/MIME/dimensions", "cross-source rejection",
                    "download response loss/recovery", "ACK response loss/reconciliation",
                    "create response loss/same-origin recovery", "offline admitted task stays Bridge-owned",
                    "offline new task pre-admission fallback", "persistent same-task restart"],
                "admitted_task_posts": 2, "dropped_responses": len(proxy.losses),
                "not_tested": ["TLS", "NAT/tunnel", "WAN", "actual VPS", "Windows CLI",
                               "Veyra/real billing", "production configured launcher"],
            }
        finally:
            if client:
                await client.close()
            await proxy.close()
            process.stop()
            store.close()


if __name__ == "__main__":
    options = arguments()
    if options.serve:
        serve(options)
    else:
        async def bounded_run():
            return await asyncio.wait_for(verify(options.bridge_checkout), timeout=120)
        print(json.dumps(asyncio.run(bounded_run()), indent=2))
