# 24 V3 Shared Capability Modules From V1/V2 Migration Spec

> **Current-status note (Docs 111, 113, 134–135):** Shared capabilities may
> contribute evidence, hard truth, admission and review obligations only. Any
> older prompt fragments, keyword-derived creative decisions, recipe fields or
> retry prose in this document are historical compatibility material and must
> not become renderer language for a new V3 Job.

This document defines how to migrate the valuable V1/V2 capabilities into V3 without contaminating the V3 architecture.

The core decision:

V1/V2 advantages should not be copied directly into the V3 central brain, and they should not be buried only inside the E-Commerce agent. They should become V3-owned shared capability modules. E-Commerce will be their first heavy user, but General Creative and future vertical packs can reuse them safely.

This phase should be implemented after `23` is complete and before building the full E-Commerce Scenario Pack in `26`.

## Document 50/51 Refinement

Doc101 activation refinement:

```text
The shared registry remains the module foundation, but registered does not mean
executed. Central Brain proposes capabilities through a structured activation
intent; the Doc101 Activation Planner resolves a frozen plan; only active
modules execute and contribute to prompt, review, and retry. New plugins use
manifests and must not add independent keyword-only activation paths.
```

Document `50` is the authority for the next ownership upgrade of this layer.
Document `51` is the current authority for the commercial visual-consistency
upgrade built on top of that ownership model.

This document created the V3-owned shared capability foundation. Document `50`
does not replace that foundation. It wraps and upgrades it. Document `51`
adds the next required child modules:

```text
app/shared_capabilities
  -> Visual Capability Cluster
      -> child modules migrated or rewritten from V1/V2 ideas
      -> strong reference binding
      -> identity/product/brand locks
      -> visual review
      -> auto retry
      -> best-output selection
```

Authoritative refinement:

```text
1. V1/V2 modules remain references only.
2. Existing V3 shared capabilities become child modules under one reusable
   Visual Capability Cluster when visual enhancement work resumes.
3. Reusable visual grammar, visual memory, reference binding, consistency
   checks, and output visual review must not be scattered across Central Brain,
   templates, Project Mode, PromptCompilerAgent, or providers.
4. The cluster is V3-native and shared by General Template, E-Commerce Template,
   and future templates through the ScenarioRuntime/shared-capability path.
5. Provider routing and image generation remain outside shared capabilities.
```

If any future implementation choice conflicts with this document, use
document `50` for visual ownership and cluster dispatch, and document `51` for
strong references, identity/product/brand locks, output review, retry patches,
best-output selection, and Lovart-gap commercial consistency requirements.

## Source Code To Reference

V2 source root:

`custom_media_agent_2_0/app/`

Important source files:

| V1/V2 Source | High-Value Capability | V3 Destination |
| --- | --- | --- |
| `schemas.py` | Asset roles, constraint strengths, asset briefs, prompt plans, case profiles, binding plans | Rewrite into V3 shared contracts only where needed. Do not import old schemas. |
| `services/uploaded_asset_vision.py` | Uploaded image analysis, role suggestion, dimensions, palette, brightness, identity requirements | `AssetRoleAnalyzer` |
| `services/asset_binding.py` | Asset role binding, template locks, provider input image planning, review expectations | `AssetBindingPlanner` and `ReferenceConditioningPlanner` |
| `services/case_intelligence.py` | Case retrieval, case profile building, feature tags, semantic matching | `CaseLibraryRetriever` |
| `services/visual_grammar_lock.py` | Composition, hierarchy, mood, lighting, text/information preservation | `VisualGrammarLockModule` and `InformationIntegrityLockModule` |
| `services/prompting.py` | Prompt plan composition, negative prompt merging, visual grammar application | `PromptConstraintCompiler` |
| `services/visual_review_agent.py` | Output review boundary, live vision fallback pattern | `OutputReviewModule` |
| `services/generation.py` | Provider routing patterns, output storage, fallback behavior | Reference only. Do not migrate provider calls into shared capabilities. |
| History/favorites/reference asset services | User preference and continuation patterns | `HistoryReferenceModule` |

## Target Package

Add:

`app/shared_capabilities/`

Suggested structure:

