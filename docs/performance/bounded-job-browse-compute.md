# Bounded Job decoding for output browsing

## Objective and scope

Improve concurrent image browsing without changing the API, image delivery rules,
JSON storage, or the single process that owns jobs and mutations. This is an
opt-in CPU isolation seam, not a conversion to multiple Uvicorn workers.

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

`V3_BROWSE_COMPUTE_WORKERS=0` is the default. `1` or `2` enables a reusable spawn
pool. Invalid values disable it; values above two are clamped to two. Keep one
API process. Set the value back to zero and restart for rollback; no migration
or cleanup is needed.

Only cold Jobs of at least 1 MiB are eligible for process decoding; smaller files
keep their original owner validation. This conservative byte threshold avoids
IPC overhead on ordinary histories; byte size is not a guarantee of CPU cost.
Admission is acquired lazily at the first eligible read, so an all-small request
does not consume pool capacity or receive a pool-overload error.

At most `workers + 1` eligible requests are admitted, with one submitted Job per request.
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

These cloud tests are not acceptance of the user's 2-core/2-GB VPS. Before
activation, repeat the benchmark and representative real read-only traffic on
that machine, including cold startup, active generation, concurrent owners,
large histories, cancellation, worker loss, and memory pressure. Choose the
worker count from successful request throughput and tail latency while leaving
memory headroom for the API, generation, image handling, and the OS. Do not
increase Uvicorn's worker count as part of this change.

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
non-regression. Keep the default off until the actual workload is measured.

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

No live provider, user computer, VPS, deployment, or merge was used. The
opt-in default and deployment qualification requirements remain unchanged.
