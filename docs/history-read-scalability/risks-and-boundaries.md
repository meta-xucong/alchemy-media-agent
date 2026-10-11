# Remaining risks and compatibility boundaries

## Existing managed-file ownership publication window

This read-scalability change does **not** close every pre-existing privacy gap.
Source inspection at baseline `5a33c05e3f54dbef786eb179973ec1407511b4e4`
establishes this publication ordering in
`src_skeleton/app/services/image_service.py`:

1. `_try_image_provider()` calls `_store_outputs()` after receiving provider
   results.
2. `_store_outputs()` calls `LocalMediaStore.save_base64_output()` before it
   constructs the `GenerationOutput` carrying
   `metadata["veyra_user_id"]`. The media file is already on disk at this point;
   that per-output ownership evidence has not yet been persisted.
3. `_run_image_request()` can then await `debit_balance()` before
   `repository.save_job(job)` persists the canonical Output and nested Job
   output records. `_persist_history_records(saved)` follows that save.
4. During this interval, the baseline global history filesystem-recovery path
   can discover the file. With no per-output canonical, manifest, or nested Job
   ownership evidence yet present, the legacy-public rule applies. The existing
   output-visibility path similarly allows ownerless legacy content.

This is an existing generation-publication boundary, not a new ownership
inference introduced by the derived index. The new managed-file dirty marker
can make the same file eligible for recovery before its ownership is published.
A first inventory build can also observe it. The SQLite build fence does not
make filesystem creation and subsequent ownership publication one transaction.
This finding is based on the code path; no real Provider or billing call was
made to demonstrate it.

Once the canonical Output/Job ownership transaction commits, its tracking
triggers must dirty the affected output in that same transaction. A subsequent
history read must refresh all affected global/session winners and their count
buckets before returning a clean snapshot. It must never continue returning the
cached public winner after that authority commit. Regression coverage must
exercise public filesystem-only recovery transitioning to a canonical private
output and check both other-account visibility and public/owner/global/session
counts.

A separate, narrowly scoped security correction should define when a file
associated with a known Job but absent from that Job's published outputs is
pending or unknown rather than legacy-public. Listing and download visibility
must share that rule, with explicit treatment of interrupted generations and
genuine legacy filesystem-only recovery. Do not infer output ownership from
the Session owner. Such a change needs generation/publication contract review;
it is not silently bundled into this read-only scalability work.

## Inventory freshness and derived-state verification

Totals describe the committed inventory snapshot. Managed changes are tracked;
unmanaged file edits and a crash between a file operation and its dirty marker
require explicit reconciliation. Bounded page checks can repair discovered
missing files, but cannot discover unknown new files or prove that every
unreturned file still exists. Reconciliation limits must be reported rather
than replaced by a hidden whole-history request scan.

Derived schema/version checks and inexpensive page/count consistency checks
detect specific failures. They do not prove the absence of arbitrary manual
corruption. Full verification and rebuild belong in explicit maintenance, not
every hot request. Neither synthetic tests nor this design establishes VPS,
production, or complete security acceptance.

## Media lookup and measurement scope

Known indexed image lookups use per-output ownership evidence and bounded path
candidates. Unknown direct-ID and legacy-video compatibility can still invoke
the existing filesystem fallback. List-handler benchmarks do not include HTTP
transport, browser rendering, all image transfers, or real account lookup, and
must not be presented as end-to-end browser-page latency measurements.
