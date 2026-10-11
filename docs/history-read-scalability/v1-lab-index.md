# V1 and Lab incremental historical reads

Baseline: `5a33c05e3f54dbef786eb179973ec1407511b4e4`.

## Correction model and authority

V1 currently decodes every image Job, gathers global ownership evidence,
rebuilds a temporary SQLite projection, and scans generated files on every
history request. Lab reads up to 10,000 manifests before filtering,
transforming and sorting them. Existing session-leading indexes also leave
global queries with a temporary sort. This is a read-projection problem, not
a Provider, generation or retention-policy problem.

The existing V1 `repository.sqlite3`, its complete `v1_records` payloads,
manifest payloads, owner-evidence table and deletion claims remain authoritative.
Media files remain byte authority. New tables are rebuildable derived state in
that same database. V2 storage and all existing public request/response schemas
remain unchanged. No business records or files are removed by index upkeep.

## Selected minimal design

Use materialized per-scope winners rather than a request-time UNION/window
ranking of all candidates: SQL-only ranking would still repeat total-history
work. Store scalar source references, not another full copy of every Job.

1. A derived source-reference table flattens image Job outputs, references each
   durable manifest, and inventories generated files. Its source identity,
   output ID, session, explicit owner, classification, eligibility, timestamps,
   insertion/nested ordinal and file-presence evidence are indexed. Reverse
   indexes by output, Job and session locate only affected records.
2. A derived winner table is keyed by surface, scope and output ID. V1 has a
   global scope plus each source session; Lab has its existing global scope.
   The row holds the winning source reference, resolved owner, sort fields and
   mock flag. Job source refs additionally store the existing per-output display
   projection, built once when that Job changes. This avoids decoding a whole
   large Job for a one-item page. Winners do not duplicate that payload per scope.
   Manifest payloads and Lab transformations are decoded only for the page.
3. Fixed count buckets are updated with changed winners in the same transaction:
   all owners, each explicit owner/public bucket, and Lab all/non-mock variants.
   V1 account totals combine that owner's and public buckets; Lab account totals
   use only that owner. SQL COUNT over every matching row is not claimed O(1).
4. A small dirty-key table and a version/ready marker make incremental refresh
   and rebuild state explicit. SQLite triggers record changed authority keys in
   the source write transaction, including direct mapping writes and deletes.
   No write invalidates the complete index.

## Ownership, projection and ordering

Resolve output ownership globally, independently of display scope:
explicit canonical Output owner, then durable manifest owner/conflict evidence,
then all legacy nested Job-copy owners. A canonical owner outranks lower-tier
disagreement; equal-authority conflicts fail closed. Missing media cannot erase
owner evidence. Do not infer output ownership from Session owner. Session
project ID still controls V1/Lab/V2 classification; deletion-event Session
ownership remains governed by existing checks.

Select display projections separately: Job before manifest before file, with
matching-owner preference within a tier. Preserve Job traversal precedence
(`sort_at DESC`, insertion rowid ASC, nested position), manifest duplicate
precedence and the existing conflict evidence even when an incoming payload
does not replace the manifest winner.

V1 display order remains parsed created-at-or-updated-at DESC, Job ID DESC,
output ID DESC. Lab retains lexical created-at-or-updated-at DESC and stable
manifest created-epoch/sequence ties. V1 Job candidates do not require a file;
manifest/file candidates and Lab do. Favorites stay current-page overlays;
Lab variant favorites remain owned by Lab session storage.

Removing the 10,000 recovery/manifest cutoff is an intentional completeness
correction requested by the user. Tests require parity below that boundary and
correct complete totals/tail pages above it. Lab's raw manifest list currently
does not consult conflict evidence; making it obey authoritative fail-closed
ownership is an explicit security correction, not preservation of that defect.
No new cursor or offset contract is introduced. Deep offsets still require
O(offset + page) index traversal.

## Transactional invalidation and refresh

Triggers on Job, Output and Session records and manifest/owner-evidence changes
insert namespace/key dirty entries in the same transaction as authority changes.
Refresh uses old source references plus current records to find the affected
output IDs; Session changes affect only its indexed Job references. Recompute
those IDs and their scopes, updating winner rows and count buckets atomically.
All map-level put/delete/clear, recovery and migration writes are covered by
the triggers. Filesystem writes/deletes explicitly enqueue the affected path.
Existing output-delete claims continue to fence stale writes and preserve retry
authorization through partial cleanup; the read model cannot invent new owner
anchors or clear those claims.

Each reader first catches up committed dirty keys, then obtains total and page
from one SQLite snapshot that contains no unprocessed dirty keys. Recheck this
condition inside the read transaction to close a concurrent-write gap. An
unchanged request performs no projection writes or global scan. Refresh work is
O(changed records plus their duplicate/session fanout), not O(total history).
Catch-up uses coalesced database keys, 128-key batches and a two-second work
budget per transaction. A request has at most three catch-up/read-repair rounds;
sustained writes or extensive missing media produce a sanitized 503, never an
unbounded retry loop. Full cold build is deliberately outside the warm catch-up
budget and can take substantially longer; operators should prepare large stores
before admitting reads. SQLite's writer fence does not freeze filesystem writes.

