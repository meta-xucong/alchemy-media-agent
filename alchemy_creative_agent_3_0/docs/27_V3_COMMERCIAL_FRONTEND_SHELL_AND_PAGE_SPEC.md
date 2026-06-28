# 27 V3 Commercial Frontend Shell and Page Specification

This document defines the commercial-grade frontend target for Alchemy Creative
Agent 3.x.

It exists because the existing V3 documents define product contracts, Scenario
Hub behavior, General Creative workflow, and future E-Commerce specialization,
but they do not yet provide a single detailed implementation guide for a
production-quality frontend that lives beside V1, V2, and Alchemy Lab.

This document is not a replacement for documents `17`-`26`. It is the frontend
implementation bridge that tells Codex how to turn those contracts into a real
shared-shell product UI.

Document `30_V3_HOME_FIRST_CARD_AND_HISTORY_FRONTEND_FIX_SPEC.md` supersedes
this document for first-screen entry behavior and the V3 independence boundary:
V3 may share only the outer page and navigation shell, but its runtime state,
APIs, history, uploads, jobs, generation, provider controls, cache keys, and
export flow must remain V3-owned.

---

## 1. Decision Summary

Use this document as:

```text
27_V3_COMMERCIAL_FRONTEND_SHELL_AND_PAGE_SPEC.md
```

Recommended development position:

```text
after document 24 shared capabilities are implemented
after documents 18, 19, 20, and 25 have been read as product contracts
before full document 26 E-Commerce activation
before, in parallel with, or immediately after, document 25 implementation
```

Do **not** wait for the full E-Commerce Scenario Pack before building the V3
commercial frontend shell.

Document 25 does not have to be fully coded before the shell starts. It does
need to be treated as the General Creative product contract so the frontend
does not build controls that would later fight the shared capability workflow.

Reason:

1. The shared site shell, V3 entry, Scenario Hub, card-module layout, General
   Creative workspace, job/result views, history panels, and placeholder
   behavior are platform infrastructure.
2. E-Commerce should plug into that infrastructure later as a Scenario Pack.
3. Waiting for full E-Commerce would delay the frontend platform and encourage
   e-commerce-specific UI shortcuts.
4. Building the frontend shell first forces E-Commerce to reuse standard V3
   pages, cards, drawers, job states, and result boards instead of becoming a
   separate app.

Recommended phase naming:

```text
V3.6C Commercial Frontend Shell and Scenario Workspace
```

Then:

```text
V3.7 General Creative With Shared Capabilities
V3.8 E-Commerce Scenario Pack and E-Commerce Workspace Activation
V3.9 Future Specialization Packs
```

---

## 2. Required Reading

Before implementing this frontend, read:

```text
00_ROOT_RULES.md
13_STEP_BY_STEP_DELIVERY_PLAN.md
15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
20_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md
21_V3_PRODUCT_INTEGRATION_EXECUTION_PROMPT.md
23_V3_FOUNDATION_GAP_AUDIT_AND_COMPLETION_SPEC.md
24_V3_SHARED_CAPABILITY_MODULES_FROM_V1_V2_SPEC.md
25_GENERAL_CREATIVE_DOC_DELTA_FOR_SHARED_CAPABILITIES.md
26_ECOMMERCE_SCENARIO_PACK_AND_COMMERCE_CAPABILITY_SPEC.md
```

Also read the existing Alchemy Lab UI documents as style and interaction
references:

```text
docs/alchemy_lab/01_product_spec.md
docs/alchemy_lab/05_ui_flow.md
```

If requirements conflict, use this precedence:

```text
1. V3 independence and product boundary rules
2. Existing V1 / V2 / Alchemy Lab smoke behavior
3. Scenario Pack registry and runtime contracts
4. This commercial frontend document
5. Individual page-level convenience choices
```

---

## 3. Product Target

The target product shape is:

```text
Shared site shell
  -> existing V1 entry
  -> existing V2 entry
  -> existing Alchemy Lab entry
  -> new V3 / 3.0 entry
        -> V3 Scenario Hub
              -> General Creative workspace
              -> E-Commerce placeholder now, full workspace later
              -> New Media placeholder
              -> Private Community placeholder
              -> Brand IP placeholder
        -> V3 job detail pages / drawers
        -> V3 asset, brand, history, and export secondary surfaces
```

