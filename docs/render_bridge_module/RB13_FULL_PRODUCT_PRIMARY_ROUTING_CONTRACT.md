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
For new V1, V2, V3 and Lab `codex-image` units carrying the frozen opt-in marker below, the
Bridge adapter sends a separate, deterministic native-default request copy;
it never mutates the frozen request used by a proven
pre-admission API fallback. Source-provider controls absent from the Codex
ImageGen tool normalize to its native defaults instead of rejecting the Bridge
route. The products share the pure Codex parameter mapping without sharing
their storage, review or billing authorities. Masks, missing references,
deterministic postprocessing and unverified required conditioning remain hard
capability gates; optional parameter adaptation does not silently waive them.
Historical admitted units retain their original semantics. Defaults do not promise
visual quality, dimensions or aspect ratio equivalent or close to the source request.

The verified `rust-v0.163.0` ImageGen tool contract is `prompt`, up to five explicit
`referenced_image_paths` (or, alternatively, a recent-image window), and
`transparent_background` (default false: opaque; true: transparent). The
Alchemy adapter uses explicit
paths, never the ambiguous recent-image window. Alchemy's `count` remains one
frozen Bridge task per output. Both verified CLI tags internally use
`model=gpt-image-2`, `quality=auto`, `size=auto`, and `n: None` (not explicit
`n=1`); one-image instructions and single-artifact acceptance are Bridge policy.
`rust-v0.157.1` has no transparency argument and uses `background=auto`; it
cannot guarantee transparent output. Current product opt-in normalization is:

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
than five references are rejected before submission of a new opt-in request.
Once Bridge has
accepted or may have accepted a task, normalization cannot authorize an API
retry or new task identity.

Codex's app-server does not expose a Bridge-side structured imagegen call
parameter object. The executor passes an explicit tool-use instruction and
`localImage` inputs; Codex itself emits the imagegen tool invocation. Therefore
these are version-aware normalized instructions, not a claim that Bridge
directly injects or independently verifies the generated function-call JSON.
Provenance such as `native_tool_argument` records the intended mapping, not an
observed tool argument, verified reference conditioning or verified alpha.

The Bridge database is the only queue admission authority.  Its transaction
must resolve an existing origin before counting active work, atomically compare
the configurable limit (default 10), then either create exactly one task or
return an explicit no-task-created `queue_capacity` proof.  Published queue
depth is diagnostic only and cannot replace the transactional check.

## Frozen adapter compatibility

New V1/Lab checkpoints and V2 frozen records persist
`adapter_version=codex_cli_imagegen_v1`; all four products send
`parameters.codex_adapter=codex_cli_imagegen_v1` on new native-default units.
V3 selects its exact legacy or native request against the existing journal
before recovery, checkpoint and ACK; cancellation retains owner-scoped bindings.
Admission requires that exact
value in the selected profile's `parameter_contract.codex_adapter.values`.
Versioned requests use its nested `image_options_contract`; the profile's outer
`image_options_contract` remains legacy-compatible for older clients.
An older Bridge without this capability receives no create request; only the
existing proven pre-admission API fallback is allowed, with original parameters.
The frozen version is not renegotiated during recovery.

V2 PR38 and initial PR39 records lack an adapter version. Recovery reconstructs
both known historical requests and selects only an exact existing journal digest
under the same product/owner/unit key. It never changes the stored digest or
payload. No matching digest fails closed; no ledger retains the older strict
adaptation. Unknown future versions also fail closed. Resume, cancel and native
registration/ACK use the same selection. Existing durable ACK intents continue
through the unchanged journal maintenance path.

V1/Lab existing unmarked checkpoints retain their exact legacy reconstruction.
Basic source edits on new marked units include the authorized original output
bytes as a reference; ownership, session and publication restrictions still apply.

## Explicit prompt canvas authority

For newly planned work, explicit current-prompt output dimensions/aspect ratio
take precedence over structured/manual controls, template suggestions and
defaults. Reference-image geometry, object measurements, negative instructions
and ambiguous mentions do not authorize a canvas override. V1 and V2 keep
product-local parsers; Lab uses the V1 planning authority. V3 uses its existing
Brain semantic canvas fields and freezes synchronized effective provider options,
so a stale typed size cannot replace the resolved prompt intent downstream.

