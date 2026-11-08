import importlib.util
import json
import os
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('archive_runtime', Path(__file__).parents[1] / 'scripts/vps_archive_inactive_runtime.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
SHA = 'a' * 40


def fixture_runtime(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    release = root / ('doc276-277-' + SHA[:12])
    runtime = release / 'custom_media_agent_2_0/.venv'
    runtime.mkdir(parents=True)
    (runtime / 'pyvenv.cfg').write_text('home = /usr/bin\n', encoding='utf-8')
    (runtime / 'package').mkdir()
    (runtime / 'package/payload').write_bytes(b'content\x00' * 50000)
    (runtime.parent / '.alchemy-v2-runtime.json').write_text(json.dumps({'schema_version': 1, 'venv_python': str(runtime / 'bin/python')}), encoding='utf-8')
    monkeypatch.setattr(guard, 'command', lambda *args: SHA)
    return root, runtime


def test_archive_roundtrip_preserves_every_file_and_leaves_source_checkout(tmp_path, monkeypatch):
    root, runtime = fixture_runtime(tmp_path, monkeypatch)
    checkout_file = runtime.parent / 'source.py'
    checkout_file.write_text('keep source', encoding='utf-8')
    assert guard.validate_runtime(SHA, root) == runtime
    before = guard.inventory(runtime)
    expected = (runtime / 'package/payload').read_bytes()
    checks = []
    result = guard.archive_runtime(runtime, lambda: checks.append(True))
    assert checks == [True] and not runtime.exists()
    assert checkout_file.read_text(encoding='utf-8') == 'keep source'
    assert (runtime.parent / '.alchemy-v2-runtime.json').is_file()
    with tarfile.open(result['archive'], 'r:gz') as archive:
        archive.extractall(runtime.parent, filter='data')
    assert (runtime / 'package/payload').read_bytes() == expected
    assert set(guard.inventory(runtime)) == set(before)


def test_invalid_identity_or_manifest_never_archives(tmp_path, monkeypatch):
    root, runtime = fixture_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(guard, 'command', lambda *args: 'b' * 40)
    with pytest.raises(guard.ArchiveBlocked, match='identity'):
        guard.validate_runtime(SHA, root)
    monkeypatch.setattr(guard, 'command', lambda *args: SHA)
    (runtime.parent / '.alchemy-v2-runtime.json').write_text('{}', encoding='utf-8')
    with pytest.raises(guard.ArchiveBlocked, match='manifest'):
        guard.validate_runtime(SHA, root)
    assert runtime.exists()


def test_state_inside_runtime_stops_before_archive(tmp_path, monkeypatch):
    _, runtime = fixture_runtime(tmp_path, monkeypatch)
    (runtime / '.render_bridge_primary').mkdir()
    with pytest.raises(guard.ArchiveBlocked, match='state_inside'):
        guard.archive_runtime(runtime, lambda: None)
    assert runtime.exists() and not runtime.with_name('.venv.inactive.tar.gz').exists()


def test_changed_same_size_bytes_are_detected_without_hashes(tmp_path, monkeypatch):
    _, runtime = fixture_runtime(tmp_path, monkeypatch)
    before = guard.inventory(runtime)
    archive = runtime.with_name('bad.tar.gz')
    with tarfile.open(archive, 'w:gz', dereference=False) as saved:
        saved.add(runtime, arcname='.venv')
    target = runtime / 'package/payload'
    info = target.stat()
    target.write_bytes(b'x' * info.st_size)
    os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))
    with pytest.raises(guard.ArchiveBlocked, match='content'):
        guard.verify_archive(archive, runtime, before)
    assert runtime.exists()


def test_new_reference_after_archive_keeps_both_copies(tmp_path, monkeypatch):
    _, runtime = fixture_runtime(tmp_path, monkeypatch)
    def reject():
        raise guard.ArchiveBlocked('release_still_referenced')
    with pytest.raises(guard.ArchiveBlocked, match='referenced'):
        guard.archive_runtime(runtime, reject)
    assert runtime.exists() and runtime.with_name('.venv.inactive.tar.gz').is_file()


