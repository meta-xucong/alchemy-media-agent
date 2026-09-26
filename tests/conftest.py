import os
from pathlib import Path

import pytest

os.environ["CODEX_AUTH_FILE"] = str(Path(__file__).parent / ".missing_auth.json")
os.environ["CLAUDE_SETTINGS_FILE"] = str(Path(__file__).parent / ".missing_claude_settings.json")
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_AUTH_TOKEN"] = ""
os.environ["LLM_PROMPT_PLANNING_ENABLED"] = "false"
os.environ["MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS"] = "false"
os.environ.setdefault("MEDIA_AGENT_MODE", "mock")
os.environ.setdefault("MOCK_IMAGE_PROVIDER_ENABLED", "true")


@pytest.fixture(autouse=True)
def _doc134_remote_brain_contract(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give Doc134 tests an explicit remote Brain double without changing production defaults."""

    test_name = Path(str(getattr(request.node, "fspath", ""))).name
    if test_name in {
        "test_doc134_codex_native_professional_relay.py",
        "test_doc134_professional_body_projection_modules.py",
    }:
        monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
        monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
        monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
