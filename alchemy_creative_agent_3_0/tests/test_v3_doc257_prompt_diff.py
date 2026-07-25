from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def test_doc257_standard_front_prompt_uses_positive_model_card_framing_only() -> None:
    source = _read("app/llm_brain/prompts.py")

    required_positive = [
        "photographer-shot",
        "age-appropriate casting/model-card",
        "reference-owned age reading",
        "hair/grooming logic",
        "model-card",
        "consistent photographer distance",
        "complete hair outline",
        "small natural headroom",
        "visible neck, collar and upper shoulders",
        "real studio softness",
    ]
    for phrase in required_positive:
        assert phrase in source

    forbidden_prompt_increments = [
        "evidence-grade standardized identity capture",
        "face midline vertical",
        "eyes level",
        "nose centered",
        "symmetric, camera-facing",
        "let small real facial asymmetry",
        "fine hair edges and camera-observed skin variation",
        "passport",
        "biometric",
        "undetectable",
    ]
    for phrase in forbidden_prompt_increments:
        assert phrase not in source


def test_doc257_expression_prompt_reuses_framing_without_old_negative_crop_stack() -> None:
    source = _read("app/llm_brain/prompts.py")

    assert "same model-card framing" in source
    assert "model-card framing family" in source
    assert "reference-owned age reading" in source
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
