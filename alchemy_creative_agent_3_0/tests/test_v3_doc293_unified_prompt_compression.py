"""Focused contract tests for Doc293's single canonical prompt policy."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.generation_router.providers import ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.generation_router.providers import ProviderRuntimeError
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompt_policy import (
    V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV,
    V3_UNIFIED_PROMPT_COMPRESSION_TARGET_MAX_CHARS,
    V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS,
    canonical_prompt_sha256,
    validate_unified_prompt_record,
)
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import BrainPromptContractInvalid
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import photography_capability_policy


PREVIOUS_PROMPT = (
    "超写实真人摄影，竖版约3:4，一名明确成年的年轻东亚女性，在中国大型会员制仓储超市的进口酒水区域蹲下挑选商品，并拿起一瓶琥珀色瓶装饮品向镜头展示。"
)


def _record(prompt: str, *, decision: str = "none", receipt: dict | None = None) -> dict:
    return {
        "output_index": 1,
        "prompt": prompt,
        "review_status": "approved",
        "prompt_status": "complete",
        "semantic_coverage": "complete",
        "compression_decision": decision,
        "compression_receipt": receipt,
    }


def _compressed_record(prompt: str = "自然光下的真实相机人像，保留完整场景、主体关系与自然材质。") -> dict:
    return _record(
        prompt,
        decision="brain_semantic_once",
        receipt={
            "contract_version": "v3_prompt_compression_receipt_v1",
            "policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV,
            "decision": "brain_semantic_once",
            "source_chars": V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS + 1,
            "final_chars": len(prompt),
            "final_prompt_sha256": canonical_prompt_sha256(prompt),
            "semantic_status": "complete",
            "owner": "remote_v3_llm_brain",
        },
    )


def test_previous_prompt_is_lossless_in_brain_request_and_policy_is_not_payload_compression() -> None:
    request = BrainRunRequest(
        user_input=PREVIOUS_PROMPT,
        stage="provider_prompt_finalize",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {},
            "unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV,
        },
    )

    payload = build_remote_payload(request)

    assert PREVIOUS_PROMPT in payload
    assert '"user_input": "' in payload
    assert '"compression_threshold_chars": 6000' in payload
    assert '"compression_target_max_chars": 3500' in payload
    assert '"do_not_apply_to": "brain_request_payload_or_token_budget"' in payload


def test_provider_audit_uses_brain_semantic_receipt_for_canonical_prompt() -> None:
    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    audit = provider._provider_prompt_audit(  # noqa: SLF001
        "A complete canonical direction that is not a literal copy.",
        "The original user direction.",
        prompt_source="remote_brain_canonical",
        user_direction_integrity={"status": "preserved"},
    )

    assert audit["user_direction_lossless"] is True
    assert audit["user_direction_literal_in_prompt"] is False
    assert audit["user_direction_semantic_status"] == "preserved"


@pytest.mark.parametrize("length", [V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS - 1, V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS])
def test_prompt_at_or_below_threshold_is_sent_unchanged(length: int) -> None:
    prompt = "A" * length
    valid, reason, decision = validate_unified_prompt_record(_record(prompt), required=True)

    assert (valid, reason, decision) == (True, "none", "none")


def test_unicode_prompt_uses_character_threshold_and_utf8_safe_envelope() -> None:
    prompt = "人" * V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS
    valid, reason, decision = validate_unified_prompt_record(_record(prompt), required=True)

    assert (valid, reason, decision) == (True, "none", "none")
    assert len(prompt) == V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS
    assert len(prompt.encode("utf-8")) <= 4 * V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS


def test_over_threshold_requires_one_brain_receipt_and_target() -> None:
    valid, reason, decision = validate_unified_prompt_record(_compressed_record(), required=True)

    assert (valid, reason, decision) == (True, "brain_semantic_once", "brain_semantic_once")
    assert len(_compressed_record()["prompt"]) <= V3_UNIFIED_PROMPT_COMPRESSION_TARGET_MAX_CHARS


@pytest.mark.parametrize(
    "mutator,expected_reason",
    [
        (lambda record: record.pop("compression_receipt"), "compression_receipt_missing"),
        (
            lambda record: record["compression_receipt"].update({"final_prompt_sha256": "0" * 64}),
            "compression_receipt_binding_invalid",
        ),
        (
            lambda record: record["compression_receipt"].update({"final_chars": 3501}),
            "compression_receipt_binding_invalid",
        ),
        (lambda record: record.update({"semantic_coverage": None}), "semantic_coverage_incomplete"),
    ],
)
def test_invalid_receipt_or_incomplete_semantics_fail_closed(mutator, expected_reason: str) -> None:
    record = _compressed_record()
    mutator(record)

    valid, reason, decision = validate_unified_prompt_record(record, required=True)

    assert valid is False
    assert reason == expected_reason
    assert decision == "blocked"


class _FinalizerProvider:
    provider = "test_brain"
    model = "test-model"

    def __init__(self, record: dict) -> None:
        self.record = record
        self.calls: list[BrainRunRequest] = []

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request: BrainRunRequest) -> dict:
        self.calls.append(request)
        return {"canonical_provider_prompts": [self.record]}


def _finalizer_request() -> BrainRunRequest:
    return BrainRunRequest(
        user_input=PREVIOUS_PROMPT,
        stage="provider_prompt_finalize",
        scenario_id="photography",
        template_id="photographer_template",
        requested_image_count=1,
        template_capability_policy=photography_capability_policy(),
        metadata={
            "canonical_prompt_context": {},
            "unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV,
        },
    )


def test_adapter_accepts_short_signed_prompt_without_second_compression_call() -> None:
    provider = _FinalizerProvider(_record(PREVIOUS_PROMPT))

    prompts, audit = V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(
        _finalizer_request()
    )

    assert len(provider.calls) == 1
    assert prompts[0].prompt == PREVIOUS_PROMPT
    assert audit["unified_prompt_compression_decisions"] == ["none"]


@pytest.mark.parametrize("bad_output_index", ["1", 1.0, True])
def test_adapter_rejects_non_integer_canonical_output_index(bad_output_index) -> None:
    record = _record(PREVIOUS_PROMPT)
    record["output_index"] = bad_output_index
    provider = _FinalizerProvider(record)

    with pytest.raises(BrainPromptContractInvalid):
        V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(_finalizer_request())


def test_adapter_preserves_exact_brain_prompt_whitespace() -> None:
    prompt = "真实相机人像。\n\n保留原始换行、双空格  与中文标点。"
    provider = _FinalizerProvider(_record(prompt))

    prompts, _audit = V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(
        _finalizer_request()
    )

    assert prompts[0].prompt == prompt


def test_adapter_accepts_brain_compressed_prompt_only_with_bound_receipt() -> None:
    provider = _FinalizerProvider(_compressed_record())

    prompts, audit = V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(
        _finalizer_request()
    )

    assert len(provider.calls) == 1
    assert prompts[0].prompt == _compressed_record()["prompt"]
    assert audit["unified_prompt_compression_decisions"] == ["brain_semantic_once"]


def test_adapter_rejects_missing_compression_receipt_without_fallback() -> None:
    record = _compressed_record()
    record.pop("compression_receipt")
    provider = _FinalizerProvider(record)

    with pytest.raises(BrainPromptContractInvalid):
        V3LLMBrainAdapter(provider=provider).finalize_canonical_provider_prompts(_finalizer_request())
    assert len(provider.calls) == 1


def test_provider_returns_brain_signed_prompt_exactly_without_local_rewrite() -> None:
    prompt = "第一句。\n第二句，保留原始空白。"
    record = _record(prompt)
    llm_brain = {
        "audit": {"unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV},
        "canonical_provider_prompts": [record],
    }
    request = SimpleNamespace(
        metadata={"llm_brain": llm_brain},
        generation_plan=SimpleNamespace(metadata={"output_index": 0}),
    )

    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    assert provider._brain_signed_provider_prompt(request) == prompt  # noqa: SLF001


def test_provider_canonical_path_does_not_call_legacy_compactor() -> None:
    prompt = PREVIOUS_PROMPT
    request = SimpleNamespace(
        metadata={
            "llm_brain": {
                "audit": {
                    "unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV
                },
                "canonical_provider_prompts": [_record(prompt)],
            }
        },
        generation_plan=SimpleNamespace(metadata={"output_index": 0}),
    )
    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())
    provider._provider_prompt_for_delivery = lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: SLF001
        AssertionError("canonical prompt must bypass the legacy local compactor")
    )

    assert provider._generation_prompt(request, [], asset_plan={}) == prompt  # noqa: SLF001


def test_provider_rejects_invalid_unified_record_and_overlong_transport() -> None:
    invalid_record = _record("A" * (V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS + 1))
    request = SimpleNamespace(
        metadata={
            "llm_brain": {
                "audit": {
                    "unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV
                },
                "canonical_provider_prompts": [invalid_record],
            }
        },
        generation_plan=SimpleNamespace(metadata={"output_index": 0}),
    )
    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    assert provider._brain_signed_provider_prompt(request) == ""  # noqa: SLF001
    with pytest.raises(ProviderRuntimeError):
        provider._assert_canonical_prompt_fits_transport(  # noqa: SLF001
            "A" * (V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS + 1),
            request=request,
        )


def test_unified_policy_rejects_route_with_lower_transport_cap(monkeypatch) -> None:
    request = SimpleNamespace(
        metadata={
            "llm_brain": {
                "audit": {
                    "unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV
                }
            }
        }
    )
    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())
    monkeypatch.setattr(provider, "_transport_prompt_char_cap", lambda: 1800)  # noqa: SLF001

    with pytest.raises(ProviderRuntimeError) as exc_info:
        provider._assert_canonical_prompt_fits_transport(PREVIOUS_PROMPT, request=request)  # noqa: SLF001

    assert exc_info.value.detail["failure_code"] == "canonical_provider_prompt_transport_capability_unsupported"


def test_invalid_utf8_prompt_fails_closed_as_provider_contract() -> None:
    request = SimpleNamespace(
        metadata={
            "llm_brain": {
                "audit": {
                    "unified_prompt_compression_policy_revision": V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV
                }
            }
        }
    )
    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    with pytest.raises(ProviderRuntimeError) as exc_info:
        provider._assert_canonical_prompt_fits_transport("\ud800", request=request)  # noqa: SLF001

    assert exc_info.value.detail["failure_code"] == "canonical_provider_prompt_invalid_utf8"
