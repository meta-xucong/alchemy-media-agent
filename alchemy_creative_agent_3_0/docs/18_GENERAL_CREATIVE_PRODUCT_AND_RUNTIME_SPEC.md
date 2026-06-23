# 18 General Creative Product, UI, and Application Runtime Specification

This document defines the complete user-facing **General Creative** product module for Alchemy Creative Agent 3.x.

It is designed to be implemented **after**:

```text
the accepted V3 core foundation
the accepted brand-memory and generation-loop contracts
the accepted Scenario Pack Platform extension in document 17
```

It does not replace, rename, or fork the existing Central Creative Brain, base agents, core schemas, provider interfaces, evaluation loop, brand-memory authority, or scenario-pack runtime.

Its purpose is to close the remaining product implementation gap between:

```text
a completed V3 creative runtime
```

and:

```text
a complete General Creative UI and application workflow
that future specialization packs can reuse without rebuilding product infrastructure
```

The target flow is:

```text
V3 Scenario Hub
→ General Creative card
→ shared V3 creative workspace
→ natural-language request
→ existing ScenarioRuntime
→ DefaultCommercialPack
→ existing Central Creative Brain
→ candidates / evaluation / refinement / rendering / packaging
→ user selection / regeneration / continuation / brand confirmation / export
```

The General Creative module is the product baseline and regression control for all future specialization packs.

## Current-Stage Boundary

This document defines the only fully usable scenario module in the current V3
frontend stage:

```text
General Creative / 通用创作
```

The current stage includes:

```text
V3 home UI entry from the shared product shell
Scenario Hub card grid
five first-screen scenario cards:
  General Creative / 通用创作
  E-Commerce / 电商特调
  New Media Marketing / 新媒体营销
  Private Community Operations / 私域社群运营
  Brand IP Operations / 品牌 IP 运营
General Creative card and full workspace
General Creative beginner workflow
General Creative agent intent logic
shared job/result/history infrastructure needed by General Creative
```

The current stage explicitly excludes detailed implementation of:

```text
E-Commerce / 电商特调
New Media Marketing / 新媒体营销
Private Community Operations / 私域社群运营
Brand IP Operations / 品牌 IP 运营
AI Manga Drama / AI 漫剧
other future specialization packs
```

Those cards may appear in the V3 home as non-executable placeholders only.
They must not define pack-owned agents, pack-owned APIs, pack-specific
generation strategies, pack-specific evaluation rules, or complex pack-specific
forms in this document.

Any future specialized pack must be specified in its own accepted document and
must reuse the General Creative workspace/runtime contracts instead of redefining
them.

Therefore, this document must be read as:

```text
complete now:
  General Creative frontend
  General Creative application runtime
  General Creative intent logic
  shared workspace services required by General Creative

placeholder now:
  ecommerce
  new_media_marketing
  private_community_operations
  brand_ip_operations

future only:
  all detailed pack-specific forms
  all detailed pack-specific agents
  all detailed pack-specific APIs
  all pack-specific generation and evaluation strategies
```

---

## 1. Document Status and Compatibility

### 1.1 Additive Companion Specification

This document is a companion to:

```text
00_ROOT_RULES.md
01_PRODUCT_VISION.md
02_SYSTEM_ARCHITECTURE.md
03_AGENT_AND_MODULE_SPEC.md
07_SCHEMA_CONTRACTS.md
09_RULES_AND_DEFAULTS.md
10_BRAND_MEMORY_SPEC.md
11_EVALUATION_AND_REFINEMENT_SPEC.md
12_PROVIDER_INTERFACES.md
13_STEP_BY_STEP_DELIVERY_PLAN.md
15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
```

It adds:

```text
General Creative product modes
shared-workspace UI behavior
frontend state and interaction contracts
application-layer job lifecycle
job / run / attempt persistence
user action semantics
V3 API request and response contracts
candidate-selection flow
regeneration flow
brand-continuation flow
text-only revision flow
export flow
partial-failure behavior
product-level tests and acceptance gates
```

### 1.2 Existing Contracts Remain Authoritative

Precedence:

```text
1. 00_ROOT_RULES.md
2. frozen V3 core schemas and provider contracts
3. existing Central Creative Brain behavior
4. 17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
5. this General Creative product specification
6. future specialization-pack product specifications
```

This document must not be interpreted as permission to:

```text
add required fields to frozen core schemas
replace DefaultCommercialPack
bypass ScenarioRuntime
call providers directly from the UI or ScenarioPack
create a second General Creative pipeline
apply brand memory without an allowed update signal
expose provider or model internals to normal users
```

### 1.3 Relationship to document 17

document 17 defines:

```text
Scenario Hub
ScenarioPack registry
ScenarioRuntime
manifest-driven UI
shared ScenarioWorkspace
GeneralCreativeScenarioPack
internal scenario API boundary
```

This document defines the detailed implementation of the **General Creative experience inside that shared workspace**.

document 17 remains unchanged.

The minimal General Creative manifest shown in document 17 is still a valid bootstrap manifest. After this document is implemented, its General Creative `modes`, `quick_actions`, and `result_sections` may be expanded using the manifest example in this document.

### 1.4 No Product-Version Renaming

This document does not redefine V3.0, V3.1, V3.2, or later delivery waves.

For implementation sequencing inside this document, use:

```text
G0, G1, G2, G3, G4, G5, G6
```

These are General Creative implementation phases only.

### 1.5 Baseline Assumption

The accepted baseline should already provide, or provide capability-gated equivalents for:

```text
CreativeJob → CommercialAssetPack pipeline
DefaultCommercialPack
ScenarioRuntime
GeneralCreativeScenarioPack
brand-memory store and MemoryUpdate contract
candidate generation abstraction
candidate evaluation and refinement loop
RendererProvider contract
V3 API namespace
V3-owned frontend boundary
```

Optional capabilities may remain unavailable at runtime.

Unavailable optional capabilities must degrade visibly and safely rather than breaking General Creative.

---

## 2. Product Objective

General Creative is the default, non-specialized product experience for commercial visual creation.

It should let a non-design user:

```text
describe a commercial need
optionally upload product, logo, or reference assets
optionally choose an existing brand
receive one image or a small coordinated asset series
review generated candidates
select preferred results
regenerate weak results
continue the same style in a new job
modify exact commercial text without regenerating the base visual
save an approved style into brand memory
export usable assets and metadata
```

The product promise remains:

```text
Say what you need.
Alchemy operates the commercial creative workflow for you.
```

General Creative must not become:

```text
a prompt playground
a model-selection panel
a node graph
a professional canvas editor
a layer-heavy design workstation
a separate vertical specialization
```

---

## 3. Non-Negotiable Product Rules

### 3.1 General Creative Is Policy-Neutral

The General Creative ScenarioPack must remain bound to:

```text
DefaultCommercialPack
```

It must not inject:

```text
industry-specific commercial strategy
specialized platform rules beyond existing core defaults
specialized evaluation weights
specialized provider preferences
specialized asset recipes
opaque prompt patches
```

General product modes may make existing user intent explicit, but they must not create a new specialization policy layer.

### 3.2 One Shared Runtime

Correct:

```text
General Creative UI
→ shared V3 JobApplicationService
→ ScenarioApplicationService
→ ScenarioRuntime
→ GeneralCreativeScenarioPack
→ DefaultCommercialPack
→ Central Creative Brain
```

Incorrect:

```text
General Creative UI
→ General-only creative pipeline
```

### 3.3 Application Logic Must Not Become Creative Logic

The application layer may own:

```text
job persistence
status transitions
idempotency
uploads
user selections
action authorization
event delivery
export requests
render revisions
brand-update confirmation
```

It must not own:

```text
creative brief reasoning
creative direction
series planning
layout planning
prompt compilation
provider routing
candidate scoring
refinement strategy
```

Those remain inside the existing V3 runtime.

### 3.4 Historical Outputs Are Immutable

A completed core run must not be edited in place.

User actions must create explicit records:

```text
new GenerationAttempt
new RunRecord when a larger re-plan is required
new CandidateSelection
new RenderRevision
new ExportRecord
new child JobRecord for style continuation
```

Old candidates and old metadata remain auditable.

### 3.5 Persistent Brand Updates Require Confirmation

The default behavior is:

```text
accepted output
→ proposed MemoryUpdate
→ visible user confirmation
→ apply or reject
```

The UI must not silently convert every result into persistent brand memory.

### 3.6 Exact Text Changes Must Avoid Image Regeneration

When a valid rendered base visual already exists:

```text
edit headline / subtitle / offer / price / CTA
→ validate text
→ create RenderRevision
→ call V3 renderer path
→ preserve base visual
```

Do not regenerate the image model output only to change exact text.

### 3.7 Product Controls Must Remain Human-Level

Allowed controls include:

```text
output mode
target platform
aspect ratio
brand
reference assets
required text
content to avoid
creative adjustment instruction
```

Do not expose by default:

```text
model name
seed
sampler
steps
CFG
LoRA
ControlNet
IP-Adapter scale
workflow graph
provider endpoint
raw system prompt
```

### 3.8 Backend Determines Allowed Actions

The frontend must not infer action availability only from local UI state.

Every job and asset view should include backend-computed allowed actions such as:

```text
select_candidate
regenerate_asset
regenerate_series
continue_style
edit_text
apply_brand_memory
export
cancel
```

### 3.9 General Creative Is the Regression Control

Adding future specialization packs must not change General Creative behavior for identical:

```text
user input
explicit controls
brand profile
provider availability
core configuration
rules version
```

Scenario metadata may differ. Core commercial outputs must not change solely because another pack was installed.

---

## 4. Scope

### 4.1 In Scope

This document covers:

```text
General Creative modes
General Creative route and page
shared composer behavior
brand selection
asset upload
optional quick controls
job submission
job progress
asset-series display
candidate review and selection
regeneration
style continuation
text-only revision
brand-memory confirmation
export
recent-job continuation
application services
application DTOs
job state machine
event model
API routes
error handling
responsive behavior
accessibility
tests
delivery phases
```

### 4.2 Out of Scope

This document does not define:

```text
e-commerce tuning rules
new-media tuning rules
private-community tuning rules
AI manga-drama tuning rules
brand-IP tuning rules
a professional freeform canvas
manual layer editing
video timeline editing
multi-user review
arbitrary cross-pack composition
third-party frontend plugins
raw provider configuration
analytics-driven automatic memory updates
production asset CDN implementation details
```

Future specialization documents must reuse the product runtime defined here.

---

## 5. Terminology and Record Model

### 5.1 Core CreativeJob

`CreativeJob` remains the frozen V3 core input schema from document 07.

It represents:

```text
the normalized creative request entering the Central Creative Brain
```

This document does not add required fields to `CreativeJob`.

### 5.2 JobRecord

`JobRecord` is an additive application-layer record.

It represents:

```text
one user-visible product job and its lifecycle
```

It stores references to:

```text
the original API request
the normalized CreativeJob
scenario selection and pinned versions
current status
runs
assets
warnings
user actions
brand-memory proposal
exports
timestamps
ownership metadata
```

### 5.3 RunRecord

A `RunRecord` represents one immutable invocation of the V3 creative runtime for a JobRecord.

Examples:

```text
initial run
whole-series creative adjustment run
asset-level regeneration run when the core re-enters planning
```

A run stores snapshots or stable references to:

```text
CommercialBrief
BrandProfile used
CreativePlan
SeriesPlan
LayoutPlans
PromptCompilationResults
ConditionPlans
GenerationPlans
EvaluationReports
CommercialAssetPack
scenario context and policy checksum
provider metadata
```

### 5.4 AssetRunRecord

An `AssetRunRecord` represents one `AssetSpec` inside one run.

