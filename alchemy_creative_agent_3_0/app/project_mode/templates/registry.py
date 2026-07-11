"""V3 Project Mode template registry and activation gate."""

from __future__ import annotations

from collections.abc import Iterable

from ...scenario_packs import ScenarioPackRegistry, ScenarioPackStatus
from ...shared_capabilities.activation import (
    TemplateCapabilityPolicy,
    ecommerce_capability_policy,
    general_capability_policy,
)
from ..contracts import (
    ECOMMERCE_TEMPLATE_ID,
    GENERAL_SCENARIO_ID,
    GENERAL_TEMPLATE_ID,
    TemplateCard,
    TemplateStatus,
)
from .contracts import (
    BrandMemoryReadMode,
    ProjectTemplateManifest,
    TemplateActivationError,
    TemplateContextReadPolicy,
    TemplateContextWritePolicy,
    TemplateInputField,
    TemplateInputFieldType,
    TemplateOutputSummaryPolicy,
)


TEMPLATE_LOCKED_MESSAGE = "\u8fd9\u4e2a\u6a21\u677f\u8fd8\u5728\u51c6\u5907\u4e2d\u3002\u5f53\u524d\u53ef\u4ee5\u5148\u7528\u901a\u7528\u6a21\u677f\u7ee7\u7eed\u505a\u56fe\u3002"
TEMPLATE_PLACEHOLDER_MESSAGE = "\u8fd9\u4e2a\u65b9\u5411\u8fd8\u5728\u89c4\u5212\u4e2d\u3002\u5f53\u524d\u53ef\u4ee5\u5148\u7528\u901a\u7528\u6a21\u677f\u5b8c\u6210\u9879\u76ee\u98ce\u683c\u3002"
TEMPLATE_UNAVAILABLE_MESSAGE = "\u8fd9\u4e2a\u6a21\u677f\u6682\u65f6\u4e0d\u53ef\u7528\u3002\u5f53\u524d\u53ef\u4ee5\u5148\u7528\u901a\u7528\u6a21\u677f\u7ee7\u7eed\u505a\u56fe\u3002"


class ProjectTemplateRegistry:
    """Owns Project Mode template manifests without duplicating runtime packs."""

    def __init__(
        self,
        manifests: Iterable[ProjectTemplateManifest] | None = None,
        scenario_registry: ScenarioPackRegistry | None = None,
    ) -> None:
        self.scenario_registry = scenario_registry or ScenarioPackRegistry()
        manifest_list = list(manifests) if manifests is not None else default_template_manifests()
        self._manifests = {manifest.template_id: manifest for manifest in manifest_list}

    def list_manifests(self, include_disabled: bool = False) -> list[ProjectTemplateManifest]:
        manifests = list(self._manifests.values())
        if include_disabled:
            return manifests
        return [manifest for manifest in manifests if manifest.status != TemplateStatus.DISABLED]

    def list_cards(self, include_disabled: bool = False) -> list[TemplateCard]:
        return [manifest.to_template_card() for manifest in self.list_manifests(include_disabled=include_disabled)]

    def get_manifest(self, template_id: str | None) -> ProjectTemplateManifest | None:
        return self._manifests.get(template_id or GENERAL_TEMPLATE_ID)

    def ensure_can_create_project_job(self, template_id: str | None) -> ProjectTemplateManifest:
        manifest = self.get_manifest(template_id)
        requested_template_id = template_id or GENERAL_TEMPLATE_ID
        if manifest is None:
            raise TemplateActivationError("template_not_found", TEMPLATE_UNAVAILABLE_MESSAGE, requested_template_id)
        if manifest.status == TemplateStatus.LOCKED:
            raise TemplateActivationError("template_locked", TEMPLATE_LOCKED_MESSAGE, manifest.template_id)
        if manifest.status == TemplateStatus.PLACEHOLDER:
            raise TemplateActivationError("template_placeholder", TEMPLATE_PLACEHOLDER_MESSAGE, manifest.template_id)
        if manifest.status in {TemplateStatus.DISABLED, TemplateStatus.INACTIVE}:
            raise TemplateActivationError("template_disabled", TEMPLATE_UNAVAILABLE_MESSAGE, manifest.template_id)
        if not manifest.context_write_policy.can_create_jobs:
            raise TemplateActivationError("template_locked", TEMPLATE_LOCKED_MESSAGE, manifest.template_id)
        if not self._scenario_pack_is_active(manifest.scenario_pack_id):
            raise TemplateActivationError("template_unavailable", TEMPLATE_UNAVAILABLE_MESSAGE, manifest.template_id)
        return manifest

    def _scenario_pack_is_active(self, scenario_pack_id: str) -> bool:
        pack = self.scenario_registry.get_pack(scenario_pack_id)
        if pack is None:
            return False
        return pack.manifest.status == ScenarioPackStatus.ACTIVE and pack.can_create_jobs