The frontend must feel like a commercial product, not a generated engineering
probe. The existing `minimal_ui.py` HTML is useful for contract testing only.
It is not the target UI.

The default interaction style should be close to Alchemy Lab:

```text
module cards
calm setup panels
clear generation button
progress state
result comparison grid
favorite / select actions
details hidden behind toggles or drawers
```

V3 should adapt that card-module style to commercial asset production:

```text
scenario cards
quick-start cards
upload reference cards
brand cards
job state cards
asset slot cards
candidate comparison cards
export cards
```

---

## 4. Non-Goals

Do not implement any of these as part of the commercial shell phase:

```text
a separate V3 website outside the shared product shell
a fork of V1 or V2 frontend state
provider/model/node-graph controls in normal UI
full E-Commerce generation workflow before document 26 contracts pass
full New Media / Private Community / Brand IP workflows
prompt piles inside frontend code
direct provider calls from frontend
hard-coded Scenario Hub cards that ignore registry manifests
```

Do not expose these beginner-facing controls:

```text
seed
sampler
CFG
LoRA
ControlNet
IP-Adapter scale
ComfyUI graph
raw model name
provider payload
negative prompt editor as default workflow
```

Advanced or diagnostic details may exist in internal debug panels only when
the current application already has an authenticated developer/debug pattern.

---

## 5. Frontend Architecture

### 5.1 One Shared Product Shell

The V3 frontend must be mounted into the existing product shell used by V1,
V2, and Alchemy Lab.

The shared shell must provide:

```text
global product navigation
active product state
shared account / balance area if already present
consistent header and page width behavior
stable return path to other product areas
```

Required nav items:

```text
V1
V2
Alchemy Lab
3.0
```

The exact labels may follow the existing product copy, but the V3 item should
be clearly discoverable as the new 3.0 agent.

### 5.2 V3-Owned Frontend Area

After the user clicks `3.0`, the routed page belongs to V3:

```text
/creative-agent-v3
```

Recommended route map:

```text
/creative-agent-v3
/creative-agent-v3/general
/creative-agent-v3/ecommerce
/creative-agent-v3/new-media
/creative-agent-v3/private-domain
/creative-agent-v3/brand-ip
/creative-agent-v3/jobs/:job_id
/creative-agent-v3/jobs/:job_id/results
/creative-agent-v3/jobs/:job_id/export
/creative-agent-v3/brands
/creative-agent-v3/history
```

Implementation may use modals or drawers instead of physical pages for detail
surfaces when that matches the existing frontend stack. Deep-linkable job
details are still recommended for support, reload, and shareability.

### 5.3 API Boundary

The V3 frontend may call only:

```text
/api/v3/creative-agent/*
```

Allowed route families:

```text
scenario hub
creative jobs
generation
selection
brands
balance estimate
future upload adapter
future export adapter
```

The V3 frontend must not call V1/V2 generation routes, V1/V2 workflow state,
or Alchemy Lab module routes unless it is navigating to those products through
the shared shell.

---

## 6. Visual Design System

### 6.1 Overall Feel

The product should feel:

```text
commercial
calm
modular
precise
agentic
operator-friendly
beginner-safe
```

It should not feel:

```text
like a marketing landing page
like a raw form generator
like a professional node/canvas tool
like a provider playground
like a one-color template demo
```

### 6.2 Layout Language

Use a card-module layout similar to Alchemy Lab, but denser and more
production-oriented.

Recommended desktop layout:

```text
Shared shell header
V3 subheader / breadcrumb

Main content band
  Scenario Hub:
    scenario cards grid
    recent jobs / quick continue module

  Scenario Workspace:
    left column: input and controls
    center column: progress and result board
    right column: job inspector / history / warnings
```

Recommended mobile layout:

```text
top product switcher
single-column task flow
sticky primary action
collapsible result sections
bottom or drawer-based job inspector
```

Do not place the primary V3 workflow behind a decorative hero page. The first
screen must let the user choose or start work.

### 6.3 Card Rules

Cards are allowed for:

```text
scenario choices
quick-start presets
uploaded assets
brand choices
job summaries
asset slots
candidate previews
export formats
history items
warnings and recovery actions
```

Cards should not be nested inside other cards. Use full-width bands or panels
for major page sections.

Use stable card dimensions where possible so loading states, labels, and action
buttons do not shift the layout.

