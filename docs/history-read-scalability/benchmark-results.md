# Offline history-read benchmark results

Measured 2026-10-11 against immutable baseline `5a33c05e3f54dbef786eb179973ec1407511b4e4`.
This is isolated synthetic backend evidence, not production/VPS or browser acceptance.

## Main findings

- All 8,400 optimized uninstrumented hot requests returned the expected IDs, order, and totals; zero 503s. The baseline served 72 of 168 offered requests and rejected 96.
- At 50,000 rows, V1 hot p95 is 8.82 / 22.13 / 40.74 ms for concurrency 2 / 4 / 8. Lab is 27.48 / 56.04 / 93.99 ms; V2 is 4.69 / 9.78 / 22.99 ms.
- Warm decode/SQL/filesystem work is page-bounded across 1k–50k histories. Cold construction is still substantial and increases disk space and logical writes; prepare indexes before serving bursts.
- Lab's old 10,000-row window was a correctness bug: owner 42 at 50k has 18,182 visible non-mock records, but baseline reports 3,637. An independent 10,001-row oldest-owner fixture returns 0 instead of 1 on baseline and 1 on optimized.

## Method and comparability

The main matrix uses 100 / 1,000 / 10,000 / 50,000 source rows, concurrency 2 / 4 / 8,
and limit 50. Each optimized cell has 50 batches: 100 / 200 / 400 successful samples.
Baseline has one batch per cell because V1's full scan is expensive; every baseline
p95 is deliberately null. Baseline p50 below has only two successful samples.
The frontend's page size is 24; a separate page-24 diagnostic checks 1k and 10k rows.

Actual async GET handlers run without HTTP transport, app lifespan, external auth,
or Provider calls. Requests alternate synthetic non-admin owners 42 and 77. V1/V2
include public records; Lab uses its own-owner/non-mock rule. V1 has N jobs, N
canonical outputs, N manifest records and N matching generated paths. Each baseline
and optimized source JSONL SHA matches. Correctness uses fixture truth, not baseline
parity. General payload-contract preservation is covered by the regression suites.

Fresh subprocesses separate source import/index construction, process-cold reads of
an existing index, and repeated hot reads. Setup warms the OS cache; “cold” does not
mean disk-cold. Hot timing and intrusive diagnostic passes are separate. Linux,
Python 3.12.14, SQLite 3.53.1; dependency versions are in each report. Worker CPU
affinity exposes nine CPUs, while the application pool is fixed at two workers;
there is no 2-vCPU pinning or memory-limit qualification. Shared-cloud timings can
vary, and earlier exploratory timing overlapped unrelated regression work.

## Full optimized hot matrix

Milliseconds, with peak worker RSS for concurrency 8. All cells are correct with zero 503s.

| Surface | Rows | p95 C2 | p95 C4 | p95 C8 | Peak RSS C8, MiB |
|---|---:|---:|---:|---:|---:|
| V1 | 100 | 10.91 | 18.88 | 38.38 | 85.2 |
| V1 | 1,000 | 9.07 | 16.76 | 34.25 | 85.2 |
| V1 | 10,000 | 10.25 | 22.07 | 40.14 | 85.0 |
| V1 | 50,000 | 8.82 | 22.13 | 40.74 | 85.4 |
| LAB | 100 | 21.80 | 42.75 | 80.96 | 84.7 |
| LAB | 1,000 | 27.80 | 53.85 | 105.71 | 86.6 |
| LAB | 10,000 | 29.24 | 56.17 | 101.27 | 86.6 |
| LAB | 50,000 | 27.48 | 56.04 | 93.99 | 86.6 |
| V2 | 100 | 5.64 | 9.95 | 22.46 | 91.0 |
| V2 | 1,000 | 6.10 | 9.56 | 20.28 | 91.2 |
| V2 | 10,000 | 6.01 | 10.48 | 21.82 | 91.2 |
| V2 | 50,000 | 4.69 | 9.78 | 22.99 | 91.9 |

## 50k hot CPU, I/O and RSS comparison

Concurrency 2, per successful request except process peak RSS. Baseline Lab is
**incorrect** at this size; its timing is not a correctness-equivalent comparator.
`rchar` is logical process-read bytes, including SQLite and measurement overhead,
not physical disk traffic.

