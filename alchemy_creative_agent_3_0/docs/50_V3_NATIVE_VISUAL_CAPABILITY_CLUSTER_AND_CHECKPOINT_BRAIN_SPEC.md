# 50 V3 Native Visual Capability Cluster And Checkpoint Brain Spec

Current authority note:

```text
Documents 51 and 52 extend this document.

Document 51 is the implementation authority for commercial-grade consistency,
strong selected-image references, explicit identity/product/brand-asset locks,
automatic output review contracts, retry patches, and best-output selection.

Document 52 is the implementation authority for the next deepening phase:
generated output file resolution, real post-generation visual inspection,
append-only retry execution, suite variation direction, and beginner-facing
output curation.

This document still owns the architecture rule that all reusable visual
enhancement belongs inside one V3-native Visual Capability Cluster. Documents
51 and 52 define the next child modules and quality gates under that cluster.
```

## 1. Purpose

This document is the current authority for the next V3 optimization:

```text
make visual enhancement reusable, cleanly owned, and centrally dispatched
inside V3, while upgrading the V3 LLM Brain into a direct multi-stage
checkpoint brain.
```

It formalizes the latest product and architecture decision:

```text
V3 should not make the central brain heavy.
V3 should not keep scattered visual enhancement logic in templates, prompt
compilers, or old V1/V2 compatibility corners.
V3 should own one native shared visual capability cluster, with child modules
under one module framework and one dispatch path.
```

This document is a development specification. It does not require code to be
changed immediately. When code work starts, this document must be read after
documents `24`, `32`-`49`, and before touching shared capability, brain,
prompt, template, or project-context logic.

---

## 2. Final Architecture Decision

### 2.1 Visual enhancement ownership

Authoritative rule:

```text
All reusable visual enhancement belongs to the V3 native shared capability
layer, organized as one Visual Capability Cluster.
```

Allowed owner:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/
```

Preferred future structure:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/
  visual_cluster/
    __init__.py
    contracts.py
    orchestrator.py
    profile_builder.py
    reference_binding.py
    case_visual_language.py
    grammar_snapshot.py
    consistency_guard.py
    quality_reviewer.py
    audit.py
```

Compatibility path:

Existing files such as `asset_role_analyzer.py`, `asset_binding_planner.py`,
`case_library.py`, `visual_grammar_lock.py`, `prompt_constraint_compiler.py`,
`output_review.py`, and `history_reference.py` may remain in place during the
first code phase. They must be registered and dispatched as child modules of
the Visual Capability Cluster.

Hard boundary:

```text
V1/V2 enhanced modules are references only.
No V1/V2 runtime import, V1/V2 API call, V1/V2 schema reuse, or V1/V2 job
dependency is allowed.
```

### 2.2 Brain ownership

Authoritative rule:

```text
V3 has one reasoning path: a V3-native direct LLM checkpoint brain.
```

Allowed:

```text
V3-owned llm_brain package
direct API calls through V3-owned provider adapters
OpenAI-compatible or other direct LLM APIs if configured through V3 settings
deterministic fallback when no LLM is available
```

Forbidden:

```text
Claude Code as a V3 expert-brain runtime
Claude Code CLI as a provider path
V2 Claude orchestrator
V2 prompt plan objects
V2 case intelligence runtime
future "Claude Code expert mode" interfaces
parallel brain implementations for the same V3 job path
```

This does not forbid a direct LLM API provider from being Anthropic-compatible
in a generic technical sense. It forbids routing V3 through the Claude Code
agent/CLI/expert runtime or treating that route as a future extension point.

### 2.3 Central brain scope

The central brain remains an orchestrator and consumer:

```text
CentralCreativeBrain
  reads capability outputs
  reads Brain checkpoint outputs
  chooses V3-level creative decisions
  returns structured plans
```

It must not own reusable visual grammar extraction, visual-memory reuse,
reference-binding semantics, output visual review, or style-consistency rules.
Those belong to the Visual Capability Cluster.

Document 67 tightens this rule into an implementation cleanup: the central
brain and deterministic fallback Brain may consume visual cluster payloads, but
must not instantiate visual child modules or rebuild their plans.

---

## 3. Compatibility With Existing V3

This plan is an upgrade on the current V3 foundation. It is not a rewrite.

Keep:

```text
Project Mode
ProjectContextPackage
ScenarioRuntime
Scenario Pack Registry
Project Template Registry
V3 Product API
V3 generation providers and output storage
V3 upload store
V3 Brand Memory confirmation flow
V3 shared_capabilities base contracts and registry
V3 llm_brain package
```

