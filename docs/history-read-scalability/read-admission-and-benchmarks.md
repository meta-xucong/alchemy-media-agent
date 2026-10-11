# Read admission and offline measurement

## Correction model and scope

Baseline: `5a33c05e3f54dbef786eb179973ec1407511b4e4`. V1/Lab and V2
independently own identical two-worker SQLite gates. Immediate admission rejects
short bursts even when their work would finish within an acceptable wait. A
deterministic blocked-worker probe at the baseline admitted 2 requests out of
2/4/8 concurrent requests, rejecting 0/2/6 respectively. Running work stayed
bounded at two; cancelled callers correctly retained execution capacity until
the real worker completed. These are scheduling observations, not endpoint
latency or production throughput measurements.

The primary performance repair belongs to indexed history projection. A queue
only absorbs bounded bursts; it cannot fix an O(N) read, increase CPU throughput,
or justify more workers. Preserve immediate `run()` admission for writes, Lab
checkpoint retry ownership, V2 task admission, public error responses, and the
existing cancellation invariant. V2 must not import the V1 implementation.

## Opt-in API and invariants

`BoundedSQLiteCalls.run_read(function, *args, **kwargs)` shares the existing
executor and execution semaphore. Production remains at two workers. Constructor
settings may reduce the default six waiting reads and 250 ms admission deadline;
they cannot increase those bounds. Only explicitly selected history GET handlers
opt in. No application-wide shutdown lifecycle changes are required.

- FIFO read tickets wait outside the physical executor queue and own no worker
  permit. Deadline measurement uses a monotonic clock.
- Queue overflow and pre-submission timeout raise `SQLiteStorageBusy` with
  `capacity_full=True`; existing wrappers preserve 503 and `Retry-After: 1`.
- Cancelling a pending ticket removes it without executing its callable.
- Once submitted, cancellation cannot cancel its concurrent Future or release
  its permit. Release occurs only after actual work completion. The admission
  timeout never becomes an execution timeout.
- Completion wakes the oldest reader without reserving a permit. Immediate
  write calls may acquire it. FIFO applies among readers; strict write/read
  starvation freedom is not claimed because writes do not register as waiters.
- Same-pool nested read submission from a worker is rejected instead of waiting
  for workers occupied by outer calls. Synchronous repository calls stay direct.
- Per-caller wake events support multiple event loops. No waiter/helper threads,
  background polling tasks, unbounded labels, or retained response payloads.
- Explicit class shutdown for owners/tests stops new admission, rejects pending
  tickets, and drains submitted work. It does not wire a new server lifecycle.

Diagnostics distinguish submitted work, actual running work, pending readers,
completion, cancellation, queue rejection, wait expiry, SQLite busy, wait time,
and execution time. Counters are aggregates; they do not log private payloads.

## Interleaving verification

Use deferred executors and thread barriers: two active plus six pending; FIFO;
pending timeout/cancel; repeated cancellation storms; cancel after submit;
notification/timeout/cancellation races; immediate completions; submission failure;
SQLite busy and ordinary errors; multiple loops; nested read rejection; shutdown;
existing immediate-write behavior. Keep existing V1/V2 cancellation, SQLite
async-boundary, delete atomicity, durable queue, and Lab checkpoint tests.

## Reproducible offline benchmark

Use temporary synthetic storage only, deterministic IDs/timestamps/PNG-shaped inventory stubs,
explicit owner/public/admin and mock-Lab distributions, and separate V1/Lab and
V2 subprocesses (`app` is their shared import name). Primary matrix: 100, 1,000,
10,000, 50,000 physical history rows; concurrency 2, 4, 8; page size 50. Include
page sizes 1/200 and deep offsets as diagnostics. Validate response IDs, totals,
ordering, and ownership against fixture expectations, not just baseline parity.
Old target-owner Lab rows beyond 10,000 source rows must remain visible.

Separate logical cold index/import construction, process-cold reads of a built
index, and hot repeated pages. Fixture creation warms the OS cache; a fresh
process is not disk-cold evidence. Do not drop global kernel caches. No Provider,
network authentication, application startup recovery, or generation endpoint is
part of the benchmark. All source/derived data is temporary; verify checkout
default storage is unchanged.

Record offered/success/503 counts and reasons, success and error latency,
p50/p95/max, throughput, batch drain time, queue wait versus service time,
event-loop heartbeat, process CPU, and RSS before/peak/after/quiescent-GC.
Record `/proc/self/io` logical and physical byte counters separately. Instrument
application rows visited, deserializations, SQL statement/connection counts,
filesystem metadata calls, directory entries, logical file bytes, and temporary
index sizes in a separate diagnostic pass so overhead does not pollute timings.
SQLite trace callbacks count statements, not engine-scanned rows. Use fetched
rows plus EXPLAIN/VM-step diagnostics; never relabel VM steps as exact scanned
rows. Python filesystem wrappers exclude SQLite native C reads; process I/O
counters cover those separately.

