from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location(
    'retire_runtime_archives', Path(__file__).parents[1] / 'scripts/vps_retire_inactive_runtime_archives.py'
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

ACTIVE_SHA = 'a' * 40
OLD_SHA = 'b' * 40


def fixture_release(tmp_path: Path, monkeypatch, revision: str = OLD_SHA):
    root = tmp_path.resolve()
    active = root / f'doc276-277-{ACTIVE_SHA[:12]}'
    active.mkdir()
    release = root / f'doc276-277-{revision[:12]}'
    v2 = release / 'custom_media_agent_2_0'
    v2.mkdir(parents=True)
    (release / 'src_skeleton').mkdir()
    (release / 'src_skeleton/.env').write_text('SECRET=not-read\n', encoding='utf-8')
    archive = v2 / '.venv.inactive.tar.gz'
    with tarfile.open(archive, 'w:gz') as saved:
        import io
        payload = b'home = /usr/bin\n'
        info = tarfile.TarInfo('.venv/pyvenv.cfg')
        info.size = len(payload)
        saved.addfile(info, io.BytesIO(payload))

    def run(*args):
        if args[:1] == ('curl',):
            return ''
        if args[:3] == ('git', '-C', str(release)) and args[3:5] == ('rev-parse', 'HEAD'):
            return revision
        if args[:3] == ('git', '-C', str(release)) and args[3:6] == ('diff', '--quiet', 'HEAD'):
            return ''
        if args[:3] == ('git', '-C', str(release)) and args[3:4] == ('ls-files',):
            return ''
        if args[:3] == ('docker', 'image', 'inspect'):
            return '{}'
        if args[:5] == ('docker', 'image', 'ls', '-q', '--filter'):
            return ''
        if args[:3] == ('docker', 'ps', '-aq'):
            return ''
        raise AssertionError(args)

    monkeypatch.setattr(guard, 'command', run)
    monkeypatch.setattr(guard, 'ROOT', root)
    monkeypatch.setattr(guard, 'ACTIVE', active)
    monkeypatch.setattr(guard, 'systemd_references', lambda: ['[Service]\nWorkingDirectory=/opt/alchemy\n'])
    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, 'iterdir', lambda path: iter(()) if path == Path('/proc') else original_iterdir(path))
    return root, active, release, archive


def test_inventory_selects_only_inactive_archived_runtime_and_preserves_source_env(tmp_path, monkeypatch):
    root, active, release, archive = fixture_release(tmp_path, monkeypatch)
    plan = guard.inventory_archives(ACTIVE_SHA, root=root, active=active)
    assert len(plan) == 1
    assert plan[0]['revision'] == OLD_SHA
    assert plan[0]['archive'] == str(archive)
    assert plan[0]['bytes'] == archive.stat().st_size
    assert (release / 'src_skeleton/.env').is_file()
    token = guard.selection_token(plan[0])
    assert guard.verify_inspected_inventory(token, plan) == [OLD_SHA]
    changed = [dict(plan[0], inode=plan[0]['inode'] + 1)]
    with pytest.raises(guard.RetirementBlocked, match='inventory_changed_since_inspection'):
        guard.verify_inspected_inventory(token, changed)


def test_live_runtime_or_invalid_archive_blocks_retirement(tmp_path, monkeypatch):
    root, active, release, archive = fixture_release(tmp_path, monkeypatch)
    (release / 'custom_media_agent_2_0/.venv').mkdir()
    with pytest.raises(guard.RetirementBlocked, match='live_runtime_present'):
        guard.inventory_archives(ACTIVE_SHA, root=root, active=active)

    (release / 'custom_media_agent_2_0/.venv').rmdir()
    with tarfile.open(archive, 'w:gz') as saved:
        import io
        data = b'x'
        info = tarfile.TarInfo('../outside')
        info.size = len(data)
        saved.addfile(info, io.BytesIO(data))
    with pytest.raises(guard.RetirementBlocked, match='runtime_archive_contains_state'):
        guard.inventory_archives(ACTIVE_SHA, root=root, active=active)


def test_retirement_requires_unreferenced_checks_and_preserves_ledger_receipt(tmp_path, monkeypatch):
    root, active, release, archive = fixture_release(tmp_path, monkeypatch)
    ledger = tmp_path / 'ledger.jsonl'
    checked = []
    result = guard.retire_archives([OLD_SHA], ACTIVE_SHA, root=root, active=active, ledger=ledger,
                                   recheck=lambda: checked.append(True))
    assert result == {'retired': [{'revision': OLD_SHA, 'bytes': result['retired'][0]['bytes']}],
                      'retired_count': 1, 'freed_archive_bytes': result['retired'][0]['bytes']}
    assert checked == [True]
    assert not archive.exists()
    assert release.is_dir() and (release / 'src_skeleton/.env').is_file()
    records = [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()]
    assert [row['state'] for row in records] == ['intent', 'removed']
    assert all(row['revision'] == OLD_SHA and 'sha256' not in row for row in records)


def test_reference_check_blocks_all_mutation(tmp_path, monkeypatch):
    root, active, release, archive = fixture_release(tmp_path, monkeypatch)
    def reject(*args, **kwargs):
        raise guard.RetirementBlocked('release_still_referenced')
    monkeypatch.setattr(guard, 'assert_unreferenced', reject)
    with pytest.raises(guard.RetirementBlocked, match='referenced'):
        guard.inventory_archives(ACTIVE_SHA, root=root, active=active)
    assert archive.is_file()


def test_untracked_sibling_content_is_preserved_during_archive_cleanup(tmp_path, monkeypatch):
    root, active, release, archive = fixture_release(tmp_path, monkeypatch)
    unexpected = release / 'unexpected.log'
    unexpected.write_text('preserve', encoding='utf-8')
    original = guard.command
    def run(*args):
        if args[:3] == ('git', '-C', str(release)) and args[3:4] == ('ls-files',):
            return 'unexpected.log\0'
        return original(*args)
    monkeypatch.setattr(guard, 'command', run)
    result = guard.retire_archives([OLD_SHA], ACTIVE_SHA, root=root, active=active,
                                   ledger=tmp_path / 'ledger.jsonl')
    assert result['retired_count'] == 1
    assert not archive.exists()
    assert unexpected.read_text(encoding='utf-8') == 'preserve'
    assert (release / 'src_skeleton/.env').read_text(encoding='utf-8') == 'SECRET=not-read\n'


def test_workflow_streams_the_exact_guard_script_and_requires_inspection_identity():
    workflow = (Path(__file__).parents[1] / '.github/workflows/guarded-vps-retire-inactive-runtime-archives.yml').read_text(encoding='utf-8')
    assert '< scripts/vps_retire_inactive_runtime_archives.py' in workflow
    assert "python3 - $remote_args" in workflow
    assert 'inputs.selection' in workflow
    assert 'inventory_changed_since_inspection' in (Path(__file__).parents[1] / 'scripts/vps_retire_inactive_runtime_archives.py').read_text(encoding='utf-8')
    assert 'python3 - < scripts/vps_retire_inactive_runtime_archives.py' not in workflow
