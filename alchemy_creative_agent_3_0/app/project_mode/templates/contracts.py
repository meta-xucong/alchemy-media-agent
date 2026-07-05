"""Template manifest contracts for V3 Project Mode."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from ...schemas.models import V3BaseModel
from ..contracts import TemplateCard, TemplateStatus


class TemplateInputFieldType(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    IMAGE_UPLOAD = "image_upload"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    TOGGLE = "toggle"
    NUMBER = "number"


class BrandMemoryReadMode(StrEnum):
    NEVER = "never"
    EXPLICIT_USER_SELECTED = "explicit_user_selected"
    AUTOMATIC_IF_PROJECT_BOUND = "automatic_if_project_bound"


class TemplateInputField(V3BaseModel):
    field_id: str
    label: str
    field_type: TemplateInputFieldType
    required: bool = False
    beginner_copy: str
    advanced: bool = False
    options: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemplateContextReadPolicy(V3BaseModel):
    reads_project_goal: bool = True
    reads_selected_outputs: bool = False
    reads_uploaded_references: bool = False
    reads_negative_feedback: bool = False
    reads_brand_memory: BrandMemoryReadMode = BrandMemoryReadMode.NEVER
    template_specific_fields: list[str] = Field(default_factory=list)


class TemplateContextWritePolicy(V3BaseModel):
    can_create_jobs: bool = False
    can_select_outputs: bool = False
    can_create_reference_assets: bool = False
    can_create_feedback: bool = False
    can_propose_brand_memory: bool = False
    template_specific_project_fields: list[str] = Field(default_factory=list)


class TemplateOutputSummaryPolicy(V3BaseModel):
    summary_sections: list[str] = Field(default_factory=list)
    image_slot_model: str | None = None
    user_visible_fields: list[str] = Field(default_factory=list)
    hidden_debug_fields: list[str] = Field(default_factory=list)


class TemplateActivationError(ValueError):
    """Structured activation error for beginner-facing API responses."""

    def __init__(self, code: str, message: str, template_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.template_id = template_id

    def to_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.template_id:
            detail["template_id"] = self.template_id
        return detail


class ProjectTemplateManifest(V3BaseModel):
    template_id: str
    display_name: str
    short_description: str
    scenario_pack_id: str
    status: TemplateStatus
    allowed_project_types: list[str] = Field(default_factory=list)
    required_inputs: list[TemplateInputField] = Field(default_factory=list)
    optional_inputs: list[TemplateInputField] = Field(default_factory=list)
    context_read_policy: TemplateContextReadPolicy
    context_write_policy: TemplateContextWritePolicy
    output_summary_policy: TemplateOutputSummaryPolicy
    frontend_workspace: str
    activation_requirements: list[str] = Field(default_factory=list)
    test_requirements: list[str] = Field(default_factory=list)
    ui_card: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def project_can_create_jobs(self) -> bool:
        return self.status == TemplateStatus.ACTIVE and self.context_write_policy.can_create_jobs

    def to_template_card(self) -> TemplateCard:
        ui_state = _ui_state_for_status(self.status)
        metadata = {
            **self.metadata,
            "manifest_version": "project_template_manifest_v1",
            "scenario_pack_id": self.scenario_pack_id,
            "allowed_project_types": list(self.allowed_project_types),
            "frontend_workspace": self.frontend_workspace,
            "activation_requirements": list(self.activation_requirements),
            "test_requirements": list(self.test_requirements),
            "context_read_policy": self.context_read_policy.model_dump(mode="json"),
            "context_write_policy": self.context_write_policy.model_dump(mode="json"),
            "output_summary_policy": self.output_summary_policy.model_dump(mode="json"),
        }
        return TemplateCard(
            template_id=self.template_id,
            scenario_id=self.scenario_pack_id,
            display_name=self.display_name,
            status=self.status,
            project_can_create_jobs=self.project_can_create_jobs,
            description=self.short_description,
            primary_action=ui_state["primary_action"],
            ui_card={
                **self.ui_card,
                "label": self.ui_card.get("label", self.display_name),
                "state": ui_state["state"],
                "action_label": ui_state["action_label"],
            },
            metadata=metadata,
        )


def _ui_state_for_status(status: TemplateStatus) -> dict[str, str]:
    if status == TemplateStatus.ACTIVE:
        return {"state": "active", "primary_action": "start_template", "action_label": "\u5f00\u59cb\u4f7f\u7528"}
    if status == TemplateStatus.LOCKED:
        return {"state": "locked", "primary_action": "show_locked", "action_label": "\u5373\u5c06\u5f00\u653e"}
    if status == TemplateStatus.PLACEHOLDER:
        return {"state": "placeholder", "primary_action": "show_placeholder", "action_label": "\u89c4\u5212\u4e2d"}
    return {"state": "disabled", "primary_action": "show_unavailable", "action_label": "\u6682\u4e0d\u53ef\u7528"}

