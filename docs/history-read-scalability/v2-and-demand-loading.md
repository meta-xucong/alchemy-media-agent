# V2 history and browser demand-loading correction model

## Scope and authority

Frozen baseline: `5a33c05e3f54dbef786eb179973ec1407511b4e4`.
This is a scoped continuation of Doc51's durable, bounded retention work. The
total history-scalability task also includes independent V1/Lab read models and
bounded scheduling; this document covers only V2 history SQL, bootstrap case
existence, and desktop/mobile demand loading. A focused pass is not final
integrated or VPS acceptance.

V2 remains isolated: its repository/history/favorites databases are its own.
No V1 imports, V1 storage access, public schema changes, provider calls, data
expiry/deletion, deployment, or production-data mutation are authorized here.
Shared browser code may invoke each product's own API when that surface is
actually requested. The existing history payload, ownership, exact total,
limit/offset, favorite, and explicit mutation contracts remain authoritative.

## Observed mismatch and responsible layers

1. V2 history decodes only its SQL page, but its sole index starts with owner.
   Global ordering scans/sorts the table; own-plus-public OR scans/sorts all
   visible matches. This is query-planning cost, not evidence of a retained
   Python-object leak.
2. Every prompt-case detail invokes bootstrap, whose `list_cases()` emptiness
   test decodes all active cases. Account template enrichment can repeat this
   up to 30 times. Existence belongs in SQL; case-detail content remains keyed.
3. Both browser shells fetch 48 V1 or 72 V2 rows to display 24. Boot starts V1
   session/provider/history work even for another module. Account opening,
   ticket login, and closed-account post-mutation refresh can fan out both
   histories/usages plus template details. Empty/error V2 history retries a
   second route backed by the same service and authorization scope.
4. A late response can render hidden grids and start protected-image fetches;
   `img.loading="lazy"` does not defer JavaScript Blob fetches.

## Baseline evidence

Isolated in-memory copied-schema EXPLAIN and progress-handler probes, page 24:

| Rows | Global approximate VM steps | Own+public approximate VM steps |
|---:|---:|---:|
| 1,000 | 12,000 | 7,200 |
| 10,000 | 120,100 | 70,200 |
| 100,000 | 1,200,000 | 700,300 |

Global: `SCAN v2_image_history` plus `USE TEMP B-TREE FOR ORDER BY`.
Own+public: `MULTI-INDEX OR` plus temporary ordering. Owner-only already uses
indexed ordering. Counts were measured separately from these page queries.

Actual isolated `list_image_history(limit=24)` at 1k/10k/100k rows decoded exactly
24 ImageHistoryItem objects for admin or owner, and zero for missing
authenticated owner. This proves page-bounded decoding, not page-bounded SQL
work, RSS, CPU/P95 improvement, or production performance.

Node VM execution of actual desktop and mobile functions confirmed nonempty
V2 history makes one request, empty/error makes two, and account opening makes
five base requests before optional fallback/template detail enrichment.

## Initial backend query-plan milestone (historical; totals superseded below)

- Add global `(created_epoch DESC, job_id DESC)` history index.
- Read own and public records as disjoint indexed streams combined with
  `UNION ALL ... ORDER BY ... LIMIT/OFFSET`, allowing SQLite's ordered merge.
- Preserve exact count and read count/page from the same read snapshot.
- Release that read snapshot immediately after capturing the bounded page,
  before JSON decoding or independent favorites-store work can pin the WAL.
- Preserve stable baseline tie behavior with explicit regression fixtures.
- Use V2 repository `has_active_cases()` backed by `SELECT 1 ... LIMIT 1` for
  bootstrap. Preserve provider creation, persisted-index recovery, and seed
  fallback when no active cases exist.
- Do not alter template catalog filtering/ranking/page contracts. Those paths
  still materialize the active catalog; that separate limit remains explicit.

