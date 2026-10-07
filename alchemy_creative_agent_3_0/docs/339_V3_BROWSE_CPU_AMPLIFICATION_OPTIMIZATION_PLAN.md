# Doc339 — V3 Project-Browse CPU Amplification Optimization Plan

Status: implementation contract; document audit pending. No source changes,
tests, real model calls, or deployment are included in this planning milestone.

Baseline: `origin/main` / local `main` at `1200f21483af23c588f5b2ffd683070743379625`.
The same release was the target of the recent bounded VPS browse observation.
Memory-boundary authority: Doc338. Scoped output freshness authority: Doc320.

## 1. Total objective and current phase

**Total objective:** reduce CPU seconds and visible stalls during V3 project
listing, opening, history browsing, and image preview on a 2-core / 2-GiB VPS,
without undoing the memory bounds or changing project visibility, output
eligibility, review, historical compatibility, or generation behavior.

**Current phase:** freeze a bounded implementation contract, obtain an
independent read-only document audit, implement only after `PASS`, then obtain
an independent code audit. Push the fully audited result to `origin/main` only
after all required checks pass. VPS deployment and live-load acceptance are
not authorized by this document.

## 2. Baseline evidence and limits

The user-provided audit of `1200f214` identifies six CPU-amplification paths.
Its operation counts and synthetic JSON timings are mechanism evidence, not a
measurement of the VPS request that previously reached one-core saturation.
They must be reproduced locally against the frozen baseline before use as code
acceptance evidence.

Read-only VPS evidence collected during project opens:

- The host reports 2 CPUs. Docker has no CPU quota or cpuset restriction.
- The sampled cgroup CPU rate briefly reached about 100%, which is one fully
  occupied core under this sampler, or roughly half of the two-core host's
  aggregate capacity. It is not evidence that both cores were saturated.
- CPU returned below 1% after the opening activity stopped. A later point
  sample showed the Python process below 20%.
- In the same browse round RSS peaked near 650 MiB and returned near 512 MiB;
  host available memory remained above 780 MiB. The container did not restart
  and was not OOM-killed.
- No per-route duration, profiler sample, or per-operation counter was
  collected. The evidence does not attribute all observed CPU to one function.

Code evidence on this baseline:

- The deployed Docker command starts one default Uvicorn worker.
- Several `async` project-read routes call `_run_v3_handler` synchronously.
- Opening a project requests a summary and preview, then starts background
  timeline, project-output, visual-asset, and latest-Job restoration work.
- Project output reads use a request-scoped snapshot, but large-catalog
  `list_by_project` / `list_by_job` calls can each scan the output directory.
- Project-list pagination scans headers to preserve exact total and cursor
  behavior. The header reader avoids full model deserialization but currently
  walks the source JSON in Python.
- Output file integrity validation is already bounded and revision-aware;
  closure verification contains a second direct original-file SHA-256 read.
- The frontend has detail epochs and request-key deduplication in some paths,
  but an epoch alone does not abort already-started HTTP work. Protected image
  fetches must be inspected because setting `loading="lazy"` after a JS
  `fetch()` does not defer that fetch.

Classification: **D0** — the requested behavior and preservation constraints
are clear. **I2** — the work crosses the file locator, Job lifecycle snapshot,
project persistence, API scheduling, and browser loading paths. **A2** —
project ownership, durable freshness, review/hash evidence, and concurrency
behavior are adjacent invariants. The exact acceptance trigger is preventing
CPU optimization from changing those existing authorities.

## 3. Authorities, non-goals, and hard constraints

Persistent project, Job, and output records remain authoritative. Existing
project-owner checks, exact `project_id` / `job_id` matching, formal-delivery
predicates, review classifications, legacy Job-only output fallback, and
canonical-file integrity checks remain mandatory. Existing limits and cache
bounds in Doc338 remain in force.

This work is limited to V3 project browsing and image-history read paths. It
must not change V1/V2, generation, Brain/Provider routing, prompts, review
decisions, retry behavior, storage retention, or public response semantics.
It must not add Uvicorn workers, a database, an unbounded cache, a new generic
state framework, or a broad thread-pool fan-out. It must not contact real
models, generate images, deploy, or modify VPS configuration.

