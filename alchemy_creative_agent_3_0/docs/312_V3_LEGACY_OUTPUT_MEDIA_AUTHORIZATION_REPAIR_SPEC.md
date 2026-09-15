# V3 Legacy Output Media Authorization Repair

Status: accepted after code audit, local regression, and VPS runtime verification
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

### 3.2 Legacy file-integrity compatibility model

The VPS audit then found a second, narrower read failure: several review-only
records had valid canonical `original.png`, `preview.png`, and `thumbnail.png`
files, but their old `width`/`height` metadata no longer matched the actual
PNG dimensions. Those records predate the immutable content-hash fields. The
stored dimensions are descriptive metadata, not an authorization or file
identity proof; rejecting the real image solely for that drift produced a
false 404.

The file authority remains the canonical output directory and actual image
decoder. New or hash-bound records must still match their SHA-256 and retain
the strict dimension/integrity checks. Only hashless legacy records may pass
when the canonical original and requested variant are real, in-root, valid
images; no path fallback or hash mismatch is accepted.

### 3.3 Cold scoped-output index correction model

The VPS end-to-end check then isolated a remaining cold-start defect. The first
project detail request still called the output store's full-history index. That
index deserialized every historical `output.json`, including large prompt and
review metadata, before it could answer a project- or Job-scoped lookup. The
same process was fast after the cache warmed, which made the UI failure appear
intermittent even though the media files were valid.

The output record and its exact `project_id`/`job_id` fields remain the
authority. A scoped lookup may first scan only the raw JSON bytes for candidate
file paths, then fully deserialize and exact-match each candidate before it is
returned. Candidate hits are therefore a locator optimization, not a new
authorization source. Full-history listing keeps its existing complete index;
normal writes advance the existing storage revision so the scoped locator is
rebuilt when records change.

### 3.4 Explicit history-surface review projection correction model

The VPS response audit then separated a second user-visible symptom from the
media authorization path. A project-scoped full read returned valid legacy
pixels in `review_items`, but the desktop home "查看图片" modal built its
gallery only from the formal/history collections. The server therefore had
returned the image and the authenticated media route could serve it, while the
explicit gallery still rendered an empty state.

The authority decision is unchanged: `items` remains formal delivery,
`history_items` remains legacy history-only output, and `review_items` remains
non-delivery review evidence. Home first paint must stay formal-only and
review-free. The minimal complete correction is for the explicit project
history modal to merge safe, image-bearing review items after its scoped full
read, label them as review-only, and keep them outside formal counts,
selection, continuation, and home-preview projections. This makes the
existing image inspectable without silently promoting a withheld result.

### 3.5 Stale project-history request failure correction model

Real browser verification exposed one remaining cross-project race: opening
project A, closing it, and immediately opening project B allowed a late A
response to overwrite B. The same risk existed when A failed, because its
error handler could clear the shared output state after B had become active.
The authoritative modal session is therefore the tuple of active project ID
and monotonically increasing modal epoch. Every scoped success, failure, and
modal continuation callback must verify that tuple before mutating shared
output state, error state, or the visible gallery; request bookkeeping is also
cleared only by the matching request owner/key. Closing the modal advances the
epoch, invalidating all outstanding callbacks. This repairs the shared state
authority once and does not change output authorization or delivery status.

## 4. Bounded implementation

1. Add a read-only project-owner resolver for an ownerless V3 output in the
   FastAPI media boundary.
2. Add project-scoped Job/output visibility helpers in Project Mode and use
   them for formal output projection, legacy history projection, and the
   existing project-specific identity-anchor read projection.
3. Build a request-scoped candidate/output snapshot for project-scoped reads;
   do not parse declared Jobs that have no output records, and reuse parsed
   Job state across formal/review/history projections.
4. Allow hashless legacy records with stale descriptive dimensions to use
   canonical validated files without rewriting their metadata; keep hash-bound
   records strict.
5. Keep output metadata and project JSON append-only during reads; no VPS data
   migration is required for this repair.
6. Use a revision-aware lightweight locator for project/Job-scoped output
   reads; retain full record parsing and exact field filters after candidate
   selection.
7. Merge review-only output pointers into the explicit desktop project history
   modal only after the scoped full read; preserve the formal/history/home
   separation and review-only labeling.
8. Guard both stale success and stale failure callbacks from a previous
   project-history modal session; add deterministic regression coverage for
   both orderings.
9. Add regression coverage for the positive legacy case and for foreign,
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
- a regression proves stale dimensions on a hashless legacy record do not
  hide valid canonical image files, while hash-bound mismatches remain denied;
- a regression proves scoped output lookups do not invoke the full-history
  deserializer on a cold store and still exact-match the returned records;
- a browser regression proves a review-only image returned by a project-scoped
  full read is visible in the explicit project history modal while remaining
  absent from the home formal-preview collection;
- a browser race regression proves a failed old project request cannot clear or
  replace the currently open project's review gallery;
- the deployed VPS container reports healthy;
- a real VPS output with project owner 1 and missing output owner is read via
  the same container code path and returns image bytes for thumbnail/preview/
  download, while negative foreign/unlinked cases remain denied.

## 7. Implementation receipt

Completed on the implementation commit `5a4d2a79023a6e60a3a189a95bfd49506b371bc8`
and the final audit/coverage commit `ea0483832404adf75ba5aa94c7f545f935b50c33`.

- Code audit: independent read-only audit passed; the stale success and stale
  failure paths are both gated by modal epoch, active project, and request
  owner/key checks. Formal delivery, review, selection, and continuation
  semantics remain isolated.
- Local verification: focused Doc311/Doc312 browser and projection suite
  passed (`17 passed`); the relevant V3 regression suite passed (`109 passed`)
  after the stale-failure regression was added; JavaScript syntax and diff
  checks passed.
- VPS deployment: `origin/main` commit `5a4d2a79023a6e60a3a189a95bfd49506b371bc8`
  is deployed in the running `alchemy-media-agent` container and `/healthz`
  returns the healthy service response.
- VPS read audit: 13 known project scopes returned HTTP 200; 140 output
  records were checked across 420 thumbnail/preview/download requests with
  zero media failures; a foreign output request remained HTTP 404.
- Real browser verification with Cookie-only authentication: standard V3
  loaded 12 projects after “加载更多”; review-only project history galleries
  loaded their actual images; the professional workspace loaded its project
  after paging. The forced stale-failure race aborted the old request and
  still rendered project B's 9/9 images with no page errors.
- Product meaning: a home card showing `0 张图片` for a review-only legacy
  project means zero formal delivery images in the home contract, not that the
  stored review pixels are inaccessible. The explicit “查看图片” modal now
  exposes those pixels with a `待复核` label and never promotes them to formal
  delivery.
