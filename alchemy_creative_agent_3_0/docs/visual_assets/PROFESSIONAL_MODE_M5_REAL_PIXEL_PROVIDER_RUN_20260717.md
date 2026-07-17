# Professional Mode M5 Real-Pixel Provider Run — 2026-07-17

## Status

```text
V3 DEFAULT PROVIDER AUTHORIZED BY USER: YES
REMOTE BRAIN: USED, FALLBACK: FALSE
GPT IMAGE 2 PIXELS: RECEIVED
SHARED VISION REVIEW: REAL HYBRID RESULT RECEIVED
ONE BOUNDED RETRY / DELIVERY PREFERENCE: COMPLETED
THREE-VIEW FACE PACK: NOT COMPLETED
M5: BLOCKED, NON-COUNTING EVIDENCE
NO PRODUCTION / GATE C-D / P10 CLAIM
```

This is an append-only evidence record for one user-authorized run on the
isolated Professional Mode branch. It uses the existing V3 Product API,
Remote Brain, GPT Image 2 Provider, and shared review seam. It does not create
a second Provider, reviewer, retry loop, storage path, browser route, or MCP
route.

## Runtime and authorization boundary

- Branch was rebased to the then-current `origin/main@756b0c7`; the default
  V3 Provider configuration was used without MCP.
- The V3 settings-backed credential was used only in-process after the user
  explicitly authorized this test. The key value is not recorded, exported,
  or persisted by this evidence.
- Provider metadata reported `provider=openai_gpt_image` and
  `model=gpt-image-2`. The configured V3 upstream host was not reclassified as
  the official OpenAI endpoint, and this run is not official Provider Gate
  evidence.
- Remote Brain metadata reported `provider=deepseek`,
  `model=deepseek-v4-pro-260425`, `llm_used=true`, and `fallback_used=false`.
- The production/browser gates remain closed.

## Source and output fingerprints

Only hashes and safe identifiers are retained; the private source path and
prompt body are intentionally omitted.

```text
source_filename: portrait_reference.png
source_bytes: 344872
source_sha256: 19A7F099245086B4310299F18A9972CBA0703523E581DBEA71255D35C1032917
job_id: job_64987888ab
candidate_id: candidate_cd7bf28c53
output_id: v3_output_85311475617d40c2ad01
asset_id: asset_28d317e518
output_original_sha256: 1994CEEF21CF1B03AB14F4792D60083EA07C3145C28E09F34A306C19A064A3EE
output_preview_sha256: 3A35F16FE35D2C2622A1B5F77871B6D8353ADA123817A8FFFC81624B0B2C796B
output_thumbnail_sha256: 17ADAC397B9E1D5D201BB7C5BB02DD715A4314F7AC48D5EB4674BD3C8CA54AFF
```

The Provider materialized one PNG output at 1024×1536. Its safe provenance
reported two derived identity references from the one uploaded source:
`portrait_identity_crop` (`feature_detail`) and
`portrait_identity_geometry_crop` (`head_geometry`). The full source frame
was suppressed from Provider input, the source integrity fingerprint was
retained, and `required_unavailable=[]`, `unresolved=[]`, and
`operation_outcome=pixels_received` were recorded.

## Review and acceptance boundary

The shared `VisionOutputInspector` was then run against the same materialized
output with the existing V3 settings-backed review route. A short 15-second
probe timed out, but the normal bounded review budget returned a real
`hybrid`/`verified` inspection. The review result was:

```text
review_mode: hybrid
verification_state: verified
review_status: fail_retryable
issue_codes: identity_drift, face_shape_drift,
  eye_shape_or_spacing_identity_drift, human_skin_or_retouch,
  human_rendering_artifact, composition_mismatch
```

This confirms the review path is reachable but slow through the configured
upstream. A second controlled Product API run then exercised exactly one
shared visual retry. The initial candidate failed the frozen prompt-owned
channel gate; the retry candidate became the preferred delivery output.

```text
job_id: job_0970cc7a64
initial_output_id: v3_output_b47b68ddaf7642b1b3f3
initial_attempt: 0
initial_score: 0.6216
initial_hard_gate: false
initial_hard_gate_failure: prompt_owned_channel_not_respected
retry_output_id: v3_output_527ab53537484abf912b
retry_attempt: 1
retry_score: 0.767
retry_hard_gate: true
delivery_preferred_output: true
delivery_preference_policy: doc95_reviewed_best_attempt
retry_reason_codes: source_hair_overinherited, prompt_owned_channel_ignored, overexposed_washout
```

The Product API harness ended while formatting an internal diagnostic field
that does not exist on `PlanningResult`; this did not undo the materialized
outputs or their append-only delivery preference. Consequently:

- the first diagnostic review receipt is non-persisted, while the controlled
  Product API retry preference is persisted in both output records;
- the retry output is the preferred one-output delivery for this smoke job;
- this is not an activated Face Identity anchor view;
- no output was activated as an anchor-pack view;
- no final delivery is certified.

The generated front-like portrait was visually inspected only as a
non-certifying diagnostic. It broadly retained the source person's dark bob,
eye/nose/mouth arrangement, and natural complexion direction, but appeared
more symmetrized/generic than the source. This observation must not be used as
an automated score or as M5 acceptance.

## Why M5 remains blocked

M5 requires the complete serial evidence chain:

```text
front: 3 candidates -> likeness-first winner
three-quarter: 3 candidates from root + front winner -> winner
profile: 3 candidates from root + front + three-quarter winners -> winner
each stage -> shared pixel review -> bounded retry -> final winner
all three winners -> human comparison and activation evidence
```

This run proves that the existing V3 default Brain/Provider can receive the
supplied portrait, return one real GPT Image 2 artifact, and exercise one
shared Vision review -> bounded retry -> best-attempt preference loop through
the Professional binding. It does not prove the complete three-view quality
contract, all-stage retry/final-winner closure, Provider Gate C/D, General
Gate D, Photography P10, E-Commerce Gate C/D, or production readiness.

## Follow-up

The next run must start the full serial three-view contract: three front
candidates, then three three-quarter candidates conditioned on the root plus
the selected front winner, then three profile candidates conditioned on all
prior winners. Each stage needs persisted shared review/retry/final-winner
evidence, followed by human comparison and explicit Face Identity activation.
Until that chain is complete, Professional Mode remains blocked and
non-production.