Any sidecar or request-local index is a disposable locator/projection only.
It may never replace the source record as an authorization, review, delivery,
or integrity authority. Do not log prompts, image bytes, auth headers, or
credentials in performance instrumentation.

## 4. Correction model and implementation work packages

### 4.1 Reduce output lookup from repeated full scans to one request scan

Add one request-local batch lookup in the existing output store for a project
and its declared Job IDs. For catalogs within the existing complete-index
bound, reuse the current revision-checked locator. Above the bound, perform a
single streaming pass over output records for the batch, retaining only
records whose raw locator fields match the requested project or one of the
requested Jobs. Exact-load and exact-match every candidate afterward.

The batch must preserve legacy outputs with no `project_id` when their
`job_id` is declared by the project. It must reject unrelated Jobs, foreign
explicit owners, stale candidate paths, and malformed records through the
existing predicates. It must not retain a whole-catalog map above Doc338's
threshold. A missing Job result must not trigger another directory scan in
the same request.

Acceptance: synthetic catalogs at 4,096 and 4,097 records; one project with
12 output-bearing Jobs and 60 no-output Job IDs; legacy Job-only output,
foreign project/owner, stale metadata, and absent Job cases. Instrument the
scanner: for the oversized catalog, a single project detail snapshot performs
one directory enumeration and reads each candidate metadata file at most once
for location, rather than one whole-catalog scan per Job. Returned records,
ordering, limits, and completeness must match the existing authority.

### 4.2 Load each durable Job at most once per request snapshot

The current snapshot may call `get_job()` for status and then
`get_job_record()` for owner/review fields. With weak-value caching the first
record can be released before the second lookup and the same large JSON is
parsed again. Reuse one strong request-local record and derive the existing
status and compact projections from it, preferably through one internal
Product API operation that preserves expired-artifact and background-timeout
semantics. Keep compatibility adapters that expose only the existing
methods.

Acceptance: a parse-counting durable store proves one parse per unique Job in
one snapshot; repeated Job IDs share that read; a later request observes a
changed file revision; expired artifacts, timeout state, output restoration,
and owner projections retain existing results. The record reference must be
released with the request and must not become a stronger long-lived cache.

### 4.3 Replace hot project-header parsing with a verified derived header

The project list needs only project ID, status, timestamps, and owner ID, but
the current streaming parser visits every source JSON character to skip large
history fields. Maintain a small derived header alongside each saved project
record. It contains only those catalog fields plus a schema version and the
source record fingerprint (`mtime_ns`, `ctime_ns`, and size).

On reads, use the header only when its schema and source fingerprint match the
authoritative `project.json`. Missing, malformed, or stale headers fall back
to the current streaming parser, then may be rebuilt. Serialize the paired
writes across all `PersistentProjectStore` instances in the process with one
shared project-metadata transaction lock; do not add an unbounded per-project
lock registry. The critical section spans authoritative project replacement,
source fingerprint capture, atomic sidecar replacement, and header-cache
publication. This may serialize writes for different projects, but must not
serialize ordinary reads. Never hold the global header-cache lock during
project or sidecar I/O. Bind publication to the exact serialized source bytes
for this save: after atomic replacement, read the authoritative file back,
confirm its bytes equal the saved payload, and capture its fingerprint across
a stable before/after stat pair. If the bytes or fingerprint change during
that check, do not publish the sidecar or cache entry; leave the sidecar
stale so the next read rebuilds from the authoritative file. If an external
writer replaces the file after the stable check, the sidecar retains the
checked source fingerprint and the next read detects the mismatch. This
readback cost occurs on saves, not warm list reads. A crash between writes leaves a fingerprint mismatch,
never a trusted stale header. External writers and same-size rewrites must be
detected by the existing source fingerprint checks. The header is rebuildable
and must not contain full project metadata or history. Store it beside the
project record so normal project deletion removes it with the containing
directory. This is one small durable sidecar per existing project; its disk
count scales with the number of project records. Doc338's 4096 bound applies
only to the in-memory header LRU, not to durable sidecars.

