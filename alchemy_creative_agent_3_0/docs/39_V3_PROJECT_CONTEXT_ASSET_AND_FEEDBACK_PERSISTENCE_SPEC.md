# 39 V3 Project Context Asset And Feedback Persistence Spec

This document defines the backend, API, and persistence details required for V3
Project Mode to truly continue a design chain across multiple jobs.

Document 38 defines the user-facing workspace. This document defines the data
that makes that workspace real.

## 1. Goal

Project Mode must persist:

```text
uploaded references that should remain useful
selected generated outputs
unselected outputs
rejected visual directions
plain-language timeline events
project context summaries
```

Future project jobs must read this state through `ProjectContextPackage`.

## 2. Core Rule

Only confirmed project state enters positive continuation context.

```text
Selected generated outputs -> positive context
Uploaded references marked useful -> positive context
Explicit project goal -> positive context
User rejection feedback -> negative context
Unselected candidates -> history only
Raw failed attempts -> history only
```

No candidate should become a style reference merely because it was generated.

## 3. Data Contract Extensions

### 3.1 ProjectReferenceAsset

Add a V3-owned project reference asset contract.

Required fields:

```text
reference_id: string
project_id: string
source_type: "uploaded" | "generated_selected"
asset_ref_id: string
preview_url: string | null
created_at: string
created_from_job_id: string | null
created_from_output_id: string | null
label: string | null
user_note: string | null
status: "active" | "inactive"
use_policy: "style" | "composition" | "product" | "mood" | "general"
```

Rules:

```text
source_type=uploaded must point to a V3 upload asset.
source_type=generated_selected must point to a generated V3 output.
inactive references remain visible in history but are excluded from context.
```

### 3.2 ProjectFeedbackRecord

Add a project feedback contract.

Required fields:

```text
feedback_id: string
project_id: string
target_type: "project" | "job" | "output" | "reference"
target_id: string | null
feedback_type: "avoid_direction" | "remove_reference" | "prefer_direction" | "note"
plain_text: string
reason_tags: list[string]
created_at: string
status: "active" | "resolved" | "archived"
```

Rules:

```text
avoid_direction feedback enters negative context.
remove_reference changes reference status to inactive.
prefer_direction can create a positive note only when explicit.
archived feedback must not affect context.
```

### 3.3 ProjectSelectedOutputState

Project output selection must be explicit and reversible.

Required fields:

```text
project_id: string
job_id: string
output_id: string
selection_state: "selected" | "unselected" | "rejected"
selected_at: string | null
unselected_at: string | null
rejected_at: string | null
selection_note: string | null
rejection_note: string | null
```

Rules:

```text
selected -> positive context
unselected -> no context
rejected -> negative context if user provides reason
```

### 3.4 ProjectTimelineItem

Extend the existing timeline with plain-language event data.

Required fields:

```text
timeline_id: string
project_id: string
event_type: string
created_at: string
title: string
summary: string
related_job_id: string | null
related_output_ids: list[string]
related_reference_ids: list[string]
visible_to_user: bool
debug_payload: object | null
```

Rules:

```text
visible_to_user timeline items must not expose raw engineering language.
debug_payload may exist but must not be rendered in normal UI.
```

## 4. ProjectRecord Extensions

Extend `ProjectRecord` without replacing it.

Suggested fields:

```text
reference_assets: list[ProjectReferenceAsset]
feedback_records: list[ProjectFeedbackRecord]
selected_output_states: list[ProjectSelectedOutputState]
memory_summary: ProjectMemorySummary
last_context_built_at: string | null
schema_version: string
```

Backward compatibility:

```text
If existing project files do not have these fields, default to empty lists.
Do not migrate old project files destructively.
Write the new fields the next time the project is saved.
```

## 5. ProjectContextPackage Rules

`ProjectContextPackage` must be built from current project state.

Recommended order:

```text
1. project goal
2. explicit latest user instruction
3. selected generated output references
4. active uploaded reference assets
5. accepted visual direction summary
6. active avoid feedback
7. template-specific context policy
8. latest job-local uploaded references
```

Do not exceed the provider prompt/context budget.

If too much context exists, prioritize:

```text
latest selected outputs
explicit active references
latest negative feedback
stable project goal
```

## 6. New API Endpoints

### 6.1 List Project Context

```text
GET /api/v3/creative-agent/projects/{project_id}/context
```

Returns:

```text
ProjectContextPackage
```

Purpose:

```text
frontend preview
tests
debugging hidden behind developer mode
```

Normal users should see only plain summaries.

### 6.2 Add Project Reference

```text
POST /api/v3/creative-agent/projects/{project_id}/references
```

Request:

```text
asset_ref_id
source_type
label
user_note
use_policy
created_from_job_id
created_from_output_id
```

Behavior:

```text
validate asset belongs to V3
validate project exists
create active ProjectReferenceAsset
append timeline item
save project
return updated reference board summary
```

