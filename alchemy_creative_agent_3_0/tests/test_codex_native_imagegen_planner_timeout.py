from __future__ import annotations

import multiprocessing
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from services.alchemy_codex_local_adapter.contracts import (
    NativeSpecializedImageGenPlanRequest,
)
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


def test_codex_native_planner_imports_app_providers_in_clean_process() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import services.alchemy_codex_local_adapter.native_planner; import app.providers.base; print('ok')",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_codex_native_planner_defaults_cover_two_stage_brain_preparation() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("CODEX_NATIVE_IMAGEGEN_PLANNING_TIMEOUT_SECONDS", None)
    env.pop("CODEX_NATIVE_IMAGEGEN_BRAIN_TRANSPORT_TIMEOUT_SECONDS", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "from services.alchemy_codex_local_adapter.native_planner import "
                "CodexNativeImageGenPlanner; "
                "p=CodexNativeImageGenPlanner(runtime_factory=lambda: None); "
                "print(json.dumps({'planning':p._planning_timeout_seconds,"
                "'brain':p._brain_transport_timeout_seconds}))"
            ),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    defaults = json.loads(result.stdout)
    assert defaults["brain"] <= 120.0
    assert defaults["planning"] > (2 * defaults["brain"]) + 30.0


class _TwoStageProbeRuntime:
    def __init__(self, delay_seconds: float = 0.05) -> None:
        self.delay_seconds = delay_seconds
        self.request_seen = None

    def plan_job(self, request):
        self.request_seen = request
        time.sleep(self.delay_seconds)
        time.sleep(self.delay_seconds)
        return {"status": "planned", "stages": ["plan", "provider_prompt_finalize"]}


class _MetadataProbeRuntime:
    def __init__(self) -> None:
        self.request_seen = None

    def plan_job(self, request):
        self.request_seen = request
        raise RuntimeError("metadata probe stop")


class _BlockingProbeRuntime:
    def __init__(self) -> None:
        self.calls = 0
        self.request_seen = None
        self.release = threading.Event()

    def plan_job(self, request):
        self.calls += 1
        self.request_seen = request
        self.release.wait(timeout=2.0)
        raise AssertionError("blocking probe finished after timeout")


def _marker_dir_from_request(request: dict) -> Path:
    asset = request["uploaded_assets"][0]
    file_path = getattr(asset, "file_path", None) or asset["file_path"]
    return Path(file_path).parent


def _slow_mutating_process_entrypoint(request: dict, result_queue) -> None:
    marker_dir = _marker_dir_from_request(request)
    with (marker_dir / "planner-start-count.txt").open("a", encoding="utf-8") as handle:
        handle.write("started\n")
    (marker_dir / "planner-started.txt").write_text("started", encoding="utf-8")
    time.sleep(6.0)
    # This marker models a late job/handoff/output/receipt/retry/delivery side
    # effect.  The parent must terminate the subprocess before this can happen.
    (marker_dir / "planner-created-record-after-timeout.txt").write_text(
        "job,handoff,output,receipt,retry,delivery",
        encoding="utf-8",
    )
    result_queue.put({"kind": "error", "error_type": "AssertionError", "message": "should have been terminated"})


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


def test_codex_native_specialized_planner_terminates_subprocess_on_timeout(tmp_path) -> None:
    planner = CodexNativeImageGenPlanner(
        planning_timeout_seconds=2.0,
        brain_transport_timeout_seconds=7.0,
        planning_process_entrypoint=_slow_mutating_process_entrypoint,
    )

    started = time.perf_counter()
    result = planner.prepare_frozen_specialized_native_imagegen_plan(_specialized_request(tmp_path))
    elapsed = time.perf_counter() - started

    assert elapsed < 3.0
    assert result == {
        "status": "blocked",
        "code": "codex_native_imagegen_planning_timeout",
        "message": "Codex Native ImageGen planning exceeded the local MCP interaction deadline before any image was created.",
        "execution_channel": "codex_native_imagegen",
        "delivery_state": "no_image_created",
    }
    assert (tmp_path / "planner-started.txt").read_text(encoding="utf-8") == "started"
    assert not (tmp_path / "planner-created-record-after-timeout.txt").exists()
    assert [
        child for child in multiprocessing.active_children()
        if child.name == "codex-native-imagegen-planner"
    ] == []
    assert [
        thread for thread in threading.enumerate()
        if thread.name == "codex-native-imagegen-planner"
    ] == []


