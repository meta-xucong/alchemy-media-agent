"""Check telemetry opt-outs without importing OCR or initializing inference."""

import os


def test_optional_runtime_telemetry_is_disabled_before_test_imports():
    assert os.environ["ORT_DISABLE_TELEMETRY"] == "1"
    assert os.environ["OPENAI_AGENTS_DISABLE_TRACING"] == "1"
