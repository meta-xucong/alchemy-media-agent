# 51 V3 Visual Consistency Pro And Lovart Gap Closure Spec

Doc93 compatibility note:

```text
Doc93 is the current reference-inheritance authority. Coarse locks in this
document that group face, hair, outfit, camera, lens, lighting, or style do not
apply by default to an ordinary portrait identity upload. They apply only to
channels explicitly assigned by the user, reference role, selected-output
purpose, structured appearance truth, or specialized template contract.
```

Current authority note:

```text
Document 52 extends this document and is the current implementation authority
for the next post-generation deepening phase: generated output file
resolution, real visual inspection, append-only automatic retry execution,
suite variation direction, and beginner-facing output curation.

This document remains the authority for strong selected-image references,
identity/product/brand locks, project-scoped consistency contracts, and the
first Visual Capability Cluster review/retry/selection data structures.
Where this document describes Phase 4-6 review/retry/best-output behavior at a
contract level, Document 52 defines the deeper execution plan.

Document 56 extends this document for human-led image series. For portraits,
models, spokespersons, or character-like humans, "identity lock" must mean
stable recognizable identity and body direction, not frozen duplication of the
same expression, face angle, pose, crop, or hair frame. If wording in this
document over-locks human presentation, Document 56 wins.

Document 58 extends this document for the next Lovart-gap closure layer:
project-scoped Identity Anchor lifecycle, automatic selected-output strong
reference continuation, General Template Suite Director roles, and batch-level
identity/diversity review. If this document describes strong references or
suite direction only at a general contract level, Document 58 defines the
current implementation plan.
```

## 1. Status And Authority

This document is the current authority for the next V3 optimization phase after
document `50`.

It converts the latest product decision into an implementation-ready
development specification:

```text
V3 already has Project Mode, visual grammar reuse, selected project context,
and multi-stage Brain checkpoints.

The next gap to close is commercial-grade long-range consistency:

1. selected images must become strong references for later generation
2. character/product/brand identity must be explicitly locked
3. generated results must be reviewed and retried automatically when they
   drift, contain artifacts, or break project identity
```

This document supersedes narrower or older wording in documents `11`, `48`,
and `50` where they describe evaluation, selected references, output review,
or Lovart-like consistency in less detail.

Compatibility rule:

```text
Doc50 remains the ownership authority:
all reusable visual enhancement belongs inside the V3-native Visual Capability
Cluster.

Doc51 is the product-grade consistency upgrade:
it adds the missing child modules, contracts, runtime order, and acceptance
tests needed to approach Lovart-level commercial visual quality.
```

This phase is a code phase only after this document is accepted. Until then it
is a planning document.

---

## 2. Product Target

Current V3 consistency level:

```text
style consistency
theme consistency
project context consistency
visual grammar reuse
multi-stage Brain reasoning
```

Target V3 consistency level:

```text
project-consistent commercial image series
strong selected-image reference reuse
explicit character / product / brand-asset locks
automatic visual review
automatic retry on fixable failures
best-output selection for commercial use
beginner-friendly display of what was preserved and why
```

The benchmark is not to clone Lovart UI or canvas behavior. The benchmark is
to close the commercial visual-quality gap:

```text
same character stays recognizable
same product keeps shape/material/logo/proportions
same brand style stays coherent
same campaign keeps camera, light, palette, and layout language
bad outputs are not treated as final deliverables
users do not need design or prompt knowledge
```

---

## 3. Architecture Decision

### 3.1 Use one visual big module with child modules

Authoritative decision:

```text
Keep the V3-native Visual Capability Cluster as the single owner of reusable
visual enhancement.

Implement the new capabilities as child modules under that cluster.
Do not create many top-level independent shared modules directly wired into
CentralCreativeBrain.
```

Reason:

```text
strong references, identity locks, visual grammar, output review, retry
planning, and best-output selection are all parts of the same commercial
visual-consistency system.

If they are scattered as independent top-level modules, the central brain will
become heavy and future templates will duplicate policy.
```

