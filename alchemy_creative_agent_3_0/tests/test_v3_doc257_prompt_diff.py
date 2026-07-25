from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def _character_card_anchor_prompt_block() -> str:
    source = _read("app/llm_brain/prompts.py")
    start = source.index("also reconcile this as a character card face identity capture")
    end = source.index("elif anchor_capture_presentation:", start)
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
