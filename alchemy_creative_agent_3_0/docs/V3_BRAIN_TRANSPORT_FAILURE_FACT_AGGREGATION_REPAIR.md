# Brain transport failure fact aggregation

## Correction model

This is a shared Brain observability repair, not a scenario or image-quality
change. The attempt receipt already aggregates bounded retries, but the timeout
failure receipt previously described only the terminal attempt. A first stream
can deliver content and stall; if its retry times out before content, the two
receipts then disagree about whether content was ever observed.

`transport_failure_receipt` remains authoritative for lifecycle facts across
the logical request. The typed timeout remains authoritative for the terminal
timeout phase, duration, elapsed time and error class. These timing fields are
not total request timing. Neither source may replace the other's responsibility.

## Minimal repair and compatibility

The adapter merges the closed aggregate receipt into the timeout diagnostics,
excluding its schema and stage. Runtime and public API reuse their existing
attempt-receipt validators to preserve the additive aggregate fields. Historical
failure records without attempt counts retain their existing projection.
Malformed aggregate extensions fail closed. No exception text, URL, credentials,
prompt, provider payload or internal identifiers are copied into diagnostics.

The existing timeout policy (Doc288), execution budget, maximum of two transport
attempts, and fail-closed generation gates are unchanged. A partial stream never
authorizes an image-provider request. This repair makes failure evidence accurate;
it does not fix an upstream stream stall or guarantee successful generation.

## Acceptance matrix

- First attempt observes content, retry observes none: both receipts retain it.
- Two timeouts: two Brain calls, zero image-provider calls, no JSON completion.
- Terminal timeout timing and phase remain those of the terminal attempt.
- Runtime and public projection preserve aggregate facts and drop unsafe extras.
- Invalid attempt counts, booleans or contradictory acceptance are rejected.
- Historical single-attempt diagnostics remain readable.
- Related Brain, runtime and public API regressions, compileall and diff check.

Deployment and a controlled real V3 request are separate acceptance steps; local
simulation must never be reported as a real VPS/provider validation.

## Implementation audit and local validation

The adapter consumes the existing closed aggregate receipt; it does not add a
second aggregator. Both projection boundaries reuse their existing attempt
validators rather than copying attempt rules. Terminal timing remains unchanged.
Only diagnostic extraction/projection is modified; dispatch, retries, budgets,
quality thresholds and generation decisions are untouched.

Regression validation: 259 tests passed across transient recovery, provider
transport timeout, Doc175 availability, Doc298 boundary repair, Brain adapter,
public API minimal UX, Doc162 bounded recovery, and Doc281 product truth recovery.
The new parameterized integration test enters real `ScenarioRuntime.generate_job`
for ecommerce and general creative, mocks only the upstream stream/image outlet,
and proves exactly two Brain calls and zero image calls. It verifies aggregate
content facts, terminal timing, safe public projection and malformed extension
rejection. The serialization recovery regression also preserves first content.
`compileall` and `git diff --check` passed. No live provider was invoked locally.

VPS deployment and real image acceptance remain pending connectivity; these
local results do not establish the deployed version or real generation success.