At this initial milestone, exact COUNT was still proportional to matching
index entries. That limitation is superseded by the approved count-bucket
completion below. Deep offsets remain proportional to offset plus page. The
initial milestone removed avoidable page sorting and full-catalog decoding
for existence checks; only the subsequent bucket implementation removes the
matching-history count scan from warm requests.

Creating the new global index on an existing database is a one-time O(N)
schema-initialization operation and adds persistent index bytes. Cold upgrade
cost must be measured separately from warm page reads. The existing strict
JSONL importer and its receipts remain unchanged; no source is replayed or
deleted to build this additional index.

## Browser compatibility constraints (fixed before implementation)

The browser correction must use demand at the resource-owning module/section,
single-flight loading, stale-response guards, and dirty invalidation rather
than a new global data/cache framework or UI redesign.

- Ordinary first and next history requests use 24 rows. Hero and grid share
  that result. V2 mock/nonrenderable records require bounded, needed refill to
  target 24 real cards; refill must stop on exhausted source or lost demand.
  Each visible demand permits at most three 24-row transport pages (the old
  72-row bootstrap budget). If still underfilled, retain explicit Load more.
  Track the raw source offset independently of renderable/unique item count;
  an all-mock page must never produce an unbounded auto-scan.
  Each subsequent gesture targets up to 24 additional displayed cards. Reuse
  enough buffered cards without reading; if the buffer supplies fewer than
  that target and raw history remains, fetch only the needed bounded refill.
  A previously underfilled display must not turn its unused render allowance
  into an oversized next page.
- Explicit favorites currently scan remaining history because no server-side
  favorite filter exists. Preserve complete requested favorites, while
  stopping further reads when the filter/picker is no longer demanded.
- Account summary count is sampled V1 up to 48 plus V2 up to 72, not exact
  all-time total. Template usage counts/top distinct cases derive from that
  same 72-row V2 window. Preserve these windows, loading them only when the
  relevant account overview content is demanded. Never relabel 24 rows as the
  previous sampled counts or silently replace them with all-time totals.
  These overview sample reads retain their 48/72 API limits; the 24-row
  transport rule applies to the ordinary module history first/next page.
- Usage amount is the sum of the existing first 100 entries per product;
  retain this contract even though the list displays 40 merged entries.
- An empty successful history response is authoritative. Errors remain errors
  with explicit retry; do not retry another same-source endpoint automatically.
- Ticket acceptance needs account identity, not all account overview records.
- Hidden account post-mutation refresh marks data dirty; visible demand loads
  it. Navigation and late responses must not start hidden image binding work.
- The visible account overview summary depends on all sampled history/usage
  windows above, so those bounded reads remain legitimate overview demand.
  API/MCP access does not demand them. Template detail enrichment and offscreen
  image grids wait for their section to become visible. This preserves current
  count/amount meaning instead of silently changing the summary contract.
- Preserve desktop Hero, module state, mobile surfaces, Back/Forward, filters,
  and returning to already loaded data. Do not modify V3 feature behavior.

## Validation gates

Backend: synthetic 1k/10k/100k rows; exact limit1/24 deserialization counts;
global/owner/public EXPLAIN with no page-query temporary sort; baseline-equal
IDs/order/total/favorites/access across ties and offsets; bootstrap empty,
inactive, persisted-index, warm keyed-detail behavior; strict import tests.

Frontend: execute actual functions with request spies in both shells. Cover
direct module entry, 24-row paging/refill, no hidden reads, single-flight,
empty/error, stale completion/navigation, ticket login, dirty invalidation,
favorites completion/cancellation, account sample windows/counts, and mobile
history dismissal. Browser acceptance remains separate from Node simulation.

No baseline timing here is a production benchmark. Final receipts must state
passed/failed/not-run stages, exact changed scope, and remaining integration
dependencies; do not claim a memory leak was established or VPS acceptance.

## Initial backend implementation receipt (historical)