### 6.4 Color and Density

Use the existing V1/V2/Alchemy Lab visual language first.

If new V3 styling is needed:

```text
base: neutral workspace background
surface: white or near-white cards
accent: one clear V3 accent for primary actions
status: standard success / warning / error colors
secondary: subdued text and border colors
```

Avoid making V3 a single-hue purple/blue demo UI. It should read as a serious
commercial production surface.

### 6.5 Icons

Use the existing icon library if the frontend already has one. If the stack
uses Lucide or a similar set, use icons for:

```text
scenario cards
upload
brand
history
generate
refresh/regenerate
select/favorite
download/export
warning
settings
more
```

Unfamiliar icons must have accessible labels or tooltips.

### 6.6 Copy Style

Default UI copy should be plain and product-facing.

Prefer:

```text
Create
Generate
Upload reference
Use this style
Keep layout similar
Select result
Export
Continue this style
```

Avoid:

```text
run pipeline
invoke agent
execute graph
model route
provider adapter
capability module
prompt compiler
```

Internal capability names must not appear in normal user-facing labels.

---

## 7. Page 1: Shared Shell Home Integration

### 7.1 Purpose

Let users switch between V1, V2, Alchemy Lab, and V3 without feeling they are
leaving the product.

### 7.2 Required Behavior

The shared shell must:

```text
show a 3.0 entry
highlight 3.0 when V3 route is active
preserve V1/V2/Alchemy Lab routes
not rewrite existing module state
not break existing smoke paths
```

### 7.3 Acceptance

```text
V1 route still loads
V2 route still loads
Alchemy Lab route still loads
V3 route loads
active nav state is correct
browser back/forward works across modules
```

---

## 8. Page 2: V3 Scenario Hub

### 8.1 Purpose

The Scenario Hub is the V3 product home. It shows the agent families as
card modules.

### 8.2 Required First-Screen Cards

Render from the Scenario Pack registry, not from hard-coded page data:

```text
General Creative / 通用创作
E-Commerce / 电商特调
New Media Marketing / 新媒体营销
Private Community Operations / 私域社群运营
Brand IP Operations / 品牌 IP 运营
```

Only General Creative is executable until the E-Commerce pack is explicitly
activated by document 26.

### 8.3 Scenario Card View Model

Each card should render:

```text
scenario_id
display_name
short description
status: active | placeholder | beta | disabled
typical use cases
primary action
secondary action if useful
route hint
visual icon
```

For active General Creative:

```text
primary action: Open workspace
secondary action: Start from blank request
```

For placeholder scenarios:

```text
primary action: View preview
secondary action: Use General Creative instead
```

Placeholder cards must not create jobs.

### 8.4 Hub Modules

Recommended modules:

```text
ScenarioCardsGrid
RecentJobsStrip
BrandContinuationStrip
BalanceSummaryModule
GettingStartedExamplesModule
```

`RecentJobsStrip` and `BrandContinuationStrip` may be hidden until their data
services exist.

### 8.5 Hub Empty and Error States

If scenarios fail to load:

```text
Show a recoverable error panel.
Offer retry.
Do not fall back to hard-coded executable cards.
```

If only General Creative is active:

```text
Show future cards as coming-soon modules.
Do not hide them unless product decides V3 should launch with one card only.
```

---

## 9. Page 3: Shared Scenario Workspace

### 9.1 Purpose

The Scenario Workspace is the reusable execution surface for all active V3
Scenario Packs.

Current active scenario:

```text
General Creative
```

Future active scenario:

```text
E-Commerce
```

The workspace must be shared. Future packs configure it; they do not fork it.

### 9.2 Desktop Structure

Recommended desktop structure:

```text
WorkspaceHeader
  breadcrumb
  scenario switcher
  job status
  balance / cost estimate

WorkspaceBody
  LeftRail
    InputComposerCard
    QuickStartPresetGallery
    UploadReferenceCard
    BrandContextCard
    OptionalControlsDisclosure
    PrimaryGenerateAction

  CenterBoard
    EmptyResultState
    ProgressTimeline
    AssetSeriesBoard
    CandidateComparisonGrid
    SelectedResultPanel

  RightInspector
    JobSummary
    AgentPlanSummary
    WarningsAndFixes
    HistoryContinuity
    ExportStatus
```

### 9.3 Mobile Structure

