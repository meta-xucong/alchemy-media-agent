import os
from pathlib import Path
import tempfile
import uuid

# Mock-provider tests must not export SDK/native telemetry. CI and documented
# local commands also set these before the Python interpreter starts.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

# Keep the suite offline even when the developer machine has a live Bridge
# config and credentials. Bridge-specific tests provide temporary configs or fakes.
_TEST_BRIDGE_ROOT = Path(tempfile.gettempdir()) / f"alchemy-tests-bridge-{os.getpid()}-{uuid.uuid4().hex}"
os.environ["ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG"] = str(_TEST_BRIDGE_ROOT / "disabled-control.json")
os.environ["ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT"] = str(_TEST_BRIDGE_ROOT / "state")
os.environ["ALCHEMY_RENDER_BRIDGE_MODE"] = "disabled"
os.environ["ALCHEMY_RENDER_BRIDGE_STORAGE"] = str(_TEST_BRIDGE_ROOT / "preview")
for _bridge_env_name in (
    "ALCHEMY_RENDER_BRIDGE_PRIMARY_TOKEN",
    "ALCHEMY_RENDER_BRIDGE_TOKEN",
    "ALCHEMY_RENDER_BRIDGE_URL",
    "ALCHEMY_RENDER_BRIDGE_WORKSPACE",
    "ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK",
    "ALCHEMY_RENDER_BRIDGE_CA_BUNDLE",
    "ALCHEMY_RENDER_BRIDGE_REWARD_READ_TOKEN",
    "ALCHEMY_RENDER_BRIDGE_PROFILES",
    "ALCHEMY_RENDER_BRIDGE_NATIVE_ENABLED",
    "ALCHEMY_RENDER_BRIDGE_NATIVE_PROFILES",
):
    os.environ.pop(_bridge_env_name, None)

for _provider_env_name in (
    "LLM_GATEWAY_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "DEEPSEEK_LLM_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_IMAGE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "BYTEPLUS_API_KEY",
    "DOUBAO_IMAGE_API_KEY",
    "V2_DOUBAO_IMAGE_API_KEY",
    "V2_DOUBAO_VISION_API_KEY",
    "LAB_DOUBAO_VISION_API_KEY",
    "V2_GEMINI_API_KEY",
    "V2_OPENAI_API_KEY",
    "LAB_OPENAI_API_KEY",
    "LAB_KIMI_API_KEY",
    "V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN",
    "VEYRA_INTERNAL_TOKEN",
    "ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_API_KEY",
):
    os.environ[_provider_env_name] = ""

import pytest

os.environ["CODEX_AUTH_FILE"] = str(Path(__file__).parent / ".missing_auth.json")
os.environ["CLAUDE_SETTINGS_FILE"] = str(Path(__file__).parent / ".missing_claude_settings.json")
os.environ["V3_LLM_BRAIN_REMOTE_ENABLED"] = "false"
os.environ["LLM_PROMPT_PLANNING_ENABLED"] = "false"
os.environ["MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS"] = "false"
os.environ["MEDIA_AGENT_MODE"] = "mock"
os.environ["MOCK_IMAGE_PROVIDER_ENABLED"] = "true"


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
