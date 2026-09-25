"""One versioned continuity anchor in the existing project's private history."""
from __future__ import annotations
from typing import Callable
from uuid import uuid4
from datetime import datetime, timezone
from ..reference_input_plan import digest

NAMESPACE = "doc322_continuity_anchor_bindings_v1"


class ContinuityAnchorConflict(ValueError):
    code = "continuity_anchor_conflict"
    v3_status_code = 409

    def __init__(self):
        super().__init__(self.code)


class ContinuityAnchorBindingService:
    def __init__(self, store, resolve_output: Callable[[str, str, str | None], dict]):
        self.store, self.resolve_output = store, resolve_output

    def state(self, project_id: str, *, verify_source: bool = True) -> dict:
        records = self.store.list_private_records(project_id, NAMESPACE)
        current = {"project_id":project_id, "version":0, "state":"none", "auto_enabled":True, "active_continuity_anchor":None}
        previous = ""
        for version, event in enumerate(records,1):
            payload = {k:v for k,v in event.items() if k != "identity_digest"}
            if event.get("identity_digest") != digest(payload) or event.get("previous_digest") != previous or event.get("version") != version or event.get("project_id") != project_id:
                raise ValueError("continuity_anchor_history_invalid")
            if (event.get("schema_version") != "v3_continuity_anchor_binding_v1"
                or type(event.get("version")) is not int or type(event.get("auto_enabled")) is not bool
                or event.get("state") not in {"none", "active", "unbound"}
                or (event.get("state") == "active") != isinstance(event.get("active_continuity_anchor"), dict)
                or (event.get("state") != "none" and event.get("auto_enabled") is not False)):
                raise ValueError("continuity_anchor_history_invalid")
            current = dict(event)
            previous = event["identity_digest"]
        anchor = current.get("active_continuity_anchor")
        if anchor and verify_source:
            try:
                resolved = self.resolve_output(project_id, anchor["output_id"], anchor["source_job_id"])
                if resolved["content_sha256"] != anchor["source_content_sha256"]:
                    raise ValueError("continuity_anchor_integrity_mismatch")
            except (ValueError, KeyError, OSError):
                return {**current, "state":"invalid", "auto_enabled":False, "active_continuity_anchor":None}
        return current

    def change(self, project_id: str, *, output_id: str | None, expected_version: int,
               expected_job_id: str | None = None, mode: str = "manual", migration: bool = False) -> dict:
        if type(expected_version) is not int or expected_version < 0 or mode not in {"manual","auto_first_formal"}:
            raise ValueError("continuity_anchor_request_invalid")
        current = self.state(project_id, verify_source=False)
        if current["version"] != expected_version:
            raise ContinuityAnchorConflict()
        if mode == "auto_first_formal" and (current["state"] != "none" or current.get("auto_enabled") is not True):
            raise ContinuityAnchorConflict()
        anchor = None
        if output_id is not None:
            reference = self.resolve_output(project_id, output_id, expected_job_id)
            anchor = {"binding_id":"anchor_binding_"+uuid4().hex, "output_id":output_id,
                "source_job_id":reference["job_id"], "source_candidate_id":reference["candidate_id"],
                "source_asset_id":reference.get("source_asset_id") or reference["asset_id"],
                "source_content_sha256":reference["content_sha256"], "binding_mode":mode,
                "state":"active", "reference":reference}
        event = {"schema_version":"v3_continuity_anchor_binding_v1", "project_id":project_id,
            "version":expected_version+1, "previous_digest":current.get("identity_digest", ""),
            "state":"active" if anchor else "unbound", "auto_enabled":False,
            "active_continuity_anchor":anchor, "binding_mode":mode, "migration":migration,
            "supersedes_binding_id":(current.get("active_continuity_anchor") or {}).get("binding_id"),
            "created_at":datetime.now(timezone.utc).isoformat()}
        event["identity_digest"] = digest(event)
        try:
            self.store.compare_and_append_private_record(project_id, NAMESPACE, event, expected_version=expected_version)
        except ValueError as exc:
            if str(exc) == "continuity_anchor_conflict":
                raise ContinuityAnchorConflict() from exc
            raise
        return self.state(project_id)

    def finish_empty_migration(self, project_id: str, *, blocked: bool = False) -> dict:
        event = {"schema_version":"v3_continuity_anchor_binding_v1", "project_id":project_id,
            "version":1, "previous_digest":"", "state":"unbound" if blocked else "none",
            "auto_enabled":not blocked, "active_continuity_anchor":None, "migration":True,
            "created_at":datetime.now(timezone.utc).isoformat()}
        event["identity_digest"] = digest(event)
        self.store.compare_and_append_private_record(project_id,NAMESPACE,event,expected_version=0)
        return self.state(project_id)

    @staticmethod
    def public(state: dict) -> dict:
        anchor = state.get("active_continuity_anchor") if state.get("state") == "active" else None
        return {"project_id":state["project_id"], "version":state["version"], "state":state["state"],
            "auto_enabled":state.get("auto_enabled") is True,
            "active_continuity_anchor":({"binding_id":anchor["binding_id"], "output_id":anchor["output_id"],
                "source_job_id":anchor["source_job_id"], "binding_mode":anchor["binding_mode"], "state":"active",
                "preview_url":f"/api/v3/creative-agent/outputs/{anchor['output_id']}/preview"} if anchor else None)}