Target structure:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/
  visual_cluster/
    __init__.py
    contracts.py
    orchestrator.py
    profile_builder.py
    grammar_snapshot.py
    reference_binding.py
    identity_lock.py
    product_lock.py
    brand_asset_lock.py
    negative_memory.py
    quality_review.py
    auto_retry.py
    best_output_selector.py
    suite_planner_policy.py
    template_policy.py
    audit.py
```

Current files may be kept and gradually wrapped:

```text
asset_role_analyzer.py
asset_binding_planner.py
case_library.py
visual_grammar_lock.py
prompt_constraint_compiler.py
output_review.py
history_reference.py
```

But by the end of this phase they must be dispatched through the cluster
orchestrator as child capabilities, not treated as scattered ownership points.

### 3.2 Central brain remains thin

CentralCreativeBrain should:

```text
read Visual Capability Cluster outputs
read LLM Brain checkpoint outputs
choose high-level creative strategy
compile structured plans
record auditable metadata
```

CentralCreativeBrain must not own:

```text
face identity extraction
product identity extraction
reference-image binding semantics
output visual review
automatic retry scoring
best-image selection
negative visual memory
template-specific consistency policy
```

Those belong to the Visual Capability Cluster.

### 3.3 LLM Brain role

The V3 LLM Brain is not the visual module.

It should:

```text
explain intent
choose strategy
turn visual-cluster outputs into prompt guidance
produce user-friendly progress messages
perform prompt/pre-generation checks
summarize post-generation review results
```

It must not become the only place where identity locks, strong-reference
binding, or retry policy live.

### 3.4 Project Mode remains the application layer

Project Mode should store and expose:

```text
selected images
active reference assets
identity/product/brand lock profiles
negative visual memory
review reports
retry attempts
best output selections
project timeline events
```

Project Mode should not implement the visual logic itself. It stores cluster
results and passes them back into future jobs.

---

## 4. Compatibility With Existing Documents

### 4.1 Documents kept intact

This phase does not replace:

```text
32 Project Mode core control
33 Project Mode compatibility and migration
34 Project contracts and context
35 Project-first frontend UX
36 General Template project flow
37 Template interface and audit
38 Project workspace continuation UX
39 Project context asset and feedback persistence
40 Project-to-Brand-Memory confirmation
41 Template manifest registry and activation gate
42 E-Commerce Template Project Mode unfreeze
43 Product experience quality gate
45 Template-first workspace and delete UX
46 Scene subpages and selection patch
47 Single production entry and suite flow
48 LLM Brain Adapter
49 General Template deproductization
50 Native Visual Capability Cluster
```

### 4.2 Document 11 relationship

Document `11` remains the foundational evaluation/refinement concept.

Doc51 adds the current Project Mode implementation target:

```text
closed-loop review must use selected project context, identity/product locks,
and visual-cluster results.

automatic retry must not be a generic "generate again"; it must use a
structured retry patch.
```

### 4.3 Document 48 relationship

Document `48` remains the Brain Adapter contract.

Doc51 clarifies:

```text
post-generation review hooks are implemented by the Visual Capability Cluster.
LLM Brain may summarize review and retry decisions, but it does not own the
review engine.
```

### 4.4 Document 50 relationship

Document `50` remains the ownership and consolidation rule.

Doc51 adds:

```text
the exact child modules needed to close the Lovart commercial consistency gap
the data contracts for strong references, identity locks, review, retry, and
best-output selection
the phase order and test plan
```

---

## 5. Commercial Consistency Levels

The implementation should make consistency measurable in levels.

```text
L0 one-off generation
  prompt creates an image, no project memory

L1 style continuity
  palette, mood, broad style, and project goal continue

L2 visual grammar continuity
  composition, light, camera, layout, materials, and image language continue

L3 strong selected-reference continuity
  selected outputs become actual provider reference inputs when files exist

L4 identity / product / brand-asset lock
  character face, hair, outfit, product shape, logo, material, brand assets,
  and camera language are explicitly preserved