It tracks:

```text
asset status
candidate batches
selected candidate
render revisions
warnings
failure information
```

### 5.5 GenerationAttemptRecord

A `GenerationAttemptRecord` represents one candidate batch for one asset.

Examples:

```text
initial candidate batch
automatic refinement round 1
automatic refinement round 2
user-requested regeneration
```

It must preserve:

```text
source plan ids
candidate ids
evaluation ids
refinement plan id when applicable
provider metadata
attempt reason
attempt index
```

### 5.6 CandidateResult

`CandidateResult` remains the existing V3 core schema.

The application layer may expose a user-safe `CandidateView`, but it must not redefine the core candidate contract.

### 5.7 CandidateSelection

A `CandidateSelection` is an application-layer record of an explicit user choice.

It should include:

```text
selection_id
job_id
run_id
asset_id
candidate_id
selected_by
selected_at
selection_reason if supplied
memory_update_requested
metadata
```

### 5.8 RenderRevision

A `RenderRevision` is an immutable text-rendering revision based on:

```text
one selected base visual
one LayoutPlan or allowed layout revision
one exact TextContent payload
one RendererProvider execution
```

### 5.9 ExportRecord

An `ExportRecord` represents one requested export package and its status.

### 5.10 Parent and Child Jobs

Style continuation must create a new JobRecord.

Relationships:

```text
parent_job_id
continuation_source_asset_ids
continuation_source_brand_id
continuation_reason
```

The original job remains unchanged.

---

## 6. General Creative Product Modes

General Creative should expose three active product modes and one optional experimental mode.

These modes make existing V3 product behavior explicit. They do not add specialization policies.

### 6.1 `auto_commercial_series`

Chinese label:

```text
自动系列
```

Purpose:

```text
Create a small coordinated commercial visual series from one request.
```

Mapping:

```text
ScenarioSelection.pack_id = general_creative
ScenarioSelection.mode_id = auto_commercial_series
CreativeJob.requested_output = commercial_image_series
```

Default behavior:

```text
use existing platform detection
use existing SeriesPlanner
use existing default series rules
use existing candidate and refinement policies
```

This is the default mode.

### 6.2 `single_asset`

Chinese label:

```text
单张图片
```

Purpose:

```text
Create one primary commercial image while preserving the same planning,
evaluation, refinement, rendering, and packaging pipeline.
```

Mapping:

```text
ScenarioSelection.pack_id = general_creative
ScenarioSelection.mode_id = single_asset
CreativeJob.requested_output = single_image
```

The application service may also add an auditable explicit constraint such as:

```text
output_count = 1
```

It must not bypass SeriesPlanner. SeriesPlanner should return one `AssetSpec`.

### 6.3 `brand_continuation`

Chinese label:

```text
延续品牌风格
```

Purpose:

```text
Create new content using an existing persistent BrandProfile
or approved assets from a previous job.
```

Mapping:

```text
ScenarioSelection.pack_id = general_creative
ScenarioSelection.mode_id = brand_continuation
CreativeJob.requested_output = commercial_image_series or single_image
CreativeJob.optional_brand_id = selected brand id when available
```

Frontend behavior:

```text
make BrandPicker prominent
show recent compatible jobs
allow selected prior assets to be used as references
explain which brand will be used
```

If no brand or prior job can be resolved:

```text
the UI should request a selection before submission where practical
the backend must still follow existing V3 fallback behavior
create a temporary BrandProfile
return structured warning metadata
do not pretend true continuation occurred
```

### 6.4 `template_matched`

Chinese label:

```text
模板匹配
```

Initial status:

```text
experimental or hidden
```

Purpose:

```text
Use optional_template_id or a future V3-owned template registry
to guide structure without copying blindly.
```

Rules:

```text
do not expose as a primary mode until template ownership,
versioning, compatibility, and rights rules exist
do not create a separate template runtime
templates may guide LayoutPlan and asset structure only through V3 contracts
```

### 6.5 Mode Selection Precedence

Recommended precedence:

```text
1. explicit mode selected in UI or API
2. explicit natural-language request such as “一张” or “沿用上次”
3. validated deep-link mode
4. auto_commercial_series default
```

Conflicts must be recorded.

Example:

```text
UI mode = single_asset
user text = “做一组”
```

Behavior:

```text
explicit UI mode wins
original text remains preserved
metadata records mode_conflict
UI may show a non-blocking confirmation before submission
```

### 6.6 Mode Capability Gates

| Mode | Required capability | Degraded behavior |
|---|---|---|
| `auto_commercial_series` | base V3 pipeline | planning-only result if generation unavailable |
| `single_asset` | base V3 pipeline | planning-only single AssetSpec |
| `brand_continuation` | brand-memory read | temporary brand with warning if unavailable |
| `template_matched` | V3 template registry | hidden or unavailable |

---

## 7. General Creative Manifest Extension

### 7.1 Binding Must Not Change

The General Creative manifest must preserve:

```text
pack_id: general_creative
bound_vertical_pack: DefaultCommercialPack
required capability modules: none
selection_policy: explicit_or_default
```

### 7.2 Policy Behavior Must Remain Empty

For every General Creative mode:

```python
GeneralCreativeScenarioPack.build_policy_bundle(...)
```

should return an empty or baseline-equivalent `ScenarioPolicyBundle`.

Mode-to-request mapping belongs in the application layer.

The General pack must not use mode selection to inject hidden creative rules.

### 7.3 Recommended Modes

```json
[
  {
    "mode_id": "auto_commercial_series",
    "display_name": {
      "zh-CN": "自动系列",
      "en-US": "Auto Series"
    },
    "status": "active",
    "default_parameters": {
      "requested_output": "commercial_image_series"
    },
    "required_modules": [],
    "optional_modules": [],
    "ui_overrides": {},
    "metadata": {
      "default": true
    }
  },
  {
    "mode_id": "single_asset",
    "display_name": {
      "zh-CN": "单张图片",
      "en-US": "Single Image"
    },
    "status": "active",
    "default_parameters": {
      "requested_output": "single_image"
    },
    "required_modules": [],
    "optional_modules": [],
    "ui_overrides": {},
    "metadata": {}
  },
  {
    "mode_id": "brand_continuation",
    "display_name": {
      "zh-CN": "延续品牌风格",
      "en-US": "Continue Brand Style"
    },
    "status": "active",
    "default_parameters": {
      "requested_output": "commercial_image_series",
      "prefer_persistent_brand": true
    },
    "required_modules": [],
    "optional_modules": [],
    "ui_overrides": {
      "brand_picker_prominence": "high",
      "show_recent_jobs": true
    },
    "metadata": {}
  },
  {
    "mode_id": "template_matched",
    "display_name": {
      "zh-CN": "模板匹配",
      "en-US": "Template Matched"
    },
    "status": "experimental",
    "default_parameters": {},
    "required_modules": [],
    "optional_modules": [],
    "ui_overrides": {
      "hidden_without_capability": "template_registry"
    },
    "metadata": {}
  }
]
```

---

## 8. Target Product Architecture

### 8.1 High-Level Flow

```text
General Creative route
  ↓
Shared ScenarioWorkspace
  ↓
GeneralCreativeDraft
  ↓
CreateCreativeJobRequest from document 17
  ↓
JobApplicationService
  ├── validation
  ├── idempotency
  ├── balance estimate / reservation through V3BalanceAdapter
  ├── JobRecord creation
  └── execution submission
  ↓
ScenarioApplicationService
  ↓
ScenarioRuntime
  ↓
GeneralCreativeScenarioPack
  ↓
DefaultCommercialPack
  ↓
Central Creative Brain
  ↓
V3 providers / evaluation / refinement / renderer / packager
  ↓
JobRepository + EventRepository
  ↓
JobView
  ↓
Shared ScenarioWorkspace
```

### 8.2 Action Flow

```text
User action
  ↓
V3 action endpoint
  ↓
JobApplicationService validates ownership, status, version, capability
  ↓
specialized application service
  ├── CandidateSelectionService
  ├── RegenerationService
  ├── ContinuationService
  ├── TextRevisionService
  ├── BrandConfirmationService
  └── ExportService
  ↓
existing V3 runtime or provider interface as appropriate
  ↓
new immutable action record
  ↓
updated JobView and events
```

### 8.3 Dependency Direction

Required:

```text
General UI depends on V3 API view contracts
V3 route layer depends on application services
application services depend on repositories and ScenarioApplicationService
ScenarioApplicationService depends on ScenarioRuntime
ScenarioRuntime depends on existing extension contracts
Central Creative Brain depends on existing core schemas and provider contracts
```

Forbidden:

```text
General UI imports core agents
General UI constructs provider payloads
JobApplicationService edits prompts directly
CandidateSelectionService calls image provider
GeneralCreativeScenarioPack stores UI state
RendererProvider writes BrandProfile directly
```

---

## 9. Additive Directory Structure

Do not move existing V3 modules.

Add equivalent V3-owned responsibilities beside the current structure.

```text
alchemy_creative_agent_3_0/
  docs/
    18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md

  app/
    application/
      __init__.py

      jobs/
        __init__.py
        models.py
        views.py
        repository.py
        service.py
        executor.py
        state_machine.py
        action_policy.py
        events.py
        errors.py

      uploads/
        __init__.py
        models.py
        repository.py
        service.py
        validation.py

      selections/
        __init__.py
        models.py
        service.py

      regeneration/
        __init__.py
        models.py
        service.py

      continuation/
        __init__.py
        models.py
        service.py

      rendering/
        __init__.py
        models.py
        text_content.py
        revision_service.py

      brand_confirmation/
        __init__.py
        service.py

      exports/
        __init__.py
        models.py
        repository.py
        service.py
        packager.py

    app_shell/
      existing files remain
      general_creative_contracts.py
      job_routes.py
      upload_routes.py
      brand_routes.py
      export_routes.py
      event_routes.py

  tests/
    application/
      test_general_mode_mapping.py
      test_job_state_machine.py
      test_job_application_service.py
      test_job_action_policy.py
      test_job_idempotency.py
      test_job_partial_completion.py
      test_candidate_selection_service.py
      test_regeneration_service.py
      test_continuation_service.py
      test_text_revision_service.py
      test_brand_confirmation_service.py
      test_export_service.py
      test_upload_validation.py
      test_job_event_stream.py

    api/
      test_general_create_job_api.py
      test_job_view_api.py
      test_candidate_selection_api.py
      test_regeneration_api.py
      test_continuation_api.py
      test_text_revision_api.py
      test_brand_memory_apply_api.py
      test_export_api.py
      test_cancel_api.py

    ui_contracts/
      test_general_workspace_manifest.py
      test_general_action_availability.py
      test_general_empty_states.py
      test_general_mobile_contract.py

    end_to_end/
      test_general_auto_series_flow.py
      test_general_single_asset_flow.py
      test_general_brand_continuation_flow.py
      test_general_partial_failure_flow.py
      test_general_text_only_revision_flow.py
      test_general_regression_against_default_pack.py
```

Frontend files should live inside the existing V3-owned frontend root.

Recommended responsibility layout:

```text
v3-frontend/
  routes/
    GeneralCreativeRoute

  workspaces/
    ScenarioWorkspace
    general/
      GeneralModeSelector
      GeneralComposer
      GeneralEmptyState
      GeneralResultActions

  components/
    ScenarioHeader
    NaturalLanguageInput
    BrandPicker
    AssetUploader
    OptionalQuickControls
    JobProgress
    AssetSeriesViewer
    AssetCard
    CandidateSelector
    TextRevisionPanel
    RegenerateDialog
    ContinueStyleDialog
    BrandSaveDialog
    ExportDialog
    WarningsPanel
    MetadataSummary

  state/
    creativeDraftStore
    jobViewStore
    actionMutationStore

  api/
    v3CreativeAgentClient
```

