# 102 V3 Doc101 Runtime Migration And Capability Isolation Implementation Spec

> **Doc135 forward-path note:** the frozen plan/envelope controls execution
> scope only. New forward paths retain facts and issue evidence, then require
> a remote-Brain canonical prompt sign-off; they do not replay local module
> prompt or retry fragments.

Status: accepted implementation companion for Doc101. This document phase does
not change runtime code. Future code work must implement the phases and gates in
this document in order.

## 1. Purpose

Doc101 defines the target capability-activation architecture. Doc102 defines
exactly how to migrate the existing V3 code to that architecture without
rewriting Project Mode, Scenario Packs, Product API, the Visual Capability
Cluster, or the GPT Image 2 generation path.

The implementation target is:

```text
minimal pre-activation understanding
-> Central Brain task profile and activation intent
-> validated frozen activation plan
-> selected plugins only
-> composed generation contribution
-> GPT Image 2
-> review and retry under the same plan
```

The migration must preserve all accepted V3 behavior while eliminating
cross-domain prompt, review, and retry leakage.

## 2. Authority And Non-Negotiable Boundaries

Doc102 implements Doc101 and extends the following authorities:

```text
Doc24  existing SharedCapabilityRegistry foundation
Doc37  ProjectTemplateManifest and template activation gate
Doc48  V3LLMBrainAdapter and checkpoint reasoning
Doc50  Visual Capability Cluster ownership
Doc53  bounded retry and loop safety
Doc67  Central Brain versus visual-module ownership
Doc76  General versus specialized-template placement
Doc91  Human Realism ownership and evidence
Doc93  reference-channel ownership
Doc100 GPT Image 2 sole production renderer
Doc101 activation contracts and hot-plug governance
```

Hard boundaries:

1. Do not create a second Project, Job, Template, Scenario Pack, Product API, or
   generation-provider runtime.
2. Do not move plugin implementation into Central Brain.
3. Do not let plugins call GPT Image 2 or create retry loops.
4. Do not make V1/V2/Lab a runtime dependency.
5. Do not change account, project, or output isolation.
6. Do not migrate historical stored jobs destructively.
7. Do not expose capability engineering data in beginner UI.
8. GPT Image 2 remains the sole final-pixel renderer.

## 3. Current Code Audit

### 3.1 Runtime Order Is Reversed

Current file:

```text
alchemy_creative_agent_3_0/app/scenario_runtime/runtime.py
```

Both `plan_job()` and `generate_job()` currently run:

```text
_run_shared_capabilities()
-> _run_llm_brain(... capability_run ...)
-> run_creative_planning() or run_generation_loop()
```

`_selected_capability_ids()` decides modules through scenario, preset,
uploaded-asset, product-profile, project-context, and explicit parameter rules.
It appends `visual_capability_cluster` before the Brain runs.

Consequences:

- Brain cannot be the semantic source of activation intent;
- Visual Cluster may build domain-specific plans before semantic classification;
- the full cluster is then sent back into Brain as input;
- explicit `scenario_selection.parameters.capabilities` may act too much like a
  direct execution list.

### 3.2 Brain Contract Does Not Carry Activation Data

Current files:

```text
app/llm_brain/contracts.py
app/llm_brain/adapter.py
app/llm_brain/prompts.py
app/llm_brain/fallback.py
```

`BrainRunRequest` has project, assets, references, product profile, and current
shared-capability output. `BrainRunResult` has intent, image-set, prompt, review,
summary, and checkpoints. It does not contain:

```text
CapabilityCatalogSnapshot
VisualTaskProfile
CapabilityActivationIntent
```

`V3LLMBrainAdapter._in_general_scope()` currently limits the active Brain path
to General Template. E-Commerce and future active templates cannot use the same
semantic activation checkpoint.

Capability activation itself must never disappear when creative LLM reasoning
is disabled. In that case the deterministic activation fallback, not an empty
or all-enabled plan, becomes authoritative.

### 3.3 Registry Has Execution But No Manifest Catalog

Current files:

```text
app/shared_capabilities/base.py
app/shared_capabilities/contracts.py
app/shared_capabilities/registry.py
```

`SharedCapabilityRegistry` registers modules and runs selected module IDs in
deterministic order. It has no manifest, dependency graph, conflict policy,
profile selection, catalog snapshot, or frozen activation plan.

The existing registry must remain the execution foundation. Doc102 adds a
manifest and activation facade over it; it must not create duplicate module
instances in a parallel registry.

### 3.4 Visual Cluster Is A Monolithic Eager Builder

Current primary file:

```text
app/shared_capabilities/visual_cluster/module.py
```

`VisualCapabilityClusterModule._build_cluster()` currently constructs or calls
most of the following during one run:

```text
reference and subject continuity
identity drift and repair strategy
visual grammar and project snapshot
identity locks and human variation
Human Realism
suite and mode direction
identity hero and subject identity card
portrait bone structure and style separation
strict visual review
commercial review
retry decisions and output selection
```

Many builders return `applies=false`, but they are still coupled to one eager
flow. `_strict_visual_review_policy()` also contains universal, portrait,
human-realism, anatomy, product, scene, and mode rules in one policy.

Observed leakage to fix:

```text
product-only tasks may receive person-attractiveness and facial-feature clauses
scene-only tasks may receive person-attractiveness and facial-feature clauses
non-human illustration tasks may receive person-specific strict-review clauses
```

### 3.5 Provider Reads Raw Cluster Fields

Current file:

```text
app/generation_router/providers.py
```

The production provider reads fields such as:

```text
role_specific_generation_plan
human_photorealism_guidance
strict_visual_review_policy
identity plans and prompt additions
```

This makes field presence, rather than activation-plan membership, capable of
influencing the final provider prompt.

### 3.6 Review And Retry Use Global Issue Sets

Current files:

```text
app/shared_capabilities/visual_cluster/vision_provider.py
app/shared_capabilities/visual_cluster/vision_inspector.py
app/product_api/service.py
```

The vision provider accepts a large cross-domain issue vocabulary. Product API
collects review signals and builds retry patches from issue codes. There is no
frozen capability plan proving that a person, product, scene, or layout issue is
legal for the current job.

### 3.7 Template Manifest Has No Capability Policy

Current files:

```text
app/project_mode/templates/contracts.py
app/project_mode/templates/registry.py
```

`ProjectTemplateManifest` contains inputs, context policies, output summaries,
activation requirements, and metadata. It does not contain the Doc101
`TemplateCapabilityPolicy` contract.

## 4. Migration Strategy

Use an incremental strangler migration:

```text
Phase A: contracts and shadow plan, no prompt change
Phase B: frozen plan and selective guards, legacy metadata retained
Phase C: structured contribution composer, provider reads composed output
Phase D: review and retry isolation
Phase E: template profiles and governed hot plug
Phase F: remove legacy eager activation after parity acceptance
```

Never combine all phases into one large refactor.

## 5. Target Package Layout

Add:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/activation/
  __init__.py
  contracts.py
  catalog.py
  planner.py
  fallback.py
  template_policies.py
  composer.py
  audit.py

alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/plugins/
  __init__.py
  base.py
  universal_visual_quality.py
  human_realism.py
  portrait_identity.py
  product_identity.py
  scene_continuity.py
  typography_layout.py
  suite_direction.py
