# 63 V3 Image-Edit Provider Health Cooldown And Fallback Spec

## 1. Status And Authority

Doc63 is the provider-stability patch after Doc62.

It responds to real upstream evidence:

```text
404token/aicodexvip image routing can intermittently return upstream 403.
aiai-gpt-image-2 can intermittently return image-edit 500.
Both can also succeed on the next call.
```

Doc63 owns V3/app image provider behavior and the downstream sub2api gateway
short-cooldown behavior for transient image-edit failures. It does not change
Project Mode, Visual Capability Cluster, prompt planning, ScenarioRuntime,
Product API contracts, or E-Commerce slot behavior.

## 2. Goal

When an image-edit/reference-image request hits a transient upstream failure,
the system should:

```text
not permanently disable the account or provider
mark only a short local image-edit cooldown
retry after the short cooldown
let downstream routing choose another schedulable account when available
surface a clear retryable provider error only after bounded attempts fail
```

The user-facing effect should be:

```text
one shaky upstream account should not fail the whole generation when another
schedulable image-edit account can recover the request
```

## 3. Scope

Allowed:

```text
add image-edit specific transient failure classification
add image-edit short cooldown separate from global quota cooldown
add bounded retry for gateway 403, 500, 502, 503, 504, timeout/transport errors
add SDK request timeout for image-edit/reference-image calls
add total operation timeout for image-edit/reference-image calls so multiple
  transient retries cannot stack into an unbounded wait
add downstream sub2api per-account short cooldown for `/v1/images/edits`
  transient failover statuses
add tests for transient 403/500 recovery
record fallback/cooldown evidence in output metadata
```

Not allowed:

```text
disable accounts permanently
write long-lived sub2api account errors for transient image-edit flaps
change account priority order
raise global retry loops without bound
retry official OpenAI authentication/permission 403 as if it were transient
hide final provider failure if all retry attempts fail
```

## 4. Transient Failure Rules

For `images.edit` / reference-image generation:

```text
408, 429, 500, 502, 503, 504:
  transient retryable

timeout / transport / connection errors:
  transient retryable

403:
  retryable only when the configured base URL is an OpenAI-compatible gateway
  such as aiself.vip, or when the error body indicates upstream/provider/account
  routing failure
```

For official `api.openai.com` 403:

```text
do not treat as transient by default
```

## 5. Cooldown Rules

Image-edit transient cooldown is separate from quota cooldown.

```text
quota cooldown:
  follows retry-after / long upstream quota rules

image-edit transient cooldown:
  short, default 12 seconds
  applies only to image-edit/reference-image calls
  clears immediately after a successful image-edit call
```

This keeps text-to-image responsive while reference-image routing recovers.

Downstream gateway rule:

```text
sub2api `/v1/images/edits` failover statuses 403, 408, 500, 502, 503, 504
temporarily mark the current account unschedulable for a short configurable
window (`gateway.image_edit_transient_cooldown_seconds`, default 12).

This is not a permanent account disable. It only prevents the next user request
from immediately choosing the same flapping image-edit account while the current
request fails over to the next schedulable account.
```

## 6. Timeout Rules

The provider must set a bounded SDK timeout for image generation and image edit,
and image-edit/reference-image generation must also have a total operation
deadline. The total deadline prevents six retry attempts from each waiting the
full SDK timeout when the upstream simply never returns.

Default:

```text
OPENAI_IMAGE_REQUEST_TIMEOUT_SECONDS = 240
OPENAI_IMAGE_EDIT_REQUEST_TIMEOUT_SECONDS = 240
```

The goal is not to make generation impatient. The goal is to prevent one stuck
upstream edit request from hanging a whole V3 continuation test forever.

## 7. Test Plan

Focused tests:

```text
OpenAI image provider retries gateway image-edit 403 and succeeds
OpenAI image provider retries gateway image-edit 500 and succeeds
OpenAI image provider slow image-edit call exits after total operation timeout
official OpenAI 403 is not classified as transient gateway 403
image-edit cooldown does not permanently disable the provider
sub2api image-edit 500 temp-unschedules only the failing account briefly
sub2api image-edit 400 does not temp-unschedule
sub2api image-edit transient cooldown can be disabled by config
```

Regression:

```text
tests/test_provider_contract.py
V3 project/provider focused tests
sub2api backend/internal/service focused unit tests
sub2api backend/internal/config focused tests
sub2api backend/internal/handler image tests
compileall
git diff --check
```

Real validation:

```text
rerun .codex-longrun/doc61_real_portrait_validation.py
if provider is stable, verify selected-output reference continuation produces
continuation outputs again
```

## 8. Completion Criteria

Doc63 is complete when:

```text
documentation exists
provider code has image-edit specific short cooldown and retry classification
provider code has image-edit total operation timeout
sub2api source has image-edit transient account short cooldown
focused tests pass
broad regression passes
real V3 reference-image continuation is attempted and recorded
ServerChan review notification is sent
```
