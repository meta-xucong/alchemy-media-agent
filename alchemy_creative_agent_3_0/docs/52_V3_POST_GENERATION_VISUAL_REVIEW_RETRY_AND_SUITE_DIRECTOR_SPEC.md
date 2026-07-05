# 52 V3 Post Generation Visual Review Retry And Suite Director Spec

## 1. Status And Authority

This document is the next development authority after document `51`.

It does not replace document `50` or document `51`.

Authority chain:

```text
Doc50:
  Owns the architecture rule that all reusable visual enhancement belongs
  inside the V3-native Visual Capability Cluster.

Doc51:
  Owns strong selected-image references, identity/product/brand locks,
  project-scoped visual consistency contracts, and first-pass retry/review
  metadata.

Doc52:
  Deepens Doc51 into a real post-generation commercial-quality loop:
  image-file resolution, real output visual inspection, automatic retry
  execution, suite variation direction, best-output curation, and
  beginner-facing quality display.

Doc53:
  Owns the exact automatic retry execution guardrails: when a retry may run,
  when it must not run, how retry outputs are appended, and how retry loops are
  prevented. Any implementation conflict about retry execution is resolved in
  favor of Doc53.

Doc54:
  Refines SuiteVariationDirector for the General Template. General Template
  continuation is not a hard-coded business suite. It uses a General Variation
  Director with four modes: similar candidates, delivery suite, creative
  exploration, and format/layout adaptation. Specialized templates own their
  own business slot definitions.

Doc55:
  Owns the exact real post-generation image inspection and review-merge
  implementation. Doc52 describes the broader target; Doc55 is the authority
  for GeneratedOutputResolver, VisionOutputInspector, OutputQualityReviewMerger,
  inspection statuses, issue taxonomy, and retry signals created from actual
  generated image files.

Doc57:
  Extends the suite/review target for ecommerce lifestyle realism,
  requested-count unification, and strict faint watermark/corner-mark QA. For
  those three topics, Doc57 wins over older generic suite wording.
```

This document is compatible with:

```text
Project Mode
ProjectContextPackage
ScenarioRuntime
V3 Product API
V3 generation providers
V3 generated output store
V3 LLM Brain Adapter
V3 Visual Capability Cluster
General Template project flow
Single production entry and suite flow
```

This document is not an instruction to:

```text
rewrite V3
replace Project Mode
replace ScenarioRuntime
replace Product API
call V1/V2 runtime code
add Claude Code as a V3 brain/provider route
unfreeze E-Commerce Template
build a Lovart canvas clone
```

---

## 2. Compatibility Audit

The plan is compatible with existing V3 because it is additive and uses the
current ownership model.

### 2.1 Compatibility with Doc50

Doc50 says:

```text
All reusable visual enhancement belongs to the V3 native shared capability
layer, organized as one Visual Capability Cluster.
```

Doc52 follows this rule:

```text
GeneratedOutputResolver:
  may live near output storage or product API as an infrastructure helper, but
  visual meaning is consumed by the Visual Capability Cluster.

VisionOutputInspector:
  belongs under visual_cluster.

VisualRetryExecutor policy:
  retry decision policy belongs under visual_cluster; actual provider rerun
  is executed by Product API / ScenarioRuntime through the normal generation
  path.

SuiteVariationDirector:
  belongs under visual_cluster because it defines reusable visual-series
  variation rules.
```

CentralCreativeBrain remains a consumer. It must not own visual inspection,
retry scoring, identity drift detection, or suite variation policy.

### 2.2 Compatibility with Doc51

Doc51 already introduced:

```text
StrongReferenceBinding
VisualIdentityLockProfile
VisualQualityReviewReport
AutoRetryDecision
CommercialOutputSelection
negative_visual_memory
template_consistency_policy
```

Doc52 keeps these contracts and extends them.

Doc52 does not rename or remove Doc51 fields. Existing code may continue to
read Doc51 structures. New fields are additive:

```text
output_file_resolution
visual_inspection_reports
retry_execution_records
suite_variation_plan
curation_groups
beginner_quality_summary
```

### 2.3 Compatibility with Project Mode

Project Mode remains the application layer:

