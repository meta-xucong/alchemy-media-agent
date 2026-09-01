# V3 Project Detail Progressive Loading Development Specification

## Objective

Open a V3 project quickly when its history contains many failed, retried, or
review-only jobs. The first paint must show the project shell and the newest
formal delivery image when one is available. Older history may continue loading
after the project is usable.

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
   source-library metadata. It does not reconcile every Job, build full context,
   or assemble the full project history.
2. `GET /api/v3/creative-agent/project-outputs?project_id={id}&limit=1&compact=true&surface=delivery_preview`
   returns at most one current formal delivery item. It considers only output
   records already indexed to this project, then asks the existing delivery
   predicates to validate the candidate Job/output. It never includes review
   items.
3. After the shell and first preview response are rendered, the client releases
   the page mask and keeps generation controls busy while it loads the full
   timeline, output list, visual bindings, and latest Job in the background.
4. A project-detail epoch prevents a slower previous project request from
   overwriting the currently open project. The full response is still used for
   refreshes and all mutation/continuation flows.

## Storage and Compatibility

The V3 output store keeps an in-memory `project_id -> records` index alongside
the existing Job index. The index is rebuilt by the existing cached record read
and invalidated with it. Old records without a project binding simply do not
qualify for the preview and remain available through the full compatibility
path.

## Acceptance Criteria

- A project with a large failed history does not call full reconciliation during
  summary or delivery-preview reads.
- A valid formal output can be shown on first paint; no valid output produces an
  empty-state shell without waiting for history.
- Full history, review visibility, exact output binding, source disclosure,
  selection, and continuation behavior remain unchanged after background sync.
- Switching projects during background loading cannot cross-contaminate state.
- Existing callers without `view`/`surface` observe the prior full behavior.
- Desktop and H5 pass syntax and DOM contract checks, plus the focused backend
  progressive-loading regression suite.

## Non-Goals

This change does not delete history, alter retention, change provider behavior,
change review thresholds, add retries, or change the visual generation prompt.
