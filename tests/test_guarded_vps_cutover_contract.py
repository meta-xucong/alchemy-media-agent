from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_activation_requires_explicit_maintenance_and_disk_budget() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")

    assert 'maintenance_confirmation="$3"' in workflow
    assert '[ "$maintenance_confirmation" = CUTOVER-PR29 ]' in workflow
    assert '[[ "$minimum_free_bytes" =~ ^[1-9][0-9]*$ ]]' in workflow
    assert '[[ ${#MINIMUM_FREE_BYTES} -le 18 ]]' in workflow
    assert 'require_backup_capacity "$inventory_file" || return 1' in workflow
    assert 'require_post_backup_data_capacity "$maintenance_backup/database-inventory.bin"' in workflow
    assert "VPS_HOST" in workflow


def test_activation_targets_the_enabled_nginx_config_file() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")

    assert 'nginx_config="/etc/nginx/sites-available/alchemy-media-agent"' in workflow
    assert 'nginx_enabled_config="/etc/nginx/sites-enabled/alchemy-media-agent"' in workflow
    assert '[ -L "$nginx_enabled_config" ] || stop_pre active_nginx_config_link_missing' in workflow
    assert '[ "$(realpath "$nginx_enabled_config")" = "$nginx_config" ] || stop_pre active_nginx_config_link_target_mismatch' in workflow
    assert workflow.index("active_nginx_config_link_target_mismatch") < workflow.index('maintenance_active=1')


