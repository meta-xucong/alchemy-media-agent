# 41 V3 Template Manifest Registry And Activation Gate Spec

This document defines the Project Mode template registry and activation gate.

It prevents future templates from becoming clickable visual cards without a real
backend contract, project context policy, tests, and beginner-facing workspace.

## 1. Purpose

V3 architecture is:

```text
V3 Foundation
  -> Project
      -> Template
          -> Scenario Pack
              -> Job
```

Templates are user-facing entrances. Scenario Packs are runtime implementations.

The registry connects them without creating a parallel runtime.

## 2. Template Manifest Contract

Every Project Mode template must declare:

```text
template_id: string
display_name: string
short_description: string
scenario_pack_id: string
status: "active" | "locked" | "placeholder" | "disabled"
allowed_project_types: list[string]
required_inputs: list[TemplateInputField]
optional_inputs: list[TemplateInputField]
context_read_policy: TemplateContextReadPolicy
context_write_policy: TemplateContextWritePolicy
output_summary_policy: TemplateOutputSummaryPolicy
frontend_workspace: string
activation_requirements: list[string]
test_requirements: list[string]
```

### 2.1 TemplateInputField

Required fields:

```text
field_id
label
field_type
required
beginner_copy
advanced
```

Field types:

```text
text
textarea
image_upload
select
multi_select
toggle
number
```

Advanced fields must be hidden by default.

### 2.2 Context Read Policy

Required fields:

```text
reads_project_goal: bool
reads_selected_outputs: bool
reads_uploaded_references: bool
reads_negative_feedback: bool
reads_brand_memory: "never" | "explicit_user_selected" | "automatic_if_project_bound"
template_specific_fields: list[string]
```

### 2.3 Context Write Policy

Required fields:

```text
can_create_jobs: bool
can_select_outputs: bool
can_create_reference_assets: bool
can_create_feedback: bool
can_propose_brand_memory: bool
template_specific_project_fields: list[string]
```

### 2.4 Output Summary Policy

Required fields:

```text
summary_sections: list[string]
image_slot_model: string | null
user_visible_fields: list[string]
hidden_debug_fields: list[string]
```

## 3. Required Initial Registry State

The registry must start as:

```text
general_template:
  scenario_pack_id: general_creative
  status: active

ecommerce_template:
  scenario_pack_id: ecommerce
  status: locked

new_media_template:
  scenario_pack_id: future_new_media
  status: placeholder

private_domain_template:
  scenario_pack_id: future_private_domain
  status: placeholder

brand_ip_template:
  scenario_pack_id: future_brand_ip
  status: placeholder
```

Only `general_template` can create project jobs in the current phase.

## 4. Backend Enforcement

The backend must enforce template status.

Rules:

```text
active -> may create project jobs if scenario pack is available
locked -> visible but cannot create jobs
placeholder -> visible or hidden by product choice, cannot create jobs
disabled -> hidden or unavailable, cannot create jobs
```

If frontend tries to create a job for a locked template, backend returns a
controlled error:

```text
template_locked
```

The response must include beginner-facing copy:

```text
这个模板还在准备中。当前可以先用通用模板继续做图。
```

## 5. Registry Location

Recommended code location:

```text
alchemy_creative_agent_3_0/app/project_mode/templates/
  __init__.py
  registry.py
  contracts.py
  general_template.py
  ecommerce_template.py
```

This location is a recommendation. If the existing codebase has a clearer V3
Project Mode structure, follow the existing pattern.

## 6. Relationship To Scenario Pack Registry

Template registry must map to the existing Scenario Pack Registry.

Do not duplicate Scenario Pack implementation.

Required validation:

```text
active template must point to existing scenario pack
locked template may point to an existing scenario pack but cannot create jobs
placeholder template may point to a future scenario pack id
disabled template may be omitted from user-facing cards
```

## 7. Frontend Behavior

Project detail should request template card states from backend.

Each card displays:

```text
display name
short description
status
beginner-facing action
```

Active card:

```text
开始使用
```

Locked card:

```text
即将开放
```

Placeholder card:

```text
规划中
```

No card should be activated only by frontend state.

## 8. Activation Gate

A template may become active only after all conditions are met:

```text
1. Dedicated spec exists and is accepted.
2. Manifest defines input fields.
3. Manifest defines context read/write policy.
4. Manifest defines output summary policy.
5. Backend routes enforce project_id.
6. Template creates jobs inside projects only.
7. Frontend workspace is beginner-facing and template-specific.
8. Tests prove it cannot pollute other templates.
9. E2E smoke proves visible outputs.
10. Documentation updates delivery order and acceptance criteria.
11. Document 43 product experience quality gate passes.
```

## 9. Template Isolation Rules

Mandatory isolation:

```text
General Template cannot show E-Commerce-only fields.
E-Commerce Template cannot create jobs while locked.
Future templates cannot inherit General Template UI blindly.
Template-specific project fields must be namespaced.
Template job creation must always validate project_id.
Template output summaries must be user-facing.
```

## 10. Implementation Steps

Recommended sequence:

```text
1. Add template manifest contract.
2. Add registry with current initial states.
3. Replace hardcoded template cards with registry response.
4. Enforce template status in project job creation.
5. Add frontend rendering for active/locked/placeholder.
6. Add tests for locked E-Commerce.
7. Add tests for active General Template.
8. Add audit command to list template states.
```

## 11. Required Tests

Backend:

```text
test_template_registry_contains_general_active
test_template_registry_contains_ecommerce_locked
test_locked_template_cannot_create_project_job
test_active_template_requires_existing_scenario_pack
test_general_template_maps_to_general_creative
test_template_job_creation_requires_project_id
```

Frontend:

```text
general card shows active action
ecommerce card shows locked message
locked card click does not call create job endpoint
placeholder cards do not create jobs
template cards use beginner-facing copy
```

Audit:

```text
rg should not find ecommerce job creation bypassing template gate
rg should not find frontend-only activation flags for locked templates
```

## 12. Acceptance Criteria

This phase is complete when:

```text
1. Template states come from a V3-owned registry.
2. Backend blocks locked templates.
3. General Template remains active.
4. E-Commerce remains locked until document 42 is implemented and accepted.
5. Future templates cannot activate without their own specs and tests.
6. Scenario Pack Registry remains the runtime source of scenario behavior.
7. Document 43 is treated as a required product-experience activation gate.
```