```text
Project
  -> Template
    -> Job
      -> Generation attempts
        -> Outputs
        -> Review reports
        -> Retry attempts
        -> Curation groups
```

Doc52 must not turn Project Mode into a visual engine. Project Mode stores:

```text
selected outputs
active references
review reports
retry records
best output selections
suite variation plans
timeline events
```

Visual logic belongs to Visual Capability Cluster.

### 2.4 Compatibility with Single Production Entry

Doc47 requires a single beginner-facing production entry. Doc52 preserves this:

```text
User sees:
  Generate a set
  Continue this project

System does internally:
  inspect outputs
  retry if safe
  rank outputs
  hide risky outputs from default view
```

No new engineering buttons should appear in the default UI.

### 2.5 Compatibility with General-First Policy

Current product decision remains:

```text
E-Commerce Template stays frozen for user-facing generation until later.
General Template is the active implementation target.
```

Doc52 applies first to General Template.

E-Commerce-specific review rules may be defined as dormant policy entries but
must not create ecommerce jobs or mix ecommerce context into general projects.

---

## 3. Product Target

Current V3 after Doc51:

```text
strong selected-image references
project-scoped context
identity/product/brand lock contracts
provider reference-image input
preflight review metadata
retry decision metadata
real GPT Image 2 generation through V3
```

Remaining Lovart-quality gap:

```text
generated images are not yet always inspected visually after creation
retry decisions are not yet always executed as an append-only generation loop
image sets can remain too repetitive or too random
best-output curation is not yet a complete user-facing delivery system
quality explanations are not yet consistently beginner-friendly
```

Doc52 target:

```text
Generate commercial-grade project-consistent image sets that:
  preserve selected character/product/brand direction
  vary composition in a useful suite structure
  inspect real generated images
  automatically retry fixable failures
  append retry outputs without overwriting old outputs
  rank and explain deliverable outputs
  show images first and workflow details only when expanded
```

---

## 4. Target Runtime Flow

### 4.1 First generation

```text
User creates project and enters one natural-language request
  -> Project Mode builds ProjectContextPackage
  -> Visual Capability Cluster builds baseline visual profile
  -> LLM Brain checkpoints produce intent/strategy/prompt guidance
  -> CentralCreativeBrain compiles job plan
  -> Provider generates candidates
  -> GeneratedOutputResolver resolves real output files
  -> VisionOutputInspector reviews real images when possible
  -> OutputQualityReviewer merges metadata, prompt-contract, and vision review
  -> AutoRetryPlanner decides whether fixable retry is needed
  -> VisualRetryExecutor appends retry outputs through normal generation path
  -> BestOutputSelector ranks all deliverable outputs
  -> Project Mode stores review, retry, curation, and timeline records
  -> UI shows recommended images first
```

### 4.2 User selects image

```text
User selects one or more satisfactory outputs
  -> Project Mode stores selected OutputRef
  -> GeneratedOutputResolver resolves selected image file
  -> StrongReferenceBinder upgrades selected output into reference binding
  -> TemplateConsistencyPolicy decides identity/style/product lock strength
  -> ProjectIdentityMemory updates inside the current project only
  -> Next generation reads this context
```

### 4.3 Continue suite generation

```text
User clicks continue / generate another set
  -> SuiteVariationDirector creates variation plan
  -> Selected image is passed as strong reference input when file exists
  -> Each variation keeps required identity/style locks
  -> Provider generates new outputs
  -> Outputs are inspected and reviewed
  -> Retryable failures append fixed outputs
  -> BestOutputSelector groups recommended / usable / needs review / hidden
  -> Old outputs remain available
```

---

## 5. New And Extended Modules

### 5.1 GeneratedOutputResolver

Purpose:

```text
Resolve the real local file, preview, thumbnail, provider metadata, and output
record for generated outputs by output_id, asset_id, candidate_id, or job_id.
```

Implementation authority:

```text
Doc55 owns the detailed GeneratedOutputResolution contract, missing/unreadable
file behavior, resolver integration tests, and Product API usage rules.
```

Why this is required:

```text
Post-generation review and strong references need real files. Candidate
payloads may not always expose file_path at the top level even when the output
store contains original.png.
```

Suggested location:

```text
app/product_api/output_resolver.py
```

It is an infrastructure helper, not a visual reasoning owner.

