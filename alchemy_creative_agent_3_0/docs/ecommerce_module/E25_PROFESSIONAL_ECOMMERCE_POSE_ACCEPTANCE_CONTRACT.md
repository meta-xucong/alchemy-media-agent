# E25 Professional E-Commerce Pose Acceptance Contract

Status: Phase implementation proposal for reviewer gate; no planning-only rerun,
host ImageGen, business delivery receipt, slot, or activation is authorized by
this document.

Scope: Professional E-Commerce product-on-person deliverables only.

> **Narrowed by Professional body-proportion runtime projection design:** This
> document governs pose/presentation receipts for Professional E-Commerce
> poolside product-on-person outputs. It does not certify body scale,
> neck/shoulder continuity, torso/limb proportions, or developmental-stage
> body coherence. Visible/full-body Professional E-Commerce outputs must also
> satisfy the shared Professional body-only reference projection gate once that
> gate is implemented; root portrait + selected face winner + selected
> product truth is a face/product/presentation chain, not body-proportion
> certification.

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

### 1A. Follow-up correction for standing presentation ambiguity

The fresh integrated run reached Host with a valid standing receipt, but the
Brain-authored standing direction chose a rear-facing look-back composition and
did not make full-body standing presentation explicit. The Host then returned
an opaque output moderation block. The public Host signal does not prove that
this composition caused the block, so this is an ambiguity-reduction repair,
not a claim about hidden policy internals.

The owning correction remains this Professional E-Commerce deliverable
contract. The standing role now carries a second closed receipt list for
camera/presentation semantics:

- `front_or_three_quarter_presentation`;
- `ordinary_full_body_commercial_framing`;
- `eye_level_or_standard_camera_height`;
- `no_rear_facing_lookback`.

These values constrain the requested deliverable's presentation only. They are
not a safety keyword filter, not renderer prose, and not a shared Human
Realism, General, Provider, or Host rule. Remote Brain still authors the final
natural-language direction; Runtime validates the returned receipt before any
new Host call.

## 2. Current typed contract

When a Professional E-Commerce request explicitly requires a two-image
poolside seated/standing package, the server-side Professional E-Commerce
planner may add:

```json
{
  "contract_version": "professional_ecommerce_pose_contract_v2",
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
      ],
      "standing_presentation_requirements": [
        "front_or_three_quarter_presentation",
        "ordinary_full_body_commercial_framing",
        "eye_level_or_standard_camera_height",
        "no_rear_facing_lookback"
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
- `standing_presentation_requirements`: empty for `seated_poolside`; for
  `standing_poolside`, exactly all of
  `front_or_three_quarter_presentation`,
  `ordinary_full_body_commercial_framing`,
  `eye_level_or_standard_camera_height`, and
  `no_rear_facing_lookback`.

Unknown values, duplicate output indexes, missing exact-N coverage, and missing
or contradictory Remote Brain receipts fail closed before host materialization.
The prior `professional_ecommerce_pose_contract_v1` shape is historical and
superseded; it remains readable only in append-only evidence and is not valid
for this standing-presentation gate.

## 3. Call graph and boundaries

1. `CodexNativeImageGenPlanner` detects only explicit Professional E-Commerce
   poolside seated/standing exact-N=2 coverage and attaches the typed contract
   to `ecommerce_creative_context`. Obvious negative or exclusive wording such
   as `no standing`, `do not create a standing image`, `avoid standing`,
   `exclude standing`, `seated only`, or `standing only` must not produce this
   hard contract. This bridge is intentionally conservative until a higher
   server-owned structured deliverable-intent owner exists.
2. `V3LLMBrainAdapter` allowlists and validates the typed contract. Present but
   invalid payloads become a sanitized invalid sentinel and are blocked before
   Remote Brain.
3. `prompts.py` includes the existing compact Remote Brain schema plus the
   closed pose receipt fields when the contract is present.
4. `ScenarioRuntime` validates that the Remote Brain image set plan returns the
   exact pose role, standing requirements, and standing presentation
   requirements for each output and freezes that receipt into deliverable
   metadata.
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

## 3A. Shared Brain response schema compatibility

`BrainOutputEvidenceContract` is a shared Remote Brain response model. E25 adds
optional fields to that model:

- `professional_ecommerce_pose_role`
- `standing_pose_requirements`
- `standing_presentation_requirements`

Compatibility impact:

- The fields are optional and require no migration for historical General,
  Photography, Standard, or non-pose E-Commerce responses.
- The added presentation field is part of
  `professional_ecommerce_pose_contract_v2`; v1 evidence is historical and is
  not accepted for a new exact-N=2 standing gate.
- The compact return schema emits these fields only when
  `ecommerce_creative_context.professional_ecommerce_pose_contract` is present
  and validated.
- General and Photography payloads must not receive the E25 fields or
  poolside role vocabulary.
- A present-but-invalid pose contract is converted by the adapter into a
  sanitized invalid sentinel and blocked by Runtime before Remote Brain; raw
  invalid values are not forwarded.
- Missing, unknown, duplicate, or contradictory pose receipts from Remote Brain
  are rejected by the Professional E-Commerce runtime path before host
  materialization.

This compatibility note narrows the shared schema change to a dormant optional
projection. It does not authorize any shared pose rule, General Template
behavior, Provider behavior, MCP behavior, storage mutation, receipt creation,
slot write, or activation.

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
- negative-intent, missing-role, and non-poolside isolation so the contract is
  not created from token coincidence;
- missing pose receipt fail-closed before materialization;
- wrong `standing_poolside` requirements fail-closed before materialization;
- missing, duplicated, or wrong `standing_presentation_requirements` fail-closed
  before materialization;
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
