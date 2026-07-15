# E20 Doc127 Phase 4 E-Commerce Gate Execution Pack

Status: acceptance preparation only; not a production release or a Gate C/D
pass

## Purpose

E20 is the E-Commerce operator pack for [Doc127](../127_V3_FINAL_ACCEPTANCE_RUNBOOK_AND_PRODUCTION_RELEASE_GATE.md)
Section 9. It translates the shared campaign requirements into a restricted
evidence manifest and a repeatable browser checklist without creating a new
recipe, Provider, reviewer, retry loop, or production flag.

The only permitted forward path remains:

```text
explicit ecommerce_template + authorized product facts + seller constraints
  + versioned platform evidence
-> remote Central Brain writes exactly N whole-image directions
-> shared GPT Image 2 generation/edit with provider-native product input
-> shared vision_model/hybrid review and bounded retry
-> append-only history and only final winners in ordinary delivery
```

`CopyRenderPlan`, static platform/category shots, semantic visual slots,
locally authored camera/crop/scene direction, default selling copy, font, OCR,
canvas/overlay composition, a private retry loop, or an unreviewed manual
assertion cannot satisfy any E20 row.

## Authority and Phase Ordering

Doc127 is the operational campaign authority. E17-E19 remain the E-Commerce
architecture, fail-closed, and evidence authorities. If they appear to differ,
Doc127's release gate decides when a result may count while E17-E19 decide the
E-Commerce boundary.

Do not run a current-build Gate C until Doc127 Sections 5-8 have passed for the
same controlled release environment. Then run N=1 Gate C before the separate
N=1, 2, 4, and 7 Gate D requests. The N=1 Gate C run may be cited as one Gate
D row only if its commit, deployment, material registration, and evidence
fields match exactly; otherwise it remains a separate run.

## Current Hold — 2026-07-15

The intended frozen source is `origin/main@8c9760d`. The mainline operator
reported that local port 8017 is currently serving
`D:\AI\Alchemy Media Agent System-codex-session@e458d23`, not that frozen
commit. Therefore:

```text
8017 observations at e458d23 -> environment_stale -> non-counting evidence
```

Do not perform a new Provider request or browser Gate C/D on that process, and
do not change its production flags. Wait for the mainline operator to confirm a
fresh controlled instance and its effective runtime commit. The historical
single-case E19 Gate C record is comparison material only; it is not a
current-release pass.

## Restricted Evidence Manifest Template

Create this manifest outside Git in the restricted campaign directory specified
by Doc127. The repository must contain neither source/generated images,
screenshots, endpoints, secrets, raw Provider bodies, nor personal data.

```json
{
  "acceptance_run_id": "ACPT-YYYYMMDD-ecommerce-N#-shortcommit",
  "timestamp_timezone": "",
  "code_commit": "",
  "deployment_id": "",
  "config_fingerprint": {
    "remote_brain_effective": false,
    "gpt_image_2_effective": false,
    "gateway_managed_failover_effective": false,
    "vision_review_effective": false,
    "specialist_gate_enabled_only_in_controlled_instance": false
  },
  "template": "ecommerce_template",
  "scenario": "ecommerce",
  "requested_count": 0,
  "requested_size": "",
  "material_rights_reference": "restricted-material-register-id",
  "material_watermark_check_reference": "",
  "product_fact_reference": "",
  "seller_request_reference": "",
  "platform_evidence_version": "",
  "frozen_envelope_or_plan_id": "",
  "brain": {
    "provider": "",
    "model": "",
    "llm_used": false,
    "fallback_used": true,
    "natural_language_plan_count": 0,
    "provenance_reference": ""
  },
  "provider": {
    "provider": "openai_gpt_image",
    "model": "gpt-image-2",
    "outer_operation_count": 0,
    "native_reference_binding_count": 0
  },
  "outputs": [
    {
      "output_id": "",
      "candidate_hash": "",
      "mime_type": "",
      "dimensions": "",
      "review_mode": "",
      "review_verdict": "",
      "verification_state": "",
      "confidence": null,
      "final_delivery": false
    }
  ],
  "retry_history_reference": "",
  "refresh_reopen_result": "",
  "browser_evidence_reference": "",
  "human_review": {
    "reviewer": "",
    "product_truth": "hold",
    "request_relevance": "hold",
    "commercial_usability": "hold",
    "pixel_and_requested_copy_accuracy": "hold",
    "decision": "hold"
  },
  "gate_result": "blocked",
  "block_reason_codes": []
}
```

The fingerprint records effective booleans only. It must not include tokens,
endpoint URLs, account identifiers, unredacted prompts, or configuration
values. Material and browser references point to restricted evidence, not a
repository path.

## Pre-Run Stop Checklist

All items must be true before spending a real Provider request:

- [ ] The running controlled process reports `8c9760d` or a later mainline
      commit frozen into this campaign; it is not a stale local process.
