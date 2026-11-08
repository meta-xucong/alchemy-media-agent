"""Recoverably archive exact inactive release dependencies; never application data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tarfile

ROOT = Path('/opt/alchemy-media-agent-releases')
ACTIVE = Path('/opt/alchemy-media-agent')
REVISION = re.compile(r'[0-9a-f]{40}')


class ArchiveBlocked(RuntimeError):
    pass


def command(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ArchiveBlocked('reference_inventory_command_failed:' + ':'.join(args[:2]) + ':' + str(result.returncode))
    return result.stdout


def validate_runtime(revision: str, root: Path = ROOT) -> Path:
    if not REVISION.fullmatch(revision):
        raise ArchiveBlocked('invalid_revision')
    release = root / ('doc276-277-' + revision[:12])
    runtime = release / 'custom_media_agent_2_0' / '.venv'
    if root.resolve() != root or release.resolve() != release or runtime.resolve() != runtime:
        raise ArchiveBlocked('linked_runtime_path')
    if not runtime.is_dir() or command('git', '-C', str(release), 'rev-parse', 'HEAD').strip() != revision:
        raise ArchiveBlocked('release_identity_mismatch')
    manifest = json.loads((runtime.parent / '.alchemy-v2-runtime.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or manifest.get('venv_python') != str(runtime / 'bin/python'):
        raise ArchiveBlocked('runtime_manifest_mismatch')
    if not (runtime / 'pyvenv.cfg').is_file():
        raise ArchiveBlocked('runtime_configuration_missing')
    return runtime


def systemd_references() -> list[str]:
    # Read installed templates and drop-ins as definitions. systemctl show
    # cannot instantiate bare @ templates returned by list-unit-files.
    references = []
    seen = set()
    pending = [Path(path) for path in shlex.split(command('systemctl', 'show', '--property=UnitPath', '--value'))]
    if not pending or any(not path.is_absolute() for path in pending):
        raise ArchiveBlocked('systemd_search_paths_unavailable')
    while pending:
        directory = pending.pop()
        if not directory.exists():
            continue
        resolved_directory = directory.resolve()
        if resolved_directory in seen:
            continue
        seen.add(resolved_directory)
        for path in directory.iterdir():
            if path.is_dir():
                pending.append(path)
                continue
            if path.suffix not in {'.service', '.conf'} or not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            references.append(path.read_text(encoding='utf-8'))
    if not references:
        raise ArchiveBlocked('systemd_definitions_unavailable')
    return references


def assert_unreferenced(releases: list[Path], expected_active: str) -> None:
    if not REVISION.fullmatch(expected_active):
        raise ArchiveBlocked('invalid_active_revision')
    if ACTIVE.resolve() != ROOT / ('doc276-277-' + expected_active[:12]):
        raise ArchiveBlocked('active_release_changed')
    protected = {ACTIVE.resolve()}
    for tag in ('alchemy-media-agent:latest', 'alchemy-media-agent:rollback-pr29'):
        command('docker', 'image', 'inspect', tag)
    image_ids = command('docker', 'image', 'ls', '-q', '--filter', 'reference=alchemy-media-agent:*').split()
    for image in json.loads(command('docker', 'image', 'inspect', *sorted(set(image_ids)))):
        revision = (image.get('Config', {}).get('Labels') or {}).get('org.opencontainers.image.revision', '')
        if not REVISION.fullmatch(revision):
            raise ArchiveBlocked('retained_image_revision_unavailable')
        protected.add(ROOT / ('doc276-277-' + revision[:12]))
    if protected.intersection(releases):
        raise ArchiveBlocked('retained_release')
    references = []
    containers = command('docker', 'ps', '-aq').split()
    if containers:
        for container in json.loads(command('docker', 'inspect', *containers)):
            references.extend(mount['Source'] for mount in container.get('Mounts', []))
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
                except FileNotFoundError:
                    pass
        except (FileNotFoundError, ProcessLookupError):
            continue
    for release in releases:
        if any(str(release) in reference for reference in references):
            raise ArchiveBlocked('release_still_referenced')


def inventory(runtime: Path) -> dict[str, tuple]:
    records = {}
    pending = [runtime]
    while pending:
        path = pending.pop()
        info = path.lstat()
        if path.name in {'.render_bridge_primary', '.media_storage', '.env'} or path.suffix in {'.sqlite', '.sqlite3', '.db'}:
            raise ArchiveBlocked('state_inside_runtime')
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
            raise ArchiveBlocked('unsupported_runtime_member')
        records[path.relative_to(runtime.parent).as_posix()] = (
            info.st_mode, info.st_size if stat.S_ISREG(info.st_mode) else 0,
            info.st_mtime_ns, info.st_uid, info.st_gid,
            os.readlink(path) if path.is_symlink() else '',
        )
        if stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
    return records


def verify_archive(archive: Path, runtime: Path, before: dict) -> None:
    seen = set()
    with tarfile.open(archive, 'r:gz') as saved:
        for member in saved:
            if member.name not in before or member.name in seen:
                raise ArchiveBlocked('archive_inventory_mismatch')
            seen.add(member.name)
            mode, size, mtime_ns, uid, gid, link = before[member.name]
            if (member.mode != stat.S_IMODE(mode) or member.uid != uid or member.gid != gid
                    or abs(member.mtime - mtime_ns / 1e9) > 0.000001):
                raise ArchiveBlocked('archive_metadata_mismatch')
            if stat.S_ISREG(mode):
                if not member.isfile() or member.size != size:
                    raise ArchiveBlocked('archive_size_mismatch')
                with saved.extractfile(member) as packed, (runtime.parent / member.name).open('rb') as source:
                    while True:
                        block = source.read(1024 * 1024)
                        if packed.read(1024 * 1024) != block:
                            raise ArchiveBlocked('archive_content_mismatch')
                        if not block:
                            break
            elif stat.S_ISDIR(mode) and not member.isdir():
                raise ArchiveBlocked('archive_directory_mismatch')
            elif stat.S_ISLNK(mode) and (not member.issym() or member.linkname != link):
                raise ArchiveBlocked('archive_link_mismatch')
    if seen != set(before) or inventory(runtime) != before:
        raise ArchiveBlocked('runtime_changed_during_archive')


def archive_runtime(runtime: Path, recheck) -> dict:
    before = inventory(runtime)
    archive = runtime.with_name('.venv.inactive.tar.gz')
    if archive.exists() or archive.is_symlink():
        raise ArchiveBlocked('archive_already_exists')
    with archive.open('xb') as stream:
        with tarfile.open(fileobj=stream, mode='w:gz', compresslevel=1, dereference=False) as saved:
            saved.add(runtime, arcname='.venv')
        stream.flush()
        os.fsync(stream.fileno())
    verify_archive(archive, runtime, before)
    recheck()
    if inventory(runtime) != before:
        raise ArchiveBlocked('runtime_changed_before_removal')
    # Exact validated .venv only. The verified sibling archive is never removed.
    shutil.rmtree(runtime)
    return {'runtime': str(runtime), 'archive': str(archive), 'members': len(before), 'archive_bytes': archive.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-active-sha', required=True)
    parser.add_argument('--revisions', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    revisions = args.revisions.split(',')
    try:
        if not 1 <= len(revisions) <= 5 or len(set(revisions)) != len(revisions):
            raise ArchiveBlocked('invalid_selection')
        runtimes = [validate_runtime(revision) for revision in revisions]
        releases = [runtime.parent.parent for runtime in runtimes]
        assert_unreferenced(releases, args.expected_active_sha)
        # Inspect every selection before the first archive or removal.
        plans = [{'runtime': str(runtime), 'members': len(inventory(runtime)), 'file_bytes': sum(row[1] for row in inventory(runtime).values())} for runtime in runtimes]
        print(json.dumps({'status': 'plan', 'runtimes': plans}), flush=True)
        if args.apply:
            for revision, runtime in zip(revisions, runtimes):
                if shutil.disk_usage(ROOT).free >= 3_000_000_000:
                    break
                def recheck():
                    validate_runtime(revision)
                    assert_unreferenced(releases, args.expected_active_sha)
                recheck()
                print(json.dumps({'status': 'archived', **archive_runtime(runtime, recheck)}), flush=True)
        print(json.dumps({'status': 'complete', 'applied': args.apply, 'free_bytes': shutil.disk_usage(ROOT).free}))
        return 0
    except (ArchiveBlocked, OSError, ValueError, tarfile.TarError) as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc) if isinstance(exc, ArchiveBlocked) else type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
