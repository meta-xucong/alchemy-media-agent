"""Doc97 view-aware, bounded reference retrieval."""

from __future__ import annotations

from ...creative_core.rules import stable_id
from .contracts import AdaptiveReferenceSelectionPlan, StrongReferenceBinding, SubjectContinuityAssetPackage


ADAPTIVE_REFERENCE_RETRIEVER_MODULE_ID = "adaptive_reference_retriever"


class AdaptiveReferenceRetriever:
    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        user_input: str,
        package: SubjectContinuityAssetPackage,
        max_identity_sources: int = 3,
    ) -> AdaptiveReferenceSelectionPlan:
        if not package.applies:
            return AdaptiveReferenceSelectionPlan(
                plan_id=stable_id(ADAPTIVE_REFERENCE_RETRIEVER_MODULE_ID, project_id, job_id),
                project_id=project_id,
                job_id=job_id,
                subject_type=package.subject_type,
            )
        target_view = infer_target_view(user_input)
        target_framing = infer_target_framing(user_input)
        eligible = [item for item in package.evidence if item.provider_eligible]
        selected = sorted(
            [item for item in eligible if item.authority == "user_selected_master"],
            key=lambda item: _reference_rank(item.view_hint, target_view, item.framing_hint, target_framing, item.trust_score),
        )
        roots = sorted(
            [item for item in eligible if item.authority == "uploaded_root_truth"],
            key=lambda item: _reference_rank(item.view_hint, target_view, item.framing_hint, target_framing, item.trust_score),
        )
        support = sorted(
            [
                item
                for item in eligible
                if item.authority not in {"user_selected_master", "uploaded_root_truth"}
            ],
            key=lambda item: _reference_rank(item.view_hint, target_view, item.framing_hint, target_framing, item.trust_score),
        )
        ordered: list[str] = []
        ordered.extend(item.source_id for item in selected)
        if roots:
            ordered.append(roots[0].source_id)
        ordered.extend(item.source_id for item in roots[1:])
        ordered.extend(item.source_id for item in support)
        ordered = _dedupe(ordered)[: max(1, min(int(max_identity_sources), 6))]
        if roots and not any(item.source_id in ordered for item in roots):
            ordered[-1:] = [roots[0].source_id]
        required = _dedupe(
            [
                *[item.source_id for item in selected if item.source_id in ordered],
                *[item.source_id for item in roots[:1] if item.source_id in ordered],
            ]
        )
        optional = [source_id for source_id in ordered if source_id not in required]
        all_ids = [item.source_id for item in package.evidence]
        excluded = _dedupe([*package.quarantined_ids, *[value for value in all_ids if value not in ordered]])
        return AdaptiveReferenceSelectionPlan(
            plan_id=stable_id(
                ADAPTIVE_REFERENCE_RETRIEVER_MODULE_ID,
                project_id,
                job_id,
                target_view,
                target_framing,
                ",".join(ordered),
            ),
            project_id=project_id,
            job_id=job_id,
            applies=bool(ordered),
            subject_type=package.subject_type,
            target_view=target_view,
            target_framing=target_framing,
            ordered_source_ids=ordered,
            required_source_ids=required,
            optional_source_ids=optional,
            excluded_source_ids=excluded,
            max_identity_sources=max(1, min(int(max_identity_sources), 6)),
            preserve_uploaded_root=bool(roots),
            user_visible_summary=["已自动选择更适合当前画面角度的参考图。"],
            metadata={
                "doc": "97",
                "explicit_user_selection_first": bool(selected),
                "uploaded_root_retained": bool(roots and any(item.source_id in ordered for item in roots)),
                "view_aware": True,
            },
        )

    def order_bindings(
        self,
        bindings: list[StrongReferenceBinding],
        plan: AdaptiveReferenceSelectionPlan,
    ) -> list[StrongReferenceBinding]:
        if not plan.applies:
            return list(bindings)
        order = {source_id: index for index, source_id in enumerate(plan.ordered_source_ids)}
        excluded = set(plan.excluded_source_ids)
        subject: list[StrongReferenceBinding] = []
        other: list[StrongReferenceBinding] = []
        for binding in bindings:
            if _is_subject_identity(binding):
                if binding.source_id not in excluded or binding.source_id in order:
                    subject.append(binding)
            else:
                other.append(binding)
        subject.sort(key=lambda item: (order.get(item.source_id, len(order) + 1), -float(item.confidence)))
        return [*subject, *other]


def infer_target_view(value: str) -> str:
    text = str(value or "").lower()
    if any(term in text for term in ("left profile", "left-side profile", "左侧脸", "左侧面", "左侧身")):
        return "left_profile"
    if any(term in text for term in ("right profile", "right-side profile", "右侧脸", "右侧面", "右侧身")):
        return "right_profile"
    if any(term in text for term in ("left three-quarter", "left 3/4", "左前方", "左侧前方", "左三分之四")):
        return "left_three_quarter"
    if any(term in text for term in ("right three-quarter", "right 3/4", "右前方", "右侧前方", "右三分之四")):
        return "right_three_quarter"
    if any(term in text for term in ("profile", "side view", "侧脸", "侧面")):
        return "profile"
    if any(term in text for term in ("front view", "front-facing", "正脸", "正面", "直视镜头")):
        return "front"
    return "unknown"


def infer_target_framing(value: str) -> str:
    text = str(value or "").lower()
    if any(term in text for term in ("face close-up", "extreme close-up", "脸部特写", "大特写")):
        return "face_closeup"
    if any(term in text for term in ("head and shoulders", "headshot", "半身特写", "肩部以上")):
        return "head_shoulders"
    if any(term in text for term in ("full body", "full-length", "全身", "全身照")):
        return "full_body"
    if any(term in text for term in ("half body", "waist-up", "半身", "腰部以上")):
        return "half_body"
    if any(term in text for term in ("wide shot", "environmental portrait", "远景", "环境人像")):
        return "environmental"
    return "unknown"


def _reference_rank(
    view_hint: str,
    target_view: str,
    framing_hint: str,
    target_framing: str,
    trust_score: float,
) -> tuple[int, int, float]:
    view_penalty = 0 if _view_matches(view_hint, target_view) else 1 if view_hint == "unknown" else 2
    framing_penalty = 0 if target_framing == "unknown" or framing_hint == target_framing else 1
    return (view_penalty, framing_penalty, -float(trust_score))


def _view_matches(view_hint: str, target_view: str) -> bool:
    if target_view == "unknown":
        return view_hint in {"front", "unknown"}
    if target_view == "profile":
        return view_hint in {"left_profile", "right_profile", "profile"}
    return view_hint == target_view


def _is_subject_identity(binding: StrongReferenceBinding) -> bool:
    value = f"{binding.role} {binding.use_policy}".lower()
    return any(term in value for term in ("identity", "person", "portrait", "character", "product"))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
