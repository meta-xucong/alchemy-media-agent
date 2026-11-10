#!/usr/bin/env python3
"""Keep one verified pre-cutover rollback snapshot and retire older snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shlex
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from typing import Callable

ROOT = Path('/var/backups/alchemy')
ACTIVE = Path('/opt/alchemy-media-agent')
RELEASES = Path('/opt/alchemy-media-agent-releases')
LEDGER = ROOT / 'vps-backup-snapshot-retirement.jsonl'
SNAPSHOT_NAME = re.compile(r'pr29-[0-9a-f]{12}-[0-9]{8}T[0-9]{6}Z')
REVISION = re.compile(r'[0-9a-f]{40}')
MAX_SELECTION = 100
MAX_SELECTION_BYTES = 20000
CONFIRMATION = 'RETAIN-ONE-ROLLBACK-SNAPSHOT'
V2_UNITS = ('alchemy-v2-api.service', 'alchemy-v2-worker.service', 'alchemy-v2-sync-worker.service')


class SnapshotBlocked(RuntimeError):
    pass


def command(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode:
        raise SnapshotBlocked('inventory_command_failed:' + ':'.join(args[:2]) + ':' + str(result.returncode))
    return result.stdout


def assert_health() -> None:
    for url in ('http://127.0.0.1:8017/healthz', 'http://127.0.0.1:8020/api/v2/health'):
        command('curl', '--noproxy', '*', '-fsS', '--connect-timeout', '5', '--max-time', '10', url)


def assert_live_state(expected_active: str, expected_rollback: str) -> None:
    if not REVISION.fullmatch(expected_active) or not REVISION.fullmatch(expected_rollback):
        raise SnapshotBlocked('release_revision_invalid')
    release = RELEASES / ('doc276-277-' + expected_active[:12])
    if ACTIVE.resolve() != release or command('git', '-C', str(release), 'rev-parse', 'HEAD').strip() != expected_active:
        raise SnapshotBlocked('active_release_changed')
    rollback_release = RELEASES / ('doc276-277-' + expected_rollback[:12])
    if (rollback_release.resolve() != rollback_release or not rollback_release.is_dir()
            or command('git', '-C', str(rollback_release), 'rev-parse', 'HEAD').strip() != expected_rollback):
        raise SnapshotBlocked('rollback_release_unavailable')
    runtime_guard = rollback_release / 'ops' / 'vps-release' / 'v2_runtime_guard.py'
    if not runtime_guard.is_file():
        raise SnapshotBlocked('rollback_runtime_guard_missing')
    command('python3', str(runtime_guard), '--release', str(rollback_release), '--verify')

    def image_revision(tag: str) -> str:
        images = json.loads(command('docker', 'image', 'inspect', tag))
        if len(images) != 1:
            raise SnapshotBlocked('retained_image_unavailable')
        labels = (images[0].get('Config', {}).get('Labels') or {})
        revision = labels.get('org.opencontainers.image.revision', '')
        if not REVISION.fullmatch(revision):
            raise SnapshotBlocked('retained_image_revision_unavailable')
        return revision

    if image_revision('alchemy-media-agent:latest') != expected_active:
        raise SnapshotBlocked('active_image_revision_mismatch')
    if image_revision('alchemy-media-agent:rollback-pr29') != expected_rollback:
        raise SnapshotBlocked('rollback_image_revision_mismatch')
    containers = json.loads(command('docker', 'inspect', 'alchemy-media-agent'))
    if len(containers) != 1 or not containers[0].get('State', {}).get('Running'):
        raise SnapshotBlocked('active_v1_container_unavailable')
    if containers[0].get('Config', {}).get('Image') != 'alchemy-media-agent:latest':
        raise SnapshotBlocked('active_v1_image_reference_changed')
    for unit in V2_UNITS:
        command('systemctl', 'is-active', '--quiet', unit)


def systemd_references() -> list[str]:
    references = []
    seen = set()
    pending = [Path(path) for path in shlex.split(command('systemctl', 'show', '--property=UnitPath', '--value'))]
    if not pending or any(not path.is_absolute() for path in pending):
        raise SnapshotBlocked('systemd_search_paths_unavailable')
    while pending:
        directory = pending.pop()
        if not directory.exists():
            continue
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for path in directory.iterdir():
            if path.is_dir():
                pending.append(path)
            elif path.suffix in {'.service', '.conf'} and path.is_file():
                references.extend((str(path), str(path.resolve()), path.read_text(encoding='utf-8')))
    if not references:
        raise SnapshotBlocked('systemd_definitions_unavailable')
    return references


def _parse_mountinfo(contents: str) -> set[str]:
    mounts = set()
    for line in contents.splitlines():
        fields = line.split()
        if len(fields) < 6:
            raise SnapshotBlocked('mount_inventory_invalid')
        mount = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), fields[4])
        if not mount.startswith('/'):
            raise SnapshotBlocked('mount_inventory_invalid')
        mounts.add(mount)
    return mounts


def mount_points() -> set[str]:
    if os.name == 'nt':
        return set()
    try:
        contents = Path('/proc/self/mountinfo').read_text(encoding='utf-8')
    except OSError:
        raise SnapshotBlocked('mount_inventory_unavailable') from None
    if not contents.strip():
        raise SnapshotBlocked('mount_inventory_unavailable')
    return _parse_mountinfo(contents)


def assert_unreferenced(paths: list[Path]) -> None:
    references = []
    container_ids = command('docker', 'ps', '-aq').split()
    if container_ids:
        for container in json.loads(command('docker', 'inspect', *container_ids)):
            references.extend(mount.get('Source', '') for mount in container.get('Mounts', []))
    references.extend(systemd_references())
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            references.append((process / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace'))
            links = [process / 'cwd', process / 'exe', *(process / 'fd').iterdir()]
            for link in links:
                try:
                    references.append(os.readlink(link))
                except (FileNotFoundError, ProcessLookupError):
                    pass
        except (FileNotFoundError, ProcessLookupError):
            continue
    for path in paths:
        if any(str(path) in reference for reference in references):
            raise SnapshotBlocked('snapshot_still_referenced')


def snapshot_identity(name: str, *, root: Path = ROOT, mounts: set[str] | None = None) -> dict:
    if not SNAPSHOT_NAME.fullmatch(name):
        raise SnapshotBlocked('snapshot_name_invalid')
    path = root / name
    if root.resolve() != root or path.resolve() != path:
        raise SnapshotBlocked('snapshot_path_linked')
    try:
        root_info = path.lstat()
    except FileNotFoundError:
        raise SnapshotBlocked('snapshot_missing') from None
    if not stat.S_ISDIR(root_info.st_mode):
        raise SnapshotBlocked('snapshot_not_directory')
    mounts = mount_points() if mounts is None else mounts
    if path.is_mount() or path.as_posix() in mounts:
        raise SnapshotBlocked('snapshot_mount_point')

    rows = []
    pending = [path]
    total_bytes = 0
    while pending:
        directory = pending.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name, reverse=True)
        except OSError:
            raise SnapshotBlocked('snapshot_inventory_failed') from None
        for child in children:
            try:
                info = child.lstat()
            except OSError:
                raise SnapshotBlocked('snapshot_inventory_changed') from None
            if (info.st_dev != root_info.st_dev or child.is_mount()
                    or child.as_posix() in mounts):
                raise SnapshotBlocked('snapshot_contains_mount_point')
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise SnapshotBlocked('snapshot_contains_unsupported_entry')
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise SnapshotBlocked('snapshot_file_hardlinked')
            relative = child.relative_to(path).as_posix()
            rows.append((relative, info.st_dev, info.st_ino, info.st_mode, info.st_size,
                         info.st_mtime_ns, info.st_ctime_ns, info.st_uid, info.st_gid, info.st_nlink))
            total_bytes += info.st_size
            if stat.S_ISDIR(info.st_mode):
                pending.append(child)
    rows.sort()
    fingerprint = hashlib.sha256(json.dumps(rows, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    return {
        'name': name,
        'path': str(path),
        'device': root_info.st_dev,
        'inode': root_info.st_ino,
        'mtime_ns': root_info.st_mtime_ns,
        'ctime_ns': root_info.st_ctime_ns,
        'mode': stat.S_IMODE(root_info.st_mode),
        'uid': root_info.st_uid,
        'gid': root_info.st_gid,
        'bytes': total_bytes,
        'entries': len(rows),
        'metadata_fingerprint': fingerprint,
    }


def inventory_snapshots(*, root: Path = ROOT) -> tuple[list[dict], list[dict]]:
    if not root.is_dir() or root.resolve() != root:
        raise SnapshotBlocked('backup_root_invalid')
    snapshots = []
    other_entries = []
    mounts = mount_points()
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if SNAPSHOT_NAME.fullmatch(path.name):
            snapshots.append(snapshot_identity(path.name, root=root, mounts=mounts))
        elif path.name.startswith('pr29-'):
            raise SnapshotBlocked('snapshot_name_invalid:' + path.name)
        else:
            try:
                info = path.lstat()
            except OSError:
                raise SnapshotBlocked('backup_root_inventory_failed') from None
            other_entries.append({'name': path.name, 'kind': 'directory' if stat.S_ISDIR(info.st_mode) else 'file_or_link',
                                  'bytes': info.st_size})
    if len(snapshots) > MAX_SELECTION:
        raise SnapshotBlocked('too_many_snapshots')
    return snapshots, other_entries


def selection_token(item: dict) -> str:
    values = (item['name'], item['device'], item['inode'], item['mtime_ns'], item['ctime_ns'],
              item['bytes'], item['entries'], item['metadata_fingerprint'])
    return ':'.join(str(value) for value in values)


def parse_selection(selection: str) -> dict[str, tuple]:
    if not selection or len(selection) > MAX_SELECTION_BYTES:
        raise SnapshotBlocked('selection_invalid')
    parsed = {}
    for token in selection.split(','):
        parts = token.split(':')
        if (len(parts) != 8 or not SNAPSHOT_NAME.fullmatch(parts[0])
                or any(not part.isdecimal() for part in parts[1:7])
                or not re.fullmatch(r'[0-9a-f]{64}', parts[7]) or parts[0] in parsed):
            raise SnapshotBlocked('selection_invalid')
        parsed[parts[0]] = (*map(int, parts[1:7]), parts[7])
    if not 1 <= len(parsed) <= MAX_SELECTION:
        raise SnapshotBlocked('selection_invalid')
    return parsed


def verify_inspected_inventory(selection: str, current: list[dict]) -> None:
    inspected = parse_selection(selection)
    actual = {item['name']: (item['device'], item['inode'], item['mtime_ns'], item['ctime_ns'],
                             item['bytes'], item['entries'], item['metadata_fingerprint']) for item in current}
    if inspected != actual:
        raise SnapshotBlocked('inventory_changed_since_inspection')


def verify_keep_snapshot(snapshot: dict, expected_active: str, *, root: Path = ROOT) -> None:
    name = snapshot['name']
    if not name.startswith('pr29-' + expected_active[:12] + '-'):
        raise SnapshotBlocked('keep_snapshot_not_current_cutover')
    base = root / name
    manifest_path = base / 'stores' / 'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise SnapshotBlocked('keep_snapshot_manifest_missing')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise SnapshotBlocked('keep_snapshot_manifest_invalid') from None
    if manifest.get('schema_version') != 2 or manifest.get('restore_scope') != 'pre_candidate_writer_start_only':
        raise SnapshotBlocked('keep_snapshot_manifest_invalid')
    roots = manifest.get('allowed_roots')
    records = manifest.get('records')
    if not isinstance(roots, list) or not roots or not isinstance(records, list) or not records:
        raise SnapshotBlocked('keep_snapshot_manifest_empty')
    persistent_root = PurePosixPath('/var/lib/alchemy')
    normalized_roots = set()
    for raw in roots:
        candidate = PurePosixPath(raw)
        if not candidate.is_absolute() or '..' in candidate.parts:
            raise SnapshotBlocked('keep_snapshot_root_invalid')
        try:
            candidate.relative_to(persistent_root)
        except ValueError:
            raise SnapshotBlocked('keep_snapshot_root_invalid') from None
        normalized_roots.add(str(candidate))
    sqlite_backups = 0
    for record in records:
        if not isinstance(record, dict) or record.get('kind') not in {'sqlite', 'source'}:
            raise SnapshotBlocked('keep_snapshot_record_invalid')
        source = PurePosixPath(record.get('path', ''))
        if not source.is_absolute() or '..' in source.parts or not any(
                source == PurePosixPath(root_name) or PurePosixPath(root_name) in source.parents
                for root_name in normalized_roots):
            raise SnapshotBlocked('keep_snapshot_record_path_invalid')
        if record.get('kind') == 'sqlite':
            sqlite_backups += 1
        if record.get('existed'):
            backup_name = record.get('backup')
            if not isinstance(backup_name, str) or Path(backup_name).name != backup_name:
                raise SnapshotBlocked('keep_snapshot_record_backup_invalid')
            saved = base / 'stores' / backup_name
            if saved.is_symlink() or not saved.is_file():
                raise SnapshotBlocked('keep_snapshot_record_backup_missing')
    if sqlite_backups == 0:
        raise SnapshotBlocked('keep_snapshot_sqlite_backup_missing')
    required = ['alchemy-media-agent.nginx.conf', 'runtime-contract/v2_runtime_guard.py',
                'runtime-contract/alchemy-v2-api.service', 'runtime-contract/alchemy-v2-worker.service',
                'runtime-contract/alchemy-v2-sync-worker.service', 'runtime-contract/alchemy-v2.env']
    for relative in required:
        candidate = base / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise SnapshotBlocked('keep_snapshot_runtime_contract_incomplete')


def append_ledger(record: dict, ledger: Path = LEDGER) -> None:
    if ledger.parent.resolve() != ledger.parent or not ledger.parent.is_dir() or ledger.is_symlink():
        raise SnapshotBlocked('retirement_ledger_path_invalid')
    if ledger.exists() and not ledger.is_file():
        raise SnapshotBlocked('retirement_ledger_not_regular_file')
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(ledger, flags, 0o600)
    try:
        if hasattr(os, 'fchmod'):
            os.fchmod(descriptor, 0o600)
        else:
            os.chmod(ledger, 0o600)
        payload = (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
        with os.fdopen(descriptor, 'ab', closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def retire_snapshots(selection: str, keep_name: str, expected_active: str, expected_rollback: str,
                     *, root: Path = ROOT, ledger: Path = LEDGER,
                     live_check: Callable[[], None] | None = None,
                     reference_check: Callable[[list[Path]], None] | None = None) -> dict:
    snapshots, _ = inventory_snapshots(root=root)
    verify_inspected_inventory(selection, snapshots)
    by_name = {item['name']: item for item in snapshots}
    if keep_name not in by_name:
        raise SnapshotBlocked('keep_snapshot_not_in_inventory')
    verify_keep_snapshot(by_name[keep_name], expected_active, root=root)
    deleting = [item for item in snapshots if item['name'] != keep_name]
    live_check = live_check or (lambda: assert_live_state(expected_active, expected_rollback))
    reference_check = reference_check or (lambda paths: assert_unreferenced(paths))
    live_check()
    reference_check([Path(item['path']) for item in deleting])

    removed = []
    for inspected in deleting:
        current = snapshot_identity(inspected['name'], root=root)
        if current != inspected:
            raise SnapshotBlocked('snapshot_changed_after_inspection')
        reference_check([Path(inspected['path'])])
        stamp = datetime.now(timezone.utc).isoformat()
        entry = {'schema_version': 1, 'operation': 'retire_old_backup_snapshot',
                 'name': inspected['name'], 'bytes': inspected['bytes'], 'entries': inspected['entries'],
                 'device': inspected['device'], 'inode': inspected['inode'], 'timestamp_utc': stamp}
        append_ledger({**entry, 'state': 'intent'}, ledger)
        current = snapshot_identity(inspected['name'], root=root)
        if current != inspected:
            raise SnapshotBlocked('snapshot_changed_before_delete')
        shutil.rmtree(inspected['path'])
        if Path(inspected['path']).exists():
            raise SnapshotBlocked('snapshot_still_present')
        append_ledger({**entry, 'state': 'removed'}, ledger)
        removed.append({'name': inspected['name'], 'bytes': inspected['bytes']})

    remaining, other_entries = inventory_snapshots(root=root)
    if [item['name'] for item in remaining] != [keep_name]:
        raise SnapshotBlocked('unexpected_snapshot_after_retirement')
    preserved = next((item for item in remaining if item['name'] == keep_name), None)
    if preserved != by_name[keep_name]:
        raise SnapshotBlocked('keep_snapshot_changed_during_retirement')
    verify_keep_snapshot(preserved, expected_active, root=root)
    live_check()
    return {'retired': removed, 'retired_count': len(removed),
            'freed_snapshot_bytes': sum(item['bytes'] for item in removed),
            'kept_snapshot': keep_name, 'other_root_entries_preserved': other_entries}


def retain_latest_snapshot(keep_name: str, expected_active: str, expected_rollback: str,
                           *, root: Path = ROOT, ledger: Path = LEDGER) -> dict:
    snapshots, _ = inventory_snapshots(root=root)
    selection = ','.join(selection_token(item) for item in snapshots)
    return retire_snapshots(selection, keep_name, expected_active, expected_rollback, root=root, ledger=ledger)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-active-sha', required=True)
    parser.add_argument('--expected-rollback-sha', required=True)
    parser.add_argument('--keep-name', required=True)
    parser.add_argument('--mode', choices=('inspect', 'retire', 'retain-latest'), required=True)
    parser.add_argument('--selection', default='')
    parser.add_argument('--confirmation', default='')
    args = parser.parse_args()
    health_before = False
    exit_code = 0
    try:
        assert_health()
        health_before = True
        assert_live_state(args.expected_active_sha, args.expected_rollback_sha)
        snapshots, other_entries = inventory_snapshots()
        if args.mode == 'inspect':
            if args.selection or args.confirmation:
                raise SnapshotBlocked('inspect_inputs_invalid')
            by_name = {item['name']: item for item in snapshots}
            if args.keep_name not in by_name:
                raise SnapshotBlocked('keep_snapshot_not_in_inventory')
            verify_keep_snapshot(by_name[args.keep_name], args.expected_active_sha)
            print(json.dumps({'status': 'plan', 'active_sha': args.expected_active_sha,
                              'rollback_sha': args.expected_rollback_sha, 'keep_snapshot': args.keep_name,
                              'snapshot_count': len(snapshots), 'delete_count': len(snapshots) - 1,
                              'delete_bytes': sum(item['bytes'] for item in snapshots if item['name'] != args.keep_name),
                              'snapshots': snapshots,
                              'selection': ','.join(selection_token(item) for item in snapshots),
                              'other_root_entries_preserved': other_entries}, sort_keys=True), flush=True)
        elif args.mode == 'retire':
            if args.confirmation != CONFIRMATION or not args.selection:
                raise SnapshotBlocked('confirmation_or_selection_invalid')
            result = retire_snapshots(args.selection, args.keep_name, args.expected_active_sha,
                                      args.expected_rollback_sha)
            print(json.dumps({'status': 'complete', 'mode': 'retire', **result}, sort_keys=True), flush=True)
        else:
            if args.selection or args.confirmation != CONFIRMATION:
                raise SnapshotBlocked('retention_inputs_invalid')
            result = retain_latest_snapshot(args.keep_name, args.expected_active_sha,
                                            args.expected_rollback_sha)
            print(json.dumps({'status': 'complete', 'mode': 'retain-latest', **result}, sort_keys=True), flush=True)
    except (SnapshotBlocked, OSError, ValueError) as error:
        reason = str(error) if isinstance(error, SnapshotBlocked) else type(error).__name__
        print(json.dumps({'status': 'blocked', 'reason': reason}, sort_keys=True), flush=True)
        exit_code = 1
    finally:
        if health_before:
            try:
                assert_health()
                print('GUARDED_BACKUP_RETENTION_HEALTH=pass', flush=True)
            except (SnapshotBlocked, OSError, ValueError) as error:
                reason = str(error) if isinstance(error, SnapshotBlocked) else type(error).__name__
                print(json.dumps({'status': 'health_failed_after', 'reason': reason}, sort_keys=True), flush=True)
                exit_code = 1
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
