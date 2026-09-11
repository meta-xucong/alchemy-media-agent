"""Provider-free release staging hygiene gate.

The gate deliberately inspects only the index candidate list.  It must not
clean, stage, or classify unrelated working-tree changes.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import PurePosixPath


FORBIDDEN_STAGED_PREFIXES = (
    ".codex-",
    ".controlled-validation/",
    ".pytest-main-",
)
FORBIDDEN_STAGED_EXACT = {
    "src_skeleton/uv.lock",
    "codex-vps-current-project-audit.ps1",
    "alchemy_creative_agent_3_0/docs/293_V3_UNIFIED_PROMPT_COMPRESSION_AND_BRAIN_FINALIZATION_SPEC.main-untracked-before-integration.md",
}


def _staged_paths() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z"],
        check=True,
        capture_output=True,
    )
    return tuple(path for path in result.stdout.decode().split("\0") if path)


def _is_release_hygiene_violation(path: str) -> bool:
    normalized = PurePosixPath(path).as_posix()
    return normalized.startswith(FORBIDDEN_STAGED_PREFIXES) or normalized in FORBIDDEN_STAGED_EXACT


class ReleaseStagingHygieneTests(unittest.TestCase):
    def test_staged_candidate_list_excludes_validation_scratch(self) -> None:
        violations = tuple(path for path in _staged_paths() if _is_release_hygiene_violation(path))
        self.assertFalse(violations, f"temporary/validation artifacts are staged: {violations}")

    def test_root_scoping_does_not_hide_nested_codex_sources(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "plugins/example/.codex/skills/README.md"],
            check=False,
        )
        self.assertEqual(result.returncode, 1, "nested .codex skill/source paths must remain visible")


if __name__ == "__main__":
    unittest.main()