Acceptance: warm list reads do not invoke the character-stream parser for
unchanged projects; first read/missing/corrupt/stale header rebuilds safely;
external edit, same-size edit, cross-Store update, and archive/owner changes
are visible on the next read. A deterministic two-Store interleaving test
forces two saves to the same project to overlap and proves the committed
project, sidecar fingerprint/header, and published cache all reflect the
latest project revision; a stale header must never be trusted. A second
deterministic test injects an out-of-process-style source replacement between
the app's source replacement and fingerprint capture; publication must be
skipped and the next read must rebuild from the replacement. Pagination
order, exact `total`, `has_more`,
cursor boundaries, and owner filtering remain unchanged. A synthetic large
catalog demonstrates lower counted parser work without a hard wall-clock
threshold. The in-memory header cache remains bounded by the existing
4096-entry policy. Verify that deletion removes the colocated sidecar and that
no sidecar is retained in an in-memory map beyond the existing cache bound.

### 4.4 Reuse verified output bytes for closure integrity

Closure verification currently resolves a canonical download file, then reads
the original bytes and hashes them even though `file_for_variant()` has
already passed the output store's revision-aware canonical integrity cache.
Add/reuse one store-owned verification method so closure code can compare the
closure SHA with the record's immutable SHA and ask the store to validate the
canonical original through its bounded file-version cache. A cold or changed
file must still be hashed. Reuse is permitted only when output identity,
canonical path, file fingerprint, and expected digest all match. Invalidate
only the changed output's entries where existing write paths can identify it;
never make a changed file inherit another file's proof.

Acceptance: byte-read/hash counters show one verification on a cold file and
no repeat read for unchanged warm closure checks; a changed original, changed
expected digest, replaced path, bad closure digest, or bad record digest is
rechecked and rejected. Cache size remains bounded; delivery, media
authorization, and canonical-path checks remain in force.

### 4.5 Bound browser work and remove duplicate refreshes

For project-detail switching, propagate an `AbortSignal` through the existing
request helper to cancel superseded browser requests. Keep the current epoch
checks to prevent stale state application. Coalesce identical in-flight
requests. Do not treat client abort as proof that an already-running server
handler stopped.

For active Job polling, one unchanged poll tick should read the Job once and
must not refresh the full project, timeline, output history, and Job again.
Refresh only the projection whose authoritative version/status changed. A
terminal transition should schedule one shared refresh path, not duplicate
timeline/output loads from both the loop and completion branch.

Protected image loading must defer the Blob `fetch()` until the image is near
the visible viewport. Share identical in-flight URL reads and limit active
image fetches to two. Preserve authenticated fetch behavior, object-URL
cleanup, thumbnail-to-preview fallback, visible ordering, and error states.
Apply the same correction to mobile only where an equivalent V3 path is
confirmed; do not alter V1/V2 image behavior.

Acceptance: fake-fetch/browser tests assert zero offscreen fetches, at most two
active image fetches, one request for identical in-flight URLs, stale detail
requests aborted before enqueue where possible, one Job read per unchanged
poll tick, and one terminal refresh. Verify thumbnail success, preview
fallback, object-URL cleanup, and that failed/partial job messaging remains
unchanged.

### 4.6 Move only immutable header enumeration off the event loop

Do not move the full summary route or its service handler to a worker. The
handler loads shared mutable `ProjectRecord` instances from the weak Store
cache; a dictionary-cache lock would not make concurrent model mutation safe.
Instead, split the route at the narrowest safe boundary:

1. Add a Store operation that enumerates project headers into detached plain
   dictionaries. Protect only header-cache mutation with a narrow lock; never
   hold that lock while loading or mutating a `ProjectRecord`.
2. For `GET /api/v3/creative-agent/projects?view=summary`, run only that
   immutable header enumeration through a dedicated bounded worker gate. The
   route then passes the detached header list through an internal-only
   parameter to the existing handler/service path.
3. Keep pagination, selected-page full-record reads, live owner/status checks,
   authorization, and response projection on the existing event-loop path.
   Revalidate selected records against current Store state so a concurrent
   save, archive, owner change, or external replacement cannot make a stale
   header authoritative.

Only ordinary detached dictionaries may cross the worker boundary. Never
return `ProjectRecord`, `JobRecord`, ORM/model objects, open iterators, or
Store references from the worker. Do not thread the following routes in this
change:

- `GET /projects/{project_id}` with `view=full` or omitted view: full
  reconciliation/context work; the endpoint can inspect a Job and recover
  planned generation. The `summary` detail view is also excluded until its
  authentication lookup and mutable ProjectRecord read are replaced with a
  detached, revision-checked snapshot.
- `GET /project-outputs` for full, `delivery_preview`, or `home_preview`
  surfaces: projections can resolve Job state, expire watchdogs, or reconcile
  project outputs. Keep current serialized behavior while reducing repeated
  scans and parses in earlier work packages.
- Timeline, Job, output-media, writes, and all generation/recovery handlers:
  not moved in this phase; their complete side-effect and concurrency behavior
  has not been proven safe for a new worker boundary.

For the header-enumeration worker, admit at most **one active** scan and
**two waiting** requests per process. Acquire admission before submitting to
the worker so its queue cannot exceed two. If the gate is full, return HTTP
`503` with detail code `v3_browse_read_capacity_exceeded`, generic retry text,
and `Retry-After: 1`. Do not use Starlette's default 40-token pool as this
route's concurrency policy. Instrument active count, queue wait, and scan
duration without recording project contents.

Acceptance: instrumented tests prove only detached header enumeration reaches
the bounded worker, the event loop remains responsive during a controlled
slow scan, admission never exceeds one active plus two waiting, and a full
gate returns the specified 503/Retry-After. A concurrent project
save/archive/owner change or out-of-band file replacement must be reflected by
the selected-page live-record recheck and the next request. Authorization,
pagination, exact totals, and cursor results remain unchanged. Tests prove
excluded endpoints and all `ProjectRecord` reads remain on the existing
serialized path. No test may call a real Provider or model.

## 5. Implementation order and audit gates

1. **Gate A — document audit:** independently review this plan against
   `1200f214`, Doc338, Doc320, the repository AGENTS rules, and DOT's six
   findings. Return `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE`. No code is
   written until `PASS`.
2. **Batch 1 — amplify less:** implement 4.1, 4.2, and 4.5; add deterministic
   regression tests and inspect the diff.
3. **Batch 2 — cheaper verified reads:** implement 4.3 and 4.4; test
   sidecar freshness, source revisions, output integrity, and memory bounds.
4. **Batch 3 — bounded responsiveness:** implement 4.6 only for the proven
   safe routes and test side-effect exclusions and queue capacity.
5. **Gate B — code audit:** freeze the exact source diff and test receipts;
   an independent read-only auditor checks each acceptance item, ownership,
   freshness, integrity, side effects, unchanged V1/V2 scope, and Doc338's
   cache bounds. Any finding returns to a bounded correction and a new audit.
6. Run the complete focused V3 read-path test set, Python compile checks,
   frontend syntax and targeted browser/fake-fetch checks where available.
   Report unavailable browser tooling as unverified, not passed.
7. After Gate B and all required tests pass, commit the documentation and
   implementation with only task-owned paths staged, then push to
   `origin/main`. Do not deploy VPS in this task.

## 6. Required evidence and comparison

Create deterministic counters for directory enumerations, output metadata
reads, unique Job parses, project-header parser calls, original-image bytes
hashed, browser requests per project open/poll tick, event-loop delay, and
bounded-read queue wait. Do not make correctness depend on timing thresholds.
For CPU comparison, use a fixed synthetic fixture and report CPU seconds per
request before/after as supplementary evidence; state the operating system,
Python version, record counts, and fixture sizes.

For eventual VPS acceptance (a later, separately authorized task), compare
the same opening sequence and project set. Record per-route P50/P95, cgroup
CPU seconds, maximum RSS, MemAvailable, and whether the page becomes
unresponsive. The code task alone cannot claim that VPS CPU saturation is
eliminated.

## 7. Files and change boundaries

Expected implementation boundary, subject to the document auditor confirming
the minimal set:

- `alchemy_creative_agent_3_0/app/product_api/outputs.py`
- `alchemy_creative_agent_3_0/app/product_api/service.py`
- `alchemy_creative_agent_3_0/app/project_mode/store.py`
- `alchemy_creative_agent_3_0/app/project_mode/service.py`
- `src_skeleton/app/main.py`
- `src_skeleton/app/static/app.js`
- `src_skeleton/app/mobile_static/mobile.js` only for a confirmed matching V3
  request path