| Surface | p50 ms, before → after | CPU ms/request, before → after | Logical read MiB/request, before → after | Peak RSS MiB, before → after |
|---|---:|---:|---:|---:|
| V1 | 59291.73 → 7.27 | 42626.50 → 5.39 | 2386.514 → 0.307 | 184.6 → 85.2 |
| LAB | 740.72 → 19.73 | 438.80 → 13.16 | 52.907 → 0.289 | 183.0 → 84.5 |
| V2 | 13.11 → 3.86 | 11.98 → 2.87 | 4.331 → 0.166 | 97.4 → 90.8 |

At concurrency 8, baseline succeeds twice and rejects six callers per burst;
optimized succeeds 400/400 per cell. Every optimized timing cell ends with submitted
work actually completed, zero in-flight/pending work, peak running ≤2 and pending ≤6.
The largest observed admission wait is 96.65 ms, below the 250 ms bound. Queue-full,
expiry and cancellation behavior is exercised deterministically rather than inferred
from these successful bursts. Writes retain immediate admission; read FIFO does not
promise cross-class starvation freedom.

Across the 50k/C8 cells, post-GC RSS is 85.4 / 86.6 / 91.8 MiB (V1/Lab/V2).
Within any 50-batch timing cell, first-to-last batch RSS growth is at most 2.27 MiB.
This supports bounded reuse in these runs, not a proof that no long-duration leak exists.

## Measured work per warm request

At limit 50 and histories of 1k, 10k and 50k, these counts remain the same:

| Counter | V1 | Lab | V2 |
|---|---:|---:|---:|
| Payload JSON/model decodes | 50 | 50 | 50 |
| Authoritative source/job decodes | 0 | 0 | n/a |
| Native winner rows visited | 51 | 50 | n/a |
| Native file existence checks | 0 | 50 | n/a |
| Directory entries visited | 0 | 0 | 0 |
| Python filesystem stat calls (all fixture paths) | 8 | 155 | 7 |
| SQL fetched rows (all traced connections) | 115 | 163 | 67 |
| SQL statements, including metadata/transaction work | 89 | 127 | 21 |
| SQL connections | 3 | 2 | 3 |
| Native page-query VM-step counter | 3,100 | 3,700 | n/a |

Lab intentionally checks only returned files to exclude missing outputs. At 100
source rows, it has fewer than 50 visible items for each owner, so its work is smaller.
The generic 1,000-step callback does not fire for V2's small warm statements; missing
VM counts are not evidence of zero engine work. The page-24 supplement uses 100-step
callbacks: V2's generic VM lower bound is 900/request at both 1k and 10k. V1/Lab native
page counters are 1,650/2,000 and all three decode 24 payloads.

For comparison, baseline V1 at 100→1k rows fetched 1,585→15,355 SQL rows, ran
2,963→29,250 SQL statements, decoded 110→1,100 JSON plus 350→3,050 model payloads,
and visited 200→2,000 directory entries per request. Baseline Lab decoded 100→1,000
records and made 104→1,004 stat calls. Baseline V2 already decoded one page, but its
SQL VM lower bound rose 1,000→11,500. SQL fetched rows and VM steps are not exact
engine rows scanned; native and generic counters have different scopes and must not
be indiscriminately added.

## Cold construction and disk tradeoff

Uninstrumented first-read wall seconds, before → after. Each is one sample.

| Surface | 100 rows | 1k rows | 10k rows | 50k rows |
|---|---:|---:|---:|---:|
| V1 | 0.051 → 0.069 | 0.515 → 0.561 | 5.193 → 5.699 | 24.016 → 29.687 |
| LAB | 0.009 → 0.053 | 0.051 → 0.463 | 0.509 → 4.666 | 1.641 → 22.915 |
| V2 | 0.006 → 0.008 | 0.026 → 0.032 | 0.236 → 0.314 | 1.098 → 1.672 |