```

Important migration rule:

The first plugin adapters may delegate to existing builders in
`visual_cluster/`. Do not copy prompt lists or duplicate review logic. Move code
only when the adapter boundary is proven by tests.

## 6. Phase 0 - Baseline And Feature Flags

### 6.1 Add Configuration

File:

```text
src_skeleton/app/config.py
```

Add:

```text
v3_capability_activation_mode = legacy | shadow | enforced
v3_capability_catalog_reload_enabled = false by default
v3_capability_plan_amendment_enabled = false by default
v3_capability_shadow_audit_enabled = true in development/test
```

Default rollout value must be `legacy` until Phase 4 acceptance passes.

### 6.2 Record Baseline

Before implementation, run and record:

```text
full V3 tests
root tests
General portrait generation metadata fixture
General product-only fixture
General scene-only fixture
General non-human illustration fixture
E-Commerce product-only fixture
E-Commerce product-on-model fixture
existing retry and best-result fixtures
```

Add no visual quality claim during shadow mode.

## 7. Phase 1 - Activation Contracts

### 7.1 New Contracts

File:

```text
app/shared_capabilities/activation/contracts.py
```

Implement the Doc101 models with `V3BaseModel`:

```text
ActivationEvidence
VisualSubjectEntity
PreservationTarget
VisualTaskProfile
RequestedCapability
RejectedCapability
CapabilityActivationIntent
CapabilityCost
VisualCapabilityManifest
TemplateCapabilityBinding
TemplateCapabilityPolicy
ActivatedCapability
InactiveCapability
CapabilityConflictDecision
CapabilityBudgetDecision
CapabilityActivationPlan
CapabilityContribution
CapabilityCatalogEntry
CapabilityCatalogSnapshot
CapabilityPlanAmendment
CapabilityGraphAudit
```

Contract requirements:

- open string entity types for future plugins;
- bounded confidence values;
- stable IDs generated with existing `stable_id()`;
- JSON-safe metadata;
- no chain-of-thought or hidden reasoning text;
- plan fingerprint from job, catalog version, template policy, capability
  versions, profiles, reasons, and evidence IDs;
- frozen-by-convention model copies rather than in-place mutation;
- version fields on catalog, plan, and contribution;
- explicit source for every activation decision.

### 7.2 Extend Existing Capability Metadata

File:

```text
app/shared_capabilities/contracts.py
```

Extend `CapabilityRunResult.metadata` usage; do not break its schema. Store:

```text
pre_activation_module_ids
activation_plan_id
activation_plan_version
active_capability_ids
catalog_version
activation_mode
```

Do not add required fields to historical `CapabilityResult` records.

### 7.3 Contract Tests

Add:

```text
tests/test_v3_doc102_activation_contracts.py
```

Cover validation, serialization, fingerprints, open entity types, invalid
confidence, duplicate IDs, undeclared stages, and safe metadata.

Gate: no production behavior changes.

## 8. Phase 2 - Manifest Catalog Over Existing Registry

### 8.1 Preserve One Execution Registry

Files:

```text
app/shared_capabilities/registry.py
app/shared_capabilities/activation/catalog.py
app/shared_capabilities/visual_cluster/plugins/base.py
```

Implement `VisualCapabilityRegistry` as a manifest/catalog facade over the
existing `SharedCapabilityRegistry` and existing Visual Cluster plugin
instances.

Do not create two live instances of the same module.

Required APIs:

```python
register_manifest(manifest, executor_ref)
unregister_manifest(capability_id)
manifest(capability_id, version=None)
manifests(enabled_only=True)
catalog_snapshot(template_id, scenario_id)
validate_graph(capability_ids)
resolve_executor(capability_id, version)
```

### 8.2 Initial Manifest Inventory

Register these logical capabilities first:

| Capability ID | Initial owner/adapter | Tier |
| --- | --- | --- |
| `asset_understanding` | `AssetRoleAnalyzer` | pre-activation base |
| `reference_inventory` | asset binding plus project references | pre-activation base |
| `project_context_digest` | existing context/history helpers | pre-activation base |
| `reference_channel_policy` | `ReferenceChannelPolicyModule` | universal evidence-gated |
| `visual_grammar` | existing grammar/profile builders | universal base |
| `universal_visual_quality` | extracted strict-review neutral rules | universal base |
| `human_realism` | `HumanPhotorealismLayer` | evidence-gated plugin |
| `portrait_identity` | portrait/subject-continuity adapters | evidence-gated plugin |
| `product_identity` | existing product locks plus new adapter | evidence-gated plugin |
| `scene_continuity` | scene advanced controls plus new adapter | evidence-gated plugin |
| `typography_layout` | layout/text integrity adapter | evidence-gated plugin |
| `suite_direction` | General Suite/Mode directors | count/mode-gated plugin |
| `commercial_quality` | `CommercialQualityClosureReviewer` | universal base with profiles |

These IDs are initial catalog entries, not a closed taxonomy.

### 8.3 Manifest Rules

- Universal base still declares contribution stages.
- Human Realism cannot activate from `photo`, `photography`, `照片`, or `摄影`
  alone.
- Portrait identity requires a visible/person target plus identity evidence.
- Product identity may activate from template policy, product intent, product
  reference role, or verified product entity.
- Scene continuity requires scene preservation intent or scene reference.
- Typography/layout requires target text, layout, poster, carousel, or explicit
  composition evidence.
- Suite direction requires requested count greater than one or an explicit
  continuation mode.

### 8.4 Registry Tests

Add:

```text
tests/test_v3_doc102_capability_catalog.py
tests/test_v3_doc102_hot_plug_registry.py
```

Test registration, duplicate version handling, disabled manifests, dependency
cycles, conflicts, catalog snapshots, executor reuse, controlled reload, and
in-flight version pinning.

Gate: catalog exists; legacy execution remains unchanged.

## 9. Phase 3 - Template Capability Policy

### 9.1 Extend Manifest Contract

File:

```text
app/project_mode/templates/contracts.py
```

Add:

```python
capability_policy: TemplateCapabilityPolicy
```

Provide a compatibility default so historical/custom test manifests still
validate.

Include policy summary in `to_template_card().metadata`, but do not expose raw
capability engineering fields in normal UI payloads. Debug/admin metadata may
contain the full policy.

### 9.2 Update Default Manifests

File:

```text
app/project_mode/templates/registry.py
```

General Template:

```text
required: universal_visual_quality, visual_grammar, commercial_quality
recommended: reference_channel_policy, suite_direction
optional by evidence: human_realism, portrait_identity, product_identity,
scene_continuity, typography_layout
deliverable role owner: general_template
profiles: broad/balanced
```

E-Commerce Template:

```text
required: universal_visual_quality, visual_grammar, commercial_quality
required specialized direction: ecommerce Scenario Pack
recommended: product_identity
human_realism only with verified visible-person evidence
scene and typography capabilities only with corresponding role/evidence
deliverable role owner: ecommerce Scenario Pack
profiles: ecommerce/commercial_strict where relevant
```

`product_identity` uses different evidence profiles:

```text
reference_truth: an uploaded/selected product reference exists and real product
appearance may be preserved

