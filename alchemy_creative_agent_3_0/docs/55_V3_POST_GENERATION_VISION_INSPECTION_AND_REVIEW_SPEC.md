# 55 V3 Post Generation Vision Inspection And Review Spec

> **Doc135 forward-path note:** inspection may classify pixels and issue
> normalized evidence codes, but it may not manufacture local re-prompt,
> negative-word or repair text for a new V3 Job. Those former examples are
> archival compatibility context only.

Doc93 compatibility note:

```text
Review must now evaluate identity fidelity and prompt-owned channel obedience
separately. Earlier examples that preserve face, hair, outfit, lens, and light
together are valid only when those channels were explicitly locked. For an
ordinary portrait identity reference, source-style leakage is a review failure.
```

## 1. Status And Authority

This document is the implementation authority for real post-generation visual
inspection in V3.

Why this is document `55`:

```text
Doc54 is already assigned to the General Variation Director and frontend mode
selector. The earlier plan mentioned post-generation vision inspection as the
next "Doc54" topic, but the numbering is now adjusted to keep the document
system conflict-free.
```

Authority chain:

```text
Doc50:
  Owns the rule that reusable visual enhancement belongs in the V3 native
  Visual Capability Cluster.

Doc51:
  Defines strong references, identity/product/brand locks, quality review
  reports, auto-retry decisions, and commercial output selection contracts.

Doc52:
  Defines the broader post-generation quality loop target.

Doc53:
  Owns safe automatic retry execution guardrails.

Doc54:
  Owns General Template variation modes and manual frontend selector behavior.

Doc55:
  Owns the exact post-generation image inspection, review merge, retry signal,
  and beginner-facing review summary behavior.
```

If documents conflict about how generated images are inspected after provider
output exists, Doc55 wins.

Doc55 does not:

```text
rewrite Project Mode
replace ScenarioRuntime
replace Product API
replace Doc53 retry execution guardrails
unfreeze E-Commerce Template
call V1/V2 runtime code
add Claude Code as a V3 brain route
```

Human-led batch extension:

```text
Document 56 extends Doc55 with batch-level human diversity review. Doc55
candidate inspection remains necessary, but human-led multi-image sets also
need to detect over-locked expression, pose, head angle, and cloned-still
behavior. If a batch-level portrait consistency issue conflicts with older
candidate-only review wording, Doc56 wins.

Document 57 extends Doc55 with stricter commercial watermark QA. Faint corner
marks, AI-generated badge traces, signature-like strokes, and subtle
watermark-like residue must be reviewed more strictly than generic visible
text. If Doc55 wording is too broad, Doc57 supplies the detailed issue taxonomy
and retry patch behavior.

Provider provenance hardening extends the same cleanliness principle to output
file metadata. When an OpenAI GPT image route is requested, third-party AIGC
metadata without expected OpenAI provenance signals must be classified as a
retryable commercial cleanliness issue, not silently accepted as a good image.

Document 60 extends Doc55 for E-Commerce product suites: product labels/logos
visible in the supplied reference, requested E-Commerce slot roles, and
listing/ad-set role coverage are reviewable post-generation signals. If Doc55
is broad and Doc60 is specific about product label or slot fidelity, Doc60 wins.
```

## 2. Product Goal

Current state after Doc53:

```text
V3 can execute a safe retry when a retryable issue signal is present.
```

Missing state:

```text
V3 does not yet reliably inspect the actual generated image and create the
retryable issue signal by itself.
```

Doc55 target:

```text
After image generation, V3 should inspect the generated image file, detect
obvious visual problems, convert them into structured review reports, and feed
retryable issues into Doc53 automatic retry execution.
```

Beginner-facing product result:

```text
V3 checked the generated image.
V3 found whether it is usable.
If there was a clear fixable issue, V3 made one safer retry.
Original images were kept.
```

## 3. Core Runtime Flow

```text
1. Product API calls ScenarioRuntime.generate_job.
2. Provider returns generated candidates and output records.
3. GeneratedOutputResolver resolves each candidate to a real output file.
4. VisionOutputInspector inspects each resolved output.
5. OutputQualityReviewMerger combines:
   - prompt contract
   - project context
   - selected reference locks
   - visual capability cluster data
   - real image inspection
6. The merged review produces VisualQualityReviewReport records.
7. Retryable reports become AutoRetryDecision input.
8. Doc53 executor decides whether a retry may run.
9. Retry outputs are appended and inspected again within safe retry budget.
10. Project Mode stores inspection, review, retry, and curation metadata.
11. UI shows recommended images first and folds review details.
```

Doc55 must run after actual provider output exists. Pre-generation metadata
review is not enough for Doc55 acceptance.

