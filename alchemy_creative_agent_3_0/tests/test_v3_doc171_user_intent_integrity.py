"""Doc171: final Brain rewriting must preserve the protected user meaning."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


_USER_INTENT = (
    "Create a professional studio portrait of a fictional fifteen-year-old person on a white background. "
    "Use neutral daylight and a natural scene-balanced complexion rather than a cool-fair treatment."
)


def _developmental_resign_request() -> BrainRunRequest:
    return BrainRunRequest(
        user_input=_USER_INTENT,
        stage="provider_prompt_developmental_presence_verify",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        requested_image_size="1024x1536",
        metadata={
            "canonical_prompt_context": {
                "protected_user_intent": _USER_INTENT,
                "frozen_binding": {
                    "activation_plan_id": "opaque-plan",
                    "execution_envelope_id": "opaque-envelope",
                    "constraint_ledger_id": "opaque-ledger",
                },
                "final_prompt_semantic_preflight": {
                    "required": True,
                    "scope": "whole_image_human_photographic_plausibility",
                    "owner": "remote_v3_llm_brain",
                    "revision_mode": "rewrite_complete_canonical_prompt",
                },
                "human_naturalness_decision": {
                    "required": True,
                    "contract_version": "v3_human_naturalness_decision_v1",
                    "owner": "remote_v3_llm_brain",
                    "frozen_binding": {
                        "activation_plan_id": "opaque-plan",
                        "execution_envelope_id": "opaque-envelope",
                        "constraint_ledger_id": "opaque-ledger",
                    },
                },
            },
            "candidate_canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "prompt": (
                        "A fifteen-year-old person stands by a window in warm afternoon light, "
                        "with a softly blurred lifestyle background."
                    ),
                }
            ],
        },
    )


def test_doc171_finalizer_keeps_protected_user_meaning_as_rewrite_boundary() -> None:
    payload = json.loads(build_remote_payload(_developmental_resign_request()))
    contract = payload["remote_response_contract"]

    assert payload["user_input"] == _USER_INTENT
    assert payload["frozen_render_context"]["protected_user_intent"] == _USER_INTENT
    assert "protected user intent is the immutable semantic source" in contract
    assert "semantically equivalent" in contract
    assert "explicit non-conflicting current-request choice" in contract
    assert "static studio capture is already a complete situation" in contract
    assert "Do not use keyword matching" in contract


def test_doc171_does_not_add_a_local_scene_or_age_recipe() -> None:
    source = inspect.getsource(ScenarioRuntime._finalize_canonical_provider_prompts).lower()  # noqa: SLF001

    assert "re.compile" not in source
    assert "white background" not in source
    assert "fifteen" not in source
    assert "six-year" not in source
    assert "prompt suffix" not in source


def test_doc171_shared_brain_authority_is_age_and_complexion_neutral() -> None:
    lowered = SYSTEM_PROMPT.lower()

    assert "six-year-old" not in lowered
    assert "fifteen-year-old" not in lowered
    assert "east asian" not in lowered
    assert "cold-fair" not in lowered
    assert "baby fat" not in lowered
    assert "facial ratio" not in lowered
    assert "do not introduce an unrequested emphasis on body shape" in lowered
    assert "without aestheticizing the person's physique" in lowered


def test_doc171_marks_historical_demographic_wording_as_non_authoritative() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "docs"
    doc77 = (docs_root / "77_V3_REAL_VISUAL_REVIEW_AND_AESTHETIC_STABILITY_FOUNDATION_SPEC.md").read_text(
        encoding="utf-8"
    )
    doc78 = (docs_root / "78_V3_LONG_TERM_IDENTITY_AND_BEAUTIFUL_REALISM_FINAL_TUNING_SPEC.md").read_text(
        encoding="utf-8"
    )

    assert "Doc94/159 correction note" in doc77
    assert "Doc94/159 correction note" in doc78
    assert "must not activate or word a fresh runtime prompt" in doc77
    assert "must not activate or word a fresh runtime prompt" in doc78
