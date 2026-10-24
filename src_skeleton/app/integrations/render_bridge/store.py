"""Only module-owned records. No native jobs, outputs or billing writes."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time

from .client import BridgeError

TERMINAL = {"preview_ready", "registered", "plan_blocked", "rejected", "canceled",
            "failed", "expired", "blocked_scope", "blocked_revision", "protocol_error"}


class PreviewStore:
    def __init__(self, root: Path, *, max_jobs=100, max_bytes=128 * 1024 * 1024):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "integration.sqlite3"
        self.max_jobs, self.max_bytes = max_jobs, max_bytes
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS integration_jobs (
              id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
              request_key TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL,
              next_poll REAL NOT NULL, lease_until REAL NOT NULL DEFAULT 0, record TEXT NOT NULL,
              UNIQUE(owner, project, request_key));
            CREATE INDEX IF NOT EXISTS bridge_due ON integration_jobs(state,next_poll,lease_until);
            CREATE TABLE IF NOT EXISTS integration_inputs (
              job_id TEXT NOT NULL, position INTEGER NOT NULL, content BLOB NOT NULL,
              metadata TEXT NOT NULL, PRIMARY KEY(job_id,position));
            CREATE TABLE IF NOT EXISTS integration_receipts (
              job_id TEXT PRIMARY KEY, receipt_id TEXT UNIQUE NOT NULL,
              manifest TEXT NOT NULL, content BLOB NOT NULL);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=1)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _budget(self, db, additional):
        used = db.execute("SELECT COALESCE(SUM(length(content)),0) FROM integration_inputs").fetchone()[0]
        used += db.execute("SELECT COALESCE(SUM(length(content)),0) FROM integration_receipts").fetchone()[0]
        if used + additional > self.max_bytes:
            raise BridgeError("preview_storage_capacity", status=503, retryable=False)

    def create(self, record, inputs):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT digest,record FROM integration_jobs WHERE owner=? AND project=? AND request_key=?",
                             (record["owner"], record["project_id"], record["request_key"])).fetchone()
            if old:
                if old["digest"] != record["digest"]:
                    raise BridgeError("idempotency_conflict", status=409, retryable=False)
                return json.loads(old["record"])
            # Upgrade guard only for new native intents. Preserve exact legacy
            # same-key replay above; never rewrite an existing frozen identity.
            # Check and insert share the same transaction. Preview is unaffected.
            if record.get("project_binding_version") == "semantic_v2":
                for row in db.execute("SELECT state,record FROM integration_jobs WHERE owner=? AND project=?",
                                      (record["owner"], record["project_id"])):
                    previous = json.loads(row["record"])
                    outcome = previous.get("native_outcome") or {}
                    legacy_review_pending = (row["state"] == "registered" and
                        (outcome.get("review_pending") is True or
                         ("review_pending" not in outcome and outcome.get("review_status") in {"finalizing", "blocked"})))
                    if (previous.get("project_binding_version") != "semantic_v2"
                            and (row["state"] not in TERMINAL or legacy_review_pending)):
                        raise BridgeError("legacy_native_project_tasks_pending", status=409, retryable=False)
            if db.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0] >= self.max_jobs:
                raise BridgeError("preview_job_capacity", status=429, retryable=False)
            self._budget(db, sum(len(content) for content, _ in inputs))
            db.execute("INSERT INTO integration_jobs VALUES(?,?,?,?,?,?,?,0,?)",
                       (record["id"], record["owner"], record["project_id"], record["request_key"],
                        record["digest"], record["state"], 0, json.dumps(record)))
            for position, (content, metadata) in enumerate(inputs):
                db.execute("INSERT INTO integration_inputs VALUES(?,?,?,?)",
                           (record["id"], position, content, json.dumps(metadata)))
            return record

    def get(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT record FROM integration_jobs WHERE id=?", (job_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, owner, project):
        with self.connection() as db:
            rows = db.execute("SELECT record FROM integration_jobs WHERE owner=? AND project=? ORDER BY rowid DESC LIMIT 100",
                              (owner, project)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def patch(self, job_id, values, *, release=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record,lease_until FROM integration_jobs WHERE id=?", (job_id,)).fetchone()
            record = json.loads(row["record"])
            record.update(values)
            # Cancellation/reopening may expedite local work, but cannot violate
            # an upstream Retry-After deadline, including across process restarts.
            record["next_poll_at"] = max(record.get("next_poll_at", 0),
                                         record.get("retry_not_before", 0))
            # A worker cannot overwrite cancellation requested while HTTP was in flight.
            if record.get("cancel_requested") and record["state"] not in {"canceled", "blocked_scope", "blocked_revision"}:
                record["state"] = "cancel_requested"
            db.execute("UPDATE integration_jobs SET record=?,state=?,next_poll=?,lease_until=? WHERE id=?",
                       (json.dumps(record), record["state"], record.get("next_poll_at", 0),
                        0 if release else row["lease_until"], job_id))
            return record

    def compare_patch(self, job_id, expected, values):
        """Durable route/dispatch CAS independent of expiring worker leases."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM integration_jobs WHERE id=?", (job_id,)).fetchone()
            record = json.loads(row[0])
            if record.get("cancel_requested") or any(record.get(key) != value for key, value in expected.items()):
                return None
            record.update(values)
            db.execute("UPDATE integration_jobs SET record=?,state=?,next_poll=? WHERE id=?",
                       (json.dumps(record), record["state"], record.get("next_poll_at", 0), job_id))
            return record

    def routing_observation(self, key, capabilities=None, profile_id=None, now=None):
        from .routing_policy import observe_availability
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS routing_observations (key TEXT PRIMARY KEY, record TEXT NOT NULL)")
            row = db.execute("SELECT record FROM routing_observations WHERE key=?", (key,)).fetchone()
            cached = json.loads(row[0]) if row else {}
            if capabilities is not None:
                observation, supported = observe_availability(cached.get("observation"), capabilities, profile_id, now, time.monotonic())
                if supported:
                    revision = capabilities["routing_availability_v1"]["revision"]
                    if revision >= cached.get("observation", {}).get("revision", -1):
                        cached = {"observation": observation, "capabilities": capabilities}
                        db.execute("INSERT OR REPLACE INTO routing_observations VALUES (?,?)", (key, json.dumps(cached)))
                else:
                    # A server that no longer advertises support must not inherit it.
                    cached = {"observation": {}, "capabilities": capabilities}
                    db.execute("INSERT OR REPLACE INTO routing_observations VALUES (?,?)", (key, json.dumps(cached)))
            return cached

    def routing_fault(self, key):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS routing_observations (key TEXT PRIMARY KEY, record TEXT NOT NULL)")
            row = db.execute("SELECT record FROM routing_observations WHERE key=?", (key,)).fetchone()
            cached = json.loads(row[0]) if row else {}
            if cached.get("observation"):
                cached["observation"].update(health="unknown", impaired=True, healthy_since=None, healthy_since_monotonic=None, healthy_reports=0)
                db.execute("UPDATE routing_observations SET record=? WHERE key=?", (json.dumps(cached), key))
            return cached

    def health_poll(self, key, now, *, defer_until=None):
        """One bounded background refresh, with durable upstream Retry-After."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS routing_observations (key TEXT PRIMARY KEY, record TEXT NOT NULL)")
            row = db.execute("SELECT record FROM routing_observations WHERE key=?", (key,)).fetchone()
            previous = json.loads(row[0]) if row else {}
            if defer_until is not None:
                previous["retry_not_before"] = max(previous.get("retry_not_before", 0), defer_until)
            elif max(previous.get("next_poll", 0), previous.get("retry_not_before", 0)) > now:
                return False
            else:
                previous["next_poll"] = now + 5
            db.execute("INSERT OR REPLACE INTO routing_observations VALUES (?,?)", (key, json.dumps(previous)))
            return True

    def health_retry_deadline(self, key):
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS routing_observations (key TEXT PRIMARY KEY, record TEXT NOT NULL)")
            row = db.execute("SELECT record FROM routing_observations WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]).get("retry_not_before", 0) if row else 0

    def claim_due(self, limit, now=None):
        now = time.time() if now is None else now
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            marks = ",".join("?" for _ in TERMINAL)
            rows = db.execute(f"SELECT id,record FROM integration_jobs WHERE state NOT IN ({marks}) AND next_poll<=? AND lease_until<=? ORDER BY next_poll,rowid LIMIT ?",
                              (*sorted(TERMINAL), now, now, limit)).fetchall()
            for row in rows:
                db.execute("UPDATE integration_jobs SET lease_until=? WHERE id=?", (now + 300, row["id"]))
            return [json.loads(row["record"]) for row in rows]

    def inputs(self, job_id):
        with self.connection() as db:
            return [(row["content"], json.loads(row["metadata"])) for row in db.execute(
                "SELECT * FROM integration_inputs WHERE job_id=? ORDER BY position", (job_id,))]

    def save_inputs(self, job_id, inputs):
        """Append a native frozen-input snapshot; never replace original bytes."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = [(row["content"], json.loads(row["metadata"])) for row in db.execute(
                "SELECT * FROM integration_inputs WHERE job_id=? ORDER BY position", (job_id,))]
            if existing:
                if existing != inputs:
                    raise BridgeError("frozen_input_conflict", retryable=False)
                return
            self._budget(db, sum(len(content) for content, _ in inputs))
            for position, (content, metadata) in enumerate(inputs):
                db.execute("INSERT INTO integration_inputs VALUES(?,?,?,?)",
                           (job_id, position, content, json.dumps(metadata)))

    def save_receipt(self, job_id, manifest, content):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM integration_receipts WHERE job_id=?", (job_id,)).fetchone()
            if old:
                if old["receipt_id"] != manifest["receipt_id"] or old["content"] != content:
                    raise BridgeError("receipt_conflict", retryable=False)
                return
            self._budget(db, len(content))
            db.execute("INSERT INTO integration_receipts VALUES(?,?,?,?)",
                       (job_id, manifest["receipt_id"], json.dumps(manifest), content))

    def receipt(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT manifest,content FROM integration_receipts WHERE job_id=?", (job_id,)).fetchone()
            return (json.loads(row[0]), row[1]) if row else None
