# 33 V3 Project Mode Compatibility And Migration Specification

This document defines how to add Project Mode without a large V3 rewrite.

It is an implementation bridge between the current job/history V3 product API
and the target project-first user experience defined in document `32`.

---

## 1. Current State To Preserve

The current V3 implementation already has valuable foundations:

```text
V3ProductApiService
ProductJobRecord
InMemoryProductJobStore
CreateCreativeJobRequest
ProductJobStatus
ScenarioRuntime
ScenarioPackRegistry
ScenarioPackManifest
GeneralCreativeScenarioPack
EcommerceScenarioPack
V3 upload and generated-output stores
shared_capabilities
BrandProfileService
```

Project Mode must reuse these. It must not rebuild the runtime pipeline.

---

## 2. Migration Principle

Use a wrapper-first migration:

```text
phase 1: add Project records and project APIs
phase 2: make V3 home read projects instead of raw job history
phase 3: create jobs through projects while preserving /jobs compatibility
phase 4: build ProjectContextPackage from selected outputs
phase 5: deprecate raw history as a primary UI object
```

Do not migrate all historical data at once. Compatibility adapters are allowed.

---

## 3. Additive Components

Add these V3-owned components in a future code phase.

### 3.1 Project Store

Current implementation:

```text
.media_storage/v3_projects/
```

`PersistentProjectStore` stores each project as local JSON and stores each
project timeline beside it. This keeps V3 project cards, selected outputs, and
timeline summaries available after a local service restart. The implementation
is intentionally small and replaceable by a database later.

Unit tests may still inject `InMemoryProjectStore` so test runs do not write
project history into the working tree.

Responsibilities:

```text
create project
read project
list recent projects
append timeline events
link jobs to project
update selected outputs
update project summary
store project context snapshots
```

### 3.2 Project API

Add a Project API layer under the existing V3 API namespace:

```text
/api/v3/creative-agent/projects
/api/v3/creative-agent/projects/{project_id}
/api/v3/creative-agent/projects/{project_id}/jobs
/api/v3/creative-agent/projects/{project_id}/timeline
```

These routes should call existing Product API job services for job creation and
generation. They should not duplicate the creative runtime.

### 3.3 Project Context Builder

Add a builder that converts project state into runtime-ready context:

```text
ProjectRecord
selected outputs
uploaded references
project style summary
rejected directions
linked brand memory
```

Output:

```text
ProjectContextPackage
```

This package should be passed through product-level metadata or an explicit
future field. It must not expose provider parameters.

### 3.4 Project History Adapter

During migration, existing job history can be surfaced as compatibility
projects.

Rules:

```text
one raw job may appear as a lightweight imported project card
imported project cards must be clearly V3-owned
clicking an imported job should create or hydrate a project shell
old localStorage job snapshots remain fallback only
```

---

## 4. What Must Not Change

Do not change these contracts as part of Project Mode foundation work unless a
later implementation document explicitly requires it:

```text
ScenarioSelection
ScenarioPackManifest
ScenarioRuntime.plan_job
ProductJobRecord lifecycle semantics
provider adapter interfaces
shared capability base contracts
BrandProfile schema
existing /api/v3/creative-agent/jobs behavior
```

Project Mode may add optional fields or metadata, but existing job calls should
continue to work for tests and backward compatibility.

---

## 5. E-Commerce Freeze During Migration

Current code may have an active E-Commerce Scenario Pack. During the Project
Mode implementation phase, product behavior must treat E-Commerce as frozen.

Required behavior:

```text
E-Commerce card may remain visible
E-Commerce route may show a coming-soon or locked state
E-Commerce must not create project jobs
direct project job creation with scenario_id=ecommerce must be rejected
legacy /jobs ecommerce behavior may remain only if not reachable from normal Project Mode UI
```

Reason:

```text
Project Mode and General Template continuity must become stable first.
E-Commerce requires stricter product-truth, market, and suite consistency rules.
```

---

## 6. Migration Phases

### Phase A - Documentation Lock

Create documents `32` to `37` and update documents `29`, `30`, and `31`.

No code changes.

### Phase B - Project Data Layer

Add Project contracts, store, service, and route handlers.

Verify:

```text
project can be created
projects can be listed
project detail can be read
timeline can be appended
existing jobs still work
```

### Phase C - Project-First Frontend

Replace V3 first screen behavior:

```text
home -> create project / project cards
project detail -> template cards
template card -> General Template workspace inside project
```

Do not remove existing V3 workspace code immediately. Wrap it with project
state first.

### Phase D - General Template Context

Make General Template job creation require a project id from the frontend.

Project-created jobs must include:

```text
project_id
template_id=general_template
scenario_id=general_creative
project context snapshot id or package
```

Existing direct `/jobs` calls remain available for API compatibility and tests.

### Phase E - History Deprecation

Raw job history becomes secondary:

```text
project cards are primary
job timeline is inside project detail
old job history is fallback/import source
```

---

## 7. Backward Compatibility Rules

1. Existing V3 tests for job creation should pass unless they explicitly assert
   old home/history UX.
2. Existing generated output records remain valid.
3. Existing uploaded asset records remain valid.
4. Existing Brand Memory files remain valid.
5. Existing localStorage job history can be read as a fallback, but new frontend
   state must use V3 project-specific keys.
6. V1, V2, and Alchemy Lab runtime state must not be read by Project Mode.

---

## 8. Recommended Code Placement

Recommended future package structure:

```text
alchemy_creative_agent_3_0/app/project_mode/
  contracts.py
  store.py
  service.py
  context_builder.py
  route_handlers.py
  template_registry.py
```

The package may call:

```text
V3ProductApiService
ScenarioPackRegistry
BrandProfileService
V3UploadedAssetStore
V3GeneratedOutputStore
```

The package must not call:

```text
V1 APIs
V2 APIs
Alchemy Lab APIs
provider adapters directly
frontend JavaScript state
```

---

## 9. Implementation Audit Checklist

Before any Project Mode code phase is accepted, verify:

```text
Project layer imports Product API, not the other way around
Scenario Pack code does not import Project UI code
provider adapters do not know about projects
shared capabilities remain optional and scenario-driven
Brand Memory updates remain confirmation-based
E-Commerce cannot create project jobs in the frozen phase
General Template does not import E-Commerce rules
```

---

## 10. Acceptance Criteria

This migration spec is satisfied when a future code phase can implement Project
Mode by adding a project layer around the existing runtime, without rewriting
the V3 creative core or provider adapters.
