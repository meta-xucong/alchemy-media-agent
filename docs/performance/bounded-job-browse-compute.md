# Bounded Job decoding for output browsing

## Objective and scope

Improve concurrent image browsing without changing the API, image delivery rules,
JSON storage, or the single process that owns jobs and mutations. This is a
bounded CPU isolation seam with a two-worker default, not a conversion to
multiple Uvicorn workers. Set the worker count to zero to disable the pool.

The accelerated path is `GET /api/v3/creative-agent/project-outputs` for the
full project image surface and the global output surface. Home-preview and
delivery-preview keep their existing lazy behavior and do not consume compute
admission. Project summary/detail, timeline, reconciliation writes, final public
projection, and provider generation are not moved into workers.

## Audit and correction model

A synthetic baseline contains 24 projects for two owners, 144 persisted Jobs,
and 144 offline PNGs. Project JSON totals approximately 31.5 MB; Job JSON totals
32.1 MB. Profiling attributes substantial output-browse CPU to the existing
Job request deserializer's recursive public-input validation. Full project
opening also spends CPU on deep copies and other reads. Profiling instrumentation
substantially inflates these small Python functions; use the separate plain
benchmark for latency, not cProfile timings.

Whole handlers cannot safely run in processes: output reads reconcile project
state; Job reads can expire a watchdog; project details can migrate continuity
state; header reads can write derivative sidecars; application startup owns
recovery of runtime jobs. Multiple API owners would also duplicate process-local
registries. The worker therefore runs only the existing JSON-to-typed-Job parser.

Returning a compact public Job status from a worker would duplicate a large
policy graph, including output closure and file-integrity reads. Instead, the
worker transfers one bounded, fully validated record. The owner immediately
runs the unchanged status/recovery/expiry predicates, compacts the result using
existing snapshot helpers, and releases the full record. This does not retain
all historical Jobs or replace the weak live-record cache with a history cache.

## Authority and freshness

- A resumable version of the existing read-snapshot loop selects exactly the
  same candidates. Its synchronous driver preserves existing callers.
- The async driver suspends only for detached Job decoding. It does not run a
  service, a store method, a provider, or `app.main` inside a worker.
- The parent selects local paths; worker input IDs and filenames are checked.
  Worker parsing never treats file contents as executable instructions.
- A returned record is accepted only for the exact requested identity and file
  revision. Existing mutable cache identities are never overwritten.
- A live Job identity, generating/finalizing Job, or changed project/Job/output
  scope causes one fresh synchronous fallback. It is not a new recovery policy.
- Before projection or reconciliation, the owner checks all captured revisions,
  project owner/status/membership, output catalog changes, output metadata and
  original-image revisions, closure revisions, and failure-expiry boundaries.
  No global lock is held over an await; no stale suspended project is saved.
- Domain lookup errors retain the existing snapshot error behavior. Infrastructure
  errors, overload, and timeout return a retryable 503 rather than an empty
  successful image list. Cancellation propagates and closes the suspended loop.
- Missing legacy timestamps, oversized records, malformed records, and unsupported
  store adapters retain the original owner path. Limits never truncate output
  lists or silently drop a valid Job.

## Bounds and lifecycle

`V3_BROWSE_COMPUTE_WORKERS` defaults to `2`. Set it to `0` to disable the pool,
or to any positive integer to request that many workers. Startup caps the
requested count to the CPU affinity/cgroup quota visible to the container, so a
larger VPS can use a larger explicit value without a source-code limit. Invalid
or negative values fall back to the default. Keep one API process; multiple API
processes would each create their own pool. Set the value to `0` and restart for
rollback; no migration or cleanup is needed.

Only cold Jobs of at least 1 MiB are eligible for process decoding; smaller files
keep their original owner validation. This conservative byte threshold avoids
IPC overhead on ordinary histories; byte size is not a guarantee of CPU cost.
Admission is acquired lazily at the first eligible read, so an all-small request
does not consume pool capacity or receive a pool-overload error.

