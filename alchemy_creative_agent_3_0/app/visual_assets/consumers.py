"""Explicit Standard/Professional consumer seam for existing V3 templates."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .contracts import ProfessionalModeBinding


SUPPORTED_PROFESSIONAL_TEMPLATES = frozenset(
    {"general_template", "ecommerce_template", "photographer_template"}
)


class ProfessionalConsumerRequest(V3BaseModel):
    """Only explicit mode/template/binding controls are accepted."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    template_id: str
    mode: Literal["standard", "professional"]
    binding: ProfessionalModeBinding | None = None

    @field_validator("template_id")
    @classmethod
    def supported_template(cls, value: str) -> str:
        if value not in SUPPORTED_PROFESSIONAL_TEMPLATES:
            raise ValueError("template is not enabled for Professional Mode")
        return value

    @model_validator(mode="after")
    def explicit_mode_contract(self) -> "ProfessionalConsumerRequest":
        if self.mode == "professional" and self.binding is None:
            raise ValueError("Professional Mode requires a selected People Asset binding")
        if self.mode == "standard" and self.binding is not None:
            raise ValueError("Standard Mode cannot receive Professional Mode asset metadata")
        return self


class ProfessionalConsumerContext(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    template_id: Literal["general_template", "ecommerce_template", "photographer_template"]
    mode: Literal["professional"]
    identity_binding: dict[str, object]
    binding_owner: Literal["visual_asset_library"] = "visual_asset_library"


class ProfessionalModeConsumerAdapter:
    """Convert one explicit binding into shared typed context, never a role recipe."""

    def prepare(self, request: ProfessionalConsumerRequest) -> ProfessionalConsumerContext | None:
        if request.mode == "standard":
            return None
        if request.template_id not in SUPPORTED_PROFESSIONAL_TEMPLATES:
            raise ValueError("template is not enabled for Professional Mode")
        if request.binding is None:  # guarded by the request model; keep fail-closed at the adapter boundary too
            raise ValueError("Professional Mode requires a selected People Asset binding")
        return ProfessionalConsumerContext(
            template_id=request.template_id,
            mode="professional",
            identity_binding=request.binding.to_brain_evidence(),
        )
