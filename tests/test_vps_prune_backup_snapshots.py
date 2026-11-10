from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'prune_backup_snapshots', Path(__file__).parents[1] / 'scripts/vps_prune_backup_snapshots.py'
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

ACTIVE_SHA = 'a' * 40
ROLLBACK_SHA = 'b' * 40
KEEP_NAME = 'pr29-' + ACTIVE_SHA[:12] + '-20261109T051417Z'


def fixture_snapshots(tmp_path: Path):
    root = tmp_path.resolve()
    keep = root / KEEP_NAME
    stores = keep / 'stores'
    contract = keep / 'runtime-contract'
    stores.mkdir(parents=True)
    contract.mkdir()
    (stores / 'sqlite-0000.db').write_bytes(b'rollback database')
    (stores / 'manifest.json').write_text(json.dumps({
        'schema_version': 2,
        'restore_scope': 'pre_candidate_writer_start_only',
        'allowed_roots': ['/var/lib/alchemy/v1/media_storage'],
        'records': [{'kind': 'sqlite', 'path': '/var/lib/alchemy/v1/media_storage/repository.sqlite3',
                     'existed': True, 'backup': 'sqlite-0000.db'}],
    }), encoding='utf-8')
    for name in ('alchemy-media-agent.nginx.conf', 'v2_runtime_guard.py', 'alchemy-v2-api.service',
                 'alchemy-v2-worker.service', 'alchemy-v2-sync-worker.service', 'alchemy-v2.env'):
        relative = Path(name) if name == 'alchemy-media-agent.nginx.conf' else Path('runtime-contract') / name
        target = keep / relative
        target.write_text('preserved rollback contract', encoding='utf-8')

    old_names = ['pr29-' + 'c' * 12 + '-20261108T010101Z', 'pr29-' + 'd' * 12 + '-20261107T010101Z']
    for name in old_names:
        backup = root / name
        backup.mkdir()
        (backup / 'old.db').write_bytes(name.encode('ascii'))
    return root, keep, [root / name for name in old_names]


def test_inventory_selection_tracks_full_snapshot_metadata_and_preserves_unclassified_entries(tmp_path):
    root, keep, old = fixture_snapshots(tmp_path)
    (root / 'operator-note.txt').write_text('preserve', encoding='utf-8')
    snapshots, others = guard.inventory_snapshots(root=root)
    assert {item['name'] for item in snapshots} == {KEEP_NAME, *(path.name for path in old)}
    assert guard.parse_selection(','.join(guard.selection_token(item) for item in snapshots))
    assert others == [{'name': 'operator-note.txt', 'kind': 'file_or_link', 'bytes': 8}]
    guard.verify_keep_snapshot(next(item for item in snapshots if item['name'] == KEEP_NAME), ACTIVE_SHA, root=root)


def test_changed_snapshot_after_inspect_blocks_all_deletion(tmp_path):
    root, keep, old = fixture_snapshots(tmp_path)
    before, _ = guard.inventory_snapshots(root=root)
    selection = ','.join(guard.selection_token(item) for item in before)
    (old[0] / 'old.db').write_bytes(b'changed after inspect')
    with pytest.raises(guard.SnapshotBlocked, match='inventory_changed_since_inspection'):
        guard.retire_snapshots(selection, KEEP_NAME, ACTIVE_SHA, ROLLBACK_SHA,
                               root=root, ledger=root / 'ledger.jsonl',
                               live_check=lambda: None, reference_check=lambda _: None)
    assert keep.is_dir() and all(path.is_dir() for path in old)


