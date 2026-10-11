# Follow-up independent design and code review

## Scope and status

Final independent security review is **incomplete**. The reviewer turn was
interrupted by a service-side cybersecurity risk flag after reporting the
known findings. No blocked probing was retried or routed elsewhere. The
implementation owners continued the already-authorized defensive corrections
and ordinary offline regressions; those results are not an independent final
security approval. Frozen changes require a separate local review before any
deployment decision. This integrator note preserves the partial review below.

Review baseline: `fd259486bebdda58eab506638991cdb04f9f1047`.
Date: 2026-10-11. This review covers the follow-up corrections to PR #29.

The reviewer independently inspected the original implementation and the
proposed corrections. Implementation and final integrated validation are still
in progress. A design endorsement is not a frozen-code test pass, browser
acceptance, production deployment approval, or a claim that all security and
resource risks are closed.

The scope is historical reads, their derived data, bounded browser retention,
and the publication/access boundary of the generated images used by those
reads. Business history, files, Job/Output authority, ownership evidence,
favorites, deletion claims, and import receipts must be preserved. No retention
policy, Provider call, production mutation, or merge is part of this review.

## Findings and correction contracts

### 1. File publication must precede discoverability

The baseline writes managed image bytes, thumbnail and preview files before
persisting the canonical output's explicit owner. Billing can add an awaited
interval before the authoritative Job/Output save. Filesystem recovery and
direct-media routes must not treat this interval as legacy-public content.

The proposed correction reserves each managed output ID durably before writing
bytes. The reservation binds the ID to its Job and request-supplied owner. The
canonical publication must match that binding. An interrupted reservation
remains non-public; it is not deleted merely to restore discovery. A published
identity cannot be reused to overwrite content under a previously authorized
ID. Review found that checking only current canonical existence would allow
reuse after deletion; the implementation owner accepted the minimal correction
of rejecting every repeated reservation. Existing generation retries already
mint fresh output IDs. The reservation is publication evidence, not
Session-derived ownership.

Listing, counts, owner lookup, file lookup, download, thumbnail and preview
access need the same publication predicate. Direct canonical-media reads should
not need a full history build merely to apply a keyed reservation check.
Unmarked legitimate canonical, manifest and nested-Job legacy outputs retain
their authority semantics. A bare file associated with a known Job but absent
from published output evidence is not automatically public. Genuine orphaned
legacy filesystem recovery remains supported.

Required edge case: a partial deletion can remove the canonical output while
leaving the durable deletion claim. A retained publication reservation must not
prevent the authorized owner from retrying that deletion. Deletion retry
authorization and read publication are distinct: admitting the owner to finish
cleanup must not make pending/deleting bytes visible again.

### 2. Anonymous local share readers must enforce visibility too

The original `/share/poster` and `/share/save-image` paths can open local V1
output bytes through `_load_share_preview_image()` without the ordinary output
authorization check. The save-image route can also return an existing cache
before reaching file resolution. Guarding only `_resolve_output_file()` is
therefore insufficient for existing cached content.

The parent explicitly included this boundary in the follow-up. In the absence
of a persisted share grant, a public share surface must not open or serve cached
private or conflicting local V1 output bytes. Safe public/legacy previews and
the existing static-placeholder fallback are compatible with the inspected
tests. There is no verified existing V1 private-share grant contract to preserve.
Absolute and relative URLs must be classified consistently before both cache
hits and uncached reads. No new share-token subsystem is required.

The existing share smoke coverage exercises escaped landing metadata, static
JPEG generation, missing-V1 placeholder behavior, and ownerless local V2
previews. It does not establish that anonymous access to private output bytes
is intentional. V2 local share ownership requires an explicit scope decision
and separate evidence; a V1 correction must not be reported as a verified V2
authorization correction.

### 3. User reads must not become full cold-build maintenance

The baseline read readiness path calls the same full builder used by explicit
maintenance. That builder holds a SQLite writer transaction while decoding
authority, inventorying files, resolving winners, and publishing counts.
Moving the work to a bounded worker does not bound its writer-lock duration.

The follow-up contract is explicit preparation/rebuild for missing or obsolete
derived state, with a typed maintenance-required 503 for ordinary reads rather
than a hidden full build or empty-success fallback. Ready-state incremental
catch-up remains separate. Version, storage-root, schema, import and count
failures must not weaken ownership checks or replay already-imported JSONL.

One large authoritative Job and one output with very many source/session copies
can still require substantial incremental work. A deadline checked only after
a dirty-key batch does not impose a hard time bound inside an individual key.
Any stronger bound must be demonstrated in code and tests rather than inferred
from the existing two-second outer budget.

The reviewed implementation now adds cooperative checks within source/winner
and Job-output loops, with a savepoint for each dirty key. Budget interruption
rolls that key back and retains its dirty work while previously completed keys
may commit. This avoids publishing partial winner/count updates. Individual
JSON parsing and SQL statements are still indivisible; this is not a hard
wall-clock timeout for arbitrary-size authoritative records.

### 4. Duplicate-source fanout must not retain all payloads

The baseline `_resolve()` fetches every complete source row, constructs several
lists, sorts them, and filters the whole set once per scope. Besides memory
proportional to duplicated payload bytes, this creates source-times-scope work.
The owner lookup has a separate all-source materialization.

The proposed scalar streaming correction retains only a global winner and the
current session's winner. Its indexed stream is ordered by output and session.
Canonical ownership remains first, then manifest/evidence authority, then the
complete nested-Job owner set, then deletion-claim fallback. SQL MIN/MAX over
the complete Job owner set can detect equal-tier disagreement without retaining
every row. Limiting the evidence to a display page would be unsafe.

