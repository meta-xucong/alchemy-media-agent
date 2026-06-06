from __future__ import annotations

from statistics import mean
from typing import Any

from app.schemas import GenerationJob, GenerationOutput, VisualReviewResult
from app.services.utils import now_iso


def review_image_output(job: GenerationJob, output: GenerationOutput) -> VisualReviewResult | None:
    if not job.asset_plan or job.asset_mode != "advanced":
        return None

    checks: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []
    roles = {str(item.get("role")) for item in job.asset_plan.get("assets", []) if item.get("role")}
    if roles & {"style_reference", "background_reference"}:
        checks["style_alignment"] = _check(
            _score(output, "asset_consistency", fallback=0.82),
            "素材风格/背景参考已进入 provider 图片输入或提示词约束。",
        )
    if roles & {"subject_reference", "portrait_identity"}:
        checks["subject_preservation"] = _check(
            _score(output, "subject_integrity", fallback=0.78),
            "主体/人物保真已声明为复检重点；强保真仍依赖真实图片引用和人工验收。",
        )
    if "composition_reference" in roles:
        checks["composition_alignment"] = _check(
            _score(output, "composition", fallback=0.8),
            "构图参考已写入最终提示词，并随参考图片传给支持的 provider。",
        )
    if "logo_overlay" in roles:
        logo_check, logo_issues = _logo_check(job, output)
        checks["logo_integrity"] = logo_check
        issues.extend(logo_issues)
    if not checks:
        checks["advanced_material_usage"] = _check(0.75, "高级素材链路已启用，但当前角色主要依赖提示词约束。")

    reference_count = 0
    provider_input_plan = job.asset_plan.get("provider_input_plan") or {}
    if isinstance(provider_input_plan, dict):
        reference_count = int(provider_input_plan.get("reference_image_count") or 0)
    reference_roles = {"style_reference", "subject_reference", "portrait_identity", "background_reference", "composition_reference"}
    if _logo_uses_reference_image(job):
        reference_roles.add("logo_overlay")
    if roles & reference_roles and reference_count <= 0:
        issues.append(
            {
                "severity": "high",
                "code": "reference_image_missing",
                "message": "高级参考角色没有进入真实图片输入链路，生成质量可能只受提示词影响。",
            }
        )

    scores = [float(item.get("score", 0)) for item in checks.values() if isinstance(item, dict) and item.get("score") is not None]
    overall = mean(scores) if scores else 0.0
    recommendation = None
    if issues:
        recommendation = "建议重新生成前检查素材角色、provider 图片引用能力和 Logo/人物保真设置。"
    elif overall < 0.72:
        recommendation = "建议提高素材保真强度，或切换到支持图片引用更稳定的生图模型。"
    else:
        recommendation = "复检未发现明显结构性风险，可进入人工验收。"

    return VisualReviewResult(
        review_status="ready",
        overall_score=round(overall, 3),
        checks=checks,
        issues=issues,
        retry_recommendation=recommendation,
        created_at=now_iso(),
    )


def _check(score: float, message: str) -> dict[str, Any]:
    return {"score": round(max(0.0, min(score, 1.0)), 3), "message": message}


def _score(output: GenerationOutput, field: str, *, fallback: float) -> float:
    if not output.score:
        return fallback
    return float(getattr(output.score, field, fallback) or fallback)


def _logo_check(job: GenerationJob, output: GenerationOutput) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if _logo_uses_reference_image(job):
        provider_input_plan = job.asset_plan.get("provider_input_plan") or {}
        reference_count = int(provider_input_plan.get("reference_image_count") or 0) if isinstance(provider_input_plan, dict) else 0
        targets = [
            (item.get("placement_intent") or {}).get("target_label")
            for item in job.asset_plan.get("assets", [])
            if item.get("role") == "logo_overlay" and item.get("provider_input_mode") == "reference_image"
        ]
        target = next((item for item in targets if item), "用户指定的物体表面")
        if reference_count <= 0:
            return _check(0.48, "Logo/标识需要作为参考图进入场景内表面，但未检测到参考图输入链路。"), [
                {"severity": "high", "code": "logo_reference_image_missing", "message": "场景内 Logo 放置缺少真实参考图输入。"}
            ]
        return _check(0.78, f"Logo/标识已作为参考图进入生图模型，应融合到{target}；仍需人工确认没有被放成海报角标或底部贴片。"), []
    steps = output.metadata.get("postprocess_steps") or []
    logo_steps = [item for item in steps if item.get("type") == "logo_overlay"]
    if not logo_steps:
        return _check(0.45, "Logo/标识未执行确定性叠加，存在被模型重绘或缺失风险。"), [
            {"severity": "high", "code": "logo_overlay_missing", "message": "未找到 Logo 后处理记录。"}
        ]
    failed = [item for item in logo_steps if item.get("status") != "succeeded"]
    if failed:
        return _check(0.5, "Logo/标识后处理失败，需要检查素材透明通道、位置和输出格式。"), [
            {
                "severity": "high",
                "code": "logo_overlay_failed",
                "message": str(failed[0].get("message") or "Logo 后处理失败。"),
            }
        ]
    return _check(0.95, "Logo/标识通过确定性后处理叠加，优先保留原素材形态。"), []


def _logo_uses_reference_image(job: GenerationJob) -> bool:
    if not job.asset_plan:
        return False
    return any(
        item.get("role") == "logo_overlay" and item.get("provider_input_mode") == "reference_image"
        for item in job.asset_plan.get("assets", [])
    )
