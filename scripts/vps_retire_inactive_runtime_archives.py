#!/usr/bin/env python3
"""Inspect and retire only unreferenced, re-downloadable V2 runtime archives."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shlex
import stat
import subprocess
import tarfile
from datetime import datetime, timezone
from typing import Callable

ROOT = Path('/opt/alchemy-media-agent-releases')
ACTIVE = Path('/opt/alchemy-media-agent')
LEDGER = Path('/var/backups/alchemy/vps-runtime-archive-retirement.jsonl')
REVISION = re.compile(r'[0-9a-f]{40}')
MAX_SELECTION = 40
CONFIRMATION = 'RETIRE-UNREFERENCED-V2-RUNTIME-ARCHIVES'


class RetirementBlocked(RuntimeError):
    pass


def command(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RetirementBlocked('inventory_command_failed:' + ':'.join(args[:2]) + ':' + str(result.returncode))
    return result.stdout


def systemd_references() -> list[str]:
    references = []
    seen = set()
    pending = [Path(path) for path in shlex.split(command('systemctl', 'show', '--property=UnitPath', '--value'))]
    if not pending or any(not path.is_absolute() for path in pending):
        raise RetirementBlocked('systemd_search_paths_unavailable')
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
                references.append(str(path))
                references.append(str(path.resolve()))
                references.append(path.read_text(encoding='utf-8'))
    if not references:
        raise RetirementBlocked('systemd_definitions_unavailable')
    return references


def assert_unreferenced(releases: list[Path], expected_active: str, *, root: Path = ROOT,
                        active: Path = ACTIVE) -> None:
    if not REVISION.fullmatch(expected_active):
        raise RetirementBlocked('invalid_active_revision')
    if active.resolve() != root / ('doc276-277-' + expected_active[:12]):
        raise RetirementBlocked('active_release_changed')

    protected = {active.resolve()}
    for tag in ('alchemy-media-agent:latest', 'alchemy-media-agent:rollback-pr29'):
        command('docker', 'image', 'inspect', tag)
    image_ids = command('docker', 'image', 'ls', '-q', '--filter', 'reference=alchemy-media-agent:*').split()
    if image_ids:
        images = json.loads(command('docker', 'image', 'inspect', *sorted(set(image_ids))))
    else:
        images = []
    for image in images:
        revision = (image.get('Config', {}).get('Labels') or {}).get('org.opencontainers.image.revision', '')
        if not REVISION.fullmatch(revision):
            raise RetirementBlocked('retained_image_revision_unavailable')
        protected.add(root / ('doc276-277-' + revision[:12]))
    if protected.intersection(releases):
        raise RetirementBlocked('retained_release')

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
    for release in releases:
        if any(str(release) in reference for reference in references):
            raise RetirementBlocked('release_still_referenced')


def assert_health() -> None:
    for url in ('http://127.0.0.1:8017/healthz', 'http://127.0.0.1:8020/api/v2/health'):
        command('curl', '--noproxy', '*', '-fsS', '--connect-timeout', '5', '--max-time', '10', url)


def _release_path(revision: str, root: Path) -> Path:
    if not REVISION.fullmatch(revision):
        raise RetirementBlocked('invalid_revision')
    release = root / ('doc276-277-' + revision[:12])
    if root.resolve() != root or release.resolve() != release or not release.is_dir():
        raise RetirementBlocked('release_path_invalid')
    if command('git', '-C', str(release), 'rev-parse', 'HEAD').strip() != revision:
        raise RetirementBlocked('release_identity_mismatch')
    return release


def _validate_archive(revision: str, root: Path = ROOT) -> dict:
    release = _release_path(revision, root)
    v2_root = release / 'custom_media_agent_2_0'
    runtime = v2_root / '.venv'
    archive = v2_root / '.venv.inactive.tar.gz'
    if v2_root.resolve() != v2_root or runtime.resolve() != runtime or archive.resolve() != archive:
        raise RetirementBlocked('linked_runtime_path')
    if runtime.exists() or runtime.is_symlink():
        raise RetirementBlocked('live_runtime_present')
    try:
        info = archive.lstat()
    except FileNotFoundError:
        raise RetirementBlocked('runtime_archive_missing') from None
    if not stat.S_ISREG(info.st_mode):
        raise RetirementBlocked('runtime_archive_not_regular_file')

    # Preserve user-local config and source. Refuse unexpected untracked release content.
    command('git', '-C', str(release), 'diff', '--quiet', 'HEAD', '--')
    # Include ignored files too; a broad .gitignore must not hide local data.
    untracked = command('git', '-C', str(release), 'ls-files', '--others', '-z')
    allowed = {'custom_media_agent_2_0/.venv.inactive.tar.gz', 'src_skeleton/.env'}
    if any(item not in allowed for item in untracked.split('\0') if item):
        raise RetirementBlocked('unexpected_untracked_release_content')

    member_count = 0
    seen_members = set()
    with tarfile.open(archive, 'r:gz') as saved:
        for member in saved:
            member_count += 1
            name = PurePosixPath(member.name)
            parts = name.parts
            if (not parts or parts[0] != '.venv' or name.is_absolute() or '..' in parts
                    or member.name in seen_members
                    or any(part in {'.render_bridge_primary', '.media_storage', '.env'} for part in parts)
                    or any(PurePosixPath(part).suffix in {'.sqlite', '.sqlite3', '.db'} for part in parts)):
                raise RetirementBlocked('runtime_archive_contains_state')
            if not (member.isdir() or member.isfile() or member.issym()):
                raise RetirementBlocked('runtime_archive_member_unsupported')
            seen_members.add(member.name)
    if member_count == 0:
        raise RetirementBlocked('runtime_archive_empty')

    return {
        'revision': revision,
        'release': str(release),
        'archive': str(archive),
        'bytes': info.st_size,
        'mtime_ns': info.st_mtime_ns,
        'mode': stat.S_IMODE(info.st_mode),
        'uid': info.st_uid,
        'gid': info.st_gid,
        'device': info.st_dev,
        'inode': info.st_ino,
        'members': member_count,
    }


def inventory_archives(expected_active: str, *, root: Path = ROOT, active: Path = ACTIVE) -> list[dict]:
    if not root.is_dir() or root.resolve() != root:
        raise RetirementBlocked('release_root_invalid')
    candidates = []
    for release in sorted(root.glob('doc276-277-*')):
        if not release.is_dir():
            continue
        archive = release / 'custom_media_agent_2_0' / '.venv.inactive.tar.gz'
        if archive.exists() or archive.is_symlink():
            head = command('git', '-C', str(release), 'rev-parse', 'HEAD').strip()
            candidates.append(_validate_archive(head, root))
    assert_unreferenced([Path(item['release']) for item in candidates], expected_active,
                        root=root, active=active)
    return candidates


def selection_token(item: dict) -> str:
    return ':'.join(str(item[key]) for key in ('revision', 'device', 'inode', 'bytes', 'mtime_ns'))


def parse_selection(selection: str) -> dict[str, dict[str, int]]:
    if not selection or len(selection) > 8192:
        raise RetirementBlocked('selection_invalid')
    result = {}
    for token in selection.split(','):
        parts = token.split(':')
        if len(parts) != 5 or not REVISION.fullmatch(parts[0]) or any(not part.isdecimal() for part in parts[1:]):
            raise RetirementBlocked('selection_invalid')
        revision = parts[0]
        if revision in result:
            raise RetirementBlocked('selection_duplicate')
        result[revision] = dict(zip(('device', 'inode', 'bytes', 'mtime_ns'), map(int, parts[1:])))
    if not 1 <= len(result) <= MAX_SELECTION:
        raise RetirementBlocked('selection_too_large')
    return result


def verify_inspected_inventory(selection: str, current: list[dict]) -> list[str]:
    inspected = parse_selection(selection)
    actual = {item['revision']: {key: item[key] for key in ('device', 'inode', 'bytes', 'mtime_ns')} for item in current}
    if inspected != actual:
        raise RetirementBlocked('inventory_changed_since_inspection')
    return sorted(inspected)


def append_ledger(record: dict, ledger: Path = LEDGER) -> None:
    parent = ledger.parent
    if parent.resolve() != parent or not parent.is_dir() or ledger.is_symlink():
        raise RetirementBlocked('retirement_ledger_path_invalid')
    if ledger.exists() and not ledger.is_file():
        raise RetirementBlocked('retirement_ledger_not_regular_file')
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


def retire_archives(revisions: list[str], expected_active: str, *, root: Path = ROOT,
                    active: Path = ACTIVE, ledger: Path = LEDGER,
                    recheck: Callable[[], None] | None = None) -> dict:
    if not revisions or len(revisions) > MAX_SELECTION or len(set(revisions)) != len(revisions):
        raise RetirementBlocked('invalid_selection')
    plans = [_validate_archive(revision, root) for revision in revisions]
    releases = [Path(item['release']) for item in plans]
    assert_unreferenced(releases, expected_active, root=root, active=active)
    if recheck is None:
        recheck = lambda: assert_unreferenced(releases, expected_active, root=root, active=active)

    retired = []
    for plan in plans:
        current = _validate_archive(plan['revision'], root)
        if current != plan:
            raise RetirementBlocked('runtime_archive_changed_after_inspection')
        recheck()
        stamp = datetime.now(timezone.utc).isoformat()
        entry = {
            'schema_version': 1,
            'operation': 'retire_inactive_v2_runtime_archive',
            'revision': plan['revision'],
            'release': plan['release'],
            'archive': plan['archive'],
            'bytes': plan['bytes'],
            'mtime_ns': plan['mtime_ns'],
            'mode': plan['mode'],
            'uid': plan['uid'],
            'gid': plan['gid'],
            'timestamp_utc': stamp,
        }
        append_ledger({**entry, 'state': 'intent'}, ledger)
        os.unlink(plan['archive'])
        if hasattr(os, 'O_DIRECTORY'):
            directory_fd = os.open(Path(plan['archive']).parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        if Path(plan['archive']).exists():
            raise RetirementBlocked('runtime_archive_still_present')
        append_ledger({**entry, 'state': 'removed'}, ledger)
        retired.append({'revision': plan['revision'], 'bytes': plan['bytes']})
    return {'retired': retired, 'retired_count': len(retired),
            'freed_archive_bytes': sum(item['bytes'] for item in retired)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-active-sha', required=True)
    parser.add_argument('--mode', choices=('inspect', 'retire'), required=True)
    parser.add_argument('--selection', default='')
    parser.add_argument('--confirmation', default='')
    args = parser.parse_args()
    health_before = False
    exit_code = 0
    try:
        if not REVISION.fullmatch(args.expected_active_sha):
            raise RetirementBlocked('invalid_active_revision')
        assert_health()
        health_before = True
        if args.mode == 'inspect':
            if args.selection or args.confirmation:
                raise RetirementBlocked('inspect_inputs_invalid')
            candidates = inventory_archives(args.expected_active_sha)
            if len(candidates) > MAX_SELECTION:
                raise RetirementBlocked('selection_too_large')
            print(json.dumps({'status': 'plan', 'archives': candidates,
                              'archive_count': len(candidates),
                              'selection': ','.join(selection_token(item) for item in candidates),
                              'potential_bytes': sum(item['bytes'] for item in candidates)}, sort_keys=True), flush=True)
            print(json.dumps({'status': 'complete', 'mode': 'inspect'}, sort_keys=True), flush=True)
        else:
            if args.confirmation != CONFIRMATION:
                raise RetirementBlocked('confirmation_invalid')
            current = inventory_archives(args.expected_active_sha)
            revisions = verify_inspected_inventory(args.selection, current)
            result = retire_archives(revisions, args.expected_active_sha)
            print(json.dumps({'status': 'complete', 'mode': 'retire', **result}, sort_keys=True), flush=True)
    except (RetirementBlocked, OSError, ValueError, tarfile.TarError) as error:
        reason = str(error) if isinstance(error, RetirementBlocked) else type(error).__name__
        print(json.dumps({'status': 'blocked', 'reason': reason}, sort_keys=True), flush=True)
        exit_code = 1
    finally:
        if health_before:
            try:
                assert_health()
                print('GUARDED_RUNTIME_ARCHIVE_RETIRE_HEALTH=pass', flush=True)
            except (RetirementBlocked, OSError, ValueError) as error:
                reason = str(error) if isinstance(error, RetirementBlocked) else type(error).__name__
                print(json.dumps({'status': 'health_failed_after', 'reason': reason}, sort_keys=True), flush=True)
                exit_code = 1
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