Recommended mobile structure:

```text
WorkspaceHeader
InputComposerCard
QuickStartPresetGallery
UploadReferenceCard
PrimaryGenerateAction sticky
ProgressTimeline
AssetSeriesBoard
CandidateComparisonGrid
Inspector drawer
```

The mobile UI must not rely on hover-only controls.

### 9.4 Core Workspace Components

#### InputComposerCard

Purpose:

```text
Collect the main natural-language request.
```

Fields:

```text
main request textarea
optional exact text / price / slogan field
optional negative direction field
```

Rules:

```text
main request is required
empty request disables create action
preserve original user input exactly in payload
do not rewrite visible prompt in frontend
```

#### QuickStartPresetGallery

Purpose:

```text
Reduce blank-page friction.
```

Use document 19 preset contracts.

Interaction:

```text
selecting a card updates visible defaults
does not auto-submit
shows a concise input summary
allows user override
```

#### UploadReferenceCard

Purpose:

```text
Let users upload product, logo, style, layout, or background references.
```

Beginner labels:

```text
Use this as product/reference
Use this style
Keep layout similar
Use as logo
Avoid this direction
```

Do not display internal capability names such as `AssetRoleAnalyzer`.

#### BrandContextCard

Purpose:

```text
Select existing brand context or continue from a prior style.
```

Behavior:

```text
brand selection is optional
style continuation must be user-visible
brand memory is not persistently updated without confirmation
```

#### OptionalControlsDisclosure

Purpose:

```text
Expose helpful product-level options without overwhelming beginners.
```

Allowed controls:

```text
output mode: one image | image series | auto
aspect ratio choice in product language
platform/use-case hint
number of outputs within safe bounds
strict text preservation toggle when exact text exists
```

Forbidden controls:

```text
provider
sampler
seed
model
node graph
raw negative prompt editor as primary UI
```

#### ProgressTimeline

Purpose:

```text
Show job progress without exposing internal pipeline mechanics.
```

Recommended states:

```text
Preparing creative plan
Creating candidates
Reviewing results
Ready to choose
Needs attention
Export ready
```

#### AssetSeriesBoard

Purpose:

```text
Show planned and generated output slots.
```

Each asset slot card should show:

```text
asset type
purpose
platform/use-case
status
preview if available
selected candidate if available
warnings if any
```

#### CandidateComparisonGrid

Purpose:

```text
Let users compare generated candidates and choose the best.
```

Each candidate card should show:

```text
image preview or mock preview
overall recommendation
fit label
select action
regenerate action if available
details toggle
```

#### RightInspector

Purpose:

```text
Keep advanced context available without cluttering the primary workflow.
```

It may show:

```text
job id
scenario
selected preset
brand context
uploaded assets
warnings in product language
agent plan summary
export package status
```

It must not show raw provider payloads in normal mode.

---

## 10. General Creative Workspace

### 10.1 Required Default Flow

```text
Open V3
Select General Creative
Enter simple request
Optionally choose quick-start card
Optionally upload references
Optionally choose brand/style history
Create job
Generate candidates or planned series
Compare results
Select preferred result
Optionally export or continue style
```

### 10.2 Quick-Start Cards

Use document 19 and document 20. Initial visible set should include:

```text
Free Create
Commercial Image Series
Single Commercial Image
Campaign Poster
Product / Service Showcase
Social Media Visual
Festival / Seasonal Visual
Poster or Cover
Brand Style Continuation
Reference Image Recreation
Text or Price Revision
Auto Planning
```

The exact card list may be adjusted to the existing manifest, but the UI must
separate:

```text
quick-start preset
scenario pack
product mode
```

### 10.3 Shared Capability UI After Document 24

Document 24 is now the capability layer. The UI should surface capability
effects in product language.

Examples:

```text
Uploaded reference understood
Product/reference image will be preserved
Layout similarity requested
Exact text will be checked
Some claims need confirmation
```

Do not show:

```text
AssetRoleAnalyzer
AssetBindingPlanner
InformationIntegrityLockModule
PromptConstraintCompiler
```

### 10.4 General Creative Must Stay Policy-Neutral

General Creative may accept product-like references and facts, but must not
turn into the E-Commerce workflow.

General Creative UI must not show:

```text
Amazon title fields
five bullet points
search terms
competitor review mining
marketplace compliance checklist
listing-ready promise
platform-specific image sequence by default
```