def test_activation_orders_fence_backup_prepare_verify_and_admission() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    markers = [
        'systemctl stop "$unit"',
        "docker stop --time 45",
        '"${unit}_still_active"',
        "backup_stores ||",
        "prepare_and_verify_target_indexes ||",
        "install_v2_unit_contract || stop_pre candidate_v2_unit_contract_install_failed",
        "candidate_services_started=1",
        "verify_v2_history_reads.py",
        "systemctl start alchemy-v2-worker.service",
        'rm -f "$maintenance_flag" || fail_post public_gate_open_failed',
        'wait_for_200 "$public_base_url/api/v2/health" || fail_public_open',
    ]
    stop_position = workflow.rindex(markers[0])
    start_position = workflow.rindex(markers[4])
    positions = [
        stop_position,
        workflow.index(markers[1], stop_position),
        workflow.index(markers[2], workflow.index(markers[1], stop_position)),
        workflow.index(markers[3], stop_position),
        workflow.index(markers[4], start_position),
        workflow.index(markers[5], start_position),
        workflow.index(markers[6], start_position),
        workflow.index(markers[7], start_position),
        workflow.index(markers[8], start_position),
        workflow.index(markers[9], start_position),
    ]
    assert positions == sorted(positions)
    stopped_verification = workflow.index(
        'python3 "$candidate_release/scripts/vps_cutover_guard.py" inspect-active-work',
        workflow.index("docker stop --time 45"),
    )
    assert workflow.index("docker stop --time 45") < stopped_verification < workflow.index("backup_stores ||")
    api_runtime_env = (ROOT / "custom_media_agent_2_0" / "deploy" / "systemd" / "alchemy-v2-api-runtime.env").read_text(encoding="utf-8")
    assert "V2_TASK_QUEUE_INLINE_WORKER_ENABLED=false" in api_runtime_env
    assert "V2_SYNC_GITHUB_ON_STARTUP=false" in api_runtime_env
    assert "V2_ENABLE_REMOTE_GITHUB_SYNC=false" in api_runtime_env
    assert "verify-v2-api-no-background-writers" in workflow
    assert "verify-v2-api-runtime-contract" in workflow
    assert "api_runtime_env=\"/etc/alchemy/alchemy-v2-api-runtime.env\"" in workflow
    assert "api_runtime_drop_in=\"/etc/systemd/system/alchemy-v2-api.service.d/90-alchemy-worker-ownership.conf\"" in workflow
    assert "verify-v2-storage-roots" in workflow
    assert "verify-v2-storage-unit-roots" in workflow
    assert workflow.count("verify_v3_runtime_storage_roots \"$old_env\" || stop_pre") == 2
    assert workflow.count("verify_v3_runtime_storage_roots \"$candidate_release/src_skeleton/.env\" || stop_pre") == 2
    assert "docker inspect \"$v1_container\" | python3 \"$candidate_release/scripts/vps_cutover_guard.py\"" in workflow
    assert "verify-v3-storage-roots --v1-media-root \"$v1_media\"" in workflow
    assert "--bootstrap-env-file \"$bootstrap_env_file\"" in workflow
    v3_root_checks = [
        index for index in range(len(workflow))
        if workflow.startswith("verify_v3_runtime_storage_roots \"", index)
    ]
    assert len(v3_root_checks) == 5
    first_v3_scan = workflow.index('python3 "$candidate_release/scripts/vps_cutover_guard.py" inspect-active-work')
    second_v3_scan = workflow.index(
        'python3 "$candidate_release/scripts/vps_cutover_guard.py" inspect-active-work', first_v3_scan + 1
    )
    docker_stop = workflow.rindex("docker stop --time 45", 0, second_v3_scan)
    assert v3_root_checks[0] < first_v3_scan
    assert docker_stop < v3_root_checks[2] < second_v3_scan
    candidate_root_check = workflow.index(
        'verify_v3_runtime_storage_roots "$candidate_release/src_skeleton/.env" || fail_post'
    )
    candidate_compose = workflow.index("compose_for \"$candidate_release\" up -d")
    candidate_health = workflow.index("wait_for_200 http://127.0.0.1:8017/healthz", candidate_compose)
    assert candidate_compose < candidate_root_check < candidate_health
    assert workflow.index("verify_v2_unit_contract || stop_pre candidate_v2_unit_contract_invalid") < workflow.index(
        "verify_v2_runtime_unit_roots || stop_pre candidate_v2_unit_storage_roots_unverified"
    ) < workflow.index("candidate_services_started=1")
    assert "verify_v2_runtime_roots || fail_post candidate_v2_storage_roots_unverified" in workflow[
        workflow.index("systemctl start alchemy-v2-sync-worker.service"):
    ]
    assert "remove_cutover_api_override" not in workflow
    assert "v2_api_final_restart_failed" not in workflow
    assert workflow.index("verify-v2-api-no-background-writers") < workflow.index("systemctl start alchemy-v2-worker.service")
    assert "candidate_v2_api_background_writer_enabled_after_admission" in workflow
    assert workflow.index("systemctl start alchemy-v2-sync-worker.service") < workflow.index(
        "candidate_v2_api_background_writer_enabled_after_admission"
    ) < workflow.index('rm -f "$maintenance_flag" || fail_post public_gate_open_failed')
    assert "GUARDED_ACTIVATE_FORWARD_RECOVERY_REQUIRED" in workflow
    assert "vps_cutover_guard.py\" restore" in workflow
    stopped_verification_block = workflow[
        workflow.index('if [ "$maintenance_timer_was_active" = 1 ]; then systemctl stop'):
        workflow.index("backup_stores ||", stop_position)
    ]
    assert 'systemctl stop alchemy-v3-storage-maintenance.service' in stopped_verification_block
    assert 'systemctl is-active --quiet alchemy-v3-storage-maintenance.timer && stop_pre' in stopped_verification_block
    assert 'require_disk_floor "$maintenance_backup_root" || stop_pre backup_consumed_disk_reserve' in workflow
    assert stopped_verification_block.index('systemctl stop alchemy-v3-storage-maintenance.service') < stopped_verification_block.index('writers_stopped=1')


def test_activation_uses_one_v3_container_lifetime_for_both_work_inventories() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")

    assert "v1_container_identity" in workflow
    assert "v1_container_started_at" in workflow
    assert workflow.count('--v3-container-started-at "$v1_container_started_at"') == 2
    stopped_verification = workflow.index(
        'python3 "$candidate_release/scripts/vps_cutover_guard.py" inspect-active-work',
        workflow.index('docker stop --time 45 "$v1_container" >/dev/null || stop_pre'),
    )
    assert workflow.index("v1_container_identity_changed_while_fencing") < stopped_verification
    guard = (ROOT / "scripts" / "vps_cutover_guard.py").read_text(encoding="utf-8")
    assert "v3_container_start_time_unreadable" in guard