described_concept: text-only product intent exists; no claim is made that V3 is
preserving a real unseen product
```

Future placeholder templates:

```text
policy may be declared for documentation
no capability may execute while template status is not active
```

### 9.3 Direct API Compatibility

Add:

```text
app/shared_capabilities/activation/template_policies.py
```

This resolver supplies accepted defaults for non-Project `/jobs` compatibility
paths. Do not trust a user-provided raw policy object.

`scenario_selection.parameters.capabilities` becomes an activation hint. It is
never a direct executor list after enforced mode.

### 9.4 Tests

Add:

```text
tests/test_v3_doc102_template_capability_policy.py
```

Cover General, E-Commerce, placeholders, custom manifests, direct API defaults,
locked template behavior, malicious capability hints, and no private plugin
imports from templates.

## 10. Phase 4 - Brain Task Profile And Activation Intent

### 10.1 Extend Brain Contracts

File:

```text
app/llm_brain/contracts.py
```

Extend `BrainRunRequest`:

```text
capability_catalog
pre_activation_capabilities
template_capability_policy
```

Extend `BrainRunResult`:

```text
visual_task_profile
capability_activation_intent
```

`safe_metadata()` must include these structured results but never raw hidden
reasoning.

### 10.2 Update Remote Prompt Contract

File:

```text
app/llm_brain/prompts.py
```

Add a checkpoint:

```text
task_profile_and_capability_activation
```

The remote model receives only the sanitized catalog snapshot. Require JSON
keys matching the new contracts. Instruct the Brain to:

- classify multiple simultaneous entities;
- attach evidence IDs and confidence;
- choose only catalog capability IDs;
- keep unknown requirements explicit;
- distinguish real people from non-human illustration;
- distinguish product, scene, layout, and mixed-subject needs;
- avoid guessing professional deliverable maps outside template policy.

### 10.3 Deterministic Fallback

File:

```text
app/llm_brain/fallback.py
```

Add a narrow fallback profile builder using:

```text
template policy
declared upload/reference roles
product profile
project-selected references
explicit user controls
positive semantic signals
stylized exclusions
```

Unknown input activates universal base only.

When `V3_LLM_BRAIN_ENABLED=false`, reasoning depth is off, the remote provider
is unavailable, or the template chooses deterministic reasoning, this fallback
must still produce a valid task profile and activation intent. A skipped
creative-enrichment result is not permission to skip capability governance.

Do not reuse the current full visual cluster as the source for activation;
activation occurs before the full cluster.

### 10.4 Expand Brain Scope Safely

File:

```text
app/llm_brain/adapter.py
```

Replace `_in_general_scope()` with policy-based eligibility:

```text
active template/scenario
template capability policy allows Brain activation
locked/placeholder templates remain blocked before Brain
```

General and E-Commerce use the same Brain adapter. Template policy and Scenario
Pack still own vertical behavior.

### 10.5 Merge And Validation

Remote output is parsed into Pydantic contracts. Unknown plugin IDs remain in
audit as rejected proposals; the planner does not execute them.

Tests:

```text
tests/test_v3_doc102_brain_activation_checkpoint.py
tests/test_v3_doc102_brain_fallback_activation.py
```

Gate: Brain and fallback produce valid activation intent for all active
templates; no plugin execution changes yet.

## 11. Phase 5 - ScenarioRuntime Reordering And Frozen Plan

### 11.1 Introduce A Preparation Result

Add to:

```text
app/scenario_runtime/contracts.py
```

```python
class CapabilityPreparationResult:
    pre_activation_run: CapabilityRunResult | None
    brain_result: BrainRunResult
    activation_plan: CapabilityActivationPlan
    active_capability_run: CapabilityRunResult | None
    combined_capability_run: CapabilityRunResult | None
