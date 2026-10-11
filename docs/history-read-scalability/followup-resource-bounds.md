# Follow-up resource-bound verification

This targeted follow-up compares the prior PR29 revision
`fd259486bebdda58eab506638991cdb04f9f1047` with the new preparation and
normalized-projection implementation. It preserves the original benchmark report
as historical evidence rather than repeating its full baseline matrix.

## Measurement contract

- Every dataset is freshly created under a marked temporary fixture root. V1/V2 use
  their separately resolved Python environments. Network connections are rejected;
  no lifespan, Provider, external auth, production data, generation, merge, or deployment runs.
- The harness calls real async GET handlers and their registered exception mappings.
  It does not measure HTTP transport, network delivery, frontend rendering, or browser memory.
- Cold request, explicit maintenance preparation, and prepared hot reads are separate
  subprocess phases. The prior revision uses the same explicit V1 preparation API,
  with only its obsolete implicit-building cold GET probe skipped.
- Corresponding before/after fixtures have identical source JSONL and authoritative
  Job/output SHA-256 hashes. Their full owner-specific page-response hashes also match.
  All retained reports have unchanged source fingerprints and unchanged checkout-default storage.
- Preparation timing is uninstrumented for the V1 disk comparison. Separate hot
  diagnostic passes count work. Lab/V2 readiness preparation is instrumented and
  is not a comparable timing result. Each V1 hot timing cell contains 100 successful
  requests at concurrency 2, page size 24. Lab/V2 diagnostic cells use two requests;
  their p95 is deliberately absent. These are shared-cloud runs without CPU isolation;
  timings are secondary evidence, not a hardware-capacity guarantee.

## Cold requests no longer perform maintenance

All seven unprepared probes return the expected `history_index_unavailable` 503.
The request-only audit guard records zero legacy-source content opens and zero
fixture-directory scans, at both 1k and 10k rows. Explicit prepare then succeeds;
all subsequent hot responses have the expected IDs, order, totals, and zero 503s.

The read guard permits metadata checks. V2's error-response JSON decoding is
included in generic diagnostic JSON counts; it is not a history source decode.
An absent index, incompatible derived schema, or exhausted catch-up budget requires
operator preparation. A large first dirty key is marked for maintenance, so retries
do not repeatedly spend the same catch-up budget.

Preparation still performs whole-dataset maintenance. It imports legacy sources,
constructs derived rows, and walks the file inventory. The public read path does not
hide that cost inside the read-admission queue. Existing-index upgrades require an
explicit rebuild; errors fail closed instead of invoking compatibility full scans.

## Disk and logical-write comparison

MiB, before → after. Storage is the sum of fixture file lengths after preparation.
Derived pages include all `v1_read_*` tables and indexes, including SQLite autoindexes.
Logical writes are Linux `/proc/self/io` `wchar`, not physical disk writes.

| Fixture | Total storage | Derived SQLite pages | Prepare logical writes | Prepare peak RSS |
|---|---:|---:|---:|---:|
| 1k outputs / one Job, 2 KiB common prompt | 10.90 → 7.67 | 8.73 → 5.50 | 40.81 → 34.19 | 113.85 → 89.85 |
| 10k outputs / one Job, 2 KiB common prompt | 107.96 → 75.68 | 86.95 → 54.66 | 617.36 → 552.74 | 144.54 → 122.29 |
| 10k outputs / 10k Jobs, default metadata | 93.47 → 94.38 | 64.25 → 65.15 | 534.14 → 536.83 | 121.28 → 92.16 |

Common Job display data is stored once and joined only for returned outputs. The
redundant single-column output index is removed: the `(output_id, session_id)` index
covers output-only lookups as well as ordered streaming. Preparation drops the old
index only after creating the replacement; ordinary connection/read paths do not
silently build an upgrade index.

The normal one-output-per-Job control is included deliberately: normalization has
little duplication to remove there, and its extra table/safety indexes still carry
small storage and write costs. This is not a claim of universally lower disk usage.
Fresh-fixture savings also do not guarantee an existing SQLite file shrinks after
rebuild. Freed pages are reusable; no VACUUM or automatic compaction is performed.

An intermediate candidate increased 10k shared-Job logical writes from about 617 MiB
to 2,331 MiB. The benchmark traced this to per-key savepoints during unlimited
maintenance. The corrected maintenance path relies on its existing atomic outer
transaction and omits unnecessary subjournals. Bounded ordinary catch-up retains
per-key rollback. Superseded candidate timings are excluded from acceptance artifacts.

