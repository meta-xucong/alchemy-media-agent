"""Focused contracts for Doc294 Brain source projection and finalization binding."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompt_policy import (
    V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV,
    V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV,
    brain_source_projection_sha256,
    build_brain_source_projection_receipt,
    build_brain_source_projection,
    validate_brain_source_projection_receipt,
)
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import BrainPromptContractInvalid
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import photography_capability_policy


PREVIOUS_PROMPT = (
    "超写实真人摄影，竖版约3:4，一名明确成年的年轻东亚女性，在中国大型会员制仓储超市的进口酒水区域蹲下挑选商品，并拿起一瓶琥珀色瓶装饮品向镜头展示。"
)


def _projection() -> dict:
    return build_brain_source_projection(
        requested_image_count=2,
        prompt_guidance={
            "optimized_direction": "A natural camera-observed portrait with coherent light.",
            "visual_direction_addons": ["preserve the requested mood"],
            "style_notes": ["real lens rendering"],
            "layout_notes": ["keep the subject readable"],
            "hard_constraints": ["preserve the declared aspect"],
            "negative_prompt_addons": ["avoid synthetic skin"],
            "consistency_strategy": "same person, distinct camera moments",
        },
        image_set_plan={
            "set_goal": "Two distinct but coherent outputs.",
            "image_count": 2,
            "size": "1024x1536",
            "aspect_ratio": "2:3",
            "shot_plan": ["front three-quarter", "quiet side profile"],
            "evidence_dimensions_by_output": [],
            "composition_rules": ["preserve subject hierarchy"],
            "quality_bar": ["credible photographic materiality"],
        },
    )


def _record(projection: dict, output_index: int = 1, prompt: str | None = None) -> dict:
    return {
        "output_index": output_index,
        "prompt": prompt or "A complete natural camera-rendered portrait with the requested scene and mood.",
        "review_status": "approved",
        "prompt_status": "complete",
        "semantic_coverage": "complete",
        "compression_decision": "none",
        "compression_receipt": None,
        "source_projection_receipt": build_brain_source_projection_receipt(
            projection,
            output_index=output_index,
            requested_image_count=projection["requested_image_count"],
        ),
    }


class _FinalizerProvider:
    provider = "test_brain"
    model = "test-model"

    def __init__(self, records: list[dict]) -> None:
        self.records = records
        self.calls: list[BrainRunRequest] = []

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request: BrainRunRequest) -> dict:
        self.calls.append(request)
        return {"canonical_provider_prompts": self.records}


def _request(projection: dict, *, records: list[dict]) -> BrainRunRequest:
    return BrainRunRequest(
        user_input="Keep the requested scene and make two coherent photographic outputs.",
        stage="provider_prompt_finalize",
        scenario_id="photography",
        template_id="photographer_template",
        requested_image_count=2,
        template_capability_policy=photography_capability_policy(),
        metadata={
            "canonical_prompt_context": {"brain_source_projection": projection},
            "unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV,
            "brain_source_projection_required": True,
            "brain_source_projection_contract_version": V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV,
            "brain_source_projection_digest": projection["source_digest"],
            "brain_source_projection_binding_digest": projection["source_binding"]["binding_digest"],
            "brain_source_projection_requested_image_count": 2,
            "_test_records": records,
        },
    )


def test_projection_digest_covers_all_brain_guidance_and_image_plan_fields() -> None:
    projection = _projection()
    assert projection["source_digest"] == brain_source_projection_sha256(projection)
    assert set(projection["prompt_guidance"]) == {
        "optimized_direction",
        "visual_direction_addons",
        "style_notes",
        "layout_notes",
        "hard_constraints",
        "negative_prompt_addons",
        "consistency_strategy",
    }
    assert set(projection["image_set_plan"]) == {
        "set_goal",
        "image_count",
        "size",
        "aspect_ratio",
        "shot_plan",
        "evidence_dimensions_by_output",
        "composition_rules",
        "quality_bar",
    }


def test_payload_exposes_complete_source_projection_and_typed_receipt_schema() -> None:
    projection = _projection()
    request = _request(projection, records=[_record(projection), _record(projection, 2)])
    payload = json.loads(build_remote_payload(request))

    projected = payload["frozen_render_context"]["brain_source_projection"]
    assert projected == projection
    schema = payload["return_schema"]["canonical_provider_prompts"][0]
    assert schema["source_projection_receipt"]["contract_version"] == V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV
    assert "complete server-owned Brain semantic source" in payload["remote_response_contract"]


def test_valid_source_projection_receipts_bind_each_output_index() -> None:
    projection = _projection()
    provider = _FinalizerProvider([_record(projection), _record(projection, 2)])
    prompts, audit = V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(
        _request(projection, records=provider.records)
    )

    assert [item.output_index for item in prompts] == [1, 2]
    assert audit["brain_source_projection_receipts"] == ["valid", "valid"]


def test_previous_prompt_survives_complete_source_projection_finalization() -> None:
    projection = _projection()
    provider = _FinalizerProvider([_record(projection, prompt=PREVIOUS_PROMPT), _record(projection, 2)])
    request = _request(projection, records=provider.records).model_copy(
        update={"user_input": PREVIOUS_PROMPT},
        deep=True,
    )

    prompts, audit = V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(request)

    assert prompts[0].prompt == PREVIOUS_PROMPT
    assert audit["unified_prompt_compression_decisions"] == ["none", "none"]
    assert audit["brain_source_projection_receipts"] == ["valid", "valid"]


@pytest.mark.parametrize(
    "field",
    ["source_digest", "output_index", "requested_image_count", "contract_version", "owner", "receipt_digest"],
)
def test_wrong_source_projection_receipt_fails_closed(field: str) -> None:
    projection = _projection()
    record = _record(projection)
    if field == "source_digest":
        record["source_projection_receipt"][field] = "0" * 64
    elif field == "output_index":
        record["source_projection_receipt"][field] = 2
    elif field == "requested_image_count":
        record["source_projection_receipt"][field] = 1
    elif field == "contract_version":
        record["source_projection_receipt"][field] = "old"
    elif field == "receipt_digest":
        record["source_projection_receipt"][field] = "0" * 64
    else:
        record["source_projection_receipt"][field] = "local"
    provider = _FinalizerProvider([record])
    request = _request(projection, records=provider.records)
    with pytest.raises(BrainPromptContractInvalid):
        V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(request)


def test_missing_source_projection_receipt_fails_closed_for_fresh_request() -> None:
    projection = _projection()
    record = _record(projection)
    record.pop("source_projection_receipt")
    provider = _FinalizerProvider([record, _record(projection, 2)])
    with pytest.raises(BrainPromptContractInvalid):
        V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(
            _request(projection, records=provider.records)
        )


def test_tampered_source_binding_fails_closed_before_provider_acceptance() -> None:
    projection = _projection()
    tampered = deepcopy(projection)
    tampered["source_binding"]["policy_revision"] = "superseded-policy"
    provider = _FinalizerProvider([_record(projection), _record(projection, 2)])
    request = _request(projection, records=provider.records)
    request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "canonical_prompt_context": {"brain_source_projection": tampered},
            }
        }
    )
    with pytest.raises(BrainPromptContractInvalid):
        V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(request)


def test_short_rich_prompt_does_not_trigger_compression() -> None:
    projection = _projection()
    prompt = "保留完整场景、人物关系、真实镜头光线、材质和构图，不要删减用户方向。"
    record = _record(projection, prompt=prompt)
    valid, reason = validate_brain_source_projection_receipt(
        record,
        required=True,
        expected_digest=projection["source_digest"],
        expected_output_index=1,
        expected_requested_image_count=2,
    )
    assert (valid, reason) == (True, "source_projection_receipt_valid")
    assert record["compression_decision"] == "none"