def default_template_manifests() -> list[ProjectTemplateManifest]:
    return [
        _general_template_manifest(),
        _ecommerce_template_manifest(),
        _future_template_manifest(
            template_id="photographer_template",
            display_name="\u6444\u5f71\u5e08\u6a21\u677f",
            scenario_pack_id="future_photographer",
            frontend_workspace="photographer_project_workspace",
        ),
        _future_template_manifest(
            template_id="new_media_template",
            display_name="\u65b0\u5a92\u4f53\u6a21\u677f",
            scenario_pack_id="future_new_media",
            frontend_workspace="new_media_project_workspace",
        ),
        _future_template_manifest(
            template_id="private_domain_template",
            display_name="\u79c1\u57df\u6a21\u677f",
            scenario_pack_id="future_private_domain",
            frontend_workspace="private_domain_project_workspace",
        ),
        _future_template_manifest(
            template_id="brand_ip_template",
            display_name="\u54c1\u724c IP \u6a21\u677f",
            scenario_pack_id="future_brand_ip",
            frontend_workspace="brand_ip_project_workspace",
        ),
    ]


def _general_template_manifest() -> ProjectTemplateManifest:
    return ProjectTemplateManifest(
        template_id=GENERAL_TEMPLATE_ID,
        display_name="\u901a\u7528\u6a21\u677f",
        short_description="\u9002\u5408\u6d77\u62a5\u3001\u5c01\u9762\u3001\u6d3b\u52a8\u56fe\u548c\u54c1\u724c\u89c6\u89c9\uff0c\u5148\u628a\u9879\u76ee\u98ce\u683c\u8dd1\u901a\u3002",
        scenario_pack_id=GENERAL_SCENARIO_ID,
        status=TemplateStatus.ACTIVE,
        allowed_project_types=["general_visual_project"],
        required_inputs=[
            TemplateInputField(
                field_id="user_goal",
                label="\u60f3\u8981\u505a\u4ec0\u4e48",
                field_type=TemplateInputFieldType.TEXTAREA,
                required=True,
                beginner_copy="\u7528\u4e00\u53e5\u8bdd\u8bf4\u660e\u4f60\u60f3\u8981\u7684\u56fe\u3002",
            )
        ],
        optional_inputs=[
            TemplateInputField(
                field_id="reference_images",
                label="\u53c2\u8003\u56fe",
                field_type=TemplateInputFieldType.IMAGE_UPLOAD,
                required=False,
                beginner_copy="\u6709\u559c\u6b22\u7684\u98ce\u683c\u6216\u4ea7\u54c1\u56fe\u53ef\u4ee5\u4e00\u8d77\u653e\u8fdb\u6765\u3002",
            )
        ],
        context_read_policy=TemplateContextReadPolicy(
            reads_project_goal=True,
            reads_selected_outputs=True,
            reads_uploaded_references=True,
            reads_negative_feedback=True,
            reads_brand_memory=BrandMemoryReadMode.EXPLICIT_USER_SELECTED,
        ),
        context_write_policy=TemplateContextWritePolicy(
            can_create_jobs=True,
            can_select_outputs=True,
            can_create_reference_assets=True,
            can_create_feedback=True,
            can_propose_brand_memory=True,
        ),
        output_summary_policy=TemplateOutputSummaryPolicy(
            summary_sections=["images", "what_changed", "next_actions"],
            image_slot_model="general_image_series",
            user_visible_fields=["image", "purpose", "why_useful", "next_step"],
            hidden_debug_fields=["provider", "job_id", "prompt_compiler", "manifest"],
        ),
        frontend_workspace="general_project_workspace",
        activation_requirements=[
            "Document 36 accepted",
            "Document 38 project workspace UX implemented",
            "Document 39 project context persistence implemented",
            "Document 43 product experience gate passed",
        ],
        test_requirements=[
            "general template can create project jobs",
            "selected outputs enter project context",
            "unselected candidates stay out of positive context",
        ],
        ui_card={"label": "\u901a\u7528\u6a21\u677f", "icon": "sparkles"},
        metadata={"maps_to_scenario_pack": GENERAL_SCENARIO_ID, "current_phase": "project_mode_foundation"},
        capability_policy=general_capability_policy(),
    )


