# V3 Brain No-Semantic-Response Start Timeout Repair Specification

Status: implementation-ready correction specification
Scope: V3 Foundation Brain transport and failure projection only
Authority: V3 Brain transport boundary; no template or image-provider contract changes

## 1. Observed mismatch

The deployed revision `665bb69a` correctly contains the semantic stream-idle
watchdog. A controlled VPS run using the frozen `Vertical magazine cover`
project input produced a new Job with these safe facts:

- the request was dispatched and a response was started;
- no semantic content or reasoning token was observed;
- no JSON parse started and no image-provider request was issued;
- the plan attempt remained in `read_timeout` for about 270 seconds and the
  outer receipt closed at about 300 seconds;
- the Job was safely blocked, but no bounded retry was admitted because the
  remaining plan window could not preserve the canonical-finalizer reserve.

This is distinct from the earlier partial-response failure, where the stream
had emitted semantic content and then stalled. The existing semantic-idle rule
cannot apply before the first semantic token exists.

## 2. Responsible layer

The owning layer is the V3 Foundation Brain transport/recovery boundary:

`SSE response start -> semantic response start -> complete JSON -> Brain contract`

It is not a prompt/template defect, an image-provider defect, a frontend
defect, or permission to invent a local Brain answer. The Core contract remains
fail-closed: a complete remote Brain plan is required before a Product Job or
image request can proceed.

## 3. Correction model

One streaming Brain call has two independent bounded response windows:

1. Before the stream has begun, the existing connect/TTFB and hard-call
   ceilings remain authoritative.
2. After HTTP response headers are received but before the first non-empty
   reasoning/content delta, a bounded first-semantic-response window applies.
3. After semantic progress begins, the existing semantic-idle window applies
   from the most recent non-empty reasoning/content delta.

The effective deadline is the minimum of the hard call deadline, stage/shared
   budget ceiling, first-semantic deadline (when applicable), and semantic-idle
   deadline (when applicable). SSE comments, blank lines, role-only deltas,
   empty deltas, and a response header do not count as semantic progress.

The first-semantic window is transport-only and bounded by code. Its default is
60 seconds, configurable only through the internal
`V3_LLM_BRAIN_STREAM_FIRST_SEMANTIC_TIMEOUT_SECONDS` setting, with a finite
5-to-120-second clamp. The underlying streaming read timeout is kept just
above this window so the outer guard can close the stream and record the same
terminal evidence.

On timeout, the transport closes its registered response/client resources and
admits the existing single transient retry only after the first worker is
confirmed stopped. If the shared/stage window cannot legally fit another
attempt, the original transport timeout remains the terminal cause. A true
shared-budget exhaustion remains a budget failure. No public error schema,
prompt, creative decision, or image-provider fallback changes.

## 4. Invariants and non-goals

- A response that never emits semantic content must not hold the plan stage for
  the full 270-second read window.
- A stream with continuous semantic progress must not be killed by the
  first-semantic window.
- A stream that emits only transport noise must not extend either semantic
  window.
- Complete-response transports are not governed by the stream-only
  first-semantic window.
- Retry remains at most once and never overlaps an uncooperative worker.
- No local JSON repair, prompt reconstruction, deterministic creative fallback,
  or image generation is allowed after a missing Brain answer.
- V1, V2, General Template, specialized templates, frontend projections, and
  image-provider routing remain unchanged.
- Internal timing flags are not persisted in public metadata; existing safe
  transport receipts remain the public contract.

## 5. Implementation and verification

Implementation is limited to the V3 Brain provider, its focused transport
regression tests, and this specification. Tests must cover:

- bounded configuration and finite clamping;
- no-semantic stream timeout and resource closure;
- semantic progress bypassing the initial window;
- transport noise not counting as semantic progress;
- complete-response transport remaining unaffected;
- one retry after a stopped first worker and fail-closed behavior when the
  retry/stage budget is insufficient.

Controlled VPS acceptance must reuse the exact frozen project input and verify
the durable chain `planning_result -> generation_result -> output file`.
Success requires a generated/selected Job with at least one durable image;
any upstream timeout must remain a safe blocked receipt and must not be
reported as a successful generation.