New focused regressions first failed on the unchanged backend in four places:
global temporary ordering, own/public temporary ordering, count/page divergence
under an interleaved WAL delete, and full-catalog bootstrap decoding.

After the minimal backend correction, the new tests plus existing history,
strict migration, favorites and persistent repository tests pass: **201 passed**
with `/workspace/shared/media-history-v2-venv/bin/python -m pytest -q
tests/test_history_read_scalability.py tests/test_bootstrap_case_existence.py
tests/test_history_retention.py tests/test_history_migration_atomicity.py
tests/test_favorites_retention.py tests/test_persistent_retention.py`, from the
V2 source root. Modified backend files compile; `git diff --check` passes.

Before count buckets, the same synthetic distribution with corrected ordered
page queries yielded the following historical intermediate result:

| Rows | Global page VM steps | Own+public page VM steps | Own+public exact count VM steps |
|---:|---:|---:|---:|
| 1,000 | 155 | 472 | 4,039 |
| 10,000 | 155 | 466 | 40,029 |
| 100,000 | 155 | 466 | 400,029 |

These are isolated SQLite execution-work probes, not production timings. The
then-remaining exact-count scaling is intentionally visible and is superseded
by the count-bucket completion. Tests verify page
decoding stays at limit 1/24 at these sizes, missing authenticated owner decodes
zero, warm case detail decodes only its one requested case, and baseline
ownership/favorite/thumbnail/tied-order/offset behavior remains intact.

Frontend implementation and integrated acceptance were still pending at this
initial backend milestone. No commit, push, browser acceptance, Provider, deployment,
or VPS resource test is covered by this receipt.

Additional compatibility command from the V2 source root:
`ORT_DISABLE_TELEMETRY=1 OPENAI_AGENTS_DISABLE_TRACING=1
/workspace/shared/media-history-v2-venv/bin/python -m pytest -q
tests/test_v2_api.py tests/test_v2_strict_isolation.py tests/test_v2_contract.py
tests/test_case_cache_bounds.py` → **183 passed, 1 existing Starlette
deprecation warning, 29.76 seconds**. Existing API fixtures select temporary
data/storage/queue roots, mock image provider, disabled startup sync and remote
orchestrator; the new SQL/bootstrap tests do not start application lifespan.
This group is separate from, and may overlap with, other receipts; do not sum
groups into a claim of full-suite coverage.

## Existing frontend-test policy migration

Only obsolete frontend source-text expectations in these existing smoke tests
are authorized to change; unrelated API, runtime history and permission
assertions are preserved:

- `test_frontend_static_app_is_served` and
  `test_mobile_h5_app_is_served_independently`: replace the old literal 72-row
  ordinary first-page expectation with 24, and separately assert the retained
  account sample windows 48/72. The approved product policy, not an incidental
  new function spelling, is the reason for this change.
- `test_v2_template_catalog_is_not_blocked_by_slow_history_fallback`: the
  automatic same-source fallback is intentionally removed. Preserve the core
  invariant that slow history does not block template initialization and its
  existing bootstrap timeout; replace the obsolete private promise/epoch and
  fallback-function spelling checks with demand-loading expectations. Execute
  the real initialization function with a pending history request in Node to
  verify independence, and verify empty/error history never starts a second
  endpoint request.
  The updated test is named
  `test_v2_template_catalog_is_not_blocked_by_slow_history_demand`.

These textual migrations are supporting smoke coverage. The new behavioral
Node request-spy tests are the authority for actual request counts, paging,
stale owner isolation and navigation cancellation. They do not replace real
browser acceptance of layout, focus or visual behavior.

### Mobile close correction identified by behavioral tests

Two actual mobile surface-close scenarios initially failed: a sparse ordinary
read started with favorites-only filtering on the history sheet, then after
the sheet closed it continued a third page under the broader Hero demand.
The owning layer is the browser demand predicate, not backend pagination.