L5 closed-loop commercial review
  bad outputs are reviewed, patched, retried, and ranked before delivery
```

Current V3 is mostly L1-L2, with partial L3.

This phase targets L3-L5.

---

## 6. Target Runtime Flow

### 6.1 First generation

```text
User creates project
  -> Project Mode builds ProjectContextPackage
  -> Visual Capability Cluster builds baseline visual profile
  -> LLM Brain runs checkpoints
  -> CentralCreativeBrain compiles plan
  -> Provider generates candidates
  -> Visual Capability Cluster reviews outputs
  -> AutoRetryPlanner retries fixable failures if budget remains
  -> BestOutputSelector ranks deliverable outputs
  -> Project Mode stores outputs, review reports, and timeline
  -> UI shows images first, with folded workflow details
```

### 6.2 User selects a good image

```text
User selects image
  -> Project Mode stores selected OutputRef
  -> StrongReferenceBinder resolves image file or preview asset
  -> Visual Capability Cluster classifies reference role
  -> IdentityLockProfile / ProductLockProfile / BrandAssetLockProfile updates
  -> ProjectVisualGrammarSnapshot updates
  -> Project timeline records "visual direction confirmed"
```

### 6.3 Continue generation

```text
User asks for another set
  -> Project Context includes selected refs, locks, negative memory, and visual snapshot
  -> StrongReferenceBinder marks hard/soft/negative refs
  -> PromptCompiler receives lock constraints
  -> Provider receives reference image inputs when available
  -> Generated outputs are reviewed against locks
  -> Retry happens automatically for fixable drift
  -> Best outputs append to project; old outputs are never overwritten
```

---

## 7. New Child Modules

### 7.1 StrongReferenceBinder

Purpose:

```text
Turn selected outputs and uploaded references into explicit provider-ready
reference bindings.
```

Inputs:

```text
ProjectContextPackage
selected_output_assets
selected_reference_assets
uploaded_reference_assets
current template_id / scenario_id
user_input
available output files
```

Outputs:

```text
VisualReferenceBindingProfile
StrongReferenceBinding records
provider_input_required_ids
hard_reference_ids
soft_reference_ids
negative_reference_ids
usage_rules
```

Reference role inference:

```text
general portrait / photographer:
  generated_identity_reference
  face_reference
  styling_reference
  camera_reference

general non-portrait:
  style_reference
  composition_reference
  lighting_reference

ecommerce:
  product_identity_reference
  product_shape_reference
  material_reference
  logo_reference

brand IP:
  brand_asset_reference
  mascot_identity_reference
  layout_reference
```

Rules:

```text
1. Only selected outputs can become positive generated references.
2. Unselected, deleted, or rejected outputs cannot become positive references.
3. Rejected outputs can become negative references or avoid rules.
4. If file_path exists, provider_input_required_ids must include the hard ref.
5. If no file exists, degrade to prompt-level reference notes with warning.
6. General Template must not infer product identity unless user intent or
   template explicitly requires product semantics.
```

### 7.2 IdentityLockProfileBuilder

Purpose:

```text
Create explicit consistency locks for characters, people, products, and
brand assets.
```

Profiles:

```text
CharacterIdentityLockProfile
ProductIdentityLockProfile
BrandAssetLockProfile
SceneIdentityLockProfile
```

Character locks:

```text
face_identity
age_range
facial_vibe
hair_color
hairstyle
skin_tone
outfit_style
key_accessories
body_proportion
pose_boundary
camera_distance
lens_language
lighting_language
forbidden_drift
```

Product locks:

```text
product_shape
material
color
logo_or_label_position
visible_packaging_facts
proportions
surface_texture
must_not_change
forbidden_extra_objects
```

Brand asset locks:

```text
brand_color_system
logo_usage
mascot_or_ip_shape
layout_language
typographic_mood_for_external_overlay
visual_symbol_rules
forbidden_brand_drift
```

Sources:

```text
selected output metadata
selected reference image
uploaded image metadata
visual grammar profile
LLM Brain intent summary
user-selected lock mode if UI later exposes it
```

First implementation can be hybrid:

```text
metadata + prompt-derived locks first
vision-model extraction later when a vision provider is configured
```

### 7.3 NegativeVisualMemory

Purpose:

```text
Turn user deletions, rejections, failed reviews, and bad outputs into avoid
rules for the project.
```

Sources:

```text
delete output
reject output
manual "not like this" feedback
review failure
retry patch
unwanted object detection
identity drift detection
```

Rules:

```text
1. Delete means remove from positive display and positive context.
2. Reject means add avoid direction.
3. Review failure can add machine-generated avoid direction.
4. Negative memory must be project-scoped unless user explicitly saves it to
   Brand Memory.