Add or refine:

```text
VisualCapabilityCluster ownership contract
VisualGrammarProfile
ProjectVisualGrammarSnapshot
VisualReferenceBindingProfile
VisualConsistencyGuardResult
VisualQualityReviewResult
multi-stage Brain checkpoints
strong ownership audit
```

Do not:

```text
replace ScenarioRuntime
replace Project Mode
replace Product API
move provider routing into shared capabilities
let templates build private visual engines
move V1/V2 modules into V3 without rewriting ownership and contracts
```

---

## 4. Current State Audit

The current V3 code already has the correct foundation:

```text
app/shared_capabilities/
  asset_role_analyzer.py
  asset_binding_planner.py
  case_library.py
  visual_grammar_lock.py
  information_integrity.py
  prompt_constraint_compiler.py
  output_review.py
  history_reference.py
  registry.py
  contracts.py
  base.py
```

This proves that document `24` was directionally correct.

The gap is not "missing shared capabilities". The gap is that these modules are
still separate capability points, not yet a product-grade reusable visual
system.

Known missing pieces:

```text
1. No cluster-level visual enhancement contract.
2. No project-level visual grammar snapshot.
3. No reusable visual profile containing composition, camera, light, material,
   color, layout, subject treatment, reference role, and avoid rules.
4. No explicit visual consistency guard that checks new prompts/jobs against
   selected project style.
5. No strong ownership audit proving scattered visual logic is centralized.
6. No multi-stage Brain checkpoint contract separating intent, visual strategy,
   prompt review, generation preparation, and post-generation review.
7. Some documents still describe optional/future provider routes too loosely.
```

---

## 5. Target Runtime Shape

The target flow:

```text
Project
  -> Template
      -> Scenario Pack
          -> ScenarioRuntime
              -> SharedCapabilityRegistry
                  -> VisualCapabilityCluster
                      -> child visual modules
                  -> other shared capabilities
              -> DirectLLMCheckpointBrain
              -> CentralCreativeBrain
              -> PromptCompilerAgent
              -> GenerationProvider
              -> PostGenerationReview
              -> ProjectContext update
```

Important:

```text
Project wraps Job.
Template wraps Scenario Pack.
VisualCapabilityCluster wraps reusable visual modules.
DirectLLMCheckpointBrain wraps LLM reasoning checkpoints.
None of these replace the layers below them.
```

---

## 6. Visual Capability Cluster Contract

### 6.1 Cluster request

Add a cluster-level input contract when implementation begins:

```text
VisualCapabilityClusterRequest
  request_id
  project_id
  job_id
  template_id
  scenario_id
  user_input
  project_context_package
  selected_output_refs
  uploaded_reference_assets
  brand_memory_summary
  negative_feedback_summary
  requested_image_count
  requested_image_size
  scenario_policy
  previous_capability_outputs
  metadata
```

Rules:

```text
1. It may read selected project outputs as positive references.
2. It may read uploaded references that belong to this V3 project/user.
3. It may read explicit Brand Memory only when linked or user-confirmed.
4. It must respect rejected directions.
5. It must not read V1/V2/Lab runtime state.
6. It must not include provider secrets or raw provider parameters.
```

### 6.2 Cluster result

Add:

```text
VisualCapabilityClusterResult
  cluster_id = visual_capability_cluster
  version
  status
  child_results
  visual_grammar_profile
  project_visual_snapshot
  reference_binding_profile
  prompt_constraints
  consistency_guard
  quality_review_plan
  user_visible_summary
  warnings
  audit
```

The result must be serializable and safe to store in job metadata.

### 6.3 Child module registry metadata

Every visual child module must declare:

```text
module_id
cluster_id = visual_capability_cluster
version
required_inputs
output_contract
template_policy
failure_policy
public_summary_policy
```

Failure rule:

```text
Optional visual modules warn and degrade.
Required visual modules block only when the template explicitly marks them
required.
```

---

## 7. Visual Data Contracts

### 7.1 VisualGrammarProfile

Purpose:

Capture the reusable "visual language" that lets a project produce a coherent
series instead of isolated one-off pictures.

Fields:

```text
profile_id
source_type
source_refs
composition
camera_or_viewpoint
subject_framing
spatial_hierarchy
lighting
color_palette
material_and_texture
background_language
layout_density
typography_or_text_treatment
mood_keywords
style_keywords
series_variation_rules
must_keep_rules
must_avoid_rules
confidence
evidence
```

