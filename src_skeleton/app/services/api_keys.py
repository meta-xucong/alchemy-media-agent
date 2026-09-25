"""Revocable V3 access credentials bound to existing Veyra user IDs.

No account, password, balance, billing or generation state lives here.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone

PREFIX = "alk_v3_"
_TOKEN = re.compile(r"^alk_v3_[A-Za-z0-9_-]{43}$")
MAX_ACTIVE_KEYS = 5
LIFETIME_DAYS = 90


class KeyAccessError(ValueError):
    def __init__(self, code: str, status: int = 401):
        super().__init__(code)
        self.code, self.status = code, status


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


class ApiKeyStore:
    def __init__(self, path: Path, *, clock=time.time):
        self.path, self.clock = Path(path), clock

    @contextmanager
    def _db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            if os.name != "nt":
                self.path.chmod(0o600)
            connection.execute("""CREATE TABLE IF NOT EXISTS access_keys (
                id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL,
                digest TEXT UNIQUE NOT NULL, masked TEXT NOT NULL,
                created_at REAL NOT NULL, expires_at REAL NOT NULL,
                revoked_at REAL, revoked_by INTEGER, last_used_at REAL,
                request_count INTEGER NOT NULL DEFAULT 0)""")
            connection.execute("CREATE INDEX IF NOT EXISTS access_keys_owner ON access_keys(owner_id)")
            connection.commit()
            with connection:
                yield connection
        finally:
            connection.close()

    def _public(self, row):
        result = {k: row[k] for k in ("id", "owner_id", "name", "masked", "request_count")}
        result.update({k: _iso(row[k]) for k in ("created_at", "expires_at", "revoked_at", "last_used_at")})
        result["status"] = "revoked" if row["revoked_at"] is not None else (
            "expired" if row["expires_at"] <= self.clock() else "active")
        return result

    def create(self, owner_id: int, name: str):
        if type(owner_id) is not int or owner_id <= 0:
            raise KeyAccessError("account_required")
        if not isinstance(name, str) or len(name) > 50 or any(ord(c) < 32 for c in name):
            raise KeyAccessError("invalid_key_name", 400)
        name = name.strip() or "My API"
        now = self.clock()
        token = PREFIX + secrets.token_urlsafe(32)
        key_id = "key_" + secrets.token_hex(12)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT COUNT(*) FROM access_keys WHERE owner_id=? AND revoked_at IS NULL AND expires_at>?", (owner_id, now)).fetchone()[0]
            if active >= MAX_ACTIVE_KEYS:
                raise KeyAccessError("active_key_limit", 409)
            db.execute("INSERT INTO access_keys (id,owner_id,name,digest,masked,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
                (key_id, owner_id, name, hashlib.sha256(token.encode()).hexdigest(),
                 PREFIX + token[len(PREFIX):len(PREFIX)+4] + "..." + token[-4:], now, now + LIFETIME_DAYS*86400))
            row = db.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone()
        return {"key": self._public(row), "secret": token}

    def resolve(self, token: str):
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            raise KeyAccessError("api_key_invalid")
        with self._db() as db:
            row = db.execute("SELECT * FROM access_keys WHERE digest=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None or row["revoked_at"] is not None or row["expires_at"] <= self.clock():
            raise KeyAccessError("api_key_invalid")
        return {"id": row["id"], "owner_id": row["owner_id"]}

    def record_use(self, key_id: str):
        # Check again after the account service call; concurrent revocation wins.
        now = self.clock()
        with self._db() as db:
            result = db.execute("UPDATE access_keys SET last_used_at=?,request_count=request_count+1 WHERE id=? AND revoked_at IS NULL AND expires_at>?", (now,key_id,now))
            if result.rowcount != 1:
                raise KeyAccessError("api_key_invalid")

    def revoke(self, key_id: str, *, owner_id: int | None, actor_id: int):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone()
            if row is None or (owner_id is not None and row["owner_id"] != owner_id):
                raise KeyAccessError("key_not_found", 404)
            db.execute("UPDATE access_keys SET revoked_at=COALESCE(revoked_at,?),revoked_by=COALESCE(revoked_by,?) WHERE id=?", (self.clock(),actor_id,key_id))
            row = db.execute("SELECT * FROM access_keys WHERE id=?", (key_id,)).fetchone()
        return self._public(row)

    def list(self, *, owner_id: int | None, query: str = "", offset: int = 0, limit: int = 20):
        predicates, params = [], []
        if owner_id is not None:
            predicates.append("owner_id=?"); params.append(owner_id)
        if query:
            predicates.append("(name LIKE ? ESCAPE '\\' OR CAST(owner_id AS TEXT)=?)")
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.extend(["%"+escaped+"%",query])
        where = " WHERE " + " AND ".join(predicates) if predicates else ""
        now = self.clock()
        with self._db() as db:
            totals = db.execute("SELECT COUNT(*) total, COALESCE(SUM(CASE WHEN revoked_at IS NULL AND expires_at>? THEN 1 ELSE 0 END),0) active, COALESCE(SUM(request_count),0) requests FROM access_keys"+where, [now,*params]).fetchone()
            rows = db.execute("SELECT * FROM access_keys"+where+" ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", [*params,limit,offset]).fetchall()
        return {"items": [self._public(row) for row in rows], "total": totals["total"],
            "summary": dict(totals), "offset": offset, "limit": limit,
            "has_more": offset+len(rows)<totals["total"], "max_active_keys": MAX_ACTIVE_KEYS,
            "default_lifetime_days": LIFETIME_DAYS}