At most `min(workers + 8, 10)` eligible requests are admitted, with one submitted Job per request.
The eight extra slots are a bounded burst queue, with a global cap of ten: with the default two workers,
ten heavy browse requests may be accepted, while the eleventh receives the existing
retryable 503 response. This increases admitted concurrency, not compute
throughput; requests beyond the two active workers wait in the executor queue.
Both source JSON and serialized return payload are capped at 4 MiB per Job.
A worker decodes one Job at a time, and the owner consumes/releases each decoded
record before requesting the next. Byte caps are not a claim that Python heap
usage equals file size: nested dictionaries and Pydantic objects expand in RAM.
The benchmark reports aggregate process RSS; real deployment acceptance must
also measure worst-case histories near the cap.

Spawn workers scrub inherited provider credential environment variables before
importing application contracts. They have no service instance or startup
recovery. This is trusted-code isolation, not an OS filesystem/network sandbox.

Admission remains occupied until physical work finishes after a caller cancels
or a 30-second read timeout. Releasing capacity on cancellation would permit an
unbounded executor queue. A broken process pool is discarded; a subsequent
request creates a fresh one. Shutdown stops admission and drains the finite
submitted work. It has no independent hard kill deadline: an OS-stalled file
read or stopped process requires the deployment supervisor's termination policy.
No automatic retry invokes providers or repeats mutations in a child.

## Verification

Run focused and existing backend regression tests with the repository's normal
Python environment:

```
python -m pytest tests/test_v3_browse_compute.py tests/test_v3_browse_compute_acceptance.py tests/test_v3_browse_cpu_optimization.py
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_persistent_store_memory_bounds.py
```

The standalone benchmark creates only temporary synthetic records and offline
PNG fixtures; it does not call paid providers. Run baseline, one worker, and two
workers on an otherwise idle machine with two-CPU affinity. Record warm/cold
latency, successful request throughput, API heartbeat stalls, parent/child CPU,
aggregate RSS, exact response parity, decode counts, and synchronous fallbacks.
Test both ordinary and history-heavy Jobs: IPC overhead can outweigh savings on
small Jobs, and more worker processes are not necessarily faster on two cores.

### Deployment acceptance is still required

The current two-worker VPS setting is a user-authorized controlled trial; it is
not proof of a production performance gain. Before raising the count above two
or claiming this optimization is performance-accepted, repeat the benchmark
and representative read-only traffic on that machine, including cold startup,
active generation, concurrent owners, large histories, cancellation, worker
loss, and memory pressure. Choose the count from successful request throughput
and tail latency while leaving memory headroom for the API, generation, image
handling, and the OS. Do not increase Uvicorn's worker count as part of this
change.

## Recorded cloud results (2026-10-08)

Environment: Python 3.12, FastAPI 0.141.1, Pydantic 2.13.4, Linux; the cloud host
exposed nine schedulable CPUs and approximately 9.7 GiB RAM. Endpoint processes
and children were pinned to CPUs 0 and 1. **No 2-GB memory limit was imposed.**
The benchmark invokes the real async endpoint directly, without HTTP transport,
uses two owners, 24 projects and 144 Jobs, and repeats worker counts in forward
and reverse order. Each measured run has six successful requests after a
separately measured warmup. These are small, noisy synthetic samples.

Reproduce with the repo on `PYTHONPATH` and its normal dependencies installed:

```
PYTHONPATH=.:src_skeleton python scripts/benchmark_v3_browse_compute.py --cpus 0,1 --surface detail --rounds 3 --order 0,1,2,2,1,0 --job-history-rows 100
PYTHONPATH=.:src_skeleton python scripts/benchmark_v3_browse_compute.py --cpus 0,1 --surface detail --rounds 3 --order 0,1,2,2,1,0 --job-history-rows 800
```

Choose CPU IDs allowed by the target host. For more stable deployment estimates,
increase `--rounds`; use `--surface global` to exercise the larger catalog.
`--diagnostic` and `--profile` are attribution tools, not latency benchmarks.
The script isolates default V1/V2/V3 storage and dotenv before importing the
endpoint, verifies eight runtime roots, and checks that checkout storage and
`.env` inventories were not changed. The heartbeat is restarted after warmup,
so cold-start stalls do not contaminate warm heartbeat statistics.

