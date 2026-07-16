# 101 V3 Extensible Capability Activation And Hot-Plug Visual Module Spec

> **Doc135 forward-path note:** activation selects evidence/review executors;
> it does not authorize any selected capability to compose renderer wording,
> prompt atoms, negative lists or retry text.

Status: accepted development specification. This document phase changes
governance and implementation instructions only; selective runtime execution is
not considered complete until the migration and acceptance tests in this
document are implemented.

Implementation companion: Doc102 is authoritative for file-level migration
order, feature flags, compatibility handling, test files, rollout gates, and
commit boundaries. Doc101 remains authoritative for the target contracts and
governance outcome.

## 1. Purpose

Doc101 is the current authority for deciding which reusable visual capabilities
run for a V3 job.

The goal is not to replace the Visual Capability Cluster or make Central Brain
heavy. The goal is to prevent a growing plugin library from becoming an
always-on prompt bundle.

```text
Central Brain understands the task and proposes required capabilities.
Capability Activation Planner validates and resolves that proposal.
Visual Capability Registry loads only the accepted capability modules.
Prompt, review, and retry consume the same immutable activation plan.
Inactive modules contribute nothing.
```

The system must support future scenes that do not exist in today's taxonomy.
Person, product, scene, and typography are initial examples, not a closed enum.

## 2. Authority And Compatibility

Doc101 extends:

```text
Doc24  shared capability contracts and registry
Doc37  template interface and activation gate
Doc48  V3-owned LLM checkpoint Brain
Doc50  one V3-native Visual Capability Cluster
Doc67  Central Brain and visual-module ownership boundary
Doc76  foundation versus specialized-template governance
Doc91  shared Human Realism Plugin ownership
Doc93  reference-channel ownership
Doc100 GPT Image 2 sole-renderer and bounded rerender governance
```

Doc101 is authoritative when older documents imply any of the following:

```text
every registered visual child module runs for every visual job
foundation-owned means always enabled
each plugin independently decides activation from keywords
templates name internal child modules without a shared activation plan
generic strict review may inject person, product, or scene rules unconditionally
post-generation review may activate a capability that was absent before generation
```

Doc101 does not change:

```text
Project -> Template -> Scenario Pack -> Job ownership
Visual Capability Cluster ownership of reusable visual intelligence
Central Brain ownership of semantic task reasoning
specialized-template ownership of professional deliverable maps
GPT Image 2 as the sole production final-pixel renderer
bounded retry budgets and best-reviewed-result retention
V1/V2/Lab runtime independence
```

## 3. Core Architecture

```text
Project Context + User Request + Uploaded Assets + Template Policy
  -> Asset Understanding
  -> Central Brain Task Understanding Checkpoint
       -> VisualTaskProfile
       -> CapabilityActivationIntent
  -> Capability Activation Planner
       -> manifest validation
       -> evidence validation
       -> dependency expansion
       -> conflict resolution
       -> cost and safety policy
       -> deterministic fallback when Brain is unavailable
       -> immutable CapabilityActivationPlan
  -> Visual Capability Registry
       -> execute accepted universal and optional modules only
  -> Capability Contribution Composer
       -> generation contributions
       -> review contributions
       -> retry contributions
  -> Prompt Compiler
  -> GPT Image 2
  -> Review using the same activation plan
  -> bounded retry using the same activation plan
```

### 3.1 Central Brain Role

Central Brain is the semantic activation authority. It identifies:

- what visible subjects or assets exist;
- what the user wants to preserve;
- what may change;
- whether the intended output is photographic, illustrative, rendered, graphic,
  typographic, or mixed;
- the business or creative purpose;
- which reusable capabilities appear necessary;
- confidence and supporting evidence for each conclusion.

Central Brain does not import, instantiate, or execute plugin classes. It emits
structured activation intent through a stable contract.

Before the activation checkpoint, Central Brain receives a sanitized
`CapabilityCatalogSnapshot` generated from registered manifests. The snapshot
contains capability ID, plain-language purpose, supported evidence, profiles,
dependencies, conflicts, and estimated cost, but no executable code. This is
how a newly installed plugin becomes selectable without adding a hard-coded
branch to Central Brain.

### 3.2 Activation Planner Role

The planner is the runtime enforcement layer, not a second creative brain. It:

- rejects unknown or unavailable capability IDs;
- verifies required evidence and template permission;
- adds declared dependencies;
- resolves conflicts by policy;
- applies user controls and safety restrictions;
- enforces cost and latency budgets;
- produces deterministic fallback activation when no LLM is available;
- freezes the result for one job and its retries.

### 3.3 Plugin Role

A plugin owns one reusable capability. It may analyze inputs and return
structured contributions. It must not:

- decide that it should run after execution has already begun;
- mutate global prompts or another plugin's output;
- call the generation provider directly;
- create a private retry loop;
- read another user's project or non-selected project outputs;
- embed a professional template's entire deliverable taxonomy;
- expose engineering metadata in beginner UI.

## 4. Visual Task Profile

Central Brain must produce a multi-label profile. Do not force a job into one
exclusive category.

```python
class VisualTaskProfile:
    profile_id: str
    project_id: str | None
    job_id: str
    template_id: str
    scenario_id: str
    output_medium: str
    subject_entities: list[VisualSubjectEntity]
    preservation_targets: list[PreservationTarget]
    allowed_changes: list[str]
    visual_intent_tags: list[str]
    commercial_goal_tags: list[str]
    requested_deliverable_roles: list[str]
    explicit_user_controls: dict
    unknown_requirements: list[str]
    confidence: float
    evidence: list[ActivationEvidence]
```

Subject entities are extensible records:

```python
class VisualSubjectEntity:
    entity_id: str
    entity_type: str
    role: str
    source_asset_ids: list[str]
    visible_in_target: bool
    preservation_level: str
    confidence: float
    attributes: dict
```

Initial `entity_type` examples include:

```text
person
product
scene
building
interior_space
vehicle
food
animal
brand_asset
text_layout
illustrated_character
generic_object
```

They are examples only. New plugins may introduce new entity types through
their manifests without changing Central Brain source code, provided the Brain
can emit them as open strings plus evidence.

## 5. Capability Activation Intent

Central Brain proposes, but does not directly execute:

```python
class CapabilityActivationIntent:
    intent_id: str
    task_profile_id: str
    requested_capabilities: list[RequestedCapability]
    rejected_capabilities: list[RejectedCapability]
    unresolved_signals: list[str]
    confidence: float
```

```python
class RequestedCapability:
    capability_id: str
    activation_mode: str
    reason_codes: list[str]
    evidence_ids: list[str]
    requested_profile: str | None
    confidence: float
```

Activation modes:

```text
required     explicit user or template hard requirement
recommended strong semantic/evidence match
optional    useful when budget permits
forbidden   explicit style, policy, or user exclusion
```

## 6. Capability Manifest

Every hot-pluggable visual module must register one manifest.

```python
class VisualCapabilityManifest:
    capability_id: str
    version: str
    display_name: str
    owner_layer: str
    status: str
    supported_entity_types: list[str]
    supported_output_media: list[str]
    activation_evidence_schema: list[str]
    minimum_activation_confidence: float
    dependencies: list[str]
    optional_dependencies: list[str]
    conflicts: list[str]
    compatible_templates: list[str]
    forbidden_templates: list[str]
    supported_profiles: list[str]
    contribution_stages: list[str]
    estimated_cost: CapabilityCost
    fallback_behavior: str
    audit_tags: list[str]
```

Contribution stages may include:

```text
asset_analysis
reference_policy
creative_strategy
generation_prompt
negative_prompt
provider_input_plan
post_generation_review
retry_patch
project_memory_proposal
export_validation
```

Manifest rules:

1. The manifest declares applicability; the plugin does not use hidden keyword
   activation as a second authority.
2. Template-specific configuration selects a profile, not a forked module.
3. Dependencies and conflicts must be explicit.
4. A plugin cannot claim a contribution stage that it does not implement.
5. Registry activation is denied when the installed implementation version does
   not satisfy the accepted manifest contract.

## 7. Capability Activation Plan

The planner emits one immutable plan per job:

```python
class CapabilityActivationPlan:
    plan_id: str
    project_id: str | None
    job_id: str
    task_profile_id: str
    template_id: str
    scenario_id: str
    base_capabilities: list[ActivatedCapability]
    active_capabilities: list[ActivatedCapability]
    inactive_capabilities: list[InactiveCapability]
    dependency_order: list[str]
    conflict_decisions: list[CapabilityConflictDecision]
    budget_decisions: list[CapabilityBudgetDecision]
    fallback_used: bool
    plan_version: str
    created_at: str
```

