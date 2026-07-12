"""Versioned, E-Commerce-owned category evidence directors."""

from __future__ import annotations

from dataclasses import dataclass


CATEGORY_PROFILE_VERSION = "v3_ecommerce_categories_2026_07_12_d2"


@dataclass(frozen=True)
class CategorySlotDirector:
    """The business proof job for one E-Commerce runtime slot."""

    slot: str
    role_id: str
    purpose: str
    evidence: tuple[str, ...]
    fact_channels: tuple[str, ...]
    review_checks: tuple[str, ...]
    differentiation_key: str
    direction: str

    def metadata(self) -> dict[str, object]:
        return {
            "id": self.role_id,
            "purpose": self.purpose,
            "evidence": list(self.evidence),
            "fact_channels": list(self.fact_channels),
            "review_checks": list(self.review_checks),
            "differentiation_key": self.differentiation_key,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class CategoryProfile:
    category_id: str
    display_name: str
    buyer_questions: tuple[str, ...]
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    default_slot_priority: tuple[str, ...]
    human_presence_policy: str
    text_roles: tuple[str, ...]
    product_truth_fields: tuple[str, ...]
    review_checks: tuple[str, ...]
    slot_directors: tuple[CategorySlotDirector, ...]

    def metadata(self) -> dict[str, object]:
        return {
            "category_id": self.category_id,
            "category_profile_version": CATEGORY_PROFILE_VERSION,
            "buyer_questions": list(self.buyer_questions),
            "required_evidence": list(self.required_evidence),
            "optional_evidence": list(self.optional_evidence),
            "human_presence_policy": self.human_presence_policy,
            "text_roles": list(self.text_roles),
            "product_truth_fields": list(self.product_truth_fields),
            "review_checks": list(self.review_checks),
        }


def _director(
    slot: str,
    role_id: str,
    purpose: str,
    evidence: tuple[str, ...],
    fact_channels: tuple[str, ...],
    review_checks: tuple[str, ...],
    differentiation_key: str,
    direction: str,
) -> CategorySlotDirector:
    return CategorySlotDirector(
        slot=slot,
        role_id=role_id,
        purpose=purpose,
        evidence=evidence,
        fact_channels=fact_channels,
        review_checks=review_checks,
        differentiation_key=differentiation_key,
        direction=direction,
    )


_PROFILES = {
    "apparel": CategoryProfile(
        category_id="apparel",
        display_name="Apparel, shoes, and bags",
        buyer_questions=(
            "What is the complete silhouette and fit?",
            "What does the construction look like from the relevant angle?",
            "What material, pattern, or hardware detail matters?",
            "How does it look in a truthful wear context?",
        ),
        required_evidence=("fit and silhouette", "front/back/side visibility", "material or texture", "wear context"),
        optional_evidence=("styling combination", "size guidance"),
        default_slot_priority=(
            "main_image",
            "feature_image_1",
            "feature_image_2",
            "detail_image",
            "scenario_image",
            "size_spec_image",
            "trust_comparison_image",
        ),
        human_presence_policy="Use an adult model only when fit or wear proof is needed; the garment must remain visible and dominant.",
        text_roles=("size_spec_image", "trust_comparison_image"),
        product_truth_fields=("silhouette", "color_or_pattern", "construction", "material", "size_or_fit", "included_pieces"),
        review_checks=("preserve garment construction", "keep human proportions natural", "show fit evidence when requested"),
        slot_directors=(
            _director("main_image", "apparel_primary_silhouette", "Show the complete product silhouette for the listing decision.", ("fit and silhouette",), ("product",), ("complete garment remains unoccluded",), "full_silhouette", "Show the complete garment in its supplied reference silhouette, color, pattern scale, and construction; do not substitute a generic garment."),
            _director("feature_image_1", "apparel_worn_front_fit", "Prove the front fit and visible construction.", ("fit and silhouette", "front/back/side visibility"), ("product", "construction"), ("front construction and drape remain visible",), "worn_front_fit", "Show an honest front worn view that makes fit, silhouette, and the supplied front construction clear without hiding the garment behind props."),
            _director("feature_image_2", "apparel_back_or_side_construction", "Prove a distinct back or side construction view.", ("front/back/side visibility",), ("construction", "product"), ("do not invent hidden construction",), "back_or_side_construction", "Show a distinct back or side construction view when that construction is supported by supplied evidence; otherwise use a distinct truthful angle and do not invent garment details."),
            _director("detail_image", "apparel_material_or_embroidery_detail", "Make one textile, stitch, embroidery, or hardware detail legible.", ("material or texture",), ("material", "construction"), ("pattern scale and finish remain accurate",), "material_detail", "Show a close, correctly located textile, stitching, embroidery, or hardware detail while preserving the supplied pattern scale and finish."),
            _director("scenario_image", "apparel_real_wear_context", "Show truthful real-wear context without losing product identification.", ("wear context",), ("product", "construction"), ("garment remains identifiable in context",), "wear_context", "Show a believable adult wear context with natural posture and styling, while keeping the garment visibly identifiable and fit-relevant."),
            _director("size_spec_image", "apparel_fit_or_size_evidence", "Clarify supplied fit, measurement, or relative-scale evidence.", ("size guidance",), ("product", "copy"), ("never invent a size chart or measurements",), "fit_or_size", "Use supplied size facts only; without confirmed measurements, show fit or relative-scale evidence and do not invent a size chart."),
            _director("trust_comparison_image", "apparel_styling_versatility", "Show a distinct truthful styling alternative, not an unsupported comparison.", ("styling combination",), ("product",), ("no performance, certification, or comparison claim",), "styling_alternative", "Show distinct, truthful styling alternatives using the same garment; do not imply a performance, certification, or comparison claim."),
        ),
    ),
    "beauty": CategoryProfile(
        category_id="beauty",
        display_name="Beauty and skincare",
        buyer_questions=(
            "What exactly is the package and applicator?",
            "What texture or application action is actually supported?",
            "Where does it fit in a truthful routine?",
            "Which ingredient or benefit facts are explicitly supplied?",
        ),
        required_evidence=("package identity", "texture or application", "usage context"),
        optional_evidence=("routine scene", "ingredient or benefit proof when supplied"),
        default_slot_priority=("main_image", "feature_image_1", "feature_image_2", "detail_image", "scenario_image", "size_spec_image", "trust_image"),
        human_presence_policy="Hands or a face may demonstrate a supported application action; do not imply efficacy, medical treatment, or a before/after result.",
        text_roles=("size_spec_image", "trust_image"),
        product_truth_fields=("package", "applicator", "texture", "volume", "confirmed_ingredients", "confirmed_use_boundary"),
        review_checks=("preserve package and label", "do not invent ingredients or medical claims", "keep effect claims evidence-backed"),
        slot_directors=(
            _director("main_image", "beauty_package_identity", "Make the actual package and applicator immediately identifiable.", ("package identity",), ("package", "product"), ("package shape, closure, and visible label match evidence",), "package_identity", "Show the actual package as sold, including its supported applicator or closure, without fabricating label text."),
            _director("feature_image_1", "beauty_texture_or_application", "Show supported texture or one truthful application action.", ("texture or application",), ("material", "product"), ("no implied efficacy result",), "texture_or_application", "Show a reference-supported texture or restrained application action; do not turn the image into a treatment, medical, or before-and-after claim."),
            _director("feature_image_2", "beauty_use_boundary", "Clarify the supported routine position or use boundary.", ("usage context",), ("product", "copy"), ("routine context does not add an unsupported benefit",), "routine_boundary", "Show one believable routine context that explains use without inventing a skin outcome, ingredient, or performance result."),
            _director("detail_image", "beauty_package_detail", "Make a package, pump, cap, or visible formula detail inspectable.", ("package identity",), ("package", "material"), ("visible copy is preserved, not regenerated",), "package_or_applicator_detail", "Show a close package, pump, cap, or supported formula detail while preserving visible design and avoiding fabricated legible copy."),
            _director("scenario_image", "beauty_routine_context", "Place the product in a believable routine environment.", ("usage context",), ("product",), ("product remains identifiable; no result claim",), "routine_scene", "Show a calm, believable routine context with the product identifiable and no implied medical or efficacy outcome."),
            _director("size_spec_image", "beauty_volume_or_scale", "Clarify supplied volume or relative package scale.", ("package identity",), ("package", "copy"), ("volume appears only when supplied",), "volume_or_scale", "Use only supplied volume or scale facts; otherwise show relative package scale and do not invent quantity text."),
            _director("trust_image", "beauty_confirmed_formula_fact", "Present one confirmed formula, package, or use fact conservatively.", ("ingredient or benefit proof when supplied",), ("package", "copy"), ("ingredient and benefit claims need supplied evidence",), "confirmed_formula_fact", "Use only a supplied, reviewable formula or use fact; do not invent certifications, ingredient percentages, or efficacy promises."),
        ),
    ),
    "electronics": CategoryProfile(
        category_id="electronics",
        display_name="Electronics and 3C",
        buyer_questions=(
            "What are the physical shape, controls, and ports?",
            "What is included in the box?",
            "How large is it in a real setup?",
            "Which specification or compatibility fact is actually supplied?",
        ),
        required_evidence=("product silhouette", "ports or functional structure", "scale", "real-use context"),
        optional_evidence=("included accessories", "compatibility or specification proof"),
        default_slot_priority=("main_image", "feature_image_1", "feature_image_2", "detail_image", "size_spec_image", "scenario_image", "trust_image"),
        human_presence_policy="Hands may establish scale or normal operation; do not depict unsupported safety, performance, connectivity, or compatibility outcomes.",
        text_roles=("size_spec_image", "trust_image"),
        product_truth_fields=("silhouette", "ports_and_controls", "dimensions", "included_items", "connector_layout", "confirmed_specs"),
        review_checks=("preserve ports and controls", "do not invent accessories", "do not alter logo or connector layout"),
        slot_directors=(
            _director("main_image", "electronics_product_silhouette", "Show the complete device and its sold form factor.", ("product silhouette",), ("product",), ("device remains complete and recognizable",), "complete_device", "Show the complete device in its supplied silhouette and finish, with controls and logo placement kept accurate."),
            _director("feature_image_1", "electronics_ports_or_controls", "Make one supplied port, control, or functional structure legible.", ("ports or functional structure",), ("construction", "product"), ("connector and control layout match evidence",), "ports_or_controls", "Show one supplied port, control, or functional structure clearly; do not invent an interface, connector, or operating state."),
            _director("feature_image_2", "electronics_included_items", "Differentiate the set by showing confirmed included items or a second truthful angle.", ("included accessories",), ("product", "package"), ("only confirmed accessories appear",), "included_items_or_angle", "Show confirmed in-box items when supplied; otherwise use a distinct truthful angle without adding accessories or compatibility claims."),
            _director("detail_image", "electronics_component_detail", "Inspect a component, finish, button, or port detail.", ("ports or functional structure",), ("construction", "material"), ("component geometry remains accurate",), "component_detail", "Show a close component, finish, button, or port detail with correct geometry and no fabricated interface text."),
            _director("scenario_image", "electronics_real_use_context", "Place the device in a believable supported use context.", ("real-use context",), ("product",), ("context does not imply unsupported performance",), "use_context", "Show a believable everyday use context that keeps the device identifiable and does not imply unsupplied performance, compatibility, or safety results."),
            _director("size_spec_image", "electronics_scale_or_dimensions", "Clarify supplied dimensions, connector compatibility, or relative scale.", ("scale",), ("product", "copy"), ("measurements and compatibility remain supplied",), "scale_or_dimensions", "Use only supplied dimensions or compatibility facts; otherwise show relative scale and do not invent measurements or supported-device lists."),
            _director("trust_image", "electronics_verified_specification", "Present one conservative, supplied specification or package fact.", ("compatibility or specification proof",), ("product", "copy"), ("specification requires a supplied source",), "verified_specification", "Use one supplied specification, included-item, or package fact only; do not invent certifications, benchmark results, or compatibility claims."),
        ),
    ),
    "home_kitchen": CategoryProfile(
        category_id="home_kitchen",
        display_name="Home and kitchen",
        buyer_questions=(
            "What is the form, material, and finish?",
            "How does it fit in the relevant space?",
            "What practical function does it demonstrate?",
            "Are capacity, quantity, cleaning, or storage facts confirmed?",
        ),
        required_evidence=("size and space fit", "material", "function"),
        optional_evidence=("capacity or quantity when confirmed", "cleaning or storage", "before/after only when truthful"),
        default_slot_priority=("main_image", "feature_image_1", "feature_image_2", "scenario_image", "detail_image", "size_spec_image", "trust_image"),
        human_presence_policy="Use hands or a person only to establish normal, safe, believable use or room scale; do not imply safety, performance, or capacity claims.",
        text_roles=("size_spec_image", "trust_image"),
        product_truth_fields=("form", "material", "finish", "dimensions", "capacity_if_confirmed", "included_parts", "supported_function"),
        review_checks=("preserve material and structure", "do not invent capacity", "keep use scene practical and believable"),
        slot_directors=(
            _director("main_image", "home_form_and_material", "Show the complete form and material finish.", ("material",), ("product", "material"), ("structure and finish remain accurate",), "form_and_material", "Show the complete product form and supplied material finish clearly, without adding a function or capacity assertion."),
            _director("feature_image_1", "home_supported_function", "Demonstrate one supported practical function.", ("function",), ("product", "construction"), ("function is visible and believable",), "practical_function", "Demonstrate one supplied practical function with the product visible; do not imply unsupported performance, safety, or capacity."),
            _director("feature_image_2", "home_space_fit", "Show a distinct room, counter, shelf, or desk fit proof.", ("size and space fit",), ("product",), ("scale remains believable",), "space_fit", "Show the product in a believable relevant space to clarify its footprint and fit without inventing dimensions."),
            _director("detail_image", "home_material_or_construction_detail", "Inspect material, assembly, or finish detail.", ("material",), ("material", "construction"), ("detail matches supplied finish",), "material_or_construction_detail", "Show a close material, assembly, or finish detail while preserving the supplied texture, color, and structural relationship."),
            _director("scenario_image", "home_real_use_context", "Show normal, practical real-use context.", ("function",), ("product",), ("no staged impossible use or safety claim",), "real_use_context", "Show a practical everyday use context with believable scale and no implied safety, performance, or before-and-after result."),
            _director("size_spec_image", "home_scale_or_capacity", "Clarify supplied size, capacity, or quantity only when confirmed.", ("size and space fit",), ("product", "copy"), ("capacity and measurements remain supplied",), "scale_or_confirmed_capacity", "Use supplied dimensions, capacity, or quantity only; otherwise show relative scale and do not invent numbers or storage volume."),
            _director("trust_image", "home_cleaning_or_storage_fact", "Present one supplied cleaning, storage, or included-part fact.", ("cleaning or storage",), ("product", "copy"), ("no unsupported durability or safety claim",), "cleaning_or_storage_fact", "Use only a supplied cleaning, storage, or included-part fact; do not invent durability tests, safety certifications, or before-and-after claims."),
        ),
    ),
    "food_beverage": CategoryProfile(
        category_id="food_beverage",
        display_name="Food and beverage",
        buyer_questions=(
            "What package, label, and count are actually sold?",
            "What does the supplied serving or contents look like?",
            "How much is included or what is the relative portion?",
            "Which ingredient facts are explicitly supplied?",
        ),
        required_evidence=("package identity", "serving or contents", "portion or scale", "consumption context"),
        optional_evidence=("ingredient detail when supplied", "gift or bundle presentation"),
        default_slot_priority=("main_image", "feature_image_1", "feature_image_2", "scenario_image", "detail_image", "size_spec_image", "trust_image"),
        human_presence_policy="Hands or people may establish a normal consumption context; never imply health, nutrition, taste, or serving claims that are not supplied.",
        text_roles=("size_spec_image", "trust_image"),
        product_truth_fields=("package", "label", "package_count", "portion_or_volume", "supplied_ingredients", "serving_context"),
        review_checks=("preserve label and package count", "do not invent ingredients", "avoid unsupported health claims"),
        slot_directors=(
            _director("main_image", "food_package_identity", "Make the package, label design, and sold form identifiable.", ("package identity",), ("package", "product"), ("package count and visible label design match evidence",), "package_identity", "Show the actual package as sold with its supplied shape, count, and visible label design; do not fabricate readable label copy."),
            _director("feature_image_1", "food_serving_or_contents", "Show supplied serving appearance or contents truthfully.", ("serving or contents",), ("product", "material"), ("contents do not add unsupplied ingredients",), "serving_or_contents", "Show a truthful supplied serving or contents view without adding ingredients, garnishes, texture, or portion facts that are not supported."),
            _director("feature_image_2", "food_portion_or_quantity", "Clarify the sold portion, pack count, or relative scale.", ("portion or scale",), ("package", "product"), ("portion and count remain supported",), "portion_or_quantity", "Show supplied pack count, portion, or relative scale truthfully; do not invent net weight, serving count, or bundle contents."),
            _director("detail_image", "food_package_or_ingredient_detail", "Inspect a supported package, ingredient, or contents detail.", ("ingredient detail when supplied",), ("package", "material"), ("ingredient details require supplied evidence",), "package_or_ingredient_detail", "Show a close package or supplied ingredient/contents detail while preserving visible design and never inventing ingredient, nutrition, or health information."),
            _director("scenario_image", "food_consumption_context", "Place the product in a normal, believable consumption moment.", ("consumption context",), ("product",), ("context does not imply health or taste result",), "consumption_context", "Show a believable consumption context that keeps the product identifiable and does not imply an unsupplied taste, nutrition, or health outcome."),
            _director("size_spec_image", "food_portion_scale", "Clarify supplied portion, volume, or relative package scale.", ("portion or scale",), ("package", "copy"), ("quantity facts remain supplied",), "portion_or_volume", "Use supplied portion, volume, or package-count facts only; otherwise show relative scale and do not invent numbers."),
            _director("trust_image", "food_supplied_ingredient_fact", "Present one supplied ingredient, package, or bundle fact conservatively.", ("ingredient detail when supplied",), ("package", "copy"), ("no nutrition, health, or certification inference",), "supplied_ingredient_fact", "Use only a supplied ingredient, package-count, or bundle fact; do not invent nutrition, health, certification, or provenance claims."),
        ),
    ),
}

# Shoes and bags share first-wave evidence coverage with apparel, but they must
# never inherit a garment-on-model or garment-construction director.
_ACCESSORY_SLOT_DIRECTORS = (
    _director("main_image", "accessory_primary_form", "Show the complete shoe or bag form for the listing decision.", ("fit and silhouette",), ("product",), ("complete accessory remains unoccluded",), "accessory_full_form", "Show the actual shoe or bag in its supplied form, color, material, and visible construction; do not substitute a generic accessory."),
    _director("feature_image_1", "accessory_front_or_opening", "Prove the relevant front, opening, closure, or wearing-side view.", ("front/back/side visibility",), ("product", "construction"), ("closure and opening geometry remain accurate",), "accessory_front_or_opening", "Show the relevant front, opening, closure, or wearing-side view clearly without applying clothing-fit or model-pose guidance."),
    _director("feature_image_2", "accessory_back_or_side", "Prove a distinct back, sole, side, or carrying-side view.", ("front/back/side visibility",), ("product", "construction"), ("distinct angle reveals supported construction",), "accessory_back_or_side", "Show a distinct back, sole, side, or carrying-side view supported by the reference; do not invent pockets, straps, hardware, or tread."),
    _director("detail_image", "accessory_material_or_hardware", "Inspect supplied material, stitching, hardware, or sole detail.", ("material or texture",), ("material", "construction"), ("material texture and hardware placement remain accurate",), "accessory_material_or_hardware", "Show a close material, stitching, hardware, or sole detail with correct location, texture, and finish."),
    _director("scenario_image", "accessory_real_use_context", "Establish carrying, on-foot, or relative-scale context without a clothing pose.", ("wear context",), ("product",), ("accessory remains central and identifiable",), "accessory_use_context", "Show a believable carrying, on-foot, or relative-scale context while keeping the shoe or bag central; do not apply clothing-fit or fashion-pose guidance."),
    _director("size_spec_image", "accessory_scale_or_size", "Clarify supplied dimensions, capacity, shoe-size, or relative scale.", ("size guidance",), ("product", "copy"), ("no invented dimensions, volume, or size chart",), "accessory_scale_or_size", "Use supplied dimensions, capacity, or size facts only; otherwise show relative scale and do not invent a chart or quantity."),
    _director("trust_comparison_image", "accessory_styling_or_function_fact", "Show a distinct supported styling or construction fact without an unsupported comparison.", ("styling combination",), ("product", "copy"), ("no performance, certification, or comparison claim",), "accessory_styling_or_function_fact", "Show one distinct supported styling or construction fact while avoiding unsupported comparison, certification, or performance claims."),
)


_ALIASES = {
    "clothing": "apparel", "fashion": "apparel", "shoes": "apparel", "bag": "apparel", "bags": "apparel", "shirt": "apparel",
    "skincare": "beauty", "cosmetics": "beauty", "makeup": "beauty", "serum": "beauty", "cream": "beauty",
    "3c": "electronics", "electronic": "electronics", "headphones": "electronics", "earbuds": "electronics",
    "keyboard": "electronics", "phone": "electronics", "tablet": "electronics", "computer": "electronics",
    "home": "home_kitchen", "kitchen": "home_kitchen", "furniture": "home_kitchen", "lamp": "home_kitchen",
    "lighting": "home_kitchen", "organizer": "home_kitchen", "storage": "home_kitchen",
    "drink": "food_beverage", "beverage": "food_beverage", "food": "food_beverage", "tea": "food_beverage",
    "coffee": "food_beverage", "juice": "food_beverage", "snack": "food_beverage", "soda": "food_beverage",
}

_SLOT_ALIASES = {
    "hero_image": "main_image",
    "benefit_image": "feature_image_1",
    "benefit_hook": "feature_image_1",
    "trust_comparison_image": "trust_image",
}

_APPAREL_EXCLUSIONS = ("shoe", "sneaker", "boot", "sandal", "bag", "handbag", "backpack", "luggage")


def resolve_category(product_category: str | None, *, user_input: str = "") -> CategoryProfile | None:
    raw = " ".join([str(product_category or ""), str(user_input or "")]).strip().lower()
    normalized = raw.replace("-", "_").replace("/", " ")
    for category_id, profile in _PROFILES.items():
        if category_id in normalized:
            return profile
    for alias, category_id in _ALIASES.items():
        if alias in normalized:
            return _PROFILES[category_id]
    return None


def list_category_profiles() -> tuple[CategoryProfile, ...]:
    return tuple(_PROFILES.values())


def category_slot_director_for(
    profile: CategoryProfile | None,
    slot: str,
    *,
    product_category: str = "",
) -> dict[str, object]:
    """Return a data-owned category director without changing shared runtime behavior."""

    empty: dict[str, object] = {
        "id": "",
        "purpose": "",
        "evidence": [],
        "fact_channels": [],
        "review_checks": [],
        "differentiation_key": "",
        "direction": "",
    }
    if profile is None:
        return empty
    if profile.category_id == "apparel" and any(token in product_category.lower() for token in _APPAREL_EXCLUSIONS):
        director = next((item for item in _ACCESSORY_SLOT_DIRECTORS if item.slot == slot), None)
        if director is None:
            resolved_slot = _SLOT_ALIASES.get(slot, slot)
            director = next((item for item in _ACCESSORY_SLOT_DIRECTORS if item.slot == resolved_slot), None)
        return director.metadata() if director else empty
    director = next((item for item in profile.slot_directors if item.slot == slot), None)
    if director is None:
        resolved_slot = _SLOT_ALIASES.get(slot, slot)
        director = next((item for item in profile.slot_directors if item.slot == resolved_slot), None)
    return director.metadata() if director else empty


def evidence_for_slot(profile: CategoryProfile | None, slot: str, *, product_category: str = "") -> tuple[str, ...]:
    return tuple(category_slot_director_for(profile, slot, product_category=product_category)["evidence"])


def slot_guidance_for(
    profile: CategoryProfile | None,
    slot: str,
    *,
    product_category: str = "",
) -> dict[str, str]:
    director = category_slot_director_for(profile, slot, product_category=product_category)
    return {"id": str(director["id"]), "direction": str(director["direction"])}