def test_emergency_closure_verifies_maintenance_or_stops_public_nginx() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    keep_closed = workflow[workflow.index("          keep_closed() {"):workflow.index("          rollback() {")]

    assert '"$status" = 503' in keep_closed
    assert '"$v1_running" = false' in keep_closed
    assert "systemctl stop nginx" in keep_closed
    assert 'systemctl is-active nginx' in keep_closed
    assert "GUARDED_ACTIVATE_CLOSED_FOR_RECOVERY" in keep_closed
    assert "GUARDED_ACTIVATE_CLOSURE_FAILED" in keep_closed
    assert "return 1" in keep_closed
    assert 'keep_closed "$reason" || {' in workflow


def test_successful_activation_restores_only_previously_active_maintenance_timer() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    assert 'maintenance_timer_was_active=0\n          if systemctl is-active --quiet alchemy-v3-storage-maintenance.timer; then maintenance_timer_was_active=1; fi' in workflow
    success = workflow[workflow.index("systemctl start alchemy-v2-sync-worker.service"):workflow.index("GUARDED_ACTIVATE_RESULT=pass")]
    restore = 'if [ "$maintenance_timer_was_active" = 1 ]; then'
    verify_active = 'systemctl is-active --quiet alchemy-v3-storage-maintenance.timer || fail_public_open maintenance_timer_restore_unverified'
    preserve_inactive = 'systemctl is-active --quiet alchemy-v3-storage-maintenance.timer && fail_public_open maintenance_timer_unexpectedly_active'
    digest_check = '[ "$(state_digest "$v1_media")" = "$before_digest" ] || fail_post historical_state_changed_before_public_open'
    open_gate = 'rm -f "$maintenance_flag" || fail_post public_gate_open_failed'
    public_smoke = 'wait_for_200 "$public_base_url/api/v2/health" || fail_public_open v2_public_health_failed'
    assert restore in success
    assert 'systemctl start alchemy-v3-storage-maintenance.timer || fail_public_open maintenance_timer_restore_failed' in success
    assert verify_active in success and preserve_inactive in success
    assert digest_check in success
    assert success.index(digest_check) < success.index(open_gate) < success.index(public_smoke) < success.index(restore)
    assert success.index(restore) < success.index(verify_active) < success.index(preserve_inactive) < workflow.index("GUARDED_ACTIVATE_RESULT=pass")


def test_emergency_nginx_fallback_rechecks_writer_state_from_fresh_baseline() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    keep_closed = workflow[workflow.index("          keep_closed() {"):workflow.index("          rollback() {")]
    fallback = keep_closed[keep_closed.index("systemctl stop nginx"):]
    assert fallback.index("writers_stopped=1") < fallback.index('for unit in "${v2_units[@]}" alchemy-v3-storage-maintenance.timer')
    assert fallback.index('for unit in "${v2_units[@]}" alchemy-v3-storage-maintenance.timer') < fallback.index('if { [ "$nginx_state" = inactive ]')


def test_api_background_worker_ownership_is_durable_and_survives_rollback() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    runtime_env = (ROOT / "custom_media_agent_2_0" / "deploy" / "systemd" / "alchemy-v2-api-runtime.env").read_text(encoding="utf-8")
    runtime_drop_in = (
        ROOT / "custom_media_agent_2_0" / "deploy" / "systemd" / "alchemy-v2-api.service.d"
        / "90-alchemy-worker-ownership.conf"
    ).read_text(encoding="utf-8")
    rollback = workflow[workflow.index("          rollback() {"):workflow.index("          fail_post() {")]

    assert runtime_env.splitlines() == [
        "V2_TASK_QUEUE_INLINE_WORKER_ENABLED=false",
        "V2_SYNC_GITHUB_ON_STARTUP=false",
        "V2_ENABLE_REMOTE_GITHUB_SYNC=false",
    ]
    assert runtime_drop_in.splitlines() == [
        "[Service]", "EnvironmentFile=/etc/alchemy/alchemy-v2-api-runtime.env",
    ]
    assert "install_api_background_worker_contract || { keep_closed api_runtime_contract_restore_failed; exit 1; }" in rollback
    assert rollback.index("install_api_background_worker_contract") < rollback.index("restart_v2")
    assert "remove_cutover_api_override" not in rollback
    assert "verify_v2_unit_contract || { keep_closed old_v2_unit_contract_unverified; exit 1; }" in rollback
    assert "old_v2_api_background_writer_enabled" in rollback


