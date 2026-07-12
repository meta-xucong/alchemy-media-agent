"""Metadata critic for e-commerce image set plans."""

from __future__ import annotations

from .contracts import CommerceCriticReport, CommerceIntelligenceBrief, EcommerceAssetRecipe, MarketplaceRuleProfile, ProductTruthLock


class CommerceCritic:
    """Review recipes for product correctness, clarity, trust, and platform fit."""

    def review(
        self,
        *,
        truth: ProductTruthLock,
        brief: CommerceIntelligenceBrief,
        marketplace_profile: MarketplaceRuleProfile,
        recipes: list[EcommerceAssetRecipe],
    ) -> CommerceCriticReport:
        checks: list[dict] = []
        warnings: list[str] = []
        checks.append(self._check("product_truth", bool(truth.immutable_attributes), "Product truth facts are available."))
        checks.append(self._check("slot_coverage", len(recipes) >= 5, f"{len(recipes)} image slot(s) planned."))
        checks.append(
            self._check(
                "selling_point_mapping",
                all(recipe.selling_point for recipe in recipes),
                "Every planned image has one primary selling point.",
            )
        )
        profile_lineage = marketplace_profile.metadata
        checks.append(
            self._check(
                "platform_profile_lineage",
                bool(profile_lineage.get("profile_id") and profile_lineage.get("profile_version") and profile_lineage.get("profile_status")),
                "Platform profile identifier, version, and status are frozen for the planned suite.",
            )
        )
        delivery_scope_status = str(profile_lineage.get("status") or "ready")
        delivery_scope_id = str(profile_lineage.get("delivery_scope_id") or "listing_only")
        scope_missing_requirements = [str(item) for item in profile_lineage.get("missing_requirements") or [] if str(item)]
        checks.append(
            self._check(
                "delivery_scope_context",
                delivery_scope_status == "ready",
                (
                    f"Delivery scope {delivery_scope_id} has the required placement context."
                    if delivery_scope_status == "ready"
                    else "Delivery scope needs explicit context before it can plan deliverables: "
                    + ", ".join(scope_missing_requirements)
                ),
            )
        )
        category_coverage = self._category_coverage(recipes)
        if category_coverage is not None:
            checks.append(
                self._check(
                    "category_evidence_coverage",
                    not category_coverage["missing"],
                    "Selected slots cover the category evidence required for this suite scope.",
                )
            )
        duplicate_pairs = self._duplicate_pairs(recipes)
        checks.append(
            self._check(
                "suite_differentiation",
                not duplicate_pairs,
                "Every selected slot has a distinct buyer-facing job and selling-point direction.",
            )
        )
        forbidden_text_request = [
            recipe
            for recipe in recipes
            if (recipe.metadata.get("copy_plan") or {}).get("policy") == "text_forbidden" and recipe.provider_native_text
        ]
        checks.append(
            self._check(
                "main_image_text_policy",
                not forbidden_text_request,
                "Text-forbidden slots do not request provider-native copy.",
            )
        )
        localization_review_slots = [
            recipe.slot
            for recipe in recipes
            if bool((recipe.metadata.get("copy_plan") or {}).get("needs_localization_review"))
        ]
        checks.append(
            self._check(
                "localization_review",
                not localization_review_slots,
                "Localized provider-native copy is user-supplied or has passed the current metadata review gate.",
            )
        )
        claim_review_slots = [
            recipe.slot
            for recipe in recipes
            if bool((recipe.metadata.get("copy_plan") or {}).get("claim_review_required"))
        ]
        checks.append(
            self._check(
                "overlay_claim_review",
                not claim_review_slots,
                "Requested provider-native copy does not contain a claim that needs supplied evidence or publication review.",
            )
        )
        checks.append(
            self._check(
                "platform_profile",
                bool(marketplace_profile.image_slots and marketplace_profile.canvas_rules),
                f"Marketplace profile is available for {marketplace_profile.platform}.",
            )
        )
        checks.append(
            self._check(
                "claim_risk",
                not brief.claim_risk_warnings,
                "Unsupported claims require softer copy or evidence before export.",
            )
        )
        confirmation_facts = [
            fact
            for fact in truth.fact_ledger
            if fact.verification == "requires_confirmation"
        ]
        unverified_visual_facts = [fact.value for fact in confirmation_facts]
        checks.append(
            self._check(
                "unverified_visual_fact_confirmation",
                not unverified_visual_facts,
                "Supplier-provided visual facts not visible in the reference require product-owner confirmation before delivery.",
            )
        )
        blocked_fact_values = [
            fact.value
            for fact in truth.fact_ledger
            if fact.verification == "blocked"
        ]
        blocked_fact_leaks = [
            recipe.slot
            for recipe in recipes
            if any(
                fact.lower() in " ".join([*recipe.required_product_facts, recipe.visual_scene, recipe.overlay_text or ""]).lower()
                for fact in blocked_fact_values
            )
        ]
        blocked_copy_slots = [
            recipe.slot
            for recipe in recipes
            if (recipe.metadata.get("copy_plan") or {}).get("policy") == "text_blocked"
        ]
        checks.append(
            self._check(
                "blocked_product_fact_leakage",
                not blocked_fact_leaks,
                "Facts marked blocked do not appear in product prompts, overlay copy, or export bindings.",
            )
        )
        if truth.warnings:
            warnings.extend(truth.warnings)
        if marketplace_profile.warnings:
            warnings.extend(marketplace_profile.warnings)
        if delivery_scope_status != "ready":
            warnings.append(
                "Delivery scope cannot plan files until required placement context is supplied: "
                + ", ".join(scope_missing_requirements)
            )
        if brief.claim_risk_warnings:
            warnings.extend(brief.claim_risk_warnings)
        if unverified_visual_facts:
            warnings.append(
                "Supplier-provided visual facts need product-owner confirmation before delivery: "
                + ", ".join(unverified_visual_facts)
            )
        if blocked_copy_slots:
            warnings.append(
                "Overlay copy was removed because it repeated blocked product facts: " + ", ".join(blocked_copy_slots)
            )
        if blocked_fact_leaks:
            warnings.append("Blocked product facts leaked into planned slots: " + ", ".join(blocked_fact_leaks))
        if localization_review_slots:
            warnings.append(
                "Provider-native copy requires native-language review before export: " + ", ".join(localization_review_slots)
            )
        if claim_review_slots:
            warnings.append("Provider-native copy requires claim review before export: " + ", ".join(claim_review_slots))
        if category_coverage and category_coverage["missing"]:
            warnings.append(
                "Selected suite does not yet cover category evidence: " + ", ".join(category_coverage["missing"])
            )
        if duplicate_pairs:
            warnings.append(
                "Selected suite has overlapping roles that need a distinct selling point or scene: "
                + ", ".join(f"{left}/{right}" for left, right in duplicate_pairs)
            )

        status = "attention" if any(check["status"] == "attention" for check in checks) else "ready"
        return CommerceCriticReport(
            status=status,
            checks=checks,
            warnings=list(dict.fromkeys(warnings)),
            metadata={
                "source": "CommerceCritic",
                "metadata_only_review": True,
                "recipe_count": len(recipes),
                "delivery_scope_id": delivery_scope_id,
                "delivery_scope_status": delivery_scope_status,
                "delivery_scope_missing_requirements": scope_missing_requirements,
                "localization_review_slots": localization_review_slots,
                "claim_review_slots": claim_review_slots,
                "unverified_visual_facts": unverified_visual_facts,
                "confirmation_fact_ids": [fact.fact_id for fact in confirmation_facts],
                "blocked_fact_ids": [fact.fact_id for fact in truth.fact_ledger if fact.verification == "blocked"],
                "blocked_fact_leak_slots": blocked_fact_leaks,
                "blocked_copy_slots": blocked_copy_slots,
                "category_evidence": category_coverage,
                "duplicate_slot_pairs": duplicate_pairs,
            },
        )

    def _check(self, check_id: str, passed: bool, detail: str) -> dict:
        return {
            "id": check_id,
            "label": check_id.replace("_", " ").title(),
            "status": "done" if passed else "attention",
            "detail": detail,
        }

    def _category_coverage(self, recipes: list[EcommerceAssetRecipe]) -> dict[str, list[str]] | None:
        category_id = ""
        required: list[str] = []
        covered: list[str] = []
        for recipe in recipes:
            metadata = recipe.metadata
            category_id = category_id or str(metadata.get("category_id") or "")
            required.extend(str(item) for item in metadata.get("required_evidence") or [])
            covered.extend(str(item) for item in metadata.get("category_evidence_targets") or [])
        required = list(dict.fromkeys(required))
        covered = list(dict.fromkeys(covered))
        if not category_id or category_id == "generic_product" or not required:
            return None
        return {
            "category_id": category_id,
            "required": required,
            "covered": covered,
            "missing": [item for item in required if item not in covered],
        }

    def _duplicate_pairs(self, recipes: list[EcommerceAssetRecipe]) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for index, recipe in enumerate(recipes):
            signature = (recipe.business_goal, recipe.selling_point.strip().lower())
            for other in recipes[index + 1 :]:
                other_signature = (other.business_goal, other.selling_point.strip().lower())
                if signature == other_signature:
                    pairs.append((recipe.slot, other.slot))
        return pairs