def _ecommerce_template_manifest() -> ProjectTemplateManifest:
    return ProjectTemplateManifest(
        template_id=ECOMMERCE_TEMPLATE_ID,
        display_name="\u7535\u5546\u6a21\u677f",
        short_description="\u5199\u4e00\u53e5\u60f3\u8981\u4ec0\u4e48\u5c31\u80fd\u751f\u6210\u7535\u5546\u5957\u56fe\uff1b\u6709\u5546\u54c1\u56fe\u65f6\u4f1a\u4f18\u5148\u4fdd\u6301\u5b9e\u7269\u4e00\u81f4\u3002",
        scenario_pack_id="ecommerce",
        status=TemplateStatus.ACTIVE,
        allowed_project_types=["ecommerce_visual_project"],
        required_inputs=[],
        optional_inputs=[
            TemplateInputField(
                field_id="product_image",
                label="\u4ea7\u54c1\u56fe",
                field_type=TemplateInputFieldType.IMAGE_UPLOAD,
                required=False,
                beginner_copy="\u53ef\u9009\u3002\u4e0a\u4f20\u5b9e\u7269\u56fe\u540e\uff0cV3 \u4f1a\u66f4\u7a33\u5730\u4fdd\u6301\u5546\u54c1\u5916\u89c2\uff1b\u4e0d\u4e0a\u4f20\u4e5f\u53ef\u4ee5\u6309\u6587\u5b57\u76f4\u63a5\u751f\u6210\u7535\u5546\u6982\u5ff5\u56fe\u3002",
            ),
            TemplateInputField(
                field_id="target_platform",
                label="\u76ee\u6807\u5e73\u53f0",
                field_type=TemplateInputFieldType.SELECT,
                required=False,
                beginner_copy="\u9009\u62e9\u8fd9\u7ec4\u56fe\u4e3b\u8981\u7528\u5728\u54ea\u4e2a\u5e73\u53f0\u3002",
                options=["generic", "amazon_us", "shopify", "tiktok_shop", "taobao", "jd"],
            ),
            TemplateInputField(
                field_id="main_selling_point",
                label="\u4e3b\u6253\u5356\u70b9",
                field_type=TemplateInputFieldType.TEXT,
                required=False,
                beginner_copy="\u53ef\u4ee5\u5199\u4e00\u4e2a\u6700\u60f3\u7a81\u51fa\u7684\u5356\u70b9\u3002",
            ),
            TemplateInputField(
                field_id="product_facts",
                label="\u5546\u54c1\u4fe1\u606f",
                field_type=TemplateInputFieldType.TEXTAREA,
                required=False,
                beginner_copy="\u6750\u8d28\u3001\u5c3a\u5bf8\u3001\u529f\u80fd\u3001\u5fc5\u987b\u4fdd\u6301\u6b63\u786e\u7684\u4fe1\u606f\u90fd\u53ef\u4ee5\u653e\u5728\u8fd9\u91cc\u3002",
                advanced=True,
            ),
            TemplateInputField(
                field_id="keywords",
                label="\u5173\u952e\u8bcd",
                field_type=TemplateInputFieldType.TEXT,
                required=False,
                beginner_copy="\u53ef\u9009\uff0c\u7528\u4e8e\u5e2e\u52a9\u7535\u5546\u753b\u9762\u66f4\u8d34\u8fd1\u641c\u7d22\u610f\u56fe\u3002",
                advanced=True,
            ),
        ],
        context_read_policy=TemplateContextReadPolicy(
            reads_project_goal=True,
            reads_selected_outputs=True,
            reads_uploaded_references=True,
            reads_negative_feedback=True,
            reads_brand_memory=BrandMemoryReadMode.EXPLICIT_USER_SELECTED,
            template_specific_fields=["ecommerce.product_profile", "ecommerce.marketplace_profile"],
        ),
        context_write_policy=TemplateContextWritePolicy(
            can_create_jobs=True,
            can_select_outputs=True,
            can_create_reference_assets=True,
            can_create_feedback=True,
            can_propose_brand_memory=True,
            template_specific_project_fields=["ecommerce"],
        ),
        output_summary_policy=TemplateOutputSummaryPolicy(
            summary_sections=["listing_image_set", "selling_points", "compliance_notes"],
            image_slot_model="ecommerce_listing_set",
            user_visible_fields=["image", "commerce_use", "selling_point", "next_step"],
            hidden_debug_fields=["product_truth_lock", "marketplace_rules", "provider", "manifest"],
        ),
        frontend_workspace="ecommerce_project_workspace",
        activation_requirements=[
            "Document 42 implemented and accepted",
            "Document 43 product experience gate passed",
            "template-specific beginner workspace exists",
            "cross-template pollution tests pass",
        ],
        test_requirements=[
            "ecommerce project jobs can run from text only and strengthen consistency when a product reference exists",
            "ecommerce project jobs are created only through the template registry",
            "legacy /jobs ecommerce compatibility remains reachable outside Project Mode",
            "ecommerce workspace does not reuse General Template UI blindly",
        ],
        ui_card={"label": "\u7535\u5546\u6a21\u677f", "icon": "shopping-bag"},
        metadata={"project_mode_active_document": "42", "requires_product_reference": False, "supports_text_to_image_fallback": True},
        capability_policy=ecommerce_capability_policy(),
    )


