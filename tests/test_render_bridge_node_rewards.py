from pathlib import Path
from types import SimpleNamespace
import hashlib
import hmac
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.integrations.render_bridge.node_rewards import install_node_reward_account_routes


def _app(tmp_path, nodes, *, truncated=False, approvals=None):
    approvals = approvals if approvals is not None else {}

    async def metrics():
        return {
            "available": True,
            "tracking_since": "2026-11-12T00:00:00Z",
            "truncated": truncated,
            "nodes": nodes,
        }

    app = FastAPI()
    install_node_reward_account_routes(
        app,
        session_user=lambda request, authorization: (
            41 if authorization == "Bearer account-41"
            else 42 if authorization == "Bearer account-42"
            else None
        ),
        account_loader=lambda user_id: SimpleNamespace(user_id=user_id, status="active"),
        auth_enabled=lambda: True,
        reward_metrics_loader=metrics,
        reward_claim_approval_loader=lambda digest: approvals.get(
            digest, {"available": False, "code": "claim_approval_not_found"}),
        node_binding_status_secret="bridge-reward-secret",
        database_path=Path(tmp_path) / "node-rewards.sqlite3",
    )
    return app


def _node(*, node_id="node_1", pool_id="pool_1", executor="executor_1",
          images=3, state="active"):
    return {
        "pool_id": pool_id,
        "pool_name": "Fixture Pool",
        "node_id": node_id,
        "executor_instance": executor,
        "node_state": state,
        "liveness": "online",
        "last_seen_at": "2026-11-12T00:01:00Z",
        "current_execution": None,
        "metrics": {"rewardable_images": images},
    }


def _headers(account=41):
    return {
        "Authorization": f"Bearer account-{account}",
        "Origin": "http://testserver",
        "X-Alchemy-UI": "node-rewards",
    }


def _approval(node, *, images=None):
    return {
        "available": True,
        "pool_id": node["pool_id"],
        "node_id": node["node_id"],
        "executor_instance": node["executor_instance"],
        "node_state": node["node_state"],
        "rewardable_images": (node["metrics"]["rewardable_images"]
                               if images is None else images),
        "pool_name": node["pool_name"],
    }


def _start_claim(client, *, account=41):
    response = client.post("/api/account/node-rewards/claims",
                           headers=_headers(account), json={})
    assert response.status_code == 200
    return response.json()["challenge"]


def _confirm_claim(client, challenge, *, account=41):
    return client.post("/api/account/node-rewards/bindings",
                       headers=_headers(account), json={"challenge": challenge})


def _register_approval(approvals, challenge, node, *, images=None):
    digest = hashlib.sha256(challenge.encode("ascii")).hexdigest()
    approvals[digest] = _approval(node, images=images)