| File | Responsibility |
| --- | --- |
| `contracts.py` | Shared capability request/result contracts and normalized asset/reference contracts. |
| `base.py` | Base capability interface. |
| `registry.py` | Capability registry and execution ordering. |
| `asset_role_analyzer.py` | Uploaded asset analysis and role suggestions. |
| `asset_binding_planner.py` | Reference image binding and conditioning strategy. |
| `case_library.py` | Case retrieval and visual inspiration extraction. |
| `visual_grammar_lock.py` | Composition/style/layout locking from references or templates. |
| `information_integrity.py` | Product/text/claim preservation constraints. |
| `prompt_constraint_compiler.py` | Converts capability outputs into V3 prompt/layout/evaluation constraints. |
| `output_review.py` | Visual review and refinement hints. |
| `history_reference.py` | Reuse selected outputs and brand memory as future references. |
| `visual_cluster/contracts.py` | Document `50` target: cluster-level visual contracts such as `VisualGrammarProfile` and `ProjectVisualGrammarSnapshot`. |
| `visual_cluster/orchestrator.py` | Document `50` target: one logical dispatch point for visual child modules. |
| `visual_cluster/consistency_guard.py` | Document `50` target: project-continuation visual drift checks. |
| `visual_cluster/quality_reviewer.py` | Document `50` target: project-aware generated-output visual review. |

## Non-Negotiable Migration Rules

1. Do not import V1/V2 modules at runtime.
2. Do not reuse V1/V2 schema objects directly.
3. Do not introduce provider-specific controls into product API contracts.
4. Do not place capability-specific logic inside `CentralCreativeBrain`.
5. Do not make E-Commerce the owner of these modules.
6. Every capability result must be serializable, auditable, and optional.
7. Capability failures must degrade gracefully unless the Scenario Pack marks the capability as required.
8. Shared capabilities must output product-level constraints, not raw provider parameters.

## Shared Capability Base Contract

Define a small common contract:

| Contract | Required Fields |
| --- | --- |
| `CapabilityInput` | job id, scenario id, user input, campaign, brand context, uploaded assets, product profile, prior capability outputs |
| `CapabilityResult` | module id, version, status, confidence, facts, constraints, warnings, audit trail |
| `CapabilityWarning` | code, message, severity, affected asset or field |
| `CapabilityConstraint` | target stage, constraint type, strength, value, source evidence |

Target stages should be V3-level:

1. intent
2. commercial brief
3. creative direction
4. series plan
5. layout plan
6. prompt compilation
7. evaluation
8. export

Do not expose provider-stage concepts as public capability targets.

## Module 1 - AssetRoleAnalyzer

Purpose:

Analyze uploaded images and infer how they should be used: product reference, style reference, logo, background, composition reference, negative reference, face reference, or color reference.

Reference:

`services/uploaded_asset_vision.py`

V3 output:

1. asset dimensions
2. orientation
3. image quality hints
4. palette summary
5. brightness/contrast summary
6. suggested asset role
7. confidence
8. identity preservation needs
9. product preservation needs
10. warnings for poor input quality

Implementation steps:

1. Recreate only the deterministic image inspection logic first.
2. Normalize V2 role names into a V3 enum.
3. Return warnings instead of raising errors for weak images.
4. Add optional live vision hooks later, behind a feature flag.
5. Add tests using small fixture images.

Audit:

1. A missing file returns a product-level capability error.
2. A valid image always produces a role suggestion or `unknown_reference`.
3. No provider call is made.
4. The output can be stored in job metadata.

## Module 2 - AssetBindingPlanner

Purpose:

Decide how uploaded assets should constrain or guide the generation.

Reference:

`services/asset_binding.py`

V3 output:

1. reference asset binding plan
2. preservation strength
3. allowed transformations
4. forbidden transformations
5. placement intent
6. review expectations
7. frame strategy

Implementation steps:

1. Port the role-priority idea from V2.
2. Replace V2 provider input image objects with V3 `ReferenceCondition` records.
3. Support multiple roles per job.
4. Let Scenario Packs choose required vs optional bindings.
5. Add conflict handling when two assets compete for the same role.

Audit:

1. Product reference cannot be silently treated as pure style reference.
2. Logo reference cannot be distorted unless the Scenario Pack explicitly allows stylization.
3. Background reference cannot override product truth.
4. Binding plan is visible in job audit metadata.

