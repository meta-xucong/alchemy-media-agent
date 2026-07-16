from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.consumers import (
    ProfessionalConsumerRequest,
    ProfessionalModeConsumerAdapter,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import ProfessionalModeBinding


def _binding() -> ProfessionalModeBinding:
    return ProfessionalModeBinding(
        job_id="job_1",
        project_id="project_1",
        people_asset_id="person_1",
        face_module_id="face_module_1",
        pack_version_id="pack_1",
        identity_view_ids=["front_1"],
    )


def test_standard_mode_has_no_people_asset_lookup_or_metadata() -> None:
    context = ProfessionalModeConsumerAdapter().prepare(
        ProfessionalConsumerRequest(template_id="general_template", mode="standard")
    )

    assert context is None


def test_professional_mode_requires_explicit_binding() -> None:
    with pytest.raises(ValueError, match="selected People Asset"):
        ProfessionalModeConsumerAdapter().prepare(
            ProfessionalConsumerRequest(template_id="general_template", mode="professional")
        )


def test_professional_mode_is_available_to_three_templates_without_role_fields() -> None:
    adapter = ProfessionalModeConsumerAdapter()
    for template_id in ("general_template", "ecommerce_template", "photographer_template"):
        context = adapter.prepare(
            ProfessionalConsumerRequest(template_id=template_id, mode="professional", binding=_binding())
        )
        assert context.template_id == template_id
        assert context.mode == "professional"
        assert context.identity_binding["people_asset_id"] == "person_1"
        assert {"slot", "platform", "marketplace", "photographer_role"}.isdisjoint(context.identity_binding)


def test_vertical_or_future_template_is_not_silently_accepted() -> None:
    with pytest.raises(ValueError, match="template"):
        ProfessionalModeConsumerAdapter().prepare(
            ProfessionalConsumerRequest(template_id="video_template", mode="professional", binding=_binding())
        )


def test_consumer_request_does_not_accept_user_text_for_keyword_activation() -> None:
    with pytest.raises(ValidationError):
        ProfessionalConsumerRequest(
            template_id="general_template",
            mode="professional",
            binding=_binding(),
            user_input="make this a professional people asset",
        )
