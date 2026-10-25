# RB23: V2 completed Bridge cache retirement

## Correction model

Published V2 originals and the native job/history remain authoritative. Frozen
reference bytes, per-unit result JSON, and the neutral transport image BLOB are
recovery copies, not a second permanent image library. Previously publication
and history deletion left all these copies indefinitely.

The minimal lifecycle repair is explicit retirement after durable native
completion **and** all units reach `acked` or `api_completed`. Unknown execution,
unACKed receipts, incomplete batches, missing native completion and unsettled
billing never qualify. No age alone authorizes deleting a recovery artifact.

## Implementation

- `PrimaryTransport.retire_units(requests)` validates every exact key/digest in
  one SQLite transaction. It clears duplicate image BLOBs and payloads, retaining
  semantic digests, execution/receipt identities, registration references and
  original image hashes. The terminal state remains unchanged.
- A `cache_retired` tombstone refuses stale writes that would restore a cleared
  BLOB. `cached_result` is read-only and cannot submit or poll remotely.
- V2 first saves a small durable cleanup intent, then performs normal ACK/API
  completion. Only a completed native job can compact frozen job/task records,
  remove embedded reference bytes, and unlink per-unit result cache files.
  The request (including authoritative owner), stable identifiers and retirement
  marker remain. The native output is not deleted or rewritten.
- All frozen copies are rewritten before deleting result caches. Retrying is
  safe after a crash between ledger retirement, either frozen rewrite, or unlink.
- Completed generation replay returns the existing native job. A retired record
  cannot enter image generation. Deleting published outputs does not let replay
  recreate them.
- Existing V2 QueueWorker runs a maintenance tick at most every 60 seconds with
  an overall 5-second async budget and at most 8 queued intents. This can retry
  ACK and cleanup only, never generation or billing. No additional daemon or V1
  import is introduced. A late ACK can therefore release protected duplicates.
- Existing history deletion requests cleanup too. If receipt ACK is unresolved,
  cleanup stays pending and does not weaken safety or fail over to an API.

The durable cleanup queue is `V2_DATA_DIR/render_bridge_primary/cleanup.sqlite3`;
back up the whole V2 Bridge directory with the neutral ledger. Existing completed
records are enrolled when replayed or deleted; this change deliberately does not
perform an unbounded startup scan or erase arbitrary historical directories.
API-only installations without a frozen Bridge record create no cleanup state.

## Capacity and recovery limits

Retirement removes JSON copies and makes neutral SQLite pages reusable. Setting
BLOBs to NULL does not guarantee immediate OS-level database shrink or forensic
secure erasure. No automatic VACUUM, ledger removal or reset is performed.
Native published originals follow their existing history deletion policy.

The generic retirement operation is opt-in: it does not automatically sweep
V1/Lab/V3 ACKed entries. Those products must independently prove durable native
publication and replay protection before invoking it. Unknown work remains
protected and can still consume storage; capacity monitoring remains necessary.

## Synthetic validation

The V2 dedicated tests cover exact digest/tombstone protection, native output
preservation, API completion, lost ACK and bounded later maintenance, unknown/
unACKed/unsettled protection, batch all-or-nothing, crash after ledger retirement,
crash between frozen-copy rewrites, and completed replay after deletion without
regeneration. No real provider, paid request or production data is used.

### Late ACK for other product owners

The neutral `request_retirement(requests)` hook can persist a product-verified
native completion intent while the transport is `artifacts_ready`. It does not
clear bytes or claim ACK success. The existing ACK reconciler clears bytes and
payload atomically only after the remote ACK succeeds; stale poll snapshots
cannot discard this intent or resurrect already-retired bytes. Batch validation
must succeed before any intent is written. Products may invoke this only after
verifying their durable native checkpoint and original hashes. V2 retains its
all-units-ACKed strategy plus its existing-worker cleanup-intent queue.
