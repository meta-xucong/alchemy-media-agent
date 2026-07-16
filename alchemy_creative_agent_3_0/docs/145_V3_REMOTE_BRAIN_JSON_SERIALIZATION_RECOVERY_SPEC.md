# Doc145 — V3 Remote Brain JSON Serialization Recovery

## Status

Implemented shared transport hardening. This document does not change visual
direction, Human Realism semantics, template ownership, reference inheritance,
or image-Provider routing.

## Observed failure

The controlled post-Doc144 blue-dress plan reached the configured remote
Central Brain with its frozen V3 context, then the remote model returned
syntactically malformed JSON. The local runtime correctly refused to guess,
repair, or turn that partial text into a plan. A simpler request could succeed,
so this is a response-serialization reliability failure at the remote Brain
transport boundary, not evidence that the V3 Human Realism capability was
absent or that GPT Image 2 received a bad prompt.

## Contract

For one logical Brain decision:

```text
frozen request + frozen evidence
  -> remote Brain attempt 1
  -> valid JSON decision
  OR
  -> syntax-invalid JSON only
  -> one remote Brain serialization-recovery attempt on the same request
  -> valid JSON decision or fail closed
```

The recovery instruction asks the same configured remote Brain to author a
complete, strictly valid response for the existing schema. It is not a local
JSON repair, a prompt patch, a visual retry, or a second image-generation
operation.

## Hard boundaries

1. Recovery is permitted only for a syntactically invalid or non-JSON remote
   answer before any accepted Brain result exists. Empty responses, HTTP/
   network failures, content policy failures, valid-but-wrong contract shapes,
   timeouts, and canonical-prompt validation failures remain fail-closed.
2. The local runtime must never repair commas, brackets, fields, directions,
   references, creative intent, or final renderer prompts.
3. Both attempts use the same immutable `BrainRunRequest`; the recovery does
   not add a child/apparel/template route, alter reference assets, or weaken
   capability requirements.
4. SDK retry remains disabled (`max_retries=0`). The maximum is one initial
   remote transport request plus one serialization-only remote re-answer. A
   second malformed answer fails with no third attempt.
5. No image Provider operation, candidate, review, retry, project/job
   persistence, or delivery can begin until a complete Brain result passes its
   existing contract validation.
6. Local MCP relay remains conversation-only and non-certified. It receives
   the same accepted canonical prompt/reference binding as the Web Provider;
   it cannot use this mechanism to invent a plan or bypass a failed Brain.

## Provenance

Accepted results may expose only this safe transport receipt in job/finalizer
audit data:

```json
{
  "attempts": 1,
  "json_serialization_recovery_attempted": false,
  "json_serialization_recovery_succeeded": false
}
```

or the corresponding `attempts: 2` / `true` values after a successful
re-answer. Raw malformed content, credentials, URLs, complete payloads, and
provider diagnostics must not be persisted or shown to ordinary users.

## Relation to existing authority

Doc122's rule against automatic creative re-planning remains intact after a
Brain decision is accepted. This document covers the narrower prior state in
which no parseable Brain decision exists. Docs134, 139, 143, and 144 remain
authoritative for Brain-owned final prompts and shared Human Realism approval.

## Acceptance matrix

| Case | Required result |
| --- | --- |
| First answer valid JSON | One request; safe receipt says one attempt. |
| First answer malformed, second valid | Exactly two remote calls with identical user payload; recovery system instruction only on call two; accepted result records the receipt. |
| Both malformed | Fail closed after exactly two calls; no local fallback prompt or third call. |
| Timeout / HTTP / policy / valid-but-invalid schema | No serialization recovery; existing failure classification remains authoritative. |
| General, E-Commerce, Photography, Local MCP | Shared behavior only; specialist fail-closed gates and template isolation remain unchanged. |