def test_retirement_keeps_only_verified_previous_release_checkpoint_and_records_receipts(tmp_path):
    root, keep, old = fixture_snapshots(tmp_path)
    before, _ = guard.inventory_snapshots(root=root)
    selection = ','.join(guard.selection_token(item) for item in before)
    ledger = root / 'vps-backup-snapshot-retirement.jsonl'
    checked = []
    result = guard.retire_snapshots(selection, KEEP_NAME, ACTIVE_SHA, ROLLBACK_SHA,
                                    root=root, ledger=ledger,
                                    live_check=lambda: checked.append('live'),
                                    reference_check=lambda paths: checked.append(tuple(paths)))
    assert result['retired_count'] == 2
    assert {item['name'] for item in result['retired']} == {path.name for path in old}
    assert result['kept_snapshot'] == KEEP_NAME
    assert keep.is_dir() and all(not path.exists() for path in old)
    remaining, _ = guard.inventory_snapshots(root=root)
    assert [item['name'] for item in remaining] == [KEEP_NAME]
    states = [json.loads(line)['state'] for line in ledger.read_text(encoding='utf-8').splitlines()]
    assert states == ['intent', 'removed', 'intent', 'removed']
    assert checked.count('live') == 2


def test_keep_checkpoint_must_match_current_revision_and_have_complete_restore_manifest(tmp_path):
    root, keep, _ = fixture_snapshots(tmp_path)
    snapshot = guard.snapshot_identity(KEEP_NAME, root=root)
    with pytest.raises(guard.SnapshotBlocked, match='keep_snapshot_not_current_cutover'):
        guard.verify_keep_snapshot(snapshot, ROLLBACK_SHA, root=root)
    (keep / 'runtime-contract/alchemy-v2-worker.service').unlink()
    with pytest.raises(guard.SnapshotBlocked, match='runtime_contract_incomplete'):
        guard.verify_keep_snapshot(snapshot, ACTIVE_SHA, root=root)


def test_unsupported_or_linked_snapshot_entries_block_inventory(tmp_path):
    root, _, old = fixture_snapshots(tmp_path)
    try:
        (old[0] / 'linked').symlink_to(old[0] / 'old.db')
    except OSError:
        pytest.skip('Host cannot create symlinks')
    with pytest.raises(guard.SnapshotBlocked, match='unsupported_entry'):
        guard.inventory_snapshots(root=root)


def test_mountpoint_inside_snapshot_blocks_recursive_deletion(tmp_path, monkeypatch):
    root, _, old = fixture_snapshots(tmp_path)
    mount = old[0] / 'nested'
    mount.mkdir()
    original_is_mount = Path.is_mount
    monkeypatch.setattr(Path, 'is_mount', lambda path: path == mount or original_is_mount(path))
    with pytest.raises(guard.SnapshotBlocked, match='contains_mount_point'):
        guard.inventory_snapshots(root=root)


def test_mountinfo_identity_detects_same_device_bind_mounts(tmp_path, monkeypatch):
    root, _, old = fixture_snapshots(tmp_path)
    mount = old[0] / 'nested'
    mount.mkdir()
    monkeypatch.setattr(guard, 'mount_points', lambda: {mount.as_posix()})
    with pytest.raises(guard.SnapshotBlocked, match='contains_mount_point'):
        guard.inventory_snapshots(root=root)


def test_mount_added_after_retirement_intent_stops_before_recursive_delete(tmp_path, monkeypatch):
    root, keep, old = fixture_snapshots(tmp_path)
    mount = old[0] / 'nested'
    mount.mkdir()
    before, _ = guard.inventory_snapshots(root=root)
    selection = ','.join(guard.selection_token(item) for item in before)
    checks = []

    def references(_paths):
        checks.append(True)
        if len(checks) == 2:
            monkeypatch.setattr(guard, 'mount_points', lambda: {mount.as_posix()})

    ledger = root / 'vps-backup-snapshot-retirement.jsonl'
    with pytest.raises(guard.SnapshotBlocked, match='contains_mount_point'):
        guard.retire_snapshots(selection, KEEP_NAME, ACTIVE_SHA, ROLLBACK_SHA,
                               root=root, ledger=ledger, live_check=lambda: None,
                               reference_check=references)
    assert keep.is_dir() and all(path.is_dir() for path in old)
    records = [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()]
    assert [record['state'] for record in records] == ['intent']