5. Negative memory must never leak across accounts or unrelated projects.
```

### 7.4 OutputQualityReviewer

Purpose:

```text
Review generated outputs against the user request, Project Context, visual
grammar snapshot, selected strong references, identity/product locks, and
commercial delivery rules.
```

Review dimensions:

```text
request_match_score
style_consistency_score
visual_grammar_score
identity_lock_score
product_integrity_score
brand_asset_score
text_artifact_score
watermark_score
composition_score
commercial_finish_score
overall_score
```

Issue categories:

```text
subject_drift
identity_drift
hair_or_outfit_drift
product_identity_drift
brand_asset_drift
unrelated_product_or_object
visible_text_artifact
watermark_or_signature
collage_or_split_screen
composition_mismatch
lighting_mismatch
low_commercial_finish
unsafe_or_policy_issue
```

Review modes:

```text
metadata_preflight
prompt_contract_review
vision_model_review
hybrid_review
manual_review_required
```

First implementation may use:

```text
metadata and prompt-contract checks
provider metadata
image dimensions
available visual review hooks
optional LLM/vision review behind settings
```

It must be designed so real vision review can be added without replacing the
contract.

### 7.5 AutoRetryPlanner

Purpose:

```text
Turn review failures into structured retry patches and decide whether to run
another generation attempt automatically.
```

Retry statuses:

```text
pass
warning
fail_retryable
fail_final
manual_review
```

Retry patch fields:

```text
strengthen_reference_ids
prompt_additions
negative_prompt_additions
lock_reinforcement
composition_repair
object_removal_instruction
identity_repair_instruction
product_repair_instruction
provider_hint_overrides
user_visible_reason
```

Retry limits:

```text
standard mode: max 1 auto retry
atelier/high-consistency mode: max 2 auto retries
provider/rate-limit failures: no visual retry; use provider error handling
policy failures: no auto retry unless safe prompt patch is possible
```

Rules:

```text
1. Auto retry never overwrites old project outputs.
2. Failed outputs may be hidden from default view but remain auditable.
3. Retry attempts must be timeline items.
4. Retry prompt patch must be visible in folded workflow details.
5. Auto retry must stop when the same failure repeats.
```

### 7.6 BestOutputSelector

Purpose:

```text
Choose the most commercially useful outputs from a batch after review.
```

Outputs:

```text
best_output_id
recommended_outputs
slot_fit
why_selected
warning_outputs
hidden_failed_outputs
```

Selection should consider:

```text
commercial finish
identity consistency
style consistency
clean composition
absence of text/watermark artifacts
fit for requested aspect ratio and platform
```

This module is important because commercial quality is not only generation
quality. It is also curation quality.

### 7.7 TemplateConsistencyPolicy

Purpose:

```text
Let each template define what consistency means without owning private visual
logic.
```

Initial policies:

```text
general_template:
  default priority: style + visual grammar
  upgrade to identity lock when people/characters are central

ecommerce_template:
  default priority: product truth + material/logo/proportion
  product reference is hard when product image exists

photographer_template:
  default priority: face/hair/outfit/camera/lens/lighting
  strong identity lock required after selection

brand_ip_template:
  default priority: mascot/brand asset shape + palette + symbol language

new_media_template:
  default priority: format + layout + topic consistency
