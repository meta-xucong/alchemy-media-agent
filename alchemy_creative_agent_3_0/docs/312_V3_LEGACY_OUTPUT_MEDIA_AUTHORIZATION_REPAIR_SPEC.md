# V3 Legacy Output Media Authorization Repair

Status: implementation in progress; performance follow-up under audit
Contract revision: `DOC312_V3_LEGACY_OUTPUT_MEDIA_AUTHORIZATION`
Upstream read-path authority: `DOC311_V1_LEGACY_PROJECT_OUTPUT_PROJECTION`

## 1. Total objective and current phase

The total objective is to make the existing images of old V3 projects
readable on the VPS while preserving account isolation and the existing
formal-delivery/review/continuation contracts.

This phase repairs the authenticated media-read boundary and the corresponding
project output visibility projection. It does not generate new images, change
provider routing, backfill project membership, or grant a historical image
formal approval.

## 2. Observed mismatch and evidence

The VPS runtime is running with `VEYRA_AUTH_ENABLED=true`. Its V3 output store
contains real `original.png`, `preview.png`, and `thumbnail.png` files, but a
substantial legacy subset has no output-level `metadata.veyra_user_id`. The
same records have an exact `metadata.project_id` whose persisted project has
`metadata.veyra_user_id=1`; a smaller subset also has a legacy Job with the
same project link but no Job-level owner.

Before this repair, the project index adapter could discover some of those
records, but two later predicates still failed:

1. Project output/history projection called the strict Job/output-owner
   predicates and discarded ownerless legacy records.
2. `/api/v3/creative-agent/outputs/{output_id}/{variant}` authorized only the
   output-level owner and returned V3 not-found for the real file.

The result was a misleading empty/zero project card and an image request that
could not read the existing file.

## 3. Correction model and authority

The project is already the authenticated caller's visible scope. For a
project-scoped legacy output read, the project owner may provide a bounded
compatibility ownership proof for an ownerless output and, when needed, its
ownerless legacy Job when all of the following are true:

- the output owner field is absent, null, or empty;
- the output has a non-empty exact `metadata.project_id` link;
- that project exists and its owner exactly matches the authenticated user.

When a Job-level check is required, an explicit Job owner remains
authoritative. For an ownerless legacy Job, either its request metadata must
carry the same exact project link, or the Job must be a persisted member of the
visible project's `job_ids` and the output being read must be ownerless with
the same exact project link. This second proof is evaluated only after the
Job's outputs are loaded and only for the project-scoped output read.

An explicit output owner remains authoritative. A foreign explicit owner,
malformed non-empty owner value, missing project link, missing project, or
ownerless project remains denied. No public fallback is introduced.

The repaired ownership chain is therefore:

```text
explicit output owner
        │ present
        ▼
strict output owner match

legacy output owner absent
        │ exact project_id + visible project owner
        ▼
project-scoped compatibility visibility

legacy Job owner absent
        │ exact project_id, or declared project Job + exact ownerless output link
        ▼
project-scoped Job visibility for that output read
```

This fallback is used only in project-scoped output/history/formal read
projection and the authenticated V3 media route. Generic output references,
uploaded assets, jobs, V2/V1 routes, generation, review decisions, and
continuation admission retain their existing predicates.

### 3.1 VPS performance correction model

The first deployed ownership correction made the legacy records addressable,
but real VPS verification exposed a separate projection defect. A project
detail read was still walking every historical `job_id`, including Jobs with
no output record, and then parsing the same large durable Job JSON again for
the review projection. Some legacy Job files are 6--20 MB and some declared
IDs no longer have a file. The client-side symptom was another apparent empty
project because the synchronous read exceeded the request timeout.

The authority decision is unchanged: the durable Job status and the shared
delivery/review predicates remain authoritative. The output store's project
and Job indexes are only candidate locators. The minimal complete correction
is to build one request-scoped snapshot, load Job state only for candidate
Jobs that actually have output records, reuse that snapshot across formal,
review, and history projections, and keep deleted/no-output Jobs as an
authoritative empty result. This removes duplicate parsing without widening
ownership, delivery, review, selection, retry, or continuation semantics.

## 4. Bounded implementation

1. Add a read-only project-owner resolver for an ownerless V3 output in the
   FastAPI media boundary.
2. Add project-scoped Job/output visibility helpers in Project Mode and use
   them for formal output projection, legacy history projection, and the
   existing project-specific identity-anchor read projection.
3. Build a request-scoped candidate/output snapshot for project-scoped reads;
   do not parse declared Jobs that have no output records, and reuse parsed
   Job state across formal/review/history projections.
4. Keep output metadata and project JSON append-only during reads; no VPS data
   migration is required for this repair.
5. Add regression coverage for the positive legacy case and for foreign,
   malformed/unlinked, and ownerless-project negative cases.

## 5. Acceptance matrix

| Case | Project output projection | Authenticated media route |
| --- | --- | --- |
| Explicit output owner matches | allowed by existing rule | 200/file |
| Explicit output owner is foreign | denied | 404 |
| Ownerless output + exact owned project | allowed in project scope | 200/file |
| Ownerless output + project owner foreign | denied | 404 |
| Ownerless output + project missing/ownerless | denied | 404 |
| Malformed non-empty output owner | denied | 404 |
| Files missing | no item / existing not-found behavior | 404 |

The fallback must not change `history_only`, `review_only`, final-delivery,
selection, retry, or continuation semantics.

## 6. Verification and release gate

Required before reporting completion:

- focused Doc311 legacy projection tests pass;
- focused Doc312/auth route tests pass;
- relevant Project Mode/account-boundary regression tests pass;
- syntax, diff, and source audit pass;
- a regression proves project-scoped formal/review/history reads reuse one
  snapshot and skip declared Jobs with no output candidates;
- the deployed VPS container reports healthy;
- a real VPS output with project owner 1 and missing output owner is read via
  the same container code path and returns image bytes for thumbnail/preview/
  download, while negative foreign/unlinked cases remain denied.

## 7. Implementation receipt

Pending completion after code audit, local tests, GitHub push, VPS deployment,
and remote runtime verification.
