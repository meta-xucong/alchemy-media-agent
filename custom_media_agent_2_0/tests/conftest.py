from __future__ import annotations

import os
import tempfile
import uuid

# Keep test imports offline. ONNX Runtime can initialize native telemetry before
# its Python disable_telemetry_events() API is callable, so set the process-level
# opt-out before importing pytest or any application/SDK module. CI and local
# test commands also set these variables before the interpreter starts.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

# Never let tests inherit a developer's live RenderBridge config or credentials.
# Bridge-specific tests can opt in explicitly with temporary settings/transports.
_TEST_BRIDGE_ROOT = os.path.join(
    tempfile.gettempdir(), f"alchemy-v2-test-bridge-{os.getpid()}-{uuid.uuid4().hex}"
)
os.environ["ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG"] = os.path.join(
    _TEST_BRIDGE_ROOT, "disabled-control.json"
)
os.environ["ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT"] = os.path.join(
    _TEST_BRIDGE_ROOT, "state"
)
os.environ["ALCHEMY_RENDER_BRIDGE_MODE"] = "disabled"
os.environ["ALCHEMY_RENDER_BRIDGE_STORAGE"] = os.path.join(_TEST_BRIDGE_ROOT, "preview")
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
os.environ["CODEX_AUTH_FILE"] = os.path.join(_TEST_BRIDGE_ROOT, "missing-auth.json")
os.environ["CLAUDE_SETTINGS_FILE"] = os.path.join(_TEST_BRIDGE_ROOT, "missing-claude-settings.json")
for _provider_env_name in (
    "LLM_GATEWAY_API_KEY",
    "OPENAI_API_KEY",
    "V2_OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN",
    "DEEPSEEK_LLM_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_IMAGE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "V2_GEMINI_API_KEY",
    "BYTEPLUS_API_KEY",
    "V2_DOUBAO_IMAGE_API_KEY",
    "DOUBAO_IMAGE_API_KEY",
    "V2_DOUBAO_VISION_API_KEY",
    "LAB_DOUBAO_VISION_API_KEY",
    "LAB_OPENAI_API_KEY",
    "LAB_KIMI_API_KEY",
    "VEYRA_INTERNAL_TOKEN",
    "ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_API_KEY",
):
    os.environ[_provider_env_name] = ""
os.environ["MEDIA_AGENT_MODE"] = "mock"
os.environ["MOCK_IMAGE_PROVIDER_ENABLED"] = "true"
os.environ["V2_CLAUDE_ORCHESTRATOR_ENABLED"] = "false"
os.environ["V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED"] = "false"

import pytest


@pytest.fixture(autouse=True)
def isolate_v2_repository_database(tmp_path):
    """Keep repository.reset() scoped to a per-test SQLite database."""
    from app.config import settings

    original_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", tmp_path)
    try:
        yield
    finally:
        object.__setattr__(settings, "data_dir", original_data_dir)