## 4. Module Ownership

### 4.1 GeneratedOutputResolver

Suggested location:

```text
app/product_api/output_resolver.py
```

Ownership:

```text
Infrastructure helper owned near Product API / output store.
It resolves files and metadata, but does not decide visual meaning.
```

Responsibilities:

```text
resolve by output_id
resolve by candidate_id
resolve by asset_id
resolve by job_id
find original image file
find preview/thumbnail file
read dimensions
detect missing/unreadable files
return a structured resolution object
```

### 4.2 VisionOutputInspector

Suggested location:

```text
app/shared_capabilities/visual_cluster/vision_inspector.py
```

Ownership:

```text
Visual Capability Cluster owns visual inspection semantics.
```

Responsibilities:

```text
inspect actual output images
detect visible visual issues
score image quality dimensions
produce VisualInspectionReport
avoid ecommerce/product wording in General Template unless policy allows it
degrade safely when vision provider is unavailable
```

### 4.3 OutputQualityReviewMerger

Suggested location:

```text
app/shared_capabilities/visual_cluster/quality_review.py
```

Responsibilities:

```text
merge image inspection with Doc51 quality review contracts
produce VisualQualityReviewReport
classify status as pass/warning/fail_retryable/fail_final/manual_review
generate retry patch hints for retryable issues
produce beginner-facing summary
```

### 4.4 Product API Retry Bridge

Suggested location:

```text
app/product_api/service.py
```

Responsibilities:

```text
run resolver and inspector after first generation
attach review reports to PlanningResult.metadata
call Doc53 retry executor only after review signal exists
store review/retry summary in ProductJobStatus.metadata
never retry provider/account/network errors as visual failures
```

## 5. Data Contracts

### 5.1 GeneratedOutputResolution

```python
class GeneratedOutputResolution(V3BaseModel):
    resolution_id: str
    project_id: str | None = None
    job_id: str | None = None
    candidate_id: str | None = None
    asset_id: str | None = None
    output_id: str | None = None
    file_path: str | None = None
    preview_path: str | None = None
    thumbnail_path: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    thumbnail_url: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    provider: str | None = None
    model: str | None = None
    status: str = "missing"  # ready | missing | remote_only | unreadable
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
```

Rules:

```text
ready:
  local original file exists and is readable

remote_only:
  only URL exists; local inspection may not run

missing:
  no output file or URL found

unreadable:
  file exists but cannot be opened as an image
```

### 5.2 VisualInspectionReport

```python
class VisualInspectionReport(V3BaseModel):
    inspection_id: str
    project_id: str | None = None
    job_id: str | None = None
    candidate_id: str | None = None
    asset_id: str | None = None
    output_id: str | None = None
    mode: str = "metadata_only"
    status: str = "manual_review"  # pass | warning | fail_retryable | fail_final | manual_review
    confidence: float = 0.0
    score_card: dict[str, float] = {}
    detected_issues: list[dict[str, Any]] = []
    preserved_elements: list[str] = []
    drift_warnings: list[str] = []
    artifact_warnings: list[str] = []
    retryable: bool = False
    retry_patch: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

### 5.3 PostGenerationReviewPackage

```python
class PostGenerationReviewPackage(V3BaseModel):
    package_id: str
    project_id: str | None = None
    job_id: str
    resolutions: list[GeneratedOutputResolution] = []
    inspections: list[VisualInspectionReport] = []
    quality_review_reports: list[dict[str, Any]] = []
    auto_retry_decisions: list[dict[str, Any]] = []
    recommended_output_ids: list[str] = []
    hidden_output_ids: list[str] = []
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

## 6. Inspection Modes

Doc55 supports multiple inspection modes.

```text
metadata_only:
  use file existence, dimensions, provider metadata, prompt contract

local_image_heuristic:
  use local image loading and simple deterministic checks

vision_model:
  use configured V3-owned multimodal vision provider

hybrid:
  combine local checks and vision model

fake_for_tests:
  deterministic fake inspector for tests
```

Default behavior:

```text
If a real vision model is configured:
  hybrid

If no real vision model is configured:
  metadata_only or local_image_heuristic

If confidence is low:
  manual_review, not automatic fail
```

100 percent Lovart-gap closure requires:

```text
vision_model or hybrid mode available for real images
```

Metadata-only mode is useful but is not enough to claim full visual inspection
parity.

## 7. Required Issue Taxonomy

Doc55 must classify these issue codes:

```text
visible_text_artifact
watermark_or_signature
faint_corner_watermark
ai_generated_badge_trace
signature_like_artifact
lower_right_mark_artifact
third_party_aigc_metadata
provider_provenance_mismatch
product_label_drift
product_label_unreadable
product_logo_or_label_obscured
ecommerce_slot_mismatch
ecommerce_suite_role_mismatch
collage_or_split_panel
identity_drift
hair_or_outfit_drift
camera_distance_drift
lighting_mismatch
composition_mismatch
unrelated_object
unrelated_product
product_identity_drift
brand_asset_drift
bad_hands_or_body
face_artifact
low_commercial_finish
file_missing
file_unreadable
vision_provider_unavailable
low_confidence_review
policy_or_safety_block
provider_error
```

General Template wording:

```text
Use subject/object/visual direction wording.
Do not expose ecommerce/product language unless template policy allows it.
```

## 8. Status Mapping

### 8.1 Pass

```text
No major issue detected.
Output is directly usable.
```

### 8.2 Warning

```text
Minor issue or low severity drift.
Output remains visible and usable.
No automatic retry unless explicit retryable issue exists.
```

### 8.3 Fail Retryable

```text
Issue is likely fixable with prompt/reference/negative patch.
Doc53 may execute retry if budget and guardrails allow.
```

Retryable examples:

```text
visible_text_artifact
watermark_or_signature
third_party_aigc_metadata
provider_provenance_mismatch
product_label_drift
product_label_unreadable
product_logo_or_label_obscured
ecommerce_slot_mismatch
ecommerce_suite_role_mismatch
collage_or_split_panel
minor identity drift
minor hair/outfit drift
unrelated object
composition mismatch
lighting mismatch
bad hands/body when not severe
face artifact when not policy/safety blocked
```

### 8.4 Fail Final

```text
Issue is not safe or useful to retry automatically.
Output should be hidden by default but kept for audit.
```

Examples:

```text
policy_or_safety_block
severe face/body artifact
unrecoverable identity/product replacement
conflicting user instruction
```

### 8.5 Manual Review

```text
Evidence is incomplete or confidence is too low.
No automatic retry.
```

Examples:

```text
vision provider unavailable
image file missing
image file unreadable
low confidence review
remote-only output with no local file
```

## 9. Retry Patch Generation

Doc55 creates retry patch suggestions. Doc53 decides whether to execute them.

Patch fields:

```text
prompt_additions
negative_additions
negative_prompt_additions
reference_requirements
identity_reinforcement
product_reinforcement
brand_asset_reinforcement
composition_repair
artifact_repair
object_removal_instruction
provider_hint_overrides
user_visible_reason
```

Examples:

```text
visible_text_artifact:
  negative_additions:
    visible text
    watermark
    signature
    AI-generated mark
  artifact_repair:
    keep the image free of generated text, watermarks, signatures, and badges

third_party_aigc_metadata or provider_provenance_mismatch:
  negative_additions:
    third-party AIGC label
    AI generated badge
    provider provenance mark
  artifact_repair:
    generate a clean commercial image with no third-party AIGC label,
    metadata badge, corner stamp, or source mark

product_label_drift, product_label_unreadable, or product_logo_or_label_obscured:
  prompt_additions:
    preserve the supplied product label/logo exactly as visible on the product
    keep label/logo readable and not covered by props, glare, crop, or condensation
  negative_additions:
    rewritten label
    misspelled label
    blurred logo
    covered product label

ecommerce_slot_mismatch or ecommerce_suite_role_mismatch:
  composition_repair:
    regenerate the failed image for the exact planned ecommerce slot and selling role
  negative_additions:
    wrong ecommerce slot
    generic product variant
    same image duty repeated

collage_or_split_panel:
  composition_repair:
    generate one complete single-frame image
  negative_additions:
    collage
    split screen
    multi-panel layout

identity_drift:
  identity_reinforcement:
    preserve selected subject face direction, hair, outfit category, lens, and lighting
  reference_requirements:
    selected reference output id
```

Rules:

```text
Empty retry patch must not trigger retry.
Provider errors must not create retry patch.
Low confidence must create manual review, not retry.
Same repeated issue must stop under Doc53 guardrails.
```

## 10. Integration With Doc53 Auto Retry

Doc53 currently executes retry when a retryable signal exists.

Doc55 supplies the missing real signal:

```text
VisualInspectionReport
  -> VisualQualityReviewReport
    -> AutoRetryDecision
      -> Doc53 executor
```

Product API order:

```text
first generation
  -> post-generation inspection package
    -> retry plan
      -> Doc53 retry execution
        -> retry output inspection
          -> final review summary
```

Retry inspection rule:

```text
Retry outputs must also be inspected.
If the same issue repeats, Doc53 stops.
```

## 11. Project Mode Storage

Project Mode should store:

