"""Doc322 immutable, mode-scoped source authority for one V3 Job.

Selection is upstream: this module neither scans history nor invents derivatives.
Physical evidence for specialized modes remains owned by their existing contracts.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

PLAN_KEY = "reference_input_plan"
SCHEMA = "v3_reference_input_plan_v3"
MODES = {"standard": "standard_direct_reference", "professional": "professional_asset_binding", "ecommerce": "ecommerce_product_truth"}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _source(raw: Any, *, channel: str) -> dict:
    value = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else dict(raw)
    asset_id = str(value.get("asset_id") or value.get("output_id") or "").strip()
    path = Path(str(value.get("file_path") or ""))
    if not asset_id or not path.is_file():
        raise ValueError("reference_input_source_unavailable")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = value.get("content_sha256") or (value.get("metadata") or {}).get("content_sha256")
    if expected and str(expected).removeprefix("sha256:").lower() != actual:
        raise ValueError("reference_input_source_integrity_mismatch")
    value.update({"asset_id":asset_id, "file_path":str(path.resolve()), "content_sha256":actual,
        "reference_channel":channel, "provider_input_required":True,
        "selected_representation":"original_full_frame"})
    # Provenance is assigned by the binding/admission owner, not by filenames.
    if channel == "direct_reference":
        value["source_type"] = "uploaded"
        value["metadata"] = {k:v for k,v in (value.get("metadata") or {}).items()
            if k not in {"source_type", "selected_project_anchor", "auto_batch_identity_anchor", "product_truth_crop"}}
    return _copy(value)


@dataclass(frozen=True)
class ReferenceInputPlan:
    _json: str

    @classmethod
    def freeze(cls, *, job_id: str, project_id: str, mode: str, inputs: list,
               anchor_snapshot: dict | None = None, professional_binding: dict | None = None,
               ecommerce_contract: dict | None = None) -> "ReferenceInputPlan":
        if mode not in MODES or not job_id:
            raise ValueError("reference_input_mode_invalid")
        state = dict(anchor_snapshot or {"state":"none", "version":0, "auto_enabled":True})
        anchor = state.get("active_continuity_anchor")
        if state.get("state") == "invalid":
            raise ValueError("continuity_anchor_integrity_mismatch")
        if anchor is not None:
            if state.get("state") != "active" or not isinstance(anchor, dict) or not anchor.get("binding_id"):
                raise ValueError("continuity_anchor_binding_invalid")
            anchor = _copy(anchor)
            anchor["reference"] = _source(anchor["reference"], channel="continuity")
        sources = [_source(item, channel={"standard":"direct_reference", "professional":"professional_asset", "ecommerce":"product_truth"}[mode]) for item in inputs]
        # Exact duplicate records can be coalesced; conflicting identities cannot.
        unique = {}
        for item in sources:
            key = item["asset_id"]
            if key in unique and unique[key] != item:
                raise ValueError("reference_input_source_ambiguous")
            unique[key] = item
        sources = list(unique.values())
        professional = None
        commerce = None
        if mode == "professional":
            if not professional_binding or professional_binding.get("state") != "valid":
                raise ValueError("reference_input_professional_binding_missing")
            professional = {"binding":_copy(professional_binding), "references":sources}
        elif mode == "ecommerce":
            if sources and not ecommerce_contract:
                raise ValueError("reference_input_product_contract_missing")
            contract = _copy(ecommerce_contract or {})
            identity_ids = contract.get("locked_identity_asset_ids", [])
            if not isinstance(identity_ids, list) or any(not isinstance(value, str) for value in identity_ids):
                raise ValueError("reference_input_product_contract_invalid")
            identity_sources = [source for source in sources if source["asset_id"] in identity_ids]
            product_sources = [source for source in sources if source["asset_id"] not in identity_ids]
            for source in identity_sources:
                source["reference_channel"] = "ecommerce_identity"
            commerce = {"contract":contract, "references":product_sources, "identity_references":identity_sources}
        refs = ([anchor["reference"]] if anchor else []) + sources
        payload = {"schema_version":SCHEMA, "job_id":job_id, "project_id":project_id,
            "project_mode":mode, "reference_mode":MODES[mode], "continuity_anchor":anchor,
            "anchor_version":state.get("version",0), "anchor_auto_enabled":state.get("auto_enabled") is True,
            "direct_references":sources if mode == "standard" else [],
            "professional_binding_set":professional, "ecommerce_product_truth":commerce,
            "derived_evidence":[], "selection_policy":"mode_scoped_inputs_plus_single_continuity_anchor",
            "logical_continuity_reference_count":int(anchor is not None), "logical_mode_input_count":len(sources),
            "physical_provider_reference_count":len({r["content_sha256"] for r in refs}) if mode == "standard" else None,
            "physical_count_state":"frozen" if mode == "standard" else "pending_specialized_materialization"}
        payload["plan_digest"] = digest(payload)
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, raw: dict, *, job_id: str | None = None, project_id: str | None = None) -> "ReferenceInputPlan":
        if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA:
            raise ValueError("reference_input_plan_invalid")
        payload = _copy(raw)
        proof = payload.pop("plan_digest", None)
        if proof != digest(payload):
            raise ValueError("reference_input_plan_digest_mismatch")
        payload["plan_digest"] = proof
        mode = payload.get("project_mode")
        if mode not in MODES or payload.get("reference_mode") != MODES[mode]:
            raise ValueError("reference_input_mode_invalid")
        if (job_id and payload.get("job_id") != job_id) or (project_id is not None and payload.get("project_id") != project_id):
            raise ValueError("reference_input_plan_binding_mismatch")
        direct, professional, commerce = (payload.get(k) for k in ("direct_references", "professional_binding_set", "ecommerce_product_truth"))
        if not isinstance(direct, list) or (mode == "standard" and (professional is not None or commerce is not None)) or (mode == "professional" and (direct or commerce is not None or not isinstance(professional, dict))) or (mode == "ecommerce" and (direct or professional is not None or not isinstance(commerce, dict))):
            raise ValueError("reference_input_mode_leak")
        anchor = payload.get("continuity_anchor")
        if anchor is not None and (not isinstance(anchor, dict) or not anchor.get("binding_id") or not isinstance(anchor.get("reference"), dict)):
            raise ValueError("reference_input_anchor_invalid")
        sources = direct if mode == "standard" else payload[{"professional":"professional_binding_set", "ecommerce":"ecommerce_product_truth"}[mode]].get("references")
        if not isinstance(sources, list) or type(payload.get("anchor_version")) is not int or payload["anchor_version"] < 0 or type(payload.get("anchor_auto_enabled")) is not bool:
            raise ValueError("reference_input_plan_invalid")
        expected_channel = {"standard": "direct_reference", "professional": "professional_asset", "ecommerce": "product_truth"}[mode]
        if any(not isinstance(source, dict) or source.get("reference_channel") != expected_channel
               or source.get("provider_input_required") is not True for source in sources):
            raise ValueError("reference_input_plan_source_invalid")
        if mode == "ecommerce":
            identity_sources = commerce.get("identity_references", [])
            if not isinstance(identity_sources, list) or any(
                not isinstance(source, dict) or source.get("reference_channel") != "ecommerce_identity"
                or source.get("provider_input_required") is not True for source in identity_sources
            ):
                raise ValueError("reference_input_plan_source_invalid")
            contract = commerce.get("contract")
            if not isinstance(contract, dict):
                raise ValueError("reference_input_product_contract_invalid")
            if identity_sources and (
                not isinstance(contract.get("locked_identity_binding"), dict)
                or contract["locked_identity_binding"].get("state") != "valid"
                or [source.get("asset_id") for source in identity_sources] != contract.get("locked_identity_asset_ids")
            ):
                raise ValueError("reference_input_professional_binding_missing")
            sources = [*sources, *identity_sources]
        if mode == "standard" and any(source.get("source_type") != "uploaded" for source in sources):
            raise ValueError("reference_input_plan_source_invalid")
        if any(not isinstance(source.get("asset_id"), str) or not source["asset_id"] for source in sources):
            raise ValueError("reference_input_plan_source_invalid")
        if len({source.get("asset_id") for source in sources}) != len(sources):
            raise ValueError("reference_input_plan_source_ambiguous")
        if mode == "professional" and (professional.get("binding") or {}).get("state") != "valid":
            raise ValueError("reference_input_professional_binding_missing")
        if anchor and (anchor["reference"].get("reference_channel") != "continuity"
                       or anchor["reference"].get("provider_input_required") is not True
                       or anchor.get("output_id") != anchor["reference"].get("output_id")):
            raise ValueError("reference_input_anchor_invalid")
        all_sources = ([anchor["reference"]] if anchor else []) + sources
        for source in all_sources:
            if not isinstance(source,dict) or not isinstance(source.get("asset_id"),str) or not source["asset_id"] or not isinstance(source.get("file_path"),str):
                raise ValueError("reference_input_plan_source_invalid")
            sha=source.get("content_sha256")
            if not isinstance(sha,str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("reference_input_plan_source_invalid")
        if type(payload.get("logical_continuity_reference_count")) is not int or payload["logical_continuity_reference_count"] != int(anchor is not None) or type(payload.get("logical_mode_input_count")) is not int or payload["logical_mode_input_count"] != len(sources):
            raise ValueError("reference_input_plan_count_invalid")
        if payload.get("derived_evidence") != []:
            raise ValueError("reference_input_plan_unapproved_representation")
        if mode == "standard":
            if type(payload.get("physical_provider_reference_count")) is not int or payload["physical_provider_reference_count"] != len({r["content_sha256"] for r in all_sources}) or payload.get("physical_count_state") != "frozen":
                raise ValueError("reference_input_plan_count_invalid")
            if any(r.get("selected_representation") != "original_full_frame" for r in all_sources):
                raise ValueError("reference_input_plan_unapproved_representation")
        elif payload.get("physical_provider_reference_count") is not None or payload.get("physical_count_state") != "pending_specialized_materialization":
            raise ValueError("reference_input_plan_count_invalid")
        return cls(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    def as_dict(self) -> dict:
        return json.loads(self._json)

    def references(self, *, verify_bytes: bool = True) -> list[dict]:
        p = self.as_dict()
        mode = p["project_mode"]
        sources = p["direct_references"] if mode == "standard" else p[{"professional":"professional_binding_set", "ecommerce":"ecommerce_product_truth"}[mode]]["references"]
        if mode == "ecommerce":
            sources = [*sources, *p["ecommerce_product_truth"].get("identity_references", [])]
        result = ([p["continuity_anchor"]["reference"]] if p["continuity_anchor"] else []) + sources
        for item in result:
            if verify_bytes:
                try:
                    actual = hashlib.sha256(Path(item["file_path"]).read_bytes()).hexdigest()
                except (OSError, KeyError) as exc:
                    raise ValueError("reference_input_source_unavailable") from exc
                if actual != item.get("content_sha256"):
                    raise ValueError("reference_input_source_integrity_mismatch")
        return result

    def facts(self) -> dict:
        p = self.as_dict()
        return {"has_explicit_continuity_anchor":p["continuity_anchor"] is not None,
            "has_direct_reference_inputs":bool(p["direct_references"]),
            "has_professional_binding":p["professional_binding_set"] is not None or bool(p["ecommerce_product_truth"] and p["ecommerce_product_truth"].get("identity_references")),
            "has_ecommerce_product_truth":bool(p["ecommerce_product_truth"] and p["ecommerce_product_truth"]["references"]),
            **{k:p[k] for k in ("reference_mode","project_mode","logical_continuity_reference_count","logical_mode_input_count","physical_provider_reference_count","physical_count_state")}}


def plan_from_metadata(metadata: dict, *, job_id: str | None = None) -> ReferenceInputPlan | None:
    if PLAN_KEY not in metadata:
        return None  # Retained pre-Doc322 jobs keep their frozen historical contract.
    return ReferenceInputPlan.from_dict(metadata[PLAN_KEY], job_id=job_id,
        project_id=str(metadata["project_id"] or "") if "project_id" in metadata else None)
