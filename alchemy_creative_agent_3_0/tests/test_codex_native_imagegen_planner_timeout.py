from __future__ import annotations

import time

from services.alchemy_codex_local_adapter.contracts import (
    NativeSpecializedImageGenPlanRequest,
)
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


class _SlowRuntime:
    def __init__(self) -> None:
        self.request_seen = None

    def plan_job(self, request):
        self.request_seen = request
        time.sleep(1.0)
        raise AssertionError("slow runtime should not finish inside the MCP deadline")


def _specialized_request(tmp_path) -> NativeSpecializedImageGenPlanRequest:
    reference = tmp_path / "product.jpg"
    reference.write_bytes(b"fake image bytes")
    return NativeSpecializedImageGenPlanRequest.from_mcp_arguments(
        {
            "user_input": "Create one ecommerce product image.",
            "template_id": "ecommerce_template",
            "requested_image_count": 1,
            "requested_image_size": "1024x1536",
            "reference_inputs": [
                {
                    "channel": "product_truth",
                    "file_path": str(reference),
                }
            ],
            "platform_profile": "taobao_xiaohongshu_kidswear",
            "photography_mode": None,
            "photographer_profile_id": None,
        }
    )


def test_codex_native_specialized_planner_times_out_before_desktop_call_hangs(tmp_path) -> None:
    runtime = _SlowRuntime()
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: runtime,
        planning_timeout_seconds=0.05,
        brain_transport_timeout_seconds=7.0,
    )

    started = time.perf_counter()
    result = planner.prepare_frozen_specialized_native_imagegen_plan(_specialized_request(tmp_path))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.5
    assert result == {
        "status": "blocked",
        "code": "codex_native_imagegen_planning_timeout",
        "message": "Codex Native ImageGen planning exceeded the local MCP interaction deadline before any image was created.",
        "execution_channel": "codex_native_imagegen",
        "delivery_state": "no_image_created",
    }
    assert runtime.request_seen is not None
    assert runtime.request_seen["metadata"]["_brain_transport_timeout_seconds"] == 7.0


def test_codex_native_specialized_timeout_is_server_side_not_mcp_payload(tmp_path) -> None:
    request = _specialized_request(tmp_path)

    assert not hasattr(request, "_brain_transport_timeout_seconds")
