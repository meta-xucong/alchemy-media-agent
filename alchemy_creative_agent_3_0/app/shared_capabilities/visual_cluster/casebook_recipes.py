"""Doc68 V3-owned casebook recipe fragments for the visual cluster.

The recipe library distills V2/GPT-Image-2 prompt experience into compact
provider-facing atoms. It is a helper used by existing visual modules, not a
second visual runtime.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


VISUAL_CASEBOOK_RECIPE_LIBRARY_ID = "visual_casebook_recipe_library"
VISUAL_PROMPT_ATOM_RECIPE_ID = "visual_prompt_atom_recipe"
VISUAL_HUMAN_REAL_CAMERA_TUNING_ID = "human_real_camera_ai_feel_tuning"
VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID = "human_attractive_realism_balance_tuning"
VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID = "human_east_asian_fair_complexion_guard"


def human_photorealism_casebook(
    *,
    variation_mode: str,
    realism_level: str,
    has_identity_reference: bool,
) -> dict[str, Any]:
    """Return Doc68 human-photo recipe atoms for the existing realism layer."""

    mode = _canonical_mode(variation_mode)
    positive = [
        "photographed skin with visible fine pores, uneven tonal transitions, and light natural texture instead of a beauty-filter surface",
        "specific micro-expression with relaxed facial muscles, slight asymmetry, and a real shutter-moment feeling",
        "real eye moisture, catchlight placement, and eyelid detail without glassy synthetic highlights",
        "natural hairline with baby hairs, flyaway strands, imperfect parting, and believable strand depth",
        "camera perspective with real facial planes, lens falloff, and depth of field rather than a flat render mask",
        "real camera medium with mild lens softness, believable highlight roll-off, and a little physical imperfection when the style allows",
        "real fabric wrinkles, clothing drape, fine hair separation, and environment contact instead of a clean synthetic mannequin finish",
        "soft 35mm or CCD-inspired capture imperfection: fine grain, subtle halation, slight edge softness, and mild handheld framing imperfection",
        "skin tonal variation around nose, eyelids, under-eye area, neck, and shoulder; not one uniform beauty-app surface",
        "tiny human asymmetries, smile-line hints, and a candid mouth/eye tension that feels caught in one real frame",
        "professional retouching that preserves human texture and avoids plastic smoothing",
        "documentary-adjacent commercial portrait feeling: publishable and attractive, but not a studio-beauty or idol-card retouch",
        "natural individuality in face proportions, lip texture, eyelid folds, jaw contour, and cheek transitions instead of algorithmically perfect features",
        "one small real-world flaw may remain visible, such as a stray hair, slight squint, uneven smile corner, soft focus edge, or subtle skin redness",
        "bright daylight still preserves pore-level skin texture, eyelid folds, under-eye shadows, lip texture, and tiny neck/shoulder tonal changes",
        "quiet neutral expression or imperfect half-smile is preferred over a sweet template cover smile unless the user explicitly asks for a big smile",
        "healthy clear complexion and fresh bright skin tone created by flattering light, not by skin whitening or beauty-filter smoothing",
        "soft natural bounce light lifts facial shadows while preserving natural skin tone, ethnicity, and real texture",
        "clean high-key summer daylight with gentle cheek warmth, awake eyes, and natural lip color",
        "clean fair luminous complexion for East Asian fresh or summer beauty portraits when no tan, dark, or bronze look is requested",
        "bright translucent facial color from high-key daylight, exposure, and soft bounce light rather than whitening filters",
        "do not darken or tan East Asian skin by default; preserve natural East Asian identity and real skin texture",
        "natural head-to-body proportion, balanced neck and shoulder line, and flattering upper-body crop",
        "harmonious natural facial features, awake eyes, relaxed facial muscles, and a flattering real-camera face angle",
    ]
    negative = [
        "over-smoothed influencer face",
        "over-retouched fashion-doll face",
        "poreless beauty-surface face",
        "beauty-app face",
        "idol photocard polish",
        "skin-blur retouching",
        "flawless porcelain mask",
        "overly symmetrical V-line jaw",
        "auto face-slimming",
        "enlarged beauty-filter eyes",
        "perfect V-shaped chin",
        "flawless K-idol beauty retouch",
        "liquified face proportions",
        "algorithmically pretty generic face",
        "too-clean stock-photo model face",
        "uniform luminous skin",
        "dewy plastic makeup skin",
        "cosmetic-ad poreless glow",
        "bright sun erasing all face texture",
        "sweet K-idol template smile",
        "perfect cute influencer smile",
        "dull complexion",
        "muddy skin tone",
        "gray or green skin color cast",
        "underexposed face",
        "harsh facial shadow",
        "tired expression",
        "overly matte documentary look",
        "unflattering dark tan or bronze cast unless requested",
        "suppressed fair complexion",
        "unnecessarily darkened East Asian skin",
        "forced tan or bronze cast unless requested",
        "gray-brown skin cast",
        "dull yellow or green facial cast",
        "fake whitening mask",
        "bleached beauty-filter skin",
        "oversized head",
        "enlarged face scale",
        "short compressed neck",
        "compressed shoulders",
        "warped upper body",
        "pinched torso",
        "bad head-to-body ratio",
        "awkward shoulder crop",
        "unflattering face drift",
        "flattened facial attractiveness",
        "skin whitening filter",
        "beauty-app glow",
        "oversized anime-like eyes in a realistic photo",
        "same perfect smile repeated",
        "hyper-clean fashion render",
        "synthetic fashion editorial face with no lived-in detail",
        "single template smile repeated across the set",
        "identical face angle and identical gaze across multiple outputs",
        "plastic makeup sheen",
        "waxy cheek highlights",
        "digital oversharpening and glossy AI eyes",
        "synthetic glass eyes",
        "perfectly symmetrical doll face",
        "AI portrait filter look",
    ]
    preserve = [
        "preserve identity through stable face-shape direction, age impression, feature relationships, and body type; reference-channel policy separately owns hair and wardrobe",
        "keep identity consistent while treating each output as a different real camera frame, not a copied still",
    ]
    do_not_inherit = [
        "do not inherit airbrushed skin, generic AI beauty-face proportions, waxy highlights, or fake eye shine from the reference",
        "do not inherit the exact same frozen expression, head angle, pose, camera crop, or retouched mask from the reference",
    ]
    review_targets = [
        "face reads as photographed rather than generated",
        "skin texture remains visible after professional polish",
        "expression, gaze, head angle, or crop differs naturally across the set",
        "identity consistency is achieved without cloned stills",
        "camera, fabric, hair, and environmental details make the frame read as a real photograph",
        "portrait looks attractive but still grounded in a real camera capture, not a beauty-app render",
        "commercial finish reads as camera-ready realism rather than face-smoothing retouch",
        "face looks fresh, healthy, and flattering without losing real skin texture or natural skin tone",
        "East Asian fresh portraits keep clean fair luminous complexion unless a tan or darker look is explicitly requested",
        "close crops keep natural head, neck, shoulder, and upper-body proportions",
    ]

    if mode == "selection_candidates":
        positive.append(
            "create close alternatives as comparable real shutter moments with only small expression, gaze, mouth tension, hair movement, hand, crop, or head-angle differences"
        )
        review_targets.append("candidate options stay close but are not identical stills")
    elif mode == "delivery_suite":
        positive.append(
            "make the batch feel like a directed professional photoshoot with cover, close, angle, and context moments; not every frame should use the same direct beauty smile"
        )
        review_targets.append("delivery-suite roles differ by photographic duty")
    elif mode == "creative_exploration":
        positive.append(
            "preserve recognizable identity while exploring a stronger lens, mood, scene, wardrobe nuance, or art-direction lane"
        )
        review_targets.append("creative distance is intentional rather than random identity drift")
    elif mode == "format_layout_adaptation":
        positive.append(
            "adapt crop and safe area while keeping natural face scale, same identity direction, and believable body proportions"
        )
        review_targets.append("layout changes do not become identity or styling drift")

    if has_identity_reference:
        preserve.append("use the selected image as identity truth while allowing expression, pose, camera, and crop variation")
        do_not_inherit.append("reference image is an identity anchor, not an instruction to clone its exact still")

    return {
        "recipe_library": VISUAL_CASEBOOK_RECIPE_LIBRARY_ID,
        "prompt_atom_recipe_library": VISUAL_PROMPT_ATOM_RECIPE_ID,
        "human_real_camera_tuning_library": VISUAL_HUMAN_REAL_CAMERA_TUNING_ID,
        "human_attractive_realism_balance_library": VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID,
        "human_east_asian_fair_complexion_guard_library": VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID,
        "mode": mode,
        "realism_level": realism_level,
        "positive_prompt_fragments": positive,
        "negative_prompt_fragments": negative,
        "reference_preserve_rules": preserve,
        "reference_do_not_inherit_rules": do_not_inherit,
        "review_targets": review_targets,
        "retry_patch_templates": {
            "prompt_additions": positive[:5],
            "negative_additions": negative,
            "artifact_repair": [
                "repair toward real photographed skin texture, specific micro-expression, natural eyes, true hairline detail, and non-plastic light response",
                "repair toward healthy clear complexion with soft natural bounce light, clean bright daylight, gentle cheek warmth, and natural skin tone preserved",
                "repair toward clean fair luminous complexion for East Asian fresh portraits through exposure, color balance, and soft bounce light; do not use fake whitening or skin smoothing",
                "repair close portrait crops so head-to-body, neck, shoulder, and upper-body proportions look natural and flattering",
            ],
            "identity_reinforcement": preserve,
        },
    }


def prompt_atom_recipe(
    *,
    mode: str,
    subject_type: str,
    role_key: str = "",
    index: int = 1,
) -> dict[str, Any]:
    """Return Doc69 prompt atom stacks for an existing role recipe."""

    normalized_mode = _canonical_mode(mode)
    normalized_subject = _normalize_subject_type(subject_type)
    if normalized_subject == "character":
        return _portrait_prompt_atom_recipe(mode=normalized_mode, role_key=role_key, index=index)
    if normalized_subject == "product":
        return _product_prompt_atom_recipe(mode=normalized_mode, role_key=role_key, index=index)
    return _generic_prompt_atom_recipe(mode=normalized_mode, role_key=role_key, index=index)


def apply_role_recipe_casebook_overlay(
    recipe: dict[str, Any],
    *,
    mode: str,
    subject_type: str,
    index: int,
) -> dict[str, Any]:
    """Merge Doc68 casebook atoms into an existing mode-role recipe."""

    result = deepcopy(recipe)
    normalized_mode = _canonical_mode(mode)
    normalized_subject = _normalize_subject_type(subject_type)
    role_key = str(result.get("role_key") or "")
    overlay = _role_overlay(
        mode=normalized_mode,
        subject_type=normalized_subject,
        role_key=role_key,
        index=index,
    )
    atom_overlay = prompt_atom_recipe(
        mode=normalized_mode,
        subject_type=normalized_subject,
        role_key=role_key,
        index=index,
    )
    if not overlay:
        return result

    result["prompt_pressure"] = _join_sentences(
        result.get("prompt_pressure"),
        overlay.get("prompt_pressure"),
        atom_overlay.get("prompt_pressure"),
    )
    result["variation_axes"] = _dedupe(
        [
            *_string_list(result.get("variation_axes")),
            *_string_list(overlay.get("variation_axes")),
            *_string_list(atom_overlay.get("variation_axes")),
        ]
    )
    result["must_keep_rules"] = _dedupe(
        [
            *_string_list(result.get("must_keep_rules")),
            *_string_list(overlay.get("must_keep_rules")),
            *_string_list(atom_overlay.get("must_keep_rules")),
        ]
    )
    result["must_not_rules"] = _dedupe(
        [
            *_string_list(result.get("must_not_rules")),
            *_string_list(overlay.get("must_not_rules")),
            *_string_list(atom_overlay.get("must_not_rules")),
        ]
    )
    result["negative_pressure"] = _dedupe(
        [
            *_string_list(result.get("negative_pressure")),
            *_string_list(overlay.get("negative_pressure")),
            *_string_list(atom_overlay.get("negative_pressure")),
        ]
    )
    result["review_checks"] = _dedupe(
        [
            *_string_list(result.get("review_checks")),
            *_string_list(overlay.get("review_checks")),
            *_string_list(atom_overlay.get("review_checks")),
        ]
    )
    metadata = dict(result.get("metadata") or {})
    metadata.update(
        {
            "doc68_casebook_recipe": True,
            "casebook_recipe_library": VISUAL_CASEBOOK_RECIPE_LIBRARY_ID,
            "casebook_subject_type": normalized_subject,
            "casebook_mode": normalized_mode,
            **dict(overlay.get("metadata") or {}),
            **dict(atom_overlay.get("metadata") or {}),
        }
    )
    result["metadata"] = metadata
    return result


def strong_reference_casebook_rules(subject_type: str) -> dict[str, list[str]]:
    """Return extra Doc68 strong-reference rules without replacing Doc66."""

    normalized_subject = _normalize_subject_type(subject_type)
    if normalized_subject == "character":
        return {
            "allowed_variations": [
                "vary expression, gaze, head angle, body turn, hand placement, crop, and camera distance like a real photoshoot",
                "allow prompt-directed hair movement, parting, volume, and styling variation without treating source hair as identity truth",
            ],
            "forbidden_drift": [
                "same frozen face copied from the reference",
                "beauty-filter identity replacement",
                "loss of age impression, body type, or broad face shape",
            ],
            "provider_prompt_rules": [
                "Treat the selected person as identity truth, but direct the next frame as a new photographed moment with natural variation.",
                "Keep identity through stable traits, not through repeated expression, repeated gaze, or repeated camera crop.",
            ],
        }
    if normalized_subject == "product":
        return {
            "allowed_variations": [
                "vary surface, camera angle, environment depth, lifestyle context, and crop while preserving product truth",
                "allow a real use-context scene when the role calls for lifestyle or scenario coverage",
            ],
            "forbidden_drift": [
                "new unrelated product identity",
                "rewritten product label or logo",
                "studio-only repetition when a lifestyle/context role is requested",
            ],
            "provider_prompt_rules": [
                "Treat the selected product as product truth, but vary scene and image duty according to the role.",
                "For lifestyle roles, use a lived-in or real-use context while keeping label/logo details readable when visible.",
            ],
        }
    return {
        "allowed_variations": ["vary crop, angle, scene depth, and presentation while keeping the selected visual world"],
        "forbidden_drift": ["unrelated subject direction", "random style jump", "copied still with no useful variation"],
        "provider_prompt_rules": ["Use the selected reference as visual truth while creating a new complete frame."],
    }


def provider_casebook_prompt_lines(role_recipe: dict[str, Any]) -> list[str]:
    """Render recipe metadata into compact provider prompt lines."""

    metadata = role_recipe.get("metadata") if isinstance(role_recipe.get("metadata"), dict) else {}
    if not metadata.get("doc68_casebook_recipe"):
        return []
    lines: list[str] = []
    for label, key in [
        ("Casebook camera recipe", "casebook_camera_recipe"),
        ("Casebook realism recipe", "casebook_realism_recipe"),
        ("Casebook product recipe", "casebook_product_recipe"),
        ("Casebook role difference", "casebook_role_difference"),
    ]:
        value = str(metadata.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    review_targets = _string_list(metadata.get("casebook_review_targets"))
    if review_targets:
        lines.append("Casebook review target: " + "; ".join(review_targets[:4]))
    atom_lines = _provider_prompt_atom_lines(metadata)
    lines.extend(atom_lines)
    return lines[:10]


def _provider_prompt_atom_lines(metadata: dict[str, Any]) -> list[str]:
    if not metadata.get("doc69_prompt_atom_recipe"):
        return []
    lines: list[str] = []
    camera = _string_list(metadata.get("prompt_atom_camera_stack"))
    light = _string_list(metadata.get("prompt_atom_light_stack"))
    texture = _string_list(metadata.get("prompt_atom_texture_stack"))
    reference = _string_list(metadata.get("prompt_atom_reference_guard"))
    product = _string_list(metadata.get("prompt_atom_product_truth_guard"))
    negative = _string_list(metadata.get("prompt_atom_negative_guard"))
    review = _string_list(metadata.get("prompt_atom_review_targets"))
    if camera:
        lines.append("Prompt atom camera stack: " + "; ".join(camera[:4]))
    if light or texture:
        lines.append("Prompt atom light/texture stack: " + "; ".join([*light[:2], *texture[:3]]))
    if reference:
        lines.append("Prompt atom reference guard: " + "; ".join(reference[:3]))
    if product:
        lines.append("Prompt atom product truth: " + "; ".join(product[:3]))
    if negative:
        lines.append("Prompt atom negative guard: " + "; ".join(negative[:5]))
    if review:
        lines.append("Prompt atom review target: " + "; ".join(review[:4]))
    return lines[:6]


def _portrait_prompt_atom_recipe(*, mode: str, role_key: str, index: int) -> dict[str, Any]:
    camera = [
        "soft 35mm or CCD-inspired real-camera imperfection with fine grain, slight edge softness, and mild candid framing",
        "real lens perspective with natural face planes and believable depth falloff",
        "specific shutter moment rather than a rendered beauty mask",
        _portrait_camera_atom(mode=mode, role_key=role_key, index=index),
    ]
    light = [
        "subtle halation or highlight bloom that feels optical, not glossy AI shine",
        "clear light source direction with soft highlight roll-off",
        "natural skin response to light, not waxy cheek shine",
        "soft natural bounce light lifts the face and keeps skin clean, bright, and healthy without flattening texture",
        "high-key summer daylight stays fresh and flattering while avoiding overexposure or a gray color cast",
        "clean fair luminous complexion is preserved for East Asian fresh portrait styling unless a tan, dark, or bronze look is requested",
        "soft bounce light and color balance lift the face without fake whitening or skin smoothing",
    ]
    texture = [
        "skin tone variation around eyelids, under-eye area, nose, neck, and shoulders",
        "visible fine pores and non-uniform cheek texture",
        "small smile-line hints, natural mouth tension, and tiny facial asymmetries",
        "under-eye detail, real eye moisture, and non-glassy catchlights",
        "hairline detail, flyaways, fabric wrinkles, and clothing drape",
        "individual facial character: natural jaw contour, real eyelid folds, lip texture, and slight non-identical cheek transitions",
        "publishable documentary-commercial polish without beauty-app smoothing or face-shape liquify",
        "bright outdoor light keeps real under-eye detail, lip texture, skin pores, and small shoulder/neck tone differences",
        "healthy clear complexion, gentle cheek warmth, natural lip color, and awake eyes while preserving natural skin tone",
        "natural head-to-body ratio, balanced neck and shoulder line, and flattering upper-body crop",
        "harmonious natural features with awake eyes and relaxed facial muscles, not a face reshaped by beauty filters",
    ]
    reference = [
        "preserve broad face shape, age direction, body type, hair family, and feature relationships",
        "allow expression, gaze, pose, crop, camera distance, and small hair-styling variation",
        "identity consistency must come from stable traits, not cloned stills",
    ]
    negative = [
        "over-retouched fashion-doll face",
        "beauty-app face",
        "idol photocard polish",
        "skin-blur retouching",
        "flawless porcelain mask",
        "overly symmetrical V-line jaw",
        "same perfect smile repeated",
        "auto face-slimming",
        "enlarged beauty-filter eyes",
        "perfect V-shaped chin",
        "flawless K-idol beauty retouch",
        "liquified face proportions",
        "algorithmically pretty generic face",
        "too-clean stock-photo model face",
        "uniform luminous skin",
        "dewy plastic makeup skin",
        "cosmetic-ad poreless glow",
        "bright sun erasing all face texture",
        "dull complexion",
        "muddy skin tone",
        "gray or green skin color cast",
        "underexposed face",
        "harsh facial shadow",
        "tired expression",
        "overly matte documentary look",
        "suppressed fair complexion",
        "unnecessarily darkened East Asian skin",
        "forced tan or bronze cast unless requested",
        "gray-brown skin cast",
        "dull yellow or green facial cast",
        "oversized head",
        "enlarged face scale",
        "short compressed neck",
        "compressed shoulders",
        "bad head-to-body ratio",
        "awkward shoulder crop",
        "unflattering face drift",
        "skin whitening filter",
        "beauty-app glow",
        "poreless beauty-surface face",
        "synthetic influencer face",
        "plastic skin",
        "same exact expression or head angle repeated",
        "digital oversharpening",
    ]
    review = [
        "same person direction without cloned expression",
        "real-photo skin, hair, fabric, and light behavior",
        "real-camera imperfection is visible without making the photo look low quality",
        "face remains attractive but not beauty-app perfect",
        "polish is interpreted as camera-ready craft, not retouched skin or beautified facial geometry",
        "attractiveness comes from flattering real light and fresh color, not whitening or smoothing filters",
        "East Asian fair luminous complexion is protected without fake whitening",
        "head, neck, shoulder, and upper-body proportions stay natural in close crops",
        "camera/pose/face angle serves this role",
        "not a generic AI beauty portrait",
    ]
    prompt = (
        "Use a real-photo portrait atom stack: lens, light, skin, hair, fabric, and environment details must make this feel photographed. "
        "Real-camera imperfection should win over beauty-app polish, while identity is preserved through stable traits and each output keeps a natural new-frame variation. "
        "If the brief asks for polished or commercial quality, interpret that as camera-ready documentary-commercial craft, not skin smoothing, face slimming, or idol-card retouch. "
        "Keep the face fresh and attractive with clean bounce light, healthy complexion, and natural skin tone preserved."
        " For East Asian fresh portrait styling, do not suppress fair luminous complexion unless the user requested tan, dark, or bronze skin."
        " Preserve natural head-to-body, neck, shoulder, and upper-body proportions in close crops."
    )
    overlay = _atom_overlay(
        prompt=prompt,
        camera=camera,
        light=light,
        texture=texture,
        reference=reference,
        negative=negative,
        review=review,
        axes=["camera medium", "light source", "skin texture", "hair detail", "micro-expression", "real-camera imperfection"],
    )
    overlay["metadata"].update(
        {
            "doc70_human_real_camera_tuning": True,
            "doc71_human_attractive_realism_balance": True,
            "doc72_east_asian_fair_complexion_guard": True,
            "human_real_camera_tuning_library": VISUAL_HUMAN_REAL_CAMERA_TUNING_ID,
            "human_attractive_realism_balance_library": VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID,
            "human_east_asian_fair_complexion_guard_library": VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID,
        }
    )
    return overlay


def _product_prompt_atom_recipe(*, mode: str, role_key: str, index: int) -> dict[str, Any]:
    camera = [
        "role-specific camera distance with inspectable product form",
        _product_camera_atom(mode=mode, role_key=role_key, index=index),
    ]
    light = [
        "controlled real-world light direction with material-specific highlight behavior",
        "avoid flat catalog lighting unless the user explicitly asks for a clean catalog frame",
    ]
    texture = [
        "material surface, edge shape, label area, finish, condensation, fabric, paper, glass, metal, or plastic cues as applicable",
        "supporting surfaces and props must feel tactile and real rather than decorative filler",
    ]
    product_truth = [
        "when a product reference is supplied, treat it as the one product truth",
        "preserve silhouette, proportions, material, edge shape, label/logo placement, and visible text shapes",
        "do not translate, rewrite, invent, blur, cover, crop, darken, or replace the visible label/logo",
    ]
    reference = [
        "vary scene, surface, camera, and role duty without changing product identity",
        "concept variation must support the same object rather than introduce a new object",
    ]
    negative = [
        "new unrelated product",
        "invented or rewritten label",
        "fake claim badge",
        "flat studio-only repetition when lifestyle/context is requested",
        "repeated prop concept across the whole set",
        "unreadable or obscured product truth",
    ]
    review = [
        "product truth remains inspectable",
        "role has a distinct image duty",
        "real-use context is believable when lifestyle/context frames are requested",
        "no fake label, watermark, or generated text",
    ]
    prompt = (
        "Use a product prompt atom stack: preserve the supplied product truth while changing only the role-specific scene, surface, light, "
        "camera distance, and use context needed for this image."
    )
    return _atom_overlay(
        prompt=prompt,
        camera=camera,
        light=light,
        texture=texture,
        reference=reference,
        negative=negative,
        review=review,
        axes=["camera distance", "surface", "material truth", "use context", "role duty"],
        product_truth=product_truth,
    )


def _generic_prompt_atom_recipe(*, mode: str, role_key: str, index: int) -> dict[str, Any]:
    camera = [
        "clear role-appropriate camera distance and framing",
        "coherent scene depth and subject scale",
    ]
    light = [
        "intentional light direction and contrast level",
        "consistent palette and atmosphere across the set",
    ]
    texture = [
        "physical surface cues that fit the requested visual direction",
        "complete single-frame image with no collage layout",
    ]
    reference = [
        "preserve the selected visual direction while changing only the requested role, crop, angle, or scene depth",
    ]
    negative = [
        "random subject drift",
        "same exact still repeated",
        "watermark",
        "new visible text",
    ]
    review = [
        "visual direction remains coherent",
        "role is clear",
        "frame is complete and usable",
    ]
    prompt = "Use a compact visual atom stack: camera, light, surface, role, and negative-space choices must serve one clear output duty."
    return _atom_overlay(
        prompt=prompt,
        camera=camera,
        light=light,
        texture=texture,
        reference=reference,
        negative=negative,
        review=review,
        axes=["camera", "light", "surface", "scene depth", "layout"],
    )


def _portrait_camera_atom(*, mode: str, role_key: str, index: int) -> str:
    role = role_key.lower()
    if mode == "selection_candidates":
        return "same camera family with one small crop, gaze, expression, hand, or head-angle change"
    if mode == "creative_exploration":
        return "intentional new lens mood or scene depth while preserving recognizable identity traits"
    if mode == "format_layout_adaptation":
        return "crop and safe-area change with natural face scale and body proportion"
    if "detail" in role or "focus" in role:
        return "closer beauty or upper-body crop with shallow depth and texture detail"
    if "side" in role or "angle" in role or "three" in role:
        return "three-quarter or side angle with changed face plane, shoulder line, and gaze"
    if "wide" in role or "context" in role or "scene" in role:
        return "wider environmental frame with body scale and scene contact"
    if index > 1:
        return "different natural camera distance or crop from the first frame"
    return "cover-safe medium portrait with a real near-camera presence"


def _product_camera_atom(*, mode: str, role_key: str, index: int) -> str:
    role = role_key.lower()
    if mode == "selection_candidates":
        return "same setup with a small angle, highlight, surface rhythm, or crop difference"
    if mode == "creative_exploration":
        return "controlled concept variation through location, prop language, surface, or lens mood"
    if mode == "format_layout_adaptation":
        return "crop and negative-space adaptation while product truth stays readable"
    if any(token in role for token in ["scenario", "lifestyle", "context", "usage"]):
        return "medium-wide lived-in context frame with environment depth and real use cue"
    if any(token in role for token in ["detail", "feature", "material", "close"]):
        return "close detail angle for material, edge, label area, condensation, or functional proof"
    if any(token in role for token in ["cover", "ad", "layout", "trust"]):
        return "layout-safe hero angle with clean blank space and clear silhouette"
    if index > 1:
        return "new role-specific camera distance, not another identical front packshot"
    return "front or three-quarter hero angle with premium product silhouette"


def _atom_overlay(
    *,
    prompt: str,
    camera: list[str],
    light: list[str],
    texture: list[str],
    reference: list[str],
    negative: list[str],
    review: list[str],
    axes: list[str],
    product_truth: list[str] | None = None,
) -> dict[str, Any]:
    product_truth = product_truth or []
    keep = [*reference, *product_truth]
    metadata = {
        "doc69_prompt_atom_recipe": True,
        "prompt_atom_recipe_library": VISUAL_PROMPT_ATOM_RECIPE_ID,
        "prompt_atom_camera_stack": camera,
        "prompt_atom_light_stack": light,
        "prompt_atom_texture_stack": texture,
        "prompt_atom_reference_guard": reference,
        "prompt_atom_product_truth_guard": product_truth,
        "prompt_atom_negative_guard": negative,
        "prompt_atom_review_targets": review,
    }
    return {
        "prompt_pressure": prompt,
        "variation_axes": axes,
        "must_keep_rules": keep,
        "must_not_rules": negative,
        "negative_pressure": negative,
        "review_checks": review,
        "metadata": metadata,
    }


def _role_overlay(*, mode: str, subject_type: str, role_key: str, index: int) -> dict[str, Any]:
    if subject_type == "character":
        return _portrait_overlay(mode=mode, role_key=role_key, index=index)
    if subject_type == "product":
        return _product_overlay(mode=mode, role_key=role_key, index=index)
    return _generic_overlay(mode=mode, role_key=role_key, index=index)


def _portrait_overlay(*, mode: str, role_key: str, index: int) -> dict[str, Any]:
    if mode == "selection_candidates":
        return _overlay(
            prompt="Keep the same shoot and person direction; make this a close alternative with one small visible change in micro-expression, gaze, mouth tension, hair movement, hand placement, crop, or head angle; do not beautify the face shape between options.",
            camera="same lens family and scene, micro crop or head-angle variation only",
            realism="real shutter-moment portrait with natural skin texture, mild camera imperfection, individual facial character, and no cloned expression",
            difference="close comparable option, not a new concept",
            review=["same person direction", "small visible difference", "not an identical beauty still"],
            negative=["wild identity change", "same exact expression copied", "same exact head angle copied", "same perfect smile repeated"],
            axes=["micro-expression", "gaze", "mouth tension", "hair movement", "head angle", "crop"],
        )
    if mode == "creative_exploration":
        return _overlay(
            prompt="Explore a distinct portrait concept through mood, scene, styling, lens, or light while preserving recognizable person direction.",
            camera="change lens mood or scene depth intentionally",
            realism="photographic realism remains intact even when art direction changes",
            difference="new concept lane, controlled identity continuity",
            review=["concept is intentionally different", "identity direction remains readable"],
            negative=["random face replacement", "uncontrolled age or body drift"],
            axes=["mood", "scene", "styling", "lens", "palette"],
        )
    if mode == "format_layout_adaptation":
        return _overlay(
            prompt="Adapt the same portrait idea to a different layout crop or safe area while keeping identity, styling family, and face scale natural.",
            camera="layout crop changes, identity camera language stays stable",
            realism="natural face scale and body proportions after crop",
            difference="format and safe-area variation only",
            review=["crop fits format", "identity and styling do not drift"],
            negative=["identity drift caused by crop", "face cut off awkwardly"],
            axes=["crop", "safe area", "subject scale", "negative space"],
        )
    role = role_key.lower()
    if "focus" in role or "detail" in role:
        return _overlay(
            prompt="Make this the closer subject/detail frame with hair texture, clean lifted skin light, shallow depth, under-eye detail, lip texture, fabric wrinkles, a candid non-doll expression, and natural head/neck/shoulder proportion.",
            camera="closer upper-body crop with shallow depth and slight real-lens softness; keep face scale, neck, shoulders, and torso proportion natural",
            realism="skin, hairline, eyes, cheek texture, lip texture, eyelid folds, fresh complexion, and fabric should read as photographed rather than beauty-app retouched",
            difference="closer identity/detail duty",
            review=["closer subject role", "natural skin detail", "natural head/neck/shoulder proportion", "not the same cover posture", "not a poreless beauty-app face"],
            negative=["same cover crop", "over-smoothed beauty mask", "skin-blur retouching", "idol photocard polish", "oversized head", "compressed neck", "awkward shoulder crop"],
            axes=["expression", "crop", "hair detail", "skin tonal variation", "depth of field", "head-to-body proportion"],
        )
    if "side" in role or "angle" in role or "three" in role:
        return _overlay(
            prompt="Make this a real side or three-quarter angle with a different face plane, body turn, shoulder line, and gaze direction.",
            camera="side or three-quarter angle, medium portrait distance",
            realism="preserve identity through feature relationships despite the changed face plane",
            difference="angle and body-turn duty",
            review=["visible angle change", "same identity direction", "not a front-facing duplicate"],
            negative=["front-facing duplicate", "extreme profile identity loss"],
            axes=["head angle", "body turn", "gaze direction", "shoulder line"],
        )
    if "wide" in role or "context" in role or "scene" in role:
        return _overlay(
            prompt="Make this the wider lifestyle/context frame with body scale, environment interaction, and scene depth from the same visual world.",
            camera="wider three-quarter or full-body environmental portrait",
            realism="subject integrated into a real environment rather than pasted onto a backdrop",
            difference="environment/context duty",
            review=["wider context", "environment interaction", "same person direction"],
            negative=["another tight headshot", "unrelated prop or product"],
            axes=["body scale", "environment interaction", "scene depth", "camera distance"],
        )
    return _overlay(
            prompt="Make this the cover hero frame with confident near-camera presence, clean shoulders, square or vertical cover-safe portrait framing, healthy bright face light, natural head/body scale, and a quiet neutral expression or imperfect half-smile with slight asymmetry rather than a sweet template smile.",
        camera="square or vertical medium portrait cover crop, front or slight three-quarter with mild handheld or lens imperfection",
            realism="professional camera-ready portrait with clean healthy complexion, real skin texture, tiny asymmetry, individual facial character, and no beauty-app polish",
        difference="hero/cover duty",
        review=["cover hero role", "professional finish", "not over-cloned", "not an idol photocard face"],
        negative=[
            "generic AI influencer face",
            "same expression as every output",
            "perfect template smile",
            "flawless porcelain mask",
            "horizontal banner crop",
            "letterboxed portrait",
            "wide panorama cover",
            "oversized head",
            "compressed shoulders",
        ],
            axes=["subject scale", "cover-safe crop", "quiet micro-expression", "real-camera softness", "head/shoulder proportion"],
    )


def _product_overlay(*, mode: str, role_key: str, index: int) -> dict[str, Any]:
    if mode == "selection_candidates":
        return _overlay(
            prompt="Keep the same product truth and setup; vary only a small angle, light, surface rhythm, crop, or highlight detail.",
            camera="same setup with micro angle or crop variation",
            product="same silhouette, label placement, material, edge, and readable visible label",
            difference="close product option for selection",
            review=["same product truth", "small useful variation", "not an identical still"],
            negative=["new product", "rewritten label", "same exact still repeated"],
            axes=["angle", "surface", "highlight", "crop"],
        )
    if mode == "creative_exploration":
        return _overlay(
            prompt="Explore a distinct product art-direction lane through location, prop language, palette, surface, lighting, or campaign mood while preserving product truth.",
            camera="controlled change in lens, surface, environment, or light",
            product="product identity remains inspectable across creative concepts",
            difference="new campaign concept lane",
            review=["concepts differ intentionally", "product truth remains clear"],
            negative=["random unrelated product", "fake claim badges"],
            axes=["location", "surface", "palette", "light", "props"],
        )
    if mode == "format_layout_adaptation":
        return _overlay(
            prompt="Adapt the same product idea to the requested crop, safe area, and platform layout without changing product identity.",
            camera="layout crop and negative-space variation",
            product="product remains readable after crop",
            difference="format/layout duty",
            review=["format fit", "product not cut off", "usable blank space"],
            negative=["bad crop", "label obscured", "new product identity"],
            axes=["crop", "safe area", "negative space", "subject scale"],
        )
    role = role_key.lower()
    if any(token in role for token in ["scenario", "lifestyle", "context", "usage"]):
        return _overlay(
            prompt="Make this a genuinely lived-in lifestyle/context image: real surface, natural use cue, believable environment depth, and product integrated into the scene rather than another studio packshot.",
            camera="medium-wide context angle with environment depth",
            product="preserve product shape, label placement, material, and readable visible logo/label",
            difference="lifestyle/context professional duty",
            review=["real context present", "not studio-only", "product truth preserved"],
            negative=["studio-only repetition", "unrelated extra product", "fake feature text"],
            axes=["environment", "surface", "usage cue", "camera distance"],
        )
    if any(token in role for token in ["detail", "feature", "material", "close"]):
        return _overlay(
            prompt="Make this a detail/material proof frame with close product texture, edge, label area, condensation, finish, or functional detail.",
            camera="close detail angle",
            product="product material and label area stay truthful and inspectable",
            difference="detail/material duty",
            review=["detail is visible", "material truth preserved", "not another hero image"],
            negative=["unreadable label", "invented icons", "generic closeup with no feature"],
            axes=["texture", "material", "label area", "edge detail"],
        )
    if any(token in role for token in ["cover", "ad", "layout", "trust"]):
        return _overlay(
            prompt="Make this a layout-safe professional cover with clear product identity and clean blank space for later external copy.",
            camera="medium product angle with safe negative space",
            product="product silhouette and label placement remain clear",
            difference="cover/layout duty",
            review=["usable blank space", "clear product identity", "no rendered badges"],
            negative=["embedded claim strip", "fake badge", "watermark"],
            axes=["negative space", "cover crop", "subject placement"],
        )
    return _overlay(
        prompt="Make this the product hero frame with clean silhouette, premium light, readable product truth, and a strong first impression.",
        camera="front or three-quarter hero product angle",
        product="shape, material, label placement, and proportions stay accurate",
        difference="main hero duty",
        review=["hero silhouette", "product identity clear", "professional finish"],
        negative=["distorted product", "rewritten label", "unrelated prop clutter"],
        axes=["scale", "placement", "light"],
    )


def _generic_overlay(*, mode: str, role_key: str, index: int) -> dict[str, Any]:
    return _overlay(
        prompt="Use one clear visual duty for this output and keep it distinct from other outputs through crop, angle, scene depth, or presentation.",
        camera="role-appropriate camera distance and framing",
        realism="polished complete image frame",
        difference="distinct role without random drift",
        review=["role is clear", "style remains coherent", "not a duplicate frame"],
        negative=["same exact still repeated", "random subject drift"],
        axes=["crop", "angle", "scene depth", "presentation"],
    )


def _overlay(
    *,
    prompt: str,
    camera: str,
    difference: str,
    review: list[str],
    negative: list[str],
    axes: list[str],
    realism: str | None = None,
    product: str | None = None,
) -> dict[str, Any]:
    metadata = {
        "casebook_camera_recipe": camera,
        "casebook_role_difference": difference,
        "casebook_review_targets": review,
    }
    if realism:
        metadata["casebook_realism_recipe"] = realism
    if product:
        metadata["casebook_product_recipe"] = product
    keep = [product] if product else []
    return {
        "prompt_pressure": prompt,
        "variation_axes": axes,
        "must_keep_rules": keep,
        "must_not_rules": negative,
        "negative_pressure": negative,
        "review_checks": review,
        "metadata": metadata,
    }


def _canonical_mode(value: str | None) -> str:
    text = str(value or "").strip()
    aliases = {
        "auto": "delivery_suite",
        "creative_explore": "creative_exploration",
        "layout_adaptation": "format_layout_adaptation",
        "format_adaptation": "format_layout_adaptation",
    }
    return aliases.get(text, text if text else "delivery_suite")


def _normalize_subject_type(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in {"character", "human", "person", "portrait"}:
        return "character"
    if text in {"product", "object", "sku"}:
        return "product"
    return "generic"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _join_sentences(*values: Any) -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return " ".join(parts)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
