"""Doc97 subject-continuity asset packaging."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    IdentityDriftGuardPlan,
    StrongReferenceBinding,
    SubjectContinuityAssetPackage,
    SubjectContinuityEvidence,
)
from .identity_metric import create_default_identity_metric_provider


SUBJECT_CONTINUITY_ASSET_PACK_MODULE_ID = "subject_continuity_asset_pack"


class SubjectContinuityAssetPackBuilder:
    """Build an auditable reference pack without persisting face embeddings."""

    def __init__(self, *, reference_profiler: Any | None = None) -> None:
        self.reference_profiler = reference_profiler or create_default_identity_metric_provider()

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        strong_bindings: list[StrongReferenceBinding],
        drift_guard: IdentityDriftGuardPlan,
    ) -> SubjectContinuityAssetPackage:
        relevant = [binding for binding in strong_bindings if _is_subject_identity(binding)]
        if subject_type not in {"character", "product"} or not relevant:
            return SubjectContinuityAssetPackage(
                package_id=stable_id(SUBJECT_CONTINUITY_ASSET_PACK_MODULE_ID, project_id, job_id, subject_type),
                project_id=project_id,
                job_id=job_id,
                subject_type=subject_type,
            )

        decision_map = {
            str(item.get("source_id") or ""): item
            for item in drift_guard.decisions
            if isinstance(item, dict) and item.get("source_id")
        }
        evidence: list[SubjectContinuityEvidence] = []
        for binding in relevant:
            decision = decision_map.get(binding.source_id, {})
            user_selected = bool(decision.get("user_selected") or binding.source_type == "selected_output")
            root_truth = bool(decision.get("root_truth"))
            quarantined = binding.source_id in drift_guard.quarantined_generated_ids
            profile = self._profile(binding) if subject_type == "character" else {}
            authority = (
                "user_selected_master"
                if user_selected
                else "uploaded_root_truth"
                if root_truth
                else "reviewed_generated_support"
                if decision.get("identity_score") is not None
                else "unreviewed_generated_support"
            )
            trust = (
                0.98
                if user_selected
                else 0.95
                if root_truth
                else 0.88
                if (decision.get("identity_score") or 0.0) >= drift_guard.commercial_identity_target
                else 0.74
            )
            evidence.append(
                SubjectContinuityEvidence(
                    evidence_id=stable_id(
                        "subject_continuity_evidence",
                        project_id,
                        binding.source_id,
                        authority,
                    ),
                    source_id=binding.source_id,
                    source_type=binding.source_type,
                    asset_id=binding.asset_id,
                    output_id=binding.output_id,
                    file_path=binding.file_path,
                    subject_type=subject_type,
                    evidence_role=binding.role,
                    authority=authority,
                    view_hint=str(profile.get("view_hint") or binding.metadata.get("view_hint") or "unknown"),
                    framing_hint=str(profile.get("framing_hint") or binding.metadata.get("framing_hint") or "unknown"),
                    face_detection_confidence=_score(profile.get("face_detection_confidence")),
                    identity_score=_score(decision.get("identity_score")),
                    geometry_score=_score(decision.get("geometry_score")),
                    trust_score=trust,
                    provider_eligible=bool(binding.file_path and (not quarantined or user_selected)),
                    quarantine_reason=str(decision.get("reason") or "") if quarantined else None,
                    user_selected=user_selected,
                    metadata={
                        "doc": "97",
                        "binding_id": binding.binding_id,
                        "strength": binding.strength,
                        "use_policy": binding.use_policy,
                        "embedding_persisted": False,
                        "profile_status": profile.get("status"),
                    },
                )
            )

        selected_ids = [item.source_id for item in evidence if item.authority == "user_selected_master"]
        root_ids = [item.source_id for item in evidence if item.authority == "uploaded_root_truth"]
        support_ids = [
            item.source_id
            for item in evidence
            if item.authority in {"reviewed_generated_support", "unreviewed_generated_support"}
            and item.provider_eligible
        ]
        quarantined_ids = [item.source_id for item in evidence if item.quarantine_reason]
        provider_ids = [item.source_id for item in evidence if item.provider_eligible]
        return SubjectContinuityAssetPackage(
            package_id=stable_id(
                SUBJECT_CONTINUITY_ASSET_PACK_MODULE_ID,
                project_id,
                job_id,
                subject_type,
                ",".join(item.source_id for item in evidence),
            ),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            subject_type=subject_type,
            evidence=evidence,
            user_selected_master_ids=_dedupe(selected_ids),
            uploaded_root_truth_ids=_dedupe(root_ids),
            accepted_generated_support_ids=_dedupe(support_ids),
            quarantined_ids=_dedupe(quarantined_ids),
            provider_candidate_ids=_dedupe(provider_ids),
            root_truth_preserved=bool(root_ids),
            embeddings_persisted=False,
            user_visible_summary=[
                "已整理本项目的人物或产品参考。",
                "你选中的图片优先，原始参考会继续帮助防止跑偏。",
            ],
            metadata={
                "doc": "97",
                "evidence_count": len(evidence),
                "provider_candidate_count": len(provider_ids),
                "ephemeral_reference_profile": True,
                "embedding_persisted": False,
            },
        )

    def _profile(self, binding: StrongReferenceBinding) -> dict[str, Any]:
        if not binding.file_path:
            return {}
        profile = getattr(self.reference_profiler, "profile_reference", None)
        if not callable(profile):
            return {}
        try:
            result = profile(binding.file_path)
        except Exception:
            return {}
        return dict(result) if isinstance(result, dict) else {}


def _is_subject_identity(binding: StrongReferenceBinding) -> bool:
    value = f"{binding.role} {binding.use_policy}".lower()
    return any(term in value for term in ("identity", "person", "portrait", "character", "product"))


def _score(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
