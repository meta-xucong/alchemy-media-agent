"""V3-owned deployment boundary adapter stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class V3DeploymentInfo:
    route_namespace: str
    runtime_mode: str
    metadata: dict


class V3DeploymentAdapter:
    adapter_name = "v3_deployment_adapter"

    def current_deployment(self) -> V3DeploymentInfo:
        return V3DeploymentInfo(
            route_namespace="/api/v3/creative-agent",
            runtime_mode="foundation_planning_only",
            metadata={"shared_server_allowed": True, "runtime_coupled_to_v1_v2": False},
        )

