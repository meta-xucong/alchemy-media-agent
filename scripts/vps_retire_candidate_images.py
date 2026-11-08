"""Retire explicitly selected unused images under the candidate release lock."""
from __future__ import annotations

import argparse
import json
import re
import subprocess


PREFIX = "alchemy-media-agent:candidate-"
PROTECTED_TAGS = ("alchemy-media-agent:latest", "alchemy-media-agent:rollback-pr29")


class RetirementBlocked(RuntimeError):
    pass


def _docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RetirementBlocked("docker_operation_failed")
    return result.stdout


def _images(*tags: str) -> list[dict]:
    images = json.loads(_docker("image", "inspect", *tags))
    if not isinstance(images, list) or len(images) != len(tags):
        raise RetirementBlocked("image_inventory_invalid")
    return images


def retire(expected_sha: str, revisions: list[str]) -> dict:
    if (
        not re.fullmatch(r"[0-9a-f]{40}", expected_sha)
        or not revisions
        or len(set(revisions)) != len(revisions)
        or expected_sha in revisions
        or any(not re.fullmatch(r"[0-9a-f]{40}", item) for item in revisions)
    ):
        raise RetirementBlocked("candidate_selection_invalid")

    protected_ids = [image["Id"] for image in _images(*PROTECTED_TAGS)]
    containers = _docker("ps", "-aq").split()
    used_ids = set(_docker("inspect", "--format", "{{.Image}}", *containers).split()) if containers else set()
    tags = [PREFIX + revision for revision in revisions]
    images = _images(*tags)
    # Check the whole selection before the first removal. Container inventory
    # includes stopped containers. Image IDs are Docker metadata, not file hashes.
    for tag, revision, image in zip(tags, revisions, images):
        if image["Id"] in used_ids or image["Id"] in protected_ids:
            raise RetirementBlocked("candidate_image_protected_or_used")
        if image.get("RepoTags") != [tag]:
            raise RetirementBlocked("candidate_image_has_other_tags")
        if image["Config"]["Labels"].get("org.opencontainers.image.revision") != revision:
            raise RetirementBlocked("candidate_revision_mismatch")

    for tag in tags:
        # No force, prune, container removal, source-release or data cleanup.
        _docker("image", "rm", tag)
    if [image["Id"] for image in _images(*PROTECTED_TAGS)] != protected_ids:
        raise RetirementBlocked("protected_image_identity_changed")
    return {"status": "retired", "retired_tags": tags, "protected_images_unchanged": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--retired-candidate-shas", required=True)
    args = parser.parse_args()
    try:
        result = retire(args.expected_sha, args.retired_candidate_shas.split(","))
    except (RetirementBlocked, ValueError, KeyError, TypeError, OSError) as exc:
        reason = str(exc) if isinstance(exc, RetirementBlocked) else "image_inventory_unreadable"
        print(json.dumps({"status": "blocked", "reason": reason}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
