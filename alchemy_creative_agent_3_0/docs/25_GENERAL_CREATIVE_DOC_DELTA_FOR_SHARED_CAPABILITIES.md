# 25 General Creative Delta For Shared Capability Modules

This document supplements `18`, `19`, and `20`.

The General Creative module should benefit from the V1/V2-derived shared capabilities, but it must remain policy-neutral. It should not become an e-commerce agent by accident.

## Core Decision

General Creative may use shared capabilities for:

1. uploaded reference understanding
2. style/reference binding
3. template or case matching
4. visual grammar preservation
5. exact text/logo/product fact preservation when the user provides those facts
6. output review and refinement hints
7. history continuation

General Creative must not use:

1. marketplace rules
2. platform-specific listing requirements
3. Amazon title/bullet/search-term logic
4. e-commerce selling point ranking
5. competitor review mining
6. product claim compliance beyond generic fact preservation

Those belong to the E-Commerce Scenario Pack in `26`.

## Required Changes To `18`

`18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md` should be interpreted with the following additions.

### Add Capability-Aware Runtime Context

General Creative requests should be able to carry optional capability context:

1. uploaded asset ids
2. selected preset id
3. selected template/case id
4. history continuation id
5. text/logo/product facts that must be preserved
6. user-selected strength controls expressed in simple product language

Do not expose low-level generation controls.

### Add General Capability Bundle

General Creative can enable this default optional bundle:

| Capability | Default Status | Purpose |
| --- | --- | --- |
| AssetRoleAnalyzer | Enabled when assets exist | Understand uploaded references. |
| AssetBindingPlanner | Enabled when assets exist | Decide how references should influence the result. |
| CaseLibraryRetriever | Optional | Find reusable creative patterns. |
| VisualGrammarLockModule | Optional | Preserve composition/style from a selected reference or template. |
| InformationIntegrityLockModule | Enabled when exact text/logo/facts exist | Prevent user-provided facts from being lost. |
| PromptConstraintCompiler | Enabled when any capability emits constraints | Merge constraints into prompt/layout/evaluation stages. |
| OutputReviewModule | Optional | Review candidate fit and propose refinements. |
| HistoryReferenceModule | Enabled when user asks to continue a prior style | Reuse selected history safely. |

### Add Simpler User Controls

General Creative UI should use simple controls:

1. "Use this as product/reference"
2. "Use this style"
3. "Keep layout similar"
4. "Keep text/logo exact"
5. "Continue previous style"
6. "Avoid previous direction"

The UI should not show internal capability names.

## Required Changes To `19`

`19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md` remains valid, but presets should now declare capability preferences.

Each preset may define:

1. default aspect ratio
2. default scene type
3. required input slots
4. optional input slots
5. enabled shared capabilities
6. visual grammar lock strength
7. output review strictness

Example preset categories:

| Preset Type | Shared Capability Use |
| --- | --- |
| Poster/key visual | Optional case retrieval and visual grammar lock. |
| Social media cover | Optional template/case retrieval. |
| Product-style hero image | Asset role analysis and fact preservation, but no marketplace rules. |
| Brand campaign visual | Brand memory and history continuation. |
| Text-heavy design | Information integrity and output review. |

Important boundary:

A "product-style hero image" preset in General Creative is not the same as the E-Commerce product set mode. It can create a nice product visual, but it should not promise platform-ready listing image sets.

## Required Changes To `20`

`20_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md` should add capability closure gates.

New closure gates:

1. Uploaded asset analysis is reflected in job metadata.
2. Reference binding choices are explainable.
3. Visual grammar lock strength is visible in run metadata.
4. Exact text/logo/fact preservation is reviewed.
5. Output review issues are visible to the user in product language.
6. History continuation can be accepted, rejected, or disabled.

## General Creative Execution Flow

Expected flow after `23` and `24`:

1. User opens General Creative.
2. User enters a simple prompt and optionally uploads references.
3. ScenarioRuntime resolves `general_creative`.
4. General Scenario Pack validates input and preset.
5. Shared capabilities run only if needed.
6. Central brain creates plan, series, prompts, and candidates.
7. OutputReviewModule adds product-language critique.
8. User selects a candidate.
9. HistoryReferenceModule and brand memory receive the selection if user allows it.

## API And Contract Notes

General Creative should accept:

1. `scenario_selection.scenario_id = "general_creative"`
2. optional `scenario_selection.preset_id`
3. optional `uploaded_asset_ids`
4. optional `product_profile` only as a generic factual profile
5. optional `metadata` for internal audit and backward compatibility

General Creative should reject:

1. platform marketplace profile as a required e-commerce mode
2. Amazon listing fields
3. SEO keyword roots as a generation requirement
4. competitor listing analysis as a required workflow

If the user supplies e-commerce-like information while using General Creative, the system can:

1. use generic product facts for visual generation, or
2. recommend switching to the E-Commerce Scenario Pack once it is active

## Tests To Add

1. General Creative runs with no uploaded assets.
2. General Creative runs with one style reference.
3. General Creative runs with one product/reference image and preserves the fact context generically.
4. General Creative preset enables VisualGrammarLockModule without activating commerce logic.
5. General Creative rejects low-level controls.
6. General Creative does not select `EcommerceAgentFamily` unless the scenario/category truly requires it.
7. History continuation is brand-scoped.

## Acceptance Before Moving To Full E-Commerce

Before implementing `26`, Codex must verify:

1. General Creative remains usable for non-commerce creative work.
2. Shared capabilities work in neutral mode.
3. No marketplace or Amazon logic appears in General Creative docs, UI labels, or runtime defaults.
4. The document `27` commercial frontend shell exists or is scheduled before E-Commerce activation, so commerce UI plugs into the shared V3 workspace instead of a forked page.
5. Existing tests and new General tests pass.
