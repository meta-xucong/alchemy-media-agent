# 96 V3 High-Fidelity Portrait Identity Metric And Local Repair Spec

## 1. Purpose

Doc96 is the implementation authority for moving universal portrait identity
from prompt-only guidance and subjective review toward measurable, provider-
aware execution.

The target is not a scene recipe. The target is:

```text
preserve the exact uploaded person's underlying identity
keep makeup, hair, wardrobe, light, scene, camera, mood, and finish prompt-owned
measure identity with more than one independent signal
repair only the identity region when the rest of the image is already good
keep the best attempt and stop after a bounded budget
```

Doc96 applies to every V3 template that produces a real person from an
identity reference. General Template is the first active consumer. Future
Photography, E-Commerce, Brand, and New Media templates consume the same
foundation capability and may add deliverable roles, never duplicate identity
execution.

## 2. Authority And Compatibility

Doc96 extends, and does not replace:

```text
Doc53 bounded retry and loop safety
Doc56 identity versus natural variation
Doc73 first-output identity anchor
Doc75 strict identity review
Doc80 provider reference transport compression
Doc83 retry delivery presentation
Doc85 image-to-image truth
Doc86 bone-structure identity
Doc87 identity/style separation
Doc88 prompt/reference balance
Doc90 user-facing strong person consistency
Doc93 reference-channel ownership
Doc94 universal shared-runtime governance
Doc95 complementary evidence and best-result selection
```

Doc96 is authoritative when older text implies that:

```text
all identity judgment must come from an LLM
image-edit input fidelity may remain at provider default
an identity failure always requires full-frame regeneration
face embeddings may never be computed even ephemerally
the latest successful retry automatically becomes delivery output
```

The compatible rule is:

```text
identity vectors may be computed ephemerally for current-output evaluation
identity vectors must not be persisted in Project, Brand Memory, logs, or API
provider features are capability-negotiated and auditable
retry and repair remain bounded and append-only
```

Doc96 does not change Project Mode, ScenarioRuntime, Scenario Packs, template
activation, account isolation, output count, or the user's existing Advanced
controls.

## 3. Measured Current Gap

The accepted same-project regression produced:

```text
earlier subjective same-person readability: about 0.58
Doc95 initial result:                    about 0.68
Doc95 retry result:                      about 0.35
```

The system correctly retained the 0.68 result. However, provider execution did
not meet Doc95's strong commercial identity gate.

Audit findings:

```text
OpenAI-compatible image edits do not request input_fidelity=high
provider prompts can approach 14,700 characters even for a modest user prompt
identity review is multimodal-LLM based but has no local identity metric
identity retry regenerates the complete frame even when only the face drifts
```

These are general execution gaps. They must not be corrected with historical,
costume, age-market, ethnicity, lighting, or product-category branches.

## 4. Architecture Placement

No new top-level visual framework is allowed.

```text
Visual Capability Cluster
  Portrait Identity Capability
    IdentityEvidenceBuilder          existing Doc95 responsibility
    IdentityExecutionPolicy         extended by Doc96
    IdentityMetricGate              new child component
    IdentityLocalRepair             new child component
    BestResultSelector              existing Doc95 responsibility

Provider Adapter
  ImageEditCapabilityNegotiator     transport-only capability
```

Ownership:

```text
visual_cluster/identity_metric.py
  face detection, alignment, ephemeral metric calculation, confidence

visual_cluster/portrait_identity.py
  identity dimensions, thresholds, fusion policy, repair eligibility

visual_cluster/vision_inspector.py
  merges objective metric evidence with multimodal review

provider_reference.py
  provider-safe evidence and repair canvas preparation

generation_router/providers.py
  requests high fidelity, emits repair transport metadata, compiles one
  protected identity block

openai_image.py
  sends input_fidelity and optional mask, negotiates unsupported parameters

product_api/service.py
  selects full retry versus local repair, enforces budget, keeps best result
```