Examples of source type:

```text
selected_project_output
uploaded_reference
case_reference
brand_memory
user_instruction
scenario_default
```

### 7.2 ProjectVisualGrammarSnapshot

Purpose:

Store the current project-level visual direction that future jobs can reuse.

Fields:

```text
snapshot_id
project_id
template_id
scenario_id
created_from_job_id
selected_output_ids
active_reference_ids
visual_grammar_profile
continuity_strength
locked_elements
flexible_elements
negative_directions
last_user_confirmed_at
metadata
```

Rules:

```text
1. Only selected or user-confirmed outputs become positive visual context.
2. Unselected candidates stay in history but do not update the snapshot.
3. Rejected outputs add negative direction notes.
4. Brand Memory is not updated automatically from this snapshot.
5. The snapshot is project-scoped unless the user explicitly saves style to
   Brand Memory.
```

### 7.3 VisualReferenceBindingProfile

Purpose:

Clarify how reference images should affect generation.

Fields:

```text
asset_id
asset_role
binding_strength
preserve_identity
preserve_shape
preserve_color
preserve_layout
allowed_transformations
forbidden_transformations
provider_reference_needed
human_summary
evidence
```

Roles should remain V3-native:

```text
subject_reference
style_reference
composition_reference
face_reference
product_reference
logo_reference
background_reference
color_reference
negative_reference
unknown_reference
```

### 7.4 VisualConsistencyGuardResult

Purpose:

Prevent a continuation job from drifting away from the confirmed project
direction.

Fields:

```text
status
consistency_score
kept_elements
drift_risks
missing_reference_usage
conflicting_user_request_parts
recommended_revisions
block_reasons
```

Statuses:

```text
pass
revise
warn
block
```

### 7.5 VisualQualityReviewResult

Purpose:

Review generated outputs with project consistency and user-visible quality in
mind.

Fields:

```text
output_id
status
visual_match_score
subject_match_score
style_match_score
series_consistency_score
visible_defects
prompt_following_issues
recommend_select
recommend_delete
regeneration_notes
user_visible_summary
```

This may start deterministic and later use vision/LLM review, but it must stay
under V3-owned contracts.

---

## 8. Child Module Ownership Map

The Visual Capability Cluster may include existing and new child modules:

| Child module | Existing source | Target responsibility |
| --- | --- | --- |
| Asset role analysis | `asset_role_analyzer.py` | Identify reference roles, image quality, and preservation needs. |
| Reference binding | `asset_binding_planner.py` | Decide how each reference constrains or guides generation. |
| Case visual language | `case_library.py` | Retrieve cases and extract reusable visual signals. |
| Visual grammar profile builder | upgrade `visual_grammar_lock.py` | Build `VisualGrammarProfile` from references, cases, selected outputs, and user request. |
| Project visual snapshot builder | new | Convert selected project context into `ProjectVisualGrammarSnapshot`. |
| Prompt visual constraints | `prompt_constraint_compiler.py` | Convert cluster outputs into V3 prompt/layout/evaluation constraints. |
| Information integrity | `information_integrity.py` | Preserve text, subject facts, product facts, and explicit user facts where relevant. |
| Visual consistency guard | new | Check continuation prompts against the active project visual snapshot. |
| Output visual review | upgrade `output_review.py` | Review outputs for visual quality and project consistency. |
| History/reference continuation | `history_reference.py` | Convert selected project history into safe continuation references. |

Rule:

```text
Existing child modules may remain separate files, but their ownership and
dispatch must be visible through the Visual Capability Cluster contract.
```

---

## 9. Project Context Integration

Project Mode is the reason the visual cluster matters.

Add to future `ProjectContextPackage` implementation:

```text
visual_grammar_snapshot
confirmed_visual_profile_summary
selected_visual_references
negative_visual_directions
continuity_strength
last_visual_quality_notes
```

The context builder must:

```text
1. Read only the current project/user data.
2. Prefer selected outputs over unselected candidates.
3. Include uploaded references only when active.
4. Include negative feedback as avoid rules.
5. Include Brand Memory only when explicitly linked or selected.
6. Provide a compact LLM-safe digest for the checkpoint brain.
```

The frontend should not show raw cluster contracts by default. It should show:

```text
V3 is keeping: style, light, color, subject, layout
V3 will avoid: rejected direction notes
This project can continue from: selected images and saved references
```

The full workflow detail may be folded behind an advanced, plain-language
"what V3 did" panel.

---

