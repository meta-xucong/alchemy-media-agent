"""Remote provider facade for the V3 LLM Brain."""

from __future__ import annotations

import json
import os
from typing import Any

from .contracts import BrainRunRequest
from .prompts import SYSTEM_PROMPT, build_remote_payload


class BrainProviderUnavailable(RuntimeError):
    """Raised when no remote brain provider is configured."""


class BrainProviderError(RuntimeError):
    """Raised when a configured remote brain provider fails."""


class BrainSemanticPreflightMissing(BrainProviderError):
    """The Brain returned a prompt but omitted a required semantic receipt."""


class V3LLMBrainProvider:
    """Small provider adapter that keeps V3 brain calls optional."""

    def __init__(self) -> None:
        self.provider = _env("V3_LLM_BRAIN_PROVIDER") or _preferred_provider()
        self.provider = self.provider.strip().lower()
        self.model = _env("V3_LLM_BRAIN_MODEL") or _default_model(self.provider)
        self.timeout = _float_env("V3_LLM_BRAIN_TIMEOUT_SECONDS", 120.0)
        self.max_tokens = _int_env("V3_LLM_BRAIN_MAX_TOKENS", 4200)

    def available(self, *, force: bool = False) -> bool:
        if not _remote_enabled(force=force):
            return False
        try:
            self._credentials()
            return True
        except BrainProviderUnavailable:
            return False

    def run(self, request: BrainRunRequest) -> dict[str, Any]:
        if self.provider in {"anthropic", "kimi", "claude"}:
            return self._run_anthropic_compatible(request)
        return self._run_openai_compatible(request)

    def _run_openai_compatible(self, request: BrainRunRequest) -> dict[str, Any]:
        api_key, base_url = self._credentials()
        # DeepSeek is OpenAI-compatible but its deployed endpoint exposes the
        # broadly supported Chat Completions contract rather than the newer
        # Responses contract.  Choosing the transport by the declared Brain
        # provider keeps an image gateway credential from deciding how the
        # Central Brain talks to its own remote model.
        if self.provider == "deepseek":
            return self._run_openai_chat_completions(
                api_key=api_key,
                base_url=base_url,
                request=request,
            )
        try:
            from openai import OpenAI

            # Central Brain has one bounded remote attempt.  SDK-level retries
            # would silently multiply a logical request and hide the actual
            # upstream terminal state from the specialized fail-closed gate.
            kwargs = _openai_client_kwargs(api_key=api_key, base_url=base_url, max_retries=0)
            client = OpenAI(**kwargs)
            response = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_remote_payload(request)},
                ],
                text={"format": {"type": "json_object"}},
                timeout=self.timeout,
                max_output_tokens=self.max_tokens,
            )
            text = getattr(response, "output_text", None) or ""
            if not text:
                text = _response_text_from_openai(response)
            return _loads_json_object(text)
        except Exception as exc:
            raise BrainProviderError(f"remote brain provider failed: {str(exc)[:240]}") from exc

    def _run_openai_chat_completions(
        self,
        *,
        api_key: str,
        base_url: str | None,
        request: BrainRunRequest,
    ) -> dict[str, Any]:
        """Run a JSON-only Central Brain request through Chat Completions.

        This is a remote-provider transport adaptation, not a deterministic
        creative fallback.  Callers still receive a provider error and
        specialized templates still fail closed if the remote answer is absent
        or violates its frozen image-set contract.
        """

        try:
            from openai import OpenAI

            # Keep the DeepSeek-compatible transport to the same one-attempt
            # contract as Responses and the managed image gateway.
            kwargs = _openai_client_kwargs(api_key=api_key, base_url=base_url, max_retries=0)
            client = OpenAI(**kwargs)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_remote_payload(request)},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                timeout=self.timeout,
                max_tokens=self.max_tokens,
            )
            choices = getattr(response, "choices", None) or []
            message = getattr(choices[0], "message", None) if choices else None
            text = getattr(message, "content", None) or ""
            return _loads_json_object(text)
        except Exception as exc:
            raise BrainProviderError(f"remote brain provider failed: {str(exc)[:240]}") from exc

    def _run_anthropic_compatible(self, request: BrainRunRequest) -> dict[str, Any]:
        api_key, base_url = self._credentials()
        if not base_url:
            raise BrainProviderUnavailable("anthropic-compatible brain base URL is not configured")
        try:
            import httpx

            headers = {"content-type": "application/json"}
            token_header = "x-api-key" if self.provider == "anthropic" else "authorization"
            headers[token_header] = api_key if token_header == "x-api-key" else f"Bearer {api_key}"
            url = f"{base_url.rstrip('/')}/v1/messages"
            payload = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": 0.2,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": build_remote_payload(request)}],
            }
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            return _loads_json_object(_anthropic_text(response.json()))
        except Exception as exc:
            raise BrainProviderError(f"remote brain provider failed: {str(exc)[:240]}") from exc

    def _credentials(self) -> tuple[str, str | None]:
        if self.provider in {"anthropic", "kimi", "claude"}:
            api_key = (
                _env("V3_LLM_BRAIN_API_KEY")
                or _settings_value("anthropic_auth_token")
                or _settings_value("anthropic_api_key")
                or _settings_value("lab_kimi_api_key")
            )
            base_url = _env("V3_LLM_BRAIN_BASE_URL") or _settings_value("anthropic_base_url") or _settings_value("lab_kimi_base_url")
        elif self.provider == "deepseek":
            # DeepSeek is OpenAI-compatible at transport level, but it owns
            # its own configured credential/base URL.  Do not silently route
            # Central Brain calls through the unrelated image gateway simply
            # because OPENAI_API_KEY is also present in the process.
            api_key = _env("V3_LLM_BRAIN_API_KEY") or _settings_value("deepseek_llm_api_key")
            base_url = _env("V3_LLM_BRAIN_BASE_URL") or _settings_value("deepseek_llm_base_url")
        else:
            api_key = _env("V3_LLM_BRAIN_API_KEY") or _settings_value("openai_api_key") or _settings_value("lab_openai_api_key")
            base_url = _env("V3_LLM_BRAIN_BASE_URL") or _settings_value("openai_base_url") or _settings_value("lab_openai_base_url")
        if not api_key:
            raise BrainProviderUnavailable("remote brain API key is not configured")
        return str(api_key), str(base_url) if base_url else None


