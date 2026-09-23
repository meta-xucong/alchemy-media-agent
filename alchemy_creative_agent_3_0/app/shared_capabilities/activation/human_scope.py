"""Transport frozen human visibility semantics without classifying prompt prose."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_PERSON_TYPES = frozenset({"person", "human", "character", "face", "portrait"})
_DETAIL_TYPES = frozenset({"hand", "hands", "arm", "arms", "leg", "legs", "body_part", "human_body_part", "human_detail", "skin_detail", "skin", "torso", "foot", "feet", "finger", "fingers"})
_DETAIL_PARTS = frozenset({"hand", "hands", "arm", "arms", "leg", "legs", "finger", "fingers", "skin", "torso", "foot", "feet"})

_NONHUMAN_TYPES = frozenset({
    "product", "object", "animal", "plant", "scene", "environment", "landscape",
    "food", "vehicle", "text", "logo", "graphic", "furniture", "architecture",
})


def frozen_human_scope(profile: Any) -> dict[str, Any]:
    """Read only typed entities/attributes signed by the planning Brain.

    An absent profile is unknown (legacy-compatible), not proof of no face.
    Descriptions, filenames, skincare claims and free-text prompts are ignored.
    """
    if not isinstance(profile, Mapping):
        return {"known": False}
    entities = profile.get("subject_entities")
    if not isinstance(entities, list) or not entities:
        return {"known": False}
    people: list[tuple[bool, bool | None]] = []
    for entity in entities:
        if not isinstance(entity, Mapping):
            return {"known": False}
        if entity.get("visible_in_target") is False:
            continue
        kind = str(entity.get("entity_type") or "").strip().casefold()
        if kind in _NONHUMAN_TYPES:
            continue
        if kind not in _PERSON_TYPES | _DETAIL_TYPES:
            # Unknown entities cannot be used as proof that no face exists.
            return {"known": False}
        attrs = entity.get("attributes")
        attrs = attrs if isinstance(attrs, Mapping) else {}
        visible = attrs.get("face_visible", attrs.get("primary_face_visibility_expected"))
        visible = visible if isinstance(visible, bool) else None
        parts = attrs.get("visible_body_parts", attrs.get("visible_parts"))
        parts = {str(part).strip().casefold() for part in parts} if isinstance(parts, list) else set()
        detail = (
            kind in _DETAIL_TYPES
            or attrs.get("human_subject_kind") == "hand_or_skin_detail"
            or (bool(parts) and parts.issubset(_DETAIL_PARTS))
        )
        if visible is True:
            detail = False
        elif detail:
            visible = False
        people.append((detail, visible))
    if not people:
        return {"known": True, "human_present": False, "human_subject_kind": "not_applicable", "face_visible": False}
    detail_only = all(detail for detail, _ in people)
    face_visible = True if any(face is True for _, face in people) else (
        False if all(face is False for _, face in people) else None
    )
    return {
        "known": True,
        "human_present": True,
        "human_subject_kind": "hand_or_skin_detail" if detail_only else "person",
        "face_visible": face_visible,
    }
