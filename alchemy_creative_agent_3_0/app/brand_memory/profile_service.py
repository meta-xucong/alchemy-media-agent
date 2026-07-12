"""V3-owned brand profile service."""

from __future__ import annotations

from .preference_update import should_apply_memory_update
from .store import BrandProfileStore
from ..creative_core.prompt_language import product_language_allowed
from ..creative_core.rules import RULE_VERSION, default_color_palette, stable_id
from ..schemas import BrandProfile, CommercialBrief, CreativeJob, MemoryUpdate, Platform


class BrandProfileService:
    def __init__(self, store: BrandProfileStore | None = None) -> None:
        self.store = store or BrandProfileStore()

    def resolve_for_job(self, job: CreativeJob, brief: CommercialBrief) -> BrandProfile:
        continuation_request = bool(job.metadata.get("continuation_request"))
        if job.optional_brand_id:
            loaded = self.store.load(job.optional_brand_id)
            if loaded is not None:
                loaded.metadata = {
                    **loaded.metadata,
                    "source_agent": "BrandProfileService",
                    "loaded_from_v3_store": True,
                    "continuation_request": continuation_request,
                    "rules_version": RULE_VERSION,
                }
                return loaded
            return self.create_temporary_profile(
                job,
                brief,
                warnings=[
                    f"Brand id {job.optional_brand_id} was not found in V3 brand memory store.",
                    *(
                        ["Continuation request could not load a persistent BrandProfile; using temporary fallback."]
                        if continuation_request
                        else []
                    ),
                ],
            )
        warnings = (
            ["Continuation request has no brand_id; using temporary BrandProfile for this job only."]
            if continuation_request
            else None
        )
        return self.create_temporary_profile(job, brief, warnings=warnings)

    def create_temporary_profile(
        self,
        job: CreativeJob,
        brief: CommercialBrief,
        warnings: list[str] | None = None,
    ) -> BrandProfile:
        allow_product_language = product_language_allowed(
            template_id=job.optional_template_id,
            scenario_id=job.metadata.get("scenario_id"),
            industry=brief.industry,
            user_input=job.raw_user_input,
            metadata={**brief.metadata, **job.metadata},
        )
        return BrandProfile(
            brand_id=f"temp_brand_{job.job_id}",
            brand_name=None,
            industry=brief.industry,
            is_temporary=True,
            visual_tone=list(brief.visual_tone),
            color_palette=default_color_palette(brief.industry, brief.visual_tone),
            layout_preference=(
                "LLM/provider-directed product presentation responsive to the approved creative brief"
                if allow_product_language
                else "LLM/provider-directed subject presentation responsive to the creative brief"
            ),
            typography_preference=(
                "provider-native typography only when the user explicitly supplies or approves in-image copy"
                if allow_product_language
                else "provider-native typography only when the user explicitly requests in-image text"
            ),
            copywriting_tone=brief.copy_strategy,
            reference_assets=[],
            rejected_style_tags=list(brief.risks),
            platform_history=list(brief.target_platforms),
            metadata={
                "source_agent": "BrandProfileService",
                "created_from": "commercial_brief",
                "rules_version": RULE_VERSION,
                "warnings": warnings or [],
                "continuation_request": bool(job.metadata.get("continuation_request")),
            },
        )

    def create_profile_from_brief(
        self,
        job: CreativeJob,
        brief: CommercialBrief,
        brand_id: str,
        brand_name: str | None = None,
    ) -> BrandProfile:
        profile = self.create_temporary_profile(job, brief)
        profile.brand_id = brand_id
        profile.brand_name = brand_name
        profile.is_temporary = False
        profile.metadata = {
            **profile.metadata,
            "created_from": "commercial_brief",
            "promoted_to_persistent": True,
        }
        return profile

    def save_profile(self, profile: BrandProfile) -> BrandProfile:
        profile.is_temporary = False
        profile.metadata = {**profile.metadata, "saved_by": "BrandProfileService"}
        return self.store.save(profile)

    def load_profile(self, brand_id: str) -> BrandProfile | None:
        return self.store.load(brand_id)

    def propose_memory_update(
        self,
        brand_profile: BrandProfile,
        accepted_asset_ids: list[str],
        style_tags: list[str],
        planning_only: bool = True,
    ) -> MemoryUpdate:
        return MemoryUpdate(
            memory_update_id=stable_id("memory_update", brand_profile.brand_id, ",".join(accepted_asset_ids)),
            brand_id=brand_profile.brand_id,
            action="propose",
            accepted_asset_ids=accepted_asset_ids,
            new_style_tags=list(dict.fromkeys(style_tags)),
            notes="Planning-only memory update proposal; not applied in V3.0 foundation." if planning_only else None,
            applied=False,
            metadata={
                "source_agent": "BrandProfileService",
                "planning_only": planning_only,
                "rules_version": RULE_VERSION,
                "update_status": "proposed",
            },
        )

    def apply_memory_update(self, update: MemoryUpdate) -> BrandProfile | None:
        if not should_apply_memory_update(update):
            return None
        profile = self.store.load(update.brand_id)
        if profile is None:
            return None
        for asset_id in update.accepted_asset_ids:
            if asset_id not in profile.successful_asset_ids:
                profile.successful_asset_ids.append(asset_id)
        existing_reference_ids = {reference.asset_id for reference in profile.reference_assets}
        for reference in update.new_reference_assets:
            if reference.asset_id not in existing_reference_ids:
                profile.reference_assets.append(reference)
                existing_reference_ids.add(reference.asset_id)
            platform_value = reference.metadata.get("platform")
            if platform_value:
                try:
                    platform = Platform(platform_value)
                except ValueError:
                    continue
                if platform not in profile.platform_history:
                    profile.platform_history.append(platform)
        for tag in update.new_style_tags:
            if tag not in profile.visual_tone:
                profile.visual_tone.append(tag)
        for tag in update.new_rejected_style_tags:
            if tag not in profile.rejected_style_tags:
                profile.rejected_style_tags.append(tag)
        update.applied = True
        update.metadata = {**update.metadata, "update_status": "applied"}
        profile.metadata = {**profile.metadata, "last_memory_update_id": update.memory_update_id}
        return self.store.save(profile)
