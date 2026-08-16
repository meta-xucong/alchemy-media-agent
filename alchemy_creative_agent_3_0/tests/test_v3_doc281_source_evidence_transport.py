from __future__ import annotations

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.project_mode.source_evidence import (
    OpenAICompatibleSourceEvidenceAnalyzer,
    SEMANTIC_AFFORDANCES,
    SEMANTIC_SUBJECT_KINDS,
    SEMANTIC_VIEW_KINDS,
    semantic_analysis_instruction,
    semantic_response_from_text,
)


def _front_observation_text() -> str:
    return (
        '{"evidence_state":"observed","subject_kind":"object_or_product",'
        '"view_kind":"front","affordances":["object_front_presentation"]}'
    )


def test_doc281_source_evidence_instruction_names_exact_closed_vocabulary() -> None:
    instruction = semantic_analysis_instruction()

    assert "plain JSON only" in instruction
    assert "Choose exactly one primary affordance" in instruction
    for value in ("observed", *SEMANTIC_SUBJECT_KINDS, *SEMANTIC_VIEW_KINDS, *SEMANTIC_AFFORDANCES):
        assert value in instruction
    for forbidden in ("filename", "project", "prompt", "private identifiers"):
        assert forbidden in instruction


def test_doc281_source_evidence_text_parser_accepts_only_complete_closed_json() -> None:
    raw = "Result:\n```json\n" + _front_observation_text() + "\n```\n"

    assert semantic_response_from_text(raw) == {
        "evidence_state": "observed",
        "subject_kind": "object_or_product",
        "view_kind": "front",
        "affordances": ["object_front_presentation"],
    }


@pytest.mark.parametrize(
    "raw",
    [
        '{"evidence_state":"directly_observed_physical_ex"',
        (
            '{"evidence_state":"observed","subject_kind":"object_or_product",'
            '"view_kind":"front","affordances":["object_front_presentation"],"asset_id":"browser"}'
        ),
        (
            '{"evidence_state":"observed","subject_kind":"product",'
            '"view_kind":"front","affordances":["object_front_presentation"]}'
        ),
    ],
)
def test_doc281_source_evidence_text_parser_rejects_incomplete_private_or_invented_values(raw: str) -> None:
    with pytest.raises(ValueError, match="source_evidence_response_invalid"):
        semantic_response_from_text(raw)


def test_doc281_chat_source_evidence_call_uses_strict_instruction_and_temperature_zero() -> None:
    calls: list[dict[str, object]] = []

    class _Completions:
        def create(self, **kwargs: object) -> object:
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="```json\n" + _front_observation_text() + "\n```")
                    )
                ]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    analyzer = OpenAICompatibleSourceEvidenceAnalyzer(
        api_key="key",
        base_url="https://example.invalid/v1",
        model="vision",
        preferred_protocol="chat",
    )

    assert analyzer._call(client, "data:image/png;base64,AAAA") == {
        "evidence_state": "observed",
        "subject_kind": "object_or_product",
        "view_kind": "front",
        "affordances": ["object_front_presentation"],
    }
    assert calls
    assert calls[0]["temperature"] == 0
    message = calls[0]["messages"][0]["content"][0]["text"]  # type: ignore[index]
    assert "Allowed subject_kind values: object_or_product, person, brand_or_graphic." in message
    assert "Allowed affordances values: object_front_presentation" in message
