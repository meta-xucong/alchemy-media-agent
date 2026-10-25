# RB25 Completed product duplicate-cache retirement

## Correction model

A transport ACK proves receipt acknowledgement, not the existence of a durable
native output. Never age-delete all ACKed ledger bytes or treat missing bytes as
permission to render again. Each owning product explicitly proves its native
checkpoint before calling the neutral exact-key/digest retirement operation.
The ledger retains identity, original hash, state, receipt and registration
metadata; only duplicate image bytes and the now-unneeded remote payload retire.

## V1 and Lab

After the persisted job is ready (following existing billing/publication),
`finish_primary` completes each exact unit's ACK/API transaction. Retirement
requires every stable native output to exist under that job, and Bridge originals
to match the ledger hash. Native outputs and private product recovery metadata
are not removed. Ready-job resume already returns the original native job rather
than generating again. Missing native media never causes another provider call.

## V3

Retirement happens only after the native output metadata records a completed
checkpoint. It verifies exact execution identity, native content hash and Bridge
original hash; incomplete, corrupt and missing checkpoints are ineligible.
Recovery checks the existing native checkpoint before rejecting an empty transport
cache. The cancellation gate still runs, and a retired cache requires the same
completed native original at each checkpoint-current check. Missing/deleted or
corrupt originals fail closed, never restart execution or switch providers.

## Delayed ACK recovery

After all native completion/hash proofs, the product records an explicit durable
retirement intent in the existing exact-key/digest ledger. An ACK that has not
succeeded retains every byte. The existing ACK maintenance atomically releases
duplicate bytes when that exact intent reaches ACKed; no product resume, extra
scanner, daemon or cross-product import is required. An ordinary ACK without
that owning-product intent never authorizes retirement.

V1/Lab records the intent only after checking every native batch output. One
network ACK failure does not prevent saving the other units' ACK intents; the
first typed network error is re-raised after the bounded batch, leaving the ready
native job intact. Identity/claim errors and cancellation are not suppressed.
V3 records the intent only after checkpoint_complete=True and original hash proof,
even when its ACK response was lost. Pending/unknown/canceled executions and
incomplete checkpoints cannot acquire the intent. Stale poll writes preserve it
and cannot resurrect bytes after retirement. V2 uses its owning-product lifecycle
as described in RB23.

## Verification

Synthetic real-entry regressions cover V1/Lab/V3 completed retirement and same
checkpoint replay, ACK-response loss and background recovery without product resume, incomplete checkpoints,
missing/corrupt native originals, cancellation, pending/unknown execution and
API fallback uniqueness. No live generation, billing, production-data cleanup,
network configuration or deployment is performed by these tests.
