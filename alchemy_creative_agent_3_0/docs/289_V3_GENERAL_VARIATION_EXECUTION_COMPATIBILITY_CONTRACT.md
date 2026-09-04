# V3 General Variation Execution Compatibility Contract

Status: active implementation contract.

## Purpose

V3 General multi-image real generation keeps the early ability to make each
output materially different while preserving Brain-first prompt ownership.
Doc59 role and prompt recipes are historical compatibility data. They are not
sent to the remote Brain and do not author provider prompts.

This contract is a narrow bridge from the existing
`ModeAwareRoleDirector` plan to the two Brain-owned semantic stages:

1. the compact real-image planning request; and
2. the frozen canonical-prompt sign-off context.

The Provider still receives only the Brain-signed complete prompt. Doc269,
Doc281, Review, and Output bindings remain authoritative and unchanged.

## Scope

The contract applies only when all of these are true:

- `scenario_id=general_creative`;
- `template_id=general_template`;
- the existing `suite_direction` capability is active; and
- the requested image count is greater than one.

The bridge preserves the existing V3 Native planning range of 2 through 16
outputs. The four historical role families are reusable semantic starting
points for larger batches; they do not impose a new four-output limit.

It is absent for a single image, inactive suite direction, and specialized
templates such as E-Commerce and Photography. General remains scenario-neutral;
this contract does not define a professional deliverable map.

## Contract Shape

The versioned typed value is `v3_general_variation_execution_v1`:

```json
{
  "contract_version": "v3_general_variation_execution_v1",
  "contract_digest": "sha256 of the canonical contract contents excluding contract_digest",
  "mode": "delivery_suite",
  "requested_image_count": 3,
  "preserve_subject": true,
  "preserve_style": true,
  "outputs": [
    {
      "output_index": 1,
      "output_purpose": "primary_presentation",
      "variation_axes": ["presentation", "scale", "layout"],
      "must_keep": ["subject_identity"],
      "avoid_drift": ["duplicate_still"]
    },
    {
      "output_index": 2,
      "output_purpose": "detail_focus",
      "variation_axes": ["detail", "framing"],
      "must_keep": ["subject_identity"],
      "avoid_drift": ["duplicate_still"]
    },
    {
      "output_index": 3,
      "output_purpose": "context_expansion",
      "variation_axes": ["context", "depth", "placement"],
      "must_keep": ["scene_continuity", "user_intent"],
      "avoid_drift": ["unrelated_scene"]
    }
  ]
}
```

`variation_axes` use a finite neutral vocabulary such as `presentation`,
`framing`, `scale`, `layout`, `expression`, `attention`, `pose`, `gesture`,
`viewpoint`, `context`, `detail`, `material`, `styling`, `mood`, `palette`,
`depth`, `placement`, `concept`, and `composition`. The projection contains
no role IDs or labels, shot/camera/light/crop rules, `prompt_pressure`, review
recipes, `prompt_additions`, or `negative_additions`.

`output_purpose`, `must_keep`, and `avoid_drift` are short semantic evidence
for the Brain. The Brain interprets them with the user request, references,
Human Realism, and the frozen activation/constraint contracts, then writes one
complete prompt per output. Local code never appends a variation phrase.

`contract_digest` is a stable SHA-256 binding over the canonical JSON form of
the contract with the digest field excluded. The director binds it once;
runtime, prompt transport, and the finalizer validate the same value. The
finalizer response must include one `VariationExecutionReceipt` per output:
the exact contract version and digest, matching `output_index`, status
`approved` or `rewritten`, and owner `remote_v3_llm_brain`. The receipt is
audit data only and never renderer wording.

## Compatibility

The contract is optional in `VisualCapabilityClusterResult` and in the frozen
ledger projection. Missing or invalid contract data in an old record is read as
no contract; it does not block single-image or specialized execution. Existing
role plans remain readable for history and existing compatibility tests, but
only this compact projection may cross the real-image Brain boundary.

## Acceptance

- General multi-image real requests expose distinct semantic output duties to
  the Brain without forwarding the old role recipe.
- Single-image requests do not receive a variation execution contract.
- Specialized templates do not receive the General contract.
- The canonical finalizer sees the same typed contract, while Provider,
  Review, Output, Doc269, and Doc281 bindings remain unchanged.
- A missing or mismatched digest, required contract, or finalizer receipt
  fails closed for a newly enforced General multi-image run; old records
  without the optional contract remain readable.