- focused tests under `alchemy_creative_agent_3_0/tests/`
- this document

No other source, dependency, deployment, storage-retention, V1, or V2 files
are in scope without returning to the document gate for a revised contract.

## 8. Completion checklist

- [ ] Independent Doc339 audit is `PASS` on the frozen document hash.
- [ ] Every work package has regression evidence and no acceptance item is
      waived by a benchmark or unrelated green test.
- [ ] Doc338 memory bounds and all ownership/review/delivery/hash predicates
      remain intact.
- [ ] Independent source-code audit is `PASS` on the final diff hash.
- [ ] Focused tests and syntax checks pass; unavailable browser tests are
      explicitly listed as unverified.
- [ ] Only task-owned files are committed; unrelated pre-existing working-tree
      changes are preserved and excluded.
- [ ] Local `main`, `origin/main`, and final commit SHA are reported.
- [ ] No VPS deployment, real model call, or real image generation is claimed.

## 9. Follow-up correction plan for baseline 17860f88

An independent review of `17860f88380f22c39e36637639bca51f1e17e1c1`
confirmed five acceptance defects and four additional CPU/lifecycle gaps.
The project-header revision conversion exception claim was not reproduced;
this follow-up still tightens revision shape/type validation so malformed
derived metadata safely falls back to the source record.

The source `project.json`, Job records, and output records remain authoritative.
The home-preview sentinel is only a bounded locator signal; it must not become
a completeness claim or a cap on full project detail. Full project detail must
retain every output previously visible through the project’s declared Jobs,
including legacy Job-only records, while locating them in one output-catalog
pass and avoiding a whole-catalog index above Doc338’s bound.

Implement these bounded corrections before any VPS validation:

1. **Separate complete detail from bounded home lookup.** Use the 4097 sentinel
   only for the home/count projection. For full project detail, stream and
   retain all exact project-linked and declared Job-only matches in the
   request snapshot. Keep the one-catalog-pass property and exact owner,
   project, Job, review, delivery, ordering, and history predicates. Add real
   store-to-detail regressions with 4096, 4097, and 4098 outputs, including a
   sole eligible delivery outside the first 4097 and the legacy Job-only path.
2. **Keep completeness separate from lookup success.** A successful batch call
   only means the query ran. On home/count reads, 4097 returned rows means the
   4096-row result is incomplete; never overwrite that sentinel result with
   `true`. Test exact counts and completeness at 4096/4097/4098 through the
   production batch method.
3. **Reuse records for failed Jobs and use linear de-duplication.** Pass the
   already batched output rows through failed/blocked output recovery instead
   of calling `list_by_job` again. Maintain a request-local set of output IDs
   beside each Job bucket so grouping remains linear for a Job with many
   outputs. Preserve all existing failure, review, ownership, and delivery
   gates.
4. **Bound deferred-image lifetime by DOM lifetime.** Before V3 list/grid
   replacement and history-modal closure, cancel pending observers, abort
   their image subscriptions, release object URLs, and remove entries for the
   removed subtree. Do not rely on a future IntersectionObserver callback for
   disconnected nodes. Add a deterministic repeated-render test proving the
   retained deferred-load map returns to the current live-node count.
5. **Retry changed output projections after read failure.** Do not commit the
   handled output signature before the project-output request succeeds.
   Distinguish successful empty results from a failed request, retain the last
   good projection on a recovery read failure, and retry with a capped
   backoff. Test failure then success at the same Job signature and prove a
   successful empty result does not loop.
6. **Lazily rebuild old or damaged project-header sidecars.** When a sidecar is
   missing or invalid, parse the source once and atomically rewrite the small
   derivative only if the project source revision is unchanged before and
   after. Serialize this with in-process project writes; an external race must
   leave the sidecar safely stale and eligible for a later retry. Do not grow
   the 4096-entry memory cache, batch-migrate the corpus, or let a sidecar
   authorize visibility. Validate exact revision shape/types and header field
   types; malformed sidecars fall back to the authoritative parser.
   Regression cases cover 4097 old projects across repeat scans and a fresh
   Store, sidecar corruption, malformed owner, malformed revision, deletion,
   and save/out-of-band interleavings.
