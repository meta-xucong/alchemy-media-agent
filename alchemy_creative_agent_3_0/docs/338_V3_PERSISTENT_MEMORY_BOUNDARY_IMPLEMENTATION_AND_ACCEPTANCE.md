# Doc338 — V3 Persistent Memory Boundary Implementation and Acceptance

Status: baseline and follow-up code are pushed to `origin/main`; this documentation update is pending its separate commit. VPS deployment and runtime RSS acceptance remain pending.

Baseline code commit: `2587864e` (`Bound V3 project and output memory`)

Follow-up code commit: `2c1e98bf` (`Fix V3 project output owner projection`)

## 1. Objective

Prevent ordinary V3 project browsing and output lookup from retaining an
ever-growing in-process copy of project, job, output, or validation data. Keep
the persistent JSON records authoritative and preserve existing paging,
ownership, output eligibility, and full-history query semantics where callers
explicitly request them.

This change bounds retained caches and avoids building a full output locator
for oversized catalogs. It does not promise a fixed process RSS: active
requests, Python allocator behavior, image decoding, and caller-requested
result lists still use temporary memory.

## 2. Correction model

Persistent files remain the source of truth. In-memory entries are disposable
read accelerators only.

- Project objects are weakly cached, so the store does not keep a project alive
  after all active callers release it.
- Project headers use a bounded 4096-entry cache. Timeline and private history
  are read for the active request instead of being retained as full histories.
- The Project Mode home path uses bounded project, job-state, and per-job output
  windows. It reads only the requested project page as full records.
- Output records use a 128-entry LRU; output integrity and image-validation
  caches use bounded 256-entry LRUs.
- A complete scoped output locator is retained only through 4096 records. Its
  per-file signature includes path, mtime, ctime, and size, so an in-place
  `output.json` edit invalidates a small-catalog index.
- Above 4096 output records, lookup keeps only a fixed-size path sample for
  threshold detection, discards the full scoped maps, then scans one output
  record at a time and yields only records matching the requested job or
  project. It does not create an all-history job/project dictionary.
- Project output queries allow up to 4097 results because Project Mode uses
  4097 as a completeness sentinel for a 4096-record boundary. Global history
  queries allow up to 10000 because an existing reconciliation caller requests
  that window. These limits remain bounded without silently reducing those
  existing queries to 256.

The scoped locator remains a candidate finder only. Loaded records are
exact-matched, and Project Mode rechecks authoritative owner visibility before
returning a project.

Project-scoped legacy Job owner fallback reads request metadata through the
same projection-aware helper as the strict owner predicate. A missing/empty
owner may use the existing narrow project-output fallback; a mismatched or
malformed non-empty owner remains denied. Lightweight status projection keeps
`missing_role_keys` so specialized output diagnostics retain the missing-role
explanation. Output ordering is explicit: `created_at` descending, then
fixed-width V3 output ID ascending for ties.

## 3. Scope

Files touched across the baseline and follow-up:

- `app/project_mode/store.py`: weak project-object cache, bounded project
  header cache, and non-retention of full timeline/private-history payloads.
- `app/project_mode/service.py`: bounded page and home-preview reads while
  preserving owner filtering and cursor/order behavior; follow-up preserves
  owner-gap checks across lightweight Job snapshots and retains missing-role
  diagnostics.
- `app/product_api/service.py`: bounded retained Job-record cache and file
  revision checks; the follow-up makes persistent `count()` count durable Job
  files rather than weak-cache entries.
- `app/product_api/outputs.py`: bounded record/validation caches, bounded
  history pages, scoped output lookup, per-file index freshness, and
  follow-up `os.scandir` iteration with stable tie order.
- `tests/test_v3_persistent_store_memory_bounds.py` and
  `tests/test_v3_provider_output_production.py`: regression coverage for
  cache limits, pagination, output limits, scoped-index behavior, and large
  catalog lookup, owner-projection parity, durable counts, output ordering, and
  lazy directory enumeration.

The baseline behavior above was pushed in `2587864e`. Owner parity, durable
count, stable ordering, missing-role diagnostics, and lazy directory iteration
are follow-up corrections and are not part of that baseline commit.

