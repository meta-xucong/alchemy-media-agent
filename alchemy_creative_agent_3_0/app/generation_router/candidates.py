"""Candidate helpers."""

from __future__ import annotations

from ..schemas import CandidateResult, EvaluationReport, Severity


def candidate_ids(candidates: list[CandidateResult]) -> list[str]:
    return [candidate.candidate_id for candidate in candidates]


def has_hard_failure(report: EvaluationReport) -> bool:
    return any(problem.severity == Severity.HARD_FAILURE for problem in report.problems)


def rank_evaluated_candidates(
    candidates: list[CandidateResult],
    evaluations: list[EvaluationReport],
) -> list[tuple[CandidateResult, EvaluationReport]]:
    """Rank candidates by V3.2 policy after removing hard failures."""

    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    pairs: list[tuple[CandidateResult, EvaluationReport]] = []
    for report in evaluations:
        if report.candidate_id is None or has_hard_failure(report):
            continue
        candidate = candidates_by_id.get(report.candidate_id)
        if candidate is not None:
            pairs.append((candidate, report))
    return sorted(
        pairs,
        key=lambda pair: (
            pair[1].overall_score,
            pair[1].commercial_score,
            pair[1].brand_consistency_score,
            pair[1].text_region_score,
        ),
        reverse=True,
    )


def select_best_candidate(
    candidates: list[CandidateResult],
    evaluations: list[EvaluationReport],
) -> tuple[CandidateResult | None, EvaluationReport | None]:
    ranked = rank_evaluated_candidates(candidates, evaluations)
    if ranked:
        return ranked[0]
    reports_by_candidate_id = {report.candidate_id: report for report in evaluations}
    scored_candidates = [
        (candidate, reports_by_candidate_id.get(candidate.candidate_id))
        for candidate in candidates
        if reports_by_candidate_id.get(candidate.candidate_id) is not None
    ]
    if not scored_candidates:
        return None, None
    return sorted(
        scored_candidates,
        key=lambda pair: pair[1].overall_score if pair[1] else -1,
        reverse=True,
    )[0]
