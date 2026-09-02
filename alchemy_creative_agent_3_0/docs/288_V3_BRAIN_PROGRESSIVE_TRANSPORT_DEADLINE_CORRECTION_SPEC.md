# Doc288 - V3 Brain Progressive Transport Deadline Correction

Status: **active shared-foundation correction authority.**

This document corrects the live Remote Brain transport boundary without
changing Brain ownership, prompt semantics, provider routing, image-provider
behavior, or V2/Sub2API behavior.

## 1. Observed defect

The earlier `210/520/540` arrangement treated 210 seconds as the maximum read
window for one Remote Brain call. A real planning trace showed a valid Brain
response beginning after more than two minutes and the call then failing at
that read boundary before complete JSON arrived. The outer logical budget was
finite, but the per-call cap was too small for this observed response shape.

The old 210-second value remains in historical evidence and historical
correction records. It is not the current runtime authority.

## 2. Current correction

The four timeout authorities use one shared contract:

| Boundary | Current default | Current maximum | Responsibility |
| --- | ---: | ---: | --- |
| Remote Brain transport call | 300 seconds | 360 seconds | One HTTP/SDK call, including response completion |
| Shared Brain preparation budget | 520 seconds | Explicit deployment setting | All Brain calls in one preparation |
| Native MCP planning parent | 540 seconds | Explicit deployment setting | Process/IPC outer deadline |

An unset `V3_LLM_BRAIN_TIMEOUT_SECONDS` uses 300 seconds. An explicit value is
bounded to 1 through 360 seconds. The shared preparation budget remains one
finite deadline; it is not multiplied by the number of calls. The default
budget is 520 seconds. If an explicit per-call window is larger than the
default, the derived default budget is at least that window plus a 220-second
handoff margin, unless the operator explicitly supplies a budget.

The Native MCP entry point derives its default transport window from the same
300-second authority and keeps its 540-second parent deadline. The parent
deadline is intentionally outside the 520-second shared Brain budget by a
small process/IPC margin. An explicit Native transport override is bounded to
the same 360-second maximum.

## 3. Execution rules

1. Each Brain call uses the smaller of its bounded per-call window and the
   remaining shared preparation budget.
2. A progress-aware stream may use the existing progress grace behavior, but
   it may not cross the shared preparation deadline.
3. When the shared budget is exhausted, the runtime returns the existing
   `execution_budget_exhausted` failure class and does not start another Brain
   call or send an image request.
4. A transport timeout still cancels and closes the in-flight transport when
   the adapter can do so. There is no detached request, opaque retry, or local
   creative fallback.
5. The timeout values are transport metadata only. They are not sent to the
   Brain, included in creative prompts, persisted as creative facts, or used
   to select an image size, route, reference, or deliverable.

## 4. Compatibility and non-goals

This is a boundary correction, not a change to the two-stage Brain contract.
The Remote Brain remains the sole creative authority, and the existing
fail-closed behavior remains in force for unavailable, malformed, incomplete,
or budget-exhausted responses. It does not add retries, split one request
into independent plans, shrink user/reference context, switch models, or
alter image-provider timeouts.

The historical Doc259 discussion of `210/520/540` remains append-only evidence
of the earlier live hypothesis. Doc288 supersedes its current-runtime
recommendation not to raise the transport window. Future changes must update
the shared constants, the HTTP adapter, the Native MCP boundary, the
environment example, and their regression tests together.

## 5. Acceptance invariants

- No production default or hard clamp leaves the live Brain call at 210
  seconds when the timeout setting is unset.
- The ordinary default is exactly 300 seconds and the explicit maximum is
  exactly 360 seconds across schema, provider, adapter, and Native MCP.
- The default shared budget remains exactly 520 seconds, and a larger explicit
  per-call window does not silently create an unbounded budget.
- A slow call that remains within the configured window can complete; a call
  that crosses the shared budget fails closed before image generation.
- No V2, Sub2API, image Provider, MCP materialization, or frontend contract is
  changed by this correction.