def test_rollback_keeps_public_gate_closed_until_old_stack_is_fully_verified() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    rollback = workflow[workflow.index("          rollback() {"):workflow.index("          fail_post() {")]

    assert "rollback_ok" not in rollback
    assert "store_restore_failed; exit 1" in rollback
    assert "old_v2_health_failed; exit 1" in rollback
    assert rollback.index("restore \\") < rollback.index("compose_for \"$old_release\" up")
    assert rollback.index("restart_v2") < rollback.index("wait_for_200 http://127.0.0.1:8020/api/v2/health")
    assert 'install -m 644 "$nginx_config_backup" "$nginx_config"' in rollback
    assert rollback.index('install -m 644 "$nginx_config_backup" "$nginx_config"') > rollback.index("wait_for_200 http://127.0.0.1:8020/api/v2/health")
    assert rollback.index('rm -f "$maintenance_flag"') < rollback.index('wait_for_200 "$public_base_url/api/v2/health"')
    assert 'wait_for_200 "$public_base_url/api/v2/health" || { keep_closed old_public_health_failed; exit 1; }' in rollback


def test_candidate_image_is_locked_and_contains_expected_revision_label() -> None:
    candidate = (ROOT / ".github" / "workflows" / "guarded-vps-candidate.yml").read_text(encoding="utf-8")
    activate = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "src_skeleton" / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "flock" in candidate and "flock" in activate
    assert "ALCHEMY_REVISION" in candidate
    assert "org.opencontainers.image.revision" in dockerfile
    assert "ALCHEMY_REVISION" in compose
    assert "candidate_image_revision_mismatch" in activate
    assert "estimate-space" in activate


def test_maintenance_flag_is_checked_before_any_https_route() -> None:
    nginx = (ROOT / "alchemy-media-agent.nginx.conf").read_text(encoding="utf-8")
    flag = "if (-f /etc/alchemy/alchemy-media-agent-maintenance)"
    assert nginx.index(flag) < nginx.index("location / {")
    assert "return 503;" in nginx[nginx.index(flag):nginx.index("location / {")]


