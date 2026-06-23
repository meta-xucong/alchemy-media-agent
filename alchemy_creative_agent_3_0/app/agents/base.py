"""Shared V3 agent contracts."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class AgentResult(BaseModel, Generic[T]):
    output: T
    reasoning_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseAgent:
    agent_name = "base_agent"

    def metadata(self, **extra: Any) -> dict[str, Any]:
        return {"source_agent": self.agent_name, **extra}

