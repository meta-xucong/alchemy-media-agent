# RB34: Recover the existing V2 Bridge task without a request SHA

## Objective and observed mismatch

Deliver the already-rendered Bridge artifact to its original V2 image job. The
existing Bridge task is `artifacts_ready` with an upload and receipt, while the
Alchemy V2 job remains queued in `bridge_wait` without an output. Recovery must
reuse that job and task; it must not create a replacement task or image.

V2's transport currently uses `PrimaryRequest.key` and `PrimaryRequest.digest`
for local ledger lookup and semantic replay checks. Those values are generated
from SHA-256 even though they do not contain image bytes. The V2 frozen-request
filename and Bridge output ID also use SHA-derived identifiers. This prevents
the requested recovery under the no-SHA constraint.

## Authority and correction model

The product's immutable V2 `job_id` and frozen request record own the V2
request. The persisted Bridge `task_id`, `origin_key`, and exact saved wire
request own its accepted execution. These existing fields provide sufficient
identity for the recovery path:

1. Find an existing V2 transport row by its stored product and `unit_id` when
   the new no-SHA key does not match a legacy row. Reuse its stored origin key,
   task ID, attempt ID, and wire request.
2. Find a legacy frozen JSON record by the embedded V2 `job_id` or queue
   `task_id`; new snapshots use a reversible filename derived from those IDs.
3. Fetch the same Bridge task by its stored origin key and require its returned
   request to equal the stored wire request. Continue through its existing
   receipt and V2 output/debit commit path.
4. Use a stable output ID formed from the existing `job_id` and output index so
   V2 commit replay remains idempotent without a request or image digest. This
   pending job has no existing output, so historical output IDs are left intact.

Stored legacy digest text may remain in old rows as historical data, but the
recovery path must neither recompute nor compare it. Bridge task creation,
provider routing, API fallback rules, billing, and receipt ownership do not
change. The current artifact recovery does not call Bridge task creation.

## Exact V3 API-key route

The V3 API-key route policy will admit only
`POST /api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/generate` for
keys that already have the `v3` surface. Other methods and project/job routes
remain governed by the existing allowlist.

## Focused acceptance

- A pure route-policy test admits the exact V3 generation route and rejects a
  sibling action and a different method.
- A legacy V2 fixture locates the original frozen record and transport row by
  job/task identity, follows the saved Bridge request, and commits the existing
  artifact once without creating a task or computing a SHA/hash/checksum.
- Final live acceptance resumes the exact existing V2 job/task and confirms its
  output is visible in V2 history. No new provider generation is part of this
  recovery acceptance.