def test_symlink_members_preserved_but_linked_runtime_rejected(tmp_path, monkeypatch):
    root, runtime = fixture_runtime(tmp_path, monkeypatch)
    try:
        (runtime / 'library-link').symlink_to('package', target_is_directory=True)
    except OSError:
        pytest.skip('Host cannot create symlinks')
    before = guard.inventory(runtime)
    archive = runtime.with_name('links.tar.gz')
    with tarfile.open(archive, 'w:gz', dereference=False) as saved:
        saved.add(runtime, arcname='.venv')
    guard.verify_archive(archive, runtime, before)
    relocated = runtime.with_name('elsewhere')
    runtime.rename(relocated)
    runtime.symlink_to(relocated, target_is_directory=True)
    with pytest.raises(guard.ArchiveBlocked, match='linked'):
        guard.validate_runtime(SHA, root)


def test_live_process_reference_blocks_archiving(tmp_path, monkeypatch):
    root, runtime = fixture_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(guard, 'ROOT', root)
    monkeypatch.setattr(guard, 'ACTIVE', root / ('doc276-277-' + 'b' * 12))
    monkeypatch.setattr(guard, 'systemd_references', lambda: [])
    process = tmp_path / '12345'
    process.mkdir()
    (process / 'cmdline').write_bytes(str(runtime / 'bin/python').encode())
    (process / 'fd').mkdir()
    original = Path.iterdir
    monkeypatch.setattr(Path, 'iterdir', lambda path: iter([process]) if path == Path('/proc') else original(path))
    monkeypatch.setattr(os, 'readlink', lambda path: '/usr/bin/python3')
    def run(*args):
        if args[:3] == ('docker', 'image', 'inspect'):
            return json.dumps([{'Config': {'Labels': {'org.opencontainers.image.revision': 'b' * 40}}}])
        if args[:4] == ('docker', 'image', 'ls', '-q'):
            return 'image'
        return ''
    monkeypatch.setattr(guard, 'command', run)
    with pytest.raises(guard.ArchiveBlocked, match='referenced'):
        guard.assert_unreferenced([runtime.parent.parent], 'b' * 40)
    assert runtime.exists()


@pytest.mark.parametrize('kind', ['active', 'rollback', 'candidate', 'container', 'systemd'])
def test_referenced_releases_are_protected(tmp_path, monkeypatch, kind):
    root, runtime = fixture_runtime(tmp_path, monkeypatch)
    release = runtime.parent.parent
    active_sha = SHA if kind == 'active' else 'b' * 40
    active = root / ('doc276-277-' + active_sha[:12])
    monkeypatch.setattr(guard, 'ROOT', root)
    monkeypatch.setattr(guard, 'ACTIVE', active)
    monkeypatch.setattr(guard, 'systemd_references', lambda: [str(release)] if kind == 'systemd' else [])
    def run(*args):
        if args[:4] == ('docker', 'image', 'ls', '-q'):
            return 'image'
        if args[:3] == ('docker', 'image', 'inspect'):
            revision = SHA if kind in {'rollback', 'candidate'} else active_sha
            return json.dumps([{'Config': {'Labels': {'org.opencontainers.image.revision': revision}}}])
        if args == ('docker', 'ps', '-aq'):
            return 'container'
        if args[:2] == ('docker', 'inspect'):
            return json.dumps([{'Mounts': [{'Source': str(release / '.env')}] if kind == 'container' else []}])
        raise AssertionError(args)
    monkeypatch.setattr(guard, 'command', run)
        # Mock the Linux process inventory when exercising other reference owners.
    if kind in {'container', 'systemd'}:
        original = Path.iterdir
        monkeypatch.setattr(Path, 'iterdir', lambda path: iter(()) if path == Path('/proc') else original(path))
    with pytest.raises(guard.ArchiveBlocked, match='retained_release|referenced'):
        guard.assert_unreferenced([release], active_sha)
    assert runtime.exists()


def test_systemd_templates_and_dropins_are_read_without_instantiation(tmp_path, monkeypatch):
    (tmp_path / 'example@.service').write_text('[Service]\nExecStart=/opt/old/.venv/bin/python\n', encoding='utf-8')
    dropins = tmp_path / 'example@.service.d'
    dropins.mkdir()
    (dropins / 'custom.conf').write_text('[Service]\nWorkingDirectory=/opt/another\n', encoding='utf-8')
    monkeypatch.setattr(guard, 'command', lambda *args: json.dumps(tmp_path.as_posix()))
    references = guard.systemd_references()
    assert len(references) == 2
    assert any('/opt/old/' in item for item in references)
    assert any('/opt/another' in item for item in references)