## 10. Direct LLM Checkpoint Brain

### 10.1 Why checkpoints

The V3 Brain should not be one opaque prompt enhancer. It should produce
auditable stages:

```text
understand intent
read project memory
choose visual strategy
prepare prompt guidance
review before generation
review after generation
```

The UI may show only simple progress messages, but the backend must keep
structured checkpoints for debugging and quality improvement.

### 10.2 Checkpoint stages

Add or evolve the V3 LLM Brain into these stages:

| Stage | Input | Output | Owner |
| --- | --- | --- | --- |
| Intent checkpoint | user input, template, scenario | `BrainIntentSummary` | LLM Brain |
| Context checkpoint | `ProjectContextPackage`, visual snapshot | `BrainProjectMemoryDigest` | LLM Brain consumes Visual Cluster |
| Visual strategy checkpoint | intent + visual cluster result | `BrainVisualStrategy` | LLM Brain |
| Prompt guidance checkpoint | strategy + constraints | `BrainPromptGuidance` | LLM Brain |
| Pre-generation review checkpoint | compiled guidance + final prompt draft | `BrainPromptReview` | LLM Brain |
| Post-generation review checkpoint | generated outputs + visual snapshot | `BrainOutputReviewDigest` | LLM Brain consumes Visual Cluster review |

The Brain must not expose hidden chain-of-thought. Store structured decisions,
not private reasoning.

### 10.3 Direct provider rule

Provider rule:

```text
V3 Brain uses V3-owned direct LLM API adapters only.
```

Configuration may include:

```text
V3_LLM_BRAIN_ENABLED=true
V3_LLM_BRAIN_PROVIDER=auto
V3_LLM_BRAIN_MODEL=
V3_LLM_BRAIN_TIMEOUT_SECONDS=45
V3_LLM_BRAIN_CHECKPOINT_MODE=standard
V3_LLM_BRAIN_FALLBACK=deterministic
```

Forbidden configuration:

```text
V3_LLM_BRAIN_PROVIDER=claude_code
V3_LLM_BRAIN_EXPERT_MODE=claude_code
V3_CLAUDE_CODE_BRAIN_ENABLED=true
```

If such settings exist later, tests must fail.

### 10.4 Fallback rule

If the LLM provider is missing or unstable:

```text
1. Use deterministic fallback checkpoints.
2. Preserve visual cluster outputs.
3. Generate a safe final prompt.
4. Record `fallback_used=true`.
5. Keep the user flow working.
```

The fallback is not a second brain. It is the fallback implementation of the
same checkpoint contract.

---

## 11. Template Integration Rules

Every template must use the same visual cluster entry point.

General Template:

```text
uses visual cluster for references, selected outputs, visual grammar,
continuation style, and output review
must stay subject/scene/style oriented
must not add product/listing/CTA wording unless user intent is explicit
```

E-Commerce Template:

```text
uses the same visual cluster for product/reference preservation and suite
consistency
adds E-Commerce-specific policy through the ecommerce Scenario Pack
does not own the visual cluster
does not leak commerce logic into General Template
```

Future templates:

```text
must declare visual cluster usage in the template manifest
must define context read/write policy
must not build private visual grammar engines
must pass the ownership audit before activation
```

Template manifest extension:

```text
visual_capability_policy:
  enabled: true
  required_child_modules: []
  optional_child_modules: []
  reads_project_visual_snapshot: true
  writes_project_visual_snapshot: true
  can_use_brand_memory_visuals: explicit_only
  output_review_required: false
```

---

## 12. Prompt And Provider Boundaries

PromptCompilerAgent may:

```text
consume `PromptConstraintCompiler` output
consume Brain prompt guidance
merge visual rules into final prompt text
store final prompt metadata
```

PromptCompilerAgent must not:

```text
extract visual grammar from references
decide selected output continuity rules
own project style memory
call V1/V2 prompt helpers
call providers directly
```

Generation providers may:

```text
receive final prompts and provider-safe reference files
return generated outputs
store output metadata
```

Generation providers must not:

```text
decide project visual strategy
rewrite user intent
own visual consistency logic
read ProjectContextPackage directly
```

---

## 13. Migration Plan

### Phase 0 - Documentation and conflict cleanup

1. Add this document.
2. Update document `13` delivery order.
3. Update document `24` so V1/V2 migration is now explicitly wrapped by the
   Visual Capability Cluster.
4. Update document `31` so the old V1/V2 enhanced-capability audit now points
   to cluster ownership.
