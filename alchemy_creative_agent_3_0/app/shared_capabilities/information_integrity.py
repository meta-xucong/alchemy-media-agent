"""Information and product fact integrity constraints."""

from __future__ import annotations

from typing import Any

from .base import SharedCapabilityModule
from .contracts import (
    CapabilityConstraint,
    CapabilityInput,
    CapabilityResult,
    CapabilityStatus,
    CapabilityTargetStage,
    CapabilityWarning,
)


CLAIM_RISK_TOKENS = ("certified", "fda", "patent", "guarantee", "guaranteed", "100%", "medical", "cure")


class InformationIntegrityLockModule(SharedCapabilityModule):
    module_id = "information_integrity_lock"
    version = "v3_shared_capability_001"
    order = 50

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        profile = capability_input.product_profile or {}
        required_text = self._list(profile.get("required_text"))
        facts = self._list(profile.get("facts") or profile.get("visible_attributes"))
        claims = self._list(profile.get("claims"))
        evidence = self._list(profile.get("evidence") or profile.get("evidence_sources"))
        if not required_text and not facts and not claims:
            return CapabilityResult(
                module_id=self.module_id,
                version=self.version,
                status=CapabilityStatus.SKIPPED,
                audit_trail=["no product facts, required text, or claims supplied"],
            )

        unsupported_claims = [claim for claim in claims if self._claim_requires_evidence(claim) and not evidence]
        warnings = [
            CapabilityWarning(
                code="unsupported_claim_requires_evidence",
                message=f"Claim requires evidence before visual use: {claim}",
                metadata={"claim": claim},
            )
            for claim in unsupported_claims
        ]
        constraints: list[CapabilityConstraint] = []
        if required_text:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                    constraint_type="exact_text_preservation",
                    strength="strong",
                    value={"required_text": required_text},
                    source=self.module_id,
                )
            )
        if facts:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.EVALUATION,
                    constraint_type="product_fact_review",
                    strength="strong",
                    value={"must_preserve_facts": facts},
                    source=self.module_id,
                )
            )
        if unsupported_claims:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                    constraint_type="forbidden_unsupported_claims",
                    strength="strong",
                    value={"claims": unsupported_claims},
                    source=self.module_id,
                )
            )
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=CapabilityStatus.WARNING if warnings else CapabilityStatus.SUCCESS,
            confidence=0.8,
            facts={
                "information_integrity": {
                    "required_text": required_text,
                    "must_preserve_facts": facts,
                    "claims": claims,
                    "unsupported_claims": unsupported_claims,
                    "evidence": evidence,
                }
            },
            constraints=constraints,
            warnings=warnings,
            audit_trail=["built information integrity constraints"],
        )

    def _list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [" ".join(str(item).strip().split()) for item in value if str(item).strip()]
        if isinstance(value, dict):
            return [f"{key}: {val}" for key, val in value.items() if str(val).strip()]
        text = str(value).strip()
        return [text] if text else []

    def _claim_requires_evidence(self, claim: str) -> bool:
        lower = claim.lower()
        return any(token in lower for token in CLAIM_RISK_TOKENS)
