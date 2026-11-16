"""Pytest collection guards for V3-owned test artifacts."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import uuid

# V3 tests must not inherit production Bridge or model credentials.
_TEST_BRIDGE_ROOT = Path(tempfile.gettempdir()) / f"alchemy-v3-tests-bridge-{os.getpid()}-{uuid.uuid4().hex}"
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

os.environ["CODEX_AUTH_FILE"] = str(_TEST_BRIDGE_ROOT / "missing-auth.json")
os.environ["CLAUDE_SETTINGS_FILE"] = str(_TEST_BRIDGE_ROOT / "missing-claude-settings.json")
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
os.environ["V3_LLM_BRAIN_REMOTE_ENABLED"] = "false"
os.environ["LLM_PROMPT_PLANNING_ENABLED"] = "false"
os.environ["MEDIA_AGENT_MODE"] = "mock"
os.environ["MOCK_IMAGE_PROVIDER_ENABLED"] = "true"
os.environ["MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS"] = "false"
os.environ["VEYRA_AUTH_ENABLED"] = "false"
os.environ["VEYRA_REQUIRE_UI_AUTH"] = "false"
os.environ["V3_VISION_INSPECTION_ENABLED"] = "false"
os.environ["LAB_LLM_ENABLED"] = "false"
os.environ["LAB_VISION_ENABLED"] = "false"
os.environ["GEMINI_IMAGE_GENERATION_ENABLED"] = "false"
os.environ["DEFAULT_IMAGE_PROVIDER"] = "mock_image"
os.environ["DEFAULT_IMAGE_MODEL"] = "mock-image-v1"
os.environ["ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED"] = "false"

import pytest


_GENERATED_TEST_DIR_PREFIXES = ("_runtime_", "_tmp_")
_GENERATED_TEST_DIR_NAMES = {"__pycache__"}


@pytest.fixture(autouse=True)
def _disable_live_v3_vision_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep ordinary tests offline; vision tests may opt in or inject a fake."""
    monkeypatch.setenv("V3_VISION_INSPECTION_ENABLED", "false")


def pytest_ignore_collect(collection_path: Path, config: object) -> bool:
    """Avoid descending into generated runtime and legacy temp folders."""
    if not collection_path.is_dir():
        return False
    name = collection_path.name
    return name in _GENERATED_TEST_DIR_NAMES or name.startswith(_GENERATED_TEST_DIR_PREFIXES)