```

### 11.2 Refactor Duplicate Plan/Generate Flow

File:

```text
app/scenario_runtime/runtime.py
```

Add:

```text
_run_pre_activation_capabilities()
_build_capability_catalog_snapshot()
_run_activation_brain()
_resolve_template_capability_policy()
_build_activation_plan()
_run_active_capabilities()
_combine_capability_runs()
_prepare_capability_execution()
```

Both `plan_job()` and `generate_job()` call the same preparation method.

New enforced order:

```text
resolve Scenario Pack and template gate
-> run minimal pre-activation modules
-> build sanitized catalog snapshot
-> run Brain/fallback task profile and activation intent
-> validate template policy
-> build and freeze activation plan
-> execute active modules in dependency order
-> pass combined result, Brain, and frozen plan to planning/generation
```

### 11.3 Minimal Pre-Activation Modules

Allowed:

```text
asset role analysis
reference inventory and declared role normalization
project context digest
template/scenario policy resolution
basic product profile presence
explicit user controls
```

Forbidden before activation:

```text
Human Realism prompt rules
portrait identity prompt rules
product identity prompt rules
scene lock prompt rules
typography prompt rules
domain-specific review/retry rules
suite role expansion beyond explicit template/mode metadata
```

### 11.4 Deprecate `_selected_capability_ids()`

Keep a compatibility helper in legacy mode. In shadow/enforced modes:

- split it into pre-activation base selection and plan-driven active selection;
- explicit capability parameters are hints validated by the planner;
- Visual Cluster is selected only when the frozen plan contains visual
  capabilities.

### 11.5 Persistence

Persist in runtime/result metadata:

```text
visual_task_profile
capability_activation_intent
capability_activation_plan
capability_activation_plan_id
capability_catalog_version
capability_activation_mode
```

Store the full plan in internal job metadata. Status APIs expose only a safe
summary unless debug/admin access is explicit.

Update Product API `_project_mode_status_metadata()` allowed internal keys as
needed, but do not send raw manifests or dependency graphs to normal frontend.

### 11.6 Failure Semantics

- Missing required plugin or dependency blocks before generation.
- Missing recommended/optional plugin degrades with structured warning.
- Brain failure uses deterministic fallback.
- Planner schema or graph failure blocks in enforced mode.
- Shadow-plan failure never changes legacy output but is recorded.

Tests:

```text
tests/test_v3_doc102_runtime_activation_order.py
tests/test_v3_doc102_activation_failure_semantics.py
```

Gate: runtime order and persistence pass in shadow mode without changing
provider prompts.

## 12. Phase 6 - Planner And Conflict Resolution

Files:

```text
app/shared_capabilities/activation/planner.py
app/shared_capabilities/activation/fallback.py
app/shared_capabilities/activation/audit.py
```

Planner algorithm:

1. Start with template required capabilities.
2. Apply explicit user prohibitions and controls.
3. Validate Brain requested capabilities against catalog.
4. Validate evidence and confidence thresholds.
5. Add dependencies recursively.
6. Apply template forbidden capabilities.
7. Resolve conflicts using Doc101 priority.
8. Apply budget and latency limits to optional capabilities.
9. Topologically sort active capabilities.
10. Record every accepted and rejected decision.
11. Freeze plan ID, versions, profiles, evidence, and fingerprint.

Hard rules:

- no unknown capability executes;
- no dependency cycle executes;
- a forbidden stylized-human conflict disables Human Realism but may keep
  portrait/style reference handling when valid;
- product-on-model may activate product identity and Human Realism together;
- user-selected strong identity evidence outranks generic aesthetic hints;
- plugin activation cannot change final renderer;
- a retry reuses the frozen plan unless one audited amendment is approved.

Tests:

```text
tests/test_v3_doc102_activation_planner.py
```

Include precedence, mixed subjects, dependencies, conflicts, budget exclusion,
unknown capabilities, deterministic order, and stable fingerprints.

## 13. Phase 7 - Selective Visual Cluster Execution

### 13.1 Add Plan Accessors

File:

```text
app/shared_capabilities/visual_cluster/module.py
```

Add helpers:

```text
_activation_plan(capability_input)
_capability_active(plan, capability_id)
_capability_profile(plan, capability_id)
_inactive_result(capability_id, reason)
```

In `legacy` mode, preserve current behavior. In `shadow` mode, compute but do
not gate. In `enforced` mode, gate all evidence-specific builders.

### 13.2 Guard Existing Builders Before Moving Code

First migration pass:

- Human Realism build/review only when `human_realism` is active.
- portrait identity, subject continuity, identity drift, adaptive reference,
  and repair strategy only when `portrait_identity` is active;
- product identity locks/review only when `product_identity` is active;
- scene continuity only when `scene_continuity` is active;
- layout/text rules only when `typography_layout` is active;
- suite/mode director only when `suite_direction` is active;
- universal grammar and quality remain active according to plan.

Create non-applicable contract shells only where existing schemas require them.
Do not execute the underlying builder merely to obtain an inactive shell.

### 13.3 Split Strict Review

Extract from `_strict_visual_review_policy()`:

```text
universal_visual_quality.py
  composition, exposure, color, contrast, depth, resolution, artifacts,
  direct-use finish