Central Brain may decide whether strong person consistency applies. It must not
detect faces, calculate embeddings, create masks, set biometric thresholds, or
directly call repair providers.

## 5. Runtime Contracts

### 5.1 Image Edit Capability

```python
class ImageEditCapabilityReport:
    provider_key: str
    model: str
    input_fidelity_requested: str | None
    input_fidelity_applied: str | None
    support_state: str  # unknown | supported | unsupported | degraded
    fallback_reason: str | None
    checked_at: str
```

Cache key:

```text
normalized base_url + provider name + model
```

An explicit unsupported-parameter response may set `unsupported`. A timeout,
rate limit, gateway error, connection error, or generic 5xx must never mark the
feature unsupported.

### 5.2 Identity Metric Result

```python
class IdentityMetricResult:
    status: str  # pass | warning | fail | unavailable
    calibrated_score: float | None
    raw_cosine_similarity: float | None
    geometry_score: float | None
    detection_confidence: float
    metric_confidence: float
    reference_face_count: int
    output_face_count: int
    selected_reference_index: int | None
    selected_output_index: int | None
    output_face_box: list[float] | None
    reason_codes: list[str]
```

No embedding values appear in this contract.

### 5.3 Identity Review Fusion

```python
class IdentityReviewFusion:
    objective_metric_score: float | None
    multimodal_same_person_score: float | None
    geometry_relationship_score: float | None
    fused_identity_score: float | None
    fusion_confidence: float
    applied_weights: dict[str, float]
    hard_gate_passed: bool
    reason_codes: list[str]
```

### 5.4 Local Repair Plan

```python
class IdentityLocalRepairPlan:
    applies: bool
    source_output_id: str | None
    repair_canvas_path: str | None
    repair_mask_path: str | None
    identity_reference_asset_ids: list[str]
    input_fidelity: str
    protected_prompt_channels: list[str]
    repair_dimensions: list[str]
    max_attempts: int
    blocked_reason: str | None
```

## 6. High-Fidelity Provider Execution

High input fidelity applies when all are true:

```text
the operation has one or more accepted reference images
the resolved policy assigns hard portrait identity or hard product identity
the selected provider is an OpenAI-compatible image-edit provider
the user did not explicitly disable strong consistency
```

Default:

```text
portrait identity truth: input_fidelity=high
product identity truth:  input_fidelity=high
style-only reference:    provider default
text-only generation:    not applicable
```

Compatibility behavior:

1. Request `input_fidelity=high` while support is `unknown` or `supported`.
2. If the provider returns a specific unsupported/unknown parameter 400, retry
   the same operation once without that parameter.
3. Cache `unsupported` for a bounded TTL, default 24 hours.
4. Do not infer unsupported state from any transient failure.
5. Record requested, applied, support state, and fallback reason on every
   generated output.
6. Never silently claim strong high-fidelity execution when the provider
   degraded to default fidelity.

Transport retries caused by 5xx, timeout, connection, or rate limits remain
Doc81 provider-failure retries. They do not consume the Doc96 visual repair
budget.

## 7. Reference Ordering

Normal strict portrait edit order:

```text
1. feature-detail identity evidence
2. head-geometry identity evidence
3. explicit user-owned non-identity references, if any
```

Local repair order:

```text
1. current generated output as repair canvas
2. feature-detail identity evidence
3. head-geometry identity evidence
```

Both identity derivatives remain evidence from one person. The repair canvas is
not an identity source. It owns only the already-approved prompt channels that
must remain unchanged outside the repair region.

## 8. Objective Identity Metric

### 8.1 Implementation

Use a commercially compatible local baseline:

```text
YuNet: face detection and five landmarks
SFace: aligned face representation and cosine similarity
OpenCV CPU inference: no GPU requirement
```

Models are version-pinned, SHA-256 verified during image build, and stored in a
read-only runtime model directory. Model unavailability must degrade to the
existing multimodal review and must not block ordinary generation.