Exact filenames may adapt to the implementation stack.

The responsibility boundaries are normative.

---

## 10. Frontend Information Architecture

### 10.1 Route

General Creative route:

```text
/v3/creative-agent/scenarios/general_creative
```

Optional validated mode query:

```text
/v3/creative-agent/scenarios/general_creative?mode=single_asset
```

The UI must validate the mode against the loaded manifest.

Unknown modes must fall back to the manifest default and show no executable unvalidated state.

### 10.2 Page Regions

The page should contain:

```text
1. Scenario header
2. Product mode selector
3. Natural-language composer
4. Optional brand and asset inputs
5. Progressive quick controls
6. Primary create action
7. Recent compatible jobs or examples
8. Job progress area after submission
9. Asset-series result area
10. Asset detail / candidate review area
11. Global result actions
12. Structured warnings and metadata summary
```

For beginner users, the default visible version of this page must reduce to:

```text
one main input box
quick-start scene cards
optional brand selector
optional reference upload
one primary generate button
result area
history area
```

Advanced configuration may exist behind an explicit disclosure control, but the
default page must not require the user to understand model names, providers,
adapters, samplers, node graphs, seeds, or other engineering concepts.

The General workspace must cover common non-specialized needs:

```text
one-sentence commercial image request
single image
multi-image series
festival or campaign image
poster / cover / promotional image
brand-style continuation
reference-image recreation
text or price revision
automatic planning when the user is unsure
```

### 10.3 Initial Desktop Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 通用创作                                      [返回场景中心]          │
│ 用一句话描述需求，Alchemy 自动完成商业视觉生产。                     │
├──────────────────────────────────────────────────────────────────────┤
│ [自动系列] [单张图片] [延续品牌风格]                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  描述你需要什么                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 例如：帮我做一组夏季新品推广图，清爽、高级，适合小红书。      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  [上传产品/Logo/参考图]  [选择品牌]                                  │
│                                                                      │
│  快速设置： [平台：自动] [比例：自动] [必须出现的文字]               │
│  高级设置 ▾                                                          │
│                                                                      │
│                                          [开始创作]                  │
├──────────────────────────────────────────────────────────────────────┤
│ 示例需求                                     最近项目                │
└──────────────────────────────────────────────────────────────────────┘
```

### 10.4 Progress Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 正在创作：奶茶店夏季新品推广                                         │
│ [取消任务]                                                           │
├──────────────────────────────────────────────────────────────────────┤
│ ✓ 理解业务需求                                                       │
│ ✓ 制定视觉方向                                                       │
│ ● 生成候选方案                                                       │
│ ○ 检查商业效果                                                       │
│ ○ 优化较弱结果                                                       │
│ ○ 排版准确文字                                                       │
│ ○ 整理最终素材                                                       │
├──────────────────────────────────────────────────────────────────────┤
│ [主视觉骨架] [社交封面骨架] [方形商品图骨架]                          │
└──────────────────────────────────────────────────────────────────────┘
```

Do not display private reasoning or raw chain-of-thought.

Progress messages must be concise, product-level summaries.

### 10.5 Completed Desktop Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 已完成：3 项素材                                  [导出素材包]        │
├───────────────────────────────────────────┬──────────────────────────┤
│ 素材系列                                  │ 当前素材                 │
│                                           │                          │
│ [主视觉] [小红书封面] [方形商品图]         │ 大图预览                 │
│                                           │                          │
│ 每张卡片：                                │ 候选：1  2  3  4         │
│ - 当前采用                                │ [采用此图]               │
│ - 质量状态                                │ [重新生成]               │
│ - 修改文字                                │ [修改文字]               │
│ - 重新生成                                │                          │
├───────────────────────────────────────────┴──────────────────────────┤
│ [继续生成同风格素材] [保存为品牌风格] [查看生成摘要]                 │
└──────────────────────────────────────────────────────────────────────┘
```

### 10.6 Mobile Layout

Mobile must use one vertical flow:

```text
header
mode selector
composer
upload / brand controls
create button
progress
asset cards
full-screen or bottom-sheet asset detail
sticky contextual action bar
```

Requirements:

```text
no horizontal canvas dependency
tap targets remain accessible
primary action remains visible
candidate comparison supports swipe or thumbnail strip
dialogs become sheets or full-screen panels
metadata remains collapsed by default
```

---

## 11. Frontend Component Specification

### 11.1 `ScenarioHeader`

Responsibilities:

```text
display scenario name and description
show route back to Scenario Hub
show pack status label only when experimental or unavailable
never display provider internals
```

### 11.2 `GeneralModeSelector`

Modes:

```text
auto_commercial_series
single_asset
brand_continuation
template_matched when enabled
```

Behavior:

```text
read available modes from manifest
preserve draft when switching modes where compatible
warn before discarding incompatible fields
make brand selection prominent in continuation mode
do not hard-code future modes
```

### 11.3 `NaturalLanguageInput`

Requirements:

```text
multiline
supports zh-CN and en-US input
preserves original text exactly
shows contextual examples
supports submit by explicit action
does not silently rewrite visible user input
```

Validation:

```text
non-empty after trimming
configurable maximum length
no raw HTML execution
```

### 11.4 `AssetUploader`

Supported logical asset purposes:

```text
product_photo
logo
preferred_style_reference
previous_poster
store_photo
brand_color_reference
other_reference
```

The uploader should let the user optionally label purpose.

The backend remains authoritative.

### 11.5 `BrandPicker`

States:

```text
no brand
temporary brand
persistent brand
missing brand warning
loading
unavailable
```

Display:

```text
brand name
small palette preview when available
visual-tone summary
last-used timestamp when available
```

Do not expose raw BrandProfile JSON in the normal picker.

### 11.6 `OptionalQuickControls`

General Creative first-pass controls:

```text
target platform
aspect ratio
required exact text
content / style to avoid
```

Defaults:

```text
auto
```

Rules:

```text
controls are optional
advanced controls are collapsed by default
values must map to explicit constraints or existing core fields
controls must not inject hidden prompt fragments
```

### 11.7 `JobProgress`

Display:

```text
current user-facing stage
overall estimated progress
asset-level status when available
non-blocking warnings
cancel action when allowed
```

The frontend must not derive completion from percentage alone.

Terminal status comes from the backend.

### 11.8 `AssetSeriesViewer`

Responsibilities:

```text
display assets in SeriesPlan / CommercialAssetPack order
show selected candidate thumbnail
show platform, ratio, and purpose
show ready / warning / failed status
support partial completion
open AssetDetail
```

### 11.9 `CandidateSelector`

Requirements:

```text
show candidates for one asset and one active run
show accepted / warning / failed indicator
show concise evaluation summary
allow explicit selection
preserve previously selected candidates
support viewing candidates from earlier attempts
```

Do not make numeric scores the primary user language.

Recommended labels:

```text
推荐
品牌一致
构图清晰
文字区域需调整
平台适配需优化
```

Raw score details may appear under advanced metadata.

### 11.10 `RegenerateDialog`

Inputs:

```text
scope
adjustment instruction
preservation choices
source candidate when applicable
```

User-facing preservation choices:

```text
保持品牌风格
保持产品主体
保持当前文案
保持当前构图
```

The dialog must not expose provider parameters.

### 11.11 `TextRevisionPanel`

Editable slots:

```text
headline
subtitle
offer
price
cta
footnote
other named slots returned by the backend
```

Behavior:

```text
preview exact text
validate required fields
submit a RenderRevision request
show overflow or rendering warnings
do not regenerate base visual
```

### 11.12 `ContinueStyleDialog`

Inputs:

```text
new request
output mode
target platforms
brand to continue
selected source assets
```

It creates a new job.

### 11.13 `BrandSaveDialog`

Display:

```text
brand name
proposed visual-tone updates
proposed palette updates
new reference assets
rejected-style updates
```

Actions:

```text
save as new brand
apply to existing brand
reject proposal
```

No default auto-apply.

### 11.14 `ExportDialog`

Options:

```text
selected final assets
all selected assets in series
include manifest
include exact text content
include planning summary
image format when conversion is available
```

Do not default to exporting all rejected candidates.

### 11.15 `WarningsPanel`

Warnings should be grouped by:

```text
job
asset
provider
brand continuation
text rendering
export
```

Warnings must be actionable where possible.

### 11.16 `MetadataSummary`

Normal users should see:

```text
business goal
visual direction
platform and ratio
brand used
generation summary
```

Advanced or admin diagnostics may additionally show:

```text
core contract version
scenario pack version
policy checksum
provider names
evaluation versions
trace ids
```

Raw hidden reasoning must never be shown or stored.

---

## 12. General Creative Draft Contract

The frontend may use an internal draft model.

It is not a core schema.

```python
class GeneralCreativeDraft(BaseModel):
    mode_id: str = "auto_commercial_series"
    user_input: str = ""

    optional_brand_id: str | None = None
    optional_template_id: str | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)

    target_platforms: list[str] = Field(default_factory=list)
    aspect_ratio: str | None = None
    exact_text: dict[str, str] = Field(default_factory=dict)
    negative_directions: list[str] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)
```

### 12.1 Draft-to-Request Mapping

The frontend sends the existing `CreateCreativeJobRequest` from document 17.

Recommended mapping:

```text
draft.user_input
→ request.user_input

draft.optional_brand_id
→ request.optional_brand_id

draft.optional_template_id
→ request.optional_template_id

draft.uploaded_asset_ids
→ request.uploaded_asset_ids

draft.mode_id
→ request.scenario_selection.mode_id

draft target platform / ratio / exact text / negative directions
→ request.scenario_selection.parameters
→ request.explicit_constraints where appropriate
```

### 12.2 Requested Output Mapping

```text
auto_commercial_series → commercial_image_series
single_asset          → single_image
brand_continuation    → selected output mode, default commercial_image_series
template_matched      → selected output mode
```

The application service maps this into the existing `CreativeJob.requested_output`.

### 12.3 Constraint Precedence

Required precedence:

```text
1. safety, rights, and hard product constraints
2. explicit UI controls
3. explicit natural-language constraints
4. persistent brand constraints
5. inferred defaults
```

Conflicts must be preserved in metadata.

### 12.4 Input Summary Before Execution

The application service should produce a normalized, user-safe summary:

```text
mode
brand
platforms
ratio
required text
uploaded asset roles
major inferred goal
```

The UI may display it before submission or immediately after job creation.

The summary is not a replacement for the original input.

---

## 13. Job Runtime State Model

### 13.1 Application Job Status

Recommended application-layer enum:

```python
class JobStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PLANNING = "planning"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    REFINING = "refining"
    RENDERING = "rendering"
    PACKAGING = "packaging"

    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"

    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
```

This enum is additive.

It does not replace `Recommendation` or any core generation schema.

### 13.2 Terminal States

Terminal:

```text
completed
partially_completed
failed
cancelled
```

### 13.3 Valid Transitions

```text
created → queued
created → planning
created → cancelled

queued → planning
queued → cancelling
queued → failed

planning → generating
planning → evaluating
planning → packaging
planning → cancelling
planning → failed

generating → evaluating
generating → refining
generating → rendering
generating → packaging
generating → cancelling
generating → failed

evaluating → refining
evaluating → rendering
evaluating → packaging
evaluating → cancelling
evaluating → failed

refining → generating
refining → evaluating
refining → rendering
refining → packaging
refining → cancelling
refining → failed

rendering → packaging
rendering → cancelling
rendering → failed

packaging → completed
packaging → partially_completed
packaging → failed