human_realism.py
  skin, face realism, anatomy, age, expression, AI-beauty artifacts

portrait_identity.py
  same-person identity, bone structure, feature relationships, style boundary

product_identity.py
  silhouette, label, pattern, material, structure, generic replacement

scene_continuity.py
  landmark, space, background, camera continuity

typography_layout.py
  text accuracy, reserved regions, hierarchy, crop/layout checks
```

Universal review must contain no person, face, skin, product, marketplace,
scene-lock, or typography-specific clause.

### 13.4 Human Realism Refactor

File:

```text
app/shared_capabilities/visual_cluster/human_photorealism.py
```

Split current behavior into:

```text
collect_activation_evidence(...)
build_guidance(active_profile, verified_evidence, ...)
review(active_review_contract, ...)
```

Current `_activation()` becomes a compatibility evidence collector during
migration. It must not be the enforced activation authority.

Generic words `photo`, `photography`, `照片`, and `摄影` cannot independently
produce verified human evidence.

### 13.5 Product And Scene Adapters

Do not invent narrow category rules. Product and scene plugins expose generic
orthogonal variables:

```text
product: geometry, silhouette, material, color, label, pattern, proportion,
structural parts, allowed context changes

scene: spatial layout, landmarks, background identity, depth, camera relation,
light/style ownership, allowed environmental changes
```

Vertical E-Commerce or future specialized templates select profiles and add
deliverable roles without copying these shared implementations.

Tests:

```text
tests/test_v3_doc102_selective_visual_execution.py
tests/test_v3_doc102_cross_domain_leakage.py
```

Gate: active child IDs, executed builders, prompt contributions, review issue
codes, and retry sources match the frozen plan.

## 14. Phase 8 - Capability Contribution Composer

### 14.1 Composer

File:

```text
app/shared_capabilities/activation/composer.py
```

Compose `CapabilityContribution` objects in activation dependency order.

Validate:

- capability/version is active in the plan;
- contribution stages are declared by manifest;
- no undeclared dependency is referenced;
- duplicate prompt clauses are removed without deleting user text;
- stage budgets are enforced;
- contribution provenance is retained internally;
- domain leakage checks pass.

Output:

```text
ComposedVisualContribution
  prompt_additions
  negative_additions
  provider_input_requirements
  review_contracts
  retry_contracts
  memory_proposals
  active_capability_ids
  activation_plan_id
