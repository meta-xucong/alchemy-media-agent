# 17 Scenario Pack Platform and Modular Specialization Extension

This document defines the additive framework required to turn the completed Alchemy Creative Agent 3.x foundation into a registry-driven, modular specialization platform.

It is written to be implemented **after the existing V3 foundation and generation-loop contracts are complete and accepted**.

It does not replace, rename, or fork the architecture defined in the existing documents.

It extends that architecture so the V3 product can expose a general creative experience and a growing set of removable, versioned specialization packs such as:

```text
General Creative
E-Commerce
New Media Marketing
Private Community Operations
AI Manga Drama
Brand IP Operations
Future Specialization Packs
```

The implementation goal is:

```text
one V3 product entry
→ one registry-driven scenario hub
→ one shared V3 creative runtime
→ many modular specialization packs
```

The system must still behave as one coherent Alchemy Creative Agent product.

## Current-Stage Boundary

This document must be interpreted with the following boundary throughout:

```text
current stage =
  build the Scenario Pack extension framework
  build the V3 / 3.0 home UI inside the existing product shell
  make General Creative the only fully usable scenario card
  show exactly five first-screen scenario cards:
    General Creative / 通用创作
    E-Commerce / 电商特调
    New Media Marketing / 新媒体营销
    Private Community Operations / 私域社群运营
    Brand IP Operations / 品牌 IP 运营

current stage does NOT =
  implement detailed e-commerce tuning
  implement detailed new-media tuning
  implement detailed private-community tuning
  implement detailed brand-IP operation tuning
  implement separate vertical-agent product workflows
```

The V3 home may display placeholder cards for future specialization packs, but
only General Creative is executable in this stage. Placeholder cards must not
open complex forms, call pack-owned APIs, run pack-owned agents, or introduce
pack-specific generation/evaluation behavior.

This boundary is non-negotiable. Any later implementation prompt derived from
this document must preserve it.

The first-screen specialization cards are product orientation only. In this
stage, `ecommerce`, `new_media_marketing`,
`private_community_operations`, and `brand_ip_operations` are manifest-backed
placeholder cards. They may display a name, short description, typical use
cases, and a "coming later" state. They must not define complete forms,
pack-owned agents, pack-owned APIs, or pack-owned generation strategies.

---

## 1. Document Status and Compatibility

### 1.1 This Is an Additive Companion Specification

This document is a companion to:

```text
00_ROOT_RULES.md
02_SYSTEM_ARCHITECTURE.md
03_AGENT_AND_MODULE_SPEC.md
07_SCHEMA_CONTRACTS.md
09_RULES_AND_DEFAULTS.md
10_BRAND_MEMORY_SPEC.md
11_EVALUATION_AND_REFINEMENT_SPEC.md
12_PROVIDER_INTERFACES.md
13_STEP_BY_STEP_DELIVERY_PLAN.md
15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
```

It fills the implementation gap between:

```text
reserved vertical-agent extensibility
```

and:

```text
a complete user-facing, registry-driven, plug-and-play specialization platform
```

### 1.2 Existing Contracts Remain Authoritative

This document must not be interpreted as permission to break any frozen V3 contract.

Precedence:

```text
1. 00_ROOT_RULES.md
2. frozen V3 core schema and provider contracts
3. existing Central Creative Brain pipeline behavior
4. this additive scenario-pack specification
5. individual future specialization-pack specifications
```

If an individual specialization pack conflicts with a V3 core invariant, the V3 core invariant wins.

### 1.3 No Existing Version Meaning Is Changed

This document does not redefine the meaning of V3.0, V3.1, V3.2, or any later delivery wave already recorded in the repository.

The work defined here should be treated as a **post-foundation platform extension**.

For this stage, "post-foundation platform extension" means the framework and
V3 home UI only. It does not mean implementing every vertical pack listed by the
catalog.

To avoid version-number conflicts, this document uses extension phases:

```text
E0, E1, E2, E3, E4, E5
```

These are implementation phases inside this extension only. They are not product-version replacements.

### 1.4 Baseline Assumption

Before implementation begins, the current accepted V3 baseline must already provide:

```text
CentralCreativeBrain / Creative Core
CreativeJob → CommercialAssetPack pipeline
VerticalAgentRegistry
DefaultCommercialPack
V3-owned schemas
V3-owned provider interfaces
brand-memory flow
generation / evaluation / refinement flow
V3 API boundary
V3 app-shell boundary
baseline tests and golden cases
```

This extension must not be used to hide unfinished core behavior inside scenario packs.

---

## 2. Non-Negotiable Extension Rules

### 2.1 One Runtime, Not One Runtime Per Scenario

Every scenario pack must use the existing V3 pipeline.

Correct:

```text
Scenario Pack
→ structured specialization context
→ existing VerticalAgentPack extension contract
→ existing Central Creative Brain
→ existing agents / providers / evaluation / asset pack
```

Incorrect:

```text
E-Commerce UI
→ separate e-commerce pipeline

AI Manga UI
→ separate manga pipeline

Brand IP UI
→ separate IP pipeline
```

Scenario packs extend V3. They do not create parallel V3 products.

### 2.2 General Creative Must Preserve the Existing Baseline

The General Creative pack is the regression control for the entire platform.

It must:

```text
use DefaultCommercialPack
preserve current V3 defaults
preserve current agent order
preserve current provider routing behavior
preserve current evaluation behavior
preserve current asset packaging behavior
```

Adding the scenario platform must not change General Creative output when the same input, configuration, provider availability, and brand memory are used.

### 2.3 No Scenario Logic Inside Core Agents

Core agents must not accumulate branches such as:

```python
if scenario_pack == "ecommerce":
    ...
elif scenario_pack == "new_media":
    ...
elif scenario_pack == "brand_ip":
    ...
```

Industry and channel specialization must live inside registered scenario packs and capability modules.

### 2.4 No Direct Provider Calls From Scenario Packs

A scenario pack must not call image, scoring, rendering, memory, or workflow providers directly.

Correct:

```text
Scenario Pack
→ refines GenerationPlan / evaluation policy / conditioning requirements
→ GenerationRouterAgent
→ V3 provider interface
→ provider adapter
```

Incorrect:

```text
Scenario Pack
→ direct Flux / GPT Image / ComfyUI / ImageReward call
```

### 2.5 No Raw Prompt-Patch Architecture

A scenario pack must not be implemented primarily as an unstructured `system_prompt_patch` string.

Specialization must be expressed through structured rules and V3 schemas:

```text
CommercialBrief refinements
CreativePlan refinements
SeriesPlan refinements
LayoutPlan refinements
PromptCompilationResult refinements
GenerationPlan hints where supported
Evaluation policy refinements
CommercialAssetPack rules where supported
```

The PromptCompiler remains responsible for producing provider-ready prompts.

### 2.6 Internal APIs Must Be Typed and Serializable

The first implementation should use in-process Python interfaces and Pydantic models.

All request and result objects must remain JSON-serializable so a future sidecar or remote module can implement the same contract without changing product logic.

An event bus, plugin microservice mesh, or distributed workflow system is not required for the first implementation.

### 2.7 UI Must Be Registry-Driven

The scenario-card list must not be permanently hard-coded into the page.

The UI should render cards from validated scenario manifests returned by the V3 API.

Adding a new active scenario pack should require:

```text
new pack directory
new manifest
new implementation or policy modules
new tests
registry activation
```

It should not require editing the main card grid or Central Creative Brain.

### 2.8 Scenario Packs Must Be Removable

Disabling or removing one pack must not break:

```text
General Creative
other scenario packs
existing historical job records
core tests
provider tests
brand-memory records
```

### 2.9 Every Job Must Pin Its Scenario Versions

A job must record:

```text
scenario pack id
scenario pack version
selected mode id
capability-module ids and versions
bound vertical-agent pack
policy checksum
selection source
fallback events
```

A running job must not switch to a newly deployed pack version mid-run.

### 2.10 No Arbitrary Third-Party Code Loading in the First Pass

The first scenario platform should load only trusted, V3-owned packages from controlled registry configuration.

Do not load arbitrary Python entrypoints, remote JavaScript, uploaded archives, or user-provided code from a manifest.

A future external plugin marketplace would require a separate sandbox, signature, permission, and supply-chain design.

---

## 3. Terminology

### 3.1 V3 Core Runtime

The existing V3-owned runtime containing:

```text
Central Creative Brain
base agents
core schemas
brand memory
layout engine
prompt compiler
condition engine
generation router
evaluation and refinement
asset packager
provider interfaces
```

This runtime remains the only creative production runtime.

### 3.2 Scenario Pack

A `ScenarioPack` is a user-facing, installable specialization package represented by a card or product mode in the V3 UI.

It contains:

```text
manifest
localized display metadata
supported modes
UI declaration
policy bundle
capability-module references
vertical-agent binding
compatibility declaration
tests
```

A ScenarioPack is product-facing packaging. It is not a second generation pipeline.

### 3.3 Scenario Mode

A `ScenarioMode` is a selectable specialization inside one ScenarioPack.

Examples:

```text
ecommerce / storefront.domestic
ecommerce / storefront.cross_border
new_media_marketing / social_post
new_media_marketing / short_video_cover
private_community_operations / wechat_group
brand_ip_operations / campaign_content
```

Modes share the parent pack runtime and may activate different capability modules or policy presets.

### 3.4 VerticalAgentPack

`VerticalAgentPack` keeps the meaning already defined in the repository.

It is the core-facing specialization contract used by the Central Creative Brain.

The scenario platform must adapt a selected ScenarioPack into this existing contract rather than replace it.

### 3.5 Capability Module

A `ScenarioCapabilityModule` is a reusable, smaller specialization component that can be composed inside a ScenarioPack.

Examples:

```text
platform rule module
commercial strategy module
asset-series module
layout-rule module
copy-structure module
prompt-compilation module
evaluation-weight module
packaging module
```

Capability modules are not displayed as top-level cards unless a future product decision explicitly promotes one into a ScenarioPack.

### 3.6 Scenario Runtime

`ScenarioRuntime` is the V3-owned application layer that:

```text
resolves a scenario selection
validates the manifest
loads required modules
builds an effective policy bundle
creates a job-scoped specialization context
adapts that context to VerticalAgentPack hooks
records trace metadata
calls the existing Central Creative Brain
```

### 3.7 Scenario Hub

The `Scenario Hub` is the first V3-owned page shown after the user enters Alchemy Creative Agent from the shared site navigation.

It presents registry-driven scenario cards.

### 3.8 Important Naming Distinction

The existing `CommercialBrief.scenario` field describes the business campaign scenario, for example:

```text
new_product_promotion
festival_promotion
opening_promotion
generic_promotion
```

It must not be overloaded with the new top-level ScenarioPack id.

Use separate names:

```text
scenario_pack_id
scenario_mode_id
```

These values should initially live in auxiliary scenario contracts and existing `metadata` fields.

---

## 4. Target Product Shape

### 4.1 Top-Level Navigation Remains Unchanged

The existing product boundary remains:

```text
Shared Home Page / Site Shell
  └── existing V1 / V2 / Alchemy Lab navigation
  └── new "3.0" title-bar entry
        └── V3-owned frontend
              └── V3-owned backend APIs
                    └── V3-owned runtime
```

This extension changes only the internal V3 landing experience.

The shared home page should keep the same visual language already used by
V1, V2, and Alchemy Lab. The 3.0 entry is a navigation addition, not a separate
site or a replacement for the existing home.

### 4.2 V3 Scenario Hub

Recommended landing page:

```text
Alchemy Creative Agent 3.0

top area:
  concise V3 title
  plain-language value summary
  one-sentence quick-start input

┌──────────────────────┐  ┌──────────────────────┐
│ General Creative     │  │ E-Commerce           │
│ 通用创作             │  │ 电商特调             │
│ available            │  │ placeholder          │
└──────────────────────┘  └──────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐
│ New Media Marketing  │  │ Private Community    │
│ 新媒体营销           │  │ 私域社群运营         │
│ placeholder          │  │ placeholder          │
└──────────────────────┘  └──────────────────────┘

┌──────────────────────┐
│ Brand IP Operations  │
│ 品牌 IP 运营         │
│ placeholder          │
└──────────────────────┘

bottom area:
  recent generated images
  recent jobs
  continue-from-history entry
```

Only the General Creative card opens a complete workspace in this stage.

Placeholder cards must show a short beginner-friendly message:

```text
This specialized mode will open in a later version.
For now, use General Creative to describe this task in natural language.
```

Placeholder cards may show example use cases, but they must not expose
pack-owned form fields, pack-owned agents, pack-owned APIs, or pack-specific
generation logic.

Additional cards may be loaded from the registry later, but they must default
to `placeholder` unless a separate pack specification has been accepted.

Current-stage card matrix:

| Card | `pack_id` | Current state | Click behavior |
|---|---|---|---|
| 通用创作 / General Creative | `general_creative` | `available` | Opens the full General Creative workspace defined in document 18. |
| 电商特调 / E-Commerce | `ecommerce` | `placeholder` | Opens only a short explanation and suggests using General Creative for now. |
| 新媒体营销 / New Media Marketing | `new_media_marketing` | `placeholder` | Opens only a short explanation and suggests using General Creative for now. |
| 私域社群运营 / Private Community Operations | `private_community_operations` | `placeholder` | Opens only a short explanation and suggests using General Creative for now. |
| 品牌 IP 运营 / Brand IP Operations | `brand_ip_operations` | `placeholder` | Opens only a short explanation and suggests using General Creative for now. |

`AI Manga Drama` and other future packs are not part of the current first-screen
card set unless a later accepted document explicitly promotes them.

### 4.3 Shared Scenario Workspace

Cards should open one shared V3-owned workspace shell.

```text
Scenario card
  ↓
Shared ScenarioWorkspace
  ├── natural-language input
  ├── optional pack-specific quick controls
  ├── brand selector / uploaded assets
  ├── job progress
  ├── result asset series
  ├── select / regenerate / continue style
  └── structured warnings and metadata summary
```

A ScenarioPack may configure the workspace declaratively, but should not ship an unrelated standalone application.

In this stage, the shared workspace is used by General Creative only.
Specialization cards are expected to reuse it later, after their own detailed
pack specifications are written and accepted.

### 4.4 Natural-Language-First Remains Mandatory

Scenario selection can reduce ambiguity, but the user should still be able to describe the request naturally.

Pack-specific controls must be optional and progressively disclosed.

The UI must not expose model names, samplers, node graphs, adapter scales, or provider internals by default.

---

## 5. Target Architecture

### 5.1 High-Level Architecture

```text
Shared Site Shell
  ↓
V3 Title-Bar Entry
  ↓
Scenario Hub
  ↓
Scenario Card / Deep Link / Auto Mode
  ↓
V3 Scenario API
  ↓
ScenarioApplicationService
  ↓
ScenarioPackRegistry + ScenarioModuleRegistry
  ↓
ScenarioRuntime
  ├── manifest validation
  ├── selection resolution
  ├── dependency resolution
  ├── policy composition
  ├── CompositeVerticalAgentPack adapter
  └── trace metadata
  ↓
Existing Central Creative Brain
  ↓
Existing Base Agents
  ↓
Existing VerticalAgentPack Hooks
  ↓
Existing Providers + Evaluation + Refinement
  ↓
Existing CommercialAssetPack
```

### 5.2 Core Dependency Direction

Required dependency direction:

```text
UI depends on Scenario API contracts
Scenario application layer depends on V3 core contracts
Scenario packs depend on extension contracts
Scenario capability modules depend on extension contracts
Central Creative Brain depends on VerticalAgentPack contract
Providers depend on provider contracts
```

Forbidden reverse dependencies:

```text
Central Creative Brain imports concrete ecommerce pack
IntentAgent imports concrete social-media module
GenerationProvider imports scenario UI config
General Creative imports another scenario pack
```

### 5.3 One Primary Scenario Pack Per Job

The first implementation should activate exactly one primary ScenarioPack per job.

That pack may compose multiple internal capability modules.

Do not initially allow arbitrary combinations of multiple top-level packs such as:

```text
E-Commerce + Brand IP + AI Manga + New Media
```

Unrestricted cross-pack composition creates unresolved policy conflicts.

Shared behavior should instead be extracted into reusable capability modules and declared as dependencies of the primary pack.

### 5.4 Future Cross-Pack Composition

A later version may support a controlled secondary-pack model, but only after defining:

```text
conflict keys
precedence rules
compatibility declarations
composition tests
UI explanation
version pinning
```

It is out of scope for the first platform extension.

---

## 6. Additive Directory Structure

Do not move or rename existing V3 modules.

Add the following V3-owned structure beside them:

```text
alchemy_creative_agent_3_0/
  docs/
    17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md

  app/
    scenario_packs/
      __init__.py
      base.py
      manifests.py
      selection.py
      context.py
      policies.py
      registry.py
      loader.py
      resolver.py
      runtime.py
      composite_vertical_pack.py
      compatibility.py
      errors.py
      tracing.py

      packs/
        general_creative/
          __init__.py
          manifest.json
          pack.py
          policies.py

        ecommerce/
          __init__.py
          manifest.json
          pack.py
          policies.py
          modes/

        new_media_marketing/
          __init__.py
          manifest.json
          pack.py
          policies.py
          modes/

        private_community_operations/
          __init__.py
          manifest.json
          pack.py
          policies.py
          modes/

        ai_manga_drama/
          __init__.py
          manifest.json
          pack.py
          policies.py
          modes/

        brand_ip_operations/
          __init__.py
          manifest.json
          pack.py
          policies.py
          modes/

    scenario_modules/
      __init__.py
      base.py
      manifests.py
      registry.py
      dependency_graph.py
      policy_merge.py
      builtins/
        __init__.py
        platform_rules/
        commercial_strategy/
        series_planning/
        layout_rules/
        prompt_rules/
        evaluation_rules/
        packaging_rules/

    app_shell/
      existing files remain
      scenario_routes.py
      scenario_ui_contracts.py

  tests/
    test_scenario_manifest_schema.py
    test_scenario_pack_registry.py
    test_scenario_module_registry.py
    test_scenario_dependency_graph.py
    test_scenario_selection.py
    test_scenario_policy_merge.py
    test_scenario_runtime.py
    test_general_scenario_regression.py
    test_scenario_api_contract.py
    test_scenario_ui_contract.py
    test_scenario_pack_isolation.py
    test_scenario_pack_version_pinning.py

    scenario_packs/
      general_creative/
      ecommerce/
      new_media_marketing/
      private_community_operations/
      ai_manga_drama/
      brand_ip_operations/
```

If the real implementation already uses a different V3-owned source layout, preserve that layout and map these responsibilities into equivalent packages.

The responsibility boundaries are normative. Exact filenames may adapt to the existing codebase.

---

## 7. Auxiliary Scenario Contracts

These are additive V3-owned contracts.

They must not rename or remove fields from existing core schemas.

Recommended implementation: Pydantic models.

### 7.1 ScenarioPackManifest

Purpose:

```text
describe one installable scenario pack
```

Recommended first-pass fields:

```python
class ScenarioPackManifest(BaseModel):
    manifest_version: str = "1.0"
    pack_id: str
    pack_version: str

    display_name: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)
    category: str
    status: str = "active"

    entrypoint: str
    bound_vertical_pack: str
    selection_policy: str = "explicit_or_auto"

    modes: list[ScenarioModeManifest] = Field(default_factory=list)
    capability_modules: list[ScenarioModuleRef] = Field(default_factory=list)

    compatibility: ScenarioCompatibility
    ui: ScenarioUIManifest

    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

Required rules:

```text
pack_id is globally unique
pack_id uses stable lowercase snake_case
pack_version follows semantic versioning
manifest_version is validated separately from pack_version
entrypoint must resolve only from an approved V3-owned package root
bound_vertical_pack must exist or be declared as a controlled stub
status must be recognized by the registry
all active modes must have unique mode ids inside the pack
```

Recommended status values:

```text
active
experimental
coming_soon
disabled
deprecated
```

### 7.2 ScenarioModeManifest

Purpose:

```text
describe one selectable mode inside a scenario pack
```

Recommended fields:

```python
class ScenarioModeManifest(BaseModel):
    mode_id: str
    display_name: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)
    status: str = "active"

    default_parameters: dict = Field(default_factory=dict)
    required_modules: list[ScenarioModuleRef] = Field(default_factory=list)
    optional_modules: list[ScenarioModuleRef] = Field(default_factory=list)

    ui_overrides: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
```

Mode ids should be stable and hierarchical where useful:

```text
storefront.domestic
storefront.cross_border
social_post.xiaohongshu
short_video.douyin
wechat_group.daily_operation
brand_ip.campaign_content
```

A mode id must not encode implementation details such as a model name.

### 7.3 ScenarioUIManifest

Purpose:

```text
drive the shared Scenario Hub and ScenarioWorkspace declaratively
```

Recommended fields:

```python
class ScenarioUIManifest(BaseModel):
    card_icon: str | None = None
    card_image_asset: str | None = None
    card_order: int = 100
    featured: bool = False

    route_slug: str
    input_fields: list[ScenarioUIField] = Field(default_factory=list)
    quick_actions: list[ScenarioUIAction] = Field(default_factory=list)
    result_sections: list[str] = Field(default_factory=list)

    empty_state_examples: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

Allowed first-pass input field types:

```text
text
textarea
select
multi_select
toggle
brand_picker
asset_upload
reference_asset_picker
```

The UI renderer must use a whitelist of V3-owned components.

A manifest must not inject arbitrary HTML, JavaScript, CSS, remote iframe code, or executable expressions.

### 7.4 ScenarioSelection

Purpose:

```text
record how a job selected a scenario pack and mode
```

Recommended fields:

```python
class ScenarioSelection(BaseModel):
    pack_id: str | None = None
    requested_pack_version: str | None = None
    mode_id: str | None = None

    source: str = "legacy_or_auto"
    parameters: dict = Field(default_factory=dict)
    allow_general_fallback: bool = False

    metadata: dict = Field(default_factory=dict)
```

Recommended source values:

```text
explicit_ui
explicit_api
deep_link
auto_inferred
legacy_or_auto
default_general
fallback_general
```

### 7.5 ScenarioCompatibility

Purpose:

```text
prevent a pack from running against incompatible core contracts
```

Recommended fields:

```python
class ScenarioCompatibility(BaseModel):
    core_contract_min: str
    core_contract_max_exclusive: str | None = None
    manifest_versions: list[str] = Field(default_factory=lambda: ["1.0"])
    required_core_capabilities: list[str] = Field(default_factory=list)
    optional_core_capabilities: list[str] = Field(default_factory=list)
```

Use a dedicated `core_contract_version` rather than inferring compatibility only from the public product version.

Example:

```text
core_contract_version: 1.0
```

This lets product delivery waves evolve without making every pack version comparison ambiguous.

### 7.6 ScenarioModuleRef

Recommended fields:

```python
class ScenarioModuleRef(BaseModel):
    module_id: str
    version_constraint: str
    required: bool = True
    order: int = 100
    config: dict = Field(default_factory=dict)
```

### 7.7 ScenarioContext

Purpose:

```text
hold job-scoped specialization state without mutating global registry state
```

Recommended fields:

```python
class ScenarioContext(BaseModel):
    selection: ScenarioSelection
    manifest: ScenarioPackManifest

    resolved_pack_version: str
    resolved_mode_id: str | None = None
    bound_vertical_pack: str

    module_refs: list[ScenarioModuleRef] = Field(default_factory=list)
    effective_policy: ScenarioPolicyBundle

    policy_checksum: str
    trace: list[ScenarioTraceEvent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

`ScenarioContext` is job-scoped and immutable after activation, except for append-only trace events and warnings.

### 7.8 ScenarioPolicyBundle

Purpose:

```text
represent specialization as structured policy rather than hidden prompt text
```

Recommended fields:

```python
class ScenarioPolicyBundle(BaseModel):
    hard_constraints: list[PolicyRule] = Field(default_factory=list)
    defaults: list[PolicyRule] = Field(default_factory=list)

    commercial_brief_rules: list[PolicyRule] = Field(default_factory=list)
    creative_plan_rules: list[PolicyRule] = Field(default_factory=list)
    series_plan_rules: list[PolicyRule] = Field(default_factory=list)
    layout_plan_rules: list[PolicyRule] = Field(default_factory=list)
    prompt_compilation_rules: list[PolicyRule] = Field(default_factory=list)
    generation_policy_hints: list[PolicyRule] = Field(default_factory=list)
    evaluation_policy_rules: list[PolicyRule] = Field(default_factory=list)
    asset_pack_rules: list[PolicyRule] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)
```

Each `PolicyRule` should include:

```python
class PolicyRule(BaseModel):
    rule_id: str
    target_path: str
    operation: str
    value: object
    priority: int = 100
    source: str
    hard: bool = False
    metadata: dict = Field(default_factory=dict)
```

Allowed first-pass operations:

```text
set_if_missing
replace_if_allowed
append_unique
remove_if_allowed
min_value
max_value
merge_mapping
weighted_override
require
forbid
```

Every applied rule must remain auditable by `rule_id` and `source`.

### 7.9 ScenarioTraceEvent

Recommended fields:

```python
class ScenarioTraceEvent(BaseModel):
    event_type: str
    source_id: str
    source_version: str | None = None
    hook: str | None = None
    rule_ids: list[str] = Field(default_factory=list)
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

Do not store private chain-of-thought or hidden model reasoning.

Store only structured decisions and concise reasoning summaries already allowed by V3 agent contracts.

---

## 8. Scenario Pack and Capability Module Interfaces

### 8.1 ScenarioPack Interface

Recommended interface:

```python
class ScenarioPack(Protocol):
    def manifest(self) -> ScenarioPackManifest:
        ...

    def validate_selection(
        self,
        selection: ScenarioSelection,
    ) -> list[str]:
        ...

    def build_policy_bundle(
        self,
        selection: ScenarioSelection,
        base_context: dict,
    ) -> ScenarioPolicyBundle:
        ...

    def build_vertical_pack_adapter(
        self,
        scenario_context: ScenarioContext,
        vertical_registry: "VerticalAgentRegistry",
        module_registry: "ScenarioModuleRegistry",
    ) -> "VerticalAgentPack":
        ...
```

A ScenarioPack must not expose methods such as:

```text
generate_image()
call_provider()
write_brand_memory_directly()
render_final_asset_directly()
```

### 8.2 ScenarioCapabilityModule Interface

Recommended interface:

```python
class ScenarioCapabilityModule(Protocol):
    def manifest(self) -> "ScenarioCapabilityModuleManifest":
        ...

    def contribute_policy(
        self,
        selection: ScenarioSelection,
        module_config: dict,
        base_context: dict,
    ) -> ScenarioPolicyBundle:
        ...
```

The first implementation should prefer declarative policy contribution over arbitrary mutation hooks.

Where executable refinement is necessary, use a typed result:

```python
class ScenarioModuleResult(BaseModel):
    output: object
    applied_rule_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

### 8.3 CompositeVerticalAgentPack

`CompositeVerticalAgentPack` is the compatibility adapter between the new scenario platform and the existing V3 extension contract.

It must implement the current `VerticalAgentPack` methods:

```python
class CompositeVerticalAgentPack:
    name: str
    supported_industries: list[str]
    supported_scenarios: list[str]

    def match(self, creative_job, commercial_brief=None) -> float:
        ...

    def refine_commercial_brief(self, context):
        ...

    def refine_creative_plan(self, context):
        ...

    def refine_series_plan(self, context):
        ...

    def refine_layout_plan(self, context):
        ...

    def refine_prompt_compilation(self, context):
        ...

    def refine_evaluation_policy(self, context):
        ...
```

Its responsibilities:

```text
wrap the selected base VerticalAgentPack
apply the effective ScenarioPolicyBundle at supported hooks
execute capability-module contributions in deterministic order
preserve user and core constraints
emit trace metadata
return standard V3 schemas
```

It must not duplicate the base-agent pipeline.

### 8.4 Optional Future Hooks

The current V3 contract may not expose every future hook required for:

```text
GenerationPlan refinement
ConditionPlan refinement
CommercialAssetPack refinement
brand-memory policy refinement
```

Do not monkey-patch or bypass the runtime.

Use capability negotiation:

```text
if core contract supports hook:
    apply hook
else:
    store compatible hints in metadata
    record unsupported-hook warning
    preserve current core behavior
```

A future core-contract revision may add optional hooks, but existing packs must continue working.

### 8.5 No Mutable Global Pack State

Registries should store factories or immutable definitions.

Per-job state belongs in `ScenarioContext`.

Do not store current user, current brand, current mode, or current job on a singleton ScenarioPack instance.

---

## 9. Registry and Loading System

### 9.1 ScenarioPackRegistry

Recommended responsibilities:

```text
register trusted pack factories
validate manifests
validate compatibility
list visible packs for UI
resolve active version
resolve explicit selection
resolve auto-inferred selection when enabled
return General Creative fallback when permitted
preserve disabled and deprecated status
```

Recommended interface:

```python
class ScenarioPackRegistry:
    def register(self, factory: ScenarioPackFactory) -> None:
        ...

    def list_manifests(
        self,
        locale: str,
        include_unavailable: bool = False,
    ) -> list[ScenarioPackManifest]:
        ...

    def resolve(
        self,
        selection: ScenarioSelection,
        creative_job: "CreativeJob | None" = None,
        commercial_brief: "CommercialBrief | None" = None,
    ) -> ResolvedScenarioPack:
        ...
```

### 9.2 ScenarioModuleRegistry

Responsibilities:

```text
register trusted capability-module factories
resolve version constraints
validate dependency graph
reject cycles
return deterministic module order
report missing optional modules as warnings
report missing required modules as activation failures
```

### 9.3 Built-In Registry Configuration

The first implementation should use an explicit V3-owned configuration file or Python registry list.

Example:

```python
BUILTIN_SCENARIO_PACKS = [
    GeneralCreativeScenarioPack,
    EcommerceScenarioPack,
    NewMediaMarketingScenarioPack,
    PrivateCommunityOperationsScenarioPack,
    AIMangaDramaScenarioPack,
    BrandIPOperationsScenarioPack,
]
```

This list may activate stubs or `coming_soon` manifests before policy implementation is complete.

### 9.4 Discovery Rules

First-pass discovery should be deterministic.

Allowed:

```text
explicit built-in registry
V3-owned config file
controlled Python entrypoint allowlist later
```

Not allowed initially:

```text
recursive import of every file in the repository
untrusted pip entrypoint discovery
remote manifest URLs
user uploads
runtime eval()
```

### 9.5 Dependency Graph Rules

Capability-module dependencies form a directed acyclic graph.

Validation must reject:

```text
cycles
missing required modules
incompatible version constraints
duplicate conflicting module ids
multiple modules claiming an exclusive conflict key
```

Module execution order:

```text
1. dependency order
2. explicit module order
3. stable module id as final tie-breaker
```

### 9.6 Reload and Removal

Controlled registry reload may be added later.

Rules:

```text
new jobs may use the new active version
running jobs remain pinned to their resolved version
historical jobs retain version metadata
removed pack versions must not make historical metadata unreadable
```

A pack removal should normally disable new selection before deleting old implementation artifacts.

---

## 10. Scenario Selection and Routing

### 10.1 Selection Precedence

Use this order:

```text
1. explicit API selection
2. explicit UI card or deep-link selection
3. existing V3 automatic vertical inference when no scenario selection is supplied
4. General Creative / DefaultCommercialPack fallback
```

An explicit user selection must not be silently replaced by a different active pack.

### 10.2 Legacy Request Compatibility

Existing API requests without `scenario_selection` must remain valid.

They should continue through the current V3 behavior:

```text
existing intent inference
→ existing VerticalAgentRegistry matching
→ existing DefaultCommercialPack fallback
```

This is necessary for backward compatibility.

### 10.3 General Creative Selection

Explicitly selecting the General Creative card should activate:

```text
pack_id: general_creative
bound_vertical_pack: DefaultCommercialPack
```

It should not silently activate a specialized scenario pack.

### 10.4 Explicit Specialized Selection

When the user selects E-Commerce, for example:

```text
scenario pack is fixed to ecommerce
mode may be explicit or inferred inside ecommerce
industry and campaign scenario are still inferred by existing agents
```

The pack may refine the result but must not rewrite the original user input.

### 10.5 Mode Resolution

Mode resolution order:

```text
1. explicit mode_id
2. pack-local inference
3. pack default mode
4. activation error if the pack has no valid default
```

Pack-local inference must be auditable and must not replace core industry inference.

### 10.6 Selection Metadata

The final selected values should be recorded in:

```text
CreativeJob.metadata["scenario_runtime"]
PlanningResult.metadata["scenario_runtime"]
CommercialAssetPack.metadata["scenario_runtime"]
```

Where a GenerationResult wrapper exists, it should also carry the same summary.

---

## 11. Policy Merge and Conflict Resolution

### 11.1 Effective Policy Layers

The runtime should construct one deterministic effective policy.

Conceptual layers:

```text
V3 core defaults
+ existing BrandProfile preferences
+ ScenarioPack defaults
+ ScenarioMode defaults
+ capability-module contributions
+ explicit mode parameters
+ explicit user constraints
+ immutable V3 hard rules
```

### 11.2 Hard Rules Always Win

The following cannot be removed by a pack:

```text
schema validity
V3 independence from V1/V2
safety and legal restrictions
provider contract requirements
required audit metadata
required brand-memory update rules
required evaluation and packaging stages
exact-text rendering rules when mandated by core policy
```

### 11.3 User Constraints Must Be Preserved

A pack must not erase explicit user requirements such as:

```text
target platform
required product
required copy text
aspect ratio
language
brand id
requested asset types
forbidden visual directions
```

If a user constraint conflicts with a hard platform or safety rule, return a structured conflict instead of silently ignoring either side.

### 11.4 Brand Identity Protection

Scenario defaults may adapt campaign style but must not casually replace locked brand identity.

Protected brand fields may include:

```text
logo rules
brand name
locked color values
product appearance
mascot identity
approved typography direction
forbidden styles
```

An explicit user request may override a brand preference, but a locked brand field should require an explicit unlock or override signal.

### 11.5 Merge Semantics

Recommended behavior by rule type:

```text
hard constraints       append-only, cannot be removed
explicit user values   replace mutable defaults
required lists         append_unique
forbidden lists        append_unique
numeric thresholds     min_value or max_value as declared
score weights          weighted_override then normalize
mappings                deep merge only on declared keys
single-choice enums     replace_if_allowed
```

Free-form deep merges of arbitrary dictionaries are forbidden because they are difficult to audit.

### 11.6 Conflict Keys

A module may declare exclusive conflict keys such as:

```text
layout.primary_template
copy.primary_framework
evaluation.weight_profile
provider.routing_profile
asset_series.primary_recipe
```

Two active modules cannot own the same exclusive key unless the parent pack declares an explicit resolver.

### 11.7 Determinism

Given the same:

```text
core contract version
pack version
module versions
selection parameters
user input
brand profile
provider availability
```

policy composition must produce the same normalized policy bundle and checksum.

### 11.8 No Hidden Prompt Concatenation

The policy merger must not concatenate opaque prompt fragments from every module.

The correct pattern is:

```text
module policy
→ structured V3 plan fields
→ PromptCompiler
→ provider-ready prompt
```

---

## 12. Internal API Boundary

### 12.1 Internal API Meaning

For the first implementation, “internal API” means stable typed service interfaces inside the V3 application.

It does not require HTTP between every module.

Recommended call chain:

```text
V3 route
→ ScenarioApplicationService
→ ScenarioRuntime
→ CentralCreativeBrain
```

### 12.2 ScenarioApplicationService

Recommended responsibilities:

```text
list available manifests
get one manifest
validate scenario selection
create a CreativeJob from API DTO
activate ScenarioContext
call CentralCreativeBrain
attach scenario metadata to result
normalize errors for UI
```

Recommended interface:

```python
class ScenarioApplicationService:
    def list_scenario_packs(self, locale: str) -> list[ScenarioPackManifest]:
        ...

    def get_scenario_pack(self, pack_id: str, locale: str) -> ScenarioPackManifest:
        ...

    def create_job(self, request: CreateCreativeJobRequest) -> PlanningResult:
        ...