### 6.3 Update Project Reference

```text
PATCH /api/v3/creative-agent/projects/{project_id}/references/{reference_id}
```

Allowed updates:

```text
label
user_note
status
use_policy
```

Common use:

```text
remove from future reference by setting status=inactive
```

No hard delete in normal UI.

### 6.4 Select Output

Existing select endpoint may be retained, but it must guarantee:

```text
selected output state is written
generated_selected reference asset is created or reactivated
timeline item is appended
project context summary is refreshed
```

If a new endpoint is needed:

```text
POST /api/v3/creative-agent/projects/{project_id}/outputs/{output_id}/select
```

### 6.5 Unselect Output

```text
POST /api/v3/creative-agent/projects/{project_id}/outputs/{output_id}/unselect
```

Behavior:

```text
set selection_state=unselected
set related reference asset status=inactive
append timeline item
refresh context summary
```

### 6.6 Reject Output Direction

```text
POST /api/v3/creative-agent/projects/{project_id}/outputs/{output_id}/reject
```

Request:

```text
plain_text
reason_tags
```

Behavior:

```text
set selection_state=rejected
create active avoid_direction feedback
set related reference inactive if needed
append timeline item
refresh context summary
```

### 6.7 Add Project Feedback

```text
POST /api/v3/creative-agent/projects/{project_id}/feedback
```

Use for project-level avoid/prefer notes not tied to one output.

## 7. Uploaded Reference Persistence

When the user uploads an image during a project job, the frontend must choose a
clear persistence mode.

Allowed modes:

```text
job_only
project_reference
ask_after_generation
```

Recommended default:

```text
ask_after_generation
```

Beginner-facing copy:

```text
要把这张图作为本项目后续参考吗？
```

If the user chooses yes:

```text
create ProjectReferenceAsset with source_type=uploaded
```

If the user does not choose:

```text
the uploaded file may be used by the current job only
```

## 8. Negative Context Rules

Negative context must be short and user-confirmed.

Examples:

```text
avoid dark lighting
avoid cluttered background
avoid cartoon style
keep product body clear
leave room for copy
```

Do not create negative context from model evaluation alone unless the user
accepts it.

Do not phrase negative context as accusations or internal failure messages.

## 9. Store Migration Rules

The persistent project store must:

```text
load old project records with missing fields
default missing list fields to []
default schema_version if missing
write updated schema on save
never delete old job files during migration
never mutate V1/V2/Lab history
```

Suggested schema version:

```text
project_mode_v2_context_assets_feedback
```

## 10. Context Builder Implementation Steps

Implementation sequence:

```text
1. Add contracts for ProjectReferenceAsset and ProjectFeedbackRecord.
2. Extend ProjectRecord with backward-compatible defaults.
3. Add store read/write helpers for references and feedback.
4. Add ProjectContextBuilder methods for positive references and negative notes.
5. Update project job creation to use the enriched ProjectContextPackage.
6. Update output selection to create generated_selected references.
7. Add uploaded reference persistence mode.
8. Add feedback endpoints.
9. Add timeline events for selection, unselection, rejection, and reference upload.
10. Add unit tests and route tests.
```

## 11. Frontend Integration Steps

Implementation sequence:

```text
1. Render active references in useful references board.
2. Render inactive references only in timeline/detail history.
3. Add select/unselect calls.
4. Add reject direction flow.
5. Add upload persistence prompt.
6. Refresh project detail after each state-changing action.
7. Optimistically update UI only if rollback handling exists.
8. Hide raw context package from normal UI.
```

## 12. Required Backend Tests

Add or update tests:

```text
test_old_project_record_loads_with_default_context_fields
test_uploaded_reference_can_be_saved_to_project
test_selected_output_creates_active_generated_reference
test_unselected_output_exits_positive_context
test_rejected_output_adds_negative_context
test_unselected_candidate_does_not_enter_context
test_context_builder_prioritizes_selected_outputs
test_project_timeline_uses_plain_language_events
test_project_job_creation_reads_project_context
test_v1_v2_lab_history_not_touched
```

## 13. Required Frontend Tests

Add or update tests:

```text
selected image appears in useful references board
unselected image remains in history but not in useful references
reject direction opens beginner-facing feedback modal
project refresh preserves useful references
upload reference prompt can persist asset to project
context details are not shown to normal users
```

## 14. Acceptance Criteria

This phase is complete when:

```text
1. Project continuation uses selected outputs and active project references.
2. Uploaded references can persist beyond one job.
3. Negative feedback is stored and affects future context.
4. Unselected candidates do not pollute positive context.
5. Timeline explains project changes in user-friendly language.
6. Existing Project Mode APIs remain backward compatible.
7. E-Commerce remains locked.
8. All existing V3 job/provider/shared capability tests still pass.
```