def _binding_status_headers(node, *, secret="bridge-reward-secret", timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    message = "\n".join(("renderbridge-node-binding-v1", str(timestamp), node["pool_id"],
                          node["node_id"], node["executor_instance"]))
    key = hmac.new(secret.encode("ascii"), b"alchemy-node-binding-status-key-v1",
                   hashlib.sha256).digest()
    signature = hmac.new(key, message.encode("ascii"),
                         hashlib.sha256).hexdigest()
    return {
        "X-Bridge-Account-Status-Timestamp": str(timestamp),
        "X-Bridge-Account-Status-Signature": signature,
    }


def test_node_reward_binding_is_account_scoped_and_points_are_separate(tmp_path):
    nodes = [_node(images=3)]
    approvals = {}
    app = _app(tmp_path, nodes, approvals=approvals)
    with TestClient(app) as client:
        challenge = _start_claim(client)
        assert len(challenge) == 43
        _register_approval(approvals, challenge, nodes[0])
        bound = _confirm_claim(client, challenge)
        assert bound.status_code == 200
        assert bound.json() == {
            "status": "bound",
            "node_id": "node_1",
            "pool_name": "Fixture Pool",
        }

        summary = client.get("/api/account/node-rewards", headers=_headers())
        assert summary.status_code == 200
        value = summary.json()
        assert value["totals"] == {
            "bound_nodes": 1,
            "successful_images": 0,
            "reward_points": "0.00",
        }
        assert value["nodes"][0]["successful_images"] == 0
        assert value["nodes"][0]["reward_points"] == "0.00"

        nodes[0]["metrics"]["rewardable_images"] = 6
        after_binding = client.get("/api/account/node-rewards", headers=_headers()).json()
        assert after_binding["totals"]["successful_images"] == 3
        assert after_binding["totals"]["reward_points"] == "0.06"
        assert value["reward_points_per_image"] == "0.02"

        repeat_challenge = _start_claim(client)
        _register_approval(approvals, repeat_challenge, nodes[0], images=6)
        repeated = _confirm_claim(client, repeat_challenge)
        assert repeated.status_code == 200
        assert repeated.json()["status"] == "already_bound"
        current_binding = app.state.node_reward_account_store.list_all_bindings()[0]
        assert current_binding["baseline_images"] == 3

        replay = _confirm_claim(client, challenge)
        assert replay.status_code == 409
        assert replay.json()["detail"]["code"] == "node_reward_claim_invalid"

        other_account = client.get("/api/account/node-rewards", headers=_headers(42))
        assert other_account.status_code == 200
        assert other_account.json()["totals"]["bound_nodes"] == 0



def test_existing_node_binding_migration_does_not_award_prebinding_images(tmp_path):
    import sqlite3

    database = Path(tmp_path) / "node-rewards.sqlite3"
    with sqlite3.connect(database) as con:
        con.execute("""
            CREATE TABLE node_reward_node_bindings (
                pool_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                executor_instance TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                bound_at INTEGER NOT NULL,
                PRIMARY KEY (pool_id, node_id, executor_instance)
            )
        """)
        con.execute("""
            INSERT INTO node_reward_node_bindings
                (pool_id,node_id,executor_instance,user_id,bound_at)
            VALUES (?,?,?,?,?)
        """, ("pool_1", "node_1", "executor_1", 41, 1_800_000_000))

    nodes = [_node(images=4)]
    app = _app(tmp_path, nodes)
    with TestClient(app) as client:
        first = client.get("/api/account/node-rewards", headers=_headers()).json()
        assert first["totals"]["successful_images"] == 0
        assert first["totals"]["reward_points"] == "0.00"

        nodes[0]["metrics"]["rewardable_images"] = 5
        next_image = client.get("/api/account/node-rewards", headers=_headers()).json()
        assert next_image["totals"]["successful_images"] == 1
        assert next_image["totals"]["reward_points"] == "0.02"

def test_node_reward_binding_rejects_cross_account_claim_and_unverified_origin(tmp_path):
    node = _node()
    approvals = {}
    app = _app(tmp_path, [node], approvals=approvals)
    with TestClient(app) as client:
        challenge = _start_claim(client)
        _register_approval(approvals, challenge, node)
        first = _confirm_claim(client, challenge)
        assert first.status_code == 200

        other_challenge = _start_claim(client, account=42)
        _register_approval(approvals, other_challenge, node)
        conflict = _confirm_claim(client, other_challenge, account=42)
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "node_already_bound"

        bad_origin = client.post("/api/account/node-rewards/claims",
                                 headers={**_headers(), "Origin": "https://other.test"},
                                 json={})
        assert bad_origin.status_code == 403



def test_node_reward_claim_is_account_created_without_node_id(tmp_path):
    app = _app(tmp_path, [_node(), _node(pool_id="pool_2", executor="executor_2")],
               truncated=True)
    with TestClient(app) as client:
        no_login = client.get("/api/account/node-rewards")
        assert no_login.status_code == 401

        supplied_node = client.post("/api/account/node-rewards/claims",
                                    headers=_headers(), json={"node_id": "node_1"})
        assert supplied_node.status_code == 422

        challenge = client.post("/api/account/node-rewards/claims",
                                headers=_headers(), json={})
        assert challenge.status_code == 200
        assert challenge.json()["status"] == "challenge_created"
        assert "node_id" not in challenge.json()
        assert challenge.json()["challenge"]

        id_only = client.post("/api/account/node-rewards/bindings",
                              headers=_headers(), json={"node_id": "node_1"})
        assert id_only.status_code == 422


def test_unconfirmed_claim_waits_for_bridge_proof_and_binds_its_identity(tmp_path):
    approvals = {}
    app = _app(tmp_path, [_node()], approvals=approvals)
    with TestClient(app) as client:
        challenge = _start_claim(client)
        missing = _confirm_claim(client, challenge)
        assert missing.status_code == 503
        assert missing.json()["detail"]["code"] == "node_reward_claim_unverified"
        assert app.state.node_reward_account_store.list_all_bindings() == []

        proved_node = _node(pool_id="pool_other", node_id="node_other",
                            executor="executor_other")
        _register_approval(approvals, challenge, proved_node)
        bound = _confirm_claim(client, challenge)
        assert bound.status_code == 200
        assert bound.json()["node_id"] == "node_other"
        binding = app.state.node_reward_account_store.list_all_bindings()[0]
        assert (binding["pool_id"], binding["node_id"], binding["executor_instance"]) == (
            "pool_other", "node_other", "executor_other")

def test_claim_challenge_is_account_bound_expiring_and_only_digest_is_stored(tmp_path):
    node = _node()
    approvals = {}
    app = _app(tmp_path, [node], approvals=approvals)
    with TestClient(app) as client:
        challenge = _start_claim(client)
        assert _confirm_claim(client, challenge, account=42).status_code == 404

        store = app.state.node_reward_account_store
        with sqlite3.connect(store.path) as con:
            rows = con.execute("SELECT challenge_digest,created_at,expires_at,consumed_at FROM "
                               "node_reward_binding_challenges").fetchall()
            assert len(rows) == 1
            assert rows[0][0] == hashlib.sha256(challenge.encode("ascii")).hexdigest()
            assert rows[0][2] - rows[0][1] == 600
            assert rows[0][3] is None
            con.execute("UPDATE node_reward_binding_challenges SET expires_at=0")

        _register_approval(approvals, challenge, node)
        expired = _confirm_claim(client, challenge)
        assert expired.status_code == 410
        assert expired.json()["detail"]["code"] == "node_reward_claim_expired"
        assert store.list_all_bindings() == []


@pytest.mark.parametrize(("node_state", "images", "status", "code"), [
    ("revoked", 3, 409, "node_revoked"),
    ("inactive", 3, 409, "node_not_active"),
    ("active", -1, 503, "node_reward_image_count_unavailable"),
    ("active", None, 503, "node_reward_image_count_unavailable"),
])
def test_unusable_approval_never_creates_binding(tmp_path, node_state, images, status, code):
    node = _node()
    approvals = {}
    app = _app(tmp_path, [node], approvals=approvals)
    with TestClient(app) as client:
        challenge = _start_claim(client)
        _register_approval(approvals, challenge, node, images=images)
        digest = hashlib.sha256(challenge.encode("ascii")).hexdigest()
        approvals[digest]["node_state"] = node_state
        if images is None:
            approvals[digest]["rewardable_images"] = None
        response = _confirm_claim(client, challenge)
        assert response.status_code == status
        assert response.json()["detail"]["code"] == code
        assert app.state.node_reward_account_store.list_all_bindings() == []



def test_bridge_proof_selects_full_identity_even_when_node_ids_are_duplicated(tmp_path):
    node = _node(images=3)
    duplicate = _node(pool_id="pool_2", executor="executor_2", images=99)
    approvals = {}
    app = _app(tmp_path, [node, duplicate], approvals=approvals)
    with TestClient(app) as client:
        challenge = _start_claim(client)
        _register_approval(approvals, challenge, duplicate, images=17)
        bound = _confirm_claim(client, challenge)
        assert bound.status_code == 200
        assert bound.json()["node_id"] == "node_1"
        binding = app.state.node_reward_account_store.list_all_bindings()[0]
        assert binding["pool_id"] == "pool_2"
        assert binding["executor_instance"] == "executor_2"
        assert binding["baseline_images"] == 17


def test_one_account_can_bind_multiple_nodes_with_separate_claims(tmp_path):
    nodes = [
        _node(node_id="node_1", pool_id="pool_1", executor="executor_1", images=4),
        _node(node_id="node_2", pool_id="pool_1", executor="executor_2", images=8),
    ]
    approvals = {}
    app = _app(tmp_path, nodes, approvals=approvals)
    with TestClient(app) as client:
        for node in nodes:
            challenge = _start_claim(client)
            _register_approval(approvals, challenge, node)
            response = _confirm_claim(client, challenge)
            assert response.status_code == 200
            assert response.json()["node_id"] == node["node_id"]

        summary = client.get("/api/account/node-rewards", headers=_headers()).json()
        assert summary["totals"]["bound_nodes"] == 2

def test_claim_codes_are_not_echoed_in_responses(tmp_path):
    node = _node()
    approvals = {}
    app = _app(tmp_path, [node], approvals=approvals)
    with TestClient(app) as client:
        challenge = _start_claim(client)
        failed = _confirm_claim(client, challenge)
        assert failed.status_code == 503
        assert challenge not in failed.text

        _register_approval(approvals, challenge, node)
        success = _confirm_claim(client, challenge)
        assert success.status_code == 200
        assert challenge not in success.text


def test_concurrent_verified_claims_produce_only_one_binding(tmp_path):
    node = _node()
    app = _app(tmp_path, [node])
    with TestClient(app) as client:
        first = _start_claim(client, account=41)
        second = _start_claim(client, account=42)
    store = app.state.node_reward_account_store
    identities = [
        (41, hashlib.sha256(first.encode("ascii")).hexdigest()),
        (42, hashlib.sha256(second.encode("ascii")).hexdigest()),
    ]
    for account, digest in identities:
        store.pending_binding_challenge(account, challenge_digest=digest)

    def bind(pair):
        account, digest = pair
        try:
            return store.bind_node_from_challenge(
                account, challenge_digest=digest, pool_id=node["pool_id"],
                node_id=node["node_id"], executor_instance=node["executor_instance"],
                baseline_images=node["metrics"]["rewardable_images"])
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(bind, identities))
    assert sum(isinstance(result, dict) and result["status"] == "bound"
               for result in results) == 1
    errors = [result for result in results if isinstance(result, Exception)]
    assert len(errors) == 1
    assert getattr(errors[0], "code", None) == "node_already_bound"
    assert len(store.list_all_bindings()) == 1