def _future_template_manifest(
    *,
    template_id: str,
    display_name: str,
    scenario_pack_id: str,
    frontend_workspace: str,
) -> ProjectTemplateManifest:
    return ProjectTemplateManifest(
        template_id=template_id,
        display_name=display_name,
        short_description="\u8fd9\u4e2a\u65b9\u5411\u8fd8\u5728\u89c4\u5212\u4e2d\uff0c\u5f53\u524d\u53ef\u4ee5\u5148\u7528\u901a\u7528\u6a21\u677f\u7ee7\u7eed\u505a\u56fe\u3002",
        scenario_pack_id=scenario_pack_id,
        status=TemplateStatus.PLACEHOLDER,
        allowed_project_types=[template_id.replace("_template", "_project")],
        required_inputs=[],
        optional_inputs=[],
        context_read_policy=TemplateContextReadPolicy(),
        context_write_policy=TemplateContextWritePolicy(),
        output_summary_policy=TemplateOutputSummaryPolicy(
            summary_sections=[],
            image_slot_model=None,
            user_visible_fields=[],
            hidden_debug_fields=["provider", "manifest"],
        ),
        frontend_workspace=frontend_workspace,
        activation_requirements=[
            "dedicated product spec accepted",
            "Scenario Pack or V3-owned runtime exists",
            "Document 43 product experience gate passed",
        ],
        test_requirements=["template cannot create jobs while placeholder"],
        ui_card={"label": display_name, "icon": "layout-template"},
        metadata={"future_template": True},
        capability_policy=TemplateCapabilityPolicy(
            policy_id=f"{template_id}_placeholder_capabilities",
            brain_activation_enabled=False,
            deliverable_role_owner=template_id,
        ),
    )
