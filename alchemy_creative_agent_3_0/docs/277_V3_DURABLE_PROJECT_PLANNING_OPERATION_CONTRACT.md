# Doc277: Durable Project Planning Operation Contract

## Problem

Remote Central Brain planning may take longer than an HTTP client is willing to
wait. Before a Product Job exists, the old V3 route leaves the browser with no
durable identity to poll. Retrying that request can create duplicate planning
or duplicate generation work.

## Authority

Project Mode owns a planning operation for interactive `auto_generate` calls.
It is not a Product Job and cannot claim Provider dispatch, output creation,
review, or delivery. Existing explicit programmatic planning calls retain their
established synchronous Product Job response contract.

- The operation is issued from the canonical project, validated request, active
  template, and server-owned relevant reference selection.
- It is stored privately and has one public-safe projection.
- A pending equivalent request returns the same operation instead of starting
  another Brain call.
- A different request while planning is pending returns that pending operation;
  it does not race a second Brain call.
- A completed operation attaches exactly one real Product Job ID.
- A failed operation is terminal and actionable. It never exposes provider,
  prompt, exception, path, hash, or request payload details.

## Lifecycle

```text
request -> planning (durable, poll project)
        -> completed (one job_id, optionally starts generation)
        -> failed (terminal, manual retry action)
```

The background planning worker is process-local. If the process restarts while
an operation is pending, recovery scans every persisted project and closes that
operation as interrupted. It is never silently replayed.

## Public Projection

The public current operation is one of:

- `planning`: `pending=true`, `terminal=false`, no Generate action.
- `planning_failed`: `pending=false`, `terminal=true`, one
  `review_project_request` action.

After completion, the planning projection is cleared and the real Job lifecycle
is authoritative. UI must clear planning timers before rendering a terminal
operation and must not show planning/preparing beside a terminal state.

## Isolation

This is Project Mode lifecycle infrastructure shared by General, E-Commerce,
and Photography. It does not change Provider routing, Brain creativity,
reference-channel authority, Product Truth admission, output delivery, or any
historical job. It never retries a planning call, provider call, or historical
job automatically.

## Acceptance

1. A delayed planner returns a durable `planning` response promptly.
2. Refreshing the project shows the same pending operation.
3. Repeating an equivalent or different request while pending starts no second
   planner call.
4. Success binds one job and starts at most the requested generation path.
5. Failure/restart closes terminally and exposes one safe manual action.
6. Desktop and mobile clear busy/progress state on terminal planning failure
   and resume polling after planning success.