## Memory and query-work bounds

The retained [source-fanout test stdout](evidence/followup-source-fanout.txt) records
Python temporary peaks of 21,356 / 21,073 / 21,073 bytes and SQLite VM-step counts
(1,000-step granularity) of 10,000 / 116,000 / 1,165,000.
The source-fanout regression uses 100 / 1k / 10k sources for one output, with
50 / 500 / 5k distinct sessions and 2 KiB of display payload per source. The resolver
streams scalar columns in indexed session order. Its test checks exact winner and
owner-conflict behavior, Python temporary peak below 512,000 bytes, and sublinear
peak growth across the 100-fold fanout increase. SQLite work remains proportional
to the number of scalar sources; it is not constant-time resolution.

For page size 24, warm V1 reads decode 24 output fragments and 24 common Job fragments;
Lab/V2 decode 24 history payloads. No authoritative Job is decoded and no directory
is scanned by unchanged prepared reads. Those work counts are unchanged between
1k and 10k fixtures. The source resolver and directory maintenance walk do not retain
all candidate payloads or all directory entries in Python.

This is not a universal fixed-byte memory bound. Parsing a single changed authoritative
Job record remains indivisible, and a page may itself contain large display fields.
SQLite native allocations and temporary-file work are not included in Python
`tracemalloc`; RSS is sampled at 10 ms and includes allocator effects. There is no
2-vCPU/VPS qualification, long-duration leak proof, physical-I/O or SSD-endurance claim.

Favorites are covered by focused API/SQL regressions rather than by another broad
performance matrix. At both 1k and 10k favorites, a deep page decodes exactly 24
payloads and never enumerates all favorite IDs in Python. The sparse-favorite query
uses the owner-favorites index followed by history output-ID lookups, with fewer
than 1,200 VM steps at 1k and 10k history rows. Exact filtered count/sort can still
scale with the matching favorite set; only scalar keys are sorted before payload
fetch. See `custom_media_agent_2_0/tests/test_history_favorite_paging.py` and
`tests/test_v1_lab_history_index.py` for the executable contracts.

## Safety and reproduction

The fixture images remain identical 68-byte PNG-shaped metadata stubs with an invalid
IDAT checksum. Content-open and Pillow/OpenCV guards record zero image reads/decodes
in every retained run. No image-codec, preview/thumbnail, or real-image quality claim
is made. The harness safety suite passes 18 tests in each of the V1 and V2 environments.

```sh
# Matching shared-Job disk/write workload. Temporary data only.
"$V1_PYTHON" scripts/benchmark_history_reads.py \
  --v1-python "$V1_PYTHON" --surfaces v1 --sizes 1000,10000 \
  --outputs-per-job 10000 --job-shared-bytes 2048 \
  --concurrency 2 --rounds 50 --limit 24 --diagnostic --output /tmp/fanout.json
# Prior PR29: add --repo /path/to/fd259486 --skip-cold-probe.
# Ordinary control: --sizes 10000 --outputs-per-job 1 --job-shared-bytes 0.
# Readiness/work supplement:
"$V1_PYTHON" scripts/benchmark_history_reads.py \
  --v1-python "$V1_PYTHON" --v2-python "$V2_PYTHON" \
  --surfaces lab,v2 --sizes 1000,10000 --concurrency 2 --rounds 1 --limit 24 \
  --diagnostic --diagnostic-cold --output /tmp/readiness.json
```

The historical `--index-lifecycle legacy-request` option is explicit and exists only
to reproduce old first-GET-building revisions. It is not the current default.

## Raw evidence

- [followup-before-fanout](evidence/followup-before-fanout.json.gz)
- [followup-before-standard](evidence/followup-before-standard.json.gz)
- [followup-after-fanout](evidence/followup-after-fanout.json.gz)
- [followup-after-standard](evidence/followup-after-standard.json.gz)
- [followup-readiness](evidence/followup-readiness.json.gz)

Raw reports are losslessly gzip-compressed. Each includes exact dependency versions,
source/harness fingerprints, fixture hashes, process I/O, RSS samples, SQLite object
page sizes and payload-byte totals. The final application-source fingerprint is
`a869bd9d2effa65baaa12a999dc9c0ef099cdd7383a9e58bd521d20e49896a94`; the harness fingerprint is
`2d19fe835f0d69616a0f107e3d47cbf32c20667fa45b3c0185e0bbb8303a4150`.