```

Future templates must provide a policy entry instead of building custom
consistency code.

---

## 8. New And Extended Contracts

### 8.1 StrongReferenceBinding

```python
class StrongReferenceBinding(V3BaseModel):
    binding_id: str
    source_type: str  # selected_output | uploaded_asset | brand_memory | negative_output
    source_id: str
    asset_id: str | None = None
    output_id: str | None = None
    file_path: str | None = None
    preview_url: str | None = None
    role: str  # generated_identity_reference | product_identity_reference | style_reference | negative_reference
    strength: str  # hard | medium | soft | negative
    use_policy: str  # identity | product_identity | brand_asset | style | composition | lighting | negative
    lock_targets: list[str] = []
    provider_input_required: bool = False
    prompt_only_fallback: bool = False
    confidence: float = 0.0
    user_visible_label: str = ""
    metadata: dict[str, Any] = {}
```

### 8.2 VisualIdentityLockProfile

```python
class VisualIdentityLockProfile(V3BaseModel):
    lock_id: str
    project_id: str
    subject_type: str  # character | product | brand_asset | scene | generic
    lock_strength: str  # weak | normal | strong | exact_when_possible
    source_binding_ids: list[str] = []
    face_lock: dict[str, Any] = {}
    hair_lock: dict[str, Any] = {}
    wardrobe_lock: dict[str, Any] = {}
    product_lock: dict[str, Any] = {}
    brand_asset_lock: dict[str, Any] = {}
    camera_lock: dict[str, Any] = {}
    lighting_lock: dict[str, Any] = {}
    keep_rules: list[str] = []
    allowed_changes: list[str] = []
    forbidden_drift: list[str] = []
    prompt_constraints: list[str] = []
    negative_constraints: list[str] = []
    user_visible_summary: list[str] = []
    confidence: float = 0.0
    metadata: dict[str, Any] = {}
```

### 8.3 VisualQualityReviewReport

```python
class VisualQualityReviewReport(V3BaseModel):
    review_id: str
    project_id: str | None = None
    job_id: str
    candidate_id: str | None = None
    output_id: str | None = None
    status: str  # pass | warning | fail_retryable | fail_final | manual_review
    review_mode: str
    scores: dict[str, float] = {}
    detected_issues: list[dict[str, Any]] = []
    passed_checks: list[str] = []
    warning_notes: list[str] = []
    retry_patch: dict[str, Any] = {}
    user_visible_summary: list[str] = []
    metadata: dict[str, Any] = {}
```

### 8.4 AutoRetryDecision

```python
class AutoRetryDecision(V3BaseModel):
    decision_id: str
    job_id: str
    project_id: str | None = None
    should_retry: bool
    retry_attempt: int = 0
    max_attempts: int = 1
    reason_codes: list[str] = []
    retry_patch: dict[str, Any] = {}
    blocked_reason: str | None = None
    user_visible_reason: str = ""
    metadata: dict[str, Any] = {}
```

### 8.5 CommercialOutputSelection

```python
class CommercialOutputSelection(V3BaseModel):
    selection_id: str
    project_id: str
    job_id: str
    best_output_id: str | None = None
    recommended_output_ids: list[str] = []
    warning_output_ids: list[str] = []
    hidden_failed_output_ids: list[str] = []
    slot_fit: dict[str, str] = {}
    user_visible_reasons: list[str] = []
    metadata: dict[str, Any] = {}