Capture whether a read began serving an explicitly visible favorite filter.
Its continuation predicate must retain that narrower demand and stop when the
sheet/filter/picker closes. A later Hero-only read with a remembered, hidden
filter counts all renderable rows rather than searching for hidden favorites.
This preserves complete explicit favorites and ordinary Hero behavior without
letting one demand silently expand into another after navigation. The two
surface-close regressions must pass before frontend acceptance.

### Cached-account delete invalidation parity

An actual-handler regression found the mobile V1 delete path lacked the
account invalidation already used by desktop V1 and both V2 paths. Under the
new lazy account cache, reopening the account could therefore retain a deleted
item. The minimal owning-layer correction is the same account invalidation
helper call after a successful mobile V1 delete; a closed account still makes
zero reads. This is cache coherence, with no deletion API/permission change.

### Failed first-page/favorites continuation correction

Final review identified and confirmed another browser-layer amplification:
the first-page wrapper caught a request failure, but `ensureHistoryDemand`
then continued into complete-favorites loading when a visible favorite filter
was remembered. That made an unrequested second same-endpoint attempt even
after removing the old cross-endpoint fallback. Return a success/read-valid
result from the wrappers and permit automatic favorites continuation only
after a successful current read. A partial refill failure also stops that
continuation. Execute the real orchestration with an active filter and failed
request to verify one request and a visible error, with no success-empty state.

### Parent full-V2 offline suite receipt

The parent reported **720 passed, 1 existing warning, 54.39 seconds** using the
file-backed `/tmp/media_history_pytest.py v2` harness, complete declared V2
dependencies, blocked socket connects and isolated storage. An earlier run
had 718 passed and two multiprocessing failures because the launcher was
`<stdin>`; those were harness `FileNotFoundError` failures. A file-backed
resource-guard group passed 10 tests before the full rerun. Do not combine
these counts with focused groups.

Timing qualification: the small snapshot-release `commit()` immediately after
page capture was added while that parent run was in progress and may not be
covered by its imported module version. The 201-test focused backend group was
rerun after that adjustment and passed in 1.92 seconds. A final frozen-code
full-suite receipt, if rerun by the parent, supersedes this qualification.

## Initial frontend frozen receipt (before Lab compatibility completion)

The frontend worker completed its owned files and a separate parent-agent
rerun of `node --test tests/*.test.mjs` passed **117 tests**, including **98 new
demand-history behavioral tests** and 19 existing V3 contract tests.
`node --check` passes for `static/app.js`, `mobile_static/mobile.js` and
`static/account-access.js`; `git diff --check` passes.

Focused Python smoke command used the shared V1 environment and selected the
three frontend tests listed above: **3 passed, 94 deselected, 6 existing
FastAPI lifecycle warnings**. These tests change only obsolete source-text
policy expectations; runtime history/permission assertions remain intact.

Coverage includes actual bootstrap/template progress with unresolved history;
ordinary first/next24 requests; sparse refill at most3pages; raw offsets despite
duplicates/mocks; cached partial-page refill; capped underfill0→24 and22→46 on
the next gesture; successful empty and failed requests without automatic
second attempts; full explicit favorites and cancellation; actual mobile
push/back/popstate/modal behavior; hidden mutation/delete invalidation;
48/72account and100-per-product usage windows; offscreen template detail
batching/cancellation; both account-access event-handler orders; stale
token/owner/session/provider/history/account/error/media responses; cross-tab
storage change/clear and the interval before event delivery.

The worker independently compared 715 V3-named function bodies across both
shells against the frozen baseline and found zero changed bodies. Shared
request helpers now reject stale-token unauthorized side effects; the image
binder's optional demand guard is used for V1/V2/account and preserves its
default behavior for existing V3 callers. Existing V3 Node contracts pass;
this is not full browser or V3 end-to-end acceptance.