Every activated capability records:

```text
capability_id and version
selected profile
activation mode
reason codes
evidence IDs
template configuration
dependency source
confidence
```

Every inactive capability considered by the planner records a concise internal
reason such as `no_evidence`, `forbidden_by_style`, `template_not_allowed`,
`conflict_lost`, `dependency_unavailable`, or `budget_excluded`.

## 8. Activation Priority And Conflict Resolution

Priority is fixed:

```text
explicit user control
> template hard requirement or prohibition
> verified uploaded-asset evidence
> selected project reference evidence
> Central Brain semantic intent
> deterministic fallback
> generic default
```

Conflict resolution examples:

- A request for manga illustration forbids real-human skin rendering even when
  the source image contains a person.
- A product-on-model job may activate both product identity and Human Realism.
- A portrait identity reference does not activate source-style inheritance.
- A scene reference may activate scene continuity without product identity.
- A template cannot forbid a capability the user explicitly needs for safety or
  asset integrity, but it may choose a stricter profile.

The planner must support multiple simultaneous capabilities. `person`,
`product`, `scene`, and `layout` are not mutually exclusive modes.

## 9. Foundation Capability Tiers

Foundation-owned does not mean always enabled.

### 9.1 Universal Base

These capabilities may run for nearly every image job because their outputs are
domain-neutral:

```text
asset role normalization
reference-channel ownership
general visual grammar
prompt ownership and integrity
basic composition, light, color, and material reasoning
provider input preparation
generic artifact and commercial-finish review
bounded retry governance
project result and selection continuity
```

Even universal base capabilities must contribute only the clauses relevant to
their stage.

### 9.2 Evidence-Gated Shared Plugins

Examples:

```text
human realism
portrait identity
product identity
scene continuity
typography and layout
brand visual memory
architecture spatial continuity
food realism
vehicle structure
animal identity
illustrated character continuity
```

These are foundation-owned reusable plugins but are never automatically
included merely because they exist in the registry.

### 9.3 Specialized Template Capabilities

Specialized templates may add unique capabilities, profiles, role directors,
and acceptance criteria. Reusable portions should still be registered as
plugins; template-only deliverable maps remain in the Scenario Pack.

## 10. General Template Boundary

General Template provides broad, safe, low-friction visual creation.

It should:

- understand arbitrary natural-language tasks;
- use universal base capabilities;
- auto-activate evidence-backed shared plugins;
- support mixed-subject jobs;
- preserve selected project direction;
- provide similar alternatives, suite expansion, creative exploration, and
  format adaptation;
- fall back to generic visual grammar for unknown scenes.

It should not:

- contain every industry's professional deliverable map;
- guess Amazon, professional photography, social campaign, private-community,
  or brand-system outputs from weak evidence;
- turn optional shared plugins into universal prompt rules;
- promise domain-optimal output when no specialized template is selected.

General Template quality target:

```text
broadly useful, visually coherent, commercially usable, and safely extensible
```

Specialized templates own domain-optimal planning and acceptance.

## 11. Specialized Template Integration

Each template manifest extends its capability policy:

```python
class TemplateCapabilityPolicy:
    required_capabilities: list[TemplateCapabilityBinding]
    recommended_capabilities: list[TemplateCapabilityBinding]
    optional_capabilities: list[TemplateCapabilityBinding]
    forbidden_capabilities: list[str]
    profile_overrides: dict[str, str]
    activation_threshold_overrides: dict[str, float]
    deliverable_role_owner: str
    review_threshold_profile: str
```

Examples:

```text
E-Commerce Template
  requires product truth and commerce integrity
  recommends Human Realism only when a visible person is planned
  owns listing/A+/selling-point deliverable roles

Photography Template
  requires photographic direction
  activates portrait identity only with identity evidence
  activates Human Realism for real-human outputs
  owns shot list, pose, lens, and photography acceptance profiles

New Media Template
  requires platform and layout planning
  activates typography/layout when text is part of the deliverable
  owns carousel, cover, thumbnail, and crop variants

Private Community Template
  configures brand memory, campaign continuity, and conversion context
  owns its content package, not generic visual quality
```

Templates configure shared capabilities; they do not copy their logic.