| Warm scoped output workload | Disabled | One compute | Two compute |
| --- | ---: | ---: | ---: |
| Ordinary Jobs (~223 KB), requests/s | 37.70–43.75 | 40.36–42.91 | 34.33–36.43 |
| Ordinary Jobs, child reads/processes | 0 / 0 | 0 / 0 | 0 / 0 |
| Heavy Jobs (~1.78 MB), requests/s | 7.24–9.85 | 8.80–8.82 | 10.35–11.29 |
| Heavy Jobs, median request latency | 154–217 ms | 215 ms | 163–194 ms |
| Heavy Jobs, p95 request latency | 206–297 ms | 243–244 ms | 205–211 ms |
| Heavy Jobs, maximum API heartbeat gap | 206–297 ms | 25–27 ms | 18–36 ms |
| Heavy Jobs, parent CPU per six requests | 0.62–0.85 s | 0.27–0.28 s | 0.23–0.24 s |
| Heavy Jobs, aggregate sampled RSS | 94–102 MiB | 182–183 MiB | 245–246 MiB |

All final runs had exact response parity, zero request errors, isolated runtime
roots, and unchanged checkout storage inventories. Eligible runs decoded 36
Jobs for six requests, with zero scope-change fallback. Two-worker processes
both accumulated CPU independently. Heavy two-worker throughput was roughly
5–15% above the fastest disabled sample, with much shorter API heartbeat stalls.
This is **not** a universal speedup: one worker was not consistently faster,
ordinary reads remain inline, and some ordinary enabled runs were slower despite
launching no children. The small samples do not establish production latency
non-regression. The historical recommendation to keep the default off is
superseded by the current operator-selected default documented above; the
performance evidence remains unaccepted.

Worker startup and first reads also matter: eligible process warmups took about
1.11–1.25 s in this run. Initial reconciliation remains on the owner and can
cost more than Job decode. Warm results must not be presented as cold first-open
latency. Existing project JSON hydration, output catalog scans, full-detail
reads, image integrity work, and generation remain possible bottlenecks.
Fixtures use 16-pixel PNGs, so they do not model production image-byte costs.

A separate dense-JSON probe decoded a 3,600,295-byte Job containing 900,000 empty
dictionaries in two workers. Each serialized result was 1,803,066 bytes, while
each worker peaked near 175 MB and the lightweight probe process tree reached
about 329 MiB. That probe did not include the full API process or unpickle both
records in it. It demonstrates heap amplification, **not** a maximum-RSS proof.

### Audit and test outcome

The final combined backend run passed **214 tests**, with 13 browser/UI cases
deselected, in 37.37 seconds. It covered both new test files, prior browse CPU
contracts, Doc301 home bootstrap, Doc311 legacy output projection, project-mode
output closure repair, project mode, persistent-store memory bounds, and timeout
recovery. `git diff --check` and Python compilation also passed.

The independent code review passed the frozen implementation. Its 88-test
selection overlaps the broader regression run and must not be added to that
run's count. The focused tests include actual spawned decoding, child crash and
pool recovery, timeout/cancellation admission retention, 1,000 rejected requests
under cancellation pressure, environment/import isolation, nonempty output
parity, ownership/archive/delete/version interleavings, late live identities,
malformed records, caps, and small-read admission bypass.

Browser/UI cases requiring Chromium were not run successfully because the
browser executable was unavailable. This backend change does not alter the UI.
No deployment, merge, provider call, or VPS qualification was performed.

## Early project-scope correction model (2026-10-08)

The authorization contract requires the ProjectRecord used for owner/status
filtering to match the durable revision guarded across asynchronous reads.
The initial guard instead sampled the file only after the service had loaded
and authorized the object. A transfer, archive, replacement, or deletion in
that interval could pair an old object with a new file revision (or absence).
This is a read-scope freshness defect in the async owner driver, not a provider,
projection-policy, or worker-decoding defect.

The store's existing weak identity and cached revision remain authoritative
for binding a loaded object to its source. The minimal repair is to require
that exact identity, a nonmissing cached revision, and a matching current file
revision at scope registration; otherwise close stale locals and use the
existing fresh synchronous fallback. A new stat alone is not evidence that an
already-loaded object belongs to that revision. Keep later checkpoint checks,
all policy predicates, public schemas, and bounded worker behavior unchanged.
No global scan, extra project decode, or lock across an await is needed.

