# V3 Project Detail Progressive Loading Development Specification

## Objective

Open a V3 project as soon as its authenticated project summary is available,
even when its history contains many failed, retried, or review-only jobs. The
project shell is the identity boundary; images and history are supplementary
and continue loading after the project is usable.

## Authority and Scope

- The Product API, Project Mode service, Brain, Provider, review, persistence,
  and continuation rules remain authoritative and unchanged.
- The existing full project response remains the default compatibility path.
- Only the project-detail read path gets an optional `view=summary` response
  and the project-scoped `surface=delivery_preview` output response.
- Review-only, failed, in-flight, historical, and retry-superseded pixels are
  never eligible for the first-paint delivery preview.
- General and Professional V3 use the same read protocol. No template-specific
  output rules are added.

## Read Protocol

1. `GET /api/v3/creative-agent/projects/{project_id}?view=summary` returns the
   authenticated project shell, safe persisted summary data, templates, and
   source-library metadata. It does not resolve Jobs, inspect output files,
   hash continuity images, migrate continuity state, build full context, or
   assemble project history. The endpoint runs outside the API event loop.
2. `GET /api/v3/creative-agent/project-outputs?project_id={id}&limit=1&compact=true&surface=delivery_preview`
   returns at most one current formal delivery item. It is requested after the
   project shell is established and does not gate opening. It considers only
   output records already indexed to this project, then asks the existing
   delivery predicates to validate the candidate Job/output. It never includes
   review items and runs outside the API event loop.
3. The client releases the page mask as soon as the summary establishes the
   project. Preview, timeline, output list, visual bindings, and latest Job
   continue loading in the background.
4. A project-detail epoch prevents a slower previous project request from
   overwriting the currently open project. The full response is still used for
   refreshes and all mutation/continuation flows.
5. If the first summary read fails, the client returns to the project list. If
   switching from an already open project fails, it restores that project's
   detail epoch and reads so its images and review state remain usable. No
   failure path may leave the workspace visible with an empty project.
6. A delivery preview is a partial projection. Once a full project-output
   response has been applied, a late preview cannot replace its outputs or
   clear its review items.

## Storage and Compatibility

The V3 output store keeps an in-memory `project_id -> records` index alongside
the existing Job index. The index is rebuilt by the existing cached record read
and invalidated with it. Old records without a project binding simply do not
qualify for the preview and remain available through the full compatibility
path.

## Acceptance Criteria

- Summary reads do not resolve Jobs, verify continuity source bytes, migrate
  continuity state, or call full reconciliation.
- A slow or failed preview does not delay opening the project shell.
- A failed summary returns to a usable project list or preserves the previously
  open valid project; workspace plus null project is impossible after failure.
- A failed switch restores the previous project's detail owner and controller;
  a delayed preview cannot overwrite a complete output/review projection.
- A valid formal output appears when its background preview completes; no valid
  output leaves a usable project shell without waiting for history.
- Full history, review visibility, exact output binding, source disclosure,
  selection, and continuation behavior remain unchanged after background sync.
- Switching projects during background loading cannot cross-contaminate state.
- Existing callers without `view`/`surface` observe the prior full behavior.
- Desktop and H5 pass syntax and DOM contract checks, plus the focused backend
  progressive-loading regression suite.

## Non-Goals

This change does not delete history, alter retention, change provider behavior,
change review thresholds, add retries, or change the visual generation prompt.
