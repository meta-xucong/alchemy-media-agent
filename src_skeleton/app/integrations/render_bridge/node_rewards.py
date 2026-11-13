from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


POINTS_PER_IMAGE = Decimal("0.02")
_IDENTIFIER = r"[A-Za-z0-9_-]{1,128}"
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class BindNodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    node_id: str = Field(min_length=1, max_length=128, pattern=_IDENTIFIER)


class NodeRewardStoreError(Exception):
    def __init__(self, code: str, status: int):
        self.code = code
        self.status = status
        super().__init__(code)


class NodeRewardAccountStore:
    def __init__(self, database_path: Path, *, clock=time.time):
        self.path = Path(database_path)
        self.clock = clock

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=3.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=3000")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""
            CREATE TABLE IF NOT EXISTS node_reward_node_bindings (
                pool_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                executor_instance TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                bound_at INTEGER NOT NULL,
                baseline_images INTEGER,
                PRIMARY KEY (pool_id, node_id, executor_instance)
            )
        """)
        columns = {row["name"] for row in con.execute(
            "PRAGMA table_info(node_reward_node_bindings)")}
        if "baseline_images" not in columns:
            con.execute(
                "ALTER TABLE node_reward_node_bindings ADD COLUMN baseline_images INTEGER")
        con.execute("""
            CREATE INDEX IF NOT EXISTS node_reward_node_bindings_user_idx
            ON node_reward_node_bindings(user_id, bound_at)
        """)
        return con

    def bind_node(self, user_id: int, *, pool_id: str, node_id: str,
                  executor_instance: str, baseline_images: int) -> dict:
        now = int(self.clock())
        identity = (pool_id, node_id, executor_instance)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute("""
                SELECT user_id FROM node_reward_node_bindings
                WHERE pool_id=? AND node_id=? AND executor_instance=?
            """, identity).fetchone()
            if existing is not None:
                if existing["user_id"] == user_id:
                    return {"status": "already_bound"}
                raise NodeRewardStoreError("node_already_bound", 409)
            con.execute("""
                INSERT INTO node_reward_node_bindings
                    (pool_id,node_id,executor_instance,user_id,bound_at,baseline_images)
                VALUES (?,?,?,?,?,?)
            """, (*identity, user_id, now, baseline_images))
        return {"status": "bound"}

    def initialize_baseline(self, user_id: int, *, pool_id: str, node_id: str,
                            executor_instance: str, baseline_images: int) -> int:
        identity = (pool_id, node_id, executor_instance)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("""
                UPDATE node_reward_node_bindings SET baseline_images=?
                WHERE pool_id=? AND node_id=? AND executor_instance=? AND user_id=?
                  AND baseline_images IS NULL
            """, (baseline_images, *identity, user_id))
            row = con.execute("""
                SELECT baseline_images FROM node_reward_node_bindings
                WHERE pool_id=? AND node_id=? AND executor_instance=? AND user_id=?
            """, (*identity, user_id)).fetchone()
        if row is None:
            raise NodeRewardStoreError("node_binding_not_found", 404)
        return int(row["baseline_images"])

    def list_bindings(self, user_id: int) -> list[dict]:
        with self._connect() as con:
            rows = con.execute("""
                SELECT pool_id,node_id,executor_instance,bound_at,baseline_images
                FROM node_reward_node_bindings WHERE user_id=?
                ORDER BY bound_at DESC,pool_id,node_id,executor_instance
            """, (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def list_all_bindings(self) -> list[dict]:
        with closing(self._connect()) as con:
            rows = con.execute("""
                SELECT pool_id,node_id,executor_instance,user_id,bound_at,baseline_images
                FROM node_reward_node_bindings
                ORDER BY bound_at,pool_id,node_id,executor_instance
            """).fetchall()
        return [dict(row) for row in rows]


def _utc(value: int) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def _points(images: int) -> str:
    return f"{(POINTS_PER_IMAGE * images):.2f}"


def _write_same_origin(request: Request) -> None:
    if request.headers.get("x-alchemy-ui") != "node-rewards":
        raise HTTPException(403, detail={"code": "same_origin_required"}, headers=NO_STORE)
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, detail={"code": "same_origin_required"}, headers=NO_STORE)
    origin = request.headers.get("origin")
    if not origin:
        return
    try:
        supplied, actual = urlsplit(origin), urlsplit(str(request.base_url))
        matches = (
            supplied.scheme,
            supplied.hostname,
            supplied.port or (443 if supplied.scheme == "https" else 80),
        ) == (
            actual.scheme,
            actual.hostname,
            actual.port or (443 if actual.scheme == "https" else 80),
        )
    except ValueError:
        matches = False
    if not matches:
        raise HTTPException(403, detail={"code": "same_origin_required"}, headers=NO_STORE)


def install_node_reward_account_routes(
    app,
    *,
    session_user,
    account_loader,
    auth_enabled,
    reward_metrics_loader,
    database_path: Path,
):
    router = APIRouter(prefix="/api/account/node-rewards")
    store = NodeRewardAccountStore(database_path)

    async def current_user_id(request: Request) -> int:
        if not auth_enabled():
            raise HTTPException(503, detail={"code": "account_login_not_configured"}, headers=NO_STORE)
        value = session_user(request, request.headers.get("authorization", ""))
        import inspect
        if inspect.isawaitable(value):
            value = await value
        if type(value) is not int or value <= 0:
            raise HTTPException(401, detail={"code": "session_login_required"}, headers=NO_STORE)
        if account_loader is not None:
            account = account_loader(value)
            if inspect.isawaitable(account):
                account = await account
            if getattr(account, "user_id", None) != value or getattr(account, "status", "") != "active":
                raise HTTPException(403, detail={"code": "account_inactive"}, headers=NO_STORE)
        return value

    async def reward_metrics():
        raw = await reward_metrics_loader()
        if not isinstance(raw, dict) or raw.get("available") is not True:
            code = raw.get("code") if isinstance(raw, dict) else None
            raise HTTPException(503, detail={"code": "node_reward_metrics_unavailable",
                                             "source_code": code if isinstance(code, str) else None},
                                headers=NO_STORE)
        if not isinstance(raw.get("nodes"), list):
            raise HTTPException(503, detail={"code": "node_reward_metrics_unavailable"}, headers=NO_STORE)
        return raw

    def image_count(item: dict) -> int:
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        value = metrics.get("rewardable_images")
        if type(value) is not int or value < 0:
            raise HTTPException(503, detail={"code": "node_reward_image_count_unavailable"},
                                headers=NO_STORE)
        return value

    @router.get("")
    async def summary(request: Request):
        user_id = await current_user_id(request)
        try:
            bindings = store.list_bindings(user_id)
        except (sqlite3.Error, OSError):
            return JSONResponse({"available": False, "code": "node_reward_storage_unavailable",
                                 "totals": None, "nodes": []},
                                status_code=200, headers=NO_STORE)
        if not bindings:
            return JSONResponse({
                "available": True,
                "tracking_since": None,
                "reward_points_per_image": "0.02",
                "totals": {"bound_nodes": 0, "successful_images": 0, "reward_points": "0.00"},
                "nodes": [],
            }, headers=NO_STORE)

        try:
            raw = await reward_metrics()
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            return JSONResponse({"available": False, "code": detail.get("code"),
                                 "totals": None, "nodes": []},
                                status_code=200, headers=NO_STORE)

        node_index = {
            (item.get("pool_id"), item.get("node_id"), item.get("executor_instance")): item
            for item in raw["nodes"] if isinstance(item, dict)
        }
        nodes = []
        total_images = 0
        for binding in bindings:
            item = node_index.get((binding["pool_id"], binding["node_id"], binding["executor_instance"]))
            if item is None:
                return JSONResponse({"available": False,
                                     "code": "node_reward_history_unavailable",
                                     "totals": None, "nodes": []},
                                    status_code=200, headers=NO_STORE)
            try:
                ledger_images = image_count(item)
                baseline_images = binding["baseline_images"]
                if baseline_images is None:
                    baseline_images = store.initialize_baseline(user_id,
                        pool_id=binding["pool_id"], node_id=binding["node_id"],
                        executor_instance=binding["executor_instance"],
                        baseline_images=ledger_images)
                images = max(0, ledger_images - baseline_images)
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                return JSONResponse({"available": False, "code": detail.get("code"),
                                     "totals": None, "nodes": []},
                                    status_code=200, headers=NO_STORE)
            total_images += images
            current = item.get("current_execution")
            nodes.append({
                "pool_name": item.get("pool_name", ""),
                "node_id": binding["node_id"],
                "executor_instance": binding["executor_instance"],
                "node_state": item.get("node_state", "unknown"),
                "liveness": item.get("liveness", "unknown"),
                "last_seen_at": item.get("last_seen_at"),
                "current_execution": current if isinstance(current, dict) else None,
                "successful_images": images,
                "reward_points": _points(images),
                "bound_at": _utc(binding["bound_at"]),
            })
        return JSONResponse({
            "available": True,
            "tracking_since": _utc(min(binding["bound_at"] for binding in bindings)),
            "reward_points_per_image": "0.02",
            "totals": {"bound_nodes": len(bindings), "successful_images": total_images,
                       "reward_points": _points(total_images)},
            "nodes": nodes,
        }, headers=NO_STORE)

    @router.post("/bindings")
    async def bind_node(body: BindNodeRequest, request: Request):
        user_id = await current_user_id(request)
        _write_same_origin(request)
        try:
            raw = await reward_metrics()
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            raise HTTPException(503, detail={"code": detail.get("code", "node_reward_metrics_unavailable")},
                                headers=NO_STORE) from exc
        if raw.get("truncated") is True:
            raise HTTPException(503, detail={"code": "node_reward_metrics_incomplete"},
                                headers=NO_STORE)
        matches = [item for item in raw["nodes"] if isinstance(item, dict)
                   and item.get("node_id") == body.node_id]
        if not matches:
            raise HTTPException(404, detail={"code": "node_not_registered"}, headers=NO_STORE)
        if len(matches) != 1:
            raise HTTPException(409, detail={"code": "node_identity_ambiguous"}, headers=NO_STORE)
        node = matches[0]
        if node.get("node_state") not in {"active", "draining"}:
            code = "node_revoked" if node.get("node_state") == "revoked" else "node_not_active"
            raise HTTPException(409, detail={"code": code}, headers=NO_STORE)
        try:
            baseline_images = image_count(node)
            result = store.bind_node(user_id, pool_id=node["pool_id"], node_id=node["node_id"],
                                     executor_instance=node["executor_instance"], baseline_images=baseline_images)
        except NodeRewardStoreError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code}, headers=NO_STORE) from None
        except (sqlite3.Error, OSError):
            raise HTTPException(503, detail={"code": "node_reward_storage_unavailable"},
                                headers=NO_STORE) from None
        return JSONResponse({"status": result["status"], "node_id": body.node_id,
                             "pool_name": node.get("pool_name", "")},
                            headers=NO_STORE)

    app.include_router(router)
    app.state.node_reward_account_store = store