### 8.2 Face Selection

Reference image:

```text
prefer the highest-confidence sufficiently large face
reject ambiguous multiple-face references unless an explicit face region exists
```

Generated output:

```text
prefer the largest face near the expected subject region
use asset composition metadata as a soft tie-breaker
do not silently compare a background bystander
```

### 8.3 Calibration

Raw SFace cosine similarity is not displayed as a 0-1 product quality score.
Calibration uses a frozen regression set containing:

```text
same-person cross-light examples
same-person cross-angle examples
same-person cross-makeup and hairstyle examples
different-person same-demographic hard negatives
different-person similar-beauty-type hard negatives
```

The calibrated score must be monotonic and versioned. Thresholds cannot be
changed merely to make acceptance numbers rise.

### 8.4 Fusion

Default high-confidence weights:

```text
calibrated SFace identity signal       55%
pose-normalized facial geometry        25%
multimodal same-person review          20%
```

If detection, alignment, occlusion, profile angle, or face size reduces metric
confidence, redistribute unavailable weight to geometry and multimodal review.
Never treat an unavailable local metric as zero.

Hard failures:

```text
clear different-person metric result
wrong face selected in a multi-person output
same beauty type but materially different facial geometry
```

Allowed changes do not reduce identity by themselves:

```text
makeup, hair styling, wardrobe, expression, pose, camera, light, scene, mood
```

## 9. Internal Prompt Materialization

The complete user prompt remains lossless. Doc96 does not restore lossy VPS
prompt compression.

The system must instead deduplicate framework-owned guidance:

```text
one user-direction block                         lossless
one identity operation block                    protected
one resolved reference-channel block            protected
one human-realism block                         deduplicated
one output-safety block                         deduplicated
one retry/repair delta block, only when active   protected
```

Target internal overhead, excluding the user prompt:

```text
preferred: <= 4,500 characters
hard warning: > 6,000 characters
```

Do not shorten explicit user details to meet this target. Remove repeated
module prose, repeated negative concepts, and repeated same-person synonyms.

Prompt audit metadata:

```text
user_direction_chars
internal_guidance_chars
final_provider_prompt_chars
deduplicated_rule_count
protected_sections
prompt_budget_warning
```

## 10. Identity-Local Repair

Local repair is eligible when:

```text
an identity truth reference exists
the output face can be detected with sufficient confidence
identity score is below pass threshold
prompt-owned channel score and commercial composition are already usable
there is no severe body, policy, watermark, collage, or full-frame failure
the local repair budget has not been consumed
```

Mask construction:

```text
derive a face polygon from detected landmarks and bounding box
include forehead, temples, cheeks, jaw corners, and chin
exclude most hairstyle and all background
expand conservatively and feather the boundary
match the exact dimensions of the prepared first provider image
store as an ephemeral PNG under provider reference cache
```

Repair instruction:

```text
restore the uploaded person's face width/length, brow-eye, nose-mouth,
cheek-jaw, and chin relationships inside the mask
preserve the current output's prompt-owned makeup direction, expression,
hairstyle, wardrobe, pose, scene, light, camera, mood, and finish
do not beautify, face-slim, enlarge eyes, sharpen the chin, or cast a new model
```

The provider receives the current output as image 1, because the mask applies
to the first input image. Identity evidence follows as image 2 and image 3.

After repair, run the complete fused review again. Accept the repair only when:

```text
identity improves by at least 0.06, or crosses the pass threshold
prompt-owned channel score falls by no more than 0.03
human realism falls by no more than 0.03
commercial finish falls by no more than 0.03
no new hard failure appears
```

Otherwise retain the earlier candidate.

## 11. Bounded Decision State Machine

Default thresholds after calibration:

