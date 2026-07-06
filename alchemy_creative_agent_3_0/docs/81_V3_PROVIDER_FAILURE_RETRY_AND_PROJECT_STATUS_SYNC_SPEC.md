# 81 V3 Provider Failure Retry And Project Status Sync Spec

## 1. Status And Authority

Doc81 is the provider-failure recovery patch after Doc80.

It is compatible with:

```text
Doc53 bounded retry guardrails
Doc63 image-edit provider health/cooldown rules
Doc64 commercial-quality review and retry rules
Doc66 candidate-scoped visual retry closure
Doc77 foundation-quality review/retry tuning
Doc80 provider-reference upload compression
```

Doc81 does not replace visual auto retry. It adds a separate first-pass
provider failure retry layer for cases where no image was produced and visual
review cannot run.

## 2. Problem

The existing V3 retry system mainly handles generated-image quality problems.
That path requires at least one candidate image.

When the first provider request fails before any image exists, for example:

```text
OpenAI image reference generation failed. TimeoutError
502 / 504 gateway timeout
OpenAI image URL could not be downloaded
provider returned no image bytes
bad_response_status_code from an OpenAI-compatible gateway
```

the Product API can return `blocked` with zero candidates. In that state:

```text
visual_auto_retry has nothing to inspect
sub2api gets no second fresh request, so it cannot reroute lanes
Project timeline may show only job_created
the frontend may look stuck even though the backend already blocked the job
```

## 3. Goal

Once a V3 job has entered real image generation, a retryable provider failure
must trigger at least one bounded fresh provider request before the job becomes
blocked.

The user-facing behavior should be:

```text
first provider failure
  -> V3 records "trying another route"
  -> V3 sends a fresh provider request
  -> sub2api can choose another schedulable lane
  -> success enters normal visual review
  -> final failure becomes a clear project timeline item and frontend message
```

## 4. Retry Taxonomy

Doc81 adds a provider failure classifier.

Retryable provider failures:

```text
TimeoutError
asyncio.TimeoutError
ProviderRuntimeError whose detail/message contains timeout
ProviderRuntimeError whose detail/message contains image reference generation failed
ProviderRuntimeError whose detail/message contains image generation failed
HTTP 408 / 429 / 500 / 502 / 503 / 504
gateway timeout
bad_gateway
bad_response_status_code from provider/gateway
OpenAI image URL could not be downloaded
provider returned no image outputs
provider output did not include image bytes
transport / connection reset / read timeout
temporary upstream 403 from OpenAI-compatible gateways
```

Non-retryable failures:

```text
provider_not_configured
missing API key
invalid API key / authentication failure
insufficient balance
policy or safety block
invalid user input
invalid uploaded asset id
source reference file missing or unreadable
unsupported media type after upload validation
official OpenAI permission 403 when not routed through a gateway
```

Unknown provider failures are retryable once if they occur after real
generation has started and are not classified as non-retryable.

## 5. Budget Rules

Doc81 introduces a provider failure budget separate from visual auto retry.

Defaults:

```text
text-to-image provider failure retry attempts: 1 extra fresh request
image-edit/reference provider failure retry attempts: 1 extra fresh request
image-edit single-attempt timeout: 420 seconds on VPS-compatible deployments
cooldown between fresh requests: 8-15 seconds
total provider failure fresh requests per job: max 2
visual auto retry: unchanged, still governed by Doc53
```

No infinite loop is allowed.

The full job safety rule is:

```text
provider failure retry first, only when zero usable candidates exist
visual auto retry second, only after candidate images exist
never retry config, billing, policy, or invalid-input failures
preserve existing outputs; never overwrite generated assets
```

## 6. Provider Layer Requirements

The V3 ProductionImageGenerationProvider must:

```text
catch wrapped retryable provider errors, not only raw TimeoutError
perform a fresh provider request on retry
add retry metadata to the App ImageGenerationRequest
mark fresh_upstream_request=true for retry attempts
sleep a bounded cooldown before the retry
raise final error only after the provider-failure budget is exhausted
```

Metadata keys:

```json
{
  "provider_failure_retry": {
    "executed_count": 1,
    "max_attempts": 2,
    "fresh_upstream_requests": 2,
    "final_status": "succeeded | failed | skipped",
    "attempts": [
      {
        "attempt": 1,
        "status": "failed",
        "classification": "retryable_provider_failure",
        "error_type": "ProviderRuntimeError",
        "message": "OpenAI image reference generation failed. TimeoutError"
      },
      {
        "attempt": 2,
        "status": "succeeded"
      }
    ]
  }
}
```

Provider retries must be visible in output metadata when successful.

## 7. Product API And Project Timeline Requirements

If provider retry succeeds:

```text
normal job_generated timeline is written
visual_review timeline is written as before
optional visual_retry timeline is written if visual auto retry executes
```

If provider retry fails:

```text
job status becomes blocked
Project timeline receives provider_failure_retry / job_blocked evidence
frontend polling receives blocked status instead of waiting forever
```

Timeline text must be beginner-friendly:

```text
V3 已自动换线重试
上游生图暂时超时，本次没有生成图片。项目已保留，可以稍后重新生成。
```

Engineering terms such as stack traces, provider class names, job internals,
and raw exception dumps must not be shown as primary UI copy.

## 8. Frontend Requirements

The V3 frontend must:

```text
poll the job after async background generation starts
stop progress when job.status is blocked or failed
show retry/failure copy instead of leaving the progress bar running
refresh project timeline after blocked/failed job status
render provider retry timeline rows as small workflow events
avoid exposing raw provider exceptions in the main project UI
```

Recommended progress copy:

```text
retrying: 正在换一条线路重试
blocked: 上游生图暂时没有成功，项目已保留
failed: 本次没有生成图片，可以稍后再试
```

## 9. Compatibility Notes

Doc81 is compatible with older docs because it does not change their retry
domain:

```text
Doc53 remains the loop-budget authority
Doc63 still owns image-edit transient classification and cooldown
Doc64/66/77 still own generated-image quality retry
Doc80 still owns reference-image compression before provider submission
```

Where older docs say provider failures should not trigger visual retry, that
still holds. Doc81 adds provider-failure retry before visual retry exists.

## 10. Implementation Steps

1. Add provider-failure classification helpers in the V3 production provider.
2. Extend `_run_app_provider_with_timeout_retry` to catch retryable wrapped
   errors and run one fresh provider request.
3. Carry provider retry summary into provider metadata and output metadata.
4. Increase image-edit timeout default or deployment value to match slow K12
   image-edit lanes.
5. Extend Project Mode timeline enum with provider retry / job blocked events.
6. Append clear Project timeline entries when a generated job is blocked or
   fails.
7. Make frontend recovery polling stop cleanly on blocked/failed and refresh
   timeline.
8. Add tests for:
   - wrapped TimeoutError retries once and succeeds
   - wrapped TimeoutError retries once and then blocks with summary
   - non-retryable config/policy failures do not retry
   - project timeline records blocked provider failures
   - frontend code contains user-friendly blocked/retrying copy

## 11. Acceptance Criteria

Doc81 is complete when:

```text
wrapped provider timeouts trigger a fresh retry
sub2api receives a second request opportunity for retryable upstream failures
zero-candidate provider failure no longer bypasses all retry logic
final blocked jobs are written to Project timeline
frontend does not appear stuck after backend blocked/fails the job
existing visual auto retry tests still pass
no unbounded retry loop is introduced
```

