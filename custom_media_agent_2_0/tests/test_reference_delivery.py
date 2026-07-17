from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from app.repositories.memory import utc_now
from app.schemas import ImageJob, ImageOutput, ImagePromptPlan, ImageReviewDecision
from app.services.copy_safe_compositor import apply_deterministic_text_overlay
from app.services.intent_integrity import compile_prompt_artifact, preflight_prompt_integrity
from app.services.output_review import review_image_job
from app.services.reference_delivery import (
    build_reference_delivery_contract,
    reference_delivery_audit,
    reference_delivery_prompt_section,
)
from app.services.reference_provider import materialize_openai_reference_request
from app.services.semantic_retry import build_semantic_retry_directive
from app.services.source_text_evidence import extract_source_text_evidence
from app.services.visual_evidence_review import apply_reference_delivery_review


def _composite_context() -> dict:
    return {
        "user_prompt": "Rebuild this uploaded menu poster into the selected template and preserve the dishes, prices, and dates.",
        "template_lock_contract": {"locked_case_id": "case_menu"},
        "task_relationship_model": {
            "primary_relationship": "extract_composite_content",
            "content_extraction": True,
        },
        "uploaded_assets": [
            {
                "asset_id": "asset_menu",
                "brief": {
                    "detected_text": [
                        {"text": "Monday 7/20", "confidence": 0.95},
                        {"text": "Lunch set ¥38", "confidence": 0.96},
                    ]
                },
            }
        ],
        "asset_binding_plan": {
            "bindings": [
                {
                    "asset_id": "asset_menu",
                    "role": "subject_reference",
                    "constraint_strength": "required",
                    "fusion_mode": "composite_content_source",
                    "provider_input_required": True,
                    "placement_intent": {"target_surface": "semantic_content_slots"},
                }
            ]
        },
    }


def test_composite_source_contract_preserves_facts_without_granting_layout() -> None:
    contract = build_reference_delivery_contract(_composite_context())

    intent = contract["reference_intents"][0]
    assert intent["usage_mode"] == "composite_content"
    assert intent["source_layout_policy"] == "only_if_unlocked"
    assert "prices" in intent["source_owned_fields"]
    assert "layout_structure" in intent["template_owned_fields"]
    assert contract["text_rendering"]["mode"] == "deterministic_overlay"
    assert contract["acceptance"]["requires_pixel_review"] is True
    assert contract["required_reference_asset_ids"] == ["asset_menu"]


def test_delivery_prompt_and_audit_separate_source_copy() -> None:
    contract = build_reference_delivery_contract(_composite_context())
    prompt_section = reference_delivery_prompt_section(contract)
    audit = reference_delivery_audit(contract)

    assert "Lunch set ¥38" in prompt_section
    assert "Lunch set ¥38" not in repr(audit)
    assert audit["source_evidence"][0]["value_hash"]
    assert audit["source_evidence"][0]["value_length"] > 0
    assert audit["evidence_capture"] == {"status": "available", "field_count": 2}


def test_information_dense_source_without_text_evidence_blocks_auto_delivery() -> None:
    context = _composite_context()
    context["uploaded_assets"][0]["brief"] = {
        "detected_text": [],
        "image": {"text_evidence": {"status": "unavailable", "engine": "tesseract"}},
    }

    contract = build_reference_delivery_contract(context)

    assert contract["evidence_capture"]["status"] == "unavailable"
    assert contract["acceptance"]["requires_source_text_evidence"] is True
    assert contract["acceptance"]["block_automatic_delivery"] is True


def test_contract_deduplicates_provider_inputs_but_retains_multiple_role_intents() -> None:
    context = _composite_context()
    context["asset_binding_plan"]["bindings"].append(
        {
            "asset_id": "asset_menu",
            "role": "logo_reference",
            "constraint_strength": "required",
            "fusion_mode": "logo_product_surface",
            "provider_input_required": True,
        }
    )

    contract = build_reference_delivery_contract(context)

    assert len(contract["reference_intents"]) == 2
    assert contract["required_reference_asset_ids"] == ["asset_menu"]
    assert all(item["required"] for item in contract["source_evidence"])


def test_preflight_rejects_reference_delivery_drift() -> None:
    prompt, trace = compile_prompt_artifact(
        user_prompt="Use the uploaded menu.",
        creative_prompt="Preserve its facts.",
        creative_source="claude_final_prompt",
    )
    result = preflight_prompt_integrity(
        trace=trace,
        effective_prompt=prompt,
        input_images=[{"asset_id": "asset_provider", "reference_index": 1}],
        provider_input_plan={"requires_image_reference": True, "reference_image_asset_ids": ["asset_provider"]},
        reference_delivery={"required_reference_asset_ids": ["asset_contract"]},
    )

    assert result["preflight"]["status"] == "failed"
    assert result["preflight"]["code"] == "reference_delivery_contract_drift"


def test_provider_receipt_does_not_send_undeclared_fidelity_parameter() -> None:
    contract = build_reference_delivery_contract(_composite_context())
    plan = SimpleNamespace(user_variables={"reference_delivery": contract})

    kwargs, receipt = materialize_openai_reference_request(
        plan=plan,
        model="gpt-image-2",
        operation="images.edit",
        reference_image_count=1,
        base_kwargs={"quality": "high", "output_format": "png"},
    )

    assert "input_fidelity" not in kwargs
    assert receipt["input_fidelity_requested"] is True
    assert receipt["input_fidelity_omission_reason"] == "model_capability_not_declared"
    assert receipt["reference_image_count"] == 1


