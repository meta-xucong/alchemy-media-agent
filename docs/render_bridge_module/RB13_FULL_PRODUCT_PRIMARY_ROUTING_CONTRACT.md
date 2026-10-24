# RB13: full-product Bridge-primary routing contract

Status: user-authorized implementation contract, 2026-10-24.

## Goal and scope

For a new image-generation unit in V1, V2, V3, or Alchemy Lab, Render Bridge
is the first transport considered.  The existing API-key-backed provider route
is used only when that unit is proven not to have been admitted by Bridge, or
when Bridge cannot represent a required hard capability.  The default shared
Bridge queue limit is 10 and is operator configurable at the Bridge service.

This supersedes the V3-development-only scope in RB00/RB10 for ordinary image
transport.  It does not authorize a deployment, merge, changes to price or
billing policy, or a rewrite of product planning/review authorities.

## Product boundaries

| Product | Primary decision point | Authorities retained locally |
| --- | --- | --- |
| V1 | `image_service._run_image_request` after planning, asset admission, and billing preflight | job/output storage, history, review, billing |
| Alchemy Lab | the same V1 transport point for each existing variant | Lab session, variant idempotency, review/history |
| V2 | `generation.create_image_job` after its fenced claim and before provider transport | V2 repositories, template lock, V2-native assets, review, billing |
| V3 | the production provider transport after canonical materialization, per output | Brain, candidate/checkpoint, review, slots, billing |

V2 must not import V1 `src_skeleton`, V3 native gateway, V1 storage, or V1
provider registry.  Explicit mocks, planning-only requests, and explicit MCP
materialization retain their current routes.

## One-way route ownership

Each unit records a durable route decision before an external call.  A Bridge
origin is stable and bound to product, owner namespace, local job/output unit,
frozen prompt/options, and ordered reference hashes.

- A capability preflight rejection, unavailable Bridge, or atomic `queue_capacity`
  rejection is a proof of non-admission and may select the API-key route.
- Loss of a create response, uncertain timeout, 5xx without an explicit
  non-admission proof, or any admitted Bridge task is `bridge_submission_unknown`
  or Bridge-owned.  Query the exact origin; do not call an API-key provider.
- Queued, running, execution-unknown, manual, or receipt-bearing Bridge tasks
  stay Bridge-owned.  Reconcile/import their original bytes only.
- User cancellation, ownership/reference mismatch, policy refusal, review/slot
  conflict, and terminal renderer failure stay at their owning layer.  They do
  not become an automatic second generation.

The prior V3 queue-wait withdrawal rule is not used for ordinary product work:
capacity affects only later, unbound requests; it never migrates an admitted
task.

## Capability and queue admission

Bridge must be asked with the original frozen request.  Required masks,
transparent background, explicit output format/compression, required input
fidelity, provider-required identity/reference treatment, and other hard
controls may use the API-key route only when negotiated Bridge capabilities do
not support them.  No code may silently strip or turn a hard control into a
prompt hint.  Advisory controls may use Bridge only when the product contract
defines their equivalence.

The Bridge database is the only queue admission authority.  Its transaction
must resolve an existing origin before counting active work, atomically compare
the configurable limit (default 10), then either create exactly one task or
return an explicit no-task-created `queue_capacity` proof.  Published queue
depth is diagnostic only and cannot replace the transactional check.

## Provenance and acceptance

Persist safe route provenance: policy version, product, selected route/reason,
Bridge origin/task/attempt, queue active count/limit, fallback execution key,
actual provider/model, receipt ID, and original image hash/size/dimensions.
Never expose tokens, local paths, raw upstream errors, or account data.

Acceptance must cover every product path, capability fallback, service outage,
queue full and 9-to-10 race, replay at capacity, response loss/restart,
unknown execution, cancellation, no double output or debit, original-byte
preservation, V2 isolation, and recovery affecting future requests only.
