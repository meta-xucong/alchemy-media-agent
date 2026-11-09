from __future__ import annotations

from app.services.access_bridge import verify_access_headers
from scripts.guarded_v2_sync_review_queue import _headers
from scripts.guarded_vision_model_acceptance import _attempt_summary


def test_review_queue_sync_headers_use_the_v2_access_bridge_signature():
    path = "/api/v2/runtime/model-settings"
    headers = _headers("local-test-secret", user_id=17, method="POST", path=path)

    verified = verify_access_headers(
        headers,
        method="POST",
        path=path,
        secret="local-test-secret",
    )

    assert verified is not None
    assert verified["surfaces"] == ["v2"]
    assert verified["user_id"] == 17


def test_candidate_acceptance_logs_only_allowlisted_diagnostics():
    summary = _attempt_summary([{
        "model": "kimi-k3",
        "outcome": "failed",
        "failure_code": "review_incomplete",
        "provider_reason": "length",
        "provider_usage": {"completion_tokens": 1024},
        "elapsed_ms": 12_345,
        "response_text": "private model response",
        "prompt": "private user prompt",
        "credential": "private credential",
    }])

    assert summary == [{
        "model": "kimi-k3",
        "outcome": "failed",
        "failure_code": "review_incomplete",
        "provider_reason": "length",
        "provider_usage": {"completion_tokens": 1024},
        "elapsed_ms": 12_345,
    }]