def test_codex_native_custom_runtime_allows_two_stage_brain_preparation_within_deadline(tmp_path) -> None:
    runtime = _TwoStageProbeRuntime(delay_seconds=0.02)
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: runtime,
        planning_timeout_seconds=0.2,
        brain_transport_timeout_seconds=0.05,
    )

    result = planner._plan_job_with_deadline(runtime, {"metadata": {}})  # noqa: SLF001 - deadline invariant

    assert result == {"status": "planned", "stages": ["plan", "provider_prompt_finalize"]}
    assert runtime.request_seen is not None


def test_codex_native_specialized_planner_rejects_overlapping_timeout_workers(tmp_path) -> None:
    planner = CodexNativeImageGenPlanner(
        planning_timeout_seconds=3.0,
        brain_transport_timeout_seconds=7.0,
        planning_process_entrypoint=_slow_mutating_process_entrypoint,
    )
    first_result: dict[str, object] = {}

    def run_first() -> None:
        first_result.update(
            planner.prepare_frozen_specialized_native_imagegen_plan(_specialized_request(tmp_path))
        )

    first_thread = threading.Thread(target=run_first, name="test-native-planner-caller")
    first_thread.start()
    deadline = time.perf_counter() + 2.0
    while time.perf_counter() < deadline and not (tmp_path / "planner-started.txt").exists():
        time.sleep(0.01)
    assert (tmp_path / "planner-started.txt").exists()

    second_result = planner.prepare_frozen_specialized_native_imagegen_plan(_specialized_request(tmp_path))

    first_thread.join(timeout=5.0)
    assert not first_thread.is_alive()
    assert first_result["code"] == "codex_native_imagegen_planning_timeout"
    assert second_result["code"] == "codex_native_imagegen_planning_in_progress"
    assert (tmp_path / "planner-start-count.txt").read_text(encoding="utf-8").splitlines() == ["started"]
    assert not (tmp_path / "planner-created-record-after-timeout.txt").exists()


def test_codex_native_custom_runtime_keeps_deadline_and_rejects_overlap(tmp_path) -> None:
    runtime = _BlockingProbeRuntime()
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: runtime,
        planning_timeout_seconds=0.05,
        brain_transport_timeout_seconds=7.0,
    )

    first = planner.prepare_frozen_specialized_native_imagegen_plan(_specialized_request(tmp_path))
    second = planner.prepare_frozen_specialized_native_imagegen_plan(_specialized_request(tmp_path))
    runtime.release.set()

    assert first["code"] == "codex_native_imagegen_planning_timeout"
    assert second["code"] == "codex_native_imagegen_planning_in_progress"
    assert runtime.calls == 1
    assert runtime.request_seen is not None
    assert runtime.request_seen["metadata"]["_brain_transport_timeout_seconds"] == 7.0


def test_codex_native_specialized_timeout_metadata_is_server_side(tmp_path) -> None:
    runtime = _MetadataProbeRuntime()
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: runtime,
        planning_timeout_seconds=0.1,
        brain_transport_timeout_seconds=7.0,
    )
    try:
        planner.prepare_frozen_specialized_native_imagegen_plan(_specialized_request(tmp_path))
    except RuntimeError as exc:
        assert "metadata probe stop" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("metadata probe should stop before a runtime result")

    assert runtime.request_seen is not None
    assert runtime.request_seen["metadata"]["_brain_transport_timeout_seconds"] == 7.0
    request = _specialized_request(tmp_path)
    assert not hasattr(request, "_brain_transport_timeout_seconds")