## Module 3 - CaseLibraryRetriever

Purpose:

Bring back V1/V2's useful "case intelligence" pattern: retrieve comparable creative cases, extract visual grammar, and help the agent avoid starting from a blank prompt.

Reference:

`services/case_intelligence.py`

V3 output:

1. selected cases
2. match reasons
3. style tags
4. composition tags
5. use-case tags
6. category tags
7. reusable visual signals
8. non-reusable elements

Implementation steps:

1. Build a V3 `CaseProfile` contract instead of reusing the V2 one.
2. Store cases in a small local case index first.
3. Retrieve by scenario id, category, user input, uploaded asset roles, and platform profile.
4. Return case signals to `VisualGrammarLockModule`.
5. Keep raw prompt examples internal; product API should not expose prompt hacking details.

Audit:

1. Retrieved cases must include match reasons.
2. If no case is found, the pipeline must continue.
3. E-Commerce cases must not leak into General Creative unless the user explicitly selects an e-commerce-like scenario.

## Module 4 - VisualGrammarLockModule

Purpose:

Preserve high-value visual structure from a reference, template, or selected case while allowing product/category/content replacement.

Reference:

`services/visual_grammar_lock.py`

V3 output:

1. composition framework
2. spatial hierarchy
3. main subject placement
4. lighting logic
5. background density
6. typography/information treatment
7. mood and design language
8. replaceable elements
9. non-replaceable elements
10. conflict policy

Implementation steps:

1. Port the idea, not the exact V2 schema.
2. Connect to V3 `LayoutPlan` and `PromptCompilation` as constraints.
3. Allow Scenario Packs to set lock strength.
4. Add a default mode for General Creative and a stricter mode for E-Commerce product sets.
5. Store the final lock contract in run metadata.

Audit:

1. Product shape and key visible attributes cannot be overridden by style grammar.
2. Text/information blocks are treated as semantic obligations, not decorative noise.
3. If visual grammar conflicts with platform rules, platform rules win.

## Module 5 - InformationIntegrityLockModule

Purpose:

Protect product facts, visible text, listing claims, material facts, sizes, logos, and compliance-sensitive details.

Reference:

`services/visual_grammar_lock.py`

V3 output:

1. must-preserve product facts
2. claims requiring evidence
3. forbidden claims
4. text that must appear exactly
5. text that may be paraphrased
6. product attributes that cannot change
7. review checklist

Implementation steps:

1. Extract fact-preservation logic into a standalone V3 module.
2. Let Scenario Packs provide stricter policies.
3. In E-Commerce, connect this module to `ProductTruthLock`.
4. In General Creative, use it only for user-provided text/logo/product facts.

Audit:

1. The module must not invent certifications, patents, guarantees, or performance numbers.
2. Claims without evidence must be downgraded to softer language or flagged.
3. Output review must check the same facts later.

## Module 6 - PromptConstraintCompiler

Purpose:

Translate capability outputs into V3 prompt, layout, and evaluation constraints.

Reference:

`services/prompting.py`

V3 output:

1. prompt constraints
2. negative constraints
3. layout constraints
4. evaluation checklist additions
5. prompt audit trail

Implementation steps:

1. Do not port V2 `ImagePromptPlan` wholesale.
2. Add a compiler that receives V3 capability results and returns V3-native constraint fragments.
3. Make `PromptCompilerAgent` consume those fragments through existing hooks or a narrow extension point.
4. Add tests proving constraints are merged deterministically.

Audit:

1. Capability constraints must not override user intent silently.
2. Negative prompts should be deduplicated.
3. Prompt output remains explainable through metadata.

## Module 7 - OutputReviewModule

Purpose:

Review generated candidates against product intent, visual grammar, information integrity, and scenario-specific rules.

Reference:

`services/visual_review_agent.py`

V3 output:

1. score deltas
2. detected issues
3. missing obligations
4. refinement instructions
5. pass/fail flags for scenario-critical checks

Implementation steps:

1. Start with deterministic metadata-based review.
2. Add live vision review later behind feature flags.
3. Connect review outputs to central brain's existing evaluation/refinement loop.
4. E-Commerce can later add strict product truth and platform compliance checks.