```text
fused identity >= 0.82
  pass

0.72 <= fused identity < 0.82
  one identity-local repair if eligible

fused identity < 0.72
  one full high-fidelity retry with structured identity deltas

after one repair or full visual retry
  inspect, compare, keep best, stop
```

Strict mode may retain the existing two-attempt ceiling, but at most one
attempt may be identity-local repair. Standard mode retains one visual-quality
attempt. Explore mode does not automatically enforce identity unless the user
enabled High person consistency.

The same repeated identity issue must not trigger alternating full retry and
local repair loops.

## 12. Persistence, Privacy, And Audit

Persist:

```text
calibrated identity score
metric status and confidence
model/version identifiers
face count and selected face index
normalized face box
reason codes
fidelity requested/applied/fallback metadata
repair attempt metadata
```

Do not persist:

```text
face embeddings
raw biometric vectors
aligned face tensors
temporary masks after retention cleanup
provider secrets
```

Project and Brand Memory continue storing user-approved images and semantic
identity summaries only. Doc96 does not make biometric data long-term memory.

## 13. Failure And Degradation Rules

```text
OpenCV unavailable:
  multimodal review remains active; mark objective metric unavailable

model files missing or hash mismatch:
  disable local metric and repair; emit operator warning

no face detected:
  do not fabricate a score; use multimodal review/manual warning

multiple ambiguous faces:
  do not repair until subject face is resolvable

mask creation failed:
  use bounded full retry, not unmasked face replacement

input_fidelity unsupported:
  degrade once, record accurately, keep provider path usable
```

User-facing UI remains beginner-safe. It may say:

```text
已检查人物一致性
已保留更像原人物的结果
```

It must not expose embeddings, cosine similarity, OpenCV, model names, masks,
provider capabilities, or biometric terminology.

## 14. Implementation Order

### Phase A: Documentation And Contracts

1. Add Doc96 authority to AGENTS, root rules, README, and delivery plan.
2. Clarify Doc56: no persistent biometric data; ephemeral evaluation is allowed.
3. Add provider fidelity, identity metric, fusion, and repair contracts.

### Phase B: High-Fidelity Transport

1. Add configurable `input_fidelity` to internal image request variables.
2. Apply `high` only for hard portrait/product identity references.
3. Add unsupported-parameter fallback and capability cache.
4. Persist fidelity audit metadata.

### Phase C: Metric Gate

1. Add pinned YuNet and SFace model bootstrap with SHA verification.
2. Add lazy OpenCV metric provider.
3. Add face selection, alignment, cosine calculation, calibration, and evidence.
4. Merge metric evidence into vision inspection and delivery scoring.

### Phase D: Prompt Cleanup

1. Inventory provider prompt sections.
2. Preserve user direction exactly.
3. Deduplicate internal rules by semantic family.
4. Emit prompt composition audit metadata.

### Phase E: Local Repair

1. Build repair eligibility from fused review.
2. Resolve the failed output file and identity source.
3. Prepare repair canvas and feathered face mask.
4. Execute masked high-fidelity edit.
5. Reinspect and retain only a demonstrably better result.

### Phase F: Delivery And Deployment

1. Keep all attempts append-only.
2. Show only preferred outputs in beginner surfaces.
3. Run full local regression and model hash audit.
4. Deploy without changing V1/V2 storage, accounts, or service boundaries.

## 15. Required Tests

High-fidelity transport:

```text
strict portrait reference sends input_fidelity=high
strict product reference sends input_fidelity=high
style-only reference does not force high fidelity
specific unsupported-parameter 400 retries once without the parameter
5xx and timeout never poison capability cache
metadata reports requested/applied/fallback truthfully
```

Metric:

```text
same image and light augmentation score strongly
same person with changed color/brightness remains above calibrated threshold
different-person hard negatives remain below threshold
multiple faces use the intended subject or mark ambiguity
unavailable OpenCV/model files degrade safely
no embedding appears in serialized contracts or logs
```

Prompt:

```text
full user prompt survives byte-for-byte in protected direction
identity guidance occurs once
reference ownership guidance occurs once
internal overhead warning appears above threshold
no historical scene/category branch returns
```

Repair:

```text
repair canvas is first input
mask dimensions equal prepared canvas dimensions
mask excludes most hairstyle/background
repair runs at most once
repair is blocked when composition or policy has a hard failure
worse repair never replaces the original
better repair becomes preferred output
```

Regression:

```text
requested image count remains exact
Project history remains append-only
General/E-Commerce boundaries remain unchanged
V1/V2/Lab runtime independence remains unchanged
desktop/H5 beginner UI exposes no engineering terms
```

## 16. Real Acceptance Matrix

Use at least six consented identity references across:

```text
bright modern portrait
low-key cinematic portrait
indoor commercial portrait
outdoor documentary portrait
changed wardrobe and hairstyle
changed camera distance and head angle
```

At least 36 evaluated outputs are required before claiming stable 0.8+.

Acceptance:

```text
mean fused identity score >= 0.83
10th percentile fused identity score >= 0.78
at least 85% of outputs >= 0.80
prompt-owned channel score >= 0.88
no source scene/hair/light leak used to inflate identity
no unbounded retries
no persisted face embeddings
full V3, frontend/API, root, compile, static, and deployment audits pass
```

One lucky output above 0.80 is evidence, not acceptance. Threshold mapping and
reviewer weights must remain frozen during a comparison run.

## 17. Non-Goals

Doc96 does not add:

```text
face swapping
celebrity cloning
template-specific portrait packages
new beginner controls
stored biometric profiles
scene-specific identity prompts
automatic Brand Memory writes
unbounded candidate generation
```

The capability remains a universal, consent-aware quality layer for preserving
the user's supplied person across prompt-owned visual transformations.

## 18. Live Acceptance Corrections

Production comparisons established two binding corrections:

1. the accepted Doc95 wide feature and head-geometry evidence remain unchanged;
2. global desaturation, face-only recropping, hair-color neutralization, and
   other pixel rewrites of either identity evidence image are rejected because
   repeated real outputs lost same-person fidelity even when style leakage
   decreased;
3. the identity detector threshold is 0.5, with largest confident-face
   selection, so partially occluded and angled commercial portraits are less
   likely to lose objective review coverage;
4. objective identity review must still run when the multimodal reviewer is
   unavailable or returns a provider error;
5. a retry whose visual review is unavailable may remain in append-only project
   history but may not replace a previously reviewed candidate for the same
   asset role;
6. reviewer failure never becomes permission to lower the identity threshold,
   fabricate a pass, or start an additional retry loop.

One exception is a strictly bounded identity closeout after an already executed
whole-image retry. It is allowed only when all conditions are true:

```text
fused identity is >= 0.72 and < 0.82
objective identity is >= 0.82
geometry relationship is >= 0.80
prompt-owned channel score is >= 0.60
human realism is >= 0.65
commercial finish is >= 0.70
no text, watermark, body, policy, scene, wardrobe, camera, or whole-style blocker exists
no prior local identity repair exists in the job
```

The closeout edits only the feathered face mask on the current generated canvas.
It is one additional provider call, not another generic retry loop. Delivery
accepts it only when identity crosses 0.82 or improves by at least 0.06 and no
prompt, realism, or commercial score drops by more than 0.03. Otherwise the
previous reviewed output remains final.

For real reference-conditioned portrait work, multimodal visual review itself
may retry up to three times after transient provider errors, with short bounded
backoff. This is review-only: it does not create image outputs or consume the
image retry budget. Configuration/unavailable states do not retry. If all three
review attempts fail, objective identity evidence is still recorded and the
candidate remains manual-review-only.

These corrections stay inside the existing evidence, review, and reviewed
delivery children of the Visual Capability Cluster. No template-specific or
scene-specific branch is introduced.