7. **Consolidate terminal refresh and cancel abandoned queued scans.** A
   recovered terminal Job must flow through one completion refresh path rather
   than refreshing inside recovery and again during completion. Preserve
   required state restoration while avoiding duplicate project, timeline,
   output, and Job reads. When an HTTP waiter is cancelled, attempt to cancel
   its header-scan Future: a queued Future releases admission when cancellation
   completes; an already-running scan retains its slot until it actually
   finishes. Test repeated terminal completion request counts and queued
   cancellation followed by successful admission.

The correction set is bounded to the existing V3 output, project-store,
project-service, route, and frontend layers plus focused regressions and this
document. No new database, persistent cache class, worker pool, state framework,
public response contract, V1/V2 behavior, generation behavior, model call, or
VPS operation is in scope.

### Follow-up release gates

1. Independently audit this amendment against the source at `17860f88`, the
   confirmed DOT findings, Doc338, and repository rules. No code changes before
   document `PASS`.
2. Add the failing boundary tests first, then implement all seven corrections
   as minimal related changes. Keep full detail untruncated; keep only home
   lookup bounded.
3. Run focused output/project/store/frontend/route tests, compile checks,
   Node fake-fetch tests, and browser tests where the environment permits.
   Browser tests unavailable in this environment remain unverified.
4. Freeze the exact final diff and evidence for a separate read-only code audit.
   Any `FAIL` returns to a bounded correction and another audit.
5. Only after code audit `PASS` and all executable acceptance gates pass, commit
   task-owned files and push `main`. Preserve all existing unrelated local
   edits. Do not deploy VPS; actual server CPU/P95/RSS validation is a separate
   phase.

## 10. Implementation and local verification record

The follow-up corrections are implemented in the existing V3 project/output,
store, route, and desktop UI layers. Full detail now requests all matching
project/declared-Job outputs in one catalog query; the 4097 sentinel remains
limited to home preview. Failed/blocked Job recovery consumes that request's
records, and output grouping uses request-local identity sets. Project header
sidecars are repaired lazily from a revision-stable source under the existing
metadata transaction lock. Deferred images are explicitly released before V3
list/grid replacement or history-modal closure. Output projection signatures
are committed only after a successful read, failures preserve the last good
projection and use capped retry delay, terminal recovery delegates refresh to
one completion path, and cancelled queued scans cancel their Future where
possible.

Regression evidence on the local checkout:

- The new boundary tests first reproduced the truncation, completeness,
  sidecar, recovery reuse, and queued-cancellation failures. After the fixes,
  the focused Python output/store/project/route set passed **47 tests** after
  adding the batch-failure fallback and explicit 4098-row completeness cases.
- Five existing review-projection fixtures were migrated to override the
  production `get_job_read_snapshot()` status while retaining the stored Job
  record; no review/delivery assertion was removed. After those fixture
  migrations and the final audit corrections, the expanded adjacent Python set
  was rerun against the final source and passed **204 tests** (2 existing
  deprecation warnings, 509.52 seconds).
- The Node browse CPU suite passed **9 tests**, including repeated deferred
  image teardown, retry after a failed output read at the same signature, and
  one terminal projection refresh. `node --check src_skeleton/app/static/app.js`
  `python -m compileall` for the modified Python modules, and `git diff --check`
  passed.
- The 4097-project sidecar fixture confirms one source parse per old project,
  disk-sidecar creation, zero repeat parses on the next scan, and zero repeat
  parses after Store reopen, while the in-memory header cache stays at 4096.
- A real output Store-to-public-project-detail fixture places the sole
  review-qualified legacy Job-only output behind 4097 newer non-qualified
  records; the public detail projection still returns that output. A separate
  failed-batch fixture verifies the uncapped declared-Job fallback above 128
  rows, and home completeness is checked at 4096/4097/4098.
- Browser-driven tests and VPS CPU/RSS/P95 validation have not run in this
  environment. This record does not claim deployed performance improvement.