```

### 8.6 ProjectContextPackage additions

Add optional fields:

```text
strong_reference_bindings
identity_lock_profiles
negative_visual_memory
latest_quality_reviews
latest_auto_retry_decisions
commercial_output_selection
template_consistency_policy
```

Compatibility:

```text
Existing clients may ignore these fields.
They are additive and must not break current ProjectContextPackage readers.
```

---

## 9. Implementation Plan

### Phase 0 - Document and baseline audit

Tasks:

```text
1. Add this document.
2. Add compatibility notes to documents 11, 29, 48, and 50.
3. Run rg audit for existing identity/review/retry wording.
4. Confirm no code changes are made in the documentation phase.
```

### Phase 1 - Contracts and cluster child registration

Files:

```text
app/shared_capabilities/visual_cluster/contracts.py
app/shared_capabilities/visual_cluster/__init__.py
app/shared_capabilities/visual_cluster/orchestrator.py
app/shared_capabilities/visual_cluster/template_policy.py
```

Tasks:

```text
1. Add new Pydantic contracts from section 8.
2. Register child modules under the Visual Capability Cluster.
3. Add feature flags for optional review/retry behavior.
4. Ensure missing optional child modules degrade with warnings.
5. Ensure required child module failures block only jobs that need them.
```

Tests:

```text
contract serialization
cluster result contains child module IDs
optional module failure warning
required module failure scoped blocking
```

### Phase 2 - Strong selected-reference binding

Files:

```text
visual_cluster/reference_binding.py
project_mode/service.py
product_api/service.py
generation_router/providers.py
tests/test_v3_project_mode.py
tests/test_v3_provider_output_production.py
```

Tasks:

```text
1. When an output is selected, resolve its stored file path if available.
2. Create StrongReferenceBinding records.
3. Classify selected references through TemplateConsistencyPolicy.
4. Add hard/soft/negative reference IDs to ProjectContextPackage.
5. Ensure provider request metadata and asset plan receive hard references.
6. If file missing, use prompt-only fallback with warning.
```

Acceptance:

```text
selected output file becomes provider reference input
unselected output is not passed
deleted output is not passed
rejected output becomes negative memory or avoid rule
provider metadata records reference IDs and roles
```

### Phase 3 - Identity/Product/Brand lock profiles

Files:

```text
visual_cluster/identity_lock.py
visual_cluster/product_lock.py
visual_cluster/brand_asset_lock.py
visual_cluster/profile_builder.py
agents/prompt_compiler_agent.py
generation_router/providers.py
project_mode/contracts.py
project_mode/service.py
```

Tasks:

```text
1. Build VisualIdentityLockProfile from strong references and visual grammar.
2. Add lock profile to ProjectContextPackage.
3. PromptCompilerAgent consumes lock prompt_constraints and negative_constraints.
4. Provider prompt repeats only concise, model-facing lock constraints.
5. UI folded workflow can show beginner-friendly lock summary.
```

No vision provider fallback:

```text
When no vision model is available, derive locks from user goal, selected-output
metadata, visual grammar profile, and reference roles. Mark confidence lower.
```

Vision provider upgrade:

```text
When configured, inspect selected images for face/hair/outfit/product/material
facts and raise lock confidence.
```

Acceptance:

```text
portrait project lock includes face/hair/outfit/camera fields
product project lock includes shape/material/logo/proportion fields
general non-product project stays style/grammar oriented
prompt contains explicit identity/product lock constraints when applicable
```

### Phase 4 - Output quality review

Files:

```text
visual_cluster/quality_review.py
product_api/service.py
project_mode/service.py
llm_brain/contracts.py
llm_brain/adapter.py
```

Tasks:

```text
1. Run review after provider returns outputs.
2. Compare each output against project goal, selected refs, lock profile,
   visual grammar, and commercial artifact rules.
