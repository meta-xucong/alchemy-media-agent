# V3 planning failure investigation

## Correction model before implementation

The user requests investigation and repair of the V3 planning failure before
further V1/V2 performance work. Production runs `75e5827c`; local/main is
`c01bf21a`, whose runtime delta only preserves nested Brain failure diagnostics.

Expected flow: project planning operation -> remote Brain -> validated plan ->
persisted Job -> generation -> shared review -> frontend delivery.

Observed: project `project_ad39308b2f`, operation
`doc277_project_planning_bd4e822215`, terminated with
`remote_creative_brain_required_for_template`. This proves the remote Brain
acceptance gate rejected the result; it does not identify the upstream cause.
Audit run `42457634064` found no operation diagnostics and reported the bound
Job `job_0669df3c0c` missing from the configured root. No new generation is
authorized as an exploratory debugger under the repository code-first rule.

The first confirmed defect is in the audit projection: `job_summary` reads
top-level `metadata`, while `PersistentProductJobStore._write_record` persists
the request metadata under `request.metadata`. Correct this read and inspect
only the exact project Job IDs in the configured root and the package default
root defined by `_default_product_job_storage_root`. Reuse the existing
allowlisted private Brain diagnostic sanitizer. These reads must not create,
change, replay or delete a Job, output, or provider request.

This is auxiliary diagnostic work in the shared V3 foundation. The runtime
Brain cause remains unproven pending this evidence. No template-specific
behavior, creative fallback, threshold change, or provider retry is justified.

## Evidence correction after read-only run 42459108798

The alternate code-defined root did not contain the two missing IDs. The
earlier claim that `job_0669df3c0c` is this operation's bound Job was an
unverified inference from the last entry in `project.job_ids`. The audit
omitted the operation's actual `job_id`. Read the exact failed operation's
private record and look up that identity directly, including whether it is
present in the project catalog. Its timestamps also distinguish this failure
from the project's September history. Do not treat historical missing jobs as
the current failure's evidence without this binding.

Run `42459284885` confirms the bound Job is `job_0669df3c0c`, but the operation
opened at `2026-09-23T03:04:42Z` and failed at `2026-09-23T03:09:58Z`. The
November project update timestamp is not the operation timestamp. This is a
historical failure, so its generic Brain error cannot establish the cause of
the user's November incident. Next inspect only allowlisted recent POST
route/time/status entries from the active container's access log to identify
the actual submission. No raw logs or request content are emitted.

## Actual incident located

Access-log audit `42459501453` located the November submission at
`2026-11-08T05:27:49Z`: project `project_c72a7decc9`. Audit `42459562880`
found its sole Job `job_37f9dcbbf6`, blocked at `05:29:20Z`, operation
`doc277_project_planning_5d3f2cc4ad`. The Job is durable in the configured
mounted root. Its safe Brain outcome is `remote_contract_invalid`,
`llm_used=true`, `fallback_used=false`, `remote_provider_available=true`.
This proves an actual remote result was obtained and failed contract
acceptance. It supersedes the old project's missing-Job/remote-required
diagnosis. Read its existing sanitized validation paths/types before deciding
whether the defect is in the remote schema contract or local validation.

## Runtime correction model

Run `42459687939` binds the actual failure to
`remote_creative_brain_task_profile_invalid` and the persisted validation
path/type `visual_task_profile` / `value_error`. Planning took 90.98 seconds.
The original invalid remote object was discarded, so its exact malformed
child field cannot be reconstructed from this record.

Code proves three defects on this path: the profile completeness check rejects
entity/evidence field omissions and types that its diagnostic function never
identifies; `_safe_semantic_contract_recovery_diagnostics` drops all profile
diagnostics and only forwards E-Commerce product-truth image-plan diagnostics;
the background failure-code allowlist omits `task_profile_invalid` and reports
the generic `planning_job_blocked` seen in this incident.

The bounded repair is shared Brain contract/recovery and background projection
work: identify the already-required malformed child fields, forward only closed
field paths/error types into the existing single remote reanswer, and retain
the known task-profile error code. Preserve all acceptance requirements and
the one-reanswer limit. Do not invent missing semantic values locally. Add a
deterministic provider fixture that repairs its incomplete profile only when
the actual recovery request identifies the field; verify repeated malformed
answers still fail closed. A passing simulation proves this recovery defect
is repaired; live V3 acceptance remains a separate required phase.

## Implemented repair and verification

- The profile diagnostic now identifies missing nested entity/evidence fields,
  their already-enforced container/boolean types and confidence ranges, and
  invalid reference evidence IDs. The acceptance predicate is unchanged.
- The existing single semantic reanswer now receives profile field paths
  derived from the same compact schema sent to Brain, with closed error types.
  Arbitrary keys, values and provider response text are excluded. Existing
  E-Commerce product-truth diagnostics remain supported.
- Background planning retains `remote_creative_brain_task_profile_invalid`.
- Nine targeted regressions failed before the runtime patch and passed after
  it. The final related set passed **38 tests**, with three UI-only tests
  deselected. This includes the outbound serialized recovery payload,
  successful mock repair, fail-closed repeated malformed answers, two-call
  maximum, unchanged user intent, diagnostic redaction and operation binding.
  Tests used isolated Job/output/upload/project storage with live Brain
  disabled globally; injected-provider cases explicitly enable their mocks.
- Workflow YAML/embedded Python syntax and `git diff --check` passed. A
  read-only scope monitor reviewed the audit and runtime changes without
  finding a scope violation. This is not live product acceptance.

Next required phase: prepare the repaired candidate, reconcile the existing
release guard's V2 unknown-work condition through its supported process, and
perform guarded deployment and one API-based V3 acceptance on the actual
target request. Verify a valid plan, RenderBridge task/receipt, shared review
and matching frontend preview/download projection. Production remains on
`75e5827c`; no production service restart, new generation or record cleanup was
performed in this investigation. No exact malformed child value is claimed
for the original request because that raw response was not retained.