Inputs:

```text
job_id
candidate_id
asset_id
output_id
V3GeneratedOutputStore
ProductJobStatus
ProjectContextPackage
```

Outputs:

```python
class GeneratedOutputResolution(V3BaseModel):
    resolution_id: str
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
    metadata: dict[str, Any] = {}
```

Rules:

```text
1. If output_id resolves to output_store file, status is ready.
2. If only URL exists, status is remote_only.
3. If file exists but cannot be read, status is unreadable.
4. Missing file must not crash the job; review degrades to metadata mode.
5. Resolved file_path should be copied into candidate metadata and reference
   binding payloads when safe.
```

Acceptance:

```text
generated candidate can resolve original.png by output_id
selected output can resolve original.png by output_id after restart
missing files produce warning, not exception
provider reference plans use resolved file paths
```

### 5.2 VisionOutputInspector

Purpose:

```text
Inspect real generated images after provider output is saved.
```

Implementation authority:

```text
Doc55 owns inspection modes, issue taxonomy, confidence handling, retryable
classification, and beginner-facing review summaries.
```

Suggested location:

```text
app/shared_capabilities/visual_cluster/vision_inspector.py
```

Inputs:

```text
GeneratedOutputResolution
ProjectContextPackage
VisualIdentityLockProfile
StrongReferenceBinding
VisualGrammarProfile
final provider prompt
user request
template consistency policy
```

Review modes:

```text
metadata_only
prompt_contract
vision_model
hybrid
manual_required
```

The first implementation may use:

```text
image dimensions and file readability
provider metadata
prompt contract checks
optional V3-owned vision/LLM provider if configured
```

It must be designed so a real multimodal vision call can be added without
changing public contracts.

Output:

```python
class VisualInspectionReport(V3BaseModel):
    inspection_id: str
    project_id: str | None = None
    job_id: str | None = None
    candidate_id: str | None = None
    output_id: str | None = None
    mode: str = "metadata_only"
    status: str = "manual_required"
    score_card: dict[str, float] = {}
    detected_issues: list[dict[str, Any]] = []
    preserved_elements: list[str] = []
    drift_warnings: list[str] = []
    artifact_warnings: list[str] = []
    retryable: bool = False
    confidence: float = 0.0
    evidence: dict[str, Any] = {}
    user_visible_summary: list[str] = []
```

Issue categories:

```text
identity_drift
hair_or_outfit_drift
camera_distance_drift
lighting_mismatch
composition_mismatch
unrelated_object
unrelated_product
visible_text_artifact
watermark_or_signature
collage_or_split_panel
bad_hands_or_body
face_artifact
low_commercial_finish
file_missing
vision_provider_unavailable
```

Required scoring dimensions:

```text
request_match
identity_consistency
style_consistency
visual_grammar
composition
lighting
artifact_safety
commercial_finish
overall
```

Rules:

```text
1. Vision inspection never deletes outputs.
2. Vision inspection never updates Brand Memory.
3. Low confidence should become warning/manual_required, not fail_final.
4. Provider/network errors are not visual failures.
5. General Template review must avoid ecommerce/product language unless the
   project policy explicitly allows it.
```

### 5.3 OutputQualityReviewMerger

Purpose:

```text
Merge Doc51 metadata preflight review with real image inspection.
```

Implementation authority:

```text
Doc55 owns the exact pass/warning/fail_retryable/fail_final/manual_review
mapping and how merged review reports feed Doc53 auto retry.
```

Suggested location:

```text
app/shared_capabilities/visual_cluster/quality_review.py
```

Inputs:

```text
VisualInspectionReport
VisualQualityReviewResult
VisualIdentityLockProfile
ProjectVisualGrammarSnapshot
StrongReferenceBinding
TemplateConsistencyPolicy
```

Output:

```text
VisualQualityReviewReport
```

Status mapping:

```text
pass:
  overall score is acceptable and no severe issue exists

warning:
  output is usable but should be shown with a plain-language note

fail_retryable:
  issue can likely be fixed with stronger references, negative prompt,
  composition repair, or artifact avoidance

fail_final:
  issue should not be retried automatically

manual_review:
  confidence is too low or provider/vision evidence is incomplete
```

### 5.4 VisualRetryExecutor