3. Produce VisualQualityReviewReport for each candidate/output.
4. Store reports in job metadata, output metadata, and project timeline.
5. Expose beginner-friendly review summary in folded workflow details.
```

Review issue examples:

```text
identity drift
hair/outfit drift
product shape drift
unrelated product/object
visible text artifact
watermark/signature
collage/split screen
low commercial finish
```

Acceptance:

```text
every generated V3 output has a review report
review can mark pass/warning/fail_retryable/fail_final/manual_review
review does not delete outputs
review never updates Brand Memory automatically
```

### Phase 5 - Automatic retry planner

Files:

```text
visual_cluster/auto_retry.py
product_api/service.py
generation_router/providers.py
creative_core/central_brain.py
tests/test_v3_generation_loop.py
```

Tasks:

```text
1. Convert fail_retryable reports into AutoRetryDecision.
2. Build retry_patch with positive and negative prompt changes.
3. Re-run generation through normal V3 job/generation path.
4. Append retry output; never overwrite old outputs.
5. Stop retry if max attempts reached or same failure repeats.
6. Store retry attempt timeline event.
```

Retry patch examples:

```text
strengthen selected identity reference
preserve black hair and original hairstyle
keep the same camera distance and soft summer light
remove unrelated cosmetic bottle
avoid visible text, watermark, and split panels
restore product shape and material
```

Acceptance:

```text
retry happens only for retryable visual failures
retry patch is auditable
old outputs remain in project history
failed retry loops stop safely
provider/rate-limit errors do not trigger visual retry
```

### Phase 6 - Best output selector

Files:

```text
visual_cluster/best_output_selector.py
product_api/service.py
project_mode/service.py
src_skeleton/app/static/app.js
src_skeleton/app/static/styles.css
```

Tasks:

```text
1. Rank outputs after review and retry.
2. Mark best/recommended/warning/failed output groups.
3. UI keeps images primary but can add small labels:
   "推荐", "可用", "需确认".
4. Do not hide everything if all outputs are warnings; show the best available
   with a plain-language note.
```

Acceptance:

```text
best output chosen for each generated set
recommended outputs appear first
failed outputs are hidden from beginner default view but remain auditable
```

### Phase 7 - UI and beginner-facing workflow

Rules:

```text
1. Do not show module names such as IdentityLockProfile or AutoRetryPlanner.
2. Do not show provider, adapter, raw JSON, job id, manifest, or cluster names.
3. Main project page stays image-first.
4. Advanced workflow details stay folded.
5. Progress bar messages explain outcomes in plain language.
```

Suggested beginner copy:

```text
已锁定这组图的参考方向
会尽量保持人物气质、发型、服装方向和画面光感
已自动检查杂字、水印、拼版和跑偏问题
发现跑偏时，V3 会自动修正再生成一次
推荐优先使用这张
```

### Phase 8 - Audit and full regression

Required command bundle:

```powershell
python -m pytest alchemy_creative_agent_3_0\tests -q
python -m pytest tests\test_v3_commercial_frontend_shell.py -q
python -m pytest tests\test_api_smoke.py -q
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
node --check src_skeleton\app\static\app.js
node --check src_skeleton\app\mobile_static\mobile.js
git diff --check
```

Browser QA is required if frontend behavior changes.

---

## 10. Commercial Quality Gates

### 10.1 Strong reference gate

Pass only when:

```text
selected output appears in ProjectContextPackage
selected output has a StrongReferenceBinding
selected output file path is passed to provider when available
unselected/rejected/deleted outputs are excluded from positive refs
provider metadata records reference count and binding roles
```

### 10.2 Identity lock gate

Pass only when:

```text
portrait continuation contains explicit face/hair/outfit/camera lock
product continuation contains explicit shape/material/logo/proportion lock
brand asset continuation contains explicit palette/logo/symbol/layout lock
prompt constraints and provider prompts include applicable locks
non-applicable locks do not contaminate general creative prompts
```

### 10.3 Review and retry gate

Pass only when:

```text
generated outputs receive review reports
retryable failures produce retry patches
automatic retry appends new outputs
old outputs are not overwritten
failed outputs are auditable
retry stops safely
```

### 10.4 Beginner UX gate

Pass only when:

```text
user sees images first
user can understand what was preserved
user can understand whether V3 auto-fixed anything
advanced details remain folded
normal UI has no engineering terms
mobile layout remains clean
```

### 10.5 Lovart-gap gate

Use a fixed validation project, for example:

```text
Create a refreshing summer portrait set of an East Asian young woman, clean,
premium, translucent, suitable for social cover.
Select the best image.
Continue the same project with two more images.
```

Pass expectations:

```text
same character vibe remains recognizable
hair direction does not drift randomly
outfit/styling direction remains coherent unless user asks to change it
camera and light language remain related
no unrelated product enters the scene
no visible text/watermark/split panel appears
new outputs append to the same project
review metadata explains pass/warning/retry in simple terms
```

---

## 11. Memory Model Clarification

Do not store all consistency as Brand Memory.

Use three scopes:

```text
BrandStyleMemory
  long-term reusable brand taste, palette, tone, visual language