A same-identity in-place transfer/archive (saved or still live) also invalidates
the earlier eligibility filter while leaving cache identity/revision valid.
Scope registration therefore reapplies the existing owner visibility predicate
and archive exclusion using the request owner. It does not invent an alternate
authorization policy. Deterministic regressions cover these variants as well.

### Correction verification

These results supersede the earlier frozen-review conclusion for project-scope
registration; the earlier 214/88 counts above are historical, not retests of
this fix. The baseline was the exact fetched PR head
`86f2f228fdfa945d36fe26f5d3259dc2d44ea6d0` in a separate cloud worktree.

Before the code change, 23 of 27 new deterministic cases failed. Each starts
with actual offline materialized outputs and injects the mutation immediately
before the original `add_scope`, after project loading and owner filtering.
The detail transfer leaked six outputs where a fresh synchronous request
returned zero; deletion returned data where a fresh scoped lookup raised
`KeyError`. Cases cover external owner transfer, archive, deletion, cache
replacement (including unchanged owner with changed title), and saved/unsaved
same-identity owner/archive changes across detail, global, and home preview.

After the fix:

- All **27 new regressions passed** (2.21 s), with exact fresh-sync response or
  exception parity. Existing real-output normal-path tests cover one/two-worker
  detail/global/home/delivery surfaces.
- The combined related regression run passed **244 tests**, with **10 actual
  Chromium-launch tests deselected**, in 37.72 s. The selection was the three
  browse test files listed above plus Doc301, Doc311, output closure repair,
  project mode, persistent-store memory bounds, and timeout recovery. This
  selection includes three source-level UI contracts omitted in the historical
  run, so its count is not simply the earlier total plus the new regressions.
- An initial unrestricted run passed those same 244 tests and failed the ten
  browser-launch cases solely because Chromium was not installed. Browser
  execution remains unverified. Eight existing FastAPI startup-event
  deprecation warnings remain.
- Independent review reran compute plus acceptance (**71 passed**, overlapping
  the combined run), reproduced the early races independently, checked both
  worker-eligible and inline-only modes, and verified rejection of absent
  cached identity/revision, deletion, and replacement during registration.
  Normal cached identity and weak-reference release checks passed.
- `git diff --check` and Python compilation passed. The fix adds constant-time
  per-project cache/eligibility checks to the existing one-stat registration;
  it adds no global scan, retained history, or additional project decode.

Historical scope note: that recorded run did not use a live provider, user
computer, VPS, deployment, or merge. Its default-off recommendation was later
superseded by the current two-worker controlled-trial default; deployment
performance qualification remains required before increasing the count or
making a performance claim.

## Output-snapshot provenance correction model (2026-10-08)

Output metadata prefetched for later Jobs (and project-linked records with no
candidate Job read) must retain the disk revision that produced each object.
Previously, the per-Job guard sampled output.json only when that Job reached
its suspension point. An in-place external owner repair or metadata deletion
during an earlier worker read could therefore bind an old object to a newer
revision or absence. The async response exposed six outputs while a fresh
synchronous response exposed five. This is a shared persistence/read-boundary
freshness defect; output ownership, Job expiry/recovery, and final-delivery
predicates remain the existing authorities.

The minimal complete repair has two parts: each loaded output carries private,
nonserialized read provenance, preserved on cache hits and beyond LRU eviction;
and every batch/fallback output read emits an owner-only registration event
before suspension or consumption. The async guard binds that evidence to the
current canonical path and rejects missing, changed, or unbound provenance.
Pre/post decode revisions must agree before a record receives usable evidence.
A new stat is only supporting evidence, never authority for old decoded bytes.
The synchronous driver ignores registration events and retains existing domain
read/error behavior. Scope changes close the generator and restart through the
fresh synchronous authority, outside the generator's domain-error handlers.

This includes project-linked orphan outputs, lazy compatibility reads, and
post-Job completion reads. Registration and final checkpoint validation are
linear in the output records/paths already visited, with no per-Job whole-scope
rescan, extra output decode, new global cache, or altered full-detail limit.
Read evidence lives only as long as its existing record object and does not
change persisted/public dataclass fields. Original-file, Project, Job, expiry,
and closure guards remain in force. No provider or delivery policy changes.

