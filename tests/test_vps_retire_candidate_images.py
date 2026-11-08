from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


_PATH = Path(__file__).parents[1] / "scripts" / "vps_retire_candidate_images.py"
_SPEC = importlib.util.spec_from_file_location("vps_retire_candidate_images", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)

TARGET = "a" * 40
OLD = "b" * 40
OTHER = "c" * 40
PREFIX = "alchemy-media-agent:candidate-"


class Docker:
    def __init__(self):
        self.calls = []
        self.images = {
            "alchemy-media-agent:latest": self.image("live", "d" * 40),
            "alchemy-media-agent:rollback-pr29": self.image("rollback", "e" * 40),
            PREFIX + OLD: self.image("old", OLD),
            PREFIX + OTHER: self.image("other", OTHER),
        }
        self.used = ["live", "bridge"]

    @staticmethod
    def image(identity, revision):
        return {
            "Id": identity,
            "RepoTags": [PREFIX + revision],
            "Config": {"Labels": {"org.opencontainers.image.revision": revision}},
        }

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("image", "inspect"):
            return json.dumps([self.images[tag] for tag in args[2:]])
        if args == ("ps", "-aq"):
            return "container1\ncontainer2\n"
        if args[:3] == ("inspect", "--format", "{{.Image}}"):
            return "\n".join(self.used)
        if args[:2] == ("image", "rm"):
            del self.images[args[2]]
            return "removed"
        raise AssertionError(args)

    @property
    def removals(self):
        return [call for call in self.calls if call[:2] == ("image", "rm")]


def test_exact_unused_candidates_removed_without_force(monkeypatch):
    docker = Docker()
    monkeypatch.setattr(guard, "_docker", docker)
    result = guard.retire(TARGET, [OLD, OTHER])
    assert result["retired_tags"] == [PREFIX + OLD, PREFIX + OTHER]
    assert docker.removals == [("image", "rm", PREFIX + OLD), ("image", "rm", PREFIX + OTHER)]
    assert "alchemy-media-agent:latest" in docker.images
    assert "alchemy-media-agent:rollback-pr29" in docker.images
    first_remove = docker.calls.index(docker.removals[0])
    assert ("image", "inspect", PREFIX + OLD, PREFIX + OTHER) in docker.calls[:first_remove]


@pytest.mark.parametrize("revisions", [[TARGET], [OLD, OLD], ["latest"], ["b" * 39], []])
def test_invalid_selection_never_calls_docker(monkeypatch, revisions):
    docker = Docker()
    monkeypatch.setattr(guard, "_docker", docker)
    with pytest.raises(guard.RetirementBlocked):
        guard.retire(TARGET, revisions)
    assert docker.calls == []


@pytest.mark.parametrize("failure", ["container", "latest", "rollback", "revision", "alias"])
def test_entire_selection_checked_before_any_removal(monkeypatch, failure):
    docker = Docker()
    # First image is eligible, second is not. Neither may be removed.
    image = docker.images[PREFIX + OTHER]
    if failure == "container":
        docker.used.append("other")
    elif failure in {"latest", "rollback"}:
        image["Id"] = "live" if failure == "latest" else "rollback"
    elif failure == "revision":
        image["Config"]["Labels"]["org.opencontainers.image.revision"] = OLD
    else:
        image["RepoTags"].append("another-service:retained")
    monkeypatch.setattr(guard, "_docker", docker)
    with pytest.raises(guard.RetirementBlocked):
        guard.retire(TARGET, [OLD, OTHER])
    assert docker.removals == []
