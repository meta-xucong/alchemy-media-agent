# V2 Bridge result polling

## Correction model

The intended behavior is to discover an existing Bridge result promptly while
preserving the exact generation, queue, receipt, cancellation, and billing
identities. A successful frontend run on 2026-11-09 took 147.328 seconds;
its node completed about 28 seconds before product completion. Code applies a
120-second reconciliation delay to every retryable `bridge_wait`, including
ordinary queued/running work. The observed timing is consistent with that
policy; the available records do not attribute every trailing second to it.

This is Auxiliary scheduling in the V2 queue adapter. Bridge remains the
authority for task state; the queue controls when to read that state again.
Image prompts, Claude stages, image settings, review, final output publication,
frontend rendering, and the 300-second upstream stream-idle tolerance retain
their existing authority.

## Minimal correction

- Query the same task after 10 seconds when a successful observation reports
  `queued`, `running`, or `uploading`.
- Keep the existing 120-second reconciliation delay for unknown/submission-
  unknown states, network/read failures, action-required states, and billing
  finalization. Terminal/deadline handling remains authoritative.
- The shared transport currently returns a cached state when a status read
  fails. Add a default-false, per-call `poll_failed` flag
  to `PrimaryResult` so V2 cannot mistake stale `running` for a healthy read.
  The flag is not written into the Bridge ledger, does not replace task state,
  and resets on the next successful observation. V1/LAB/V3 do not consume it.
  `artifacts_ready` without downloaded bytes already remains on the conservative
  interval; receipt/artifact download behavior needs no change.
- Carry that observation through V2's existing `BridgeWait` error detail to
  the existing queue retry directive. Reuse `not_before` and
  `consume_attempt=False`; add no polling loop, worker sleep, retry counter,
  second generation, or new task.

The optional trailing result field preserves existing constructors and other
product adapters. Deployment replaces application workers together; old queued
records without the flag remain readable. In-flight `not_before` timestamps
are not rewritten: an already scheduled 120-second wait keeps that one delay.

## Acceptance

Use offline regression tests to demonstrate normal-state scheduling, failed
reads retaining conservative scheduling, failure-marker reset, existing queue
identity/frozen-prompt reuse, one generated output and one settlement, deadline
and cancellation protection. Compare old/new discovery schedules against the
same deterministic task-completion times; this is a scheduling comparison,
not a live image quality or end-to-end speed benchmark.

Run the relevant transport, V2 Bridge/queue/cancellation, and shared-adapter
regressions; independent read-only audit precedes integration/deployment.
Deploy via existing guarded candidate/preflight/activation workflows and check
the existing output delivery records afterward. Real frontend generation is
the subsequent production latency observation, not an exploratory debugger.

## Verification result (2026-11-09)

343 relevant cases passed: 81 neutral transport cases, 110 V2 Bridge/cache/
durable-queue/cancellation cases, two schedule comparisons, and 150 V1/LAB/V3
adapter cases. One Windows-inapplicable filename case was skipped. An existing
loopback configuration test initially inherited the operator's Bridge URL;
clearing that child-process environment override made the case pass without
changing the production endpoint guard.

The comparison uses the existing durable queue and frozen-generation adapter:
for a task ready at 94 seconds, the old policy discovers it at 120 seconds and
the new policy at 100 seconds. Both retain one queue/task identity, identical
image bytes, and one ACK. More status reads are expected (2 versus 11 in this
fixture); generation and Claude planning are not repeated. Independent
read-only implementation audit and scope review passed before integration.
