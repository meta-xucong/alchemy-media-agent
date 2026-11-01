from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_loopback_compose_rebuilds_from_current_alchemy_source() -> None:
    base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    loopback = (ROOT / ".runtime" / "render-bridge-local" / "docker-compose.loopback.yml").read_text(encoding="utf-8")
    revision_overlay = (ROOT / "docker-compose.local-source-build.yml").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts" / "start_local_alchemy.ps1").read_text(encoding="utf-8")
    batch_entrypoint = (ROOT / "start_local_alchemy.bat").read_text(encoding="utf-8")

    assert "dockerfile: ./src_skeleton/Dockerfile" in base
    dockerfile = (ROOT / "src_skeleton" / "Dockerfile").read_text(encoding="utf-8")
    assert "build: !reset null" not in loopback
    assert "pull_policy: build" in loopback
    assert 'ALCHEMY_REVISION: "${ALCHEMY_REVISION:?Use start_local_alchemy.bat to supply the Git revision}"' in loopback
    assert "dockerfile: ./src_skeleton/Dockerfile" in revision_overlay
    assert "ALCHEMY_REVISION" in revision_overlay
    assert "DEBIAN_MIRROR_HOST: mirrors.tuna.tsinghua.edu.cn" in revision_overlay
    assert "ARG DEBIAN_MIRROR_HOST=deb.debian.org" in dockerfile
    assert 'https://${DEBIAN_MIRROR_HOST}' in dockerfile
    assert "ARG PIP_INDEX_URL=https://pypi.org/simple" in dockerfile
    assert 'pip install --index-url "$PIP_INDEX_URL" --upgrade pip' in dockerfile
    assert 'pip install --index-url "$PIP_INDEX_URL" -r requirements.txt' in dockerfile
    assert "PIP_INDEX_URL: https://pypi.tuna.tsinghua.edu.cn/simple" in revision_overlay
    assert "rev-parse --verify HEAD" in launcher
    assert "status', '--porcelain', '--untracked-files=all'" in launcher
    assert "ALCHEMY_REVISION" in launcher
    assert "Get-Command docker.exe -CommandType Application" in launcher
    assert "image inspect alchemy-media-agent:bridge-local" in launcher
    assert "--no-build --no-deps alchemy-media-agent" in launcher
    assert "scripts\\start_local_alchemy.ps1" in batch_entrypoint
