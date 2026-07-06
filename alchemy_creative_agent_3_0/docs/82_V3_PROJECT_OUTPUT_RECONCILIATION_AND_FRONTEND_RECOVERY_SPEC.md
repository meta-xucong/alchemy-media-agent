# Doc82: V3 Project Output Reconciliation and Frontend Recovery

## Purpose

Doc81 fixes provider failure retry. Doc82 fixes the separate project-state problem where a real image output is already written to the V3 output store, but the project timeline or frontend recovery state still says the job is pending or failed.

This document is additive and compatible with the Project Mode architecture:

```text
V3 Project
  -> Job
      -> provider generation
      -> output store
      -> project timeline and project output board
```

The output store is the source of truth for generated image files. Project timeline is the user-facing narrative. If these two diverge, V3 must self-heal instead of asking the user to guess whether generation succeeded.

## Problem

The current background generation path can produce this partial state:

- `/projects/{project_id}/jobs` returns successfully
- background generation writes one or more `v3_output_*` files
- browser fetch or server worker is interrupted before project timeline receives `job_generated`
- frontend keeps polling and may show `Failed to fetch`
- the user cannot reliably see that a usable image already exists

This is not primarily a provider retry problem. It is a project-state reconciliation problem.

## Rules

1. The output store wins when real generated files exist.
2. Project reads must reconcile missing completion state before returning data.
3. Reconciliation must be idempotent and never duplicate timeline entries.
4. Reconciliation must not select images automatically.
5. Reconciliation must not update Brand Memory.
6. Reconciliation must respect project ownership filters when listing cross-project outputs.
7. Frontend recovery must check project outputs as a first-class completion source, not only `/jobs/{job_id}`.

## Backend Design

Add a private Project Mode method:

```text
_reconcile_project_outputs(project)
```

It should:

- scan `project.job_ids`
- query `product_service.output_store.list_by_job(job_id)`
- if any output exists for a job and no `job_generated` timeline item exists for that job, append one
- if no visual review timeline exists for that restored job, append a user-facing restored review note
- refresh `project.memory_summary`
- save the project only when changes were made

Call reconciliation before returning:

- project detail
- project timeline
- project output list
- recent project list

## Frontend Design

During generation recovery:

- refresh project detail
- refresh timeline
- refresh project outputs
- if project outputs contain the current job id, synthesize a generated job object and finish the progress bar
- keep polling only if neither job API nor project outputs show completion

The user-facing result should be:

- if images exist, show success and render images
- if provider truly failed, show the friendly failure message from Doc81
- never leave the workspace stuck in an indefinite pending state

## Acceptance Tests

- A project job with output files but no generated timeline is opened.
- `get_project_timeline()` appends exactly one `job_generated` item.
- Calling `get_project_timeline()` again does not duplicate the item.
- `project-outputs` includes the restored output.
- Frontend recovery can complete from project outputs even if `/jobs/{job_id}` is pending, failed to fetch, or incomplete.