def test_bridge_signed_local_status_returns_only_current_account_reference(tmp_path):
    node = _node()
    app = _app(tmp_path, [node])
    app.state.node_reward_account_store.bind_node(
        41, pool_id=node["pool_id"], node_id=node["node_id"],
        executor_instance=node["executor_instance"], baseline_images=3)
    identity = {key: node[key] for key in
                ("pool_id", "node_id", "executor_instance")}

    with TestClient(app) as client:
        headers = _binding_status_headers(node)
        response = client.post("/api/internal/render-bridge/node-account-binding",
                               headers=headers, json=identity)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "available": True, "bound": True, "account_user_id": 41,
        }
        assert "email" not in response.text
        assert "node_token" not in response.text

        wrong_signature = {**headers, "X-Bridge-Account-Status-Signature": "0" * 64}
        rejected = client.post("/api/internal/render-bridge/node-account-binding",
                               headers=wrong_signature, json=identity)
        assert rejected.status_code == 401

        expired = _binding_status_headers(node, timestamp=int(time.time()) - 600)
        rejected = client.post("/api/internal/render-bridge/node-account-binding",
                               headers=expired, json=identity)
        assert rejected.status_code == 401

        extra_identity = {**identity, "user_id": 42}
        rejected = client.post("/api/internal/render-bridge/node-account-binding",
                               headers=headers, json=extra_identity)
        assert rejected.status_code == 422


def test_bridge_signed_local_status_reflects_unbind_without_exposing_history(tmp_path):
    node = _node()
    app = _app(tmp_path, [node])
    store = app.state.node_reward_account_store
    store.bind_node(41, pool_id=node["pool_id"], node_id=node["node_id"],
                    executor_instance=node["executor_instance"], baseline_images=3)
    identity = {key: node[key] for key in
                ("pool_id", "node_id", "executor_instance")}

    with TestClient(app) as client:
        headers = _binding_status_headers(node)
        active = client.post("/api/internal/render-bridge/node-account-binding",
                             headers=headers, json=identity)
        assert active.json() == {
            "available": True, "bound": True, "account_user_id": 41,
        }

        with sqlite3.connect(store.path) as con:
            con.execute("DELETE FROM node_reward_node_bindings WHERE pool_id=? AND node_id=? "
                        "AND executor_instance=?",
                        (node["pool_id"], node["node_id"], node["executor_instance"]))
        unbound = client.post("/api/internal/render-bridge/node-account-binding",
                              headers=_binding_status_headers(node), json=identity)
        assert unbound.status_code == 200
        assert unbound.json() == {"available": True, "bound": False,
                                  "account_user_id": None}