### Output-snapshot correction verification

The tested code/test commit is `77d36e37a57c90ebb94cb434dbd0a43b8f025170`
(tree `3b4db53525997f512016746b5f4689c2596fe503`), based on fetched PR head
`befc0834f0ef889cbc70f87f6fb4eb75fa2e9d41`. Subsequent edits to this section
are documentation-only. These results supersede the earlier snapshot-safety
conclusion and are not additive to the historical test counts above.

- The untouched baseline failed **10 of 12** deterministic matrix cases.
  Later output owner transfer/deletion during an actual earlier Job worker
  wait leaked stale records in detail/global, with large or small later Jobs.
  Project-linked orphan rows exposed the same bug in detail history: five
  formal items plus one history item should become five formal and no history.
- All **22 new repository regressions passed**. They cover those cases,
  registration gaps before the first await, external replacement/deletion,
  refreshed cache identities, live same-object metadata, combined-index
  fallback, bounded-LRU eviction without synchronous restart, unchanged
  persisted/public fields, and mutation during output JSON decoding. Fixtures
  contain real offline materialized images; parity is not empty-response-only.
- Independent final acceptance passed **285 Python tests**, with **10 actual
  Chromium-launch cases deselected** and eight existing FastAPI deprecation
  warnings (92.15 seconds). This is the existing 244-test backend selection,
  the 22 new tests, 17 external auditor cases, and two independent two-worker
  capacity cases. The repository-only portion is 266 tests; the external
  cases are independent simulation evidence, not additional checked-in tests.
  Separately, **19 Node VM/source frontend tests passed**. Rendered browser UI
  remains unverified because Chromium is absent.
- The independent capacity cases verified two distinct executing child PIDs,
  three physically retained admitted tasks after timeout/cancellation, 1,000
  further admissions rejected, later drainage to zero, and rejection after
  shutdown. Existing ownership, expiry/recovery, closure, full-history output,
  and persistent-memory regressions remained green.
- `git diff --check` and Python compilation passed. Default checkout storage
  inventories were unchanged. No provider, user computer, VPS, merge, or
  deployment was used.

Run the existing backend selection above with
`tests/test_v3_browse_output_snapshot.py` added. The frontend source/VM checks
are `node --test tests/v3_browse_cpu_optimization.test.mjs
 tests/v3_frontend_terminal_contract.test.mjs
 tests/v3_mobile_terminal_contract.test.mjs` (one shell command).

### Fresh performance qualification: no speedup established

A fresh independent run on the corrected tree repeated worker order
`0,1,2,2,1,0` for ordinary and heavy detail (five rounds, ten measured requests
per run), plus `0,1,2` for a heavy global smoke (two rounds). All **132 measured
requests and 30 warmup requests succeeded**; every measured response pair
matched the disabled baseline. Runtime roots were isolated and default
checkout storage was unchanged. There was no scope or child-decode fallback.
Ordinary Jobs stayed inline; heavy detail decoded 60 Jobs per ten requests,
heavy global 288 per four requests. Both workers accumulated CPU.

The Linux cloud host had nine CPUs and about 9.73 GiB reported memory. The
benchmark restricted endpoint/descendant CPU affinity to CPUs 0 and 1, but
**did not impose a 2 GiB memory limit**. The fixture used 24 projects, 144 Jobs,
16-pixel PNGs, and the real direct async endpoint without HTTP or providers.
Ordinary Jobs were approximately 223 KB; heavy Jobs approximately 1.78 MB.
A temporary observer retained every response pair and hashed them after the
timing interval. This adds small retained response-object memory; hash CPU is
outside timing. No benchmark instrumentation changed production code.