```

### 14.2 Visual Cluster Result

Extend existing cluster contracts without removing historical fields:

```text
capability_activation_plan_summary
capability_contributions
composed_visual_contribution
```

Historical fields remain readable during migration, but new enforced jobs use
the composed contribution as authority.

### 14.3 Prompt Constraints

Update `VisualCapabilityClusterModule._constraints()` so prompt/evaluation
constraints carry the plan ID and composed contribution, not an unconditional
dump of every domain plan.

Tests:

```text
tests/test_v3_doc102_capability_contribution_composer.py
```

Gate: exact prompt ownership and inactive-plugin zero-contribution tests pass.

## 15. Phase 9 - Provider Consumption

File:

```text
app/generation_router/providers.py
```

Add:

```text
_composed_visual_contribution(request)
_activation_plan_summary(request)
_active_capability(request, capability_id)
```

Provider behavior:

1. For enforced jobs with a valid plan, read only composed generation
   contribution and provider input requirements.
2. Do not scan raw Human Realism, strict-review, identity, product, scene, or
   layout fields when their capability is inactive.
3. Keep a legacy read path only for jobs without an activation plan.
4. Record plan ID and active capability IDs in provider audit metadata.
5. Never allow a plugin to alter provider selection or model; Doc100 remains
   authoritative.

Add provider prompt tests asserting:

```text
product-only prompt contains no face/skin/person-attractiveness rules
scene-only prompt contains no person or product rules
illustration prompt contains no Human Realism rules
product-on-model contains product and human rules
portrait contains identity and Human Realism when evidence supports both
layout task contains layout rules only when activated
```

Test file:

```text
tests/test_v3_doc102_provider_contribution_isolation.py
```

## 16. Phase 10 - Review And Retry Alignment

### 16.1 Vision Review Contract

Files:

```text
app/shared_capabilities/visual_cluster/vision_provider.py
app/shared_capabilities/visual_cluster/vision_inspector.py
```

Build the remote/local review request from:

```text
universal issue codes
+ active capability review issue codes
```

Do not send the complete global issue vocabulary for every job.

Build review score dimensions the same way:

```text
universal score dimensions
+ score dimensions declared by active capability review contracts
```

Do not require identity, face, human-realism, product, scene, or typography
scores when the owning capability is inactive. Commercial quality aggregation
must treat those dimensions as not applicable rather than zero.

Every inspection records:

```text
activation_plan_id
active_capability_ids
review_capability_sources
ignored_out_of_scope_issue_codes
```

If a provider returns an out-of-scope domain code, retain it in internal audit
but do not let it trigger retry or lower a domain score that does not apply.

### 16.2 Product API Retry Filter

File:

```text
app/product_api/service.py
```

Before `_visual_retry_signal()` returns issue codes:

1. load the frozen activation plan;
2. map each issue code to its owning capability;
3. keep universal codes plus active capability codes;
4. discard and audit inactive capability codes;
5. compose retry patch only from active retry contracts;
6. preserve Doc53 budgets and same-issue stop rules;
7. preserve Doc100 GPT Image 2 rerender and best-result closure.

Add:

```text
_activation_plan_from_result()
_filter_review_issues_by_activation_plan()
_compose_retry_patch_from_active_capabilities()
```

### 16.3 Plan Amendments

Do not enable amendments in the first enforced release.

Later, when `v3_capability_plan_amendment_enabled` is true, allow at most one
amendment inside the existing quality retry budget when post-generation evidence
reveals a genuinely new visible entity. Amendment flow:

```text
new evidence
-> planner validates manifest and remaining budget
-> versioned CapabilityPlanAmendment
-> new whole-image GPT Image 2 candidate
-> append-only review history
```

No amendment may reset retry counters or repeat the same issue loop.

Tests:

```text
tests/test_v3_doc102_review_retry_alignment.py
tests/test_v3_doc102_plan_amendment_safety.py
```

## 17. Phase 11 - Project And API Persistence

Files:

```text
app/product_api/contracts.py
app/product_api/service.py
app/project_mode/contracts.py
app/project_mode/service.py
```

Persistence rules:

- each new job stores the frozen plan internally;
- retries reference the same plan ID or explicit amendment ID;
- project timeline receives a beginner-facing summary only;
- selected outputs retain the plan ID for audit, not as Brand Memory content;
- Brand Memory is not updated automatically;
- account and project isolation are unchanged;
- deletion/archive behavior remains unchanged.

Normal UI may show friendly summaries such as:

```text
kept product appearance
used the person reference
continued the scene direction
prepared the requested layout
```

Do not expose manifests, confidence, graph, dependency, issue ownership, or
plugin version in normal UI.

## 18. Phase 12 - Historical Compatibility

### 18.1 Existing Jobs And Projects

Historical records without `capability_activation_plan_id` remain readable and
continue to use legacy metadata readers. Do not rewrite stored JSON files.

### 18.2 New Jobs

In `enforced` mode every new real or mock V3 job must have a frozen plan before
generation. Missing plan is an internal error, not permission to run every
plugin.

### 18.3 In-Flight Jobs During Deployment

Jobs created before activation enforcement retain legacy behavior. Jobs created
after deployment use the new plan. Do not switch an in-flight job halfway.

### 18.4 Compatibility Removal Gate

Remove legacy raw-cluster prompt consumption only after:

- two complete releases pass;
- no active jobs require the old path;
- production metadata audit confirms plan presence;
- General and E-Commerce regressions pass;
- rollback artifacts are retained.

## 19. Phase 13 - Rollout

### 19.1 Legacy Mode

Current runtime only. New contracts and catalog may exist but do not affect
execution.

### 19.2 Shadow Mode

For every job:

- run current legacy path;
- compute task profile, activation intent, and plan;
- do not change prompt, review, retry, or output;
- record comparison audit.

Required shadow comparisons:

```text
legacy module IDs versus proposed active capabilities
legacy prompt clauses versus composed clauses
legacy review codes versus allowed review codes
legacy retry codes versus allowed retry codes
latency and token overhead
```

### 19.3 Enforced Test Mode

Enable for tests and local development after shadow fixtures pass.

### 19.4 Enforced Production Mode

Enable only after all acceptance gates pass. Keep one operator-controlled
rollback to legacy for newly created jobs during the first release. Rollback
must not mutate existing project data or re-run completed jobs.

## 20. Required Test Matrix

### 20.1 Core Scene Matrix

| Fixture | Required active capabilities | Forbidden contributions |
| --- | --- | --- |
| portrait with identity reference | portrait identity, Human Realism, universal quality | product/listing rules |
| real person without identity reference | Human Realism, universal quality | same-person hard lock |
| product-only reference | product identity, universal quality | face, skin, portrait rules |
| product-on-model | product identity, Human Realism, universal quality | unrelated scene lock |
| scene/landscape reference | scene continuity, universal quality | face and product rules |
| non-human illustration | visual grammar, universal quality | Human Realism and portrait rules |
| poster with text/layout | typography/layout, universal quality | person/product rules unless separately evidenced |
| mixed person+product+scene | all three evidenced plugins | unrequested layout rules |
| unknown scene | universal base only | speculative specialist rules |

### 20.2 Four General Modes

Run every applicable fixture under:

```text
selection candidates
suite expansion
creative exploration
format/layout adaptation
```

Mode changes role direction; it does not activate unrelated subject plugins.

### 20.3 Template Matrix

Run General and E-Commerce for:

```text
text only
one uploaded reference
multiple mixed references
selected prior output
negative feedback
manual advanced reference controls
LLM available
LLM unavailable fallback
```

Future placeholder templates must remain non-executable.

### 20.4 Review/Retry Matrix

Inject:

```text
universal artifact issue
human realism issue on human job
human issue on product-only job
product drift on product job
product drift on portrait-only job
scene drift with and without scene capability
out-of-scope provider issue code
same issue repeated
retry budget exhausted
```

Only in-scope issues may trigger retry.

## 21. Test Commands

Focused sequence:

```powershell
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_activation_contracts.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_capability_catalog.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_activation_planner.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_brain_activation_checkpoint.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_runtime_activation_order.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_cross_domain_leakage.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_provider_contribution_isolation.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc102_review_retry_alignment.py -q
```

Regression sequence:

```powershell
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_project_mode.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_llm_brain_adapter.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_provider_output_production.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_visual_auto_retry.py -q
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_ecommerce_doc26_scenario_pack.py -q
python -m pytest alchemy_creative_agent_3_0/tests -q
python -m pytest -q
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests src_skeleton/app
node --check src_skeleton/app/static/app.js
node --check src_skeleton/app/mobile_static/mobile.js
git diff --check
```

## 22. Per-Phase Audit Checklist

After every phase:

1. Confirm no V1/V2/Lab runtime import.
2. Confirm no provider call from plugin code.
3. Confirm no plugin-specific retry loop.
4. Confirm Project/Template/Scenario/Job boundaries remain intact.
5. Confirm inactive plugins add zero prompt, review, retry, and memory content.
6. Confirm full user prompt remains lossless.
7. Confirm GPT Image 2 remains the sole renderer.
8. Confirm General stays scenario-neutral.
9. Confirm E-Commerce owns its professional deliverable map.
10. Confirm beginner UI receives no engineering fields.
11. Confirm historical jobs still load.
12. Confirm account isolation and deletion semantics are unchanged.

## 23. Stop And Rollback Conditions

Stop the phase and return to the last passing commit when:

- General or E-Commerce jobs lose existing outputs;
- project history or selected references no longer load;
- provider prompt drops user-owned positive instructions;
- a required plugin silently fails open;
- inactive capability leakage remains in enforced mode;
- retry counters reset after plan amendment;
- provider routing changes away from GPT Image 2;
- account/project isolation changes;
- full V3 or root regression fails for an objective-related reason.

Do not mask a planner failure by enabling every plugin.

## 24. Implementation Completion Criteria

Doc102 is complete only when:

1. ScenarioRuntime runs minimal pre-activation understanding before Brain.
2. Brain/fallback emits `VisualTaskProfile` and
   `CapabilityActivationIntent` for every active template.
3. Template policies and manifest catalog are implemented.
4. Planner freezes one valid plan per new job.
5. Only active plugins execute.
6. Provider consumes only the composed active contribution for planned jobs.
7. Review and retry use the same plan and reject out-of-scope issue codes.
8. Person rules no longer leak into product, scene, or illustration tasks.
9. Mixed-subject tasks activate multiple compatible plugins.
10. General remains broad and specialized templates remain deep.
11. Hot-plug registration does not require Central Brain source changes.
12. Historical jobs remain readable without destructive migration.
13. Focused, full V3, root, compile, frontend syntax, and diff checks pass.
14. Shadow audit and enforced acceptance matrices are recorded.

## 25. Recommended Commit Boundaries

Use small reversible commits:

```text
1. contracts and feature flags
2. catalog and manifest inventory
3. template capability policies
4. Brain activation checkpoint and fallback
5. ScenarioRuntime shadow-plan ordering
6. Activation Planner enforcement
7. selective Visual Cluster guards
8. strict-review domain split
9. contribution composer and provider consumption
10. review/retry alignment
11. persistence and compatibility cleanup
12. enforced rollout and final audit
```

Each commit must pass its focused tests. Do not defer all verification to the
last commit.

## 26. Final Implementation Rule

```text
Understand first.
Plan capabilities once.
Freeze the plan.
Execute only what is active.
Compose contributions through contracts.
Review and retry under the same plan.
Keep General broad.
Let specialized templates go deep.
Keep GPT Image 2 as the final renderer.
```
