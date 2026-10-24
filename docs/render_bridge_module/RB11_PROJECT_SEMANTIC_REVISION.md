# RB11: sibling native tasks and semantic project revisions

## Correction model

Creating a second native plan in one project appends job/timeline bookkeeping.
The former revision hashed the entire job list and project updated timestamp,
so the first task's unchanged frozen input became invalid while queued/running.
Its returned original could then be withheld. The API and UI did not restrict
projects to one inflight task. This was an authority-scope error, not an input edit.

New server-created native plans carry the server-only request metadata marker
`render_bridge_project_binding=semantic_v2`. Their revision still binds the full
request, canonical planning result, target and authenticated actor. It now binds
all ProjectRecord fields except derived bookkeeping: job_ids, timeline_refs,
updated_at, latest_context, last_context_built_at, memory_summary and schema_version.
The last field is a derived project serialization label rewritten by job linking,
not the authoritative template/mode selection. Actual goal, title, style,
preferences, references, feedback, selection, brand, template/mode metadata,
owner and status remain revision-bound. Target job membership is checked
independently on every access; removing the target is never ignored.

No prompt, reference, options, generation, billing or review policy is relaxed.
Same-project new-version tasks can queue and complete independently. Native
receipt and cloud checkpoint recovery continue using the original exact binding;
review-only completion never renders a replacement.

## Existing records and rollout

Unversioned plans retain the exact legacy revision algorithm and frozen/output
identities. This change never recalculates an existing journal or relabels an old
frozen task as v2. An atomic module-store admission guard rejects a new native intent with HTTP
409 `legacy_native_project_tasks_pending` while an unversioned task in the same
owner/project is pending, unknown or awaiting review. The check follows exact
idempotent lookup, so retrying the old request returns it unchanged. Completed
legacy tasks do not block, and v2 tasks are not single-inflight limited.
Finish/reconcile existing legacy tasks before adding sibling plans; never delete
their journals or change stored hashes. This guard covers the optional native
entry, not ordinary Generate or arbitrary host project edits: legacy tasks retain
their conservative constraints until drained.
The stable plan key still looks up the original native job, including old plans.
Default Generate and public request contracts remain unchanged. External callers
cannot supply the revision-policy marker through ordinary job metadata.

## Verification

Focused synthetic regressions create/freeze task A, create task B in the same
project, then import A's original and recover interrupted review with exactly one
output/review and preserved ordered reference hashes. Cloud continuation similarly
recovers its exact checkpoint after a sibling is added without repeating transport.
Meaningful project edits, ownership/status changes, target removal and cancellation
still reject the original receipt. Legacy hashes are checked against the original
algorithm and replay keeps one output. No real provider or user account is used.

Local sanitized verification on 2026-10-21: 106 focused native/facade/planning/
cloud tests passed; subsequent coordinator/routing/preview/admin selection passed
127 tests; all eight legacy pending/review admission cases passed separately.
These selections overlap. Independent revision/facade review passed 34 cases
before the last two legacy registered-review cases were added. Existing legacy
project-timestamp rejection tests were retained unchanged; new-version tests use
actual semantic edits rather than pretending a bookkeeping timestamp is input.
JavaScript syntax and whitespace checks passed. Integrated two-service HTTP and
user-machine real-tool acceptance remain separate checks, not claimed here.