| Workload | Workers | Requests/s | p95 ms | Maximum heartbeat gap ms | Sampled process-tree MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary detail | 0 | 38.02–38.88 | 57–59 | 57–59 | 93–101 |
| Ordinary detail | 1 | 34.24–39.35 | 54–65 | 54–65 | 99–101 |
| Ordinary detail | 2 | 38.47–38.97 | 57–58 | 57–58 | 96 |
| Heavy detail | 0 | 10.03–10.60 | 229–239 | 229–239 | 97–102 |
| Heavy detail | 1 | 7.56–8.46 | 298–334 | 63–75 | 186–187 |
| Heavy detail | 2 | 8.68–8.97 | 293–351 | 80–114 | 249–250 |
| Heavy global smoke | 0 | 0.764 | 2640 | 2641 | 143 |
| Heavy global smoke | 1 | 0.631 | 3205 | 253 | 223 |
| Heavy global smoke | 2 | 0.766 | 2819 | 228 | 285 |

These monitored results **do not establish throughput improvement or latency
non-regression**. In these monitored runs, heavy detail was slower with one or
two workers; global throughput roughly matched disabled with two and was lower
with one. The observer-control result below prevents attributing that entire
measured slowdown to the product itself. Process
decoding reduced owner CPU and heartbeat stalls while increasing sampled
process-tree memory. Ordinary-path variation is noise despite no workers being
spawned. The earlier opt-in-default recommendation is historical and is
superseded by the current configured default. Earlier performance measurements
above are historical and must not be presented as a current speedup guarantee.

Process startup and reconciliation remain outside the warm measurements;
heavy detail worker warmups were approximately 1.12–1.39 seconds. Sampled RSS
excludes the fixture controller and is not a strict heap maximum. Actual VPS
memory headroom, real image costs, cold first-open behavior, and concurrent
generation still need separate deployment-specific qualification.

**Performance acceptance: NOT_ACCEPTED / HOLD.** Correctness and CPU-count
scaling do not establish a repeatable throughput or latency improvement. Keep
the PR Draft and do not describe this as a proven performance win. The current
VPS value of `2` is a user-authorized controlled trial; raising it further
requires measured CPU, P95 latency, and process-tree RSS with representative
histories. Roll back by setting the value to `0` and restarting. This supersedes
the historical 5–15% speedup interpretation. No further speculative tuning was
made in this correction.

A next design iteration needs a measured end-to-end cost breakdown separating
worker decode, per-Job submission/IPC, owner unpickle, output catalog/integrity
reads, and reconciliation. Reduced owner CPU alone is insufficient evidence
of faster completion. Any batching or crossover-policy proposal must retain
read-time provenance, final freshness validation, bounded physical admission,
and full-result semantics, then demonstrate repeatable latency/throughput
benefit and acceptable deployment memory before worker counts are raised above
the current controlled trial.


### Bounded low-observer control

One additional control removed the whole-`/proc` 10 ms sampling thread and the
2 ms heartbeat from the temporary benchmark copy, leaving the same two-CPU
affinity, heavy-detail fixture, and every-round response comparison. This
checks whether observer scheduling/GIL contention contributes to the monitored
results; it does not change production code. Worker order was `0,2,2,0`, with
ten rounds and 20 measured requests per run.

| Workers, in run order | Requests/s | p95 ms | Owner CPU seconds per 20 requests |
| --- | ---: | ---: | ---: |
| 0 | 9.719 | 269.1 | 2.056 |
| 2 | 9.718 | 232.6 | 0.770 |
| 2 | 9.283 | 312.8 | 0.826 |
| 0 | 9.215 | 277.9 | 2.170 |

All **80 additional measured requests and eight warmups** succeeded, with zero
errors, every measured response pair matching the disabled baseline, isolated
runtime roots, and unchanged checkout storage. This control intentionally
provides no memory or heartbeat measurement.

Two-worker throughput overlapped disabled throughput (approximately parity),
and p95 moved in both directions. The monitored slowdown therefore cannot be
attributed entirely to intrinsic product cost; neither an intrinsic regression
nor a universal speedup is established. The historical 5–15% speedup claim
remains superseded. **Performance acceptance remains NOT_ACCEPTED / HOLD
because a repeatable end-to-end benefit and latency non-regression have not
been demonstrated.** Keep the PR Draft and do not describe the change as a
proven performance win. The user-authorized VPS trial uses two workers; higher
counts remain gated on representative CPU, P95 latency, and process-tree RSS
evidence. No further tuning or benchmark runs were performed after this bounded
control.