def test_legacy_vps_entrypoints_stop_before_remote_side_effects() -> None:
    direct = (ROOT / "scripts" / "deploy_vps.sh").read_text(encoding="utf-8")
    migration = (ROOT / "scripts" / "vps_migrate_release_layout.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "deploy-vps.yml").read_text(encoding="utf-8")

    assert direct.index('if [[ "$LOCAL_MODE" != "1" ]]; then') < direct.index("run_as_root()")
    assert "Direct VPS deployment is disabled" in direct
    assert "retired and performs no changes" in migration
    assert "exit 2" in migration
    assert "VPS_HOST" not in workflow
    assert "exit 2" in workflow


def test_v1_index_prepare_and_verify_share_the_container_storage_path() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    verifier = (ROOT / "scripts" / "prepare_v1_history_index.py").read_text(encoding="utf-8")
    prepare = workflow[workflow.index("          prepare_and_verify_target_indexes() {"):workflow.index("          restart_v2() {")]
    assert prepare.count("--storage-root \"$v1_root_in_container\" --verify") == 1
    assert "--storage-root \"$v1_media\" --verify" not in prepare
    assert prepare.count("--mount \"type=bind,src=$v1_media,dst=$v1_root_in_container") >= 2
    assert "--storage-root \"$v1_media\" --verify" not in workflow
    assert "--storage-root /app/.media_storage --verify || fail_post active_v1_history_index_unready" in workflow
    post_start = workflow[workflow.index("          docker run --rm --network none", workflow.index("active_v2_runtime_guard_failed")):workflow.index("active_v1_history_index_unready")]
    assert '--mount "type=bind,src=$v1_media,dst=/app/.media_storage"' in post_start
    assert '--mount "type=bind,src=$v1_media,dst=/app/.media_storage,readonly"' not in post_start
    assert '"?mode=ro"' in verifier


def test_v2_index_prepare_verify_and_write_probe_run_as_service_user() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    block = workflow[workflow.index("          prepare_and_verify_target_indexes() {"):workflow.index("          restart_v2() {")]
    assert block.count("runuser -u alchemy -- env") >= 3
    assert "prepare_v2_history_reads.py" in block
    assert "verify_v2_history_reads.py" in block
    assert "verify-v2-write-access" in block
    assert "V2_STORAGE_DIR=\"$v2_storage\"" in block
    verifier_positions = []
    cursor = 0
    while True:
        cursor = workflow.find("verify_v2_history_reads.py", cursor)
        if cursor < 0:
            break
        verifier_positions.append(cursor)
        cursor += 1
    assert len(verifier_positions) == 2
    for position in verifier_positions:
        assert "runuser -u alchemy -- env" in workflow[max(0, position - 350):position]
        env_prefix = workflow[max(0, position - 350):position]
        assert "V2_STORAGE_DIR=\"$v2_storage\"" in env_prefix
        assert "V2_TASK_QUEUE_DB_PATH=\"$v2_queue_db\"" in env_prefix


def test_candidate_and_activation_reject_staged_and_untracked_source_changes() -> None:
    candidate = (ROOT / ".github" / "workflows" / "guarded-vps-candidate.yml").read_text(encoding="utf-8")
    activate = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    for workflow in (candidate, activate):
        assert "git -C \"$release\" diff --quiet HEAD --" in workflow
        assert "git -C \"$release\" ls-files --others --exclude-standard -z" in workflow
        assert "src_skeleton/.env" in workflow
        assert "verify_release_source_tree \"$candidate_release\"" in workflow
    assert "git -C \"$active_release\" diff --quiet ||" not in candidate
    assert "git -C \"$old_release\" diff --quiet ||" not in activate
    assert candidate.index("verify_release_source_tree \"$candidate_release\"") < candidate.index("compose_candidate build")
    assert activate.index("verify_release_source_tree \"$candidate_release\"") < activate.index("maintenance_active=1")


def test_rollback_restores_inactive_timer_and_service_before_reopening_public_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "guarded-vps-activate.yml").read_text(encoding="utf-8")
    rollback = workflow[workflow.index("          rollback() {"):workflow.index("          fail_post() {")]
    inactive = rollback[rollback.index("else", rollback.index('if [ "$maintenance_timer_was_active" = 1 ]; then')):]
    assert "systemctl stop alchemy-v3-storage-maintenance.timer" in inactive
    assert "systemctl stop alchemy-v3-storage-maintenance.service" in inactive
    assert "systemctl is-active --quiet alchemy-v3-storage-maintenance.timer && { keep_closed" in inactive
    assert "systemctl is-active --quiet alchemy-v3-storage-maintenance.service && { keep_closed" in inactive
    assert rollback.index("maintenance_timer_restore_inactive") < rollback.index('install -m 644 "$nginx_config_backup" "$nginx_config"')


def test_git_head_comparison_detects_staged_and_untracked_source_changes(tmp_path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)

    assert git("init", "-q").returncode == 0
    assert git("config", "user.email", "test@example.invalid").returncode == 0
    assert git("config", "user.name", "Cutover Test").returncode == 0
    source = repo / "src.py"
    source.write_text("stable\n", encoding="utf-8")
    assert git("add", "src.py").returncode == 0
    assert git("commit", "-qm", "baseline").returncode == 0
    source.write_text("staged edit\n", encoding="utf-8")
    assert git("add", "src.py").returncode == 0
    assert git("diff", "--quiet", "HEAD", "--").returncode != 0
    assert git("reset", "-q", "HEAD", "--", "src.py").returncode == 0
    assert git("diff", "--quiet", "HEAD", "--").returncode != 0
    assert git("checkout", "--", "src.py").returncode == 0
    (repo / "unexpected.py").write_text("untracked\n", encoding="utf-8")
    untracked = git("ls-files", "--others", "--exclude-standard", "-z")
    assert untracked.returncode == 0 and "unexpected.py" in untracked.stdout
    (repo / ".gitignore").write_text("src_skeleton/.env\n", encoding="utf-8")
    (repo / "src_skeleton").mkdir()
    (repo / "src_skeleton" / ".env").write_text("runtime=true\n", encoding="utf-8")
    assert "src_skeleton/.env" not in git("ls-files", "--others", "--exclude-standard", "-z").stdout