An exact supported canvas is sent without aspect-ratio approximation. An
unsupported well-formed canvas uses the selected renderer's native default;
strict malformed-input validation remains separate. The complete original
prompt is retained, and derived hints must not contradict it. Native defaults
and requested dimensions are not evidence of decoded output dimensions. Trusted
historical frozen plans are not reinterpreted or regenerated by this change.

The [official GPT Image 2 guide](https://developers.openai.com/api/docs/guides/image-generation)
and [Images generate reference](https://developers.openai.com/api/reference/resources/images/methods/generate)
allow custom sizes such as 1536x864: both edges are multiples of 16, the longest
edge is at most 3840, aspect ratio at most 3:1, and area is 655360–8294400 pixels.
These API rules are not Codex CLI arguments: the pinned CLI still uses native
`size=auto`. Compatibility-gateway acceptance and actual image dimensions still
require separate live verification.

V1 revisions resolve canvas intent from the current feedback, not concatenated
historical prompt text. V2 planning cache policy is versioned so decisions made
under manual-controls-first precedence cannot be reused for fresh planning;
already frozen jobs and execution journals are unchanged.

Provider policies remain separate. Gemini accepts only its existing declared
aspect-ratio set and otherwise omits the override. For the configured known
Seedream 4.0 model, the [official image-generation contract](https://console.volcengine.com/ark/region:cn-beijing/docs/image-generation-api)
allows 921600–16777216 pixels and width/height from 1/16 to 16, with default
2048x2048; it does not impose OpenAI's multiple-of-16 rule. Its unsupported size
is omitted, not sent as literal `auto`. The existing compatibility-gateway JSON
and multipart routes are not changed or certified by these official model rules.

Bridge wire requests without `codex_adapter` retain the legacy Bridge contract,
including its eight-reference admission limit for compatibility/recovery. Eight
is not a verified CLI editing capability: both pinned tools cap edit inputs at five.
Initial PR39/Bridge PR2 unversioned traffic cannot be retrospectively identified
as native-default traffic from its parameter contents alone. Recovery preserves
its original bytes and identity; it must not reinterpret a JPEG or other hard
legacy contract to force acceptance. Ambiguous historical outputs may require
manual confirmation rather than regeneration or relaxed validation.

## Official parameter evidence (rechecked 2026-10-25)

- [Codex rust-v0.163.0 tool.rs](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/ext/image-generation/src/tool.rs)
  and [rust-v0.157.1 tool.rs](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/ext/image-generation/src/tool.rs): exact tool arguments, defaults and mutually exclusive reference modes.
- [0.163.0 TurnStartParams](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server-protocol/schema/typescript/v2/TurnStartParams.ts)
  and [0.157.1 TurnStartParams](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/app-server-protocol/schema/typescript/v2/TurnStartParams.ts): no direct imagegen argument injection field.
- [GPT Image 2 parameter reference](https://developers.openai.com/api/docs/guides/image-prompting),
  [Images edit API](https://developers.openai.com/api/reference/resources/images/methods/edit),
  and [Responses image-generation](https://developers.openai.com/api/docs/guides/tools-image-generation).

API support for quality, size, formats/compression, quantity, sixteen edit inputs,
or Responses `action` does not establish those CLI tool fields. The pinned CLI
selects generate/edit from reference presence, exposes no seed control, and
omits `input_fidelity` as required for GPT Image 2. Unknown CLI versions remain
rejected pending separate review and local acceptance. Source review is not a
real-generation or account-capability acceptance result.

## Provenance and acceptance

Persist safe route provenance: policy version, product, selected route/reason,
Bridge origin/task/attempt, queue active count/limit, fallback execution key,
actual provider/model, receipt ID, and original image hash/size/dimensions.
Never expose tokens, local paths, raw upstream errors, or account data.

Acceptance must cover every product path, capability fallback, service outage,
queue full and 9-to-10 race, replay at capacity, response loss/restart,
unknown execution, cancellation, no double output or debit, original-byte
preservation, V2 isolation, and recovery affecting future requests only.
