"""Deterministic case retrieval and visual inspiration extraction."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .base import SharedCapabilityModule
from .contracts import CapabilityInput, CapabilityResult, CapabilityStatus


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


DEFAULT_CASES = [
    {
        "case_id": "case_general_campaign_poster",
        "scenario_id": "general_creative",
        "category": "campaign",
        "title": "Clean Campaign Poster",
        "style_tags": ["clean", "bright", "polished"],
        "composition_tags": ["large hero", "cover-safe clean space", "simple background"],
        "use_case_tags": ["poster", "social", "launch"],
        "visual_signals": ["large central hero", "clean optional blank space", "bright clean lighting"],
    },
    {
        "case_id": "case_general_social_cover",
        "scenario_id": "general_creative",
        "category": "social",
        "title": "Social Media Cover",
        "style_tags": ["fresh", "youthful", "high clarity"],
        "composition_tags": ["square crop", "safe margins", "strong cover rhythm"],
        "use_case_tags": ["social", "cover", "campaign"],
        "visual_signals": ["square composition", "cover-safe clean space", "clean subject separation"],
    },
]


class CaseLibraryRetriever(SharedCapabilityModule):
    module_id = "case_library_retriever"
    version = "v3_shared_capability_001"
    order = 30

    def __init__(self, cases: list[dict[str, Any]] | None = None, max_cases: int = 3) -> None:
        self.cases = cases or DEFAULT_CASES
        self.max_cases = max_cases

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        query_tokens = self._tokens(
            " ".join(
                [
                    capability_input.user_input,
                    str(capability_input.product_profile.get("category", "")),
                    str(capability_input.product_profile.get("style", "")),
                ]
            )
        )
        scored = []
        for case in self.cases:
            if not self._scenario_allowed(capability_input.scenario_id, case):
                continue
            case_text = " ".join(
                [
                    case.get("scenario_id", ""),
                    case.get("category", ""),
                    case.get("title", ""),
                    " ".join(case.get("style_tags", [])),
                    " ".join(case.get("composition_tags", [])),
                    " ".join(case.get("use_case_tags", [])),
                ]
            )
            case_tokens = self._tokens(case_text)
            overlap = sorted(set(query_tokens) & set(case_tokens))
            score = len(overlap) / max(len(set(query_tokens)) or 1, 1)
            if not query_tokens and case.get("scenario_id") == capability_input.scenario_id:
                score = 0.1
            if score > 0:
                scored.append((score, overlap, case))
        scored.sort(key=lambda item: (-item[0], item[2]["case_id"]))
        selected = [
            {
                **case,
                "match_score": round(score, 3),
                "match_reasons": [f"matched token: {token}" for token in overlap[:6]] or ["scenario default match"],
            }
            for score, overlap, case in scored[: self.max_cases]
        ]
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=CapabilityStatus.SUCCESS if selected else CapabilityStatus.SKIPPED,
            confidence=0.68 if selected else 0.0,
            facts={"selected_cases": selected},
            audit_trail=[f"retrieved {len(selected)} case(s) for scenario {capability_input.scenario_id}"],
            metadata={"case_index_size": len(self.cases)},
        )

    def _scenario_allowed(self, scenario_id: str, case: dict[str, Any]) -> bool:
        case_scenario = case.get("scenario_id")
        if scenario_id == "general_creative":
            return case_scenario == "general_creative"
        return case_scenario in {scenario_id, "general_creative"}

    def _tokens(self, text: str) -> Counter[str]:
        return Counter(token.lower() for token in TOKEN_RE.findall(text))