Purpose:

```text
Execute safe retry decisions through the normal V3 generation path.
```

Policy owner:

```text
AutoRetryPlanner under Visual Capability Cluster.
```

Execution owner:

```text
Product API / ScenarioRuntime, because provider calls and job state are not
owned by shared capabilities.
```

Input:

```text
AutoRetryDecision
retry_patch
original GenerationRequest
ProjectContextPackage
attempt budget
provider capability
```

Retry patch fields:

```python
class VisualRetryPatch(V3BaseModel):
    patch_id: str
    source_review_ids: list[str] = []
    strengthen_reference_ids: list[str] = []
    prompt_additions: list[str] = []
    negative_prompt_additions: list[str] = []
    identity_reinforcement: list[str] = []
    product_reinforcement: list[str] = []
    brand_asset_reinforcement: list[str] = []
    composition_repair: list[str] = []
    artifact_repair: list[str] = []
    object_removal_instruction: list[str] = []
    provider_hint_overrides: dict[str, Any] = {}
    user_visible_reason: str = ""
```

Retry execution record:

```python
class RetryExecutionRecord(V3BaseModel):
    retry_execution_id: str
    project_id: str | None = None
    original_job_id: str
    retry_job_id: str | None = None
    source_output_ids: list[str] = []
    retry_output_ids: list[str] = []
    attempt_index: int
    max_attempts: int
    status: str  # skipped | executed | blocked | failed
    reason_codes: list[str] = []
    retry_patch: dict[str, Any] = {}
    created_at: str
    metadata: dict[str, Any] = {}
```

Rules:

```text
1. Retry appends outputs. It never overwrites old outputs.
2. Retry must use the normal provider route and normal output store.
3. Retry must preserve project_id and project context.
4. Retry cannot trigger on provider/rate-limit/network failures.
5. Retry stops when max attempts is reached.
6. Retry stops when the same issue category repeats for the same output.
7. Retry records must be visible in folded workflow details.
```

Default limits:

```text
standard: 1 retry
strict/high-consistency: 2 retries
explore: 0 or 1 retry depending on user preference
```

### 5.5 SuiteVariationDirector

Purpose:

```text
Convert "continue this project" into useful image-set variation plans rather
than simple repeated images.
```

Suggested location:

```text
app/shared_capabilities/visual_cluster/suite_director.py
```

Input:

```text
ProjectContextPackage
selected references
identity locks
visual grammar snapshot
user continuation request
template consistency policy
requested image count
requested aspect ratio
```

Output:

```python
class SuiteVariationPlan(V3BaseModel):
    plan_id: str
    project_id: str | None = None
    job_id: str | None = None
    template_id: str
    requested_count: int
    aspect_ratio: str | None = None
    slots: list[dict[str, Any]] = []
    locked_elements: list[str] = []
    allowed_changes: list[str] = []
    forbidden_changes: list[str] = []
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

General Template refinement:

```text
For the General Template, this section is refined by Doc54.

General Template must not treat every multi-image request as a fixed business
suite. It first selects a variation mode:

  selection_candidates
  delivery_suite
  creative_exploration
  format_adaptation

Only delivery_suite uses universal non-business slots. Similar candidate mode
uses small pose/expression/crop/angle variants instead of hero/detail/scene
roles.
```

General Template delivery-suite universal slots:

```text
hero_cover
close_portrait
atmosphere_wide
detail_or_mood
social_vertical
cover_with_clean_space
```

Portrait project rules:

```text
Keep:
  recognizable character vibe
  hair direction
  outfit style category
  skin tone direction
  camera and lighting language

Allow:
  pose
  crop
  background detail
  camera angle within same lens language
  negative-space placement

Forbid:
  face swap
  random hairstyle change
  major wardrobe category change
  unrelated product/object insertion
  visible text or watermark
```

General non-portrait rules:

```text
Keep:
  style, palette, lighting, composition grammar

Allow:
  subject arrangement, scene details, crop, angle

Forbid:
  unrelated objects, visible text artifacts, collage/split panels
