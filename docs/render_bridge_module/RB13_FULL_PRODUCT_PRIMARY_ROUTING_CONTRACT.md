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

Alchemy freezes the original product/provider request before route selection.
For `codex-image`, the Bridge adapter sends a separate, deterministic native
request copy; it never mutates the frozen request used by a proven
pre-admission API fallback. Source-provider controls absent from the Codex
ImageGen tool normalize to its native defaults instead of rejecting the Bridge
route. The normalized mapping is recorded in safe result provenance.

Codex ImageGen's native request contract is `prompt`, up to five explicit
`referenced_image_paths` (or, alternatively, a recent-image window), and
`transparent_background` (default false). The Alchemy adapter uses explicit
paths, never the ambiguous recent-image window. Alchemy's `count` remains one
frozen Bridge task per output. Current normalization is:

| Alchemy control | Codex ImageGen mapping |
| --- | --- |
| `quality` | `auto` / native default |
| `size`, `width`, `height`, `aspect_ratio` | `auto` / native default |
| `seed` | omitted |
| `output_format`, `output_compression` | native default; preserve and publish returned original bytes/MIME |
| `input_fidelity` | omitted; GPT Image 2 model default is high |
| `background=transparent` / `transparent_background=true` | 0.163.0: instruct native `transparent_background=true`; 0.157.1: normalize to the CLI's `background=auto` default |
| `input_images` | validated local files mapped to `referenced_image_paths` (maximum 5) |
| `count` | one output per task unit |
| `provider_hint` | configured Bridge execution profile |

Unsupported product operations that are not mere optional rendering controls
(for example required downstream deterministic post-processing) remain subject
to their owning product contract. No reference is silently truncated: more
than five references are rejected before Bridge submission. Once Bridge has
accepted or may have accepted a task, normalization cannot authorize an API
retry or new task identity.

Codex's app-server does not expose a Bridge-side structured imagegen call
parameter object. The executor passes an explicit tool-use instruction and
`localImage` inputs; Codex itself emits the imagegen tool invocation. Therefore
these are version-aware normalized instructions, not a claim that Bridge
directly injects or independently verifies the generated function-call JSON.

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
