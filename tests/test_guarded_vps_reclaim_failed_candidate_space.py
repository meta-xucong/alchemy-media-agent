from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "guarded-vps-reclaim-failed-candidate-space.yml"


def test_failed_candidate_reclaimer_is_exact_and_guarded() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "RECLAIM-FAILED-CANDIDATE-SPACE" in source
    assert "cache_only" in source
    assert '[ "$ARTIFACT_CONTAINER_ID" = none ]' in source
    assert '[ "$ARTIFACT_IMAGE_ID" = none ]' in source
    assert "artifact_outside_failed_run_window" in source
    assert 'state.get("Status") != "exited"' in source
    assert 'if container.get("Mounts"):' in source
    assert "scripts/fetch_v3_identity_models.py" in source
    assert "python -m pip install" in source
    assert "artifact_container_not_dockerfile_build_step" in source
    assert "GUARDED_FAILED_BUILD_RECLAIM_IMAGE_PRESERVED" in source
    assert 'docker rm "$container_id"' in source
    assert 'docker image rm "sha256:$image_id"' not in source
    assert "python3 -m pip cache purge" in source
    assert "apt-get clean" in source
    assert "package_manager_active" in source
    assert "docker system prune" not in source
    assert "docker container prune" not in source

    assert source.index("active_v1_health_failed") < source.index('docker rm "$container_id"')
    assert source.index('state.get("Status") != "exited"') < source.index('docker rm "$container_id"')
    assert source.index("artifact_container_not_dockerfile_build_step") < source.index('docker rm "$container_id"')
    assert source.index("package_manager_active") < source.index("apt-get clean")
    assert source.index('if [ "$mode" = full ]; then') < source.index('docker rm "$container_id"')
    assert source.index('elif [ "$mode" != cache_only ]; then') < source.index("pip_cache=")
