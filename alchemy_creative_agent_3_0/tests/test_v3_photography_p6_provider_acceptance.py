from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    PhotographyDeliveryMode,
    PhotographyInputMode,
    PhotographyProviderAcceptanceDirector,
    PhotographySceneDomain,
)


def test_p6_single_hero_provider_matrix_covers_every_first_wave_scene_and_input_mode() -> None:
    matrix = PhotographyProviderAcceptanceDirector().baseline_single_hero_matrix()

    assert matrix.matrix_kind == "p6_single_hero_provider_baseline"
    assert len(matrix.cases) == 8
    assert {case.scene_domain for case in matrix.cases} == {
        PhotographySceneDomain.PORTRAIT,
        PhotographySceneDomain.LANDSCAPE,
        PhotographySceneDomain.STILL_LIFE,
        PhotographySceneDomain.ANIMAL,
    }
    for scene in PhotographySceneDomain:
        if scene == PhotographySceneDomain.GENERAL:
            continue
        scene_cases = [case for case in matrix.cases if case.scene_domain == scene]
        assert {case.input_mode for case in scene_cases} == {
            PhotographyInputMode.TEXT_TO_PHOTO,
            PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
        }
        assert all(case.delivery_mode == PhotographyDeliveryMode.SINGLE_HERO for case in scene_cases)
        assert all("PHOTOGRAPHY-MAINLINE-003" in case.required_mainline_contracts for case in scene_cases)


def test_p6_reference_cases_preserve_only_declared_truth_and_animal_requires_native_fidelity() -> None:
    matrix = PhotographyProviderAcceptanceDirector().baseline_single_hero_matrix()
    references = [case for case in matrix.cases if case.input_mode == PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT]

    assert {case.required_reference_role for case in references} == {
        "face_reference",
        "background_reference",
        "product_reference",
        "nonhuman_identity_reference",
    }
    animal = next(case for case in references if case.scene_domain == PhotographySceneDomain.ANIMAL)
    assert animal.preservation_controls["nonhuman_subject_identity"] == "preserve"
    assert animal.metadata["requires_high_fidelity_reference"] is True
    assert animal.metadata["must_block_without_high_fidelity"] is True
    assert "nonhuman_subject_identity" in animal.required_shared_capabilities


def test_p6_professional_set_release_matrix_explicitly_waits_for_shared_role_execution() -> None:
    matrix = PhotographyProviderAcceptanceDirector().release_professional_set_matrix()

    assert len(matrix.cases) == 8
    assert all(case.delivery_mode == PhotographyDeliveryMode.PROFESSIONAL_SET for case in matrix.cases)
    assert all("PHOTOGRAPHY-MAINLINE-004" in case.required_mainline_contracts for case in matrix.cases)
    assert matrix.metadata["professional_set_requires_mainline_004"] is True


def test_p6_provider_acceptance_contract_keeps_rendering_review_retry_and_delivery_shared() -> None:
    matrix = PhotographyProviderAcceptanceDirector().baseline_single_hero_matrix()

    assert matrix.shared_execution_contract == {
        "provider_owner": "shared_v3_runtime",
        "review_owner": "shared_visual_review",
        "retry_owner": "shared_frozen_plan_retry",
        "final_delivery_owner": "shared_final_delivery_resolver",
        "photography_private_provider_or_retry": False,
    }
    payload = json.dumps(matrix.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "provider_id" not in payload
    assert "source_url" not in payload
    assert "ecommerce" not in payload
