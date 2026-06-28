# 23 V3 Foundation Gap Audit and Completion Supplement

Audited on: 2026-06-28

This document is an additive supplement to `00`-`22`. It exists because the V3 framework already has a working foundation, but the later Scenario Pack / General Creative / E-Commerce specialization documents assume several platform pieces that are not fully implemented yet.

The rule for future Codex work is:

1. Complete the V3 foundation gaps in this document first.
2. Then add the V1/V2-derived shared capability modules in `24`.
3. Then finish General Creative integration deltas in `25`.
4. Then implement the E-Commerce Scenario Pack in `26`.

Do not jump directly from the current minimal V3 foundation into a full e-commerce agent. The e-commerce agent should be a Scenario Pack that consumes shared V3 capabilities, not a pile of V1/V2 code copied into the central brain.

## Current Implementation Snapshot

The current codebase is in:

`alchemy_creative_agent_3_0/`

The full test suite currently passes:

`81 passed`

That is a good baseline. All future phases must preserve this baseline unless a test is intentionally replaced by a stricter equivalent.

## What Is Already Done

| Area | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Core V3 rules and schema direction | Done enough | `docs/00`-`16`, `app/creative_core`, `app/schemas.py` | The core principle is strong: product API stays simple, central brain owns orchestration, providers stay behind adapters. |
| Central brain orchestration | Done enough | `app/creative_core/central_brain.py` | Intent, commercial strategy, vertical pack selection, creative direction, series planning, layout, prompt compilation, routing, evaluation, and packaging are already connected. |
| Vertical agent hook mechanism | Done enough | `app/vertical_agents/base.py`, `registry.py` | Scenario-specific refinement hooks exist and are test-covered. |
| Lightweight e-commerce vertical family | Done as placeholder/specialization seed | `app/vertical_agents/ecommerce_pack.py` | It refines brief, plan, layout, prompt, and evaluation policy, but it is not a full e-commerce Scenario Pack. |
| Product API minimal UX | Done enough | `app/product_api/contracts.py`, `service.py` | Create job, run generation loop, select candidate, and brand update flows exist. |
| App shell namespace | Done enough | `app/app_shell/routes.py`, `navigation.py`, `minimal_ui.py` | V3 route namespace and minimal UI contracts exist. |
| Safety boundary against low-level generation controls | Done | `CreateCreativeJobRequest` validation and tests | User-facing requests reject provider-level controls such as seed/sampler/LoRA/ControlNet. |
| Regression tests | Done enough | `tests/` | Current tests protect product API, V3 boundaries, and vertical specialization behavior. |

## What Is Not Yet Done

| Missing Area | Related Original Docs | Why It Matters |
| --- | --- | --- |
| Scenario Pack directory and manifest layer | `17`, `18`, `21`, `22` | Later docs talk about Scenario Hub, General Creative, and future vertical packs, but code does not yet have a dedicated `app/scenario_packs` layer. |
| Scenario Runtime | `17`, `18`, `20`, `21` | The central brain can run plans, but there is no runtime layer that normalizes scenario selection, capability activation, and scenario-specific policy before entering the brain. |
| General Creative full product workspace | `18`, `19`, `20` | Current UI/API is minimal. The full workspace, presets, history continuation, and common-scene closure are not implemented. |
| Quick-start preset system | `19` | Presets are specified in docs but not represented as runtime objects, manifests, or UI-facing contracts. |
| Full Job/Run/Candidate/Revision/Export record model | `18`, `20` | Current `ProductJobRecord` is intentionally small. Later product features need richer lifecycle records. |
| Shared capability modules | New `24` | V1/V2 have valuable logic for asset analysis, binding, visual grammar locks, case retrieval, and review. V3 currently has no clean place for these capabilities. |
| Full e-commerce Scenario Pack | New `26` | Current `EcommerceAgentFamily` is a hook-level specialization only. It cannot yet produce mature e-commerce image sets from product images + simple prompt. |
| Documentation execution order | `05`, `13`, `21`, `22` | The previous docs correctly avoided implementing e-commerce too early, but they did not explicitly insert a V1/V2 capability migration phase before vertical specialization. |

## Corrected Development Order

Use this order from now on:

### Phase A - Freeze The Current Baseline

Purpose: make sure current V3 remains stable before adding larger platform pieces.

Steps:

1. Run the full current test suite.
2. Record the passing baseline in the implementation log.
3. Do not modify central brain behavior yet.
4. Do not add e-commerce-specific logic to General Creative or central brain.

Acceptance:

1. Existing tests still pass.
2. No new runtime dependency on V1/V2 code exists.

### Phase B - Complete The Scenario Pack Foundation

Purpose: turn the Scenario Pack idea from documentation into an actual V3 platform layer.

Add:

`app/scenario_packs/`

Suggested files:

| File | Responsibility |
| --- | --- |
| `contracts.py` | Scenario pack manifest, scenario selection request, preset contract, capability declaration, UI affordance contract. |
| `base.py` | Base scenario pack interface. It should adapt product input into central-brain-ready context and declare allowed capabilities. |
| `registry.py` | Registry for active, beta, and placeholder scenario packs. |
| `general.py` | General Creative active pack. |
| `placeholders.py` | E-Commerce, New Media, Private Domain, Brand IP placeholder manifests until their real packs are implemented. |

