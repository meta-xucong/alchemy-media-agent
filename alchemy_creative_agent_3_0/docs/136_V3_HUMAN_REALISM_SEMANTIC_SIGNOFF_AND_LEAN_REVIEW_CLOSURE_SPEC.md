# Doc136 — V3 Human Realism Semantic Sign-off and Lean Review Closure

Status: **historical implementation baseline; forward contract refined by Doc143.** This document closes a controlled General real-image audit finding. It extends Docs 128, 134 and 135; it does not create a child, apparel, E-Commerce, General or Photography-specific creative route. The v1 payload recorded below is historical. Doc143 supersedes the v2 semantic shape for fresh enforced Human Realism jobs and adds frozen pixel attestation; existing history remains readable.

## 1. Recorded finding

A controlled, reference-bound real-person run correctly produced all of the following before materialization:

- a remote Brain creative plan with `llm_used=true` and no fallback;
- a photoreal, whole-image rendering intent;
- `human_realism=required` in the frozen CapabilityActivationPlan; and
- an enforced Human Realism executor result with its five shared review dimensions.

The resulting canonical Provider prompt nevertheless remained too thin to show that the Brain had considered the real-person quality boundary. The failure was **not** an activation failure and was **not** caused by an object-surface illustration being classified as a whole-image cartoon style.

The execution gap was simpler: the frozen ledger retained `human_photorealism_guidance`, while `provider_prompt_finalize` received only the `human_realism` capability ID. Consequently the Brain could not verify the resolved Human Realism semantic obligation before it signed the only renderer-facing prompt.

This document records that evidence and prevents a false remedy such as adding local face/hand/skin keyword piles to the Provider prompt.

## 2. Correct forward path

```text
protected user intent + admitted reference truth
-> remote Brain semantic interpretation and draft direction
-> frozen activation plan + execution envelope + constraint ledger
-> shared Human Realism emits a typed semantic contract
-> remote Brain final sign-off of one complete canonical prompt per output
-> exact prompt/reference relay to Web Provider or Codex Native ImageGen
-> frozen-contract pixel review + bounded Brain re-sign-off when needed
```

The Human Realism contract is an input to Brain reasoning, not renderer prose. Only the remote Brain may convert it into natural language. The materializer and Local MCP relay only transmit the Brain-approved canonical string and its integrity binding.

## 3. Typed Human Realism semantic contract

The v1 payload below is the historical implementation baseline for the allow-listed, data-only contract:

```json
{
  "contract_version": "v3_human_realism_semantic_v1",
  "capability_id": "human_realism",
  "rendering_goal": "photographic_real_person|photographic_human_detail",
  "quality_axes": [
    "human_rendering_artifact",
    "human_anatomy_or_proportion",
    "human_age_or_identity_fidelity",
    "human_skin_or_retouch",
    "human_scene_coherence"
  ],
  "identity_age_fidelity": "explicit_or_reference_backed",
  "physical_coherence": "required",
  "reference_boundary": "resolved_channels_only",
  "ordinary_age_appropriate_context": false,
  "creative_direction_owner": "remote_v3_llm_brain",
  "provider_prompt_owner": "remote_v3_llm_brain"
}
```

For a hand/skin-detail task, the three applicable axes are anatomy, skin/retouch and scene coherence. The contract remains shared and is still owned by the Brain. `ordinary_age_appropriate_context` is a generic, evidence-gated safety boundary: it is not an age classifier, a prompt recipe, a demographic route or a substitute for user intent. The recorded Doc138 v2 contract was the baseline that added generic natural-presence and aesthetic-boundary decisions; fresh enforced jobs now use Doc143 v3 and still must not revive local renderer prose.

An active Human Realism capability with a missing, malformed or incompatible semantic contract must block final Brain sign-off with the safe reason `human_realism_semantic_contract_missing`. It must never silently revert to legacy local fragments.

## 4. Strictly prohibited forward data

For enforced Brain-owned execution, Human Realism must not expose any of the following to the finalizer, Provider or Local MCP relay:

- `positive_prompt_fragments`, `negative_prompt_fragments`, or local prompt additions;
- retry patch prose, raw visual issue codes, anatomy micro-instructions, or beauty/skin word lists;
- named children/kidswear, geography, ecommerce, Photography or General recipes;
- camera, crop, pose, scene, lighting or composition directives.

Historical records may retain those fields for read compatibility only. New enforced paths emit empty compatibility fields and no downstream reader may turn them into renderer language.

## 5. Brain sign-off and retry rule

