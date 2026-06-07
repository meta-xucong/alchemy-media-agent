from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _load_project_env() -> None:
    configured = os.getenv("V2_ENV_FILE")
    if configured:
        _load_env_file(Path(configured).expanduser())
    _load_env_file(PROJECT_ROOT / ".env")


_load_project_env()


def _codex_auth_value(name: str) -> str | None:
    auth_path = Path(os.path.expandvars(os.getenv("CODEX_AUTH_FILE", r"%USERPROFILE%\.codex\auth.json")))
    if not auth_path.exists():
        return None
    try:
        value = json.loads(auth_path.read_text(encoding="utf-8")).get(name)
    except (OSError, json.JSONDecodeError):
        return None
    return value or None


@dataclass(frozen=True)
class Settings:
    service_name: str = "custom-media-agent-v2"
    version: str = "0.1.0"
    api_prefix: str = "/api/v2"
    db_namespace: str = "alchemy_v2"
    redis_prefix: str = "alchemy:v2:"
    object_storage_prefix: str = "v2/"
    trace_project: str = "alchemy-media-agent-v2"
    agent_runtime: str = "openai_agents_sdk"
    default_agent_model: str = "gpt-4.1-mini"
    data_dir: Path = PROJECT_ROOT / ".v2_data"
    storage_dir: Path = PROJECT_ROOT / ".v2_storage"
    case_index_path: Path = PROJECT_ROOT / ".v2_data" / "case_index.json"
    image_history_path: Path = PROJECT_ROOT / ".v2_data" / "image_history.jsonl"
    remote_snapshot_dir: Path = PROJECT_ROOT / ".v2_data" / "remote_snapshots"
    case_thumbnail_dir: Path = PROJECT_ROOT / ".v2_data" / "case_thumbnails"
    history_thumbnail_dir: Path = PROJECT_ROOT / ".v2_data" / "history_thumbnails"
    task_queue_db_path: Path = PROJECT_ROOT / ".v2_data" / "task_queue.sqlite3"
    task_queue_inline_worker_enabled: bool = True
    task_queue_poll_interval_seconds: float = 1.0
    task_queue_claim_timeout_seconds: float = 900.0
    task_queue_max_attempts: int = 3
    output_review_agent_enabled: bool = False
    output_review_agent_model: str | None = None
    case_intelligence_provider: str = "rules"
    case_intelligence_model: str | None = None
    provider_seed_path: Path = PROJECT_ROOT / "provider_data" / "evolinkai_seed_cases.json"
    github_provider_source_uri: str = "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts"
    enable_remote_github_sync: bool = False
    sync_github_on_startup: bool = True
    resource_sync_interval_minutes: int = 360
    github_sync_timeout_seconds: float = 60.0
    image_generation_provider: str = "auto"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_image_model: str = "gpt-image-2"
    openai_image_timeout_seconds: float = 900.0
    openai_image_local_max_requests_per_minute: int = 12
    openai_image_local_max_outputs_per_minute: int = 24
    openai_image_local_queue_timeout_seconds: float = 900.0
    openai_image_upstream_cooldown_seconds: float = 90.0
    openai_image_max_retry_after_seconds: float = 900.0
    gemini_api_key: str | None = None
    gemini_base_url: str | None = None
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_image_timeout_seconds: float = 900.0
    allow_mock_fallback: bool = True
    persist_image_history: bool = True
    claude_orchestrator_enabled: bool = False
    claude_orchestrator_cli: str = "claude"
    claude_orchestrator_model: str | None = None
    claude_orchestrator_timeout_seconds: float = 240.0
    claude_orchestrator_max_output_tokens: int = 32000
    claude_orchestrator_effort: str = "low"
    claude_orchestrator_disable_slash_commands: bool = True
    claude_orchestrator_tools: str = "none"
    claude_orchestrator_permission_mode: str = "bypassPermissions"
    claude_orchestrator_fallback_model: str | None = None
    claude_orchestrator_workspace_dir: Path = PROJECT_ROOT / ".v2_data" / "claude_orchestrator_runs"
    claude_orchestrator_cache_enabled: bool = True
    claude_orchestrator_semantic_cache_enabled: bool = True
    claude_orchestrator_semantic_cache_threshold: float = 0.92
    claude_orchestrator_cache_path: Path = PROJECT_ROOT / ".v2_data" / "claude_orchestrator_cache.json"
    claude_orchestrator_max_attempts: int = 2
    claude_orchestrator_retry_delay_seconds: float = 2.0
    cors_allow_origins: tuple[str, ...] = (
        "http://127.0.0.1:8017",
        "http://localhost:8017",
        "http://127.0.0.1:8020",
        "http://localhost:8020",
    )