Changed frontend scope: both shell JavaScript files, the account-view event
notification/duplicate-open guard in `static/account-access.js`, new
`tests/frontend_demand_history.test.mjs`, and the three authorized source-smoke
test sections. No commit/push, real Provider, production-data operation,
deployment, or real-browser visual/focus acceptance was performed here.

### Direct Lab configuration compatibility correction

The final shared-configuration trace found Lab submits `provider_preference`
from `state.selectedProvider`. Removing unconditional V1 boot without a Lab
replacement left direct Lab on a hardcoded provider instead of the configured
default/capability fallback. Lab therefore demands the existing shared
provider/settings pair itself, without any V1 session or history request, and
submission awaits that configuration. V1 and Lab share one in-flight provider
load with token/owner generation guards. This preserves existing Lab behavior;
it does not activate hidden V1 history. Pin direct Lab configured-provider and
fallback behavior, immediate submit, concurrent V1/Lab demand and stale auth.
Ordinary shared-configuration starts and stale-auth restarts also require
visible V1/Lab demand. An explicit Lab submission may await its required
configuration only for its captured auth context; cancellation must not
restart reads for a new owner after navigation to V2/V3.
The separate V3 consumer trace must confirm it has no former V1-state
dependency before final frontend acceptance.

## Count-bucket completion model (approved before implementation)

The original query-plan milestone leaves exact COUNT proportional to visible
history. That does not fully meet the user's page-dominated hot-read criterion,
so the next minimal V2-only step supersedes that residual-count limitation.

Use disposable global and owner/public count buckets in the existing V2
history database. INSERT, DELETE and owner-changing UPDATE triggers maintain
them atomically with each authoritative history mutation. Native conflict
upserts remain UPDATEs; rejected older upserts leave counts unchanged. Strict
JSONL imports and their rollbacks update/revert buckets in the same transaction.
Read one global or at most two own/public buckets and the history page in one
snapshot, then release it before favorites work.

Initialization is versioned and fenced by BEGIN IMMEDIATE: aggregate the
existing indexed owner column once, install all triggers, and publish a
separate derived-state version only on commit. Never change legacy import
markers/receipts. Existing derived state with missing/incorrect table, trigger,
version, or global counter fails closed. A missing requested owner/public
bucket is verified with an indexed existence probe before treating it as zero.
Explicit maintenance verification compares all derived counts against SQL
aggregates without decoding payloads. A writer-fenced rebuild replaces only
these disposable derived objects and never replays JSONL or changes history.

Managed history connections enable recursive_triggers. This is required for
SQLite INSERT OR REPLACE to run the implicit DELETE trigger before its INSERT
trigger; replacement behavior must be tested explicitly. Arbitrary manual SQL
through unmanaged connections, disabled recursive triggers, or direct edits
to derived counters are unsupported. Such maintenance requires verification
and rebuild before history service resumes. Arbitrary positive-value counter
tampering cannot be detected on every hot read without restoring an O(N)
aggregate; do not claim otherwise. Schema/version/missing-bucket failures are
detected promptly and never converted to empty history.

Tradeoffs: one-time O(N) cold backfill plus persistent small bucket storage and
two small count updates on inserts/deletes. SQLite already serializes writers;
the global bucket adds work within that boundary, not a new cross-product
authority. Warm exact totals become a bounded indexed lookup; deep OFFSET and
explicit complete-favorites scans retain their separately documented costs.

Required regressions: legacy pre-count database upgrade/reopen, empty/own/public
totals, update without owner change, owner move, stale upsert, delete/replacement,
strict-import rollback/retry, concurrent initialization/writes, missing
objects/version/buckets, explicit corruption verification/rebuild, count/page
snapshot, and 1k/10k/100k page-plus-total VM work without payload decoding beyond
the page. This supersedes earlier full-suite receipts for the changed V2 files.

### Count-bucket implementation receipt