```

### 12.3 API Request Envelope

Do not add required fields to `CreativeJob`.

Use an API-layer DTO:

```python
class CreateCreativeJobRequest(BaseModel):
    user_input: str
    optional_brand_id: str | None = None
    optional_template_id: str | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    explicit_constraints: list[str] = Field(default_factory=list)

    scenario_selection: ScenarioSelection | None = None
    metadata: dict = Field(default_factory=dict)
```

The application service converts this request into the existing `CreativeJob` contract.

Scenario data should be copied into `CreativeJob.metadata`, not into new required core fields.

### 12.4 Recommended V3 Routes

Extend the existing V3 namespace:

```text
GET  /api/v3/creative-agent/scenario-packs
GET  /api/v3/creative-agent/scenario-packs/{pack_id}
POST /api/v3/creative-agent/jobs
GET  /api/v3/creative-agent/jobs/{job_id}
```

Optional validation endpoint:

```text
POST /api/v3/creative-agent/scenario-packs/{pack_id}/validate-selection
```

Do not create unrelated public APIs for every scenario pack.

Incorrect:

```text
/api/ecommerce/generate
/api/new-media/generate
/api/brand-ip/generate
```

Correct:

```text
/api/v3/creative-agent/jobs
+ scenario_selection in request envelope
```

### 12.5 Example Create-Job Request

```json
{
  "user_input": "帮我做一组适合国内网店上新的产品视觉",
  "optional_brand_id": "brand_123",
  "uploaded_asset_ids": ["product_front", "product_side"],
  "scenario_selection": {
    "pack_id": "ecommerce",
    "mode_id": "storefront.domestic",
    "source": "explicit_ui",
    "parameters": {
      "target_platform": "taobao"
    },
    "allow_general_fallback": false
  }
}
```

### 12.6 Example Response Metadata

```json
{
  "scenario_runtime": {
    "pack_id": "ecommerce",
    "pack_version": "1.0.0",
    "mode_id": "storefront.domestic",
    "selection_source": "explicit_ui",
    "bound_vertical_pack": "EcommerceAgentFamily",
    "modules": [
      {"module_id": "ecommerce.platform_rules", "version": "1.0.0"},
      {"module_id": "ecommerce.layout_rules", "version": "1.0.0"}
    ],
    "policy_checksum": "sha256:...",
    "fallbacks": [],
    "warnings": []
  }
}
```

### 12.7 Future Remote Modules

A future out-of-process module may be supported through a `RemoteScenarioModuleAdapter` implementing the same request and result contracts.

It must add:

```text
timeouts
retries
health checks
authentication
circuit breaker
version handshake
structured failure behavior
```

Remote modules are not required for the first implementation.

---

## 13. UI Contract

### 13.1 Registry-Driven Card Grid

The Scenario Hub should call:

```text
GET /api/v3/creative-agent/scenario-packs
```

The backend returns visible manifests already filtered by:

```text
status
compatibility
feature flag
account entitlement later
locale
```

The UI sorts by `ui.card_order`.

The shared site shell must keep the same visual language as V1, V2, and
Alchemy Lab. The only top-level shell change required by this document is a new
`3.0` navigation entry. Selecting `3.0` opens the V3 Scenario Hub; it must not
replace the existing V1/V2/Alchemy Lab entry points.

### 13.2 Card States

Recommended card states:

```text
active          clickable and executable
experimental    clickable with label
placeholder     visible card, not executable in the current stage
coming_soon     visible but not executable
disabled        hidden by default or shown as unavailable
deprecated      hidden for new users, retained for historical jobs
```

For the current stage:

```text
general_creative = active
ecommerce = placeholder
new_media_marketing = placeholder
private_community_operations = placeholder
brand_ip_operations = placeholder
```

`placeholder` cards may open a lightweight explanation panel only. They must not
open the shared workspace with pack-specific controls, start jobs, or call
pack-owned APIs.

Placeholder cards must be non-executable in both frontend and backend behavior:

```text
frontend:
  no complex form
  no submit button that starts a pack-owned job
  no pack-specific advanced controls

backend:
  no pack-specific endpoint
  no pack-owned agent invocation
  no pack-specific generation or evaluation policy activation
```

### 13.3 General Card Is Mandatory

The registry must always return one active General Creative card unless the V3 product itself is unavailable.

If the General Creative pack fails validation, V3 startup should fail loudly because the baseline is not usable.

### 13.4 Shared Workspace Components

The first implementation should use shared components:

```text
ScenarioHeader
NaturalLanguageInput
BrandPicker
AssetUploader
OptionalQuickControls
JobProgress
AssetSeriesViewer
CandidateSelector
RegenerateAction
ContinueStyleAction
WarningsPanel
MetadataSummary
```

Scenario manifests may control labels, available quick controls, examples, and result-section order.

### 13.5 No Arbitrary Scenario Frontend Bundles

A pack should not ship a separate unmanaged frontend bundle in the first implementation.

Specialized UI components may be added later only through a V3-owned component registry:

```text
component id
version
props schema
pack allowlist
compatibility tests
```

### 13.6 Recommended Routes

```text
/v3/creative-agent
/v3/creative-agent/scenarios/general_creative
/v3/creative-agent/scenarios/ecommerce
/v3/creative-agent/scenarios/new_media_marketing
/v3/creative-agent/scenarios/private_community_operations
/v3/creative-agent/scenarios/brand_ip_operations
```

Exact frontend route prefixes may adapt to the host application, but each route must remain inside the V3-owned UI boundary.

In the current stage, only `/v3/creative-agent/scenarios/general_creative`
is executable. Other listed routes render placeholder detail panels and must not
create jobs.

### 13.7 Deep-Link Behavior

A deep link must:

```text
load the manifest
verify active compatibility
resolve requested mode
show unavailable state if invalid
never execute an unvalidated pack id directly
```

---

## 14. Scenario Runtime Lifecycle

Lifecycle:

```text
DISCOVER
→ VALIDATE
→ REGISTER
→ RESOLVE
→ ACTIVATE
→ COMPOSE
→ EXECUTE THROUGH CORE
→ TRACE
→ RELEASE
```

### 14.1 DISCOVER

Load trusted built-in pack and module definitions.

### 14.2 VALIDATE

Validate:

```text
manifest schema
pack id uniqueness
version syntax
core compatibility
vertical-pack binding
module dependencies
UI field types
route slug uniqueness
```

### 14.3 REGISTER

Store immutable factories and manifests in registries.

### 14.4 RESOLVE

Resolve one pack version and one mode for the request.

### 14.5 ACTIVATE

Create an immutable, job-scoped `ScenarioContext`.

### 14.6 COMPOSE

Merge pack, mode, module, brand, user, and core policies into one effective policy bundle.

Compute a checksum.

### 14.7 EXECUTE THROUGH CORE

Build `CompositeVerticalAgentPack` and pass specialization through the existing V3 extension points.

The Central Creative Brain retains orchestration ownership.

### 14.8 TRACE

Attach concise structured trace metadata to major outputs.

### 14.9 RELEASE

Release job-scoped resources.

Do not mutate registry definitions or pack-global state.

---

## 15. General Creative Pack

### 15.1 Purpose

General Creative is the stable, non-specialized user entry.

It proves that the new scenario platform has not changed the existing V3 product contract.

### 15.2 Manifest Binding

```text
pack_id: general_creative
bound_vertical_pack: DefaultCommercialPack
selection_policy: explicit_or_default
required capability modules: none
```

### 15.3 Behavior

General Creative must not add:

```text
new industry assumptions
new platform rules
new score weights
new provider preferences
new prompt fragments
new asset recipes
```

It may provide UI examples and labels only.

### 15.4 Regression Requirement

For a fixed test fixture, these outputs should remain equivalent before and after scenario-platform integration:

```text
CreativeJob
CommercialBrief
BrandProfile
CreativePlan
SeriesPlan
LayoutPlan
PromptCompilationResult
ConditionPlan
GenerationPlan
EvaluationReport
CommercialAssetPack
```

Scenario metadata may be added, but business output must not change solely because the platform layer exists.

---

## 16. Initial Scenario-Pack Catalog

This section defines placeholders and boundaries only.

It does not define final tuning behavior.

Current-stage catalog rule:

```text
only general_creative is active
all other first-screen specialization cards are placeholders
placeholder cards are visible for product orientation but cannot execute jobs
future packs must be added through manifest / registry extension
future packs must not require Central Creative Brain edits
```

### 16.1 General Creative

```text
pack_id: general_creative
Chinese label: 通用创作
binding: DefaultCommercialPack
current-stage status: active
opens workspace: yes
implements detailed agent logic: yes, in document 18
```

### 16.2 E-Commerce

```text
pack_id: ecommerce
Chinese label: 电商特调
binding: EcommerceAgentFamily
current-stage status: placeholder
opens workspace: no
implements detailed agent logic: no
initial modes:
  storefront.domestic
  storefront.cross_border