Those belong to the E-Commerce workspace after document 26.

---

## 11. E-Commerce Frontend Strategy

### 11.1 Current Stage

Before document 26 is fully implemented, E-Commerce is a placeholder card and
placeholder route.

Clicking it should show a simple preview panel:

```text
电商特调将在后续版本开放。
你可以先使用通用创作，用自然语言描述商品图、活动图或店铺素材需求。
```

Allowed actions:

```text
Use General Creative instead
Back to Scenario Hub
```

Forbidden actions:

```text
create e-commerce job
open marketplace form
upload product image as an e-commerce required input
call e-commerce pack API
show Amazon-specific workflow
```

### 11.2 Full E-Commerce Workspace After Document 26

After document 26 backend contracts and tests pass, the same Scenario Workspace
can activate E-Commerce mode.

Default E-Commerce flow:

```text
Upload product image
Type a short request
Optionally choose platform / market
Generate mature image set
Review image slots
Select/export package
```

Default mode:

```text
one_click_product_set
```

Visible default input modules:

```text
ProductImageUploadCard
ShortCommerceRequestCard
PlatformMarketOptionalCard
BrandStoreStyleCard
AdvancedCommerceDetailsDisclosure
```

Advanced collapsed fields may include:

```text
product facts
target buyer
price band
keywords
competitor/style reference
forbidden claims
required overlay text
```

Do not force the user through an Amazon copywriting workflow unless they open
an advanced mode.

### 11.3 E-Commerce Result Board

For `one_click_product_set`, the default result board should show slot cards:

```text
Main image
Feature image
Scenario/lifestyle image
Detail/material image
Size/spec image
Trust/comparison image
Ad cover
```

The pack may reduce or expand these slots based on product category and
platform. The user sees a mature set, not a list of internal recipes.

---

## 12. Secondary Pages, Drawers, and Modals

V3 must support richer commercial workflows without cluttering the main page.
Use secondary pages, drawers, or modals depending on the existing frontend
stack.

Required surfaces:

### 12.1 Asset Upload Drawer

Purpose:

```text
Upload and label reference assets.
```

Inputs:

```text
file upload
asset role selection in beginner language
optional note
remove / replace
```

### 12.2 Brand Picker Drawer

Purpose:

```text
Select brand memory or continue from previous style.
```

Shows:

```text
brand name
recent style references
visual tone
last used time
```

### 12.3 Candidate Preview Modal

Purpose:

```text
Inspect a result candidate.
```

Shows:

```text
large preview
asset purpose
recommendation
warnings
select action
regenerate action
download/export action when available
details toggle
```

### 12.4 Job Details Page Or Drawer

Purpose:

```text
Persist and inspect a job after refresh.
```

Shows:

```text
job status
request summary
scenario
asset series
candidates
selected result
history and revisions
export package
```

### 12.5 Export Drawer

Purpose:

```text
Prepare selected outputs for user download or platform handoff.
```

Shows:

```text
selected assets
file naming
dimensions
format
metadata summary
download action
```

### 12.6 Warning And Recovery Panel

Purpose:

```text
Make failures recoverable.
```

Examples:

```text
Some images failed, successful results are ready.
Your reference image is too small.
Exact text needs confirmation.
This scenario is not active yet.
Insufficient balance.
```

Warnings must be written in product language, not internal exception language.

---

## 13. Frontend State Model

Recommended frontend state slices:

```text
ProductShellState
ScenarioHubState
WorkspaceState
DraftRequestState
UploadState
BrandContextState
JobState
GenerationState
CandidateSelectionState
HistoryState
ExportState
DrawerState
```

### 13.1 ScenarioHubState

```json
{
  "loading": false,
  "error": null,
  "scenario_cards": [],
  "active_scenario_ids": [],
  "placeholder_scenario_ids": []
}
```

### 13.2 DraftRequestState

```json
{
  "scenario_id": "general_creative",
  "preset_id": null,
  "mode_id": null,
  "user_input": "",
  "uploaded_asset_ids": [],
  "brand_id": null,
  "product_profile": {},
  "visible_summary": []
}
```

### 13.3 JobState

```json
{
  "job_id": null,
  "status": "ready",
  "scenario": null,
  "asset_series": [],
  "candidates": [],
  "selected_result": null,
  "warnings": [],
  "metadata": {}
}
```

