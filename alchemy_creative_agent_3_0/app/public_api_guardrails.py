"""Shared guardrails for public/product-level V3 contracts."""

from __future__ import annotations

from typing import Any


LOW_LEVEL_GENERATION_CONTROL_KEYS = {
    "seed",
    "sampler",
    "lora",
    "lora_weight",
    "controlnet",
    "controlnet_type",
    "control_net",
    "control_net_type",
    "adapter_scale",
    "ip_adapter_scale",
    "node_graph",
}


def normalise_public_key(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def low_level_control_paths(value: Any, prefix: str = "") -> list[str]:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return low_level_control_paths(value.model_dump(mode="python"), prefix)
    if isinstance(value, dict):
        paths: list[str] = []
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if normalise_public_key(key) in LOW_LEVEL_GENERATION_CONTROL_KEYS:
                paths.append(path)
            paths.extend(low_level_control_paths(raw_value, path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            paths.extend(low_level_control_paths(item, path))
        return paths
    return []


def reject_low_level_controls(value: Any) -> None:
    blocked_paths = low_level_control_paths(value)
    if blocked_paths:
        raise ValueError(
            "low-level generation controls are not part of the V3 product API: "
            + ", ".join(sorted(blocked_paths))
        )