Report rejection rates with latency: the baseline eight-request burst serves
only two callers, so successful-response p95 alone is misleading. Repeated
same-process batches should release responses before post-GC RSS measurement.
A stable retained RSS plateau can be allocator reuse; it is not a leak proof.
Tracemalloc can diagnose live allocations but cannot replace RSS.

Reuse fixture patterns from V1 history retention/API ownership tests, Lab history
tests, V2 history retention/migration tests, and the existing V3 benchmark's
isolation/monitoring design without changing V3 behavior. CI declares conflicting
V1/V2 SDK versions, so use separate Python environments and record exact versions.
Disable telemetry and dotenv discovery before importing application modules.

Synthetic results are development evidence, not VPS, browser, Provider, full
suite, or production acceptance. No deployment or business-data migration is
authorized by this work.

## Implemented command and evidence rules

The reusable harness is `scripts/benchmark_history_reads.py`. Example:

```sh
"$V1_PYTHON" scripts/benchmark_history_reads.py \
  --v1-python "$V1_PYTHON" --v2-python "$V2_PYTHON" \
  --sizes 100,1000,10000,50000 --concurrency 2,4,8 \
  --rounds 50 --diagnostic --output /tmp/history-read-optimized.json
```

Use `--repo /path/to/immutable-baseline --rounds 1` for the expensive baseline.
This deliberately provides limited baseline samples; the harness sets p95 to
null below 100 successful samples instead of presenting an unstable percentile.
Use `--owner-mode old-owner --surfaces lab --sizes 50000 --limit 1` to exercise an
owner whose sole non-mock record is older than the historical 10,000-row cap.
Use `--admission immediate` only to compare gate policy on the same optimized
read implementation; it is not a substitute for the immutable source baseline.
`--diagnostic` adds separate instrumented hot passes while leaving the cold-build
timing uninstrumented. Use the explicit `--diagnostic-cold` switch only when cold
work counters are required; those cold timings are not comparable to the normal
uninstrumented cold cells.
The generic SQLite progress interval defaults to 1,000 VM instructions; use
`--vm-step-interval 100` for the finer page-24 diagnostic. Smaller intervals
increase diagnostic overhead and still do not count exact engine-scanned rows.

Generated IDs obey the actual filesystem-recovery fullmatch rules: `out_` or
`job_` followed by at least 12 alphanumeric characters. The first exploratory
fixture used an extra underscore and therefore omitted filesystem-source rows;
its reports are explicitly superseded and are not acceptance evidence. The
corrected 100-row diagnostic observed 100 filesystem inventory entries during
cold construction, and zero entries/source decodes/file checks during two warm
pages. Fixture JSONL hashes and expected IDs/totals make subsequent comparisons
reproducible. Both initial process-cold and measured-hot correctness contribute
to the result.

Seed workers refuse existing directories. Read workers require the matching
synthetic-fixture marker. Every fixture must be under the system temporary
folder, outside the source checkout. Default storage inventory is checked before
and after the run. Measurements include real handler work and exclude initial
application import (reported separately); external account lookup is replaced
by an explicit synthetic authenticated owner. The application lifespan is not
started. Timing and intrusive diagnostic passes are separate. Native
`HistoryReadMetrics`, where available, give projection-specific counters;
SQL trace/fetch and Python filesystem counters provide baseline comparison.
Their scopes differ and counters must not be added together indiscriminately.
Process I/O captures temporary scratch writes; final `storage_bytes` is not a
claim to measure peak transient scratch-disk allocation.

The deterministic scheduler suite covers both independent implementations and
uses controlled admission clocks with generous synchronization windows, avoiding
Windows/loaded-CI dependence on a 20 ms scheduling opportunity. Focused results
after the full matrix: 44 scheduler tests and 7 benchmark safety/fixture tests
(51 combined). Earlier focused results included
49 combined scheduler/V1 boundary/cancellation tests; 34 V2 cancellation,
durable-queue, favorite-boundary, and route-admission tests. These groups overlap
and are not additive or full-suite acceptance.

### Image-content scope of this matrix

The inventory files contain identical 68-byte PNG-shaped fixed stubs (SHA-256
`6b1048f8a6d40bac0b2954c18fefa40c4ea7a96120fc2e54b7317c0e43c2bbec`).
Their IDAT checksum is invalid. They are not valid-pixel fixtures and no image
codec, thumbnail generation, preview rendering, or browser measurement is claimed.
History listing only inventories/stats the paths and reads metadata/SQLite.
The harness now rejects generated-image content opens through Python audit hooks
and rejects Pillow/OpenCV decoding calls; it reports these attempt counters.
Baseline and optimized inventory bytes, lengths, IDs, and timestamps remain
identical. Existing API smoke tests separately exercise real Pillow-valid images.