## First build, versioning and recovery

Fresh empty installations build immediately. An existing store's first build is
one explicit cold operation in the already bounded worker, never on the event
loop: hold a SQLite writer fence, stream current SQLite authorities and file
inventory into derived tables, reconcile owners/winners/counts, and commit the
ready version only after completion. Until commit, other readers cannot observe
partial state. SQLite busy/admission limits remain explicit errors. This cold
cost can be prepared before serving via the same explicit rebuild operation;
it is not repeated on ordinary reads or after each write.

Crashes roll back incomplete builds/refreshes; authoritative records are intact.
Version mismatch or corrupt/incomplete derived state requires controlled
rebuild, never a public/empty-history fallback. Rebuild streams SQLite's current
state. It never clears legacy import markers, synthesizes import receipts, or
replays completed JSONL sources. Existing strict import-state checks run before
the new projection, including half-marker failures and unverified legacy-marker
rules. Schema version is independent of first-import receipt version.
The committed build also binds the resolved storage root. A copied or moved
database is rejected before any indexed file access until explicit rebuild in
the new root. Page/locator paths must stay inside that root's generated-media
directory, including after symlink resolution; foreign/corrupt paths fail closed.

## File freshness boundary

Managed file writes/deletes enqueue inventory changes. A crash between a file
operation and its SQLite enqueue, or an unmanaged file change, needs explicit
reconciliation. A controlled reconciliation scans file/manifest presence and
refreshes changed IDs without changing business payloads or file bytes.

Normal reads do not enumerate directories. They may repair missing returned
manifest/file candidates with a capped number of page checks/refills; exhausting
that bound reports reconciliation-required rather than silently returning a
false complete page. Unknown new files cannot be discovered by page repair.
Counts are exact for the committed inventory snapshot, not a claim of live
filesystem-wide stat consistency. Exact instantaneous counts for arbitrary
external file mutations cannot coexist with no full filesystem observation.
No background daemon, automatic retention or Provider work is added.

The explicit operator entry point is `scripts/prepare_v1_history_index.py` with
required `--storage-root` (an existing directory) and exactly one of `--prepare`,
`--rebuild`, `--reconcile` or `--verify`. It pins the application storage root before imports,
prints aggregate status/counts only, and refuses pending legacy-file imports.
Legacy authority import/backfill needs its separately authorized existing flow;
the operator command never quietly turns projection maintenance into that import.
Normal application reads retain the existing strict lazy-import behavior.
`--verify` instead opens SQLite with `mode=ro`, without application imports or
legacy import: it checks ready/dirty state, tracking triggers, dangling winner
references and every count bucket against grouped winner rows. It detects both
under-counts and over-counts. This is derived internal-coherence verification,
not proof of complete authority/payload parity or resistance to arbitrary
database tampering; use a consistent offline backup for operator verification.

Repository-sourced entries can remain visible while their file is missing.
Filesystem-only recovery is withheld while an output deletion claim exists;
the existing claim remains the authorization anchor. Indexed direct lookups also
replace the old 10,000-entry favorites/classification/revision lookup windows.
Legacy thumbnail owner lookup now uses indexed global scalar owner evidence;
known image file lookup uses inventory paths and bounded recognized-extension
probes. Locator inventory also records irregular legacy names and video files,
but only the original strict generated-ID/image-format rules permit file-only
history recovery. Global Provider file discovery is unchanged. Unindexed direct
ID/video compatibility requests retain the legacy discovery fallback; they are
not a claim of bounded lookup for every arbitrary URL.

## Verification

### Cold inventory lookup correction

The first scale run found quadratic cold SQL work despite linear JSON/file
counts: each file checked for matching manifest refs with `kind='history' AND
file_path=?`, but SQLite chose the `(kind,sequence)` index and scanned all
manifest refs. A synthetic no-ANALYZE query executed about 5,010 VM steps for
1,000 refs and 50,016 for 10,000 refs. This is a derived-query access-path defect;
authority, visibility, filesystem freshness and winner rules remain unchanged.
The minimal correction is a `(kind,file_path)` composite index, so both equality
predicates bound every inventory lookup. A regression checks the selected plan
and VM work across increasing synthetic source populations without `ANALYZE`.

Synthetic isolated stores at 100, 1,000, 10,000 and 50,000 records measure build
separately from warm/reopened reads. Count actual JSON decodes, candidate
transforms, SQLite rows/index steps, directory/stat operations, temporary bytes,
RSS, wall P50/P95 and DB/WAL growth; inspect query plans. Cover global/session,
limit 1/50/200, deep offsets, own/public/admin, sparse Lab/owner populations,
mock filtering, missing files and duplicate-heavy sources. A single source
update must refresh only its affected outputs. Warm reads must not scan Jobs,
rebuild request SQLite, enumerate files or transform all matching records.

Negative cases include cross-session owner evidence, canonical precedence,
manifest/Job-only same-tier conflicts, missing private media with ownerless
recovery, stale ownerless saves, Lab/V2 exclusion, timestamp ties, delete failure
at each stage, concurrent favorites, interrupted build/refresh, reopen and strict
import/receipt failures. No Provider, production data, deployment or user-data
mutation participates in these tests.