The UI may store richer local data, but requests sent to V3 APIs must remain
product-level and low-level-control-free.

---

## 14. User Interaction Logic

### 14.1 Scenario Selection

```text
User clicks scenario card
  -> if active: navigate to shared workspace with scenario_id
  -> if placeholder: open placeholder panel or placeholder route
```

Placeholder selection must never call create-job.

### 14.2 Job Creation

```text
User completes visible request
  -> frontend validates required visible fields
  -> POST /api/v3/creative-agent/jobs
  -> status panel shows planned/blocked state
  -> if planned, enable generate action
```

### 14.3 Generation

```text
User clicks generate
  -> POST /api/v3/creative-agent/jobs/:job_id/generate
  -> poll or refresh job state
  -> render asset series and candidates
```

If the current backend is synchronous, still keep the UI state model compatible
with future async progress.

### 14.4 Candidate Selection

```text
User selects a candidate
  -> POST /api/v3/creative-agent/jobs/:job_id/select
  -> selected state updates
  -> offer export and optional brand-memory confirmation
```

### 14.5 Brand Memory Confirmation

```text
Never silently persist brand memory.
```

The UI must show an explicit confirmation when a selected result can update a
brand profile.

### 14.6 History Continuation

```text
User opens history
  -> selects prior job/style
  -> draft request records continuation source
  -> workspace summary shows the selected source
```

### 14.7 Exact Text Revision

If text rendering exists:

```text
User edits exact text
  -> frontend calls V3 text/render revision route
  -> does not regenerate base image unless required
```

If text rendering is not available:

```text
UI shows capability unavailable or uses normal regeneration with clear warning.
```

---

## 15. Commercial Frontend Implementation Sequence

### Phase F0 - Document And Audit

1. Add this document.
2. Update README and delivery plan index.
3. Confirm existing V3 app-shell contracts remain useful as test probes only.

### Phase F1 - Shared Shell Navigation

1. Locate existing V1/V2/Alchemy Lab frontend shell.
2. Add V3 / 3.0 navigation entry.
3. Preserve V1/V2/Alchemy Lab routes and smoke behavior.
4. Add route to `/creative-agent-v3`.
5. Add tests or smoke probes for all product entries.

### Phase F2 - Commercial V3 Scenario Hub

1. Build real Scenario Hub page.
2. Load card data from V3 scenario hub contract/API.
3. Render five scenario cards.
4. Make General Creative active.
5. Make all future scenario cards placeholder-only.
6. Add desktop and mobile layout tests.

### Phase F3 - Shared Scenario Workspace MVP

1. Build shared workspace layout.
2. Wire General Creative draft request to V3 Product API.
3. Render planned job status, asset series, candidates, selected result, and
   warnings.
4. Add job detail route or drawer.
5. Add result preview modal.

### Phase F4 - General Creative Commercial UX

1. Add quick-start cards from documents 19 and 20.
2. Add upload reference card and brand context card.
3. Add capability-aware product-language summaries from document 25.
4. Keep General Creative policy-neutral.
5. Add end-to-end tests for create, generate, select, and placeholder behavior.

### Phase F5 - E-Commerce Placeholder

1. Route `/creative-agent-v3/ecommerce` to a placeholder panel.
2. Show coming-soon state and General Creative fallback.
3. Prove placeholder cannot create jobs.

### Phase F6 - E-Commerce Workspace Activation After Document 26

Only start after document 26 backend contracts and tests pass.

1. Activate E-Commerce card as beta or active.
2. Reuse shared Scenario Workspace.
3. Add product image upload, short prompt, platform/market optional card.
4. Add e-commerce result slot board.
5. Keep advanced commerce fields collapsed.
6. Add full e-commerce UI tests.

---

## 16. Tests And Verification

### 16.1 Unit / Contract Tests

Required:

```text
Scenario Hub cards come from registry data
placeholder cards cannot create jobs
General Creative request payload contains scenario_selection
frontend request builder rejects low-level controls
capability summaries are mapped to product-language UI labels
```

### 16.2 Smoke Tests

Required:

```text
V1 route loads
V2 route loads
Alchemy Lab route loads
V3 route loads
V3 Scenario Hub renders
General Creative workspace renders
E-Commerce placeholder renders
```

### 16.3 Browser / E2E Tests

