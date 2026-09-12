# V3 Policy-Blocked Generation Public Status Repair

## 1. Scope

This document covers the VPS acceptance run for the persisted General V3
project and the public status projection used after an upstream image policy
decision. It is a foundation/Product API projection repair, not a prompt
quality change and not a new template behavior.

## 2. Observed production fact

The same original user input reached the configured aiself OpenAI-compatible
image endpoint through the V3 background worker. The endpoint returned HTTP
400 with the structured upstream code `content_policy_violation` before any
image bytes were returned. V3 correctly classified this as terminal
`provider_policy_blocked`, made no outer retry, and preserved the Job.

The public General Phase 3 status path did not carry the already-safe
`provider_execution` projection. The browser therefore had no operation-level
`safe_reason_code` and could fall back to the generic terminal message even
though the durable retry record contained the policy classification.

## 3. Authority and correction model

1. The upstream policy response is authoritative for this request. Local V3
   must not bypass it with a different provider, repeated identical requests,
   age/scene substitutions, or an automatic semantic rewrite.
2. The durable Job remains append-only and retains the original request and
   provider evidence. A policy block is not a visual-review failure and does
   not create a candidate or delivery.
3. The Product API may expose only its existing safe operation projection:
   operation, blocked/unavailable state, reference count, delivery
   availability, and safe reason code. Raw provider messages, prompts, URLs,
   request IDs, and credentials remain private.
4. General Phase 3 must expose that same safe projection as part of its
   lifecycle metadata. The browser's terminal create/recovery paths must use
   the provider failure message for every template when one is available.

## 4. Minimal implementation

- Add `provider_execution` to the allowlisted lifecycle projection in
  `_doc270_general_phase3_safe_status`.
- Use `v3ProviderFailureUserMessage(created)` for the non-specialized V3
  terminal create response instead of unconditionally showing the generic
  no-delivery sentence.
- Keep `provider_policy_blocked` terminal and non-retryable. Do not add a
  policy-retry or prompt-rewrite fallback.

## 5. Acceptance criteria

- A General Phase 3 policy-blocked Job exposes only the safe
  `provider_execution` operation projection.
- The public response contains no raw policy text, prompt, request ID,
  provider route, or credential.
- A terminal General create response selects the specific policy-blocked
  user message; an ordinary terminal failure still has a safe fallback.
- Existing policy closure, no-pixel, retry-boundary, and frontend shell tests
  remain green.