No V1 or V2 behavior, provider routing, generation prompts, review decisions,
output eligibility rules, persistent output retention, or VPS configuration
was changed by this memory-boundary commit.

## 4. Acceptance evidence

The following offline regression command passed after the follow-up code edits,
excluding one unrelated browser assertion described below:

```powershell
$env:V3_LLM_BRAIN_REMOTE_ENABLED='false'
src_skeleton\.venv\Scripts\python.exe -m pytest -q `
  alchemy_creative_agent_3_0/tests/test_v3_provider_output_production.py `
  alchemy_creative_agent_3_0/tests/test_v3_persistent_store_memory_bounds.py `
  alchemy_creative_agent_3_0/tests/test_v3_doc320_scoped_output_read_boundary.py `
  alchemy_creative_agent_3_0/tests/test_v3_doc284_project_pagination.py `
  alchemy_creative_agent_3_0/tests/test_v3_doc301_home_bootstrap_performance.py `
  alchemy_creative_agent_3_0/tests/test_v3_doc311_legacy_project_output_projection.py `
  alchemy_creative_agent_3_0/tests/test_v3_doc284_account_boundary.py::test_project_output_projection_requires_both_job_and_output_owner `
  -k "not desktop_explicit_history_modal_reveals_project_review_pixels"
```

Result: **117 passed, 1 deselected in 29.77s**. The excluded browser test
also fails when run alone: it expects `thumbnail_url` but receives
`preview_url`. This is unrelated to the memory/owner correction; no frontend
URL-selection code changed in this follow-up.

The baseline received an independent read-only review. A later audit found a
P1 owner fallback mismatch between full Job records and lightweight snapshots.
This follow-up routes the fallback through the existing projection-aware
metadata helper and tests missing owner without a Job project link, matching
owner, mismatched owner, and malformed owner across full records and
lightweight snapshots. It also fixes persistent `count()` to count durable Job
files instead of weak-cache entries. Existing Doc320 regression coverage moves
a warmed output record from one project ID to another and verifies both scopes
after the edit.

No real image generation, model/provider request, or VPS deployment was part
of this acceptance. A separate broader test attempt earlier in the work tried
to contact the configured remote Brain and was stopped; its result is not
counted as a pass. The final command above explicitly disabled remote Brain
access.

## 5. Known limits and operational follow-up

- `list_by_job(limit=None)` intentionally preserves its full-history behavior
  and can materialize all outputs belonging to one job for that request. This
  is request-scoped memory, not a retained cache; callers that need a bounded
  window should pass `limit`.
- A large output catalog still requires an O(N) sequential metadata scan to
  locate one project or job. Directory entries are consumed through lazy
  `os.scandir` iteration rather than a `Path.glob` list, but the scan still
  reads one complete `output.json` byte buffer at a time. Global history pages
  also deserialize records sequentially and retain only the requested top
  window; total I/O still grows with catalog size. The separate MCP operation
  ID index is not accessed by ordinary project browsing and remains outside
  this change; this document does not claim every application index is bounded.
- Bounded object caches prevent browsing from retaining every object forever,
  but do not guarantee that the operating system immediately returns freed
  allocator arenas or that RSS stays at one exact number.
- VPS memory behavior still needs a separate post-deployment observation under
  repeated project pagination and detail browsing. This commit has not been
  deployed to the VPS.

## 6. Completion criteria

- [x] Baseline code and focused regressions committed and pushed to
  `origin/main` at `2587864e`.
- [x] Follow-up code and focused regressions committed and pushed to
  `origin/main` at `2c1e98bf`.
- [x] Independent read-only A2 code audit passed.
- [x] Development and acceptance record added in this document.
- [x] Follow-up owner-scope, ordering, diagnostics, durable-count, and
  lazy-directory changes pass the documented regression run and independent
  A2 code audit.
- [ ] Deploy through the approved VPS path and verify GitHub/local/VPS commit
  parity.
- [ ] Observe memory across repeated project pagination/detail requests and
  confirm retained application caches stay bounded in the running process.