```

Dormant ecommerce future rules:

```text
main image
feature image
scenario image
detail image
packaging image
comparison image
```

These rules must stay dormant until E-Commerce Template is intentionally
unfrozen.

### 5.6 BestOutputCurator

Purpose:

```text
Turn all original and retry outputs into beginner-friendly delivery groups.
```

Input:

```text
VisualQualityReviewReport
VisualInspectionReport
RetryExecutionRecord
SuiteVariationPlan
generated output metadata
```

Output:

```python
class OutputCurationResult(V3BaseModel):
    curation_id: str
    project_id: str | None = None
    job_id: str | None = None
    best_output_ids: list[str] = []
    recommended_output_ids: list[str] = []
    usable_output_ids: list[str] = []
    needs_review_output_ids: list[str] = []
    hidden_failed_output_ids: list[str] = []
    slot_assignments: dict[str, str] = {}
    user_visible_reasons: list[str] = []
    metadata: dict[str, Any] = {}
```

Rules:

```text
1. Recommended outputs appear first.
2. Hidden failed outputs remain auditable.
3. If all outputs are warnings, show the best available output with a note.
4. Do not present retry failures as final recommended results.
5. Do not remove user-selected outputs automatically.
```

---

## 6. Project Context And Storage Additions

Extend `ProjectContextPackage` additively:

```text
output_file_resolution
visual_inspection_reports
retry_execution_records
suite_variation_plan
output_curation
beginner_quality_summary
```

Suggested JSON-friendly fields:

```python
output_file_resolution: list[dict[str, Any]]
visual_inspection_reports: list[dict[str, Any]]
retry_execution_records: list[dict[str, Any]]
suite_variation_plan: dict[str, Any]
output_curation: dict[str, Any]
beginner_quality_summary: list[str]
```

Timeline item additions:

```text
output_reviewed
auto_retry_executed
auto_retry_skipped
suite_plan_created
output_curated
```

Timeline language rules:

```text
Default UI:
  plain beginner-friendly wording

Folded details:
  final prompt
  preserved elements
  retry reason
  review summary

Never show by default:
  provider
  job id
  raw JSON
  module names
  manifest
  capability IDs