5. Update document `37` so every template must declare visual cluster policy.
6. Update document `48` so Claude Code expert/provider paths are explicitly
   forbidden and checkpoint stages are the current target.
7. Update document `29` execution audit so this document is marked as a new
   future implementation spec, not yet implemented.

### Phase 1 - Cluster contracts

1. Add cluster contracts in the V3 shared capability layer.
2. Add child-module ownership metadata.
3. Add focused tests proving module IDs belong to the cluster.
4. Do not move code yet unless needed.

### Phase 2 - Cluster orchestrator

1. Add a Visual Capability Cluster orchestrator.
2. Wrap existing child modules without changing their public behavior.
3. Ensure `ScenarioRuntime` can call the cluster as one logical major module.
4. Keep old capability metadata compatible during migration.

### Phase 3 - Visual grammar profile and project snapshot

1. Add `VisualGrammarProfile`.
2. Add `ProjectVisualGrammarSnapshot`.
3. Build snapshots only from selected/confirmed project references.
4. Add negative direction handling.
5. Store the snapshot in project context and job metadata.

### Phase 4 - Visual consistency guard

1. Check continuation jobs before prompt compilation.
2. Warn or revise when the new request drifts from selected project direction.
3. Block only when hard template rules are violated.
4. Add tests for selected-output continuity and rejected-direction avoidance.

### Phase 5 - Checkpoint Brain

1. Split the current LLM Brain flow into checkpoint contracts.
2. Keep one direct LLM API path plus deterministic fallback.
3. Feed visual cluster outputs into the context and strategy checkpoints.
4. Store user-visible summaries and progress steps.
5. Ensure no Claude Code provider/expert route exists.

### Phase 6 - Prompt and review integration

1. PromptCompilerAgent consumes checkpoint guidance and cluster constraints.
2. Final prompts record visual snapshot references.
3. Post-generation review consumes output metadata and cluster review contract.
4. Project timeline receives a simple "what V3 did" summary.

### Phase 7 - Frontend display

1. Keep beginner UI image-first.
2. Show progress messages during generation, not as large explanation cards.
3. Fold advanced workflow details behind a plain-language panel.
4. Never expose cluster names, provider fields, or raw prompt internals by
   default.

---

## 14. Strong Verification Gate

When code work is done, the implementation is not accepted until this strong
verification passes.

### 14.1 Ownership audit

Run static searches and inspect every match:

```text
rg -n "VisualGrammarProfile|ProjectVisualGrammarSnapshot|VisualReferenceBindingProfile|VisualConsistencyGuard|VisualCapabilityCluster" alchemy_creative_agent_3_0/app
rg -n "visual grammar|composition|lighting|palette|camera|style consistency|reference binding|selected output" alchemy_creative_agent_3_0/app
```

Acceptance:

```text
1. Defining/owning visual enhancement logic is under `app/shared_capabilities`
   and its visual cluster children.
2. Project Mode may store and pass visual snapshots, but not compute visual
   grammar privately.
3. CentralCreativeBrain may orchestrate and consume results, but not own visual
   extraction logic.
4. PromptCompilerAgent may merge constraints, but not own visual memory.
5. Templates may declare policy, but not implement private visual engines.
```

### 14.2 V1/V2 isolation audit

Run:

```text
rg -n "custom_media_agent_2_0|custom_media_agent_1|src_skeleton\.app|ImagePromptPlan|prompt_transform|user_variables" alchemy_creative_agent_3_0/app
```

Acceptance:

```text
no V1/V2 runtime import
no V1/V2 schema dependency
no V1/V2 job API call
no V1/V2 prompt helper call
no Lab runtime state dependency
```

Provider credential reuse through explicit V3 configuration adapters remains
allowed, because it is platform configuration, not V1/V2 runtime logic.

### 14.3 Brain route audit

Run:

```text
rg -n "Claude Code|claude_code|claude-code|expert mode|expert_mode|V2 Claude|Claude orchestrator" alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/docs
```

Acceptance:

```text
1. App code has no Claude Code brain/provider/expert route.
2. Docs may mention Claude Code only as a forbidden path or historical V2
   comparison.
3. Direct LLM API provider docs do not imply Claude Code CLI integration.
4. There is one V3 Brain contract with deterministic fallback, not multiple
   competing brain systems.
```

### 14.4 Cluster dispatch audit

Run focused tests or API probes proving:

```text
1. ScenarioRuntime dispatches the visual cluster or its registered children.
2. General Template jobs receive cluster outputs.
3. E-Commerce Template jobs receive cluster outputs only inside the correct
   template/scenario path.
4. Future templates cannot bypass the cluster if visual policy is enabled.
5. A missing optional child module degrades with warnings.
6. A required child module failure blocks only the correct template job.
```

### 14.5 Project consistency audit

Run tests proving:

```text
1. Selected images update project visual snapshot.
2. Unselected candidates do not update positive visual context.
3. Rejected images become avoid directions.
4. Continue generation reads the project visual snapshot.
5. New outputs append to project history instead of replacing old outputs.
6. General Template and E-Commerce Template do not share private context
   accidentally.
7. Account/user scoping still hides other users' projects and images.
```

### 14.6 Prompt contamination audit

Run tests and dry prompt probes proving:

```text
1. General Template prompt text stays subject/scene/style oriented.
2. E-Commerce-only words such as product listing, selling point, CTA,
   marketplace, keyword, and competitor appear only when the template or user
   intent requires them.
3. No random product object is introduced by stale context.
4. Final prompt references selected project visuals when continuation requests
   require consistency.
```

### 14.7 UI audit

Run desktop and mobile browser QA proving:

```text
1. V3 stays beginner-facing and image-first.
2. Progress messages are shown during generation.
3. Advanced workflow details are folded and readable.
4. No provider, adapter, prompt compiler, capability module, job id, manifest,
   raw JSON, or cluster name appears in normal UI.
5. Project history and generated-image history remain project-scoped.
6. Image preview, delete, select, reject, continue, and save-style actions are
   clear and do not overwrite old outputs.
```

### 14.8 Required command bundle

Minimum verification after implementation:

```text
python -m pytest alchemy_creative_agent_3_0/tests -q
python -m pytest tests/test_v3_commercial_frontend_shell.py -q
python -m pytest tests/test_api_smoke.py -q
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
node --check src_skeleton/app/static/app.js
node --check src_skeleton/app/mobile_static/mobile.js
git diff --check
python "%USERPROFILE%\.codex\skills\long-running-task\scripts\validate_state.py" --project .
```

Add browser QA when frontend behavior changes.

---

## 15. Acceptance Criteria

This future code phase is complete only when:

```text
1. One V3-native Visual Capability Cluster owns reusable visual enhancement.
2. Existing V1/V2-derived enhancements are either cluster child modules or
   explicitly retired.
3. No visual enhancement logic remains scattered in CentralCreativeBrain,
   templates, Project Mode, PromptCompilerAgent, or providers as private
   ownership.
4. Direct LLM checkpoint brain is the only V3 reasoning path.
5. Claude Code expert/provider mode is not present as a current or future V3
   interface.
6. Project visual snapshots drive continuation consistency.
7. Selected outputs become positive context; unselected candidates do not.
8. Rejected outputs become avoid directions.
9. General Template remains clean from product/E-Commerce prompt contamination.
10. E-Commerce keeps its own template/scenario policy without owning the shared
    visual cluster.
11. Beginner UI remains simple, image-first, and free from engineering terms.
12. The strong verification gate in section 14 passes.
```

---

## 16. Non-Goals

This document does not require:

```text
1. A large rewrite of the V3 foundation.
2. Moving all existing files immediately.
3. Replacing ScenarioRuntime or Product API.
4. Replacing the image provider layer.
5. Building future templates.
6. Auto-writing Brand Memory.
7. Showing professional/debug workflow internals to beginner users.
8. Depending on V1/V2 code at runtime.
9. Adding Claude Code as a V3 expert brain.
```

---

## 17. Developer Handoff Prompt

When implementation begins, use this handoff:

```text
Implement document 50.

Keep V3 architecture intact. Do not rewrite Project Mode, ScenarioRuntime,
Product API, or provider storage.

Create a V3-native Visual Capability Cluster under the shared capability layer.
Treat existing shared capability modules as child modules. Add missing contracts
for VisualGrammarProfile, ProjectVisualGrammarSnapshot, visual reference
binding, consistency guard, and visual review. Make Project Mode store and pass
visual snapshots, but do not let Project Mode own visual extraction logic.

Upgrade the V3 LLM Brain into a direct multi-stage checkpoint brain. Do not add
Claude Code, V2 Claude orchestrator, or a future Claude Code expert/provider
interface. Keep deterministic fallback under the same checkpoint contract.

After code changes, run the strong verification gate from document 50 section
14 and prove all scattered visual enhancement logic is consolidated into one unified
cluster-owned module framework with child modules.
```
