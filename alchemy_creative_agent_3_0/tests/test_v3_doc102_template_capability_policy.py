from alchemy_creative_agent_3_0.app.project_mode.templates import ProjectTemplateRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import compatibility_policy


def test_general_and_ecommerce_own_different_policy_profiles() -> None:
    registry = ProjectTemplateRegistry()
    general = registry.get_manifest("general_template").capability_policy
    ecommerce = registry.get_manifest("ecommerce_template").capability_policy
    assert general.deliverable_role_owner == "general_template"
    assert ecommerce.deliverable_role_owner == "ecommerce_template"
    assert ecommerce.metadata["creative_direction_owner"] == "remote_v3_llm_brain"
    assert ecommerce.requires_remote_creative_brain is True
    assert ecommerce.review_threshold_profile == "commercial_strict"


def test_placeholder_template_disables_brain_activation() -> None:
    manifest = ProjectTemplateRegistry().get_manifest("photographer_template")
    assert manifest.capability_policy.brain_activation_enabled is False
    assert manifest.project_can_create_jobs is False


def test_template_card_contains_safe_policy_summary_only() -> None:
    card = ProjectTemplateRegistry().get_manifest("general_template").to_template_card()
    summary = card.metadata["capability_policy_summary"]
    assert summary["policy_id"] == "general_template_capabilities"
    assert "dependencies" not in summary
    assert "manifests" not in summary


def test_direct_api_policy_is_trusted_from_scenario_not_user_payload() -> None:
    assert compatibility_policy(None, "ecommerce").policy_id == "ecommerce_template_capabilities"
    assert compatibility_policy("malicious_template", "general_creative").policy_id == "general_template_capabilities"
