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
    bridge = release / "render_bridge_primary"
    bridge.mkdir()
    (bridge / "__init__.py").write_text("# transport\n")
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

    assert 'if [[ "$LOCAL_MODE" != "1" ]]; then' in deploy
    assert deploy.index('if [[ "$LOCAL_MODE" != "1" ]]; then') < deploy.index("run_as_root()")
    assert "Direct VPS deployment is disabled" in deploy
    assert "prepare_v2_runtime()" in candidate
    assert "python3 -m venv" in candidate
    assert "--write-manifest" in candidate
    assert "for runtime_entry in .v2_data .v2_storage; do" in candidate
    assert "candidate_v2_data_missing" not in activate
    assert "prepare_v2_runtime_for_release" in activate
    assert "install_v2_unit_contract" in activate
    assert "--verify" in activate
    migration = (root / "scripts" / "vps_migrate_release_layout.sh").read_text(encoding="utf-8")
    nginx = (root / "alchemy-media-agent.nginx.conf").read_text(encoding="utf-8")
    assert "retired and performs no changes" in migration
    assert "exit 2" in migration
    assert "location ^~ /api/v2/" in nginx
    assert "location = /api/v2" in nginx
    assert "/etc/alchemy/alchemy-media-agent-maintenance" in nginx
    assert deploy.index('if [[ "$LOCAL_MODE" != "1" ]]; then') < deploy.index(
        'echo "${DEPLOY_DIR} is an active release link; use scripts/vps_migrate_release_layout.sh'
    )
    workflow = (root / ".github" / "workflows" / "deploy-vps.yml").read_text(encoding="utf-8")
    assert "workflow is retired" in workflow
    assert "exit 2" in workflow
    assert "VPS_HOST" not in workflow


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


def test_v3_brain_route_is_explicit_in_all_runtime_bootstraps() -> None:
    root = Path(__file__).parents[1]
    bootstrap = (root / "scripts" / "bootstrap_env.ps1").read_text(encoding="utf-8")
    direct_deploy = (root / "scripts" / "deploy_vps.sh").read_text(encoding="utf-8")
    migration = (root / "scripts" / "vps_migrate_release_layout.sh").read_text(encoding="utf-8")
    example = (root / "src_skeleton" / ".env.example").read_text(encoding="utf-8")

    expected = {
        "V3_LLM_BRAIN_ENABLED": "true",
        "V3_LLM_BRAIN_REMOTE_ENABLED": "true",
        "V3_LLM_BRAIN_PROVIDER": "anthropic",
        "V3_LLM_BRAIN_MODEL": "claude-sonnet-5-5",
        "V3_LLM_BRAIN_BACKUP_MODEL": "kimi-k3",
        "V3_LLM_BRAIN_TRANSPORT": "chat_nonstream",
        "V3_LLM_BRAIN_TIMEOUT_SECONDS": "300",
        "V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS": "2200",
        "V3_LLM_BRAIN_MAX_TOKENS": "20000",
    }
    for key, value in expected.items():
        assert example.count(f"{key}=") == 1
        assert f"{key}={value}" in example
        assert f'"{key}={value}"' in bootstrap
        if key in {"V3_LLM_BRAIN_PROVIDER", "V3_LLM_BRAIN_MODEL", "V3_LLM_BRAIN_BACKUP_MODEL"}:
            assert f"{key}={value}" in direct_deploy
        else:
            assert f"{key}=${{{key}:-{value}}}" in direct_deploy
    assert "retired and performs no changes" in migration


def test_runtime_preflight_imports_lazy_bridge_dependency(tmp_path, monkeypatch):
    release, paths = _prepared_release(tmp_path)
    calls = []
    monkeypatch.setattr(_MODULE, "_run", lambda args, **kwargs: calls.append((args, kwargs)))
    _MODULE.verify_bridge_install(paths)
    assert "import render_bridge_primary" in calls[0][0][2]
    assert calls[0][1]["cwd"] == paths.v2_root


def test_actual_workflows_install_bridge_before_manifest():
    root = Path(__file__).parents[1]
    for name in ("candidate", "activate"):
        body = (root / ".github/workflows" / f"guarded-vps-{name}.yml").read_text()
        assert '--no-deps --force-reinstall' in body
        assert body.index('--no-deps --force-reinstall') < body.index('--write-manifest')


@pytest.mark.parametrize('workflow,function', [('candidate','prepare_v2_runtime'), ('activate','prepare_v2_runtime_for_release')])
def test_guarded_update_executes_neutral_install_before_manifest(tmp_path, workflow, function):
    """Exercise the actual workflow function with no-network command doubles."""
    import os
    import subprocess
    root = Path(__file__).parents[1]
    source = (root / '.github/workflows' / f'guarded-vps-{workflow}.yml').read_text()
    start = source.index(f'          {function}() {{')
    end = source.index('\n          }', start) + len('\n          }')
    body = '\n'.join(line[10:] for line in source[start:end].splitlines())
    release, paths = _prepared_release(tmp_path)
    guard = release / 'ops/vps-release/v2_runtime_guard.py'
    guard.parent.mkdir(parents=True); guard.write_text('# fixture\n')
    log = tmp_path / 'commands.log'
    fake = '#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_LOG"\nexit 0\n'
    paths.python.write_text(fake); paths.python.chmod(0o755)
    bin_path = tmp_path / 'bin'; bin_path.mkdir()
    (bin_path / 'python3').write_text(fake); (bin_path / 'python3').chmod(0o755)
    (bin_path / 'id').write_text('#!/bin/sh\nexit 1\n'); (bin_path / 'id').chmod(0o755)
    call = function if workflow == 'candidate' else f'{function} "$candidate_release" "$candidate_release/ops/vps-release/v2_runtime_guard.py"'
    script = f'set -Eeuo pipefail\nstop() {{ return 1; }}\ncandidate_release="$TEST_RELEASE"\n{body}\n{call}\n'
    env = {**os.environ, 'PATH': str(bin_path) + ':' + os.environ['PATH'], 'TEST_LOG': str(log), 'TEST_RELEASE': str(release)}
    result = subprocess.run(['bash'], input=script, text=True, capture_output=True, env=env)
    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert '--no-deps --force-reinstall ' + str(release / 'render_bridge_primary') in commands
    assert commands.index('--no-deps --force-reinstall') < commands.index('--write-manifest')
    assert commands.index('--write-manifest') < commands.index('--verify')
