from __future__ import annotations

from app.repositories import repository
from app.schemas import ImagePromptPlan, PromptCaseSummary, SafetyDecision
from app.services.ids import new_id


BLOCKED_TERMS = {
    "fake passport",
    "stolen identity",
    "child sexual",
    "explicit minor",
}
CONFIRMATION_TERMS = {
    "celebrity",
    "real person",
    "passport",
    "id card",
    "trademark logo",
}


def run_safety_check(
    *,
    scope: str,
    user_prompt: str,
    prompt_plan: ImagePromptPlan | None = None,
    selected_cases: list[PromptCaseSummary] | None = None,
) -> SafetyDecision:
    user_intent_text = user_prompt.lower()
    generation_text = " ".join(
        [
            user_prompt or "",
            prompt_plan.prompt if prompt_plan else "",
        ]
    ).lower()
    blocked_terms = [term for term in sorted(BLOCKED_TERMS) if term in generation_text]
    confirmation_terms = [term for term in sorted(CONFIRMATION_TERMS) if term in user_intent_text]
    selected_cases = selected_cases or []
    reasons: list[str] = []
    required_transforms: list[str] = []

    if blocked_terms:
        decision = "blocked"
        reasons.append("Blocked content terms were detected.")
    elif confirmation_terms:
        decision = "need_user_confirmation"
        reasons.append("The request may involve identity, portrait, trademark, or sensitive user asset authorization.")
        required_transforms.append("Collect explicit user authorization before final commercial use.")
    else:
        decision = "allow_with_warning"
        reasons.append("No prohibited content detected.")

    if selected_cases:
        reasons.append("Reference cases are used for abstract visual structure only.")
        required_transforms.append("Do not reproduce raw provider images or third-party brand marks.")

    commercial_use_status = "blocked" if blocked_terms else "allowed_after_generation_review"
    safety_decision = SafetyDecision(
        decision_id=new_id("safety"),
        scope=scope,
        decision=decision,
        reasons=reasons,
        blocked_terms=blocked_terms,
        required_transforms=required_transforms,
        user_confirmation_required=bool(confirmation_terms),
        commercial_use_status=commercial_use_status,
    )
    return repository.save_safety_decision(safety_decision)
