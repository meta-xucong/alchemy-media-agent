# Doc320 — V3 Scoped Output Read Boundary and Index Freshness Repair

Status: implementation candidate; local audit and simulation required

## Objective

Close two read-path gaps found after Doc310–319:

1. Home-preview compatibility reads must not deserialize an unbounded number of
   outputs for one legacy Job.
2. The scoped output locator must notice out-of-band changes to existing
   `output.json` files, even when the output root directory timestamp is not
   updated.

## Authority and boundaries

The durable output record remains the authority for `job_id`, `project_id`,
ownership, media integrity, review state, and delivery state. The scoped index
is only a candidate locator. Exact record loading and the existing Project Mode
predicates remain mandatory.

This repair changes no ownership fallback, formal-delivery predicate, review
decision, continuation admission, provider route, public status, or V2 path.

## Correction model

`V3GeneratedOutputStore.list_by_job()` gains an optional `limit` argument. The
default remains unbounded for existing full-history callers. Home-preview
compatibility calls pass the bounded per-Job window
`_HOME_PREVIEW_MAX_OUTPUTS_PER_JOB`; adapters with the legacy one-argument
signature are sliced after return for compatibility.

The scoped locator revision becomes:

```text
(output-root revision, per-output path/mtime/ctime/size signature)
```

The byte scan still avoids full JSON deserialization while building candidates,
but any added, removed, or externally modified `output.json` causes the
locator to rebuild. Candidate records are still exact-matched after loading.

## Acceptance matrix

| Case | Expected result |
| --- | --- |
| Home fallback Job has 100 outputs | At most bounded window enters the home snapshot |
| Existing one-argument test adapter | Works and is sliced locally |
| Existing production store caller without limit | Preserves full-history behavior |
| Existing output metadata changes in place | Next scoped lookup rebuilds locator |
| New output record appears without root mtime update | Next scoped lookup discovers it |
| Stale candidate path after metadata change | Exact-match filtering prevents false ownership/project visibility |

## Required verification

- focused bounded-output and external-metadata-change tests;
- existing Doc310/311/313/316/317 and Brain/Vision timeout regressions;
- Python compile check and diff audit;
- deterministic simulation with a fake store containing oversized Job output
  history and an out-of-band `output.json` rewrite;
- no provider, VPS, or real-generation side effects.

