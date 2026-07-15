"""Deterministic validator and planner for capability activation."""

from __future__ import annotations

from typing import Any

from .catalog import VisualCapabilityRegistry
from .contracts import (
    ActivatedCapability,
    CapabilityActivationIntent,
    CapabilityActivationPlan,
    CapabilityBudgetDecision,
    CapabilityConflictDecision,
    InactiveCapability,
    TemplateCapabilityBinding,
    TemplateCapabilityPolicy,
    VisualTaskProfile,
    activation_fingerprint,
)


class CapabilityActivationError(ValueError):
    pass


class CapabilityActivationPlanner:
    def __init__(self, registry: VisualCapabilityRegistry) -> None:
        self.registry = registry

    def plan(
        self,
        *,
        task_profile: VisualTaskProfile,
        intent: CapabilityActivationIntent,
        template_policy: TemplateCapabilityPolicy,
        catalog_version: str,
        activation_mode: str,
        fallback_used: bool = False,
        budget: int | None = None,
    ) -> CapabilityActivationPlan:
        requested = {item.capability_id: item for item in intent.requested_capabilities}
        required = {item.capability_id: item for item in template_policy.required_capabilities}
        recommended = {item.capability_id: item for item in template_policy.recommended_capabilities}
        optional = {item.capability_id: item for item in template_policy.optional_capabilities}
        forbidden = set(template_policy.forbidden_capabilities)
        active: dict[str, ActivatedCapability] = {}
        inactive: dict[str, InactiveCapability] = {}
        budget_decisions: list[CapabilityBudgetDecision] = []
        conflict_decisions: list[CapabilityConflictDecision] = []

        for capability_id, binding in required.items():
            self._activate(active, capability_id, "required", ["template_required"], [], 1.0, binding, template_policy)

        # A remote Brain may correctly describe a visible real person in its
        # task profile yet omit the corresponding capability from its proposed
        # list.  In enforced mode that omission used to suppress the shared
        # Human Realism executor altogether.  The profile is the evidence
        # authority; a capability proposal is not allowed to weaken this
        # foundation-level routing invariant.
        #
        # This is deliberately not a template, commerce, apparel, or child
        # rule.  It applies only to an asserted visible person in a
        # non-stylized image task, and it keeps the evidence on the frozen
        # activation plan for provider, review, and retry provenance.
        for capability_id, reason_codes, evidence_ids, confidence in self._shared_required_capabilities(task_profile):
            if capability_id in forbidden:
                raise CapabilityActivationError(f"required shared capability is forbidden: {capability_id}")
            self._activate(
                active,
                capability_id,
                "required",
                reason_codes,
                evidence_ids,
                confidence,
                optional.get(capability_id),
                template_policy,
            )

        candidates: list[tuple[str, str, TemplateCapabilityBinding | None]] = []
        for capability_id in requested:
            candidates.append((capability_id, requested[capability_id].activation_mode, None))
        for capability_id, binding in recommended.items():
            candidates.append((capability_id, "recommended", binding))
        for capability_id, binding in optional.items():
            if capability_id in requested:
                candidates.append((capability_id, "optional", binding))

        evidence_ids = {item.evidence_id for item in task_profile.evidence}
        for capability_id, default_mode, binding in candidates:
            if capability_id in active:
                continue
            request = requested.get(capability_id)
            manifest = self.registry.manifest(capability_id)
            if manifest is None:
                inactive[capability_id] = InactiveCapability(capability_id=capability_id, reason_code="unknown_capability")
                continue
            if capability_id in forbidden or (request and request.activation_mode == "forbidden"):
                inactive[capability_id] = InactiveCapability(capability_id=capability_id, reason_code="template_or_user_forbidden")
                continue
            if task_profile.template_id in manifest.forbidden_templates:
                inactive[capability_id] = InactiveCapability(capability_id=capability_id, reason_code="template_not_allowed")
                continue
            confidence = request.confidence if request else 0.0
            threshold = template_policy.activation_threshold_overrides.get(
                capability_id,
                binding.minimum_confidence if binding and binding.minimum_confidence is not None else manifest.minimum_activation_confidence,
            )
            matching_evidence = [item for item in (request.evidence_ids if request else []) if item in evidence_ids]
            if confidence < threshold:
                inactive[capability_id] = InactiveCapability(
                    capability_id=capability_id,
                    reason_code="no_evidence" if request is None else "insufficient_confidence",
                    evidence_ids=matching_evidence,
                )
                continue
            mode = request.activation_mode if request else default_mode
            if budget is not None and mode == "optional" and len(active) >= budget:
                inactive[capability_id] = InactiveCapability(capability_id=capability_id, reason_code="budget_excluded")
                budget_decisions.append(CapabilityBudgetDecision(capability_id=capability_id, included=False, reason_code="budget_excluded", cost=manifest.estimated_cost))
                continue
            effective_binding = binding
            if request and request.requested_profile:
                effective_binding = (binding or TemplateCapabilityBinding(capability_id=capability_id)).model_copy(
                    update={"profile": request.requested_profile}
                )
            self._activate(
                active,
                capability_id,
                mode,
                request.reason_codes if request else ["template_recommended"],
                matching_evidence,
                confidence,
                effective_binding,
                template_policy,
            )
            budget_decisions.append(CapabilityBudgetDecision(capability_id=capability_id, included=True, reason_code="within_budget", cost=manifest.estimated_cost))

        self._add_dependencies(active, inactive, template_policy)
        for capability_id in list(active):
            manifest = self.registry.manifest(capability_id)
            if manifest is None:
                continue
            for conflict in manifest.conflicts:
                if conflict not in active:
                    continue
                winner = self._conflict_winner(active[capability_id], active[conflict])
                loser = conflict if winner == capability_id else capability_id
                active.pop(loser, None)
                inactive[loser] = InactiveCapability(capability_id=loser, reason_code="conflict_lost")
                conflict_decisions.append(CapabilityConflictDecision(capability_ids=sorted([capability_id, conflict]), winner=winner, reason_code="activation_precedence"))

        graph = self.registry.validate_graph(list(active))
        if not graph.valid:
            raise CapabilityActivationError(
                f"invalid capability graph: missing={graph.missing_dependencies}, cycles={graph.cycles}"
            )
        ordered = graph.dependency_order
        activated = [active[item] for item in ordered]
        base_ids = {item.capability_id for item in template_policy.required_capabilities}
        base = [item for item in activated if item.capability_id in base_ids]
        fingerprint = activation_fingerprint(
            task_profile.job_id,
            catalog_version,
            template_policy.model_dump_json(),
            *[
                f"{item.capability_id}@{item.version}:{item.selected_profile}:{item.activation_mode}:"
                f"{','.join(item.reason_codes)}:{','.join(item.evidence_ids)}"
                for item in activated
            ],
        )
        return CapabilityActivationPlan(
            plan_id=activation_fingerprint("plan", fingerprint),
            fingerprint=fingerprint,
            project_id=task_profile.project_id,
            job_id=task_profile.job_id,
            task_profile_id=task_profile.profile_id,
            template_id=task_profile.template_id,
            scenario_id=task_profile.scenario_id,
            base_capabilities=base,
            active_capabilities=activated,
            inactive_capabilities=sorted(inactive.values(), key=lambda item: item.capability_id),
            dependency_order=ordered,
            conflict_decisions=conflict_decisions,
            budget_decisions=budget_decisions,
            fallback_used=fallback_used,
            catalog_version=catalog_version,
            activation_mode=activation_mode,
        )

    @staticmethod
    def _shared_required_capabilities(
        task_profile: VisualTaskProfile,
    ) -> list[tuple[str, list[str], list[str], float]]:
        """Return evidence-backed shared capabilities that cannot be omitted.

        The current invariant is intentionally narrow: a *visible* ``person``
        plus an affirmative real-person/visible-person evidence item requires
        Human Realism, unless the task profile explicitly declares a
        non-photorealistic person.  A person noun alone, a hidden person, an
        animal, or a product does not qualify.
        """

        visible_people = [
            entity
            for entity in task_profile.subject_entities
            if entity.entity_type.strip().casefold() == "person" and entity.visible_in_target
        ]
        if not visible_people:
            return []

        if task_profile.rendering_intent.explicitly_stylized_whole_image:
            return []

        evidence = [
            item
            for item in task_profile.evidence
            if item.evidence_type in {"visible_person", "real_human_output"}
            and item.value is not False
        ]
        if not evidence:
            return []

        return [
            (
                "human_realism",
                ["visible_real_person_execution_invariant"],
                [item.evidence_id for item in evidence],
                max([item.confidence for item in evidence] + [entity.confidence for entity in visible_people]),
            )
        ]

    def _activate(
        self,
        active: dict[str, ActivatedCapability],
        capability_id: str,
        mode: str,
        reasons: list[str],
        evidence_ids: list[str],
        confidence: float,
        binding: TemplateCapabilityBinding | None,
        policy: TemplateCapabilityPolicy,
        dependency_source: str | None = None,
    ) -> None:
        manifest = self.registry.manifest(capability_id)
        if manifest is None:
            if mode == "required":
                raise CapabilityActivationError(f"required capability is not registered: {capability_id}")
            return
        profile = policy.profile_overrides.get(capability_id) or (binding.profile if binding else None) or manifest.supported_profiles[0]
        if profile not in manifest.supported_profiles:
            raise CapabilityActivationError(f"unsupported profile {profile} for {capability_id}")
        active[capability_id] = ActivatedCapability(
            capability_id=capability_id,
            version=manifest.version,
            selected_profile=profile,
            activation_mode=mode,
            reason_codes=list(dict.fromkeys(reasons)),
            evidence_ids=list(dict.fromkeys(evidence_ids)),
            template_configuration=dict(binding.config) if binding else {},
            dependency_source=dependency_source,
            confidence=max(0.0, min(1.0, confidence)),
        )

    def _add_dependencies(
        self,
        active: dict[str, ActivatedCapability],
        inactive: dict[str, InactiveCapability],
        policy: TemplateCapabilityPolicy,
    ) -> None:
        queue = list(active)
        while queue:
            capability_id = queue.pop(0)
            manifest = self.registry.manifest(capability_id)
            if manifest is None:
                continue
            for dependency in manifest.dependencies:
                if dependency in policy.forbidden_capabilities:
                    raise CapabilityActivationError(f"dependency {dependency} is forbidden for {capability_id}")
                if dependency in active:
                    continue
                if self.registry.manifest(dependency) is None:
                    raise CapabilityActivationError(f"missing dependency {dependency} for {capability_id}")
                self._activate(active, dependency, "required", ["dependency"], [], 1.0, None, policy, capability_id)
                inactive.pop(dependency, None)
                queue.append(dependency)

    def _conflict_winner(self, left: ActivatedCapability, right: ActivatedCapability) -> str:
        rank = {"required": 4, "recommended": 3, "optional": 2, "forbidden": 0}
        left_key = (rank.get(left.activation_mode, 1), left.confidence, left.capability_id)
        right_key = (rank.get(right.activation_mode, 1), right.confidence, right.capability_id)
        return left.capability_id if left_key >= right_key else right.capability_id