ProjectIdentityMemory
  current project's character/product/asset identity locks

CampaignVisualMemory
  current project/campaign's series rules, camera, layout, and negative memory
```

Rules:

```text
1. ProjectIdentityMemory is project-scoped by default.
2. BrandStyleMemory requires explicit user confirmation.
3. Failed/rejected outputs become project negative memory first.
4. Nothing identity-specific should become global brand style automatically.
5. Account scoping remains mandatory.
```

---

## 12. Template Policy Matrix

| Template | Main consistency priority | Strong ref default | Identity lock default | Review focus |
| --- | --- | --- | --- | --- |
| General | style and visual grammar | soft, upgraded by subject | auto when people/products central | drift, artifacts, composition |
| E-Commerce | product truth | hard for product references | product identity hard | product drift, claims, extra objects |
| Photographer | character and camera | hard after selection | character identity hard | face/hair/outfit/lens drift |
| Brand IP | brand asset/IP shape | hard for brand assets | brand asset hard | mascot/logo/palette drift |
| New Media | format and layout | soft | normally off | layout and platform fit |

Future templates must add policy rows instead of private consistency code.

---

## 13. Non-Goals

This phase does not require:

```text
rewriting Project Mode
rewriting ScenarioRuntime
rewriting Product API from scratch
creating a Lovart-style infinite canvas
adding layer-based manual design editing
calling V1/V2 runtime code
adding Claude Code as V3 brain
showing engineering workflow internals to normal users
automatic global Brand Memory overwrite
guaranteeing perfect real-person identity without suitable reference/provider
```

---

## 14. Risks And Guardrails

### 14.1 Over-locking risk

If locks are too strict, outputs become repetitive.

Guardrail:

```text
separate keep_rules from allowed_changes
template policy controls lock strength
user prompt can explicitly request a new outfit/scene/composition
```

### 14.2 Provider limitation risk

Some providers may not preserve identity strongly even with references.

Guardrail:

```text
record provider capability
degrade to prompt-level constraints with warning
review output and retry when drift is fixable
do not overpromise exact identity preservation in UI
```

### 14.3 Review false-positive risk

Automated review may incorrectly reject creative variations.

Guardrail:

```text
use warning/manual_review when confidence is low
show best available output if all candidates are warnings
let user select outputs manually
negative memory only becomes strong after explicit reject/delete/repeated review
```

### 14.4 Context leakage risk

Identity/product locks may leak across projects.

Guardrail:

```text
project-scoped by default
brand memory only by explicit confirmation
account scoping tests
template isolation tests
```

---

## 15. Implementation Handoff Prompt

When coding begins, use this handoff:

```text
Implement document 51.

Do not rewrite the V3 foundation. Keep Project Mode, ScenarioRuntime, Product
API, provider storage, LLM Brain, and document 50 Visual Capability Cluster
ownership intact.

Add the next Visual Capability Cluster child modules:
StrongReferenceBinder, IdentityLockProfileBuilder, ProductLockProfileBuilder,
BrandAssetLockProfileBuilder, NegativeVisualMemory, OutputQualityReviewer,
AutoRetryPlanner, BestOutputSelector, and TemplateConsistencyPolicy.

Selected outputs must become strong references when files exist. Identity,
product, and brand-asset locks must be explicit structured contracts. Generated
outputs must receive review reports. Retryable visual failures must produce a
retry patch and append retried outputs without overwriting old project outputs.

Keep UI beginner-facing, image-first, and free of engineering terms. Fold
workflow details. No V1/V2 runtime imports. No Claude Code expert/provider
route. Run the verification bundle and a real project continuation validation.
```