cancelling → cancelled
cancelling → completed only when execution completed before cancellation took effect
```

Any unlisted transition is invalid.

### 13.4 Planning-Only Runtime

When only planning is available:

```text
created → planning → evaluating or packaging → completed
```

`JobView.runtime_mode` must indicate:

```text
planning_only
```

The UI must not imply that image files were generated.

### 13.5 Asset Status

Recommended asset-level enum:

```text
pending
planning
generating
evaluating
refining
rendering
ready
failed
cancelled
```

### 13.6 Partial Completion Rule

A job is `partially_completed` when:

```text
at least one requested asset is ready
and
at least one requested asset reaches a terminal failed or cancelled state
```

The UI must show successful assets immediately and provide retry actions for failed assets.

### 13.7 User-Facing Progress Stages

Backend stage codes:

```text
understanding_request
building_commercial_brief
loading_brand
building_visual_direction
planning_asset_series
planning_layout
preparing_generation
generating_candidates
reviewing_candidates
improving_candidates
rendering_exact_text
packaging_assets
complete
```

Recommended Chinese copy:

```text
正在理解业务需求
正在整理商业目标
正在读取品牌风格
正在制定视觉方向
正在规划素材系列
正在安排构图与文字
正在准备生成
正在生成候选方案
正在检查商业效果
正在优化较弱结果
正在排版准确文字
正在整理最终素材
已完成
```

### 13.8 Progress Percentage

Progress percentage is advisory.

Rules:

```text
must be monotonic inside one run
must not be used as the terminal source of truth
must include is_estimated = true when provider progress is unavailable
must not jump backward during automatic refinement
may expose asset-level progress separately
```

---

## 14. Job Event Model

### 14.1 Event Contract

```python
class JobEvent(BaseModel):
    event_id: str
    job_id: str
    event_type: str

    status: str | None = None
    stage_code: str | None = None
    progress_percent: float | None = None

    run_id: str | None = None
    asset_id: str | None = None
    attempt_id: str | None = None

    message_key: str | None = None
    message_params: dict = Field(default_factory=dict)

    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    created_at: str
```

### 14.2 Event Types

Recommended:

```text
job_created
job_queued
job_started
stage_changed
asset_started
candidate_batch_created
candidate_evaluated
refinement_started
asset_ready
asset_failed
render_revision_created
selection_changed
memory_update_proposed
memory_update_applied
export_started
export_ready
warning_added
job_completed
job_partially_completed
job_failed
job_cancelled
```

### 14.3 Delivery

Mandatory first-pass delivery:

```text
GET /api/v3/creative-agent/jobs/{job_id}
```

The frontend may poll.

Recommended optional streaming endpoint:

```text
GET /api/v3/creative-agent/jobs/{job_id}/events
```

using Server-Sent Events.

Requirements:

```text
UI must fall back to polling
events are append-only
event ids support resume
event payloads contain no private reasoning
```

WebSocket is not required.

---

## 15. Backend Application Services

### 15.1 `JobApplicationService`

Responsibilities:

```text
validate create-job requests
validate General Creative mode
enforce idempotency
estimate and reserve cost through V3BalanceAdapter when configured
create JobRecord
submit execution
return JobView
load JobView
compute allowed actions
coordinate cancellation
normalize application errors
```

Recommended interface:

```python
class JobApplicationService:
    def create_job(
        self,
        request: CreateCreativeJobRequest,
        idempotency_key: str,
        actor_context: ActorContext,
    ) -> JobView:
        ...

    def get_job(
        self,
        job_id: str,
        actor_context: ActorContext,
    ) -> JobView:
        ...

    def cancel_job(
        self,
        job_id: str,
        expected_version: int | None,
        actor_context: ActorContext,
    ) -> JobView:
        ...
```

### 15.2 `JobExecutor`

Purpose:

```text
decouple API request handling from core execution
```

Interface:

```python
class JobExecutor(Protocol):
    def submit(self, job_id: str) -> None:
        ...

    def execute(self, job_id: str) -> None:
        ...
```

First-pass implementations may include:

```text
SynchronousTestJobExecutor
InProcessJobExecutor
```

A future queue-backed executor may implement the same interface.

The executor must still call:

```text
ScenarioApplicationService
→ ScenarioRuntime
→ Central Creative Brain
```

### 15.3 `CandidateSelectionService`

Responsibilities:

```text
validate candidate belongs to job / run / asset
create immutable CandidateSelection
mark active selection for the asset
create or update proposed MemoryUpdate where allowed
never apply persistent memory automatically
emit event
```

### 15.4 `RegenerationService`

Responsibilities:

```text
validate requested scope
create a new run or attempt record
preserve source lineage
convert user adjustment into auditable constraints
call the existing V3 runtime
preserve old candidates
emit progress events
```

It must not call a generation provider directly.

### 15.5 `ContinuationService`

Responsibilities:

```text
resolve source job
resolve brand and approved source assets
create a new CreateCreativeJobRequest
pin general_creative pack and selected mode
create a new child JobRecord
preserve parent linkage
```

### 15.6 `TextRevisionService`

Responsibilities:

```text
validate editable text slots
sanitize text content
check renderer capability
create immutable RenderRevision
call the V3 renderer path
record overflow / rendering warnings
update active rendered revision
```

It must not overwrite the original candidate file.

### 15.7 `BrandConfirmationService`

Responsibilities:

```text
load proposed MemoryUpdate
show normalized proposal
apply to an existing persistent BrandProfile
or promote a temporary profile to a new persistent BrandProfile
reject proposal
record actor and timestamp
```

### 15.8 `UploadService`

Responsibilities:

```text
validate ownership
validate file type and size
store V3-owned upload metadata
assign logical purpose
return uploaded_asset_id
prevent arbitrary path access
```

### 15.9 `ExportService`

Responsibilities:

```text
validate selected assets
create ExportRecord
package files
include manifest and exact text when requested
return download metadata
handle expired files
```

---

## 16. Application DTOs and View Models

These models are additive API/application contracts.

They must not replace core schemas.

### 16.1 `JobView`

```python
class JobView(BaseModel):
    job_id: str
    status: str
    runtime_mode: str

    scenario_selection: dict
    scenario_runtime: dict

    mode_id: str
    request_summary: dict

    current_stage: dict | None = None
    progress: dict | None = None

    brand: dict | None = None
    runs: list[dict] = Field(default_factory=list)
    assets: list[dict] = Field(default_factory=list)

    memory_update: dict | None = None
    exports: list[dict] = Field(default_factory=list)

    allowed_actions: list[str] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
    error: dict | None = None

    version: int
    created_at: str
    updated_at: str
```

### 16.2 `AssetView`

```python
class AssetView(BaseModel):
    asset_id: str
    asset_type: str
    platform: str
    aspect_ratio: str
    purpose: str

    status: str
    active_run_id: str | None = None
    active_attempt_id: str | None = None

    selected_candidate_id: str | None = None
    active_render_revision_id: str | None = None

    preview_uri: str | None = None
    candidates: list[dict] = Field(default_factory=list)
    render_revisions: list[dict] = Field(default_factory=list)

    evaluation_summary: dict | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
```

### 16.3 `CandidateView`

```python
class CandidateView(BaseModel):
    candidate_id: str
    asset_id: str
    attempt_id: str

    preview_uri: str | None = None
    thumbnail_uri: str | None = None

    selected: bool = False
    recommended: bool = False
    status_label: str | None = None
    evaluation_summary: dict | None = None

    warnings: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

Normal `CandidateView.metadata` must not expose secrets, raw provider credentials, or hidden reasoning.

### 16.4 `ActionAvailability`

```python
class ActionAvailability(BaseModel):
    action_id: str
    allowed: bool
    reason_code: str | None = None
    reason_message: str | None = None
    capability_required: str | None = None
```

A structured list is preferred over a plain string list when the UI must explain disabled actions.

### 16.5 `SelectCandidateRequest`

```python
class SelectCandidateRequest(BaseModel):
    run_id: str
    asset_id: str
    candidate_id: str

    selection_reason: str | None = None
    request_memory_update: bool = True

    metadata: dict = Field(default_factory=dict)
```

`request_memory_update` means:

```text
create or refresh a proposal
```

It does not mean apply automatically.

### 16.6 `RegenerateRequest`

```python
class RegenerateRequest(BaseModel):
    scope: str
    asset_ids: list[str] = Field(default_factory=list)

    instruction: str | None = None
    source_candidate_ids: list[str] = Field(default_factory=list)

    preserve_brand: bool = True
    preserve_product: bool = True
    preserve_copy: bool = True
    preserve_layout: bool = False

    metadata: dict = Field(default_factory=dict)
```

Allowed first-pass scopes:

```text
selected_assets
whole_series
```

### 16.7 `ContinueJobRequest`

```python
class ContinueJobRequest(BaseModel):
    user_input: str
    mode_id: str = "auto_commercial_series"

    optional_brand_id: str | None = None
    source_asset_ids: list[str] = Field(default_factory=list)

    target_platforms: list[str] = Field(default_factory=list)
    aspect_ratio: str | None = None

    metadata: dict = Field(default_factory=dict)
```

### 16.8 `TextContent`

```python
class TextContent(BaseModel):
    headline: str | None = None
    subtitle: str | None = None
    offer: str | None = None
    price: str | None = None
    cta: str | None = None
    footnote: str | None = None

    named_slots: dict[str, str] = Field(default_factory=dict)
```

### 16.9 `CreateRenderRevisionRequest`

```python
class CreateRenderRevisionRequest(BaseModel):
    run_id: str
    asset_id: str
    candidate_id: str

    base_render_revision_id: str | None = None
    text_content: TextContent

    allow_typography_reflow: bool = True
    metadata: dict = Field(default_factory=dict)
```

### 16.10 `ApplyMemoryUpdateRequest`

```python
class ApplyMemoryUpdateRequest(BaseModel):
    memory_update_id: str

    target_brand_id: str | None = None
    create_new_brand: bool = False
    new_brand_name: str | None = None

    accepted_fields: list[str] = Field(default_factory=list)
    rejected_fields: list[str] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)
```

### 16.11 `CreateExportRequest`

```python
class CreateExportRequest(BaseModel):
    asset_ids: list[str] = Field(default_factory=list)

    include_manifest: bool = True
    include_text_content: bool = True
    include_generation_summary: bool = True
    include_unselected_candidates: bool = False

    image_format: str | None = None
    package_format: str = "zip"

    metadata: dict = Field(default_factory=dict)
```

---

## 17. V3 API Routes

All routes remain under:

```text
/api/v3/creative-agent
```

Do not create `/api/general/*`.

### 17.1 Scenario and Manifest Routes

Inherited from document 17:

```text
GET /scenario-packs
GET /scenario-packs/{pack_id}
POST /scenario-packs/{pack_id}/validate-selection
```

### 17.2 Job Routes

```text
POST /jobs
GET  /jobs/{job_id}
GET  /jobs
POST /jobs/{job_id}/cancel
GET  /jobs/{job_id}/events
```

`GET /jobs` supports recent-job and continuation UI.

Recommended filters:

```text
status
scenario_pack
brand_id
parent_job_id
limit
cursor
```

### 17.3 Candidate Selection

```text
POST /jobs/{job_id}/select
```

### 17.4 Regeneration

```text
POST /jobs/{job_id}/regenerate
```

The request identifies asset scope.

Do not create provider-specific regenerate routes.

### 17.5 Style Continuation

```text
POST /jobs/{job_id}/continue
```

Returns a new JobView with a new `job_id`.

### 17.6 Text Revision

```text
POST /jobs/{job_id}/assets/{asset_id}/render-revisions
GET  /jobs/{job_id}/assets/{asset_id}/render-revisions
```

