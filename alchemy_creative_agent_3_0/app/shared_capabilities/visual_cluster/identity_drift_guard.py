"""Doc97 generated-reference drift control inside the Visual Capability Cluster."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import IdentityDriftGuardPlan, StrongReferenceBinding


IDENTITY_DRIFT_GUARD_MODULE_ID = "identity_drift_guard"


class IdentityDriftGuard:
    """Classify generated references without overriding explicit user selection."""

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        strong_bindings: list[StrongReferenceBinding],
        selected_outputs: list[dict[str, Any]],
        minimum_identity_score: float = 0.72,
        commercial_identity_target: float = 0.82,
    ) -> IdentityDriftGuardPlan:
        relevant = [binding for binding in strong_bindings if _is_subject_identity(binding)]
        if not relevant or subject_type not in {"character", "product"}:
            return IdentityDriftGuardPlan(
                plan_id=stable_id(IDENTITY_DRIFT_GUARD_MODULE_ID, project_id, job_id, subject_type),
                project_id=project_id,
                job_id=job_id,
                subject_type=subject_type,
            )

        selected_by_id: dict[str, dict[str, Any]] = {}
        for item in selected_outputs:
            for value in (item.get("output_id"), item.get("asset_id"), item.get("candidate_id")):
                if value:
                    selected_by_id[str(value)] = item

        roots: list[str] = []
        accepted: list[str] = []
        warnings: list[str] = []
        quarantined: list[str] = []
        overrides: list[str] = []
        decisions: list[dict[str, Any]] = []
        for binding in relevant:
            source_id = binding.source_id
            user_selected = binding.source_type == "selected_output" or source_id in selected_by_id
            root_truth = not _is_generated_binding(binding)
            score_payload = {
                **dict(binding.metadata or {}),
                **dict(selected_by_id.get(source_id, {}).get("metadata") or {}),
            }
            identity_score = _find_score(
                score_payload,
                ("fused_identity_score", "identity_consistency", "same_person_readability", "objective_identity_metric"),
            )
            geometry_score = _find_score(
                score_payload,
                ("identity_metric_geometry", "geometry_score", "geometry_relationship_score"),
            )
            decision = "accepted_root_truth" if root_truth else "accepted_generated_support"
            reason = "uploaded_or_external_truth"
            if root_truth:
                roots.append(source_id)
            elif user_selected:
                accepted.append(source_id)
                if identity_score is not None and identity_score < minimum_identity_score:
                    overrides.append(source_id)
                    decision = "accepted_user_override"
                    reason = "explicit_user_selection_overrides_automatic_quarantine"
                elif identity_score is None:
                    warnings.append(source_id)
                    decision = "accepted_unreviewed_user_selection"
                    reason = "explicit_user_selection_without_review_score"
                elif identity_score < commercial_identity_target:
                    warnings.append(source_id)
                    decision = "accepted_warning_user_selection"
                    reason = "explicit_user_selection_in_warning_band"
                else:
                    reason = "explicit_user_selection_passed_commercial_identity_target"
            elif identity_score is None:
                quarantined.append(source_id)
                decision = "quarantined_unreviewed_generated_support"
                reason = "generated_support_missing_root_comparison_score"
            elif identity_score < minimum_identity_score:
                quarantined.append(source_id)
                decision = "quarantined_identity_drift"
                reason = "generated_support_below_minimum_identity_score"
            elif identity_score < commercial_identity_target:
                warnings.append(source_id)
                accepted.append(source_id)
                decision = "accepted_auxiliary_warning_support"
                reason = "generated_support_in_warning_band"
            else:
                accepted.append(source_id)
                reason = "generated_support_passed_commercial_identity_target"
            decisions.append(
                {
                    "source_id": source_id,
                    "asset_id": binding.asset_id,
                    "output_id": binding.output_id,
                    "decision": decision,
                    "reason": reason,
                    "user_selected": user_selected,
                    "root_truth": root_truth,
                    "identity_score": identity_score,
                    "geometry_score": geometry_score,
                }
            )

        status = "warning" if quarantined or warnings or overrides else "pass"
        return IdentityDriftGuardPlan(
            plan_id=stable_id(
                IDENTITY_DRIFT_GUARD_MODULE_ID,
                project_id,
                job_id,
                subject_type,
                ",".join(binding.source_id for binding in relevant),
            ),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            subject_type=subject_type,
            status=status,
            root_truth_ids=_dedupe(roots),
            accepted_generated_ids=_dedupe(accepted),
            warning_generated_ids=_dedupe(warnings),
            quarantined_generated_ids=_dedupe(quarantined),
            user_override_ids=_dedupe(overrides),
            minimum_identity_score=minimum_identity_score,
            commercial_identity_target=commercial_identity_target,
            root_comparison_required=bool(roots),
            decisions=decisions,
            user_visible_summary=[
                "已保留你选中的参考方向。",
                "系统会同时用原始参考防止人物或产品越做越偏。",
            ],
            metadata={
                "doc": "97",
                "generated_reference_count": sum(1 for item in relevant if _is_generated_binding(item)),
                "root_truth_count": len(roots),
                "explicit_user_selection_wins": True,
            },
        )


def _is_subject_identity(binding: StrongReferenceBinding) -> bool:
    value = f"{binding.role} {binding.use_policy}".lower()
    return any(term in value for term in ("identity", "person", "portrait", "character", "product"))


def _is_generated_binding(binding: StrongReferenceBinding) -> bool:
    value = str(binding.source_type or "").lower()
    return value == "selected_output" or "generated" in value or bool(binding.output_id)


def _find_score(value: Any, keys: tuple[str, ...]) -> float | None:
    key_set = {key.lower() for key in keys}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in key_set:
                score = _score(child)
                if score is not None:
                    return score
        for child in value.values():
            score = _find_score(child, keys)
            if score is not None:
                return score
    elif isinstance(value, list):
        for child in value:
            score = _find_score(child, keys)
            if score is not None:
                return score
    return None


def _score(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
