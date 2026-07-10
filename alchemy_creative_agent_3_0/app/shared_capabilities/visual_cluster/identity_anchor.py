"""Doc58 project identity anchor builder."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import ProjectIdentityAnchor, ResolvedReferencePolicyPackage, StrongReferenceBinding, VisualIdentityLockProfile


class ProjectIdentityAnchorBuilder:
    """Create project-scoped anchors from selected outputs and strong bindings."""

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        selected_outputs: list[dict[str, Any]],
        strong_bindings: list[StrongReferenceBinding],
        identity_locks: list[VisualIdentityLockProfile],
        template_policy: dict[str, Any],
        reference_policy_package: ResolvedReferencePolicyPackage | None = None,
    ) -> list[ProjectIdentityAnchor]:
        if not selected_outputs and not strong_bindings:
            return []
        subject_type = _subject_type(template_policy, identity_locks)
        output_ids = _dedupe(_identity(item, "output_id", "asset_id", "candidate_id") for item in selected_outputs)
        asset_ids = _dedupe(_identity(item, "asset_id", "output_id", "candidate_id") for item in selected_outputs)
        candidate_ids = _dedupe(_identity(item, "candidate_id", "output_id", "asset_id") for item in selected_outputs)
        binding_ids = _dedupe(binding.binding_id for binding in strong_bindings)
        hard_binding = any(binding.strength == "hard" for binding in strong_bindings)
        provider_required = any(binding.provider_input_required for binding in strong_bindings)
        prompt_only = bool(strong_bindings) and not provider_required
        keep_rules, allowed_variations, forbidden_drift = _rules_for_subject(
            subject_type,
            reference_policy_package=reference_policy_package,
        )
        style_reference_active = _channel_is_reference_owned(reference_policy_package, "style_finish")
        style_rules = (
            _dedupe(
                rule
                for lock in identity_locks
                for rule in [*lock.keep_rules, *lock.prompt_constraints]
            )[:8]
            if subject_type != "character" or style_reference_active
            else []
        )
        return [
            ProjectIdentityAnchor(
                anchor_id=stable_id(
                    "project_identity_anchor",
                    project_id,
                    subject_type,
                    ",".join(output_ids),
                    ",".join(binding_ids),
                ),
                project_id=project_id,
                subject_type=subject_type,
                source_output_ids=output_ids,
                source_asset_ids=asset_ids,
                source_candidate_ids=candidate_ids,
                source_binding_ids=binding_ids,
                anchor_strength="strong" if hard_binding else "medium",
                identity_keep_rules=keep_rules,
                style_keep_rules=style_rules,
                allowed_variations=allowed_variations,
                forbidden_drift=forbidden_drift,
                provider_reference_required=provider_required,
                prompt_only_fallback=prompt_only,
                user_visible_summary=_summary(subject_type, provider_required),
                metadata={
                    "doc": "58",
                    "job_id": job_id,
                    "template_policy": template_policy.get("policy_id"),
                    "selected_output_count": len(selected_outputs),
                    "strong_binding_count": len(strong_bindings),
                    "doc93_reference_channel_policy": bool(reference_policy_package and reference_policy_package.applies),
                    "reference_policy_package_id": reference_policy_package.package_id if reference_policy_package else None,
                },
            )
        ]


def _subject_type(template_policy: dict[str, Any], identity_locks: list[VisualIdentityLockProfile]) -> str:
    for lock in identity_locks:
        if lock.subject_type in {"character", "product", "brand_asset"}:
            return lock.subject_type
    value = str(template_policy.get("identity_lock_default") or "generic")
    return {"character": "character", "product": "product"}.get(value, "generic")


def _rules_for_subject(
    subject_type: str,
    *,
    reference_policy_package: ResolvedReferencePolicyPackage | None = None,
) -> tuple[list[str], list[str], list[str]]:
    if subject_type == "character":
        keep = [
            "keep the same recognizable person identity",
            "preserve face shape, feature relationships, body type, and broad age direction",
        ]
        forbidden = [
            "identity drift",
            "face swap",
            "major body type drift",
            "same exact expression, pose, and head angle across the full batch",
        ]
        if _channel_is_reference_owned(reference_policy_package, "hair_direction"):
            keep.append("preserve the explicitly assigned hair direction")
            forbidden.append("locked hair direction drift")
        if _channel_is_reference_owned(reference_policy_package, "wardrobe_structure"):
            keep.append("preserve the explicitly assigned wardrobe structure")
            forbidden.append("locked wardrobe structure drift")
        return (
            keep,
            [
                "expression",
                "gaze",
                "pose",
                "head angle",
                "camera distance",
                "small hair movement or styling detail",
                "compatible scene or background",
            ],
            forbidden,
        )
    if subject_type == "product":
        return (
            [
                "keep product shape, material, color, proportions, and label position",
                "do not invent extra product variants or unsupported package details",
            ],
            ["camera angle", "lighting", "surface", "lifestyle scene", "crop"],
            ["product identity drift", "wrong label", "extra unrelated product", "distorted material"],
        )
    return (
        ["keep the selected visual direction, palette, lighting, and composition language"],
        ["framing", "crop", "scene detail", "camera distance"],
        ["style drift", "unrelated object drift", "cluttered composition"],
    )


def _channel_is_reference_owned(package: ResolvedReferencePolicyPackage | None, channel: str) -> bool:
    if package is None or not package.applies:
        return False
    owner = str(package.effective_channel_owners.get(channel) or "")
    return owner.startswith("reference:") and owner.rsplit(":", 1)[-1] in {"hard", "medium"}


def _summary(subject_type: str, provider_required: bool) -> list[str]:
    base = {
        "character": "Selected image is now the person reference for the next generation.",
        "product": "Selected image is now the product reference for the next generation.",
    }.get(subject_type, "Selected image is now the visual reference for the next generation.")
    mode = "Image file will be passed as a strong reference." if provider_required else "Prompt will carry the reference direction when no file is available."
    return [base, mode]


def _identity(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