- [ ] The mainline operator records a clean controlled deployment identity,
      storage namespace, timezone, and non-sensitive configuration fingerprint.
- [ ] The effective process—not merely a shell variable—can reach the remote
      Brain, selects GPT Image 2, uses the gateway-managed single outer
      materialization policy, and produces `vision_model` or `hybrid` review.
- [ ] The E-Commerce specialist gate, if needed for this run, is enabled only
      in the named controlled instance. No production default is changed.
- [ ] The material register has a written ownership/licence, source, allowed
      evaluation scope, watermark check, asset ID, and `product_reference`
      role for this exact run.
- [ ] Doc127 Phases 0-3 are passed or formally attached as current-build
      evidence. A historical E19 case alone is insufficient.
- [ ] The operator has a restricted evidence folder and reviewer assignment.

If any row is false, set `gate_result=blocked`, record only the appropriate
reason codes, and make no workaround request. In particular, do not replace a
reference with text-only generation, use an old browser process, or silently
change model/provider/retry policy.

## Browser Acceptance Checklist

Use the real browser only after the pre-run checklist passes. Capture the
listed screenshots and redacted status/provenance responses in the restricted
folder, then record their references in the manifest.

### Common steps for every N

1. Start a new project and explicitly select `ecommerce_template`. Verify that
   a General request containing product or marketplace words remains General;
   it must not enter E-Commerce by keyword.
2. Upload/register the authorized product reference as `product_reference`.
   Enter only product facts, seller-approved constraints/copy, and the chosen
   versioned platform evidence. Do not enter a shot list, static slot,
   camera/crop instruction, default claim, or local-text instruction.
3. Request the test's exact N. Before generation, inspect the redacted job
   record: `llm_used=true`, `fallback_used=false`,
   `image_set_plan.image_count = N`, N natural-language directions, and N
   deliverables in the frozen envelope. Any deviation is blocked before
   Provider execution.
4. Verify every operation uses GPT Image 2 and a shared provider-native product
   binding. There must be no V3/SDK duplicate outer operation and no local
   image/compositor output.
5. For each physical output, require a verified `vision_model` or `hybrid`
   review. `metadata_only`, local-only, manual confirmation, missing review,
   or failed review is held/blocked and cannot enter ordinary delivery.
6. If review calls shared bounded retry, retain the rejected attempt in history
   and inspect only the later final winner. Do not use selection/delete or a
   user slot-redo action as a retry. The E-Commerce UI must not show a
   pseudo-enabled "redo this slot" control.
7. Refresh and reopen the project. Verify final winners, Brain provenance,
   review/retry history, factual provenance, and held/blocked reasons remain
   queryable; ordinary results show only final deliveries.
8. The human reviewer records product truth, seller-request relevance,
   commercial usability, final-pixel quality, and literal requested-copy/claim
   accuracy where copy was explicitly requested.

### Count matrix

| Run | Gate role | Additional evidence that must match the manifest |
| --- | --- | --- |
| N=1 | Gate C first; also a Gate D row only when all evidence is identical | one Brain direction, one provider operation, one reviewed terminal output, one final delivery after refresh |
| N=2 | Gate D | two directions, two deliverables, two per-output terminal review states, two final deliveries or individually diagnosed holds |
| N=4 | Gate D | four directions and exact four-output lifecycle; verify no hidden truncation or card duplication after refresh |
| N=7 | Gate D | seven directions, seven frozen deliverables and shared operations; if a declared capacity is below seven, verify structured pre-generation block and zero generated subset |

The matrix does not define the visual content of any image. The remote Brain
decides the natural-language whole-image directions from the admitted facts and
the user's request.

## Offline Contract Evidence to Attach

Attach the relevant test result and commit to every Phase 4 package. At a
minimum it must prove:

- E-Commerce needs explicit selection; General and Photography Brain requests
  do not receive `ecommerce_creative_context`, platform rules, E-Commerce
  roles, or static-suite semantics.
- unavailable Brain, `llm_used != true`, `fallback_used = true`, empty,
  malformed, incomplete, or count-mismatched plans block before Provider
  execution without a local fallback image.
- requests for N=1/2/4/7 preserve exact counts; a declared capacity mismatch
  becomes structured `blocked`, not truncation.
- legacy recipe, slot, overlay, `CopyRenderPlan`, and text-pixel fields are
  read-compatible only and cannot enter a new Brain request, provider prompt,
  envelope, or delivery result.
- browser code has no E-Commerce slot-redo control and no static suite/overlay
  controls; retry attempts are not ordinary delivery cards.

## E19 Update Rule

Only after a current-build controlled run is complete, update E19 with its
non-sensitive commit, deployment fingerprint, restricted evidence reference,
job/output IDs, count, review verification, retry/delivery result, refresh
result, and human decision. Mark only the specific gate row passed. Do not
upgrade E-Commerce production status until every Doc127 Section 9 Gate C and
Gate D row is accepted.
