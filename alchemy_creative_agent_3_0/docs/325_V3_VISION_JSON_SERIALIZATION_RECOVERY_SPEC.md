# Doc325 — V3 Vision Review Single-Request Failure Policy

## Current authority

This revision supersedes the earlier two-call JSON serialization recovery policy.
Each generated output gets one Vision provider request in one review execution.

## Contract

```text
one image + frozen review context
  -> one provider request
  -> valid JSON object: validate and apply the existing visual-review contract
  -> timeout, provider error, or malformed JSON: preserve the image and mark
     review incomplete / manual confirmation required
```

Hard rules:

- Never issue a second full multimodal request for the same image because the
  first response timed out or could not be parsed.
- `protocol=auto` uses the Responses route once. It must not resend the image via
  Chat after a malformed response or route error; operators can explicitly pin
  `chat_completions` when that is the supported gateway protocol.
- A timeout or malformed response is an unavailable review result, not a visual
  quality verdict. It must not create a quality failure or an automatic image
  regeneration retry.
- Keep the generated output visible and preserved; report the provider failure
  separately so the user can review the image manually.
- An explicit later user action may start a new review execution. Automatic
  finalizing recovery must not silently resubmit the same image after a review
  transport or serialization failure.
- Retain the existing per-request timeout setting and its 300-second maximum.
- Keep compatibility evidence fields for recovery attempts, but they must report
  `false` for this single-request policy.

## Why parsing can fail

The provider request already asks for `json_object`, but this is an
OpenAI-compatible endpoint and its implementation may not honor that mode
consistently. The parser accepts a JSON object and can strip surrounding prose;
it still rejects empty output, non-JSON text, truncated JSON, invalid syntax,
and non-object JSON values. Current request logs do not retain the provider body,
finish reason, or output-token usage, so a specific malformed response cannot be
attributed to truncation, gateway behavior, or model formatting after the fact.

The response is parsed before semantic validation. Therefore this failure policy
applies only to syntax/empty/non-object failures, not to a valid JSON object that
is missing a required review field or has an invalid verdict. Those cases remain
fail-closed under the existing review contract.

## Diagnostics boundary

The current records retain the failure class and, for syntax errors, sometimes
the JSON parse position. They do not retain `finish_reason` or output-token
usage, so historical malformed responses cannot be attributed more narrowly.
If future diagnosis needs those fields, add only sanitized metadata such as
failure kind, parse position, `finish_reason`, and output-token usage. Never
persist or expose full provider response bodies, prompts, credentials, or image
data URLs. This can distinguish gateway formatting drift from output
truncation without issuing a second image review.
