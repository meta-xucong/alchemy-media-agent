"""Thin framework-neutral route handler facade for V3 API adapters."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..app_shell import get_scenario_hub_contract
from ..project_mode import InMemoryProjectStore, ProjectTemplateRegistry, V3ProjectModeService
from ..visual_assets import (
    AnchorPackPreparationHost,
    LibraryVisualAssetCreateRequest,
    PeopleAssetLifecycleService,
    ProjectVisualAssetBindingRequest,
    ProjectVisualAssetBindingService,
    VisualAssetLibraryCatalog,
    VisualAssetLibraryLifecycleService,
)
from ..visual_assets.character_card import CharacterCardStageHost
from ..visual_assets.character_card import BodySilhouettePublicRequest
from .service import V3ProductApiService


class V3ProductRouteHandlers:
    """Method names mirror the reserved V3 route contract."""

    def __init__(
        self,
        service: V3ProductApiService | None = None,
        project_store: InMemoryProjectStore | None = None,
        template_registry: ProjectTemplateRegistry | None = None,
        anchor_pack_preparation_host: AnchorPackPreparationHost | None = None,
        character_card_stage_host: CharacterCardStageHost | None = None,
        visual_asset_library_catalog: VisualAssetLibraryCatalog | None = None,
        project_visual_asset_binding_service: ProjectVisualAssetBindingService | None = None,
        visual_asset_owner_scope: str = "local_default",
    ) -> None:
        self.service = service or V3ProductApiService()
        self.visual_asset_owner_scope = visual_asset_owner_scope.strip() or "local_default"
        self.visual_asset_library_catalog = visual_asset_library_catalog or VisualAssetLibraryCatalog()
        self.project_visual_asset_binding_service = (
            project_visual_asset_binding_service
            or ProjectVisualAssetBindingService(self.visual_asset_library_catalog)
        )
        self.project_service = V3ProjectModeService(
            product_service=self.service,
            project_store=project_store,
            template_registry=template_registry,
            project_visual_asset_binding_service=self.project_visual_asset_binding_service,
        )
        self.people_asset_service = PeopleAssetLifecycleService(
            self.service.visual_asset_catalog,
            root_source_resolver=self.service.asset_store.get_upload,
            anchor_pack_host=anchor_pack_preparation_host,
        )
        self.visual_asset_library_service = VisualAssetLibraryLifecycleService(
            self.visual_asset_library_catalog,
            root_source_resolver=self.service.asset_store.get_upload,
            anchor_pack_host=anchor_pack_preparation_host,
            character_card_stage_host=character_card_stage_host,
        )

    def post_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_job(payload).model_dump(mode="json")

    def post_creative_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post_jobs(payload)

    def post_uploads(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_uploaded_asset(payload).model_dump(mode="json")

    def put_upload_content(self, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.service.store_uploaded_asset_content(asset_id, payload)
        if record is None:
            raise KeyError("uploaded asset not found")
        return record.model_dump(mode="json")

    def post_upload_complete(self, asset_id: str) -> dict[str, Any]:
        record = self.service.complete_uploaded_asset(asset_id)
        if record is None:
            raise KeyError("uploaded asset not found")
        return record.model_dump(mode="json")

    def get_upload(self, asset_id: str) -> dict[str, Any]:
        record = self.service.get_uploaded_asset(asset_id)
        if record is None:
            raise KeyError("uploaded asset not found")
        return record.model_dump(mode="json")

    def get_scenarios(self) -> dict[str, Any]:
        return get_scenario_hub_contract()

    def get_photographer_profiles(self) -> dict[str, Any]:
        return self.service.get_photographer_profiles()

    def get_history(self, limit: int = 20) -> dict[str, Any]:
        return self.service.list_history(limit=limit).model_dump(mode="json")

    def get_projects(self, limit: int = 20, owner_user_id: int | None = None) -> dict[str, Any]:
        return self.project_service.list_projects(limit=limit, owner_user_id=owner_user_id).model_dump(mode="json")

    def get_project_outputs(
        self,
        limit: int = 60,
        owner_user_id: int | None = None,
        compact: bool = False,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        return self.project_service.list_project_outputs(
            limit=limit,
            owner_user_id=owner_user_id,
            compact=compact,
            project_id=project_id,
        )

    def post_projects(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.create_project(payload).model_dump(mode="json")

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.project_service.get_project(project_id).model_dump(mode="json")

    def post_project_archive(self, project_id: str) -> dict[str, Any]:
        return self.project_service.archive_project(project_id).model_dump(mode="json")

    def delete_project(self, project_id: str) -> dict[str, Any]:
        return self.project_service.delete_project(project_id)

    def get_project_timeline(self, project_id: str) -> dict[str, Any]:
        return self.project_service.list_timeline(project_id).model_dump(mode="json")

    def get_project_context(self, project_id: str) -> dict[str, Any]:
        return self.project_service.get_project_context(project_id).model_dump(mode="json")

    # Doc173 library-first public surface.  These methods deliberately do not
    # call the historical project-scoped People Asset lifecycle above.  Legacy
    # routes stay available for read/recovery only while new assets are owned
    # by the user/workspace library and projects only hold explicit bindings.
    def get_visual_assets(self, owner_scope: str | None = None) -> dict[str, Any]:
        resolved_owner_scope = self._visual_asset_owner_scope(owner_scope)
        return {
            "visual_assets": [
                self._visual_asset_public_record(item)
                for item in self.visual_asset_library_service.list(owner_scope=resolved_owner_scope)
            ]
        }

    def post_visual_assets(self, payload: dict[str, Any], owner_scope: str | None = None) -> dict[str, Any]:
        request = LibraryVisualAssetCreateRequest.model_validate(payload)
        asset = self.visual_asset_library_service.create_draft(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            request=request,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def get_visual_asset(self, visual_asset_id: str, owner_scope: str | None = None) -> dict[str, Any]:
        asset = self.visual_asset_library_service.get(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_prepare(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        if payload:
            raise ValueError("visual_asset_prepare_payload_must_be_empty")
        asset = self.visual_asset_library_service.prepare(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_activate(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        version_id = str(payload.get("version_id") or "").strip()
        confirmed = payload.get("confirm_activation") is True
        if not version_id:
            raise ValueError("visual_asset_version_required")
        asset = self.visual_asset_library_service.activate(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
            version_id=version_id,
            confirm_activation=confirmed,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_character_card_prepare(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        """Prepare one explicit Character Card stage; details stay server-owned."""

        stage = payload.get("stage")
        if stage not in {
            "face_identity",
            "expression_set",
            "body_silhouette",
        }:
            raise ValueError("character_card_stage_required")
        resume = payload.get("resume", False)
        if not isinstance(resume, bool):
            raise ValueError("character_card_resume_flag_invalid")
        generation_channel = payload.get("generation_channel", "provider")
        if generation_channel not in {"provider", "mcp"}:
            raise ValueError("character_card_generation_channel_invalid")
        body_request = None
        expression = None
        if stage == "body_silhouette":
            allowed = {
                "stage",
                "resume",
                "generation_channel",
                "source_class",
                "body_reference_asset_id",
                "body_facts",
            }
            if not set(payload).issubset(allowed):
                raise ValueError("character_card_body_payload_invalid")
            body_request = BodySilhouettePublicRequest.model_validate(
                {key: value for key, value in payload.items() if key not in {"stage", "resume", "generation_channel"}}
            )
        elif stage == "expression_set" and "expression" in payload:
            if set(payload) - {"stage", "resume", "generation_channel", "expression"}:
                raise ValueError("character_card_stage_payload_invalid")
            expression = payload.get("expression")
            if expression != "smile":
                raise ValueError("character_card_expression_slot_not_explicitly_supported")
        elif set(payload) - {"stage", "resume", "generation_channel"}:
            # Expression intent remains Brain/host-owned.  A browser may not
            # inject a local expression dictionary or prompt fragment.
            raise ValueError("character_card_stage_payload_invalid")
        if stage == "face_identity":
            asset = self.visual_asset_library_service.prepare_character_card_face(
                owner_scope=self._visual_asset_owner_scope(owner_scope),
                visual_asset_id=visual_asset_id,
                resume=resume,
                generation_channel=generation_channel,
            )
        else:
            asset = self.visual_asset_library_service.prepare_character_card_stage(
                owner_scope=self._visual_asset_owner_scope(owner_scope),
                visual_asset_id=visual_asset_id,
                stage=stage,
                expression=expression,
                body_request=body_request,
                generation_channel=generation_channel,
            )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_character_card_activate(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        if set(payload) != {"module", "confirm_activation"}:
            raise ValueError("character_card_module_activation_payload_invalid")
        module = payload.get("module")
        if module not in {"face_identity", "expression_set", "body_silhouette"}:
            raise ValueError("character_card_module_required")
        owner = self._visual_asset_owner_scope(owner_scope)
        if module == "face_identity":
            asset = self.visual_asset_library_service.activate_character_card_face(
                owner_scope=owner,
                visual_asset_id=visual_asset_id,
                confirm_activation=payload.get("confirm_activation") is True,
            )
        else:
            asset = self.visual_asset_library_service.activate_character_card_module(
                owner_scope=owner,
                visual_asset_id=visual_asset_id,
                module=module,
                confirm_activation=payload.get("confirm_activation") is True,
            )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_archive(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        if payload.get("confirm_archive") is not True:
            raise ValueError("visual_asset_archive_confirmation_required")
        asset = self.visual_asset_library_service.archive(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def get_project_visual_asset_bindings(self, project_id: str) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        binding_set = self.project_visual_asset_binding_service.current(project_id=project_id)
        return self._project_visual_asset_binding_public_record(binding_set)

    def post_project_visual_asset_binding(
        self,
        project_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        request = ProjectVisualAssetBindingRequest.model_validate(payload)
        self.project_visual_asset_binding_service.bind(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            project_id=project_id,
            request=request,
        )
        return self.get_project_visual_asset_bindings(project_id)

    def delete_project_visual_asset_binding(
        self,
        project_id: str,
        binding_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        self.project_visual_asset_binding_service.remove(
            project_id=project_id,
            binding_id=binding_id,
            confirm_removal=payload.get("confirm_removal") is True,
        )
        return self.get_project_visual_asset_bindings(project_id)

    def _visual_asset_owner_scope(self, supplied_owner_scope: str | None) -> str:
        value = str(supplied_owner_scope or self.visual_asset_owner_scope).strip()
        return value or "local_default"

    @staticmethod
    def _visual_asset_public_record(asset: Any) -> dict[str, Any]:
        """Safe browser projection: no source IDs, prompt or review internals."""

        def _character_card_slot_public(slot: Any) -> dict[str, Any]:
            state = str(getattr(slot, "state", "empty") or "empty")
            output_id = str(getattr(slot, "output_id", "") or "").strip()
            public = {
                "state": state,
                "available": state in {"winner_selected", "active"},
            }
            # Media URLs are safe, server-owned projections.  They expose no
            # prompt, provider, source path or review body.
            # Empty/preparing/blocked/stale slots deliberately remain empty.
            if output_id and public["available"]:
                encoded = quote(output_id, safe="")
                public.update(
                    {
                        "preview_url": f"/api/v3/creative-agent/outputs/{encoded}/preview",
                        "download_url": f"/api/v3/creative-agent/outputs/{encoded}/download",
                    }
                )
            return public

        def _anchor_candidate_history_public(candidate: Any) -> dict[str, Any]:
            output_id = str(getattr(candidate, "output_id", "") or "").strip()
            public = {
                "stage": str(getattr(candidate, "stage", "") or ""),
                "view_role": str(getattr(candidate, "view_role", "") or ""),
                "candidate_index": int(getattr(candidate, "candidate_index", 0) or 0),
                "failure_code": str(getattr(candidate, "failure_code", "") or ""),
            }
            candidate_id = str(getattr(candidate, "candidate_id", "") or "").strip()
            handoff_id = str(getattr(candidate, "mcp_handoff_id", "") or "").strip()
            if output_id:
                encoded = quote(output_id, safe="")
                public.update(
                    {
                        "output_id": output_id,
                        "preview_url": f"/api/v3/creative-agent/outputs/{encoded}/preview",
                        "download_url": f"/api/v3/creative-agent/outputs/{encoded}/download",
                    }
                )
            if candidate_id:
                public["candidate_id"] = candidate_id
            if handoff_id:
                public["mcp_handoff_id"] = handoff_id
            return public

        def _preparation_public(version: Any, *, include_resume: bool = False) -> dict[str, Any]:
            pack = getattr(version, "anchor_pack", None)
            public = {
                "status": version.lifecycle_status,
                "version_id": version.version_id,
                "user_activation_confirmed": version.activation_confirmed,
                "anchor_views": [
                    {
                        "view_role": view.view_role,
                        "active": bool(view.active),
                    }
                    for view in getattr(pack, "anchor_views", [])
                ],
            }
            candidate_history = [
                _anchor_candidate_history_public(item)
                for item in getattr(pack, "candidate_failures", [])
            ]
            if candidate_history:
                public["candidate_history"] = candidate_history
            generation_channel = str(getattr(version, "generation_channel", "") or "")
            handoff_ids = list(getattr(version, "mcp_handoff_ids", []) or [])
            if generation_channel == "mcp":
                public["generation_channel"] = generation_channel
            if handoff_ids:
                public["mcp_handoff_ids"] = handoff_ids
            failure_attempt_count = int(getattr(version, "failure_attempt_count", 0) or 0)
            if failure_attempt_count:
                public["failure_attempt_count"] = failure_attempt_count
            failure_code = str(getattr(version, "failure_code", "") or "").strip()
            if failure_code:
                public["failure_code"] = failure_code
            if include_resume:
                resume_available = bool(
                    getattr(pack, "status", "") == "failed"
                    and getattr(asset, "character_card", None) is not None
                    and getattr(asset.character_card, "resume_available", False)
                )
                if failure_attempt_count or resume_available:
                    public["failure_attempt_count"] = failure_attempt_count
                    public["resume_available"] = resume_available
            return public

        active_version = asset.active_version()
        latest_version = asset.versions[-1] if asset.versions else None
        latest_preparation = None
        if latest_version is not None:
            latest_preparation = _preparation_public(latest_version, include_resume=True)
        preparation_history = [
            _preparation_public(version)
            for version in getattr(asset, "versions", [])
            if getattr(version, "anchor_pack", None) is not None
        ]
        card = getattr(asset, "character_card", None)
        card_public = None
        if card is not None:
            card_public = {
                "face_identity_status": card.face_identity_status,
                "expression_set_status": card.expression_set_status,
                "body_silhouette_status": card.body_silhouette_status,
                "face_identity_base_active": card.face_identity_base_active,
                "face_identity_complete": card.face_identity_complete,
                "resume_available": bool(card.resume_available),
                "last_failed_module": card.last_failed_module,
                "last_failed_slot_key": card.last_failed_slot_key,
                "last_failure_code": card.last_failure_code,
                "last_failure_attempt_count": card.last_failure_attempt_count,
                "slots": {
                    **{
                        key: _character_card_slot_public(slot)
                        for key, slot in card.face_slots.items()
                    },
                    **{
                        key: _character_card_slot_public(slot)
                        for key, slot in card.expression_slots.items()
                    },
                    **{
                        key: _character_card_slot_public(slot)
                        for key, slot in card.body_slots.items()
                    },
                },
            }
            pending_mcp_handoff_ids = list(getattr(card, "pending_mcp_handoff_ids", []) or [])
            if pending_mcp_handoff_ids:
                card_public["pending_mcp_handoff_ids"] = pending_mcp_handoff_ids
        return {
            "visual_asset_id": asset.visual_asset_id,
            "display_name": asset.display_name,
            "asset_type": asset.asset_type,
            "lifecycle_status": asset.lifecycle_status,
            "active_version_id": asset.active_version_id,
            "available_for_projects": bool(active_version and asset.lifecycle_status == "active"),
            "latest_preparation": latest_preparation,
            "preparation_history": preparation_history,
            "character_card": card_public,
        }

    @staticmethod
    def _project_visual_asset_binding_public_record(binding_set: Any) -> dict[str, Any]:
        return {
            "project_id": binding_set.project_id,
            "state": binding_set.state,
            "bindings": [
                {
                    "binding_id": item.binding_id,
                    "visual_asset_id": item.visual_asset_id,
                    "selected_version_id": item.selected_version_id,
                    "asset_type": item.asset_type,
                    "status": item.status,
                }
                for item in binding_set.bindings
            ],
        }

    def get_project_people_assets(self, project_id: str) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        return {
            "project_id": project_id,
            "people_assets": [self._people_asset_public_record(project_id, item) for item in self.people_asset_service.list(project_id)],
        }

    def post_project_people_asset(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        raise ValueError("legacy_project_people_asset_forward_write_forbidden")

    def get_project_people_asset(self, project_id: str, people_asset_id: str) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        asset = self.people_asset_service.get(project_id, people_asset_id)
        return {"people_asset": self._people_asset_public_record(project_id, asset)}

    def _people_asset_public_record(self, project_id: str, asset: Any) -> dict[str, Any]:
        """Expose only lifecycle truth needed to restore the Professional UI.

        The browser must be able to recover a pending review after refresh, but
        it must not receive prompts, candidate payloads, provider details or
        raw pixel evidence. Pack history is projected to view/status facts only.
        """

        record = asset.model_dump(mode="json")
        latest = None
        try:
            history = self.people_asset_service.catalog.list_pack_history(project_id, asset.people_asset_id)
            if history:
                snapshot = history[-1].pack_snapshot
                latest = {
                    "status": snapshot.status,
                    "pack_version_id": snapshot.pack_version_id,
                    "user_activation_confirmed": snapshot.user_activation_confirmed,
                    "anchor_views": [
                        {"view_role": view.view_role, "active": view.active}
                        for view in snapshot.anchor_views
                    ],
                }
        except (AttributeError, KeyError, IndexError):
            latest = None
        if latest is not None:
            record["latest_preparation"] = latest
        card = getattr(asset, "character_card", None)
        if card is not None:
            record["character_card"] = {
                "face_identity_status": card.face_identity_status,
                "expression_set_status": card.expression_set_status,
                "body_silhouette_status": card.body_silhouette_status,
                "slots": {
                    key: {"state": slot.state, "available": slot.state == "active"}
                    for key, slot in {
                        **card.face_slots,
                        **card.expression_slots,
                        **card.body_slots,
                    }.items()
                },
            }
            pending_mcp_handoff_ids = list(getattr(card, "pending_mcp_handoff_ids", []) or [])
            if pending_mcp_handoff_ids:
                record["character_card"]["pending_mcp_handoff_ids"] = pending_mcp_handoff_ids
        return record

    def post_project_people_asset_prepare(
        self,
        project_id: str,
        people_asset_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        raise ValueError("legacy_project_people_asset_forward_write_forbidden")

    def post_project_people_asset_activate(
        self,
        project_id: str,
        people_asset_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        raise ValueError("legacy_project_people_asset_forward_write_forbidden")

    def post_project_reference(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.add_project_reference(project_id, payload).model_dump(mode="json")

    def patch_project_reference(self, project_id: str, reference_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.update_project_reference(project_id, reference_id, payload).model_dump(mode="json")

    def post_project_reference_remove(self, project_id: str, reference_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.remove_project_reference(project_id, reference_id, payload or {}).model_dump(mode="json")

    def post_project_feedback(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.add_project_feedback(project_id, payload).model_dump(mode="json")

    def post_project_brand_memory_proposal(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.create_brand_memory_proposal(project_id, payload).model_dump(mode="json")

    def post_project_brand_memory_confirm(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.confirm_brand_memory_proposal(project_id, payload).model_dump(mode="json")

    def post_project_output_unselect(self, project_id: str, output_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.unselect_project_output(project_id, output_id, payload or {})

    def post_project_output_reject(self, project_id: str, output_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.reject_project_output(project_id, output_id, payload)

    def post_project_job(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.create_project_job(project_id, payload).model_dump(mode="json")

    def post_project_ecommerce_slot_continuation(
        self,
        project_id: str,
        parent_job_id: str,
        slot_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.project_service.create_ecommerce_slot_continuation(
            project_id,
            parent_job_id,
            slot_id,
            payload,
        ).model_dump(mode="json")

    def get_project_ecommerce_slot_delivery(
        self,
        project_id: str,
        root_job_id: str,
        slot_id: str,
    ) -> dict[str, Any]:
        return self.project_service.get_ecommerce_slot_delivery(
            project_id,
            root_job_id,
            slot_id,
        ).model_dump(mode="json")

    def post_project_photography_role_continuation(
        self,
        project_id: str,
        parent_job_id: str,
        role_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.project_service.create_photography_role_continuation(
            project_id,
            parent_job_id,
            role_id,
            payload,
        ).model_dump(mode="json")

    def get_project_photography_role_delivery(
        self,
        project_id: str,
        root_job_id: str,
        role_id: str,
    ) -> dict[str, Any]:
        return self.project_service.get_photography_role_delivery(
            project_id,
            root_job_id,
            role_id,
        ).model_dump(mode="json")

    def post_project_job_generate(self, project_id: str, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.generate_project_job(project_id, job_id, payload or {}).model_dump(mode="json")

    def mark_project_job_generating(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str | None = None,
        background_timeout_seconds: float | None = None,
        background_runtime_id: str | None = None,
    ) -> dict[str, Any]:
        return self.project_service.mark_project_job_generating(
            project_id,
            job_id,
            background_attempt_id=background_attempt_id,
            background_timeout_seconds=background_timeout_seconds,
            background_runtime_id=background_runtime_id,
        ).model_dump(mode="json")

    def mark_project_job_generation_timed_out(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        return self.project_service.mark_project_job_generation_timed_out(
            project_id,
            job_id,
            background_attempt_id=background_attempt_id,
            timeout_seconds=timeout_seconds,
        ).model_dump(mode="json")

    def mark_project_job_generation_worker_failed(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str,
        failure_code: str,
    ) -> dict[str, Any]:
        return self.project_service.mark_project_job_generation_worker_failed(
            project_id,
            job_id,
            background_attempt_id=background_attempt_id,
            failure_code=failure_code,
        ).model_dump(mode="json")

    def post_project_job_select(self, project_id: str, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.select_project_job(project_id, job_id, payload or {})

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self.service.get_job(job_id).model_dump(mode="json")

    def get_mcp_materialization(self, handoff_id: str) -> dict[str, Any]:
        return self.service.mcp_materialization_store.public_view(handoff_id)

    def post_mcp_materialization_submit(self, handoff_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {"nonce", "prompt_sha256", "reference_asset_hashes", "artifact_base64", "artifact_path"}
        if set(payload) - allowed:
            raise ValueError("mcp_materialization_submit_payload_invalid")
        if not isinstance(payload.get("reference_asset_hashes"), list):
            raise ValueError("mcp_materialization_reference_hashes_required")
        artifact_base64 = payload.get("artifact_base64")
        artifact_path = payload.get("artifact_path")
        if bool(artifact_base64) == bool(artifact_path):
            raise ValueError("mcp_materialization_single_artifact_required")
        if artifact_path:
            path = Path(str(artifact_path))
            if not path.is_file():
                raise ValueError("mcp_materialization_artifact_path_unavailable")
            content = path.read_bytes()
        else:
            try:
                raw = str(artifact_base64 or "")
                if raw.startswith("data:image/") and "," in raw:
                    raw = raw.split(",", 1)[1]
                content = base64.b64decode(raw, validate=True)
            except Exception as exc:
                raise ValueError("mcp_materialization_artifact_base64_invalid") from exc
        return self.service.mcp_materialization_store.submit(
            handoff_id,
            nonce=str(payload.get("nonce") or ""),
            prompt_sha256=str(payload.get("prompt_sha256") or ""),
            reference_asset_hashes=[str(item or "") for item in payload["reference_asset_hashes"]],
            artifact_bytes=content,
        )

    def get_creative_job(self, job_id: str) -> dict[str, Any]:
        return self.get_job(job_id)

    def get_job_export(self, job_id: str) -> dict[str, Any]:
        return self.service.export_job(job_id).model_dump(mode="json")

    def get_job_export_download(self, job_id: str) -> dict[str, Any]:
        return self.service.export_job_download(job_id).model_dump(mode="json")

    def post_generate(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.service.generate_job(job_id, payload or {}).model_dump(mode="json")

    def post_creative_job_generate(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.post_generate(job_id, payload)

    def post_select(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.service.select_result(job_id, payload or {}).model_dump(mode="json")

    def post_creative_job_select(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.post_select(job_id, payload)

    def post_brands(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_brand(payload).model_dump(mode="json")

    def post_product_brands(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post_brands(payload)

    def get_brand(self, brand_id: str) -> dict[str, Any]:
        return self.service.get_brand(brand_id).model_dump(mode="json")

    def get_product_brand(self, brand_id: str) -> dict[str, Any]:
        return self.get_brand(brand_id)