def _default_model(provider: str) -> str:
    if provider in {"anthropic", "kimi", "claude"}:
        return _settings_value("kimi_llm_model") or _settings_value("backup_llm_model") or "kimi-for-coding"
    if provider == "deepseek":
        return _settings_value("deepseek_llm_model") or _settings_value("default_llm_model") or "deepseek-v4-pro-260425"
    return _settings_value("openai_llm_model") or _settings_value("default_llm_model") or "gpt-5.5"


def _preferred_provider() -> str:
    configured = str(_settings_value("default_llm_provider") or "").strip().lower()
    if configured in {"openai", "deepseek", "anthropic", "kimi", "claude"}:
        return configured
    if _settings_value("openai_api_key") or _settings_value("lab_openai_api_key"):
        return "openai"
    return _settings_value("default_llm_provider") or "openai"


def _settings_value(name: str) -> Any:
    try:
        from app.config import settings

        return getattr(settings, name, None)
    except Exception:
        return None


def _openai_client_kwargs(*, api_key: str, base_url: str | None, **extra: Any) -> dict[str, Any]:
    try:
        from app.config import openai_sdk_client_kwargs

        return openai_sdk_client_kwargs(api_key=api_key, base_url=base_url, **extra)
    except Exception:
        kwargs: dict[str, Any] = {"api_key": api_key, **extra}
        if base_url:
            kwargs["base_url"] = base_url
        return kwargs


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _remote_enabled(*, force: bool = False) -> bool:
    raw = os.getenv("V3_LLM_BRAIN_REMOTE_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if force:
        return True
    return bool(_env("V3_LLM_BRAIN_API_KEY"))


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return max(512, min(8000, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def _loads_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise BrainProviderError("remote brain returned empty output")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise BrainProviderError("remote brain returned non-json output")
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise BrainProviderError("remote brain json output was not an object")
    return parsed


def _response_text_from_openai(response: Any) -> str:
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def _anthropic_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("content", []) if isinstance(payload, dict) else []:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return "\n".join(chunks)
