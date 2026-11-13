from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.render_bridge.node_rewards import install_node_reward_account_routes


def _app(tmp_path, nodes, *, truncated=False):
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


def test_node_reward_binding_is_account_scoped_and_points_are_separate(tmp_path):
    nodes = [_node(images=3)]
    app = _app(tmp_path, nodes)
    with TestClient(app) as client:
        bound = client.post("/api/account/node-rewards/bindings",
                            headers=_headers(), json={"node_id": "node_1"})
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
    app = _app(tmp_path, [_node()])
    with TestClient(app) as client:
        first = client.post("/api/account/node-rewards/bindings",
                            headers=_headers(), json={"node_id": "node_1"})
        assert first.status_code == 200

        conflict = client.post("/api/account/node-rewards/bindings",
                               headers=_headers(42), json={"node_id": "node_1"})
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "node_already_bound"

        bad_origin = client.post("/api/account/node-rewards/bindings",
                                 headers={**_headers(), "Origin": "https://other.test"},
                                 json={"node_id": "node_1"})
        assert bad_origin.status_code == 403


def test_node_reward_binding_requires_login_and_unique_live_node_identity(tmp_path):
    app = _app(tmp_path, [_node(), _node(pool_id="pool_2", executor="executor_2")])
    with TestClient(app) as client:
        no_login = client.get("/api/account/node-rewards")
        assert no_login.status_code == 401

        ambiguous = client.post("/api/account/node-rewards/bindings",
                                headers=_headers(), json={"node_id": "node_1"})
        assert ambiguous.status_code == 409
        assert ambiguous.json()["detail"]["code"] == "node_identity_ambiguous"

        malformed = client.post("/api/account/node-rewards/bindings",
                                headers=_headers(), json={"node_id": "node_1", "user_id": 42})
        assert malformed.status_code == 422

    partial_app = _app(tmp_path / "partial", [_node()], truncated=True)
    with TestClient(partial_app) as partial_client:
        incomplete = partial_client.post("/api/account/node-rewards/bindings",
                                          headers=_headers(), json={"node_id": "node_1"})
        assert incomplete.status_code == 503
        assert incomplete.json()["detail"]["code"] == "node_reward_metrics_incomplete"
