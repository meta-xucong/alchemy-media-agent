# RB29: V3 API Fallback Unknown Outcome Diagnostics

## Objective

Classify and expose a safe diagnosis when V3 has selected the API route and the
API execution outcome is unknown. Preserve the terminal, no-automatic-retry
behavior and the existing route-selection policy.

## Confirmed observation and root cause

In `bridge_primary.generate`, `bridge_api_execution_unknown` is raised only
after `PrimaryTransport.resolve` returns `route == "api"`, when the durable API
claim cannot be acquired or the API provider call raises. The code therefore
describes an API fallback outcome, not a Render Bridge execution failure. The
old message also said no second provider was called even though the API branch
had been entered.

The transport result already carries the selected route and reason, including
safe capability rejection data when applicable. The provider retry audit and
V3 public projection previously omitted those fields. Current records therefore
cannot recover the route reason for a historical `bridge_api_execution_unknown`
failure. A queue-capacity reproduction confirms that `bridge_queue_capacity` is
available for a new failure record; it does not establish the exact subreason
for an older failure.

## Correction model

- API claim contention or an API callback exception whose submission point
  cannot be established is reported as `api_execution_unknown` from provider
  `api`, with an explicit unknown-outcome message and the existing terminal
  retry owner/outcome. Cancellation during the callback is also terminalized
  as unknown; the durable API claim prevents replay.
- An API response with a missing or unusable image payload is reported as
  `api_output_contract_invalid` from provider `api`; its outcome remains
  `accepted_unknown`, and the durable claim prevents a second API call.
- Bridge-owned wait, submission-unknown, and execution-unknown failures keep
  their Bridge code/provider and state-recovery behavior. API is not called.
- Provider retry audit and V3 public projection carry only a validated route,
  route reason, capability rejection `code`/`field`, and API exception class.
  They never carry prompts, credentials, local paths, image bytes, or raw API
  exception text.
- Route selection semantics are unchanged. Historical fallback subreasons are
  not inferred or reconstructed.

## Scope and non-goals

This correction is limited to V3 error classification, retry audit, safe public
projection/warning, focused regressions, and this document. It does not change
Bridge/API routing policy, retry eligibility, the durable API claim, provider
capabilities, or historical records. It does not run real generation.

## Regression coverage

Focused automated coverage verifies that queue-capacity pre-admission fallback
followed by API timeout produces `api_execution_unknown`, exposes
`route=api` and `reason=bridge_queue_capacity`, remains terminal, and does not
invoke API a second time. It also verifies that the public projection and
warning show the safe route reason, and that Bridge execution-unknown remains
Bridge-owned without an API invocation.

The focused regressions were run with the repository's bundled Python and
pytest after granting local test execution permission because Windows asyncio
requires a local socketpair that the sandbox blocks. No external API or real
image generation was used:

```powershell
pytest alchemy_creative_agent_3_0/tests/test_v3_bridge_primary_transport.py -q -k api_fallback
```

Focused API-fallback result: 5 passed. An earlier pre-release run of the full
file had 74 passed and 1 failed in
`test_disabled_still_resumes_existing_bridge`: that assertion expected
`bridge_execution_unknown`, while the wait-budget path correctly returned
`bridge_wait_budget_exhausted`. The test was corrected to make the production
wait budget zero for this recovery assertion and to expect the stable
`bridge_wait_budget_exhausted` classification. On the release candidate, the
full file then passed: 75 passed, 10 existing FastAPI deprecation warnings.
This test-only correction leaves the production wait budget unchanged.
The API malformed-output regression verifies the first response is classified
as API-owned, the durable claim blocks a second invocation, its failure code
survives V3 public projection, and no duplicate API call occurs. The callback
cancellation regression verifies a terminal unknown outcome and no replay.
`git diff --check` and Python syntax compilation passed.

## Manual route-correlation acceptance

For a newly observed unknown outcome, correlate the V3 job's provider retry
attempt with its `route`, `route_reason`, and `api_error_type`. Confirm that the
route reason agrees with the durable Render Bridge transport record for the
same request unit. Treat the structured route reason as the source of diagnosis;
do not infer it from prompt text or raw exception messages. Existing records
without the structured fields remain historically unattributed.