### 17.7 Brand Routes

```text
GET  /brands
POST /brands
GET  /brands/{brand_id}
POST /jobs/{job_id}/brand-memory/apply
POST /jobs/{job_id}/brand-memory/reject
```

These routes use V3 brand-memory services only.

### 17.8 Upload Routes

First-pass simple route:

```text
POST /assets/uploads
GET  /assets/uploads/{uploaded_asset_id}
DELETE /assets/uploads/{uploaded_asset_id}
```

A future direct-to-object-store upload protocol may be added behind the same UploadService.

### 17.9 Export Routes

```text
POST /jobs/{job_id}/exports
GET  /jobs/{job_id}/exports
GET  /exports/{export_id}
```

### 17.10 HTTP Semantics

Recommended:

```text
POST /jobs                         → 202 Accepted
POST regenerate / continue         → 202 Accepted
POST render revision               → 202 Accepted or 200 if synchronous
POST export                        → 202 Accepted or 200 if immediate
GET job / export                   → 200
invalid request                    → 400
not authenticated                  → 401
not authorized                     → 403
not found                          → 404
version or state conflict          → 409
unsupported capability             → 422
insufficient balance               → 402 or project-standard business error
provider temporarily unavailable   → 503 when no fallback exists
```

Use the host platform's established error envelope if one exists.

The V3 error codes in this document remain required.

---

## 18. Create-Job Contract

### 18.1 Request

Use the request envelope from document 17.

Example:

```json
{
  "user_input": "帮我做一组夏季新品推广视觉，清爽、高级，适合小红书和朋友圈。",
  "optional_brand_id": "brand_123",
  "optional_template_id": null,
  "uploaded_asset_ids": [
    "upload_product_front",
    "upload_logo"
  ],
  "explicit_constraints": [
    "必须保留产品包装外观",
    "标题必须出现：夏日新品"
  ],
  "scenario_selection": {
    "pack_id": "general_creative",
    "mode_id": "auto_commercial_series",
    "source": "explicit_ui",
    "parameters": {
      "target_platforms": [
        "xiaohongshu",
        "wechat_moments"
      ],
      "aspect_ratio": "auto",
      "exact_text": {
        "headline": "夏日新品",
        "cta": "立即尝鲜"
      },
      "negative_directions": [
        "avoid_clutter",
        "avoid_cheap_look"
      ]
    },
    "allow_general_fallback": false
  },
  "metadata": {
    "client": "v3_web",
    "draft_version": "1"
  }
}
```

### 18.2 Response

```json
{
  "job_id": "job_01H...",
  "status": "created",
  "runtime_mode": "generation",
  "mode_id": "auto_commercial_series",
  "current_stage": {
    "code": "understanding_request",
    "label": "正在理解业务需求"
  },
  "progress": {
    "percent": 0,
    "is_estimated": true
  },
  "scenario_selection": {
    "pack_id": "general_creative",
    "mode_id": "auto_commercial_series",
    "source": "explicit_ui"
  },
  "scenario_runtime": {
    "pack_id": "general_creative",
    "pack_version": "1.0.0",
    "bound_vertical_pack": "DefaultCommercialPack",
    "policy_checksum": "sha256:..."
  },
  "allowed_actions": [
    "cancel"
  ],
  "warnings": [],
  "version": 1,
  "created_at": "2026-06-22T00:00:00Z",
  "updated_at": "2026-06-22T00:00:00Z"
}
```

---

## 19. Job View and Result Contract

### 19.1 Completed Job Example

```json
{
  "job_id": "job_01H...",
  "status": "completed",
  "runtime_mode": "generation",
  "mode_id": "auto_commercial_series",
  "request_summary": {
    "business_goal": "新品推广",
    "platforms": [
      "xiaohongshu",
      "wechat_moments"
    ],
    "brand_name": "茶小满",
    "asset_count": 2
  },
  "current_stage": {
    "code": "complete",
    "label": "已完成"
  },
  "progress": {
    "percent": 100,
    "is_estimated": false
  },
  "assets": [
    {
      "asset_id": "asset_xhs_cover",
      "asset_type": "social_cover",
      "platform": "xiaohongshu",
      "aspect_ratio": "4:5",
      "purpose": "新品推广封面",
      "status": "ready",
      "selected_candidate_id": "candidate_003",
      "active_render_revision_id": "render_002",
      "preview_uri": "/signed/asset_xhs_cover.png",
      "candidates": [
        {
          "candidate_id": "candidate_003",
          "selected": true,
          "recommended": true,
          "status_label": "推荐",
          "thumbnail_uri": "/signed/thumb_candidate_003.png"
        }
      ],
      "allowed_actions": [
        "select_candidate",
        "regenerate_asset",
        "edit_text",
        "export"
      ],
      "warnings": []
    }
  ],
  "memory_update": {
    "memory_update_id": "memory_update_001",
    "status": "proposed",
    "summary": {
      "new_reference_assets": 2,
      "new_style_tags": [
        "fresh",
        "clean",
        "premium"
      ]
    }
  },
  "allowed_actions": [
    "regenerate_series",
    "continue_style",
    "apply_brand_memory",
    "export"
  ],
  "warnings": [],
  "version": 12
}
```

### 19.2 Response Size

Default JobView should return:

```text
user-safe summaries
active run
active selections
thumbnail references
current warnings
```

Large core snapshots, all historical attempts, and debug traces should use:

```text
explicit include parameters
or dedicated admin / diagnostic endpoints
```

This avoids overloading the normal UI.

---

## 20. Candidate Selection Semantics

### 20.1 Selection Is Per Asset

A series job may select one candidate for each asset.

Selecting a candidate must:

```text
validate ownership
validate asset and candidate lineage
create CandidateSelection
update active selected candidate pointer
emit selection_changed
refresh proposed MemoryUpdate when allowed
increment JobRecord version
```

### 20.2 Selection Does Not Delete Other Candidates

Rejected or unselected candidates remain in history.

They may be hidden by default but must remain auditable.

### 20.3 Automatic Recommendation vs User Selection

The V3 runtime may recommend or package the highest-ranked candidate.

The UI must distinguish:

```text
system recommended
user selected
```

A user selection overrides the active presentation but does not rewrite the original EvaluationReport.

### 20.4 Memory Interaction

Selection may create a proposed MemoryUpdate only when:

```text
candidate is valid
candidate is not a failed mock
brand-memory policy allows proposal
```

Persistent application remains a separate action.

---

## 21. Regeneration Semantics

### 21.1 Regeneration Must Preserve Lineage

Every regeneration must record:

```text
source_job_id
source_run_id
source_asset_ids
source_candidate_ids
user instruction
preservation choices
new run or attempt id
scenario pack and module versions
core contract version
```

### 21.2 First-Pass Scopes

#### `selected_assets`

Regenerate one or more assets.

The service may reuse:

```text
CommercialBrief
BrandProfile
CreativePlan
SeriesPlan
unaffected AssetSpecs
```

It must still execute through supported Central Creative Brain entrypoints.

If the current runtime has no safe partial entrypoint, it may execute a new full run with explicit locked context and only package requested assets.

It must not call the GenerationProvider directly.

#### `whole_series`

Create a new run for the complete series.

Use when the user changes:

```text
overall visual direction
commercial goal
campaign concept
brand direction
series composition
```

### 21.3 Preservation Choices

Default:

```text
preserve_brand = true
preserve_product = true
preserve_copy = true
preserve_layout = false
```

These choices become auditable constraints.

They are not provider-specific flags.

### 21.4 Previous Results Remain Available

After regeneration:

```text
new run becomes active when valid
old runs remain viewable
old user selections remain recorded
user may restore an earlier selected candidate
```

### 21.5 Regeneration Cost

Before execution:

```text
estimate cost
reserve credits through V3BalanceAdapter when configured
commit on successful provider use
refund or release according to provider failure policy
```

The UI should display a human-readable cost estimate when the platform supports it.

---

## 22. Style Continuation Semantics

### 22.1 Continue Creates a New Job

Correct:

```text
source job
→ POST /jobs/{job_id}/continue
→ new JobRecord
→ parent_job_id points to source
```

Incorrect:

```text
overwrite the old job with a new request
```

### 22.2 Continuation Source Priority

Recommended:

```text
1. explicitly selected persistent brand
2. source job persistent brand
3. accepted source assets converted to explicit reference assets
4. source job temporary profile with warning
5. new temporary profile with warning
```

### 22.3 Source Asset Rules

Only use assets that are:

```text
user selected
system accepted and not rejected
owned or accessible by the same user
valid reference types
```

Do not automatically use every candidate.

### 22.4 Continuation UI Summary

Before creating the child job, show:

```text
brand being continued
reference assets being reused
new request
new output mode
target platforms
```

### 22.5 Missing Brand Behavior

The UI should encourage a valid brand selection.

The backend must follow the existing brand-memory fallback contract:

```text
temporary profile
structured warning
no false claim of persistent style continuity
```

---

## 23. Brand-Memory Confirmation Flow

### 23.1 Proposal Creation

A proposal may be created after:

```text
user selects a candidate
candidate passes acceptance policy
user explicitly asks to keep the style
```

### 23.2 Proposal Contents

The UI-safe proposal should summarize:

```text
new successful asset ids
new reference assets
new style tags
new rejected style tags
platform-history updates
copywriting-tone updates
layout-preference updates
```

### 23.3 Apply Choices

The user may:

```text
apply all allowed fields
apply selected fields
save as a new brand
apply to an existing brand
reject the proposal
```

### 23.4 Concurrency

Applying to an existing BrandProfile should use:

```text
brand version
optimistic concurrency
conflict response when the profile changed
```

Do not silently overwrite newer brand memory.

### 23.5 Temporary Brand Promotion

When promoting a temporary profile:

```text
create new persistent brand_id
copy approved fields only
attach accepted reference assets
record source job and MemoryUpdate
set is_temporary = false
```

---

## 24. Text Revision and External Rendering

### 24.1 Capability Gate

`edit_text` is available only when:

```text
a selected base visual exists
a LayoutPlan exists
a supported RendererProvider is available
the asset type permits external text rendering
```

### 24.2 No Base-Visual Mutation

Each revision must preserve:

```text
base candidate id
base visual file
source LayoutPlan id
exact TextContent
renderer name and version
render warnings
output file
```

### 24.3 Typography Reflow

When `allow_typography_reflow = true`, the renderer may adjust:

```text
font size within configured limits
line breaks
tracking
slot alignment
safe padding
```

It must preserve:

```text
text hierarchy
exact text content
brand typography constraints
reserved visual regions
```

### 24.4 Overflow

If exact text cannot fit safely:

```text
do not silently truncate
return text_overflow warning
keep the previous active revision
offer a layout-adjustment action
```

A future layout revision may re-enter the existing LayoutAgent path.

### 24.5 Text Sanitization

Required:

```text
escape HTML
reject executable markup
normalize unsupported control characters
preserve intended Chinese punctuation
validate price and required text as strings
```

### 24.6 Revision History

The user may view and restore earlier render revisions.

Restoring creates an active pointer change, not destructive deletion.

---

## 25. Export Behavior

### 25.1 Default Export

Default package:

```text
selected final asset for each ready asset
exact text content
asset manifest
platform
aspect ratio
purpose
brand consistency summary
generation summary
```

### 25.2 Optional Contents

Optional:

```text
planning summary
evaluation summary
unselected candidates
render revision history
brand-memory proposal
```

Unselected candidates must be off by default.

### 25.3 File Naming

Recommended deterministic pattern:

```text
{safe_brand_or_job_name}_{asset_type}_{platform}_{aspect_ratio}_{revision}.{ext}
```