```

Detailed platform, conversion, asset, layout, and evaluation policies belong in a later e-commerce pack specification.

### 16.3 New Media Marketing

```text
pack_id: new_media_marketing
Chinese label: 新媒体营销
binding: NewMediaMarketingAgentFamily or a controlled composite adapter
current-stage status: placeholder
opens workspace: no
implements detailed agent logic: no
initial modes may later include:
  social_post
  short_video_cover
  campaign_content
```

This pack is channel-oriented rather than a replacement for an industry pack.

Shared behavior should be implemented as reusable capability modules where possible.

### 16.4 Private Community Operations

```text
pack_id: private_community_operations
Chinese label: 私域社群运营
binding: PrivateCommunityAgentFamily or a controlled composite adapter
current-stage status: placeholder
opens workspace: no
implements detailed agent logic: no
initial modes may later include:
  wechat_group
  wechat_moments
  member_campaign
  crm_touchpoint
```

This pack must still produce outputs through the normal V3 asset and evaluation pipeline.

### 16.5 AI Manga Drama

```text
pack_id: ai_manga_drama
Chinese label: AI 漫剧
binding: AIMangaDramaAgentFamily
current-stage status: future_pack_not_on_first_screen
opens workspace: no
implements detailed agent logic: no
```

Character identity, sequence continuity, and storyboard behavior are later pack-level policies and capability modules.

### 16.6 Brand IP Operations

```text
pack_id: brand_ip_operations
Chinese label: 品牌 IP 运营
binding: BrandIPAgentFamily
current-stage status: placeholder
opens workspace: no
implements detailed agent logic: no
```

Brand character consistency and long-term IP content operations must continue to use V3 brand memory and standard asset contracts.

### 16.7 Future Packs

Possible future packs:

```text
restaurant_marketing
local_service_marketing
education_marketing
hospitality_marketing
real_estate_marketing
live_commerce
festival_campaigns
```

A future pack must not require a new top-level runtime.

---

## 17. Brand Memory and Scenario-Specific State

### 17.1 One Brand Memory Authority

Scenario packs must not create independent competing brand-memory systems.

The existing V3 BrandMemoryAgent and BrandProfile remain authoritative for shared brand facts.

### 17.2 Shared Brand Facts

Keep these in the standard BrandProfile contract:

```text
brand identity
visual tone
color palette
copywriting tone
layout preference
reference assets
accepted outputs
rejected styles
platform history
```

### 17.3 Scenario-Namespace Metadata

Pack-specific preferences may initially be stored under a namespaced metadata key:

```json
{
  "scenario_namespaces": {
    "ecommerce": {
      "preferred_product_angle": "front_three_quarter"
    },
    "brand_ip_operations": {
      "approved_expression_set": ["happy", "curious"]
    }
  }
}
```

Rules:

```text
pack writes must go through BrandMemoryAgent or a V3-owned memory service
pack cannot write another pack's namespace
shared brand facts must not be duplicated into every namespace
accepted-output update policy remains unchanged
```

### 17.4 Future Companion Store

If pack-specific state becomes too large for BrandProfile metadata, add a V3-owned companion store keyed by:

```text
brand_id + pack_id + schema_version
```

Access must still be mediated by the V3 memory layer.

---

## 18. Provider and Resource Isolation

### 18.1 Provider Routing Remains Centralized

A pack may declare requirements such as:

```text
needs product identity conditioning
prefers accurate text renderer
needs character identity conditioning
requires batch candidates
requires platform-fit scorer
```

The GenerationRouterAgent and provider registries decide the actual provider.

### 18.2 Capability-Based Routing

Scenario policies should request capabilities, not concrete provider names, unless a controlled operator configuration explicitly pins one.

Correct:

```text
requires_identity_conditioning: true
requires_text_rendering: true
```

Avoid:

```text
always_use_provider: some_external_vendor
```

### 18.3 Cost and Quota

A future pack may declare a cost profile, but credit reservation and charging must still use `V3BalanceAdapter`.

Scenario packs must not access the shared balance implementation directly.

### 18.4 File and Network Access

Capability modules should not receive unrestricted file-system or network access.

They should receive only the V3 contract objects and approved asset references required for their hook.

Secrets must never be stored in manifests or policy bundles.

---

## 19. Failure, Fallback, and Degradation

### 19.1 Explicit Selection Failure

When the user explicitly selects a specialized pack and it cannot activate:

```text
return a structured unavailable / incompatible error by default
```

Do not silently run General Creative and present the result as specialized.

If `allow_general_fallback` is true, fallback may occur with visible warning and metadata.

### 19.2 Automatic Selection Failure

When automatic pack inference fails:

```text
fallback to existing VerticalAgentRegistry behavior
then DefaultCommercialPack
```

Record the fallback.

### 19.3 Optional Module Failure

If an optional module is unavailable:

```text
skip module
continue pack activation
record warning
record missing capability
```

### 19.4 Required Module Failure

If a required module is unavailable or incompatible:

```text
fail pack activation
```

Fallback to General Creative only when allowed by request policy.

### 19.5 Hook Failure

A hook failure must be isolated and structured.

Recommended error fields:

```text
code
pack_id
module_id
hook
message
severity
fallback_action
metadata
```

### 19.6 Core and Provider Failures

After the scenario layer has activated successfully, core and provider failures continue to follow existing V3 error, retry, evaluation, and refinement policies.

The scenario platform must not invent a parallel retry loop.

### 19.7 Historical Jobs

A disabled or removed pack must not make old job records unreadable.

Historical results should render from stored manifests or normalized display snapshots in metadata.

---

## 20. Observability and Audit Metadata

### 20.1 Required Scenario Metadata

Every specialized run should preserve:

```text
pack id
pack version
manifest version
mode id
selection source
bound vertical pack
module ids and versions
policy checksum
applied rule ids
unsupported optional hooks
warnings
fallbacks
activation timestamp if available
```

### 20.2 Recommended Metadata Shape

```json
{
  "scenario_runtime": {
    "pack_id": "ecommerce",
    "pack_version": "1.0.0",
    "manifest_version": "1.0",
    "mode_id": "storefront.domestic",
    "selection_source": "explicit_ui",
    "bound_vertical_pack": "EcommerceAgentFamily",
    "core_contract_version": "1.0",
    "modules": [],
    "policy_checksum": "sha256:...",
    "applied_rule_ids": [],
    "unsupported_hooks": [],
    "warnings": [],
    "fallbacks": []
  }
}
```

### 20.3 Audit Boundary

Metadata should explain:

```text
what pack was active
what structured rules changed
what fallback occurred
what version produced the result
```

It should not reveal hidden chain-of-thought.

---

## 21. Security Requirements

### 21.1 Trusted Code Boundary

Only V3-owned, reviewed, allowlisted packs and modules are executable in the first implementation.

### 21.2 Manifest Validation

Reject manifests containing:

```text
unknown executable field
path traversal
unapproved entrypoint root
invalid version
unknown UI component
remote script URL
secret value
cyclic dependency
incompatible core requirement
```

### 21.3 Least Privilege

A module receives only the structured input required by its declared hook.

Examples:

```text
layout module does not need balance-adapter access
evaluation-weight module does not need file-write access
UI manifest does not need provider credentials
```

### 21.4 Pack Namespace Isolation

Pack-specific configuration and memory must use pack-id namespaces.

One pack must not modify another pack's manifest, registry entry, state, or memory namespace.

### 21.5 Future External Plugins

External third-party plugins are out of scope.

A future design must cover:

```text
code signing
package provenance
sandboxing
permission declarations
network policy
secret access
resource quotas
malware scanning
revocation
compatibility certification
```

---

## 22. Testing Strategy

### 22.1 Baseline Regression Is the First Gate

Before adding specialized behavior, capture the accepted current V3 baseline through deterministic fixtures or snapshots.

Required test:

```text
test_general_scenario_regression
```

It must prove that adding the scenario platform does not alter the General Creative pipeline.

### 22.2 Contract Tests

Required tests:

```text
all scenario contracts serialize to JSON
manifest ids and versions validate
unsupported manifest versions fail
all active packs are core-compatible
all active modes are unique inside their pack
all module dependencies resolve
cycles are rejected
policy merge is deterministic
policy checksum is stable
```

### 22.3 Registry Tests

Required tests:

```text
General Creative is always registered
active packs appear in UI list
coming-soon packs are non-executable
explicit pack resolves exact version
disabled pack cannot start new job
deprecated pack remains readable for historical metadata
```

### 22.4 Selection Tests

Required tests:

```text
explicit API selection wins
explicit UI selection wins
deep link validates pack and mode
legacy request preserves current behavior
auto inference falls back correctly
explicit failure is not silently hidden
```

### 22.5 Isolation Tests

Required tests:

```text
scenario packs do not import V1/V2
scenario packs do not call providers directly
scenario packs do not bypass evaluation
scenario packs do not bypass asset packaging
one pack cannot mutate another pack definition
one job cannot mutate another job's ScenarioContext
```

### 22.6 UI Contract Tests

Required tests:

```text
card list renders from API manifests
card order follows manifest
unsupported UI field type is rejected
General card opens shared workspace
coming-soon card cannot create job
unknown deep-link pack shows unavailable state
```

### 22.7 Version-Pinning Tests

Required tests:

```text
job stores resolved pack version
job stores module versions
registry update does not change running job context
historical result remains readable after pack disable
```

### 22.8 Pack-Owned Golden Cases

Every active specialization pack must add its own golden cases later.

Recommended location:

```text
tests/scenario_packs/{pack_id}/
```

Each pack must still pass the shared V3 core assertions.

### 22.9 Offline Test Requirement

Registry, manifest, merge, General Creative, and stub-pack tests must pass without:

```text
GPU
external provider
network access
V1/V2 runtime
```

Use Noop and Mock providers already required by V3.

---

## 23. Post-Foundation Implementation Phases

### E0. Freeze and Verify the Existing Baseline

Deliverables:

```text
current V3 test suite passes
baseline General Creative fixtures captured
current core-contract version recorded
current VerticalAgentPack behavior documented in tests
```

Acceptance criteria:

```text
1. No scenario-platform code is required to pass the current suite.
2. Baseline outputs are reproducible.
3. Existing API requests are captured as compatibility fixtures.
```

### E1. Add Auxiliary Contracts and Registries

Deliverables:

```text
ScenarioPackManifest
ScenarioModeManifest
ScenarioUIManifest
ScenarioSelection
ScenarioContext
ScenarioPolicyBundle
ScenarioPackRegistry
ScenarioModuleRegistry
GeneralCreativeScenarioPack
```

Acceptance criteria:

```text
1. General Creative registers successfully.
2. Manifests serialize to JSON.
3. Invalid manifests fail deterministically.
4. No current core schema is changed.
5. No current core agent behavior is changed.
```

### E2. Add ScenarioRuntime and Core Adapter

Deliverables:

```text
ScenarioRuntime
policy merger
module dependency resolver
CompositeVerticalAgentPack
scenario trace metadata
version pinning
```

Acceptance criteria:

```text
1. General Creative produces baseline-equivalent output.
2. A no-op specialized pack can run through the same core.
3. No separate generation pipeline exists.
4. Existing VerticalAgentPack hooks are used.
5. Unsupported optional hooks degrade with warnings.
```

### E3. Add V3 Scenario API

Deliverables:

```text
list-scenario-packs endpoint
get-scenario-pack endpoint
scenario-aware create-job request envelope
structured activation errors
```

Acceptance criteria:

```text
1. Legacy create-job requests remain valid.
2. Explicit selection is recorded.
3. Active version is pinned.
4. No pack-specific generation endpoint is added.
```

### E4. Add Scenario Hub and Shared Workspace

Deliverables:

```text
registry-driven card page
General Creative card
shared ScenarioWorkspace
manifest-driven quick controls
active / coming-soon states
placeholder states for first-screen specialization cards
deep-link validation
```

Acceptance criteria:

```text
1. Cards are not hard-coded as business logic.
2. General Creative is always available.
3. Specialized cards render as placeholders and cannot create jobs in this stage.
4. No arbitrary plugin frontend code executes.
5. The V3 home uses the same visual language as V1, V2, and Alchemy Lab.
6. Recent images and recent jobs are visible without entering advanced controls.
```

### E5. Add Empty or Stub Specialization Packs

Initial stubs:

```text
ecommerce
new_media_marketing
private_community_operations
brand_ip_operations
```

Acceptance criteria:

```text
1. Every stub has a valid manifest.
2. Every stub can be disabled independently.
3. Coming-soon stubs cannot execute.
4. Placeholder stubs cannot execute jobs or call pack-owned APIs.
5. Adding or removing a stub requires no Central Creative Brain change.
6. Full scenario tuning has not yet been mixed into framework code.
```

### Sequential Rule

Do not begin detailed e-commerce, new-media, community, AI-manga, or brand-IP tuning until E0-E5 pass.

This prevents specialization work from defining architecture accidentally.

For the current stage, even if E0-E5 pass, only General Creative is complete.
Detailed specialization work must wait for separate pack-specific documents.

---

## 24. Definition of Done for the Scenario Platform

The framework extension is complete when:

```text
1. Entering V3 opens a registry-driven Scenario Hub.
2. General Creative is an active card and preserves current V3 behavior.
3. E-commerce, new-media, private-community, and brand-IP cards are visible placeholders.
4. One shared ScenarioWorkspace serves all executable packs; in this stage, only General Creative is executable.
5. One shared create-job API serves all executable packs; placeholders cannot call it.
6. One Central Creative Brain executes all executable packs; placeholders never reach runtime execution.
7. Scenario policies reach core only through typed V3 contracts.
8. Scenario packs do not call providers directly.
9. Scenario packs do not fork evaluation, refinement, memory, or packaging.
10. A pack can be enabled, disabled, or removed without breaking the core.
11. A new pack can be added without editing Central Creative Brain.
12. Every job records pack and module versions.
13. Legacy requests remain compatible.
14. General Creative regression tests pass.
15. Manifest, registry, merge, isolation, API, and UI tests pass offline.
16. Stub entries exist for the first planned specialization families.
17. Detailed vertical tuning can begin as independent pack specifications.
18. Placeholder cards cannot create jobs, expose pack-specific complex forms, or run pack-owned agents.
19. The current stage cannot be marked complete if any specialization card is implemented as a full workflow.
```

---

## 25. Developer Workflow for Adding a New Scenario Pack

A developer adding a future pack should follow this sequence:

```text
1. Choose a stable pack_id.
2. Create a pack directory under scenario_packs/packs/.
3. Add a validated manifest.
4. Bind an existing VerticalAgentPack or add a new V3-owned vertical pack.
5. Reuse existing capability modules where possible.
6. Add new capability modules only for genuinely reusable behavior.
7. Express specialization as structured policies.
8. Add pack-owned golden cases and contract tests.
9. Register or feature-flag the pack.
10. Verify General Creative regression.
11. Verify no V1/V2 imports.
12. Verify no Central Creative Brain branch was added.
```

A normal new pack should require zero edits to:

```text
CentralCreativeBrain agent sequence
core schema required fields
provider implementations
General Creative policies
other pack implementations
```

---

## 26. Example End-to-End Flow

This is a future flow example, not current-stage scope.

In the current stage, clicking `电商特调` shows only a placeholder panel:

```text
电商特调将在后续版本开放。
你可以先使用通用创作，用自然语言描述商品图、活动图或店铺素材需求。
```

The future flow below becomes valid only after an accepted e-commerce pack
specification exists.

User action:

```text
clicks “电商特调”
selects “国内网店”
enters a natural-language request
uploads product references
```

Runtime flow:

```text
1. UI loads ecommerce manifest.
2. UI sends scenario_selection with mode storefront.domestic.
3. ScenarioApplicationService creates the existing CreativeJob.
4. ScenarioRuntime resolves ecommerce pack version.
5. ScenarioRuntime resolves required capability modules.
6. ScenarioRuntime composes a deterministic policy bundle.
7. ScenarioRuntime creates CompositeVerticalAgentPack.
8. Existing Central Creative Brain runs the normal pipeline.
9. Existing agents return standard V3 schemas.
10. Existing generation, evaluation, refinement, and packaging run.
11. CommercialAssetPack receives scenario audit metadata.
12. UI renders results in the shared ScenarioWorkspace.
```

At no point does the e-commerce pack create a second creative runtime.

---

## 27. Compatibility Mapping to Existing Documents

### 27.1 00_ROOT_RULES.md

Preserved by:

```text
all scenario code lives under V3-owned packages
no V1/V2 imports
no shared product-runtime dependency
```

### 27.2 02_SYSTEM_ARCHITECTURE.md

Preserved by:

```text
Central Creative Brain remains orchestrator
core IR remains provider-neutral
one data flow remains authoritative
```

### 27.3 03_AGENT_AND_MODULE_SPEC.md

Extended by:

```text
ScenarioRuntime composes existing VerticalAgentPack hooks
base agents remain unchanged
new packs remain extensions, not replacements
```

### 27.4 07_SCHEMA_CONTRACTS.md

Preserved by:

```text
no required core fields are renamed or removed
scenario contracts are auxiliary
scenario values initially use existing metadata fields
```

### 27.5 09_RULES_AND_DEFAULTS.md

Preserved by:

```text
existing rules remain core fallback defaults
scenario rules are layered and auditable
General Creative uses the existing defaults unchanged
```

### 27.6 10_BRAND_MEMORY_SPEC.md

Preserved by:

```text
one BrandMemoryAgent remains authoritative
accepted-output update rules remain unchanged
pack-specific state is namespaced and mediated
```

### 27.7 11_EVALUATION_AND_REFINEMENT_SPEC.md

Preserved by:

```text
scenario packs refine evaluation policy through existing hooks
hard failures remain authoritative
one retry and refinement loop remains authoritative
```

### 27.8 12_PROVIDER_INTERFACES.md

Preserved by:

```text
packs request capabilities
GenerationRouterAgent chooses providers
all providers remain optional adapters
```

### 27.9 13_STEP_BY_STEP_DELIVERY_PLAN.md

Preserved by:

```text
this extension begins only after the current baseline is accepted
extension phases do not rename existing delivery waves
full specialization begins only after registry and fallback are stable
```

### 27.10 15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md

Implemented more completely by:

```text
registry-driven UI modes
standard pack manifests
job-scoped specialization context
CompositeVerticalAgentPack adapter
modular capability packages
versioning, lifecycle, isolation, and tests
```

---

## 28. Non-Goals of This Document

This document does not define:

```text
final e-commerce conversion rules
Taobao or Amazon asset specifications
new-media content strategy
private-community message strategy
AI manga storyboard rules
brand-IP character consistency algorithms
provider-specific model prompts
final visual design of every scenario page
external plugin marketplace
multi-pack arbitrary composition
```

Those belong in separate specialization-pack documents after this framework is accepted and implemented.

---

## 29. Non-Negotiable Summary

```text
The existing V3 core remains the only runtime.
General Creative preserves the completed baseline.
The Scenario Hub is registry-driven.
A ScenarioPack is a product-facing specialization package.
A VerticalAgentPack remains the core-facing extension contract.
Capability modules are reusable structured policy contributors.
Scenario packs do not directly call providers.
Scenario packs do not bypass brand memory, evaluation, refinement, or packaging.
No raw prompt-patch architecture is allowed.
No pack-specific generation API is allowed.
All communication uses typed, serializable V3-owned contracts.
Every job pins pack and module versions.
Packs can be independently enabled, disabled, and removed.
Adding a new pack must not require a Central Creative Brain fork.
Detailed specialization begins only after the platform extension passes its gates.
```

---

## Appendix A. Example General Creative Manifest

```json
{
  "manifest_version": "1.0",
  "pack_id": "general_creative",
  "pack_version": "1.0.0",
  "display_name": {
    "zh-CN": "通用创作",
    "en-US": "General Creative"
  },
  "description": {
    "zh-CN": "使用 Alchemy Creative Agent 的通用商业视觉能力。",
    "en-US": "Use the default Alchemy Creative Agent commercial visual pipeline."
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
        "zh-CN": "自动商业视觉系列",
        "en-US": "Auto Commercial Series"
      },
      "status": "active",
      "default_parameters": {},
      "required_modules": [],
      "optional_modules": [],
      "ui_overrides": {},
      "metadata": {}
    }
  ],
  "capability_modules": [],
  "compatibility": {
    "core_contract_min": "1.0",
    "core_contract_max_exclusive": "2.0",
    "manifest_versions": ["1.0"],
    "required_core_capabilities": [],
    "optional_core_capabilities": []
  },
  "ui": {
    "card_icon": "sparkles",
    "card_image_asset": null,
    "card_order": 10,
    "featured": true,
    "route_slug": "general_creative",
    "input_fields": [],
    "quick_actions": [],
    "result_sections": [
      "asset_series",
      "candidate_selection",
      "brand_consistency",
      "generation_summary"
    ],
    "empty_state_examples": [
      "帮我做一组新品推广视觉",
      "沿用上次品牌风格做一个节日活动系列"
    ],
    "metadata": {}
  },
  "tags": ["general", "commercial_visual"],
  "metadata": {}
}
```

---

## Appendix B. Example E-Commerce Stub Manifest

```json
{
  "manifest_version": "1.0",
  "pack_id": "ecommerce",
  "pack_version": "0.1.0",
  "display_name": {
    "zh-CN": "电商特调",
    "en-US": "E-Commerce"
  },
  "description": {
    "zh-CN": "面向网店商品视觉生产的专用场景包。",
    "en-US": "A specialization pack for storefront product visual production."
  },
  "category": "commerce",
  "status": "coming_soon",
  "entrypoint": "alchemy_creative_agent_3_0.app.scenario_packs.packs.ecommerce.pack:EcommerceScenarioPack",
  "bound_vertical_pack": "EcommerceAgentFamily",
  "selection_policy": "explicit_or_auto",
  "modes": [
    {
      "mode_id": "storefront.domestic",
      "display_name": {
        "zh-CN": "国内网店",
        "en-US": "Domestic Storefront"
      },
      "status": "coming_soon",
      "default_parameters": {},
      "required_modules": [],
      "optional_modules": [],
      "ui_overrides": {},
      "metadata": {}
    },
    {
      "mode_id": "storefront.cross_border",
      "display_name": {
        "zh-CN": "跨境网店",
        "en-US": "Cross-Border Storefront"
      },
      "status": "coming_soon",
      "default_parameters": {},
      "required_modules": [],
      "optional_modules": [],
      "ui_overrides": {},
      "metadata": {}
    }
  ],
  "capability_modules": [],
  "compatibility": {
    "core_contract_min": "1.0",
    "core_contract_max_exclusive": "2.0",
    "manifest_versions": ["1.0"],
    "required_core_capabilities": [
      "vertical_agent_pack",
      "evaluation_policy_hook"
    ],
    "optional_core_capabilities": [
      "generation_plan_hook",
      "asset_pack_hook"
    ]
  },
  "ui": {
    "card_icon": "shopping_bag",
    "card_image_asset": null,
    "card_order": 20,
    "featured": true,
    "route_slug": "ecommerce",
    "input_fields": [],
    "quick_actions": [],
    "result_sections": [
      "asset_series",
      "candidate_selection",
      "platform_fit",
      "brand_consistency",
      "generation_summary"
    ],
    "empty_state_examples": [
      "帮我做一组适合国内网店上新的商品视觉",
      "为跨境独立站制作一组产品图"
    ],
    "metadata": {}
  },
  "tags": ["ecommerce", "storefront"],
  "metadata": {
    "framework_stub": true
  }
}
```

---

## Appendix C. Minimal README Index Addition

After adding this file to the repository, add the following line to the existing document index without changing the meaning of earlier entries:

```text
alchemy_creative_agent_3_0/docs/17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
```

Recommended index category:

```text
Scenario platform and modular specialization docs:
```

