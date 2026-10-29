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

The current Codex profile supports original PNG/JPEG and bounded local image
references. Renderer controls that the Codex adapter cannot express (such as
quality, size, alpha, compression, fidelity and seed hints) use the CLI's
native defaults; they do not cause an otherwise valid image-generation unit to
fall back to the traditional provider. Strong identity and required-reference
conditioning remain best-effort semantics on Codex, with the original reference
files preserved. Separate operations such as mask editing and deterministic
postprocessing remain capability-gated because they are not renderer defaults.
See the 2026-10-27 correction below for the current rule.

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
Multiple references within the declared profile limit and materialized
hard-required identity/conditioning do not by themselves force capability
fallback; see the current defaulting correction below.

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

## 2026-10-27 V3 reference-generation defaulting correction

The current V3 contract supersedes the earlier capability fallback for a
Codex `image.generate` unit solely because its materialized reference asks for
strong identity or required reference conditioning. When Bridge is accepting
tasks and the explicit reference count fits the Codex profile limit, V3 keeps
the original reference files and sends them as native Codex image inputs; it
does not route the unit to the legacy API because Bridge cannot certify an
identity-strength guarantee. `strong_identity`, `input_fidelity_required`,
`required_reference_conditioning`, and known optional rendering controls that
the Codex adapter omits use the CLI's native defaults. Unknown operations and
separate processing steps remain capability-gated. This is best-effort
native reference conditioning, not verified identity fidelity.

This correction is limited to V3's Codex image-generation adapter. It does not
change durable-task recovery, reference bytes, API fallback for Bridge
unavailability or queue-capacity rejection, or the owning handling of a
separate mask/postprocess operation.

## 2026-10-27 V3 parameter-normalization and rejection-monitor correction

The local V3 journal records only `bridge_capability_unsupported` for a
pre-admission rejection; it does not record which capability predicate failed.
The completed `job_86e9df4945` therefore proves API fallback before Bridge task
creation, but its exact rejected field cannot be reconstructed. The V3 adapter
now treats `moderation`, per-unit `count`, profile `provider_hint`, and the
direct or `option_` forms of reference-fidelity hints as native-default
controls, consistently with the Codex adapter. Unknown controls remain
hard-gated; mask and deterministic postprocess operations are not normalized
away.

For future V3 capability fallbacks, the journal and result provenance include
only a safe rejection code and, when applicable, a field name. They never
include prompt text, option values, reference paths, or image bytes. This
diagnostic does not change the route decision. Structural input limits such as
reference count, supported file type, and maximum input bytes remain explicit
capability gates and can now be distinguished from parameter mismatches.

## 2026-10-28 Reference input capacity contract

The previous Bridge advertised a 1 MiB / 1,048,576-pixel input ceiling. A V3
continuity request with a 2,976,403-byte, 1024x1536 PNG was therefore routed to
the legacy API before Bridge task creation. The Bridge input contract now
advertises a 16 MiB byte ceiling and a separate 16,777,216-pixel input ceiling;
Alchemy checks both before upload. The original PNG bytes, SHA256 and dimensions
remain unchanged. Older Bridge capabilities without input-limit fields use the
same bounded 16 MiB / 16,777,216-pixel Alchemy defaults.

The V3 project-reference admission path uses the same current byte and pixel
ceilings as Alchemy transport preflight. It reads at most 16 MiB + 1 bytes to
detect overflow, validates the image without transforming it, and returns the
original uploaded record. This prevents an earlier project filter from
silently dropping a valid reference before Bridge routing.

The frontend's `127.0.0.1:18106` listener was host Python PID `35052`, started
at `2026-10-27 22:58:46` local time. The edited V3 adapter file timestamp was
`2026-10-27 22:42:06`, so the host process started after the previous source
optimization was present. The Docker container `alchemy-media-agent:latest`
was a separate service configured for port 8017, had no host listener on that
port, and was not the process serving the observed frontend. Its image revision
label was `unknown`, but it does not explain this request's route. The proven
cause class remains an incomplete default-option allowlist in the loaded V3
adapter; the old journal cannot identify which omitted option triggered this
particular rejection. The source changes below must be loaded by the host
Alchemy process before the next real run.

## 2026-10-28 V3 continuity-reference semantic recovery

The later local V3 planning failure `job_c7a61e9f17` with
`human_realism_execution_mismatch` occurred before the image provider or
Bridge. Its persisted failure frame points to reference-channel policy
resolution for a request whose frozen input plan contains one continuity
anchor. The Brain returned an ownership intent, but its applicability was not
`applicable`; the prior path accepted that value as a complete Brain profile
and failed later during shared capability execution.

For a frozen Brain request that actually carries reference assets or selected
continuity outputs, the adapter treats `ambiguous` and `not_applicable`
ownership as a semantic-contract rejection and uses the existing single
same-request Brain recovery before capability execution. It does not infer the
reference's meaning locally. If the recovered decision remains unresolved,
the task stays blocked before any image provider request. Requests without
reference inputs continue to accept `not_applicable`.
