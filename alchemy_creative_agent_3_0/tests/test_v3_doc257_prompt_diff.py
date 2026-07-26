from pathlib import Path

from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    _character_card_stage_mcp_prompt_current,
)


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def _character_card_anchor_prompt_block() -> str:
    source = _read("app/llm_brain/prompts.py")
    start = source.index("also reconcile this as a character card face identity capture")
    end = source.index("elif anchor_capture_presentation:", start)
    return source[start:end]


def _source_block(relative_path: str, start_marker: str, end_marker: str) -> str:
    source = _read(relative_path)
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_doc257_standard_front_prompt_uses_positive_model_card_framing_only() -> None:
    source = _character_card_anchor_prompt_block()

    required_positive = [
        "photographer-shot",
        "model-card",
        "consistent photographer distance",
        "complete hair outline",
        "small natural headroom",
        "visible neck, collar and upper shoulders",
    ]
    for phrase in required_positive:
        assert phrase in source

    forbidden_prompt_increments = [
        "evidence-grade standardized identity capture",
        "upper_shoulders_only_no_half_body_or_big_head_crop",
        "normalize_to_symmetric_camera_facing_front",
        "face_midline_vertical_eyes_level_nose_centered",
        "balanced_ears_cheeks_shoulders_no_head_turn_or_tilt",
        "face midline vertical",
        "eyes level",
        "nose centered",
        "symmetric, camera-facing",
        "let small real facial asymmetry",
        "fine hair edges and camera-observed skin variation",
        "passport",
        "biometric",
        "undetectable",
        "age-appropriate casting/model-card",
        "hair/grooming logic",
        "natural expression tendency",
        "real studio softness",
        "commercially polished",
        "beautiful, and relaxed",
    ]
    for phrase in forbidden_prompt_increments:
        assert phrase not in source


def test_doc257_expression_prompt_reuses_framing_without_old_negative_crop_stack() -> None:
    source = _character_card_anchor_prompt_block()

    assert "same model-card framing" in source
    assert "model-card framing family" in source
    assert "laugh" in source
    assert "anger" in source
    assert "sad" in source

    forbidden_expression_crop_stack = [
        "avoid close-up",
        "not a half-body crop",
        "no chest-or-torso panel",
        "not through face-area",
        "checklist of eye, ear, nose or chin-line tokens",
    ]
    for phrase in forbidden_expression_crop_stack:
        assert phrase not in source


def test_doc257_expression_generation_uses_child_model_card_affect_without_detector_stack() -> None:
    source = _source_block(
        "app/product_api/anchor_pack_host.py",
        "def _character_card_expression_slot_intents",
        "def _character_card_single_expression_intent",
    )
    recovery_source = _source_block(
        "app/scenario_runtime/runtime.py",
        "def _character_card_expression_slot_delta_recovery_prompt",
        "def _character_card_slot_delta_transport_timeout_seconds",
    )
    combined = "\n".join([source, recovery_source])

    for phrase in (
        "playful innocent child energy",
        "bright childlike laugh",
        "childlike annoyed pout",
        "small stubborn frown",
        "soft childlike sadness",
        "misty-eyed",
    ):
        assert phrase in combined

    for phrase in (
        "detector",
        "undetectable",
        "ai-generated",
        "plastic skin",
        "micro-detail",
        "pore",
    ):
        assert phrase not in combined


def test_doc257_expression_stage_pins_vertical_model_card_size() -> None:
    source = _source_block(
        "app/product_api/service.py",
        "elif trusted_professional_character_card:",
        "else:\n            self._bind_professional_mode",
    )

    assert '"requested_image_size": "1024x1536"' in source
    assert '"quality_mode": "strict"' in source
    assert '"professional_anchor_rendering_contract": "size:1024x1536|quality:strict|reference_card"' in source


