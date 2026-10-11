# V2 paged favorites and explicit read readiness

## Correction model

The total objective is bounded browser retention plus bounded application payload
work for history and favorites. This V2 backend phase provides the server-side
filter and separates cold preparation from admitted browser reads. Browser
windowing and V1 changes are separate cooperating parts, not implied by this
backend result alone.

The prior browser favorites path needed to fetch all history to find starred
outputs. V2 already had a durable favorites authority and page-scoped badge
lookups, but no filtered history page. History listing also performed legacy
JSONL import, count backfill, and favorite JSON import during a request. The
minimal correction belongs to read projection and preparation; generation,
favorite writes, ownership semantics, and retention policy stay authoritative.

## Public contract and visibility

- Both `/api/v2/image/history` and `/api/v2/veyra/history` accept optional
  `favorite=true`. Omission or `false` keeps the existing all-history behavior.
- `items` and exact `total` retain the existing response shape. `limit` and
  `offset` apply after the favorite/history visibility intersection.
- History visibility and favorite visibility are separate predicates. A normal
  signed-in user sees their history plus legacy-public history, intersected with
  their favorites plus legacy-public favorites. The existing service option
  excluding public records applies to both authorities.
- Existing `include_all` / administrator behavior includes every owner's
  favorites, and auth-disabled unscoped behavior remains global. This change
  does not introduce a new global-owner identity or reinterpret favorite writes.
- Duplicate favorite records for one output, such as owner and public records,
  produce one output. Missing outputs and other users' inaccessible history do
  not inflate `total`.
- Creation epoch and job ordering are unchanged. Tied own/public records remain
  owner-first; within a tied stream the existing row insertion order is retained.
- Every filtered result has `favorite=true` from the captured query snapshot;
  a later separate favorite lookup cannot change those flags within the result.

## Read costs and concurrency

The existing V2 favorites database is attached at its configured filesystem path
using a bound read-only SQLite URI. There are no user-controlled paths or aliases.
The attachment is closed with the history connection. No write spans the attached
databases and no cross-database atomic-write guarantee is claimed.

A distinct, visibility-scoped favorite-ID query drives indexed history
`output_id` lookups. Explicit `CROSS JOIN` preserves that candidate-first loop
order instead of allowing the planner to scan all visible history. Exact count,
page IDs, and page payload retrieval run in one attached read transaction.
Independent WAL database snapshots are held for that read, then released before
payload decoding. The ordinary unfiltered badge lookup remains a separate,
page-scoped read as before.

Only page IDs and page payloads enter Python. The sort contains scalar identity
and ordering fields, not full history payloads. Temporary storage is configured
file-backed with a 2 MiB cache target; the attached favorites cache uses the same
target. SQLite scalar deduplication, sorting, and exact counting still grow with
the visible favorite candidate set F. Deep offsets have additional traversal
cost. This is a bounded payload/Python-memory contract, not page-constant CPU,
I/O, database size, or temporary disk use. Existing bounded read admission still
governs these requests.

## Explicit preparation

An ordinary V2 history list checks only bounded schema, count metadata, migration
markers, and source existence/size. It does not open legacy JSONL/JSON, add missing
indexes over populated authorities, or backfill history count buckets. A genuinely
empty new store may bootstrap its empty schema. A subsequently restored legacy
source still requires preparation.

Unavailable history/count state returns sanitized HTTP 503
`history_index_unavailable`. Pending favorites return
`favorites_index_unavailable`. Both use `retryable=false` and do not return an
invented empty page. Existing strict-import failure handling is retained for
operator preparation and managed mutation paths.

Run only against explicitly authorized V2 paths:

```sh
python scripts/prepare_v2_history_reads.py \
  --data-root /absolute/v2/data \
  --history-path /absolute/v2/data/image_history.jsonl \
  --minimum-free-bytes "$OPERATOR_CAPACITY_REQUIREMENT_BYTES"
```

The CLI invokes `app.services.image_history.prepare_history_reads()`, which
reuses the unchanged strict atomic legacy importers and count initialization.
It starts no application lifespan, queue, provider, or V1 subsystem. Cold work
is operator-controlled and may scale with all legacy records. Success reports
`ready`; sanitized failure reports `blocked` with an exception type and exit 2.
This is preparation, not an automatic repair/rebuild for corrupt existing count
objects. Such objects still require the established verify/rebuild procedure.

Quiesce competing application writes and run the capacity preflight before
maintenance. Mutating preparation requires a positive operator-supplied
`--minimum-free-bytes`. The CLI reports free capacity and existing database,
WAL, and SHM footprints for both explicit locations, and stops before importing
application code or writing databases if either location is below that budget.
`--preflight` reports those values read-only and does not require a budget.
The budget is the operator's capacity requirement, not an exact forecast of
index/import growth or a guarantee against concurrent disk consumption. No
automatic cleanup, source truncation, checkpoint cleanup, or VACUUM is added.

Native history persistence continues to check the strict legacy boundary before
upserting. For a pristine native store it establishes the existing-style `jsonl`
completion marker in the SQLite write transaction before appending its JSONL
mirror. This is native authoritative-mirror initialization, not a fabricated
legacy import receipt. Corrupt legacy data or an orphan import receipt blocks
the native write before upsert or marker insertion.

## Verification scope

Synthetic offline tests cover:

- All/user/public/admin/auth-disabled visibility, ownership badges and access,
  duplicate favorite records, missing outputs, tied jobs/epochs, and offsets.
- 1k/10k favorite populations with exactly 24 payload decodes for a 24-row page,
  including deep offsets, and no Python all-favorite enumeration.
- Sparse favorites over 1k/10k histories with fewer than 1,200 SQLite VM steps,
  indexed owner-favorite selection and history primary-key lookup, scalar sort,
  and attempted writes rejected by the read-only attachment.
- Concurrent deletion from both authorities between count and page, preserving
  the captured total/items/true flags.
- Cold requests blocked without reading source contents; explicit preparation
  followed by ready reads; pending favorites and pre-count databases.
- First native write readability, corrupt legacy/orphan-receipt write blocking,
  and preservation of the existing strict migration/retention regressions.

These tests use temporary synthetic stores and a socket-denying runner. No
production database, Provider action, deployment, or merge is part of this phase.

Final focused validation: **338 passed** (one existing dependency deprecation
warning). The command was the isolated `/tmp/media_history_pytest.py v2` runner
over `test_history_favorite_paging.py`, `test_prepare_history_reads_cli.py`,
`test_history_read_scalability.py`, `test_history_read_admission_routes.py`,
`test_history_retention.py`, `test_history_migration_atomicity.py`,
`test_history_count_buckets.py`, `test_history_count_error_api.py`,
`test_favorites_retention.py`, `test_favorites_migration_atomicity.py`,
`test_prompt_transform.py`, and `test_persistent_retention.py` from the V2 test
directory. This is the named focused group, not the entire product test suite.

A subsequent whole-suite audit found seven older API/auth fixtures that wrote
legacy JSONL and relied on request-time import. Those fixtures now explicitly
call `prepare_history_reads()` after writing the source; pagination, thumbnail,
auth, legacy-public, and administrator assertions are unchanged. The affected
`test_v2_api.py` and `test_veyra_auth.py` files plus the new favorite/readiness and
preparation-CLI files passed together: **237 passed**. Production readiness was
not relaxed to satisfy those fixtures.
