# Doc325 — V3 Vision Review Model Failover and Single-Model Request Policy

## Current authority

This revision supersedes the earlier same-model JSON serialization recovery
policy and the previous single-provider-request wording. A review uses the same
ordered model candidates as the V3 Brain: configured primary, `kimi-k3`, the
configured Brain backup if distinct, and `gpt-6.1-sol` as the final fallback.
Each candidate can receive at most one request for a given image in one review
execution.

Both Brain and visual review read the unified gateway key and base URL through
the same shared configuration helper. Lab-specific or legacy V3 vision
credentials must not silently redirect review traffic to another endpoint.
This contract governs the shared post-generation visual inspector. The
specialized formal-slot Body Cross-View Review remains owned by its separate
Lab configuration and review contract.

## Contract

```text
one image + frozen review context
  -> ordered model candidates (shared V3 Brain routing rule)
  -> at most one request per candidate; no same-model retry or JSON repair call
  -> valid JSON object: validate and apply the existing visual-review contract
  -> model refusal: stop and preserve the image for manual confirmation
  -> recoverable transport/provider failure or malformed JSON: try the next candidate once
  -> gateway authentication/permission rejection or model refusal: stop the chain
  -> all candidates exhausted: preserve the image and mark review incomplete /
     manual confirmation required
```

Hard rules:

- Use the same model-candidate builder as pre-generation V3 Brain; do not keep a
  separate model order or a hard-coded single review model.
- A candidate gets at most one multimodal request. Do not retry that same model,
  repair its JSON locally, or send a second recovery prompt to it.
- A timeout, recoverable provider failure, or malformed JSON may advance to the
  next model candidate, once. HTTP 401 stops immediately. HTTP 403 advances
  only when the structured error explicitly scopes `model_not_found`,
  `model_not_available`, `model_access_denied`, or `model_permission` to a
  `model` or `candidate`; an unscoped/account-level 403 stops because changing
  models cannot repair shared permissions. A valid JSON response proceeds
  directly to semantic review; a model refusal also stops the chain without
  sending the image to another model.
- A timeout or malformed response is not itself a visual-quality verdict. If
  all candidates fail, mark review incomplete/manual confirmation required; do
  not convert transport/serialization failure into an image regeneration retry.
- The image is sent at most once to each candidate in one review execution. A
  later explicit user action may start a new review execution.
- Keep the generated output visible and preserved; report the provider failure
  separately so the user can review the image manually.
- An explicit later user action may start a new review execution. Automatic
  finalizing recovery must not silently resubmit the same image after a review
  transport or serialization failure.
- Each upstream candidate request uses the configured per-request timeout, with
  a 300-second maximum. The enclosing wait budget must cover the sequential
  candidate chain; the default three candidates allow up to 900 seconds and a
  distinct configured backup can produce four candidates / up to 1200 seconds,
  plus the bounded queue wait.
- Keep compatibility evidence fields for same-model recovery attempts; they
  must remain `false`. Record the selected model and sanitized per-candidate
  outcomes so operators can distinguish primary success from failover.

## Why parsing can fail

OpenAI-compatible candidates ask for `json_object`; Anthropic Messages relies on
the frozen review prompt's JSON-only contract. The parser accepts a JSON object
and can strip surrounding prose; it still rejects empty output, non-JSON text,
truncated JSON, invalid syntax, and non-object JSON values. A malformed response
may move the image to the next distinct model once, but it never triggers a
same-model repair prompt. Current request logs do not retain full provider
bodies, finish reason, or output-token usage; sanitized diagnostic metadata may
be added without retaining prompts, images, credentials, or response bodies.

The response is parsed before semantic validation. Therefore model failover on
malformed JSON applies only to syntax/empty/non-object failures, not to a valid
JSON object that is missing a required review field or has an invalid verdict.
Those cases remain fail-closed under the existing review contract and do not
start a second model request.

## Diagnostics boundary

The current records retain per-model outcome/failure class and elapsed time,
along with the JSON parse position when available. They do not retain
`finish_reason` or output-token usage, so malformed responses cannot be
attributed more narrowly. If future diagnosis needs those fields, add only
sanitized metadata such as failure kind, parse position, `finish_reason`, and
output-token usage. Never persist or expose full provider response bodies,
prompts, credentials, or image data URLs.