## 12. Contribution Contract

Each active plugin returns a contribution package:

```python
class CapabilityContribution:
    capability_id: str
    capability_version: str
    activation_plan_id: str
    facts: dict
    prompt_additions: list[str]
    negative_additions: list[str]
    provider_input_requirements: list[dict]
    review_contract: dict
    retry_contract: dict
    project_memory_proposal: dict | None
    warnings: list[dict]
```

The composer accepts contributions only when:

- the capability is active in the frozen plan;
- the version matches the plan;
- the contribution stage is declared in the manifest;
- the contribution references no undeclared capability;
- its prompt clauses pass ownership and cross-domain leakage checks.

Hard rule:

```text
Inactive plugins contribute nothing.
Inactive plugin output is not serialized into the provider prompt, review
package, retry patch, project memory, or user-facing explanation.
```

## 13. Review And Retry Alignment

Generation, review, and retry use the same activation plan.

```text
active before generation -> may contribute generation and declared review rules
inactive before generation -> cannot add review or retry rules later
```

A post-generation detector may report new evidence, such as an unexpected
visible person or generated text. It may request a new activation decision, but
it cannot silently mutate the current plan. The allowed behavior is:

1. record the new evidence;
2. ask the Activation Planner for a versioned plan amendment;
3. validate remaining retry budget;
4. create a new GPT Image 2 candidate under the amended plan;
5. retain all previous attempts.

Plan amendments must be exceptional and auditable. They cannot create an
unbounded retry loop.

## 14. Hot-Plug Lifecycle

Hot-pluggable means a capability can be installed, enabled, disabled, upgraded,
or reused by another template without changing Central Brain, Project Mode, or
the generation provider.

Safe lifecycle:

```text
package installed
-> manifest discovered
-> schema and signature validated
-> dependency graph validated
-> capability registered disabled
-> operator or accepted template policy enables it
-> registry refresh at startup or controlled reload
-> new jobs may activate it
```

In-flight jobs keep their frozen capability versions. A hot reload must not
change an active job or its retry semantics.

Arbitrary runtime code upload from end users is forbidden. Hot plug is a
governed application-extension mechanism, not unrestricted plugin execution.

## 15. Registry Interfaces

Recommended interfaces:

```python
class VisualCapabilityPlugin(Protocol):
    def manifest(self) -> VisualCapabilityManifest: ...
    def analyze(self, context: CapabilityExecutionContext) -> CapabilityContribution: ...
    def review(self, context: CapabilityReviewContext) -> CapabilityContribution: ...
    def retry(self, context: CapabilityRetryContext) -> CapabilityContribution: ...

class VisualCapabilityRegistry:
    def register(self, plugin: VisualCapabilityPlugin) -> None: ...
    def unregister(self, capability_id: str) -> None: ...
    def resolve(self, capability_id: str, version: str | None = None) -> VisualCapabilityPlugin: ...
    def manifests(self) -> list[VisualCapabilityManifest]: ...
    def catalog_snapshot(self) -> CapabilityCatalogSnapshot: ...
    def validate_graph(self, capability_ids: list[str]) -> CapabilityGraphAudit: ...

class CapabilityActivationPlanner:
    def build(
        self,
        task_profile: VisualTaskProfile,
        intent: CapabilityActivationIntent,
        template_policy: TemplateCapabilityPolicy,
        registry: VisualCapabilityRegistry,
        user_controls: dict,
    ) -> CapabilityActivationPlan: ...
```

## 16. Deterministic Fallback

When the LLM Brain is unavailable, V3 remains usable.

Fallback may use:

- explicit template policy;
- declared upload roles;
- selected-reference roles;
- product profile;
- explicit user controls;
- conservative semantic rules.

Fallback rules must be narrow. Unknown evidence falls back to universal visual
grammar rather than activating the nearest specialized plugin.

## 17. Observability And Beginner UX

Internal audit stores:

```text
task profile
activation intent
final activation plan
manifest versions
dependency and conflict decisions
module contribution summaries
plan amendments
review and retry capability sources
```

Normal UI shows only concise outcomes such as:

```text
已识别并保留商品外观
已参考人物特征
已延续场景氛围
已按当前版式生成
```

Do not show capability IDs, manifests, dependency graphs, confidence scores,
provider internals, or engineering issue codes to beginner users.

