# E25 Professional E-Commerce Pose Acceptance Contract

Status: Phase implementation proposal for reviewer gate; no planning-only rerun,
host ImageGen, business delivery receipt, slot, or activation is authorized by
this document.

Scope: Professional E-Commerce product-on-person deliverables only.

## 1. Correction model

The final integrated poolside acceptance run produced one acceptable seated
output and one rejected standing output. The rejected image was visually
poolside and product-on-person, but the person was kneeling/half-crouched with
low support rather than standing with both feet bearing weight. The frozen
provider prompt said `stands`, but that natural-language cue did not form a
machine-checkable deliverable receipt before host materialization.

The owning layer is Professional E-Commerce deliverable pose acceptance:

- E-Commerce owns the requested package map and output role coverage.
- Remote Brain and the finalizer still own the final natural-language prompt.
- Shared Human Realism owns human realism and post-review, not exact
  commerce-package pose coverage.
- Provider/MCP owns rendering/materialization, not semantic pose repair.

Therefore the minimal correction is a closed pose receipt attached to the
Professional E-Commerce plan and verified before host materialization. This is
not a prompt patch and not a Provider/global safety rule.

## 2. Current typed contract

When a Professional E-Commerce request explicitly requires a two-image
poolside seated/standing package, the server-side Professional E-Commerce
planner may add:

```json
{
  "contract_version": "professional_ecommerce_pose_contract_v1",
  "owner": "professional_ecommerce_deliverable_pose_acceptance",
  "source": "explicit_user_pose_coverage_request",
  "required_pose_by_output": [
    {
      "output_index": 1,
      "pose_role": "seated_poolside",
      "standing_requirements": []
    },
    {
      "output_index": 2,
      "pose_role": "standing_poolside",
      "standing_requirements": [
        "both_feet_weight_bearing",
        "interaction_may_use_one_hand_but_body_remains_standing",
        "no_crouched_low_support",
        "no_kneeling"
      ]
    }
  ]
}
```

Closed values:

- `pose_role`: `seated_poolside`, `standing_poolside`.
- `standing_requirements`: empty for `seated_poolside`; for
  `standing_poolside`, exactly all of
  `both_feet_weight_bearing`, `no_kneeling`,
  `no_crouched_low_support`, and
  `interaction_may_use_one_hand_but_body_remains_standing`.

Unknown values, duplicate output indexes, missing exact-N coverage, and missing
or contradictory Remote Brain receipts fail closed before host materialization.

## 3. Call graph and boundaries

1. `CodexNativeImageGenPlanner` detects only explicit Professional E-Commerce
   poolside seated/standing exact-N=2 coverage and attaches the typed contract
   to `ecommerce_creative_context`.
2. `V3LLMBrainAdapter` allowlists and validates the typed contract. Present but
   invalid payloads become a sanitized invalid sentinel and are blocked before
   Remote Brain.
3. `prompts.py` includes the existing compact Remote Brain schema plus the
   closed pose receipt fields when the contract is present.
4. `ScenarioRuntime` validates that the Remote Brain image set plan returns the
   exact pose role and standing requirements for each output and freezes that
   receipt into deliverable metadata.
5. `CodexNativeImageGenPlanner` reads the frozen deliverable metadata and
   projects the pose receipt into each output's `reference_input_contract`.
6. The host renderer may be called only after this receipt is present and
   consistent. Missing receipt or mismatch returns a blocked plan, not a local
   prompt patch, retry, hidden output deletion, or route fallback.

The contract preserves:

- exact requested output count;
- Professional identity binding and approved view admission;
- product truth pool/selection and provider reference cap;
- provider admission receipt;
- Remote Brain/finalizer prompt authority;
- no business job/candidate/output/formal receipt/slot/activation writes from
  planning-only validation.

## 4. Isolation

This document does not authorize:

- adding pose rules to E24 creative-risk preflight;
- adding poolside, kidswear, swimwear, or child-specific rules to shared Human
  Realism;
- modifying General Template or Photography;
- changing Provider/MCP materialization, storage, receipts, slots, or UI;
- retrying the old rejected output or reusing old frozen host prompts.

The previous poolside output2 remains append-only rejected evidence. It is not
accepted delivery and must not be used to claim standing coverage.

## 5. Regression requirements

Focused deterministic tests must cover:

- valid Professional E-Commerce poolside exact-N=2 contract projection;
- missing pose receipt fail-closed before materialization;
- wrong `standing_poolside` requirements fail-closed before materialization;
- wrong output role fail-closed before materialization;
- real payload schema includes closed pose fields only when the typed contract
  is present;
- General/non-E-Commerce payload isolation;
- product truth selection, provider cap, exact-N, identity binding, provider
  admission, and no-leakage behavior remain unchanged.

## 6. Reviewer gate

After the focused tests and compile/diff checks pass, the feature branch may be
submitted for reviewer inspection. A passing feature branch does not authorize
planning-only reruns, host ImageGen, formal delivery receipts, slots, or
activations. Those require a separate reviewer gate.