The new projection adds one-time work. At 50k, final synthetic file sizes grow
149→477 MiB for V1, 83→268 MiB for Lab, and 78→82 MiB for V2. These sums exclude
filesystem block/directory overhead and are not peak transient storage. Cold logical
write counters are approximately 3.00 / 2.55 / 1.34 GiB respectively, versus
0.30 / 0.13 / 0.09 GiB on baseline. All reported physical read/write byte deltas are
zero on this cached cloud filesystem; do not infer zero real disk cost or SSD endurance.

A diagnostic run discovered a quadratic cold query: `kind='history' AND file_path=?`
used a kind-only index scan (50,016 VM steps for one miss at 10k rows). The added
composite `(kind,file_path)` index has a no-ANALYZE plan/VM regression test. Corrected
cold diagnostic work is 1.533M→15.298M VM steps for V1 and 1.210M→12.081M for Lab at
1k→10k rows. Final uninstrumented 10k→50k time grows 5.70→29.69 s and 4.67→22.91 s,
respectively. Superseded exploratory runs are excluded from the acceptance artifacts.

## Fixture and safety boundaries

Generated filenames satisfy the real recovery rules. Their contents are identical
68-byte PNG-shaped fixed stubs, SHA-256
`6b1048f8a6d40bac0b2954c18fefa40c4ea7a96120fc2e54b7317c0e43c2bbec`.
The IDAT checksum is invalid; these are metadata-only fixtures, not valid-pixel images.
No thumbnail/preview codec or browser performance claim is made. All optimized runs
and supplemental checks reject generated-file content opens and Pillow/OpenCV decode
calls; all attempt counts are zero. The earlier full baseline V1 timing cells predate
that guard, while the separate baseline 100/1k diagnostics are guarded. The bytes did
not change. Valid-image API behavior is covered separately by existing smoke tests.

All reports show stable application-source fingerprints and unchanged checkout default
storage. No business storage, Provider, remote account or deployment was used. The
benchmark's direct GET calls omit transport, serialization delivery, browser layout,
network conditions and startup recovery. Deep offsets still traverse scalar index
entries; the primary timing matrix covers first pages, not arbitrary-offset guarantees.

## Evidence and reproduction

- [Baseline full matrix](evidence/baseline-valid-matrix.json.gz), [baseline work diagnostics](evidence/baseline-diagnostic-small.json.gz)
- [Optimized full matrix](evidence/optimized-valid-matrix.json.gz), [page-24/cold diagnostics](evidence/page24-diagnostics.json.gz)
- [Oldest-owner baseline](evidence/lab-old-owner-baseline.json.gz), [oldest-owner optimized](evidence/lab-old-owner-optimized.json.gz)
- [Read gate and measurement definitions](read-admission-and-benchmarks.md), [broader validation receipt](validation.md)

Raw reports are losslessly gzip-compressed to avoid committing megabytes of
repetitive JSON. Read with `json.load(gzip.open(path, 'rt'))` or decompress with
standard gzip tools; no measurements are removed. The source fingerprint remains
plain JSON. Generated uncompressed local copies are excluded from the commit.

The optimized application-source fingerprint is
`d4fea24995f6eef8903713a5383d43cb2209f0b9f31d2d19d30794979d77c0cb`;
baseline is `80212cb988b3f45ff44eef657ae9cedfea332e440cde278406769b0c432ffeb9`.
The final scheduler/safety check passes 51 tests (44 scheduler + 7 harness tests).
The benchmark script is Linux-only; scheduler interleaving tests use fake admission
clocks and generous synchronization windows for Windows/loaded CI.

```sh
# Separate V1/V2 Python environments are required. Never point fixtures at real data.
"$V1_PYTHON" scripts/benchmark_history_reads.py \
  --v1-python "$V1_PYTHON" --v2-python "$V2_PYTHON" \
  --sizes 100,1000,10000,50000 --concurrency 2,4,8 --rounds 50 \
  --diagnostic --output /tmp/history-read-optimized.json
# Baseline: add --repo /path/to/immutable-baseline and use --rounds 1.
# Page-24 supplement: --sizes 1000,10000 --concurrency 2 --rounds 1 --limit 24 \
#   --diagnostic --diagnostic-cold --vm-step-interval 100
# Tail check: --surfaces lab --sizes 10001 --concurrency 2 --rounds 1 \
#   --limit 1 --owner-mode old-owner
```