```text
post_generation_review_package
visual_inspection_reports
quality_review_reports
auto_retry_decisions
retry_execution_records
recommended_output_ids
hidden_output_ids
user_visible_review_summary
```

Only selected/confirmed outputs become positive project context.

Failed or hidden outputs:

```text
remain in history
do not become positive references
may contribute to negative visual memory
```

## 12. Frontend UX

Default UI:

```text
images first
recommended images first
failed outputs hidden or folded
review details folded
no engineering language
```

Beginner-facing review messages:

```text
V3 已检查这组图片
没有发现明显文字或水印
这张图更适合继续使用
这张图有小问题，V3 已尝试生成更干净的版本
这张图需要人工确认，暂不自动重试
```

Do not show:

```text
VisualInspectionReport
GeneratedOutputResolver
VisionOutputInspector
AutoRetryDecision
provider strategy
score_card raw JSON
```

Advanced folded details may show:

```text
检查了什么
发现了什么
为什么重试
保留了什么方向
避免了什么问题
```

## 13. Implementation Phases

### Phase 1 - Documentation And Contracts

1. Add Doc55.
2. Update Doc52 and Doc53 compatibility notes.
3. Add contract models for:

```text
GeneratedOutputResolution
VisualInspectionReport
PostGenerationReviewPackage
```

### Phase 2 - Output Resolver

1. Resolve from ProductJobStatus candidates.
2. Resolve from V3GeneratedOutputStore by output_id.
3. Resolve selected outputs after restart.
4. Handle missing/unreadable files without crashing.

### Phase 3 - Inspector Adapter

1. Add local metadata/file inspector.
2. Add fake inspector for tests.
3. Add real vision model adapter behind configuration.
4. Fail closed to manual_review when confidence is low.

### Phase 4 - Review Merger

1. Convert inspection reports into VisualQualityReviewReport.
2. Build retry patches for fail_retryable cases.
3. Preserve Doc51/Doc53 contracts.
4. Sanitize General Template wording.

### Phase 5 - Product API Integration

1. Run inspection after successful first generation.
2. Attach review metadata to PlanningResult.
3. Feed retryable reports into Doc53 executor.
4. Inspect retry outputs.
5. Return beginner-facing summary in ProductJobStatus.

### Phase 6 - Project Mode Timeline

1. Add timeline item:

```text
V3 checked generated images
```

2. Add retry item only when retry executes.
3. Fold technical details.

### Phase 7 - Tests And Real Validation

Run deterministic tests first, then real provider validation.

## 14. Required Tests

Unit tests:

```text
output resolver finds original.png by output_id
missing output becomes manual_review
unreadable output becomes manual_review
fake inspector visible_text_artifact becomes fail_retryable
fake inspector watermark_or_signature becomes fail_retryable
fake inspector provider_error does not become visual retry
low confidence becomes manual_review
empty retry patch does not trigger Doc53
same issue repeated stops retry
General Template review wording avoids ecommerce/product leakage
```

Integration tests:

```text
Product API real/mock generation attaches post_generation_review_package
fail_retryable inspection triggers Doc53 retry without force_visual_retry_issue_codes
retry output is appended, not overwritten
retry output is inspected after retry
hidden failed output is not selected as positive context
selected good output can still become strong reference
Project timeline includes beginner-facing review item
```

Frontend tests:

```text
review summary is folded
recommended images appear first
failed outputs are hidden/folded by default
no engineering terms appear in beginner UI
manual details can be opened
```

Real validation:

```text
run East Asian summer portrait task
run selected-reference continuation
run forced visible-text/watermark fake inspector path
run at least one real provider path when image upstream is available
compare original vs retry output
```

## 15. Acceptance Criteria

```text
Generated outputs are resolved to real files or safe missing states.
Every generated candidate receives a post-generation inspection status.
Real or fake vision inspector can detect visible text/watermark/collage issues.
Retryable visual issues create structured retry patches.
Doc53 can execute retry from Doc55 signals without manual force metadata.
Provider errors never trigger visual retry.
Low confidence does not trigger visual retry.
Retry output is appended and inspected.
Project history stores review and retry metadata.
Beginner UI shows image-first, folded, plain-language review details.
General Template remains free of ecommerce-specific language.
All deterministic tests pass.
At least one real provider validation is recorded when provider is available.
```

## 16. Known Limitations

```text
Without a configured real vision model, metadata/local inspection can catch
file and contract issues but cannot fully judge identity drift, subtle anatomy,
or commercial finish.

Without selected/uploaded references, same-person or same-product consistency
cannot be guaranteed.

External provider outages must be recorded as provider failures, not visual
quality failures.
```