def test_doc257_laugh_mcp_prompt_current_accepts_simplified_model_card_contract() -> None:
    current_prompt = (
        "Professional modeling card vertical 2:3 frame, same child as the face.front reference, "
        "head and upper shoulders centered, clean white studio background, identical lighting and white balance. "
        "The child's expression is a genuine joyful laugh caught at a lively keyframe: eyes crinkled into happy crescents, "
        "cheeks lifted, mouth open in a relaxed laugh with natural small teeth visible, slight spontaneous asymmetry, lively gaze."
    )
    old_soft_prompt = (
        "Same child in a softly amused portrait with a gentle happy look and no explicit model-card framing contract."
    )

    assert _character_card_stage_mcp_prompt_current("expression.laugh", current_prompt)
    assert not _character_card_stage_mcp_prompt_current("expression.laugh", old_soft_prompt)


def test_doc257_host_no_longer_writes_deprecated_realism_prompt_gate_metadata() -> None:
    source = _read("app/product_api/anchor_pack_host.py")

    forbidden_active_metadata = [
        "professional_absolute_portrait_realism_required",
        "professional_absolute_portrait_realism_provenance",
        "professional_micro_real_human_fidelity_required",
        "professional_micro_real_human_fidelity_guidance",
        "professional_micro_real_human_fidelity_visual_direction_addons",
        "professional_micro_real_human_fidelity_negative_prompt_addons",
        "append_micro_real_human_fidelity_guidance",
    ]
    for phrase in forbidden_active_metadata:
        assert phrase not in source


def test_doc257_generation_recovery_exits_drop_old_micro_and_detector_wording() -> None:
    source = _source_block(
        "app/scenario_runtime/runtime.py",
        "def _recover_character_card_slot_delta_brain_result",
        "def _finalize_canonical_provider_prompts",
    )

    for phrase in (
        "head, neck, and upper shoulders reference-card crop",
        "plain white studio background",
        "requested face-view angle must be visible",
        "close model-card crop",
        "not half-body",
        "not big-head",
        "reference-card",
    ):
        assert phrase in source

    for phrase in (
        "avoid plastic skin",
        "avoid dirty noise or smeared texture",
        "no plastic skin",
        "noise or smear",
    ):
        assert phrase not in source


def test_doc257_active_retry_patches_use_neutral_photo_quality_not_micro_defect_stack() -> None:
    product_api_retry = _source_block(
        "app/product_api/service.py",
        "def _visual_retry_patch_from_issues",
        "def _merge_post_generation_review_chain",
    )
    inspector_retry = _source_block(
        "app/shared_capabilities/visual_cluster/vision_inspector.py",
        "elif code in _aesthetic_stability_issues",
        "elif code in {\"weak_lifestyle_context\"",
    )

    combined_generation_exits = "\n".join([product_api_retry, inspector_retry])
    for phrase in (
        "synthetic micro-detail",
        "synthetic micro detail",
        "waxy polish",
        "ai-looking micro-sharpness",
        "ai-looking sharpness",
        "poreless glass-like skin",
        "avoid plastic skin",
        "plastic texture",
        "generic ai beauty identity",
        "overprocessed hdr",
        "generic stock-photo polish",
    ):
        assert phrase not in combined_generation_exits


def test_doc257_shared_provider_strict_policy_remains_out_of_prompt_cleanup_scope() -> None:
    provider_prompt = _source_block(
        "app/generation_router/providers.py",
        "strict_policy = plan_metadata.get",
        "def _role_prompt_pressure_for_provider",
    )

    for phrase in (
        "poreless glass-like skin",
        "generic ai beauty identity",
        "overprocessed hdr finish",
    ):
        assert phrase in provider_prompt


def test_doc257_review_prompt_preserves_quality_and_angle_acceptance_checks() -> None:
    source = _read("app/shared_capabilities/visual_cluster/vision_provider.py")

    for phrase in (
        "waxy/plastic or poreless/smeared skin",
        "visible ai-render artifact",
        "standard_front reads as front-facing",
        "left_front_25",
        "right_front_25",
        "three_quarter and reverse_three_quarter read",
        "profile reads as a 90-degree side card",
        "rear_head reads as a back-of-head",
    ):
        assert phrase in source