File names must be sanitized.

### 25.4 Export Manifest

Recommended manifest fields:

```text
export_id
job_id
source_run_ids
asset entries
selected candidate ids
render revision ids
platforms
aspect ratios
exact text
brand id
scenario pack and version
core contract version
created_at
warnings
```

### 25.5 Expiration

If download URLs expire:

```text
ExportRecord remains
download URL may be renewed
historical export metadata remains auditable
```

---

## 26. Action Availability Rules

### 26.1 Job-Level Actions

`cancel` allowed when:

```text
status is non-terminal
executor supports cancellation or best-effort cancellation
```

`regenerate_series` allowed when:

```text
job has at least one completed run
generation capability is available
job is not currently mutating
```

`continue_style` allowed when:

```text
job has a usable BrandProfile or accepted reference asset
```

It may remain allowed with warning if only temporary context exists.

`apply_brand_memory` allowed when:

```text
MemoryUpdate.status = proposed
user has write access to target brand
```

`export` allowed when:

```text
at least one asset is ready
```

### 26.2 Asset-Level Actions

`select_candidate` allowed when:

```text
candidate is valid
candidate belongs to asset
candidate is not a hard failure
```

`regenerate_asset` allowed when:

```text
asset exists
generation capability is available
job is not in a conflicting mutation
```

`edit_text` allowed when:

```text
renderer capability exists
selected candidate exists
layout supports text rendering
```

### 26.3 Backend Reason Codes

Recommended:

```text
job_not_terminal
job_busy
no_ready_assets
no_selected_candidate
candidate_invalid
renderer_unavailable
generation_unavailable
brand_memory_unavailable
memory_update_not_proposed
insufficient_permission
insufficient_balance
pack_unavailable
historical_version_unavailable
```

---

## 27. Failure, Partial Success, and Recovery

### 27.1 Error Shape

```python
class ProductError(BaseModel):
    code: str
    message: str
    retryable: bool = False

    job_id: str | None = None
    asset_id: str | None = None
    action_id: str | None = None

    details: dict = Field(default_factory=dict)
    trace_id: str | None = None
```

### 27.2 Required Error Codes

```text
invalid_request
invalid_mode
scenario_unavailable
scenario_version_conflict
job_not_found
job_not_actionable
job_version_conflict
candidate_not_found
candidate_invalid
brand_not_found
brand_version_conflict
memory_update_not_found
upload_invalid
upload_not_found
upload_not_owned
insufficient_balance
provider_failure
all_providers_failed
renderer_unavailable
render_failure
text_overflow
export_failure
idempotency_conflict
cancellation_not_supported
permission_denied
```

### 27.3 Provider Failure

If one provider fails:

```text
use existing provider fallback policy
record structured warning
continue unaffected assets
```

If all providers fail for one asset:

```text
mark asset failed
continue other assets
```

If all requested assets fail:

```text
mark job failed
```

### 27.4 Partial Completion UI

The UI must:

```text
show ready assets
show failed asset reason
allow retry for failed assets
allow export of successful assets
avoid presenting the whole job as lost
```

### 27.5 Retry Rules

Automatic retry belongs to the existing refinement/provider policy.

User-triggered retry belongs to RegenerationService.

Do not mix them silently.

### 27.6 Application Recovery

If the API process restarts:

```text
JobRecord remains readable
non-terminal jobs are reconciled by JobExecutor
duplicate execution is prevented by run status and idempotency
historical scenario versions remain pinned
```

---

## 28. Idempotency, Concurrency, and Versioning

### 28.1 Idempotency

Require or strongly recommend `Idempotency-Key` for:

```text
POST /jobs
POST /jobs/{job_id}/select
POST /jobs/{job_id}/regenerate
POST /jobs/{job_id}/continue
POST render revisions
POST brand-memory apply
POST exports
POST cancel
```

Same key and same payload:

```text
return the original result
```

Same key and different payload:

```text
idempotency_conflict
```

### 28.2 Optimistic Concurrency

JobView includes:

```text
version
```

Mutations should support:

```text
If-Match
or expected_version in the project-standard request envelope
```

Stale mutations return:

```text
409 job_version_conflict
```

### 28.3 Scenario Version Pinning

Every run must preserve:

```text
pack_id
pack_version
mode_id
module versions
policy checksum
core contract version
rules version
provider versions
```

### 28.4 Historical Readability

If a pack version is removed:

```text
historical records remain viewable
existing output files remain downloadable when retained
historical job must not be silently reinterpreted using a newer pack
new regeneration may require explicit migration or current-version run
```

General Creative should be especially stable because it is the baseline pack.

---

## 29. Persistence Boundary

### 29.1 Repository Interfaces

Recommended:

```text
JobRepository
JobEventRepository
UploadRepository
ExportRepository
IdempotencyRepository
```

The application layer depends on interfaces, not database details.

### 29.2 First-Pass Storage

For offline development and tests:

```text
in-memory repository
or V3-owned local JSON / SQLite implementation
```

For concurrent production use:

```text
transaction-capable persistent storage
```

The storage implementation must remain inside the V3 boundary.

### 29.3 Stored Data

Store:

```text
original request
normalized request mapping
CreativeJob reference or snapshot
scenario selection
scenario version pins
status and version
run lineage
asset lineage
candidate ids and file references
user selections
render revisions
MemoryUpdate status
export records
warnings and errors
events
timestamps
```

Do not store:

```text
provider secrets
raw authentication tokens
private chain-of-thought
unbounded raw model logs
```

### 29.4 Core Snapshot Strategy

At minimum, persist stable references or snapshots for:

```text
CommercialBrief
BrandProfile used
CreativePlan
SeriesPlan
LayoutPlans
PromptCompilationResults
ConditionPlans
GenerationPlans
EvaluationReports
CommercialAssetPack
```

This supports audit and historical rendering.

---

## 30. Balance and Cost Boundary

### 30.1 V3BalanceAdapter Only

General Creative application services must use:

```text
V3BalanceAdapter
```

They must not call the host product's balance internals directly.

### 30.2 Cost Lifecycle

Recommended:

```text
estimate
→ show estimate when available
→ reserve
→ execute
→ commit actual cost
→ release or refund unused reservation
```

### 30.3 Partial Failure

When only some assets fail:

```text
charge only according to actual provider-use policy
record per-run or per-asset cost summary
make refund behavior auditable
```

### 30.4 Free Actions

Candidate selection and metadata-only actions should not consume generation credits.

Text re-rendering may have a separate renderer cost policy.

---

## 31. Upload, Security, and Rights Requirements

### 31.1 Ownership

Every uploaded asset must be associated with:

```text
user or account
upload id
logical purpose
storage reference
created time
status
```

### 31.2 Validation

Configurable validation should cover:

```text
allowed MIME types
allowed extensions
maximum size
image decoding
malware or content scan when available
pixel dimensions
corrupt-file rejection
```

### 31.3 Path and URL Safety

Do not:

```text
trust client file paths
allow arbitrary local-path reads
allow unrestricted server-side URL fetches
expose permanent storage paths
```

Use controlled storage references or signed URLs.

### 31.4 Renderer Safety

Exact text and metadata must be escaped before HTML/SVG rendering.

Scenario manifests cannot inject executable frontend content.

### 31.5 User Rights

The product should require the user to have rights to uploaded:

```text
logos
product photos
people
characters
brand materials
reference images
```

Detailed rights enforcement may be implemented through future policy modules, but the upload flow must preserve ownership and source metadata.

---

## 32. Observability and Audit

### 32.1 Required Correlation IDs

```text
request_id
trace_id
job_id
run_id
asset_id
attempt_id
candidate_id
render_revision_id
export_id
```

### 32.2 Required Product Metadata

```text
mode id
scenario pack and version
bound vertical pack
policy checksum
core contract version
rules version
provider versions
status transitions
action actor
idempotency key hash or reference
cost summary when available
```

### 32.3 User-Safe Reasoning Summary

Allowed:

```text
selected a clean product-centered direction because the request prioritizes clarity
created a 4:5 social cover because Xiaohongshu was selected
reserved the upper text region because exact Chinese text is required
```

Forbidden:

```text
private chain-of-thought
hidden system prompts
secret provider payloads
credentials
```

### 32.4 Metrics

Recommended:

```text
job creation success rate
time to first asset
time to completion
partial completion rate
provider failure rate
automatic refinement count
user selection rate
regeneration rate
text revision rate
brand-memory apply rate
export rate
```

Metrics must not change creative behavior by themselves.

---

## 33. Responsive, Accessibility, and Localization Requirements

### 33.1 Responsive

The full flow must work on:

```text
desktop
tablet
mobile
```

Mobile is a first-class target because the intended users may operate only by phone.

### 33.2 Accessibility

Required:

```text
keyboard navigation
visible focus states
semantic buttons and labels
screen-reader descriptions
sufficient text contrast
non-color-only status indicators
alternative text for generated previews when available
accessible dialogs and sheets
```

### 33.3 Localization

The manifest and UI should support:

```text
zh-CN
en-US
```

First-pass default:

```text
zh-CN
```

Backend events should use stable `message_key` values.

The frontend localizes display copy.

Do not store localized UI sentences as the only machine-readable status.

---

## 34. Performance Requirements

### 34.1 Result Loading

Use:

```text
thumbnail-first loading
lazy full-resolution loading
pagination or collapsed history for many candidates
signed or controlled asset URLs
```

### 34.2 Polling

When SSE is unavailable:

```text
poll faster during active stages
poll slower after completion
stop polling at terminal state
use ETag or version to avoid unnecessary payloads when available
```

### 34.3 Large Histories

Do not return every historical candidate and event in the default JobView.

Use:

```text
active attempt by default
explicit history expansion
cursor pagination
```

### 34.4 Draft Persistence

The frontend may persist an unsent draft locally.

It must not persist sensitive uploads or permanent access URLs in insecure browser storage.

---

## 35. General Creative UI State Model

### 35.1 Client States

Recommended:

```text
loading_manifest
manifest_unavailable
empty
editing_draft
uploading_assets
validating
submitting
job_active
job_partial
job_completed
job_failed
action_pending
```

### 35.2 Empty State

Show:

```text
mode selector
composer
example requests
recent jobs
brand continuation shortcut
```

### 35.3 Manifest Unavailable

If General Creative manifest validation fails:

```text
show product unavailable state
do not silently route to another scenario
log a startup or runtime error
```

document 17 requires General Creative to be mandatory.

### 35.4 Action Pending

Only the affected action should be disabled where possible.

Examples:

```text
selecting candidate does not block viewing other assets
exporting does not block text review
asset regeneration should not hide existing output
```

### 35.5 Stale View

When a mutation returns version conflict:

```text
refresh JobView
preserve unsent dialog input
explain that the job changed
allow user to retry
```

### 35.6 Beginner-First General Workspace

The General Creative workspace is the only complete scenario workspace in the
current stage.

Default visible layout:

```text
top:
  one natural-language composer
  optional brand selector
  optional reference upload entry

middle:
  beginner quick-start cards
  no provider/model controls

bottom:
  job progress
  candidate/result board
  recent images and recent jobs
```

The default UI must be understandable to a non-technical user.

Visible beginner actions:

```text
Generate commercial image
Generate a small series
Continue a brand style
Use a reference image
Change text or price
Plan it for me
Export selected results
```

Advanced options may exist, but they must be collapsed by default and must not
use these words in beginner mode:

```text
provider
adapter
sampler
node graph
IP-Adapter
ControlNet
ComfyUI
seed
CFG
```

### 35.7 General Quick-Start Cards

The General workspace should expose quick-start cards that configure the same
GeneralCreativeScenarioPack, not separate pack logic.

