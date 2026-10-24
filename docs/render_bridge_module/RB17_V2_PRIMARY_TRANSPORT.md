# V2 Render Bridge-primary correction model

RB13 owns routing; V2 owns claims, templates, assets, review, history and billing.
The old transport preselected API credentials, regenerated creative plans and job IDs
on queue retry, and applied overlays to every provider output. Those behaviors cannot
be reused for an accepted or uncertain Bridge request.

The minimal correction freezes the V2 request and ordered reference bytes under the
existing task claim before dispatch. Queue recovery resumes that same frozen job
before planning. Neutral transport owns route/admission evidence. V2 queue waits do
not consume the ordinary retry budget. API selection follows proven nonadmission.
Accepted/unknown Bridge results never enter the provider/mock exception fallback.
Required deterministic overlays and QR preservation are unsupported Bridge hard
capabilities, not permission to mutate returned Bridge pixels. Original bytes are
stored unchanged; thumbnails/previews remain separate derivatives. Debit and output
commit retain V2 claim fences and existing idempotency keys. Receipt ACK follows
committed output/debit/checkpoint, not receipt download.

Validation uses offline fake transport and isolated V2 storage only. No live account,
provider, deployment or production acceptance is implied by passing these tests.

## Deployment and limits

The neutral transport is a separately installed package. From repository root,
install it into the same V2 interpreter with:

    custom_media_agent_2_0/.venv/bin/python -m pip install -e ./render_bridge_primary

Windows setup_venv.ps1 performs the corresponding install. V2 API and worker
processes must use the same absolute ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG path.
V2 request snapshots, reference bytes and unit caches live under
V2_DATA_DIR/render_bridge_primary. The neutral transport ledger uses the shared
ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT/v2, so admin pending-task guards see V2
ownership. Neither location is V1 storage. Treat those directories
as durable application data and include them in normal V2 backup/recovery.

V2 currently synthesizes quality=high by default. Bridge fff5244 advertises only
auto quality. High is retained as a hard requirement, so such requests explicitly
fall back with bridge_capability_unsupported. This integration does not weaken
quality defaults. Compatible quality=auto requests exercise Bridge-primary.
Strong reference fusion/high fidelity, unrepresentable options, QR and deterministic
text composition likewise fall back rather than lose user intent. Batches route
per stable job:index and aggregate once for the existing V2 debit and review.

Queued creative runs recover automatically without replanning. Direct image jobs
use POST /api/v2/image/jobs/{job_id}/resume; cancellation uses the matching /cancel.
Both enforce ownership when authentication is enabled. Queue-owned pending jobs
reject direct resume so they cannot escape queue claim fencing; cancellation
atomically terminalizes the matching queue task and revokes its claim before
canceling existing Bridge units. Completed job resume only retries receipt ACK. Existing read-only
GET status routes remain read-only. A canceled/failed/unknown Bridge task never
becomes permission for another image generation.

## Offline verification (2026-10-24)

- Standalone V2 working directory, PYTHONPATH unset, neutral package installed:
  import of neutral package and V2 generation passed.
- Complete V2 test suite: 822 passed (47.19 seconds).
- Final focused Bridge adapter tests: 23 passed, including actual queue-worker
  recovery, claim revocation cancellation, no post-cancel next-unit dispatch,
  billing crash/replay, native original bytes, actual neutral capability negotiation,
  direct owner checks, API response-loss quarantine, ACK outage replay and
  consistent resume capacity/storage-busy HTTP responses.
- Existing durable queue regression plus initial adapter tests: 44 passed.
- No real provider/account/local-machine or deployment tests were run.

Audit corrections: outer worker balance preflight now skips already-frozen admitted
requests; canceled native jobs are monotonic across late pending/error responses;
queue cancellation revokes claims before remote RPC; the neutral V2 ledger remains
visible to shared admin pending-work guards. These checks establish the V2 adapter
phase only, not complete multi-product or real-machine acceptance.

## Debit/cancellation finalization correction

Audit reproduced a debit that was accepted upstream while cancellation revoked the
local job before the debit response returned, leaving a charged user without an
output. The owning authority is V2 durable finalization, not Bridge admission.

Before any debit await, the existing V2 queue SQLite authority now records a
finalization boundary and the exact debit parameters/key under BEGIN IMMEDIATE.
Both direct and queued cancellation arbitrate against that same record: before the
boundary cancellation wins normally; after it cancellation returns 409 without
revoking the claim, cancelling the renderer or hiding cached pixels. A crash or
uncertain debit response retains finalization and retries the same debit key and
same cached output. This adds no refund, price or retry-generation policy.

Finalization verification: final standalone V2 suite 828 passed (45.15 seconds);
focused Bridge and existing durable queue tests 50 passed. Added direct and queued
applied-debit barriers proving cancel returns 409 without claim revocation and the
original pixels are published; restart tests prove exact debit arguments survive
runtime policy changes. Bridge-owned billing errors retain a non-consuming 120-second
finalization wait instead of exhausting the ordinary provider retry budget.