The `provider_prompt_finalize` payload contains `active_semantic_capability_contracts`, validated from the frozen ledger. The system prompt instructs the Brain to reconcile this boundary holistically with the user-owned direction and admitted references, then write one natural whole-image prompt. It must not echo contract keys, review codes or a checklist.

A retry keeps the same semantic contract. It supplies only normalized, frozen review dimensions as evidence to a fresh Brain sign-off. Local code may not translate a review issue into repair language or append anything to the previous canonical prompt.

## 6. Lean enforced pixel review

Enforced reviews must build their inspection instruction directly from the frozen active review contract. The inspector sees only:

- the output and admitted reference-policy boundary;
- user goal and applicable frozen truth/evidence contracts;
- active issue codes, score dimensions and capability sources; and
- the strict JSON response shape derived from those same fields.

The legacy full issue catalogue remains readable only for non-enforced/archive compatibility. An enforced job must not first construct a large historical prompt and then try to delete irrelevant named cases. This is review schema reduction, not creative prompting.

`metadata_only` and local-only inspection remain non-certifying. A hard real-person or reference truth contract requires `vision_model` or `hybrid` pixel evidence before final delivery can be certified.

## 7. Verification matrix

The implementation must prove all of the following:

| Case | Required proof |
| --- | --- |
| Real visible person | Human Realism activates and a valid typed contract reaches Brain finalization. |
| Surface illustration on real apparel | Frozen `photoreal/object_surface` intent remains intact; no whole-image style downgrade. |
| Product-only/flat-lay | Human Realism does not activate merely from garment association. |
| Enforced forward execution | No Human Realism compatibility phrase/retry field reaches Brain, Provider or MCP. |
| Missing active contract | Finalization fails closed before a materialization operation. |
| Enforced review | Prompt contains only active frozen review codes/dimensions, not the historical mega catalogue. |
| Web and Codex Native relay | Both bind byte-identical canonical prompt and admitted-reference hashes. |

## 8. Documentation status and boundaries

- Doc128 remains the shared activation/review authority; its former fragment-oriented compatibility fields are historical for enforced jobs.
- Doc138 records the v2 forward semantic baseline. Doc142 adds a schema-only, same-pass re-signing receipt; Doc143 is the fresh-job v3 semantic and pixel-attestation authority. None authorizes a third Brain pass or a local prompt patch.
- Docs134–135 remain the canonical-prompt ownership authority. This document supplies the missing typed Human Realism sign-off bridge.
- Child/apparel samples are regression evidence only. Later visual-quality work may refine the remote Brain or visual review using cross-scene evidence, but must not add a child-specific runtime module or structured prompt stack.
- This closure does not certify a rendered image by itself. It makes the Brain/Provider contract complete; visual quality still needs the appropriate real-pixel or Local-MCP comparison evidence under the active acceptance plan.

## 9. Implementation evidence

Implementation completed under the Doc136 contract:

- `HumanPhotorealismGuidance.semantic_contract` now carries the allow-listed frozen data contract.
- New enforced Brain-owned execution emits no local Human Realism prompt, negative, reference-overlay or retry-prose compatibility fields.
- `ScenarioRuntime` validates and projects the active contract to `provider_prompt_finalize`; a malformed active contract blocks before materialization.
- The Brain system instruction requires holistic semantic reconciliation and prohibits copying contract data into the final prompt.
- Enforced visual inspection now projects directly from its frozen review contract instead of constructing the historical mega catalogue first.

Regression evidence recorded during implementation:

- Doc136 + Human Realism + Doc102/113 + retry + Photography/E-Commerce focused suite: `71 passed`.
- Root frontend/configuration and Codex Native prompt/relay parity suite: `34 passed` (two pre-existing FastAPI deprecation warnings).
- `compileall`, browser script syntax validation and `git diff --check` passed.

During the broad regression run, two stale test assumptions were corrected without changing production behavior: the Lab candidate test now supplies the Lab-scoped OpenAI credential that its adapter actually reads, and the V3 shell test now asserts that the retired `one_click_product_set` execution default is absent. These guard the current LLM-first contract rather than reviving legacy behavior.

Final full-suite evidence:

- V3 suite, all 106 `alchemy_creative_agent_3_0/tests/test_*.py` files:
  `747 passed` (executed in deterministic file batches because the local
  terminal display truncates a long single-run progress stream; every batch
  returned exit code zero).
- Repository root suite: `185 passed`, with two existing FastAPI deprecation
  warnings and no failures.