def _parse_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _normalize_claude_effort(value: str | None) -> str:
    normalized = str(value or "low").strip().lower()
    return normalized if normalized in {"low", "medium", "high", "xhigh", "max"} else "low"


def _normalize_case_intelligence_provider(value: str | None) -> str:
    normalized = str(value or "rules").strip().lower()
    return normalized if normalized in {"rules", "claude-code"} else "rules"


def load_settings() -> Settings:
    return Settings(
        service_name=os.getenv("V2_SERVICE_NAME", "custom-media-agent-v2"),
        version=os.getenv("V2_VERSION", "0.1.0"),
        api_prefix=os.getenv("V2_API_PREFIX", "/api/v2"),
        db_namespace=os.getenv("V2_DB_SCHEMA", "alchemy_v2"),
        redis_prefix=os.getenv("V2_REDIS_PREFIX", "alchemy:v2:"),
        object_storage_prefix=os.getenv("V2_OBJECT_STORAGE_PREFIX", "v2/"),
        trace_project=os.getenv("V2_AGENT_TRACE_PROJECT", "alchemy-media-agent-v2"),
        agent_runtime=os.getenv("V2_AGENT_RUNTIME", "openai_agents_sdk"),
        default_agent_model=os.getenv("V2_AGENT_DEFAULT_MODEL", "gpt-4.1-mini"),
        data_dir=Path(os.getenv("V2_DATA_DIR", str(PROJECT_ROOT / ".v2_data"))),
        storage_dir=Path(os.getenv("V2_STORAGE_DIR", str(PROJECT_ROOT / ".v2_storage"))),
        case_index_path=Path(os.getenv("V2_CASE_INDEX_PATH", str(PROJECT_ROOT / ".v2_data" / "case_index.json"))),
        image_history_path=Path(
            os.getenv("V2_IMAGE_HISTORY_PATH", str(PROJECT_ROOT / ".v2_data" / "image_history.jsonl"))
        ),
        remote_snapshot_dir=Path(
            os.getenv("V2_REMOTE_SNAPSHOT_DIR", str(PROJECT_ROOT / ".v2_data" / "remote_snapshots"))
        ),
        case_thumbnail_dir=Path(
            os.getenv("V2_CASE_THUMBNAIL_DIR", str(PROJECT_ROOT / ".v2_data" / "case_thumbnails"))
        ),
        history_thumbnail_dir=Path(
            os.getenv("V2_HISTORY_THUMBNAIL_DIR", str(PROJECT_ROOT / ".v2_data" / "history_thumbnails"))
        ),
        task_queue_db_path=Path(os.getenv("V2_TASK_QUEUE_DB_PATH", str(PROJECT_ROOT / ".v2_data" / "task_queue.sqlite3"))),
        task_queue_inline_worker_enabled=os.getenv("V2_TASK_QUEUE_INLINE_WORKER_ENABLED", "true").lower()
        in {"1", "true", "yes", "on"},
        task_queue_poll_interval_seconds=float(os.getenv("V2_TASK_QUEUE_POLL_INTERVAL_SECONDS", "1.0")),
        task_queue_claim_timeout_seconds=float(os.getenv("V2_TASK_QUEUE_CLAIM_TIMEOUT_SECONDS", "900")),
        task_queue_max_attempts=max(1, int(os.getenv("V2_TASK_QUEUE_MAX_ATTEMPTS", "3"))),
        output_review_agent_enabled=os.getenv("V2_OUTPUT_REVIEW_AGENT_ENABLED", "false").lower()
        in {"1", "true", "yes", "on"},
        output_review_agent_model=os.getenv("V2_OUTPUT_REVIEW_AGENT_MODEL") or None,
        case_intelligence_provider=_normalize_case_intelligence_provider(
            os.getenv("V2_CASE_INTELLIGENCE_PROVIDER", "rules")
        ),
        case_intelligence_model=os.getenv("V2_CASE_INTELLIGENCE_MODEL") or None,
        provider_seed_path=Path(
            os.getenv("V2_PROVIDER_SEED_PATH", str(PROJECT_ROOT / "provider_data" / "evolinkai_seed_cases.json"))
        ),
        github_provider_source_uri=os.getenv(
            "V2_GITHUB_PROVIDER_SOURCE_URI",
            "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts",
        ),
        enable_remote_github_sync=os.getenv("V2_ENABLE_REMOTE_GITHUB_SYNC", "false").lower()
        in {"1", "true", "yes"},
        sync_github_on_startup=os.getenv("V2_SYNC_GITHUB_ON_STARTUP", "true").lower()
        in {"1", "true", "yes", "on"},
        resource_sync_interval_minutes=max(1, int(os.getenv("V2_RESOURCE_SYNC_INTERVAL_MINUTES", "360"))),
        github_sync_timeout_seconds=float(os.getenv("V2_GITHUB_SYNC_TIMEOUT_SECONDS", "60")),
        image_generation_provider=os.getenv("V2_IMAGE_GENERATION_PROVIDER", "auto"),
        openai_api_key=os.getenv("V2_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or _codex_auth_value("OPENAI_API_KEY") or None,
        openai_base_url=(os.getenv("V2_OPENAI_BASE_URL") or "").rstrip("/") or None,
        openai_image_model=os.getenv("V2_OPENAI_IMAGE_MODEL", "gpt-image-2"),
        openai_image_timeout_seconds=float(os.getenv("V2_OPENAI_IMAGE_TIMEOUT_SECONDS", "900")),
        openai_image_local_max_requests_per_minute=max(
            1,
            int(os.getenv("V2_OPENAI_IMAGE_LOCAL_MAX_REQUESTS_PER_MINUTE", "12")),
        ),
        openai_image_local_max_outputs_per_minute=max(
            1,
            int(os.getenv("V2_OPENAI_IMAGE_LOCAL_MAX_OUTPUTS_PER_MINUTE", "24")),
        ),
        openai_image_local_queue_timeout_seconds=max(
            0.0,
            float(os.getenv("V2_OPENAI_IMAGE_LOCAL_QUEUE_TIMEOUT_SECONDS", "900")),
        ),
        openai_image_upstream_cooldown_seconds=max(
            1.0,
            float(os.getenv("V2_OPENAI_IMAGE_UPSTREAM_COOLDOWN_SECONDS", "90")),
        ),
        openai_image_max_retry_after_seconds=max(
            1.0,
            float(os.getenv("V2_OPENAI_IMAGE_MAX_RETRY_AFTER_SECONDS", "900")),
        ),
        gemini_api_key=os.getenv("V2_GEMINI_API_KEY") or None,
        gemini_base_url=(os.getenv("V2_GEMINI_BASE_URL") or "").rstrip("/") or None,
        gemini_image_model=os.getenv("V2_GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
        gemini_image_timeout_seconds=float(os.getenv("V2_GEMINI_IMAGE_TIMEOUT_SECONDS", "900")),
        allow_mock_fallback=os.getenv("V2_ALLOW_MOCK_FALLBACK", "true").lower() in {"1", "true", "yes", "on"},
        persist_image_history=os.getenv("V2_PERSIST_IMAGE_HISTORY", "true").lower() in {"1", "true", "yes", "on"},
        claude_orchestrator_enabled=os.getenv("V2_CLAUDE_ORCHESTRATOR_ENABLED", "false").lower()
        in {"1", "true", "yes", "on"},
        claude_orchestrator_cli=os.getenv("V2_CLAUDE_ORCHESTRATOR_CLI", "claude"),
        claude_orchestrator_model=os.getenv("V2_CLAUDE_ORCHESTRATOR_MODEL") or None,
        claude_orchestrator_timeout_seconds=float(os.getenv("V2_CLAUDE_ORCHESTRATOR_TIMEOUT_SECONDS", "240")),
        claude_orchestrator_max_output_tokens=max(
            512,
            int(os.getenv("V2_CLAUDE_ORCHESTRATOR_MAX_OUTPUT_TOKENS", "32000")),
        ),
        claude_orchestrator_effort=_normalize_claude_effort(os.getenv("V2_CLAUDE_ORCHESTRATOR_EFFORT", "low")),
        claude_orchestrator_disable_slash_commands=os.getenv(
            "V2_CLAUDE_ORCHESTRATOR_DISABLE_SLASH_COMMANDS",
            "true",
        ).lower()
        in {"1", "true", "yes", "on"},
        claude_orchestrator_tools=os.getenv("V2_CLAUDE_ORCHESTRATOR_TOOLS", "none"),
        claude_orchestrator_permission_mode=os.getenv(
            "V2_CLAUDE_ORCHESTRATOR_PERMISSION_MODE",
            "bypassPermissions",
        ),
        claude_orchestrator_fallback_model=os.getenv("V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODEL") or None,
        claude_orchestrator_workspace_dir=Path(
            os.getenv(
                "V2_CLAUDE_ORCHESTRATOR_WORKSPACE_DIR",
                str(PROJECT_ROOT / ".v2_data" / "claude_orchestrator_runs"),
            )
        ),
        claude_orchestrator_cache_enabled=os.getenv("V2_CLAUDE_ORCHESTRATOR_CACHE_ENABLED", "true").lower()
        in {"1", "true", "yes", "on"},
        claude_orchestrator_semantic_cache_enabled=os.getenv(
            "V2_CLAUDE_ORCHESTRATOR_SEMANTIC_CACHE_ENABLED",
            "true",
        ).lower()
        in {"1", "true", "yes", "on"},
        claude_orchestrator_semantic_cache_threshold=max(
            0.5,
            min(float(os.getenv("V2_CLAUDE_ORCHESTRATOR_SEMANTIC_CACHE_THRESHOLD", "0.92")), 1.0),
        ),
        claude_orchestrator_cache_path=Path(
            os.getenv(
                "V2_CLAUDE_ORCHESTRATOR_CACHE_PATH",
                str(PROJECT_ROOT / ".v2_data" / "claude_orchestrator_cache.json"),
            )
        ),
        claude_orchestrator_max_attempts=max(1, int(os.getenv("V2_CLAUDE_ORCHESTRATOR_MAX_ATTEMPTS", "2"))),
        claude_orchestrator_retry_delay_seconds=float(os.getenv("V2_CLAUDE_ORCHESTRATOR_RETRY_DELAY_SECONDS", "2.0")),
        cors_allow_origins=_parse_csv_env(
            "V2_CORS_ALLOW_ORIGINS",
            (
                "http://127.0.0.1:8017",
                "http://localhost:8017",
                "http://127.0.0.1:8020",
                "http://localhost:8020",
            ),
        ),
    )


settings = load_settings()


def ensure_runtime_dirs() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.image_history_path.parent.mkdir(parents=True, exist_ok=True)
    settings.remote_snapshot_dir.mkdir(parents=True, exist_ok=True)
    settings.case_thumbnail_dir.mkdir(parents=True, exist_ok=True)
    settings.history_thumbnail_dir.mkdir(parents=True, exist_ok=True)
    settings.task_queue_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.claude_orchestrator_workspace_dir.mkdir(parents=True, exist_ok=True)
    settings.claude_orchestrator_cache_path.parent.mkdir(parents=True, exist_ok=True)