Winner precedence is source tier first, matching owner within that tier second,
and the existing traversal order last. Job traversal is job-sort descending,
insertion sequence ascending, nested position ascending. File traversal is
mtime descending and sequence ascending. Any non-V1 source excludes V1 even
when it is not itself display-eligible. Lab's separate winner remains before
that V1 exclusion, with its existing file-existence contract.

Streaming makes retained candidates bounded, not total work constant. Resolving
an affected output still visits its source/session fanout and maintains each
affected winner/count bucket. A single authoritative Job is still validated as
one complete business record.

### 5. Browser history and favorites need bounded navigable windows

The baseline keeps appending ordinary pages, and explicit favorites can read
and retain all historical responses. Limiting an individual response to 24
rows does not bound the browser's arrays, cards or retained media.

The proposed browser contract uses fixed 72-raw-row windows, bounded rendering,
and previous/next refetch rather than an accumulating page cache. Raw offsets
must remain independent of deduplicated or renderable item counts. Empty or
sparse windows must still expose a route to earlier/later results. The Hero
may keep a separate first-page snapshot capped at 24 rows. Account sampling
windows and V3 behavior stay under their existing contracts.

The additive `favorite=true` backend option provides a filtered page and exact
filtered total without transferring every non-favorite output to the browser.
Own/public favorite rows can refer to the same output: the result must dedupe
IDs and independently enforce the history row's visibility. V2 favorites live
in another SQLite database, so initialization/import precedes the attached
read transaction, and the filtered count and page share that snapshot. Only
the selected page's payloads should be decoded. Existing own-before-public
tied ordering must remain stable.

This optional filtered query may still perform scalar work proportional to the
favorite/history intersection and may sort IDs. It must be measured and
disclosed separately from the page-dominated ordinary-history hot path. No
claim of constant-time exact favorites totals follows from bounded browser
retention. Authentication change, favorite toggle and deletion must invalidate
the affected windows and stop stale responses from repopulating them.

Review identified two integration details for correction: V1's filtered page
must retain `favorite=true` from the captured count/page snapshot instead of
overwriting it with a later badge query; and its join must be candidate-driven.
An independent query-plan probe showed that an ordinary JOIN can scan the
whole visible history before checking favorites, whereas the candidate-first
CROSS JOIN uses the winner primary key per favorite. A leftover favorites
import receipt also prevents a missing favorites table from being classified
as a pristine empty store.

The browser review additionally found that directly removing a V1 history
card before renderer cleanup leaves its authenticated Blob URL unreleased.
The implementation owner was asked to clean that card's media before removal.

### 6. Derived payload compaction is a storage tradeoff

The baseline stores a complete display projection for every Job output,
including repeated Job-wide plans and prompts. The proposed versioned
`v1_read_jobs` table stores common display fields once per Job; source rows keep
output-specific display fields. Page hydration combines the two. Manifest
payloads continue to come from their existing authoritative keyed records.

The new table belongs in schema completeness, rebuild and missing-source
checks. Job replacement/deletion must refresh both common and output-specific
derived records atomically. Missing common data is a typed failure, never a
silently incomplete response. The change reduces repeated payload bytes but
does not remove the necessary scalar source/winner indexes or authoritative
history. Database/WAL and cold-build costs still need separate measurements.

## Independent evidence collected so far

- Read-only review of `history_index.py`, `history_projection.py`,
  `image_service.py`, `local.py`, `memory.py`, V1 media/share handlers, V2
  history/favorites storage and both proposed browser/backend contracts.
- Inspected existing share smoke tests in `tests/test_api_smoke.py`; these do
  not test or authorize anonymous private-output access.
- Ran 8,000 deterministic synthetic comparisons of the new streaming winner
  comparator against the baseline ordering algorithm: 2,000 generated source
  populations times global and three session scopes, seed 1729. All passed.
  The probe used only scalar in-memory data and imported the repository helper;
  it did not open application storage or invoke a Provider. This is comparator
  evidence only, not a database or final integrated test pass.
- Independently reran `tests/test_v1_lab_history_index.py` using the existing
  file-backed offline harness with socket connects blocked and isolated
  temporary runtime storage: **33 passed**, six existing FastAPI lifecycle
  warnings, **26.23 seconds**. Command:
  `/workspace/shared/media-history-v1-venv/bin/python /tmp/media_history_pytest.py v1 tests/test_v1_lab_history_index.py`.
  The process imported the code at approximately 06:50 UTC, before the final
  integration freeze. `git diff --check` also passed when that run finished.
  These results are not coverage of subsequent edits or full-suite acceptance.

## Final verification still required

The implementation owners and integrator must freeze the changed code, rerun
the relevant complete regression groups, and bind the receipt to the actual
commit/file fingerprint. This document will record the reviewer-observed final
results and unresolved findings when those results exist. Pending checks must
not be inferred from an implementer's design statement or an older PR receipt.

Required coverage includes reservation interruptions and mismatches; ordinary
and share cache-hit publication denial; owner-conflict and legitimate legacy
compatibility; deletion retry after canonical removal; cold-read refusal versus
explicit preparation; large duplicate/session fanout; common-payload parity and
disk cost; bounded ordinary/favorite browser windows and backward access;
filtered-count/page consistency; stale account responses; and old history tails.

Real Provider generation, real-browser visual/focus acceptance, production
storage, VPS capacity, deployment and merge remain unperformed in this review.
