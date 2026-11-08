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