```

---

## 7. LLM Brain Role

LLM Brain may:

```text
summarize user intent
summarize visual inspection reports
produce beginner-friendly progress messages
explain retry reasons
help write retry patch wording
summarize final curation
```

LLM Brain must not:

```text
own visual inspection policy
own retry scoring
own identity locks
own provider rerun execution
own output curation contract
```

If LLM Brain is unavailable:

```text
Doc52 still runs deterministic review/curation fallbacks.
User-facing messages become shorter but stable.
```

---

## 8. Frontend UX Requirements

Main project page remains simple:

```text
project overview
recommended images
usable images
continue / generate another set
folded workflow details
```

Default display:

```text
Images first.
Small plain-language quality labels.
No engineering terms.
No raw prompt unless user expands details.
No provider messages unless there is an actionable error.
```

Recommended groups:

```text
Recommended
Usable
Needs confirmation
Hidden from default view
```

Folded workflow details may show:

```text
what V3 preserved
what V3 changed
why V3 retried
what V3 avoided
final prompt
reference image usage
```

Mobile:

```text
same groups
fixed image cards
scrollable details
no dense tables
no engineering labels
```

---

## 9. Implementation Plan

### Phase 0 - Documentation and compatibility audit

Tasks:

```text
1. Add document 52.
2. Add compatibility notes to documents 36, 43, 47, 48, 50, and 51.
3. Run rg audit for conflicting review/retry/suite wording.
4. Confirm this phase is a Doc51 deepening, not an architecture rewrite.
```

Acceptance:

```text
Doc52 exists
old docs point to Doc52 for post-generation review/retry/suite director details
no document says LLM Brain owns visual review
no document says retry overwrites outputs
no document requires unfreezing E-Commerce Template
```

### Phase 1 - Output file resolution

Files:

```text
app/product_api/output_resolver.py
app/product_api/service.py
app/project_mode/service.py
tests/test_v3_output_resolution.py
```

Tasks:

```text
1. Resolve generated files by output_id, asset_id, candidate_id, and job_id.
2. Backfill candidate metadata with file_path when available.
3. Ensure selected outputs can resolve files after service restart.
4. Ensure provider reference plans use resolved selected-output file paths.
```

Acceptance:

```text
real output id resolves to original.png
selected output after restart becomes hard reference with file_path
missing output file degrades safely
```

### Phase 2 - Vision inspection contract and fallback

Files:

```text
app/shared_capabilities/visual_cluster/contracts.py
app/shared_capabilities/visual_cluster/vision_inspector.py
app/shared_capabilities/visual_cluster/quality_review.py
tests/test_v3_visual_inspection.py
```

Tasks:

```text
1. Add VisualInspectionReport.
2. Implement metadata_only and prompt_contract review.
3. Add optional vision_model hook behind settings.
4. Merge inspection into VisualQualityReviewReport.
```

Acceptance:

```text
every generated output can receive inspection report
missing vision provider does not fail generation
bad mock image metadata can produce fail_retryable
general template public metadata remains deproductized
```

### Phase 3 - Retry execution loop

Files:

```text
app/shared_capabilities/visual_cluster/auto_retry.py
app/product_api/service.py
app/scenario_runtime/runtime.py
app/generation_router/providers.py
tests/test_v3_visual_auto_retry.py
```

Tasks:

```text
1. Convert fail_retryable review reports to VisualRetryPatch.
2. Execute retry through normal generation path.
3. Append retry outputs to same project/job context.
4. Add retry execution timeline item.
5. Stop loops safely.
```

Acceptance:

```text
retry appends outputs
old outputs remain
same failure repeated stops retry
provider errors do not trigger visual retry
retry patch is stored and auditable
```

### Phase 4 - Suite variation director

Files:

```text
app/shared_capabilities/visual_cluster/suite_director.py
app/scenario_runtime/runtime.py
app/agents/series_planner_agent.py
app/agents/prompt_compiler_agent.py
tests/test_v3_suite_variation_director.py
```

Tasks:

```text
1. Add SuiteVariationPlan.
2. For General Template, map requested count to useful variation slots.
3. Keep identity/style locks while allowing controlled variation.
4. Feed variation slot guidance into prompt compilation/provider prompt.
```

Acceptance:

```text
continue generation produces slot plan
portrait suite varies pose/crop/background without changing identity rules
non-portrait suite varies composition without product contamination
requested image count and aspect ratio remain respected
```

### Phase 5 - Output curation

Files:

```text
app/shared_capabilities/visual_cluster/best_output_selector.py
app/project_mode/service.py
app/product_api/service.py
tests/test_v3_output_curation.py
```

Tasks:

```text
1. Merge original outputs and retry outputs.
2. Rank outputs by review score and slot fit.
3. Build recommended / usable / needs-review / hidden groups.
4. Store curation result in job metadata and project context.
```

Acceptance:

```text
recommended outputs appear first
failed outputs hidden from default display but auditable
all-warning batches still show best available output
manual user selection still overrides machine recommendation
```

### Phase 6 - Beginner UI

Files:

```text
src_skeleton/app/static/app.js
src_skeleton/app/static/styles.css
src_skeleton/app/mobile_static/mobile.js
src_skeleton/app/mobile_static/mobile.css
tests/test_v3_commercial_frontend_shell.py
```

Tasks:

```text
1. Show recommended images first.
2. Add compact beginner quality summary.
3. Add folded workflow details for review/retry/preservation.
4. Keep history/project cards stable.
5. Ensure mobile layout remains clean.
```

Acceptance:

```text
default UI remains image-first
no engineering terms in normal view
review/retry details are folded
mobile layout does not overflow
```

### Phase 7 - Real validation

Required real validation:

```text
Project:
  Generate a refreshing summer portrait set of an East Asian young woman,
  clean, premium, translucent, suitable for social cover.

Steps:
  1. Generate first image.
  2. Select best image.
  3. Continue same project with 3-4 images.
  4. Confirm selected image is hard identity reference.
  5. Confirm later outputs use reference image input.
  6. Confirm suite has useful variation.
  7. Confirm no visible text, watermark, unrelated product, or split panel.
  8. Confirm review/curation summary is readable.
