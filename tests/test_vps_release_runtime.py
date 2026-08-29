from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


_MODULE_PATH = Path(__file__).parents[1] / "ops" / "vps-release" / "v2_runtime_guard.py"
_SPEC = importlib.util.spec_from_file_location("v2_runtime_guard", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
RuntimeGuardError = _MODULE.RuntimeGuardError
build_manifest = _MODULE.build_manifest
runtime_paths = _MODULE.runtime_paths
validate_manifest = _MODULE.validate_manifest


def _prepared_release(tmp_path: Path) -> tuple[Path, object]:
    release = tmp_path / "release"
    v2_root = release / "custom_media_agent_2_0"
    (v2_root / ".venv" / "bin").mkdir(parents=True)
    (v2_root / ".venv" / "bin" / "python").write_bytes(b"python")
    (v2_root / "requirements.txt").write_text("httpx>=0.28.0\nhttpcore>=1.0.0,<2\n", encoding="utf-8")
    return release, runtime_paths(release)


def test_v2_runtime_manifest_binds_exact_requirements(tmp_path: Path) -> None:
    release, paths = _prepared_release(tmp_path)
    manifest = build_manifest(paths)

    validate_manifest(paths, manifest)
    assert manifest["schema_version"] == 1
    assert manifest["venv_python"] == str(paths.python)

    paths.requirements.write_text("httpx>=0.28.0\nhttpcore>=1.0.0,<2\nPillow>=10.4\n", encoding="utf-8")
    with pytest.raises(RuntimeGuardError, match="requirements"):
        validate_manifest(paths, manifest)


def test_v2_runtime_manifest_rejects_wrong_release_python(tmp_path: Path) -> None:
    release, paths = _prepared_release(tmp_path)
    manifest = build_manifest(paths)
    tampered = {**manifest, "venv_python": str(release / "other" / "bin" / "python")}

    with pytest.raises(RuntimeGuardError, match="different release"):
        validate_manifest(paths, tampered)


def test_systemd_templates_are_active_release_bound_and_guarded() -> None:
    root = Path(__file__).parents[1] / "custom_media_agent_2_0" / "deploy" / "systemd"
    for unit in ("alchemy-v2-api.service", "alchemy-v2-worker.service", "alchemy-v2-sync-worker.service"):
        text = (root / unit).read_text(encoding="utf-8")
        assert "__ALCHEMY_RELEASE_LINK__" in text
        assert "ExecStartPre=/usr/bin/python3 /usr/local/lib/alchemy/v2_runtime_guard.py" in text
        assert ".venv/bin/python" in text


def test_runtime_manifest_is_ignored_inside_v2_release() -> None:
    ignore = (Path(__file__).parents[1] / "custom_media_agent_2_0" / ".gitignore").read_text(encoding="utf-8")
    assert ".alchemy-v2-runtime.json" in ignore


def test_deploy_paths_prepare_release_bound_runtime() -> None:
    root = Path(__file__).parents[1]
    deploy = (root / "scripts" / "deploy_vps.sh").read_text(encoding="utf-8")
    candidate = (root / ".github" / "workflows" / "guarded-vps-candidate.yml").read_text(encoding="utf-8")
    activate = (root / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")

    assert "vps_prepare_v2_runtime.sh" in deploy
    assert "verify_v2_runtime_before_v1_start()" in deploy
    assert deploy.rindex("\nensure_v2_runtime") < deploy.rindex("\nverify_v2_runtime_before_v1_start")
    assert deploy.rindex("\nverify_v2_runtime_before_v1_start") < deploy.rindex("\nstart_stack")
    assert deploy.rindex("\nrestart_v2_services_if_present") > deploy.rindex("\nstart_stack")
    assert "prepare_v2_runtime()" in candidate
    assert "python3 -m venv" in candidate
    assert "--write-manifest" in candidate
    assert "for runtime_entry in .v2_data .v2_storage; do" in candidate
    assert "candidate_v2_data_missing" not in activate
    assert "prepare_v2_runtime_for_release" in activate
    assert "install_v2_unit_contract" in activate
    assert "--verify" in activate
    migration = (root / "scripts" / "vps_migrate_release_layout.sh").read_text(encoding="utf-8")
    assert "git -C \"${REPOSITORY_ROOT}\" worktree add --detach" in migration
    assert "v2_runtime_guard.py" in migration
    assert "__ALCHEMY_RELEASE_LINK__" in migration
    assert "compose_cmd=(docker compose)" in migration
    assert "compose_cmd=(docker-compose)" in migration
    assert 'units_installed=1' in migration
    assert "VPS_ALCHEMY_SUB2API=untouched" in migration
    assert 'runtime_requirements="${candidate}/custom_media_agent_2_0/requirements.txt"' in migration
    assert migration.index('v2_runtime_guard.py" --release "${candidate}" --verify') < migration.index('ln -sfn "${candidate}" "${DEPLOY_LINK}"')


def test_runtime_guard_requires_bridge_transport_import() -> None:
    guard = (Path(__file__).parents[1] / "ops" / "vps-release" / "v2_runtime_guard.py").read_text(encoding="utf-8")
    assert "import app.main; import httpx, httpcore" in guard


def test_both_image_dependency_manifests_declare_httpcore() -> None:
    root = Path(__file__).parents[1]
    v1_requirements = (root / "src_skeleton" / "requirements.txt").read_text(encoding="utf-8")
    assert "httpcore==1.0.9" in v1_requirements
    assert "httpx==0.28.1" in v1_requirements
    assert "openai==2.53.0" in v1_requirements
    assert "openai-agents==0.20.0" in v1_requirements
    assert "mcp==2.0.0" in v1_requirements
    v2_requirements = (root / "custom_media_agent_2_0" / "requirements.txt").read_text(encoding="utf-8")
    assert "httpcore==1.0.9" in v2_requirements
    assert "httpx==0.28.1" in v2_requirements
    assert "openai-agents==0.17.4" in v2_requirements
    assert "openai==2.41.0" in v2_requirements
    assert "mcp==1.27.2" in v2_requirements
