# RB27: Unknown executor health must not masquerade as Bridge downtime

## Observed failure

On 2026-10-26, the local V2 request reached the authenticated Bridge-primary
client. `GET /bridge/v1/capabilities` returned successfully and reported
`admission.accepting_new_tasks=true`, but `codex-image` health was
`unknown/unverified`. Alchemy's preflight required a fresh `available` health
report and classified every other state as `bridge_unavailable`; it selected
the API route before `POST /bridge/v1/tasks`. The task completed through the
API, and no matching task or receipt existed in Bridge. This was a local
Alchemy pre-admission routing defect, not an Alchemy-to-Bridge connectivity
failure.

The Bridge contract defines `unknown` as absence of current execution evidence,
not evidence that the Bridge endpoint is down. Its task-creation authority is
the authenticated workspace, enabled profile and request validation, accepting
mode, and atomic queue capacity. `create_task` does not require the health
signal to be `available`. Therefore a reachable Bridge that advertises the
requested profile and accepts tasks can admit a `bridge_only` request even when
the executor health report is unknown.

## Corrected routing rule

- A valid, unexpired `available` report is positive readiness evidence.
- Profile health is execution telemetry, not task-admission authority. Once the
  authenticated capabilities response advertises the requested profile and
  `admission.accepting_new_tasks=true`, `available`, `unavailable`, `unknown`,
  missing, malformed-time, or expired health cannot select the API. Submit the
  frozen request as `bridge_only`; let the task report executor/account health.
- Existing hard-capability rejection, Bridge transport unreachability,
  explicit draining, and atomic queue-capacity rejection retain their existing
  pre-admission fallback rules. No queue snapshot is treated as a permit.
- During reference input staging, HTTP 503 `store_busy` means transient Bridge
  storage contention, not service downtime. Retry the same input key and bytes
  once after the supplied `Retry-After`. If still busy, retain durable
  `data.state=preflight` and return an explicit Bridge failure with
  `reason=bridge_store_busy`. No Bridge task/deadline exists to queue against;
  do not invent one or select API. Keep the preflight ledger for diagnosis; no
  image task was admitted. Other staging errors retain the existing fallback
  behavior.
- Once Bridge submission is attempted, an uncertain response remains owned by
  the same Bridge origin. A Bridge executor/account error after admission is
  surfaced and recovered as that same task; it must not create an API retry or
  second billable generation.

This rule does not fabricate `available`, `production_verified`, login, or real
generation evidence. The Bridge may admit the task and subsequently report an
executor/account attention state; the product must expose that state for the
same task rather than pretending it completed or generating elsewhere.

## Regression and manual acceptance

The Alchemy regressions prove that an accepting Bridge with unavailable,
unknown, expired, or malformed profile health receives a create request; API
selection remains for proven non-admission. Input staging tests prove one
  same-key/same-byte retry after `Retry-After`; if the store remains busy the
  product fails promptly, retains the preflight ledger, and makes no task/API
  call. Existing tests continue to cover network failure,
unsupported capability, drain, queue-full non-admission, lost create responses,
and same-origin recovery.

These offline tests do not prove the local CLI is logged in or can generate.
Before a new manual image attempt, confirm the running Alchemy process is the
tested revision and inspect the route/job details. Success requires a Bridge
task/attempt/receipt correlation; a returned image alone is not proof of Bridge
execution. If Bridge accepts the task but reports attention or unknown
execution, keep and reconcile that original task—do not clear its journal or
resubmit through API.

## 2026-10-29 local V3 startup environment regression

V3 job `job_5654bb6b5a` stopped before Bridge admission. Both provider attempts
reported `invalid_bridge_url`; the local control file contained the expected
`http://127.0.0.1:8798`, but the Alchemy process did not inherit
`ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK=true`. The flag was present in the
Windows user environment, while the long-lived shell that started Alchemy had
no process-scoped copy. The V3 primary journal and Bridge ledger therefore had
no unit/task for this job, and no image API fallback was called.

Keep the loopback opt-in in `src_skeleton/.env` as well as the Windows user
environment. `src_skeleton/app/config.py` loads that file during startup, so a
stale shell cannot omit the opt-in. The example environment now includes the
same explicit local setting; it only permits HTTP for loopback hosts. When
restarting from a long-lived shell, copy the user-scoped Bridge primary
variables into the new process or start a fresh shell. Before manual image
acceptance, use an authenticated, read-only capabilities probe to confirm the
running Alchemy process reaches Bridge.

The retry record also showed two repeats of the same local configuration error.
Those attempts never reached Bridge or the image API; `provider_unavailable` is
the sanitized public classification, not evidence of an upstream outage.

## Local acceptance incident: invalid control-file encoding

The next manual V2 attempt on 2026-10-26 failed before any Bridge request with
`primary_config_invalid`. The isolated local `control.json` had numeric
`schema_version: 1`; the Alchemy contract requires the string `"1"`. The
loopback HTTP endpoint also requires the process opt-in
`ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK=true`. This was a local test
configuration error, not an executor failure and not evidence that the API
fallback ran. The V2 queue record has no generation job, and the Bridge queue
remained empty.

The local control file and V2 process environment were corrected, and a
read-only `PrimarySettings.from_env("v2")` preflight returned enabled with the
expected `127.0.0.1:8798` endpoint and workspace. The restarted V2 health check
passed. An authenticated, read-only Bridge capabilities check reports
accepting mode and zero of ten task slots used, while `codex-image` remains
`attention` / not production-verified. No real generation was run as part of
this correction. A subsequent manual attempt must still be inspected for a
Bridge task and CLI attempt before claiming the route works end to end.