def test_pixel_review_requires_verified_source_text_for_dense_contract(tmp_path) -> None:
    contract = build_reference_delivery_contract(_composite_context())
    path = tmp_path / "output.png"
    Image.new("RGB", (64, 48), "white").save(path)
    now = utc_now()
    plan = ImagePromptPlan(
        plan_id="plan_delivery_review",
        mode="template_customize",
        prompt="Use the uploaded menu.",
        negative_prompt="watermark",
        user_variables={"reference_delivery": contract},
    )
    job = ImageJob(
        job_id="job_delivery_review",
        status="completed",
        provider_id="test_provider",
        model="test_model",
        prompt_plan=plan,
        created_at=now,
        updated_at=now,
    )
    output = ImageOutput(
        output_id="out_delivery_review",
        job_id=job.job_id,
        url="/api/v2/test.png",
        metadata={"storage_path": str(path), "live": True},
        created_at=now,
    )
    baseline = ImageReviewDecision(
        review_id="review_delivery",
        output_id=output.output_id,
        decision="pass",
        score=0.9,
        created_at=now,
    )

    reviewed = apply_reference_delivery_review(output, job, baseline)

    assert reviewed.decision == "needs_review"
    assert "required_source_text_unverified" in reviewed.detected_risks
    assert reviewed.analysis_mode == "pixel_file_and_contract"


def test_pixel_review_blocks_dense_source_when_ocr_evidence_is_unavailable(tmp_path) -> None:
    context = _composite_context()
    context["uploaded_assets"][0]["brief"] = {
        "detected_text": [],
        "image": {"text_evidence": {"status": "unavailable", "engine": "tesseract"}},
    }
    contract = build_reference_delivery_contract(context)
    path = tmp_path / "output.png"
    Image.new("RGB", (64, 48), "white").save(path)
    now = utc_now()
    job = ImageJob(
        job_id="job_evidence_missing",
        status="completed",
        provider_id="test_provider",
        model="test_model",
        prompt_plan=ImagePromptPlan(
            plan_id="plan_evidence_missing",
            mode="template_customize",
            prompt="Use the uploaded menu.",
            user_variables={"reference_delivery": contract},
        ),
        created_at=now,
        updated_at=now,
    )
    output = ImageOutput(
        output_id="out_evidence_missing",
        job_id=job.job_id,
        url="/api/v2/test.png",
        metadata={"storage_path": str(path), "live": True},
        created_at=now,
    )
    reviewed = apply_reference_delivery_review(
        output,
        job,
        ImageReviewDecision(
            review_id="review_evidence_missing",
            output_id=output.output_id,
            decision="pass",
            score=0.9,
            created_at=now,
        ),
    )

    assert reviewed.decision == "needs_review"
    assert "source_text_evidence_unavailable" in reviewed.detected_risks


def test_source_text_evidence_groups_confident_ocr_words(monkeypatch) -> None:
    class FakeOutput:
        DICT = object()

    class FakeTesseract:
        @staticmethod
        def image_to_data(*_args, **_kwargs):
            return {
                "text": ["Lunch", "set", "", "¥38"],
                "conf": [94, 90, -1, 91],
                "block_num": [1, 1, 1, 1],
                "par_num": [1, 1, 1, 1],
                "line_num": [1, 1, 1, 2],
                "page_num": [1, 1, 1, 1],
            }

    monkeypatch.setattr(
        "app.services.source_text_evidence._tesseract_backend",
        lambda: (FakeTesseract, FakeOutput, "eng"),
    )

    evidence, receipt = extract_source_text_evidence(object())

    assert [item["text"] for item in evidence] == ["Lunch set", "¥38"]
    assert receipt["status"] == "extracted"


def test_overlay_receipt_can_verify_explicit_source_fields_without_modifying_unknown_layout() -> None:
    contract = build_reference_delivery_contract(_composite_context())
    original = b"not-an-image-but-overlay-is-not-configured"
    content, receipt = apply_deterministic_text_overlay(
        original,
        delivery_contract=contract,
        output_format="png",
    )

    assert content == original
    assert receipt == {"applied": False, "reason": "no_explicit_overlay_slots", "verified_field_ids": []}

    review = ImageReviewDecision(
        review_id="review_retry",
        output_id="out_retry",
        decision="needs_review",
        detected_risks=["required_source_text_unverified"],
        created_at=utc_now(),
    )
    retry = build_semantic_retry_directive(review, contract)
    assert retry["eligible"] is True
    assert retry["remaining_attempts"] == 1


def test_review_persists_safe_semantic_retry_receipt(tmp_path) -> None:
    contract = build_reference_delivery_contract(_composite_context())
    path = tmp_path / "output.png"
    Image.new("RGB", (64, 48), "white").save(path)
    now = utc_now()
    job = ImageJob(
        job_id="job_retry_receipt",
        status="completed",
        provider_id="test_provider",
        model="test_model",
        prompt_plan=ImagePromptPlan(
            plan_id="plan_retry_receipt",
            mode="template_customize",
            prompt="Use the uploaded menu.",
            negative_prompt="watermark",
            user_variables={"reference_delivery": contract},
        ),
        outputs=[
            ImageOutput(
                output_id="out_retry_receipt",
                job_id="job_retry_receipt",
                url="/api/v2/test.png",
                metadata={"storage_path": str(path), "live": True},
                created_at=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )

    reviewed = review_image_job(job)
    retry = reviewed.outputs[0].metadata["reference_delivery_retry"]

    assert retry["eligible"] is True
    assert retry["retry_scope"] == "reference_delivery_repair"
