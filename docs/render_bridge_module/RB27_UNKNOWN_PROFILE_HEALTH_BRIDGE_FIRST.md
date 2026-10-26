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
- An explicit `unavailable` profile report remains a known pre-admission
  rejection and may select the existing API fallback.
- Missing, `unknown`, malformed-time, or expired health is indeterminate. It is
  not a non-admission proof and must not silently select the API. When the
  authenticated Bridge capability response advertises the requested profile
  and says it is accepting tasks, submit the frozen request as `bridge_only`.
- Existing hard-capability rejection, Bridge transport unreachability,
  explicit draining, and atomic queue-capacity rejection retain their existing
  pre-admission fallback rules. No queue snapshot is treated as a permit.
- Once Bridge submission is attempted, an uncertain response remains owned by
  the same Bridge origin. A Bridge executor/account error after admission is
  surfaced and recovered as that same task; it must not create an API retry or
  second billable generation.

This rule does not fabricate `available`, `production_verified`, login, or real
generation evidence. The Bridge may admit the task and subsequently report an
executor/account attention state; the product must expose that state for the
same task rather than pretending it completed or generating elsewhere.

## Regression and manual acceptance

The Alchemy regression tests prove that an accepting Bridge with unknown or
expired profile health receives one create request, while an explicitly
unavailable profile still selects API before Bridge submission. Existing tests
continue to cover network failure, unsupported capability, drain, queue-full
non-admission, lost create responses, and same-origin recovery.

These offline tests do not prove the local CLI is logged in or can generate.
Before a new manual image attempt, confirm the running Alchemy process is the
tested revision and inspect the route/job details. Success requires a Bridge
task/attempt/receipt correlation; a returned image alone is not proof of Bridge
execution. If Bridge accepts the task but reports attention or unknown
execution, keep and reconcile that original task—do not clear its journal or
resubmit through API.

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