Audit:

1. Review failure must not crash job packaging.
2. Critical failures should trigger regeneration or mark the candidate as not recommended.
3. Review reasons must be visible in candidate metadata.

## Module 8 - HistoryReferenceModule

Purpose:

Convert selected outputs, favorites, and brand memory into reusable reference context.

Reference:

V1/V2 history, favorites, and reference asset patterns.

V3 output:

1. reusable style references
2. selected brand visual preferences
3. rejected visual patterns
4. continuation candidates
5. memory update proposals

Implementation steps:

1. Use the existing V3 brand memory update path as the destination.
2. Add a module that can assemble prior selections into a context package.
3. Keep user-facing controls simple: continue brand style, continue this image, avoid this direction.

Audit:

1. The user can disable history use.
2. Rejected styles should not reappear as positive references.
3. Private user assets should not leak across brands/jobs.

## Provider And Billing Patterns

Do not migrate V2 provider routing or billing code into shared capabilities.

Allowed:

1. Read V2 provider routing code to understand fallbacks and output storage patterns.
2. Recreate any needed behavior inside V3 provider adapters later.
3. Keep billing and provider calls outside shared capabilities.

Forbidden:

1. Shared capability calls image provider.
2. Shared capability accepts raw provider parameters from product API.
3. Shared capability writes provider artifacts directly.

## Migration Steps

### Step 0 - Add Empty Package And Contracts

Create `app/shared_capabilities` with base contracts and registry.

Tests:

1. Registry can register a fake capability.
2. Registry can run capabilities in deterministic order.
3. Failed optional capability returns warning.
4. Failed required capability returns product-level error.

### Step 1 - Port AssetRoleAnalyzer

Reference only:

`services/uploaded_asset_vision.py`

Tests:

1. Detect dimensions/orientation.
2. Produce role suggestion.
3. Return low-quality image warning.
4. No provider call.

### Step 2 - Port AssetBindingPlanner

Reference only:

`services/asset_binding.py`

Tests:

1. Product reference receives stronger preservation than style reference.
2. Logo reference receives exactness warning.
3. Conflicting roles produce a warning.

### Step 3 - Port CaseLibraryRetriever

Reference only:

`services/case_intelligence.py`

Tests:

1. Query returns ranked cases with match reasons.
2. Empty case index degrades gracefully.
3. Scenario filter prevents unrelated vertical cases from leaking.

### Step 4 - Port VisualGrammarLockModule

Reference only:

`services/visual_grammar_lock.py`

Tests:

1. Generates layout constraints from case/reference signals.
2. Does not override product truth.
3. Strength levels change strictness predictably.

### Step 5 - Port InformationIntegrityLockModule

Tests:

1. Preserves exact required text.
2. Flags unsupported claims.
3. Adds review obligations.

### Step 6 - Add PromptConstraintCompiler

Reference only:

`services/prompting.py`

Tests:

1. Merges constraints deterministically.
2. Deduplicates negative constraints.
3. Adds audit metadata.

### Step 7 - Add OutputReviewModule

Reference only:

`services/visual_review_agent.py`

Tests:

1. Metadata-only review works.
2. Critical issue produces refinement hints.
3. Optional live vision can be disabled.

### Step 8 - Add HistoryReferenceModule

Tests:

1. Selected candidate becomes reusable reference.
2. Rejected visual direction is stored as avoidance hint.
3. Brand scoping is respected.

### Step 9 - Integrate With ScenarioRuntime

Implementation:

1. Scenario Packs declare which capabilities are allowed.
2. ScenarioRuntime executes allowed capabilities.
3. Capability outputs become central brain context.
4. Central brain remains mostly unchanged.

Tests:

1. General Creative can run with no capabilities.
2. General Creative can run with optional asset analysis.
3. Placeholder E-Commerce does not execute full commerce modules before `26`.

## Final Audit Before Moving To `25` And `26`

Codex must verify:

1. No runtime imports from `custom_media_agent_2_0`.
2. All new contracts are V3-owned.
3. Product API remains simple.
4. Low-level provider controls remain rejected.
5. Shared capability outputs are serializable.
6. Capability warnings are visible in job/run metadata.
7. Full test suite passes.