Use the repository's existing browser test stack. If none exists, add the
smallest appropriate Playwright smoke suite.

Cover:

```text
desktop V3 hub
mobile V3 hub
desktop General workspace
mobile General workspace
create job from General Creative
generate result when backend mock/real path supports it
select result
open candidate preview
open export drawer
placeholder card cannot create job
browser back/forward between shared-shell modules
```

### 16.4 Visual QA

Before accepting the frontend, capture screenshots for:

```text
desktop 1440px
desktop 1024px
mobile 390px
mobile 430px
```

Check:

```text
no overlapping text
buttons do not resize unexpectedly
cards have stable dimensions
long labels wrap cleanly
empty/loading/error states are visible
placeholder cards are clearly disabled
primary action is obvious
```

### 16.5 Accessibility

Required:

```text
keyboard navigation for cards and actions
visible focus states
form labels
button accessible names
modal/drawer focus trapping
non-color-only status signals
```

---

## 17. File Placement Guidance

Codex must inspect the existing frontend stack before choosing files.

Preferred:

```text
extend the existing shared frontend shell
reuse existing CSS variables / visual tokens if present
reuse static layout primitives only when they do not carry runtime state
```

Avoid:

```text
creating a separate frontend framework if one already exists
adding a second visual system for V3
copying V1/V2 runtime state logic
copying Alchemy Lab runtime state logic
putting V3 API calls inside V1/V2 modules
using V1/V2/Lab API routes as V3 data sources
sharing V1/V2/Lab history, uploads, job IDs, cache keys, or provider controls
```

If the repository has no real frontend application in the current worktree,
Codex should implement the commercial frontend as the smallest compatible web
layer that can be served and tested locally, while keeping V3 APIs and state
V3-owned.

---

## 18. Acceptance Criteria

Commercial frontend status is `PASS` only when:

```text
1. V3 appears beside V1, V2, and Alchemy Lab in the shared product shell.
2. Clicking V3 opens a real V3 Scenario Hub, not the old minimal contract HTML.
3. Scenario Hub renders registry-driven card modules.
4. General Creative opens a V3-owned workspace.
5. E-Commerce and other future packs are visible placeholders unless activated by their own accepted specs.
6. General Creative can create, inspect, generate/select where backend capability exists.
7. Candidate/result boards are card-based and commercially usable.
8. Drawers/modals exist for upload, brand/history, preview, warnings, and export as supported by current backend.
9. Beginner UI hides provider, model, adapter, node graph, and raw capability names.
10. V3 frontend calls only V3 API routes for V3 work.
11. V1, V2, and Alchemy Lab smoke paths still pass.
12. Desktop and mobile screenshots pass visual QA.
13. Tests pass.
```

---

## 19. Required Final Report

When this frontend phase is implemented, Codex must report:

```text
V3_COMMERCIAL_FRONTEND_STATUS: COMPLETE or INCOMPLETE
SHARED_SHELL_STATUS: PASS or FAIL
V1_V2_ALCHEMY_LAB_SMOKE_STATUS: PASS or FAIL
SCENARIO_HUB_UI_STATUS: PASS or FAIL
GENERAL_WORKSPACE_UI_STATUS: PASS or FAIL
PLACEHOLDER_BOUNDARY_STATUS: PASS or FAIL
API_BOUNDARY_STATUS: PASS or FAIL
DESKTOP_VISUAL_QA_STATUS: PASS or FAIL
MOBILE_VISUAL_QA_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
```

Also summarize:

```text
frontend stack used
routes added
files changed outside alchemy_creative_agent_3_0/
tests run
screenshots captured
known limitations
whether E-Commerce remains placeholder or is activated
```

---

## 20. Strategic Rule

The commercial frontend should be built before full E-Commerce is complete, but
it must not pretend E-Commerce is complete.

Correct:

```text
Build shared shell
Build V3 Scenario Hub
Build General Creative workspace
Show E-Commerce card as placeholder
Later activate E-Commerce inside the same workspace after document 26 passes
```

Incorrect:

```text
Wait for all E-Commerce backend logic before building any real V3 frontend
Build a separate E-Commerce frontend first
Hard-code prompt workflows into E-Commerce UI
Let E-Commerce fork V3 workspace infrastructure
```

The frontend platform comes first. Specialized agent pages plug into it.