```

Optional negative validation:

```text
Create or mock a bad output with visible text/watermark/unrelated object.
Confirm review marks fail_retryable and retry patch is generated.
```

---

## 10. Test Plan

Focused tests:

```powershell
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_output_resolution.py -q
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_visual_inspection.py -q
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_visual_auto_retry.py -q
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_suite_variation_director.py -q
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_output_curation.py -q
```

Regression tests:

```powershell
python -m pytest alchemy_creative_agent_3_0\tests -q
python -m pytest tests\test_v3_commercial_frontend_shell.py -q
python -m pytest tests\test_api_smoke.py -q
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
node --check src_skeleton\app\static\app.js
node --check src_skeleton\app\mobile_static\mobile.js
git diff --check
```

Audit scans:

```powershell
rg -n "Claude Code|V2 Claude|custom_media_agent_2_0|V1 runtime|V2 runtime" alchemy_creative_agent_3_0\app
rg -n "provider|job id|capability|manifest|raw metadata" src_skeleton\app\static src_skeleton\app\mobile_static
rg -n "overwrite|replace old outputs|delete old outputs" alchemy_creative_agent_3_0\docs alchemy_creative_agent_3_0\app
```

Pass rules:

```text
no forbidden V1/V2 runtime imports
no Claude Code expert route
no retry overwrite behavior
no general-template product/commercial leakage
full regression passes
real validation output quality is manually inspected
```

---

## 11. Commercial Acceptance Criteria

The phase is acceptable only when:

```text
1. Real generated outputs resolve to image files for review.
2. Selected portrait outputs become hard identity references.
3. Continuation uses selected image as provider reference input.
4. Generated outputs receive visual inspection reports.
5. Retryable visual failures produce retry patches.
6. Auto retry appends outputs and never overwrites old outputs.
7. Suite continuation creates useful variation instead of duplicate images.
8. Best outputs are ranked and shown first.
9. Failed outputs remain auditable but are not recommended by default.
10. UI explains preserved direction, retry, and recommendation in plain
    beginner language.
11. E-Commerce Template remains frozen unless a later accepted document
    explicitly unfreezes it.
12. V3 remains independent from V1/V2 runtime code.
```

---

## 12. Non-Goals

This phase does not require:

```text
pixel-perfect real-person identity preservation
training a face-recognition model
creating a Lovart-style infinite canvas
manual layer editing
ecommerce module completion
global Brand Memory auto-updates
removing user choice
deleting failed outputs automatically
rewriting provider integrations from scratch
```

---

## 13. Risk Controls

### 13.1 Over-retry

Risk:

```text
System wastes credits by retrying too aggressively.
```

Guardrail:

```text
strict retry budget
no retry for provider errors
stop repeated same issue
store retry reason
```

### 13.2 Over-locking

Risk:

```text
Suite becomes repetitive and loses creative usefulness.
```

Guardrail:

```text
SuiteVariationDirector separates keep_rules from allowed_changes.
Identity lock preserves character direction, not exact frozen pixels.
```

### 13.3 Vision false positive

Risk:

```text
Review rejects usable creative variations.
```

Guardrail:

```text
low confidence becomes warning/manual_review
best available output is still shown if all outputs are warnings
user selection remains authoritative
```

### 13.4 Context leakage

Risk:

```text
Negative memory or identity locks leak across projects/templates/accounts.
```

Guardrail:

```text
project-scoped by default
account scoping tests
brand memory only by explicit confirmation
template policy gating
```

---

## 14. Implementation Handoff Prompt

Use this prompt when coding begins:

```text
Implement document 52.

Do not rewrite the V3 foundation. Keep Project Mode, ScenarioRuntime, Product
API, generated output storage, provider routing, LLM Brain, and Doc50/Doc51
Visual Capability Cluster ownership intact.

Deepen Doc51 into a post-generation commercial-quality loop:
  1. resolve generated output files reliably
  2. inspect real generated images when possible
  3. merge inspection into quality review reports
  4. execute safe automatic retry through the normal V3 generation path
  5. append retry outputs without overwriting old outputs
  6. create suite variation plans for General Template continuation
  7. curate recommended / usable / needs-review / hidden outputs
  8. expose beginner-friendly summaries while folding advanced workflow details

Keep E-Commerce Template frozen for user-facing generation. Do not add V1/V2
runtime imports. Do not add Claude Code expert/provider route. Run focused
tests, full regression, frontend syntax checks if UI changes, and a real
GPT Image 2 continuation validation.
```
