# V3 Legacy Project Output Discovery and History Projection Repair

Status: implemented and locally verified
Contract revision: `DOC311_V1_LEGACY_PROJECT_OUTPUT_PROJECTION`
Baseline: `c9a18b8a` (`origin/main` synchronized before audit)

## 1. Scope and total objective

The total objective is to make V3 project cards and project history show
existing, safely readable project images for old projects, while preserving the
existing formal-delivery, review, owner, and continuation authorities.

The current phase is a bounded read-path repair: identify project-associated
output records that are already present in the V3 output store, project them to
the appropriate surface, add regression coverage, and verify both desktop and
mobile rendering. Brain, Provider, generation, review policy, and VPS
deployment are outside this phase.

## 2. Observed mismatch and root cause

The output store has a bounded index keyed by `metadata.project_id`. A number
of legacy `project.json` records have an empty or partial `job_ids` list even
though their `output.json` records contain the same `project_id` and valid
media files.

The current read path discovers those indexed records, then the count and cover
helpers restrict candidates back to `project.job_ids`. The records are
therefore discarded and the browser receives an empty or incomplete formal
projection. For records whose Job record is also absent, Product API recovery
correctly marks the pixels as `needs_recovery` or `delivery_withheld`; the
current code then hides them from the normal project output list. This is safe
for delivery but incorrect for a history/home surface because it turns
readable historical pixels into a false `0`/empty state.

## 3. Authority and correction model

One authority remains in force for each concern:

| Concern | Authoritative source | Repair behavior |
| --- | --- | --- |
| Current project mutation and continuation membership | `ProjectRecord.job_ids`, selected references, and existing project contracts | Never mutate the project record during a read; never grant continuation rights from the compatibility projection |
| Candidate location for legacy pixels | V3 output-store `metadata.project_id` index | Use only as a bounded, project-scoped read locator; filter project identity, usable media, and owner before projection |
| Formal delivery | Existing Job status, closure, review, retry, selection, and output predicates | Preserve `_project_output_items` and `delivery_preview` semantics |
| Historical visibility | New additive `history_items` projection | Expose readable legacy pixels with `history_only=true`; never label them `final_delivery` or place them on formal result boards |
| Browser rendering | Surface-specific display filters | History cards may show history-only media; generation/result/reference surfaces remain formal-only |

This is a compatibility adapter, not a persistence migration. It does not
backfill `job_ids`, synthesize a closure, mark a Job generated, relax owner
checks, or infer that a historical image is approved for delivery.

## 4. Minimal complete implementation

1. Derive an ephemeral, newest-first-capable Job candidate list from indexed
   project records only when the persisted `job_ids` list is empty. Reuse the
   existing Project output gate with a shallow copy; do not save the copy.
2. Let records with a valid recovered/closed delivery path enter ordinary
   `items` through that existing gate.
3. For indexed records whose Job id is absent from the persisted project
   membership, or whose project has no membership list, emit safe
   `history_items` with no prompt, filesystem path, review authority, or
   continuation authority. Keep the existing `review_items` behavior for
   records belonging to an explicit `job_ids` membership; readable pixels do
   not relabel an incomplete declared Job as history.
4. Return additive `project_history_counts` on `home_preview`; keep
   `project_output_counts` as the formal-delivery count. A history-only count
   must not be silently reported as a formal count.
5. Desktop and mobile home/history surfaces consume `history_items`, display a
   truthful history label, and prefer a formal cover when both formal and
   history media exist. Formal result boards, selected references, and
   continuation paths continue to consume only canonical final delivery items.
6. Owner filtering is fail-closed for both the project and output record.

## 5. Acceptance matrix

| Case | Formal `items` | `history_items` | Home count/label | Result/continuation |
| --- | --- | --- | --- | --- |
| Modern closed project | Existing behavior | Empty | Existing formal count | Existing behavior |
| Legacy project, indexed output, complete closure | Existing gate decides | Empty | Formal count | Formal only |
| Legacy project, indexed output, missing/incomplete closure | Empty | Safe historical media | Formal count plus separate history count | Excluded |
| Legacy project, partial `job_ids`, indexed orphan output | Existing gate for declared Jobs | Safe historical media for undeclared Jobs | Formal count plus separate history count | Excluded |
| Explicit project `job_ids` with incomplete closure | Empty | Empty | Existing behavior | Review-only behavior unchanged |
| Foreign output owner | Empty | Empty | No count/media | Excluded |
| Missing/unusable output file or URL | Empty | Empty | No false positive | Excluded |

Required tests cover backend projection, non-mutation, owner isolation, the
existing unclosed-recovery regression, desktop history rendering, mobile
history rendering, and formal-result exclusion.

## 6. Out of scope and release gate

No Brain/provider/generation changes, no output-store rewrite, no automatic
recovery or closure creation, no V2 changes, and no VPS deployment are part of
this repair. The phase is complete only after the focused tests, the relevant
full V3 regression set, a source/diff audit, and a local commit/push are green.
VPS synchronization requires an explicit follow-up authorization.

## 7. Implementation receipt

- changed files: `app/project_mode/service.py`, desktop `app.js`, mobile
  `mobile.js`, this specification, and its focused regression test.
- focused tests: `test_v3_doc311_legacy_project_output_projection.py` — **10
  passed**; Node syntax checks for both browser bundles — **passed**;
  `git diff --check` — **passed**.
- relevant V3 regression result: Doc301/308/309/310, Doc311, progressive
  project loading, and output-closure repair — **66 passed** after the
  partial-membership correction.
- local data replay: 89 non-archived projects were read through the
  persistent app stores; 17 projects now expose indexed legacy history and
  the formal/history counts remain separate. The partial-membership fixture
  exposes 3 formal outputs and 2 history-only outputs.
- commit/push: pending final source audit and local mainline commit.
- remaining integration dependency: VPS synchronization is intentionally
  not included in this phase and needs explicit follow-up authorization.
