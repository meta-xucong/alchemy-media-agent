# 37 V3 Template Interface And Audit Specification

This document defines how V3 templates plug into Project Mode.

The goal is to avoid creating a second module system. Templates are
beginner-facing entries over Scenario Packs.

Current authority note:

```text
Document 42 later reactivates E-Commerce Template inside Project Mode through
the template registry. The early E-Commerce freeze language below remains
historical for the Project Mode foundation phase.

Document 50 is the ownership authority for reusable visual enhancement.
Templates must not create private visual engines. They must declare how they
use the V3 Visual Capability Cluster and consume its project visual snapshots
through the shared ScenarioRuntime/shared-capability path.

Document 51 is the current authority for template-specific consistency policy.
Templates may declare whether they prioritize style, product truth, character
identity, brand assets, or layout, but they must not implement private strong
reference binding, identity locks, output review, retry, or best-output
selection outside the Visual Capability Cluster.

Document 101 supersedes the earlier child-module activation shape. Templates
declare capability requirements, recommendations, prohibitions, and profiles;
they do not directly instantiate child modules. Central Brain proposes the job
activation intent and the shared Activation Planner validates it.
```

---

## 1. Template Definition

In product language:

```text
template = a user-facing way to start a type of project work
```

In implementation:

```text
template = a Project Mode wrapper over a Scenario Pack
```

Current mapping:

```text
general_template -> general_creative
ecommerce_template -> ecommerce
new_media_template -> future Scenario Pack
private_domain_template -> future Scenario Pack
brand_ip_template -> future Scenario Pack
```

Do not create a parallel template runtime.

---

## 2. Template Manifest

Project Mode may add a template manifest layer, but it should be derived from
or linked to Scenario Pack manifests.

Minimum fields:

```text
template_id
scenario_id
display_name
status
project_can_create_jobs
default_project_mode
supported_project_actions
required_project_inputs
optional_project_inputs
context_read_policy
context_write_policy
ui_card
metadata
visual_capability_policy
```

Recommended status values:

```text
active
locked
placeholder
inactive
```

Current phase:

```text
general_template: active
ecommerce_template: locked
new_media_template: locked
private_domain_template: locked
brand_ip_template: locked
```

Status supersession:

```text
After document 42, `ecommerce_template` is active only through Project Mode and
the registry, with product-reference requirements. After document 50, every
active template with visual generation must declare `visual_capability_policy`.
```

Recommended `visual_capability_policy`:

```text
enabled
required_capabilities
recommended_capabilities
optional_capabilities
forbidden_capabilities
capability_profile_overrides
activation_threshold_overrides
reads_project_visual_snapshot
writes_project_visual_snapshot
can_use_brand_memory_visuals
output_review_required
deliverable_role_owner
review_threshold_profile
```

Historical `required_child_modules` and `optional_child_modules` fields may be
read during migration, but new templates must use Doc101 capability IDs and
must not import plugin implementations.

---

## 3. General Template Contract

General Template must declare:

```text
template_id=general_template
scenario_id=general_creative
project_can_create_jobs=true
context_read_policy=selected_outputs_and_uploaded_references
context_write_policy=selected_outputs_only
```

It may support:

```text
first_generation
continue_style
regenerate
select_output
download_output
```

It must not support:

```text
marketplace_listing_set
amazon_copywriting
competitor_analysis
keyword_strategy
ecommerce_export_manifest as a user promise
```

---

## 4. E-Commerce Freeze Contract

During the Project Mode foundation phase, E-Commerce Template must declare:

```text
template_id=ecommerce_template
scenario_id=ecommerce
project_can_create_jobs=false
status=locked
```

Allowed UI:

```text
card visible
short description
coming soon message
optional suggestion to use General Template first
```

Forbidden:

```text
creating project jobs
showing marketplace form fields as active inputs
calling ecommerce pack runtime from Project Mode
allowing direct frontend generation through ecommerce template
```

If direct legacy `/jobs` ecommerce behavior remains for tests during migration,
it must not be reachable from the normal Project Mode UI.

---

## 5. Future Template Activation Rules

A future template can become active only when it has:

1. accepted product spec,
2. Scenario Pack or equivalent V3-owned runtime,
3. Project context read/write policy,
4. beginner-facing UI copy,
5. tests proving it cannot contaminate General Template,
6. tests proving it cannot read V1/V2/Lab state directly,
7. acceptance criteria for generated outputs,
8. a declared `visual_capability_policy`,
9. tests proving reusable visual logic runs through the Visual Capability
   Cluster rather than template-private code.
10. a Doc101 `TemplateCapabilityPolicy` with no undeclared plugin dependency.

No future template may become active by simply adding a card.

---

## 6. Context Policies

Each template must define what it reads and writes.

### 6.1 Read Policy

Allowed read sources:

```text
ProjectRecord
ProjectContextPackage
selected project outputs
uploaded V3 project assets
linked Brand Memory when explicitly selected
template-specific project fields
```

Forbidden read sources:

```text
V1 runtime state
V2 runtime state
Alchemy Lab runtime state
other users' projects
unselected candidates as positive style references
provider secrets
```

### 6.2 Write Policy

Allowed writes:

```text
timeline item
job link
selected output refs
project style summary
rejected direction notes
export refs
memory proposal
```

Forbidden writes:

```text
silent Brand Memory overwrite
cross-project selected output mutation
provider configuration
V1/V2/Lab history
raw debug metadata into beginner UI
```

---

## 7. Code Audit Requirements

When Project Mode code is later implemented, audit:

```text
Project service does not import frontend code
Scenario Packs do not import Project UI code
General Template does not import ecommerce modules
E-Commerce locked state is enforced by backend and frontend
Project job creation uses V3 Product API only
localStorage keys are V3 project-specific
V1/V2/Lab state objects are not shared
normal UI does not display forbidden engineering terms
```

Search terms for audit:

```text
provider
adapter
seed
sampler
prompt compiler
capability module
job id
manifest
product truth lock
marketplace
keywords
competitor
```

Some terms may exist in docs or debug-only code, but they must not appear in
normal Project Mode UI.

---

## 8. Test Requirements

Future code phase must add tests for:

```text
scenario hub returns template card states
only general template can create project jobs
ecommerce template card is locked
project job creation maps general_template to general_creative
project context contains selected outputs only
unselected candidates stay out of positive context
Brand Memory update requires explicit confirmation
Project Mode UI does not call V1/V2/Lab APIs
direct /jobs compatibility still works where required
active templates with visual generation declare visual_capability_policy
visual-capability behavior runs through the shared cluster path
```

---

## 9. Next Implementation Order

The next Codex implementation phase should follow this exact order:

```text
1. Add Project contracts and store.
2. Add Project service and route handlers.
3. Add template registry wrapper that maps general_template -> general_creative.
4. Lock ecommerce_template and future templates in backend contract.
5. Add ProjectContextPackage builder.
6. Add project job creation wrapper around existing V3ProductApiService.
7. Update frontend V3 home to project-first.
8. Add project detail view and General Template workspace inside project.
9. Add selected-output-to-project-context flow.
10. Add continuation flow that creates a new project job.
11. Update tests and audits.
```

Stop conditions:

```text
do not implement E-Commerce generation in Project Mode
do not remove existing /jobs compatibility
do not rewrite provider adapters
do not share V1/V2/Lab state
do not silently apply Brand Memory updates
```

Minimum verification commands should include:

```text
python -m pytest alchemy_creative_agent_3_0/tests -q
python -m pytest tests/test_v3_commercial_frontend_shell.py -q
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
node --check src_skeleton/app/static/app.js
git diff --check
```

If frontend behavior changes materially, also run a browser click-through for:

```text
V3 home
new project
project detail
General Template generation
select result
continue same style
locked E-Commerce card
```

---

## 10. Documentation Audit Requirements

Before implementation starts, audit documents `29` to `37`:

1. Document `32` must be the highest Project Mode authority.
2. Documents `30` and `31` must state that job-history-first UI is superseded.
3. E-Commerce must be described as locked/frozen in Project Mode foundation.
4. General Template must be described as the only active project-generation
   template.
5. No document may imply that Project Mode rewrites the V3 foundation.

---

## 11. Acceptance Criteria

The template interface is correct when:

1. Product users see templates.
2. Code continues to use Scenario Packs.
3. Project context rules are explicit.
4. General Template is active.
5. E-Commerce and future templates are locked.
6. Activating a future template requires its own accepted spec and tests.
