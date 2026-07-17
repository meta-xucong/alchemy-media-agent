from __future__ import annotations

from app.repositories.memory import utc_now
from app.schemas import ImageJob, ImageOutput, ImagePromptPlan
from app.services.intent_integrity import compile_prompt_artifact, preflight_prompt_integrity
from app.services.output_review import review_output


def test_compiler_keeps_required_tail_and_reports_unsatisfied_budget() -> None:
    user_prompt = "用户原始意图 " + ("A" * 96) + " REQUIRED_USER_TAIL"
    claude_prompt = "Claude 创意决策 " + ("B" * 96) + " REQUIRED_CLAUDE_TAIL"

    prompt, trace = compile_prompt_artifact(
        user_prompt=user_prompt,
        creative_prompt=claude_prompt,
        creative_source="claude_final_prompt",
        budget_chars=80,
    )

    assert user_prompt in prompt
    assert claude_prompt in prompt
    assert prompt.endswith("REQUIRED_CLAUDE_TAIL")
    assert trace["manifest"]["budget_satisfied"] is False
    assert trace["manifest"]["required_intent_ids"] == ["intent_user_request", "intent_creative_decision"]
    assert trace["manifest"]["included_intent_ids"] == ["intent_user_request", "intent_creative_decision"]


def test_preflight_rejects_missing_required_reference() -> None:
    prompt, trace = compile_prompt_artifact(
        user_prompt="Use the uploaded product as the subject.",
        creative_prompt="Use the product reference faithfully.",
        creative_source="claude_final_prompt",
        asset_sections=[
            {
                "asset_id": "asset_required_product",
                "role": "subject_reference",
                "constraint_strength": "required",
                "provider_input_required": True,
                "reference_index": 1,
                "prompt_instruction": "Use Image 1 as the concrete product subject.",
            }
        ],
    )

    result = preflight_prompt_integrity(
        trace=trace,
        effective_prompt=prompt,
        input_images=[],
        provider_input_plan={
            "requires_image_reference": True,
            "reference_image_asset_ids": ["asset_required_product"],
        },
    )

    assert result["preflight"]["status"] == "failed"
    assert result["preflight"]["code"] == "required_reference_missing"


def test_preflight_records_effective_payload_when_contract_is_complete() -> None:
    prompt, trace = compile_prompt_artifact(
        user_prompt="Use the uploaded product as the subject.",
        creative_prompt="Use the product reference faithfully.",
        creative_source="claude_final_prompt",
        asset_sections=[
            {
                "asset_id": "asset_required_product",
                "role": "subject_reference",
                "constraint_strength": "required",
                "provider_input_required": True,
                "reference_index": 1,
                "prompt_instruction": "Use Image 1 as the concrete product subject.",
            }
        ],
    )

    result = preflight_prompt_integrity(
        trace=trace,
        effective_prompt=prompt,
        input_images=[{"asset_id": "asset_required_product", "reference_index": 1}],
        provider_input_plan={
            "requires_image_reference": True,
            "reference_image_asset_ids": ["asset_required_product"],
        },
    )

    assert result["preflight"]["status"] == "passed"
    assert result["effective_payload_hash"]
    assert result["effective_payload_length"] == len(prompt)


def test_preflight_rejects_reference_index_drift() -> None:
    prompt, trace = compile_prompt_artifact(
        user_prompt="Use Image 1 as the product and Image 2 as the logo.",
        creative_prompt="Keep each reference in its declared role.",
        creative_source="claude_final_prompt",
    )

    result = preflight_prompt_integrity(
        trace=trace,
        effective_prompt=prompt,
        input_images=[
            {"asset_id": "asset_product", "reference_index": 2},
            {"asset_id": "asset_logo", "reference_index": 1},
        ],
        provider_input_plan={
            "requires_image_reference": True,
            "reference_image_asset_ids": ["asset_product", "asset_logo"],
        },
    )

    assert result["preflight"]["status"] == "failed"
    assert result["preflight"]["code"] == "reference_index_mismatch"


def test_live_reference_output_is_not_marked_adherent_without_pixel_review() -> None:
    now = utc_now()
    prompt_plan = ImagePromptPlan(
        plan_id="plan_reference_review",
        mode="template_customize",
        prompt="Use Image 1 as the product reference.",
        negative_prompt="watermark",
        user_variables={
            "provider_input_plan": {
                "requires_image_reference": True,
                "reference_image_count": 1,
                "reference_image_asset_ids": ["asset_product"],
            }
        },
    )
    job = ImageJob(
        job_id="job_reference_review",
        status="completed",
        provider_id="test_provider",
        model="test_model",
        prompt_plan=prompt_plan,
        created_at=now,
        updated_at=now,
    )
    output = ImageOutput(
        output_id="output_reference_review",
        job_id=job.job_id,
        url="/api/v2/test-output.png",
        metadata={"live": True, "input_images": [{"asset_id": "asset_product", "reference_index": 1}]},
        created_at=now,
    )

    review = review_output(output, job)

    assert review.decision == "needs_review"
    assert "reference_adherence_unverified" in review.detected_risks