The new regression first measured **533,980 VM instructions** for one own/public
100,000-row request (exact total plus 24-row page), failing its bounded-work
assertion before the bucket change. Final service-level probes attach SQLite's
progress handler immediately when each managed connection opens, count every
VM instruction, use the same synthetic fixture and fully migrated/warm schema,
and call the actual `list_image_history(limit=24)` implementation:

| Stored rows | Global total+page+metadata VM steps | Own/public total+page+metadata VM steps | Owner-only VM steps |
|---:|---:|---:|---:|
| 1,000 | 756 | 1,096 | 788 |
| 10,000 | 756 | 1,096 | 788 |
| 100,000 | 756 | 1,096 | 788 |

All cases return 24 items and exact totals for their owner scope. The fixed
metadata checks are included. These are work probes, not VPS latency/RSS
claims; cold index/bucket construction and writes are excluded deliberately.

Final focused command, V2 source root, shared V2 Python:
`python -m pytest -q tests/test_history_count_buckets.py
tests/test_history_count_error_api.py tests/test_history_read_scalability.py
tests/test_bootstrap_case_existence.py tests/test_history_retention.py
tests/test_history_migration_atomicity.py tests/test_favorites_retention.py
tests/test_persistent_retention.py tests/test_history_read_admission_routes.py
tests/test_import_error_api.py` → **228 passed, 1 existing Starlette warning,
4.49 seconds**. Modified backend files compile and whitespace checks pass.

The three final safety additions are a typed sanitized 503
`history_index_unavailable` response (never an empty success), a cheap page
length versus count/offset invariant, and a read snapshot owned by explicit
maintenance verification when its caller does not already own a transaction.
Zero owner/public buckets are removed by exact key on delete/owner change;
1,000 distinct owner transitions followed by deletion leave only `all=0`.
The strict-import test repairs and retries the same initially failed fixture,
proving both counter rollback and subsequent successful import.

Read-only maintenance uses `verify_history_counts(connection)` on a SQLite
URI opened with `mode=ro`; the test verifies BEGIN/ROLLBACK, zero total_changes,
no INSERT/UPDATE/DELETE/DDL, and consistency while a separate WAL writer commits.
Operator-authorized repair uses `rebuild_history_counts(connection)` on a
writable connection outside a transaction; it fences writers, replaces only
the derived objects, verifies, and commits atomically. A simulated interruption
rolls the whole replacement back, preserving history and import receipts.

These final count changes require a fresh full-V2/integration receipt; earlier
720-test results are historical, not coverage of the new counter implementation.

## Final frontend compatibility receipt

After the direct-Lab compatibility correction and final cancellation review,
the complete Node suite passes **139/139 tests**, including **120 focused
demand/dependency tests** and 19 existing V3 contracts. This count was rerun
independently by the owning audit/implementation agent with
`node --test tests/*.test.mjs`; all three JavaScript syntax checks and
`git diff --check` also pass. The three authorized Python smoke tests were
rerun by the frontend worker and again passed with 94 deselected and six
existing FastAPI lifecycle warnings. These replace the earlier frontend
117-test intermediate receipt; do not add the counts.

The executed dependency tests show direct Lab respects configured Doubao and
the existing disabled-Gemini/configured-provider fallback, immediate submit
waits for configuration, failures block submission, V1/Lab share one provider
load, and canceled/stale-owner work cannot restart shared reads after moving
to V2/V3. Lab's necessary two configuration reads do not create a V1 session or
request V1 history. Actual desktop V3 route/bootstrap and mobile V3 tab/bootstrap
succeed with throwing getters on V1 provider/settings/session fields and zero
V1 requests. Mobile's pre-existing URL route parser does not accept `v3`; no
new route behavior was invented for this task. The worker reconfirmed all 715
V3-named function bodies are unchanged from baseline.

All owned frontend/backend code is ready for the parent integration freeze,
final full-V2 run, scalable benchmark matrix, and separate browser acceptance.
No commit, push, deployment, production migration, or real Provider action is
included in this scoped completion.
