"""Exercise one real V2 vision model against an existing output copy, without production writes."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


ALLOWED_MODELS = {"claude-sonnet-5-5", "kimi-k3"}


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and key and not key.startswith("#"):
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_source_record(database: Path, job_id: str) -> str:
    uri = database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute(
            "SELECT payload FROM v2_records WHERE namespace='image_jobs' AND record_key=?",
            (job_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None or not isinstance(row[0], str):
        raise RuntimeError("source_job_unavailable")
    return row[0]


def _attempt_summary(attempts: list[dict]) -> list[dict]:
    allowed = {
        "model", "outcome", "failure_code", "failure_class", "provider_reason",
        "http_status", "provider_usage", "elapsed_ms",
    }
    return [{key: value for key, value in item.items() if key in allowed} for item in attempts]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--model", required=True, choices=sorted(ALLOWED_MODELS))
    arguments = parser.parse_args()

    v2_root = Path(__file__).resolve().parents[1]
    service_environment = _read_env(Path("/etc/alchemy/alchemy-v2.env"))
    source_root_value = service_environment.get("V2_DATA_DIR")
    source_storage_value = service_environment.get("V2_STORAGE_DIR")
    if not source_root_value or not source_storage_value:
        raise RuntimeError("source_runtime_roots_unconfigured")
    source_root = Path(source_root_value).expanduser().resolve()
    source_storage = Path(source_storage_value).expanduser().resolve()
    source_runtime_path = source_root / "runtime_model_settings.json"
    source_runtime = json.loads(source_runtime_path.read_text(encoding="utf-8")) if source_runtime_path.is_file() else {}
    gateway = dict(service_environment)
    gateway.update(_read_env(source_root / "llm_gateway.env"))
    if not gateway.get("LLM_GATEWAY_API_KEY") or not gateway.get("LLM_GATEWAY_BASE_URL"):
        raise RuntimeError("vision_gateway_unconfigured")

    source_database = source_root / "repository.sqlite3"
    original_record = _load_source_record(source_database, arguments.job_id)
    job_payload = json.loads(original_record)
    outputs = job_payload.get("outputs")
    if job_payload.get("status") != "completed" or not isinstance(outputs, list) or len(outputs) != 1:
        raise RuntimeError("source_job_not_single_completed_output")
    output_metadata = outputs[0].get("metadata") or {}
    if output_metadata.get("input_images"):
        raise RuntimeError("source_output_has_external_references")
    source_image_value = output_metadata.get("storage_path")
    if not isinstance(source_image_value, str) or not source_image_value:
        raise RuntimeError("source_image_path_unavailable")
    source_image = Path(source_image_value).expanduser()
    if not source_image.is_absolute():
        source_image = source_storage / source_image
    source_image = source_image.resolve()
    if not source_image.is_relative_to(source_storage) or not source_image.is_file():
        raise RuntimeError("source_image_outside_v2_storage")
    original_bytes = source_image.read_bytes()

    with tempfile.TemporaryDirectory(prefix="v2-vision-model-acceptance-") as temporary:
        scratch = Path(temporary).resolve()
        data_dir = scratch / "data"
        storage_dir = scratch / "storage"
        data_dir.mkdir()
        storage_dir.mkdir()
        copied_image = storage_dir / source_image.name
        shutil.copy2(source_image, copied_image)

        runtime_settings = dict(source_runtime)
        runtime_settings["output_review_agent_enabled"] = True
        runtime_settings["claude_orchestrator_multimodal_model"] = arguments.model
        runtime_settings["claude_orchestrator_fallback_model"] = None
        runtime_settings["claude_orchestrator_fallback_models"] = []
        (data_dir / "runtime_model_settings.json").write_text(
            json.dumps(runtime_settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        isolated_paths = {
            "V2_DATA_DIR": data_dir,
            "V2_STORAGE_DIR": storage_dir,
            "V2_TASK_QUEUE_DB_PATH": data_dir / "task_queue.sqlite3",
            "V2_IMAGE_HISTORY_PATH": data_dir / "image_history.jsonl",
            "VEYRA_USAGE_PATH": data_dir / "veyra_usage.jsonl",
            "V2_CASE_INDEX_PATH": data_dir / "case_index.json",
            "V2_REMOTE_SNAPSHOT_DIR": data_dir / "remote_snapshots",
            "V2_CASE_THUMBNAIL_DIR": data_dir / "case_thumbnails",
            "V2_HISTORY_THUMBNAIL_DIR": data_dir / "history_thumbnails",
            "V2_CLAUDE_ORCHESTRATOR_WORKSPACE_DIR": data_dir / "claude_orchestrator_runs",
            "V2_CLAUDE_ORCHESTRATOR_CACHE_PATH": data_dir / "claude_orchestrator_cache.json",
            "ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG": scratch / "absent-bridge-control.json",
            "ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT": scratch / "bridge-state",
        }
        os.environ.update({key: str(value) for key, value in isolated_paths.items()})
        os.environ.update({
            "V2_ENV_FILE": str(scratch / "absent.env"),
            "V2_OUTPUT_REVIEW_AGENT_ENABLED": "true",
            "V2_OUTPUT_REVIEW_TIMEOUT_SECONDS": "300",
            "LLM_GATEWAY_API_KEY": gateway["LLM_GATEWAY_API_KEY"],
            "LLM_GATEWAY_BASE_URL": gateway["LLM_GATEWAY_BASE_URL"],
            "OPENAI_AGENTS_DISABLE_TRACING": "1",
            "ORT_DISABLE_TELEMETRY": "1",
        })
        sys.path[:0] = [str(v2_root), str(v2_root.parent)]

        from app.config import settings
        from app.repositories import repository
        from app.schemas import ImageJob
        from app.services.model_routing import visual_review_models
        from app.services.output_review import review_image_job
        from app.services.runtime_model_settings import apply_persisted_runtime_model_settings
        from app.services import visual_review_agent

        isolated_roots = (settings.data_dir, settings.storage_dir, settings.task_queue_db_path)
        if any(not Path(path).resolve().is_relative_to(scratch) for path in isolated_roots):
            raise RuntimeError("candidate_storage_isolation_failed")
        apply_persisted_runtime_model_settings()
        if visual_review_models(settings) != [arguments.model]:
            raise RuntimeError("candidate_model_queue_mismatch")

        job_payload["outputs"][0]["metadata"]["storage_path"] = str(copied_image)
        job_payload["outputs"][0]["review"] = None
        pending = review_image_job(ImageJob.model_validate(job_payload))
        repository.save_image_job(pending)
        reviewed = asyncio.run(visual_review_agent.review_generated_job(pending))
        repository.save_image_job(reviewed)
        verdict = reviewed.outputs[0].review
        persisted = repository.get_image_job(arguments.job_id)
        if verdict is None or persisted is None or persisted.outputs[0].review != verdict:
            raise RuntimeError("candidate_review_persistence_failed")

        attempt_details = _attempt_summary(verdict.model_attempts)
        safe_result = {
            "job_id": arguments.job_id,
            "requested_model": arguments.model,
            "configured_queue": visual_review_models(settings),
            "actual_attempts": attempt_details,
            "analysis_mode": verdict.analysis_mode,
            "decision": verdict.decision,
            "selected_model": verdict.model,
            "failure_code": verdict.failure_code,
            "elapsed_ms": verdict.elapsed_ms,
            "output_url_preserved": reviewed.outputs[0].url == job_payload["outputs"][0]["url"],
            "isolated_verdict_persisted": True,
            "source_record_unchanged": _load_source_record(source_database, arguments.job_id) == original_record,
            "source_image_unchanged": source_image.read_bytes() == original_bytes,
            "copied_image_unchanged": copied_image.read_bytes() == original_bytes,
            "production_writes": False,
        }
        print("SAFE_V2_REVIEW_ACCEPTANCE=" + json.dumps(safe_result, ensure_ascii=False), flush=True)
        accepted = (
            verdict.analysis_mode == "vision_model"
            and verdict.model == arguments.model
            and verdict.failure_code is None
            and len(verdict.model_attempts) == 1
            and verdict.model_attempts[0].get("outcome") == "accepted"
            and safe_result["output_url_preserved"]
            and safe_result["source_record_unchanged"]
            and safe_result["source_image_unchanged"]
            and safe_result["copied_image_unchanged"]
        )
        return 0 if accepted else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        print(json.dumps({
            "event": "SAFE_V2_REVIEW_ACCEPTANCE_ERROR",
            "error_type": type(error).__name__,
        }), flush=True)
        raise SystemExit(1)