## 18. Migration From Current Visual Cluster

Doc102 expands this section into the executable code plan. If implementation
ordering or file placement here is less specific, follow Doc102 without changing
the Doc101 target architecture.

This is an incremental refactor, not a rewrite.

Phase 1 - inventory and leakage tests:

1. Inventory every current visual child module and prompt/review contribution.
2. Classify it as universal base, evidence-gated shared plugin, or specialized
   template behavior.
3. Add product-only, scene-only, illustration-only, human-only, mixed-subject,
   and unknown-scene leakage tests.
4. Record existing person-specific clauses that leak into non-person tasks.

Phase 2 - contracts and planner:

1. Add task-profile, activation-intent, manifest, plan, and contribution schemas.
2. Add the registry manifest layer without changing provider or Project APIs.
3. Add Central Brain activation checkpoint and deterministic fallback.
4. Persist the frozen activation plan in job metadata.

Phase 3 - universal review split:

1. Extract domain-neutral composition, exposure, color, depth, artifact, and
   direct-use checks into `universal_visual_quality`.
2. Move person, face, skin, anatomy, and identity checks into person plugins.
3. Move product silhouette, label, material, and structure checks into product
   plugins.
4. Move space, landmark, background, and camera-continuity checks into scene
   plugins.
5. Move text accuracy and layout checks into typography/layout plugins.

Phase 4 - selective execution:

1. Execute only active modules in dependency order.
2. Compose only active contributions.
3. Apply the same plan to real review and retry.
4. Keep compatibility readers for historical cluster metadata.

Phase 5 - template adoption:

1. General Template adopts universal base plus evidence-gated plugins.
2. E-Commerce declares product and commerce capability profiles.
3. Future Photography, New Media, Private Community, and other templates adopt
   the same interface when their specs are accepted.

## 19. Required Tests

### 19.1 Activation

- portrait reference plus real-photo intent activates portrait identity and
  Human Realism;
- product-only reference does not activate portrait or face rules;
- scene-only reference does not receive person or product rules;
- non-human illustration does not receive Human Realism rules;
- product-on-model activates product identity and Human Realism together;
- explicit CG/anime intent disables real-human rendering while preserving
  applicable identity/style reference rules;
- unknown task uses universal base without speculative specialist activation.

### 19.2 Leakage

- inactive person plugins contribute zero face, skin, anatomy, or portrait
  clauses to product, scene, and illustration prompts;
- inactive product plugins contribute zero listing, label, selling-point, or
  product-identity clauses to unrelated prompts;
- inactive scene plugins contribute no scene-lock retry reasons;
- inactive modules do not appear in review, retry, or user summaries.

### 19.3 Registry And Hot Plug

- a new compatible plugin can register without changing Central Brain code;
- missing dependencies prevent activation with a structured reason;
- conflicts resolve according to fixed priority;
- disabling a plugin affects new jobs only;
- in-flight jobs keep frozen versions;
- a template can select a plugin profile without importing its implementation;
- invalid manifests and undeclared contribution stages are rejected.

### 19.4 Compatibility

- Project Mode and template isolation tests pass;
- General Template remains scenario-neutral;
- E-Commerce does not leak its deliverable map into General;
- existing reference-channel, Human Realism, identity, product, scene, review,
  retry, and best-result tests remain valid after migration;
- GPT Image 2 remains the sole final-pixel renderer.

## 20. Acceptance Criteria

Doc101 implementation is complete when:

1. Every reusable visual plugin has a manifest.
2. Central Brain emits a structured task profile and activation intent.
3. Activation Planner emits one frozen plan per job.
4. Only active modules execute and contribute.
5. Prompt, review, and retry use the same plan.
6. Non-person product, scene, and illustration tasks contain no person-specific
   prompt or review rules.
7. Mixed-subject tasks activate multiple compatible plugins.
8. General Template stays broad and simple.
9. Specialized templates can configure and extend capabilities without copying
   shared implementation.
10. A new governed plugin can be registered without modifying Central Brain,
    Project Mode, Product API, or Generation Router.

## 21. Final Governance Rule

```text
Central Brain decides what the task needs.
Activation Planner proves that the decision is valid and safe.
Registry supplies only the accepted plugins.
Plugins contribute only through contracts.
General Template stays broad.
Specialized templates go deep.
GPT Image 2 remains the final renderer.
```
