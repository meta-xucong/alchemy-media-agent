# RB18: V3 primary transport implementation

## Correction model

RB13 requires Bridge-first transport, not a replacement for V3 planning or
review. The current production adapter always invokes the app provider; its
output store may crop bytes to the requested aspect ratio. The authoritative
boundary is the canonical materialized, frozen, per-output request. Bridge
owns admission/recovery, while V3 owns candidate persistence, review and slots.

The minimal correction adds a V3-owned adapter at the actual production
transport boundary. A durable neutral transport binds owner/job/asset/output
and frozen options/references before dispatch. Pending, ambiguous, terminal
Bridge and previously claimed API executions never become new API calls.
Explicit mock, planning-only and MCP adapters remain untouched. Server-owned
Bridge provenance issues deterministic candidate/output checkpoints and opts
out of aspect-ratio cropping. Only persisted original pixels may be acknowledged.
Normal review and delivery authority are unchanged; this is not the older
review-only experimental native gateway.

Resume uses the same frozen generation unit. Polling may stop at the product
execution budget, but that never clears durable ownership. A repeated Generate
on the existing planned job must resolve that unit, not generate another image.
Capability requests retain exact output format/compression/background, mask,
input fidelity and identity/reference semantics; unsupported controls fall
back before admission. Reference files come from the canonical materialized
provider input plan, not the original unprocessed uploads.

## Preflight correction found by entrance tests

The first synthetic entrance run found that legacy provider selection required
an API key before the Bridge adapter could run. Transport selection is not an
API-key availability gate: when primary routing or durable recovery is active,
legacy provider construction/configuration is deferred until proven fallback.
Disabled fresh legacy requests retain the previous preflight behavior.

## Cancellation and compatibility

The owner-checked V3 endpoint POST
`/api/v3/creative-agent/jobs/{job_id}/render-bridge/cancel` only targets existing
Bridge-owned units of that job. It records the product cancellation latch
before remote cancellation. Generate cannot resume a canceled job. Late
workers may leave quarantined original bytes but cannot import a generation
result, enter review or commit a delivery slot. Checkpoint admission also checks
the durable transport latch before and after output persistence.

The current Codex profile supports quality `auto`, original PNG/JPEG, advisory
size and unverified local image references. V3's existing default `medium`
quality is not silently downgraded: it takes a capability fallback. Explicit
`auto` requests can use Bridge. Required fidelity/identity/fusion/masks/alpha
and compression remain traditional-provider requests until Bridge certifies
those controls. This is intentional, not proof that those controls work.

## Synthetic validation

The focused V3 entrance suite exercises real production materialization and the
actual CentralCreativeBrain two-output loop. The first output is checkpointed,
the second is execution-unknown, and a fresh provider/brain run reuses the first
exact output and resolves the second origin with no third create/API call.
Frozen canonical authority is Product API's `_bind_frozen_remote_creative_brain`
and ScenarioRuntime's `_frozen_remote_creative_brain_for_execution`, which binds
and verifies the answer against the server-pinned activation plan.

Focused entrance, existing provider/output/timeout and formal-slot regression:
124 passed. The separate legacy Doc203 MCP resume suite has 7 Doc228 failures
also reproduced independently on unchanged main a15ff3e (66 pass); these are
not masked or changed by this transport phase. Validation uses synthetic
pixels/clients only, not a real Codex account or paid image provider. This is
code/simulation evidence, not local-machine acceptance.

Partial specialized batches may already have a generation-result record. The
cancel operation selects only still-active Bridge units rather than treating
any partial result as proof the entire batch finished. Existing pixels remain
append-only; remaining units are canceled and cannot advance the review chain.
Multiple-reference fusion and materialized hard-required conditioning also
force capability fallback while the Codex profile only promises unverified
local image inputs.

## Between-output cancellation correction

An empty active-unit list is not whole-job completion: the first output can
already be ACKed while the serial loop has not yet created the second unit.
Cancellation now writes a V3-owned persistent batch latch even in that window,
unless the complete product job is already GENERATED. A per-job SQLite gate
serializes that latch with initial transport resolution, so cancellation cannot
miss a concurrently admitted next unit. Every subsequent unit and API fallback
claim checks the latch. Previously persisted output pixels are never deleted.
Mode disable during an already-owned batch does not bypass the latch or the
neutral API execution claim.
