import os
from pathlib import Path

os.environ["CODEX_AUTH_FILE"] = str(Path(__file__).parent / ".missing_auth.json")
os.environ["CLAUDE_SETTINGS_FILE"] = str(Path(__file__).parent / ".missing_claude_settings.json")
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_AUTH_TOKEN"] = ""
os.environ["LLM_PROMPT_PLANNING_ENABLED"] = "false"
os.environ["MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS"] = "false"
os.environ.setdefault("MEDIA_AGENT_MODE", "mock")
os.environ.setdefault("MOCK_IMAGE_PROVIDER_ENABLED", "true")
