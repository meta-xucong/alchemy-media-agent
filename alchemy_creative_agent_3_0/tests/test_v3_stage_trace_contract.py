"""Focused regression coverage for the public-safe Brain stage trace."""

from __future__ import annotations

import json

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.stage_trace import record_stage_event


_LIFECYCLE_BOOLEAN_FIELDS = (
    "response_started",
    "first_content_observed",
    "reasoning_content_observed",
    "complete_response_observed",
    "json_parse_started",
    "json_parse_completed",
    "json_serialization_recovery_attempted",
    "json_serialization_recovery_succeeded",
    "cardinality_valid",
    "semantic_recovery_attempted",
    "protocol_fallback_attempted",
)


def _record(tmp_path, monkeypatch, extra: dict[str, object]) -> dict[str, object]:
    trace_file = tmp_path / "stage-trace.jsonl"
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))

    record_stage_event("brain_provider", "test_event", stage="plan", extra=extra)

    return json.loads(trace_file.read_text(encoding="utf-8").splitlines()[0])


@pytest.mark.parametrize("field", _LIFECYCLE_BOOLEAN_FIELDS)
@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_stage_trace_drops_non_boolean_lifecycle_values(tmp_path, monkeypatch, field, value) -> None:
    record = _record(
        tmp_path,
        monkeypatch,
        {field: value, "requested_image_count": 1},
    )

    assert field not in record
    assert record["requested_image_count"] == 1


def test_stage_trace_drops_response_facts_without_a_started_response(tmp_path, monkeypatch) -> None:
    record = _record(
        tmp_path,
        monkeypatch,
        {
            "response_started": False,
            "first_content_observed": True,
            "reasoning_content_observed": True,
            "complete_response_observed": True,
            "json_parse_started": True,
            "json_parse_completed": True,
        },
    )

    assert record["response_started"] is False
    for field in (
        "first_content_observed",
        "reasoning_content_observed",
        "complete_response_observed",
        "json_parse_started",
        "json_parse_completed",
    ):
        assert field not in record


def test_stage_trace_drops_parse_completion_without_parse_start(tmp_path, monkeypatch) -> None:
    record = _record(
        tmp_path,
        monkeypatch,
        {
            "response_started": True,
            "json_parse_started": False,
            "json_parse_completed": True,
        },
    )

    assert record["response_started"] is True
    assert record["json_parse_started"] is False
    assert "json_parse_completed" not in record


@pytest.mark.parametrize("acceptance", ["not_started", "unknown"])
def test_stage_trace_drops_acceptance_that_conflicts_with_response(
    tmp_path,
    monkeypatch,
    acceptance,
) -> None:
    record = _record(
        tmp_path,
        monkeypatch,
        {"request_acceptance": acceptance, "response_started": True},
    )

    assert record["response_started"] is True
    assert "request_acceptance" not in record


@pytest.mark.parametrize("acceptance", [False, True, 0, 1, None, []])
def test_stage_trace_drops_non_string_request_acceptance(tmp_path, monkeypatch, acceptance) -> None:
    record = _record(
        tmp_path,
        monkeypatch,
        {"request_acceptance": acceptance},
    )

    assert "request_acceptance" not in record


def test_stage_trace_preserves_reasoning_only_complete_response(tmp_path, monkeypatch) -> None:
    record = _record(
        tmp_path,
        monkeypatch,
        {
            "request_acceptance": "dispatched",
            "response_started": True,
            "reasoning_content_observed": True,
            "first_content_observed": False,
            "complete_response_observed": True,
        },
    )

    assert record["request_acceptance"] == "dispatched"
    assert record["response_started"] is True
    assert record["reasoning_content_observed"] is True
    assert record["first_content_observed"] is False
    assert record["complete_response_observed"] is True