Required quick-start cards:

```text
single_commercial_image        一张商业图
commercial_image_series       一组营销图
festival_campaign             节日活动图
poster_or_cover               海报 / 封面 / 宣传图
brand_style_continuation      延续品牌风格
reference_image_recreation    参考图再创作
text_or_price_revision        改文字 / 改价格
auto_planning                 不知道怎么做，帮我规划
```

Each card opens a lightweight panel with:

```text
plain-language explanation
example input
optional reference upload
optional brand selector
generation count when relevant
primary submit button
```

The panel must not introduce specialized e-commerce, new-media, community, or
brand-IP workflows. If a user's wording resembles those domains, General
Creative should still process it through the general intent classifier.

### 35.8 General Agent Intent Logic

General Creative must route user input through a simple intent-understanding
layer before creating the V3 job.

Supported General intent categories:

```text
single_image
image_series
brand_continuation
reference_image_recreation
text_revision
campaign_or_event
ambiguous_request
```

Rules:

```text
1. User input is always accepted as natural language first.
2. If intent is ambiguous, expand it into a concise CommercialBrief before generation.
3. The agent may ask the runtime to infer missing platform, purpose, mood, and asset count.
4. The agent must preserve explicit user constraints.
5. The agent may use brand memory, layout planning, prompt compilation, generation routing, evaluation, and asset packaging.
6. The agent must not call e-commerce, new-media, private-community, brand-IP, or AI-manga specialized agents in this stage.
7. Domain-like user requests are handled as normal General Creative briefs until a future specialized pack is accepted.
```

Implementation mapping:

```text
NaturalLanguageInput
  -> GeneralIntentInterpreter
  -> optional brief expansion for ambiguous_request
  -> CreativeJob draft
  -> ScenarioRuntime
  -> GeneralCreativeScenarioPack
  -> DefaultCommercialPack
  -> existing Central Creative Brain
```

The General intent interpreter may classify domain language, but only to produce
a better general CommercialBrief. It must not dispatch to future ecommerce,
new-media, community, brand-IP, or AI-manga agent code.

Allowed V3 core collaborators:

```text
CommercialBrief construction
BrandProfile / brand memory read and confirmation proposal
CreativePlan
SeriesPlan
LayoutPlan
PromptCompilationResult
ConditionPlan
GenerationPlan
EvaluationReport
CommercialAssetPack manifest
```

Forbidden current-stage collaborators:

```text
EcommerceAgentFamily
NewMediaMarketingAgentFamily
PrivateCommunityAgentFamily
BrandIPAgentFamily
AIMangaDramaAgentFamily
pack-specific provider router
pack-specific generation endpoint
pack-specific scoring policy
```

Examples:

```text
Input: 做一张火锅店冬季套餐推广图
Intent: single_image or campaign_or_event
Route: GeneralCreativeScenarioPack -> DefaultCommercialPack

Input: 帮我做一组适合小红书和朋友圈的新品图
Intent: image_series
Route: GeneralCreativeScenarioPack -> DefaultCommercialPack

Input: 我也不知道怎么做，帮我想一个好看的活动图
Intent: ambiguous_request
Route: expand brief first, then GeneralCreativeScenarioPack
```

### 35.9 Placeholder Boundary With Other Scenario Cards

The V3 home may show e-commerce, new-media, private-community, and brand-IP
cards, but this General document does not implement those modules.

Required placeholder behavior:

```text
show card name
show one-sentence description
show "coming later" or equivalent state
offer "Use General Creative instead" action
do not create jobs
do not open pack-specific forms
do not call pack-specific APIs
do not call pack-specific agents
```

---

## 36. Capability-Gated UI

Backend should return a capability summary.

Example:

```json
{
  "capabilities": {
    "planning": true,
    "generation": true,
    "candidate_selection": true,
    "regeneration": true,
    "brand_memory_read": true,
    "brand_memory_write": true,
    "text_rendering": true,
    "export": true,
    "event_stream": false
  }
}
```

UI behavior:

| Capability | UI behavior |
|---|---|
| planning only | show plans and manifest, no image claim |
| generation unavailable | disable create or run planning-only according to configuration |
| candidate selection unavailable | show packaged result only |
| regeneration unavailable | hide or disable regenerate |
| brand memory unavailable | hide persistent brand actions; temporary profile warning |
| text rendering unavailable | hide text revision; preserve exact text in output metadata |
| export unavailable | allow individual file download when possible |
| event stream unavailable | poll JobView |

A missing optional capability must not break the page.

---

## 37. Testing Strategy

### 37.1 Core Regression Gate

The first gate is:

```text
General Creative through ScenarioRuntime
produces equivalent core output to the previous DefaultCommercialPack path
for the same fixture
```

Compare:

```text
CreativeJob
CommercialBrief
BrandProfile
CreativePlan
SeriesPlan
LayoutPlans
PromptCompilationResults
ConditionPlans
GenerationPlans
EvaluationReports
CommercialAssetPack
```

Ignore only approved application/scenario metadata differences.

### 37.2 Mode Mapping Tests

Required:

```text
auto series maps to commercial_image_series
single asset maps to single_image
brand continuation maps optional_brand_id correctly
template mode remains hidden without capability
explicit UI mode wins over inferred mode
mode conflict is recorded
```

### 37.3 Job State Machine Tests

Required:

```text
all valid transitions succeed
invalid transitions fail
terminal states cannot restart implicitly
partial completion rule works
planning-only completion works
cancellation transitions work
```

### 37.4 Idempotency Tests

Required for every mutation route.

### 37.5 Candidate Selection Tests

Required:

```text
candidate lineage validated
selection is per asset
old candidates remain
user selection differs from system recommendation
selection may propose MemoryUpdate
selection never auto-applies persistent memory
```

### 37.6 Regeneration Tests

Required:

```text
new attempt or run created
old run remains immutable
source lineage preserved
preservation choices recorded
service calls ScenarioRuntime, not provider directly
partial asset regeneration works
```

### 37.7 Continuation Tests

Required:

```text
new child job created
parent job unchanged
persistent brand preferred
accepted reference assets reused
missing brand falls back with warning
```

### 37.8 Text Revision Tests

Required:

```text
exact Chinese text preserved
HTML/SVG is escaped
base candidate remains unchanged
new RenderRevision created
overflow does not truncate silently
previous revision can be restored
renderer unavailable disables action
```

### 37.9 Brand Confirmation Tests

Required:

```text
proposal visible
apply selected fields only
temporary profile promotion works
brand version conflict detected
rejected proposal remains unapplied
```

### 37.10 Export Tests

Required:

```text
selected assets exported by default
manifest contains required lineage
unselected candidates excluded by default
file names sanitized
expired download can be renewed
partial job can export successful assets
```

### 37.11 UI Contract Tests

Required:

```text
manifest drives modes
General card opens shared workspace
advanced controls collapsed by default
provider knobs absent
mobile layout contract exists
disabled actions include reason
partial completion displays successful assets
```

### 37.12 Security Tests

Required:

```text
upload type validation
upload ownership
path traversal prevention
text escaping
scenario manifest cannot inject executable code
cross-user job access denied
```

### 37.13 Offline Tests

Application service, state machine, manifest, and view tests must run without:

```text
GPU
external generation provider
external object storage
external event bus
V1/V2 runtime
```

Use mock repositories and existing Noop/Mock providers.

---

## 38. End-to-End Acceptance Cases

### 38.1 Auto Series Without Existing Brand

Input:

```text
帮我做一组咖啡店夏季新品宣传图，清爽、干净，适合小红书和朋友圈。
```

Expected:

```text
General Creative auto mode
temporary BrandProfile
existing core planning chain
multiple AssetSpecs
candidate loop when available
partial or complete asset series
proposed memory update only
```

### 38.2 Single Image

Input:

```text
帮我做一张美甲店开业优惠图，适合朋友圈。
```

UI mode:

```text
single_asset
```

Expected:

```text
one AssetSpec
same evaluation and rendering path
one selected packaged asset
```

### 38.3 Brand Continuation

Source:

```text
persistent brand_123
```

Input:

```text
沿用这个品牌的清爽风格，做端午节活动系列。
```

Expected:

```text
BrandProfile loaded
continuation metadata present
new child job if started from previous result
same brand constraints influence existing core plans
```

### 38.4 Candidate Selection and Brand Save

Expected:

```text
user selects one candidate per asset
MemoryUpdate proposed
user confirms selected fields
persistent BrandProfile updated
audit record created
```

### 38.5 Text-Only Price Change

Expected:

```text
user changes price and CTA
base visual unchanged
new RenderRevision
exact text preserved
no image-generation charge
```

### 38.6 Partial Failure

Expected:

```text
two assets ready
one asset provider failure
job partially_completed
ready assets exportable
failed asset regeneratable
```

### 38.7 Whole-Series Adjustment

Instruction:

```text
整体更年轻一点，但保持品牌配色和产品包装。
```

Expected:

```text
new RunRecord
brand and product preservation constraints
old run remains available
new run executes through Central Creative Brain
```

---

## 39. Implementation Phases

### G0. Baseline Verification

Before new code:

```text
run existing V3 tests
run document 17 scenario-platform tests
capture General Creative golden fixtures
verify DefaultCommercialPack path
verify capability list
```

Deliverable:

```text
General Creative baseline report
```

Gate:

```text
no unresolved core regression
```

### G1. Application Contracts and State Machine

Implement:

```text
JobRecord
RunRecord
AssetRunRecord
GenerationAttemptRecord
CandidateSelection
RenderRevision
ExportRecord
JobStatus
JobEvent
repositories
state machine
action availability policy
```

Tests:

```text
serialization
state transitions
partial completion
idempotency
version conflicts
```

### G2. Create, Execute, Read, and Observe Jobs

Implement:

```text
JobApplicationService
JobExecutor
POST /jobs
GET /jobs/{job_id}
GET /jobs
POST cancel
polling
optional SSE
```

Connect:

```text
ScenarioApplicationService
→ GeneralCreativeScenarioPack
→ DefaultCommercialPack
→ Central Creative Brain
```

Gate:

```text
auto series and single asset complete through one runtime
```

### G3. General Creative Workspace

Implement:

```text
shared V3 home entry compatibility
Scenario Hub handoff
General route
manifest loading
mode selector
composer
brand picker
asset uploader
quick controls
progress
asset-series viewer
partial-failure UI
mobile layout
```

Gate:

```text
a non-design user can create and view a job without provider controls
e-commerce, new-media, private-community, and brand-IP cards remain placeholders
placeholder cards cannot create jobs
```

### G4. Candidate and Regeneration Actions

Implement:

```text
candidate detail
candidate selection
selection history
asset regeneration
whole-series regeneration
old-run history
action availability
```

Gate:

```text
all mutations are immutable, idempotent, and version-safe
```

### G5. Continuation, Brand Confirmation, Text Revision, and Export

Implement:

```text
continue style
recent jobs
brand-memory proposal UI
apply / reject memory update
temporary brand promotion
text revision
render history
export package
```

Capability-gate unavailable features.

### G6. Hardening

Implement:

```text
security review
accessibility
localization
performance
recovery
metrics
load tests
provider-failure tests
mobile regression
documentation index update
```

### Sequential Rule

Do not start specialized e-commerce UI or action APIs before:

```text
G2 shared job runtime is accepted
G3 shared workspace is accepted
G4 shared candidate actions are stable
```

For the current stage, specialized packs remain placeholders even after these
shared gates pass. Specialized packs may begin strategy design in parallel, but
production implementation requires separate accepted pack-specific documents and
must reuse these frozen contracts.

---

## 40. Definition of Done

General Creative is complete when:

