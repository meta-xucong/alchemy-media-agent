from __future__ import annotations

from app.schemas import ProviderError


BLOCKED_TERMS = ["违法", "色情", "仇恨", "暴力血腥", "泄露密钥", "复刻受保护角色"]


def check_generation_prompt(prompt: str) -> ProviderError | None:
    normalized = prompt.lower()
    for term in BLOCKED_TERMS:
        if term.lower() in normalized:
            return ProviderError(
                code="safety_rejected",
                message="请求触发内容安全或合规边界，请调整为安全、合法且具备授权的生成需求。",
                retryable=False,
                detail={"matched_policy": term},
            )
    return None