def test_mountinfo_parser_decodes_escaped_mount_paths():
    parsed = guard._parse_mountinfo('36 25 8:1 / /var/backups/alchemy/a\\040b rw,relatime - ext4 /dev/vda1 rw')
    assert parsed == {'/var/backups/alchemy/a b'}


def test_inventory_names_the_unclassified_snapshot_entry_and_stops(tmp_path):
    root, _, _ = fixture_snapshots(tmp_path)
    (root / 'pr29-partial').mkdir()
    with pytest.raises(guard.SnapshotBlocked, match='snapshot_name_invalid:pr29-partial'):
        guard.inventory_snapshots(root=root)


def test_selection_rejects_duplicate_or_malformed_tokens(tmp_path):
    root, _, _ = fixture_snapshots(tmp_path)
    snapshots, _ = guard.inventory_snapshots(root=root)
    token = guard.selection_token(snapshots[0])
    with pytest.raises(guard.SnapshotBlocked, match='selection_invalid'):
        guard.parse_selection(token + ',../unsafe')
    with pytest.raises(guard.SnapshotBlocked, match='selection_invalid'):
        guard.parse_selection(token + ',' + token)


def test_activation_prunes_only_after_public_acceptance_and_keeps_the_new_rollback_checkpoint():
    workflow = (Path(__file__).parents[1] / '.github/workflows/guarded-vps-activate.yml').read_text(encoding='utf-8')
    assert workflow.index('protected_ok "$project_status" || fail_public_open v3_projects_not_protected') < workflow.index('--mode retain-latest')
    assert workflow.index('--mode retain-latest') < workflow.index('GUARDED_ACTIVATE_RESULT=pass')
    assert '--keep-name "${maintenance_backup##*/}"' in workflow
    assert 'GUARDED_ACTIVATE_BACKUP_RETENTION=blocked' in workflow


def test_live_state_requires_the_exact_rollback_release_and_verified_runtime(monkeypatch, tmp_path):
    releases = tmp_path / 'releases'
    active = releases / ('doc276-277-' + ACTIVE_SHA[:12])
    rollback = releases / ('doc276-277-' + ROLLBACK_SHA[:12])
    active.mkdir(parents=True)
    rollback.mkdir()
    runtime_guard = rollback / 'ops/vps-release/v2_runtime_guard.py'
    runtime_guard.parent.mkdir(parents=True)
    runtime_guard.write_text('guard', encoding='utf-8')
    monkeypatch.setattr(guard, 'RELEASES', releases)
    monkeypatch.setattr(guard, 'ACTIVE', active)
    calls = []

    def run(*args):
        calls.append(args)
        if args[:3] == ('git', '-C', str(active)):
            return ACTIVE_SHA
        if args[:3] == ('git', '-C', str(rollback)):
            return ROLLBACK_SHA
        if args[:1] == ('python3',):
            return ''
        if args[:3] == ('docker', 'image', 'inspect'):
            revision = ACTIVE_SHA if args[3].endswith(':latest') else ROLLBACK_SHA
            return json.dumps([{'Config': {'Labels': {'org.opencontainers.image.revision': revision}}}])
        if args[:2] == ('docker', 'inspect'):
            return json.dumps([{'State': {'Running': True}, 'Config': {'Image': 'alchemy-media-agent:latest'}}])
        if args[:2] == ('systemctl', 'is-active'):
            return ''
        raise AssertionError(args)

    monkeypatch.setattr(guard, 'command', run)
    guard.assert_live_state(ACTIVE_SHA, ROLLBACK_SHA)
    assert ('python3', str(runtime_guard), '--release', str(rollback), '--verify') in calls

    runtime_guard.unlink()
    with pytest.raises(guard.SnapshotBlocked, match='rollback_runtime_guard_missing'):
        guard.assert_live_state(ACTIVE_SHA, ROLLBACK_SHA)