```text
1. The General Creative card is registry-driven and active.
2. It opens the shared V3 ScenarioWorkspace.
3. Auto series, single image, and brand continuation modes work.
4. GeneralCreativeScenarioPack remains bound to DefaultCommercialPack.
5. No General-only creative pipeline exists.
6. Natural-language input remains the primary interaction.
7. Brand and reference assets are optional and validated.
8. Job creation is idempotent.
9. Job status and progress are backend-driven.
10. Planning-only and generation runtimes are represented honestly.
11. Asset-level partial completion works.
12. Candidate selection is per asset and auditable.
13. Regeneration preserves prior runs and executes through the V3 runtime.
14. Style continuation creates a new child job.
15. Persistent brand updates require explicit confirmation.
16. Text-only revision uses the renderer and preserves the base visual.
17. Export produces selected assets and a lineage manifest.
18. Backend computes allowed actions and disabled reasons.
19. Mobile, accessibility, and localization requirements are covered.
20. General Creative core outputs pass regression against DefaultCommercialPack.
21. No V1/V2 runtime dependency is introduced.
22. Future scenario packs can reuse the same job, action, rendering, brand, and export services.
23. Other first-screen scenario cards are placeholders only.
24. No e-commerce, new-media, private-community, brand-IP, or AI-manga specialized workflow is implemented by this document.
25. Placeholder cards offer a "use General Creative instead" path.
```

---

## 41. Reuse Contract for Future Specialization Packs

The following product infrastructure is shared and must not be rebuilt by e-commerce, new media, private community, AI manga-drama, or brand-IP packs:

```text
JobRecord and state machine
JobApplicationService
JobExecutor
job event model
upload service
brand picker and brand-confirmation flow
candidate viewer and selection semantics
regeneration lineage
style continuation
render revision system
export system
idempotency
optimistic concurrency
partial completion
error model
responsive workspace shell
warnings and metadata UI
```

Future packs may configure:

```text
mode list
pack-specific optional fields
quick actions
empty-state examples
result-section order
asset labels
specialized action labels
specialized policy modules
specialized evaluation summaries
```

Future packs must not create:

```text
new top-level generation endpoint
new incompatible job state machine
new candidate-selection semantics
new brand-memory authority
new provider-calling UI
new unrelated workspace shell
```

This is the primary reason General Creative must be completed before detailed specialization implementation.

---

## 42. Compatibility Mapping

### 42.1 `00_ROOT_RULES.md`

Preserved:

```text
independent V3 UI
independent V3 APIs
natural-language-first
central brain + multi-agent
no V1/V2 runtime dependency
commercial output over technical controls
```

### 42.2 `01_PRODUCT_VISION.md`

Implements:

```text
auto commercial series
brand continuation
single image
optional template matching
accurate text workflow
minimal user correction
```

### 42.3 `02_SYSTEM_ARCHITECTURE.md`

Preserved:

```text
CreativeJob → CommercialAssetPack
Central Creative Brain ownership
BrandProfile influence
layout / prompt / condition / generation / evaluation separation
```

### 42.4 `07_SCHEMA_CONTRACTS.md`

Preserved:

```text
no required core-schema changes
application DTOs remain outside frozen IR
CreativeJob.requested_output is reused
optional_brand_id and optional_template_id are reused
core output schemas remain authoritative
```

### 42.5 `09_RULES_AND_DEFAULTS.md`

Preserved:

```text
single-image behavior
default-series behavior
platform detection
text-rendering defaults
clarification minimization
rules versioning
```

### 42.6 `10_BRAND_MEMORY_SPEC.md`

Preserved:

```text
temporary profile fallback
persistent profile read
allowed update signals
proposed-before-applied lifecycle
accepted assets only
continuation behavior
```

### 42.7 `11_EVALUATION_AND_REFINEMENT_SPEC.md`

Preserved:

```text
candidate scoring
automatic recommendation
refinement loop
hard failures
candidate ranking
accepted candidate memory interaction
```

### 42.8 `12_PROVIDER_INTERFACES.md`

Preserved:

```text
application and UI never call external providers directly
generation uses GenerationProvider through V3 runtime
text revision uses RendererProvider through V3 rendering service
provider capability gating
Noop/Mock offline tests
```

### 42.9 `15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md`

Implements:

```text
independent V3 route namespace
create / retrieve / select job concepts
V3BalanceAdapter boundary
DefaultCommercialPack fallback
vertical-pack compatibility
```

### 42.10 `17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md`

Implements:

```text
General Creative manifest
shared ScenarioWorkspace
ScenarioApplicationService integration
registry-driven UI
version pinning
pack isolation
General regression
one primary ScenarioPack per job
```

---

## 43. Non-Goals of This Document

This document intentionally does not specify:

```text
which e-commerce platforms receive which asset recipes
which new-media channels receive which hook structures
which community-operation messages are generated
which brand-IP continuity scores are used
which AI manga-drama storyboard schemas are required
```

Those belong to future specialization documents after this shared product runtime is accepted.

---

## 44. Non-Negotiable Summary

```text
General Creative is the baseline product experience.
It remains bound to DefaultCommercialPack.
It adds product and application infrastructure, not a new creative pipeline.
All jobs execute through ScenarioRuntime and the existing Central Creative Brain.
Core schemas remain unchanged.
Application DTOs and lifecycle records are additive.
The UI remains natural-language-first and hides provider internals.
Candidate selection, regeneration, continuation, rendering, memory confirmation,
and export are explicit, immutable, auditable actions.
Persistent brand memory is never silently updated.
Exact text changes use external rendering rather than image regeneration.
Partial success is preserved and recoverable.
Future specialization packs reuse this workspace and runtime instead of forking it.
```

---

## Appendix A. Recommended Extended General Creative Manifest

```json
{
  "manifest_version": "1.0",
  "pack_id": "general_creative",
  "pack_version": "1.1.0",
  "display_name": {
    "zh-CN": "通用创作",
    "en-US": "General Creative"
  },
  "description": {
    "zh-CN": "用自然语言生成通用商业视觉、单张图片或延续品牌风格。",
    "en-US": "Create general commercial visuals, a single image, or brand-continuation work from natural language."
  },
  "category": "general",
  "status": "active",
  "entrypoint": "alchemy_creative_agent_3_0.app.scenario_packs.packs.general_creative.pack:GeneralCreativeScenarioPack",
  "bound_vertical_pack": "DefaultCommercialPack",
  "selection_policy": "explicit_or_default",
  "modes": [
    {
      "mode_id": "auto_commercial_series",
      "display_name": {
        "zh-CN": "自动系列",
        "en-US": "Auto Series"
      },
      "description": {
        "zh-CN": "自动规划并生成一组统一风格的商业视觉。",
        "en-US": "Automatically plan and create a coordinated commercial visual series."
      },
      "status": "active",
      "default_parameters": {
        "requested_output": "commercial_image_series"
      },
      "required_modules": [],
      "optional_modules": [],
      "ui_overrides": {},
      "metadata": {
        "default": true
      }
    },
    {
      "mode_id": "single_asset",
      "display_name": {
        "zh-CN": "单张图片",
        "en-US": "Single Image"
      },
      "description": {
        "zh-CN": "只生成一张主要商业图片，但仍使用完整规划与评估流程。",
        "en-US": "Create one primary commercial image through the full planning and evaluation pipeline."
      },
      "status": "active",
      "default_parameters": {
        "requested_output": "single_image"
      },
      "required_modules": [],
      "optional_modules": [],
      "ui_overrides": {},
      "metadata": {}
    },
    {
      "mode_id": "brand_continuation",
      "display_name": {
        "zh-CN": "延续品牌风格",
        "en-US": "Continue Brand Style"
      },
      "description": {
        "zh-CN": "使用已有品牌档案或已采用素材继续创作。",
        "en-US": "Continue from an existing brand profile or approved assets."
      },
      "status": "active",
      "default_parameters": {
        "requested_output": "commercial_image_series",
        "prefer_persistent_brand": true
      },
      "required_modules": [],
      "optional_modules": [],
      "ui_overrides": {
        "brand_picker_prominence": "high",
        "show_recent_jobs": true
      },
      "metadata": {}
    },
    {
      "mode_id": "template_matched",
      "display_name": {
        "zh-CN": "模板匹配",
        "en-US": "Template Matched"
      },
      "description": {
        "zh-CN": "使用 V3 模板契约辅助结构规划。",
        "en-US": "Use a V3 template contract to guide structure."
      },
      "status": "experimental",
      "default_parameters": {},
      "required_modules": [],
      "optional_modules": [],
      "ui_overrides": {
        "hidden_without_capability": "template_registry"
      },
      "metadata": {}
    }
  ],
  "capability_modules": [],
  "compatibility": {
    "core_contract_min": "1.0",
    "core_contract_max_exclusive": "2.0",
    "manifest_versions": [
      "1.0"
    ],
    "required_core_capabilities": [
      "vertical_agent_pack"
    ],
    "optional_core_capabilities": [
      "generation_loop",
      "brand_memory",
      "renderer",
      "job_event_stream",
      "export"
    ]
  },
  "ui": {
    "card_icon": "sparkles",
    "card_image_asset": null,
    "card_order": 10,
    "featured": true,
    "route_slug": "general_creative",
    "input_fields": [],
    "quick_actions": [
      {
        "action_id": "select_mode",
        "component_id": "GeneralModeSelector"
      },
      {
        "action_id": "select_brand",
        "component_id": "BrandPicker"
      },
      {
        "action_id": "upload_assets",
        "component_id": "AssetUploader"
      },
      {
        "action_id": "quick_controls",
        "component_id": "OptionalQuickControls"
      }
    ],
    "result_sections": [
      "job_progress",
      "asset_series",
      "candidate_selection",
      "text_revision",
      "brand_consistency",
      "generation_summary",
      "export"
    ],
    "empty_state_examples": [
      "帮我做一组新品推广视觉，适合小红书和朋友圈",
      "帮我做一张开业优惠海报",
      "沿用上次品牌风格做一个节日活动系列"
    ],
    "metadata": {
      "current_stage_boundary": "general_creative_only",
      "specialization_cards": "placeholder_only",
      "quick_start_cards": [
        "single_commercial_image",
        "commercial_image_series",
        "festival_campaign",
        "poster_or_cover",
        "brand_style_continuation",
        "reference_image_recreation",
        "text_or_price_revision",
        "auto_planning"
      ],
      "placeholder_card_action": "use_general_creative_instead"
    }
  },
  "tags": [
    "general",
    "commercial_visual",
    "brand_continuation",
    "single_image"
  ],
  "metadata": {
    "policy_neutral": true
  }
}
```

---

## Appendix B. Recommended README Index Addition

Add:

```text
alchemy_creative_agent_3_0/docs/18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
```

Recommended category:

```text
Scenario platform and shared product runtime docs:
```

Do not remove or renumber earlier entries.

---

## Appendix C. Minimal Implementation Status Report

At the end of implementation, report:

```text
GENERAL_CREATIVE_PRODUCT_STATUS: COMPLETE or INCOMPLETE
GENERAL_DEFAULT_PACK_REGRESSION_STATUS: PASS or FAIL
GENERAL_UI_STATUS: PASS or FAIL
JOB_RUNTIME_STATUS: PASS or FAIL
CANDIDATE_ACTION_STATUS: PASS or FAIL
BRAND_CONFIRMATION_STATUS: PASS or FAIL
TEXT_REVISION_STATUS: PASS or FAIL or CAPABILITY_NOT_AVAILABLE
EXPORT_STATUS: PASS or FAIL
MOBILE_ACCESSIBILITY_STATUS: PASS or FAIL
INDEPENDENCE_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
```

