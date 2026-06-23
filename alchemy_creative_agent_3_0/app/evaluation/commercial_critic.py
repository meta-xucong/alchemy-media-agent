"""Commercial critic stubs for V3.0."""

from __future__ import annotations

from ..schemas import EvaluationReport


def has_hard_failure(report: EvaluationReport) -> bool:
    return any(problem.severity == "hard_failure" for problem in report.problems)