Implementation rules:

1. Scenario Pack objects may prepare context, choose defaults, expose presets, and enable shared capabilities.
2. Scenario Packs must not call image providers directly.
3. Scenario Packs must not own low-level generation settings.
4. Scenario Packs must call the central brain through stable product-level contracts.
5. The registry must make General Creative the only fully active scenario until `26` is implemented.

Acceptance:

1. A request with no scenario selection routes to General Creative.
2. A request selecting a placeholder scenario returns a clear product-level "not active yet" state or routes to a safe placeholder, depending on UI needs.
3. Existing tests still pass.
4. New tests cover registry defaults and placeholder behavior.

### Phase C - Add Scenario Runtime

Purpose: introduce the layer that joins product API, Scenario Packs, shared capabilities, and central brain.

Add:

`app/scenario_runtime/`

Suggested files:

| File | Responsibility |
| --- | --- |
| `runtime.py` | Main ScenarioRuntime entry point. |
| `context.py` | Runtime context assembled from product request, scenario selection, brand memory, uploaded assets, and optional capability outputs. |
| `capability_runner.py` | Deterministic runner that executes enabled shared capability modules in declared order. |
| `errors.py` | Product-facing errors for inactive packs, invalid scenario parameters, and capability failures. |

Runtime flow:

1. Product API receives a simple request.
2. Product API passes request to ScenarioRuntime.
3. ScenarioRuntime resolves Scenario Pack.
4. ScenarioRuntime validates scenario parameters.
5. ScenarioRuntime runs allowed shared capabilities.
6. ScenarioRuntime invokes central brain with enriched product-level context.
7. Central brain remains the main orchestrator.

Acceptance:

1. General Creative requests still work with minimal input.
2. Capability failure returns a recoverable product-level error.
3. No provider-specific fields appear in public request contracts.
4. Tests prove central brain can still be invoked without ScenarioRuntime for lower-level unit coverage if needed.

### Phase D - Extend Product API Contracts Carefully

Purpose: support scenario selection and richer job lifecycle without breaking the simple UX.

Current contract:

`CreateCreativeJobRequest`

It currently has:

1. `user_input`
2. `brand_id`
3. `continue_style_from_brand_id`
4. `campaign`
5. `metadata`

Add only product-level fields:

| Field | Type | Notes |
| --- | --- | --- |
| `scenario_selection` | Optional object | Contains scenario id, preset id, mode id, platform profile, and simple user-facing parameters. |
| `uploaded_asset_ids` | Optional list | References assets already uploaded through an upload service. Do not place binary data here. |
| `product_profile` | Optional object | High-level product/category/spec facts. No provider controls. |

Do not add:

1. seed
2. sampler
3. LoRA
4. ControlNet
5. IP adapter scale
6. node graph
7. raw model name
8. provider-specific image strength

Acceptance:

1. Existing rejection tests for low-level controls still pass.
2. New tests prove scenario selection is accepted only when product-level.
3. Requests without scenario selection continue to work.

### Phase E - Upgrade Job Lifecycle Records

Purpose: prepare for General Creative and E-Commerce workflows that need selectable candidates, revisions, exports, and history continuation.

Current:

`ProductJobRecord` is minimal and in-memory.

Add or prepare richer records:

| Record | Purpose |
| --- | --- |
| `JobRecord` | Stable job-level request, scenario, brand, and status. |
| `RunRecord` | One planning/generation run under a job. |
| `CandidateRecord` | One output candidate with scoring, prompt plan id, provider artifact metadata, and review summary. |
| `CandidateSelectionRecord` | User selection and reason. |
| `RevisionRecord` | Follow-up edit or regeneration instruction. |
| `ExportRecord` | Export package, target platform, dimensions, naming, and delivery state. |

Implementation rule:

The first implementation can remain in-memory, but the data shape should be storage-ready.

Acceptance:

1. Existing product API responses remain simple.
2. Internal records can represent multiple runs per job.
3. Candidate selection can update brand memory through the existing central brain mechanism.

### Phase F - Bring Docs And Tests Back Into Alignment

Purpose: avoid the docs describing a product the code does not have.

Required updates:

1. Update `README.md` document order.
2. Mark `23`-`26` as required reading before E-Commerce development.
3. Add tests for Scenario Pack registry, runtime default behavior, scenario selection validation, and lifecycle records.
4. Re-run the full test suite.

Acceptance:

1. Current tests pass.
2. New Scenario Pack tests pass.
3. No docs claim E-Commerce is active before `26` is implemented.

## Audit Checklist For Codex Before Moving To `24`

Codex must verify:

1. `app/scenario_packs` exists and has tests.
2. `app/scenario_runtime` exists and has tests.
3. General Creative is the default active scenario.
4. E-Commerce is still placeholder-only unless explicitly implementing `26`.
5. Product API remains simple.
6. Public contracts still reject low-level generation controls.
7. Central brain remains provider-agnostic and scenario-neutral.
8. V1/V2 code is not imported at runtime.
9. Full test suite passes.
