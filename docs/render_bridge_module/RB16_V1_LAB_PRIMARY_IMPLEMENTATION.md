# RB16: V1 and Lab primary transport

The total goal is RB13 four-product routing; this phase owns V1 and Lab only.
The observed mismatch is that V1 calls its API registry directly, Lab retries
with a new attempt identity, and startup closes all unfinished jobs. Transport
ownership must instead remain with the neutral durable primary ledger. Product
planning, asset intent, billing, history, and review remain V1/Lab authorities.

The minimal fix freezes the existing request before transport, resolves each
output ordinal through the neutral ledger, checkpoints each original output
under a deterministic ID, and resumes the same job from authenticated polling.
Existing mock and disabled unowned jobs retain their legacy path. A primary
request never enters the old provider fallback loop. API invocation requires a
durable claim; an interrupted claim is not permission to invoke again. Billing
retains the existing job idempotency key, and Bridge ACK follows saved outputs,
billing, and history. Recovery excludes these jobs from old interrupted-job
failure. Lab retains pending variants and resumes their existing job identity.

Hard controls are explicit capability requirements, including high quality,
format, alpha, compression, masks, high fidelity, edit source, and structured
asset fusion/postprocessing. Unsupported controls choose the traditional route
without weakening the frozen request. Bridge bytes bypass mutating postprocess;
thumbnail/preview derivatives do not replace the original. Lab currently asks
for high quality, which requires explicit Bridge support, not a silent downgrade.

## Publication correction established by billing-crash test

Existing V1 publication is canonical output presence, not Job.status. A partial
primary checkpoint therefore must not call save_job with Job.outputs populated.
Private per-unit metadata stays in the primary checkpoint until all output units
and the existing idempotent billing operation finish. Only the final ready save
publishes the outputs. An opt-in original-hash reservation permits recovery of
unpublished Bridge bytes for exactly the same output/job/owner/hash; legacy
reservations and already published IDs remain strictly single-use.

## Validation and limitations

Focused offline tests use the actual V1 submit/run entry, Lab exploration runner,
authenticated poll handlers, real SQLite product storage and neutral primary
ledger, with only Bridge HTTP and image provider/billing boundaries doubled.
They include same-origin create-response loss and unknown recovery, batch partial
checkpoint privacy, canceled late receipts, no repeated API invocation, debit
response loss with one idempotency key, post-write original recovery, and byte,
hash, and actual dimension preservation. Primary checkpoint merges and terminal
state monotonicity prevent stale polling workers from losing completed units.

No live provider, account, local Codex CLI, deployment, or merge was exercised.
Existing Codex capabilities do not represent Lab's mandatory high-quality option
or advanced fusion controls; these intentionally produce explicit capability
fallback. Polling is the product recovery trigger after restart. Unknown API
execution remains blocked for reconciliation rather than regenerated. A Bridge
receipt without a verified model name is recorded as unknown, not invented.

Cancellation uses owner-authorized V1 job and Lab session POST endpoints. Lab
checks its own persisted session ownership, never a V1 media-session ownership
shortcut. Session cancellation latches before remote calls, preserves completed
variants, and prevents stale runners from publishing late results or new attempts.

### Serial-loop cancellation correction

Independent review found that preserving the canceled persisted session alone did
not stop a runner holding an older variant list. The runner now checks the durable
cancellation latch before every variant/submission and respects checkpoint returns.
Lab also cancels its own jobs awaiting billing preflight before a primary binding
exists; the image runner rechecks cancellation after preflight awaits. Two-variant
cooldown cancellation retains the first success and creates no second job.

### Billing versus cancellation finalization boundary

A debit-barrier regression reproduced cancellation hiding pixels after a charge
had committed. The image repository now serializes a durable billing-finalizing
latch with cancellation before calling debit. Once that boundary is entered,
V1 and Lab owner cancellation return a 409 finalization-in-progress result rather
than discarding paid pixels. The latch survives uncertain debit responses and
uses the existing debit key during recovery. Lab checks all active variant jobs
and commits its session/job cancellation under the same repository transaction;
it cannot label a billing-finalizing variant canceled. No refund or pricing rule
is introduced, and cancellation that wins before the boundary prevents debit.

The V1 public job projection removes the frozen request and private output
checkpoints, exposing only allowlisted per-unit route evidence and the billing
finalization indicator. GET, create/replay, revise, and cancel all use that
projection. Durable records remain complete for recovery. Lab already projects
its own session/variant metadata rather than the V1 raw job checkpoint.

The finalization transaction also freezes the exact user, amount, idempotency key,
source, and reference ID of the first debit. Recovery reads those parameters,
not current billing configuration, even when billing has since been disabled or
its rule/key/price changed. This preserves the originally selected charge and
prevents a lost-response retry from becoming a new charge identity.
