# RB28: Codex event bursts and bounded V2 reconciliation

## Objective and scope

Total objective: make the V2 Bridge-primary image path complete or leave the
user with an explicit, bounded failure state rather than a task displayed as
generating forever. Preserve the same Bridge task for all post-admission
recovery; never move an admitted or uncertain image to an API route or create a
second generation.

This phase corrects two cooperating defects in the pinned local candidates:

1. Bridge treated the 257th lifetime app-server notification as a protocol
failure even when the notification was ordinary command-output streaming.
2. V2 retried every nonterminal `bridge_wait` every five seconds without a
   deadline-bound terminal projection, so a permanently unknown Bridge execution
   could keep the V2 queue and public run in `generating` indefinitely.

The incident evidence makes the Bridge count cap a high-confidence likely cause,
not a directly recorded fact: Codex logs showed a burst of 454 output-delta
notifications while reading the ImageGen skill, then an interrupted turn with
no image event; the app-server logs record sends, not Bridge receive acknowledgements.
The code path and timeline align, but the exact notification that crossed
Bridge's guard cannot be proven retrospectively.

The current Windows host also has multiple Codex installations on `PATH`.
Read-only probing found `codex` resolves differently in the sanitized Bridge
probe than in an interactive PowerShell command: the generic executable name
reports `codex-cli 0.163.0-alpha.11.2` (unsupported), while the explicit npm
shim path reports the accepted `codex-cli 0.163.0` and advertises app-server
stdio. The controlled local Agent config therefore pins the exact accepted
shim path; this is a host configuration issue, not proof of the historical
V2 interruption cause.

## Authority and correction model

- Bridge's authenticated task, attempt, grant, and receipt ledger is authoritative
  for remote ownership and execution state. Its existing byte, line, JSON
  complexity, task deadline, and capability checks remain in force.
- Codex's event stream is transport evidence. Stream deltas are not image
  evidence; only an identity-bound completed native image item plus matching
  completed turn can produce a ready artifact.
- Alchemy's durable V2 task/run and frozen Bridge request remain authoritative
  for V2 queue projection and same-task recovery. `execution_unknown` is not a
  permit to regenerate or fall back.
- The V2 active queue is a projection, not the Bridge ledger. V2 polls the same
  task against the exact deadline persisted in the Bridge request, then marks
  the run failed/attention without deleting its frozen request or recovery data.

## Bounded event collection

Bridge now backpressures the app-server producer through its already bounded
message queue rather than interpreting a queue or total-notification count as
protocol failure. It discards streaming payloads, counts event categories with
fixed keys, and retains only image-item completion and turn-terminal evidence.
Existing per-line, per-session byte, JSON nesting/complexity, request, and wall
clock limits remain unchanged. A separate cap still protects the number of
captured lifecycle events.

Attempt diagnostics contain only stage, exception class, event counts, byte and
structure counts, and process exit status. They are append-only and never store
prompts, command-output payloads, credentials, or image base64. Normal completion
now accepts the two verified image item forms already supported by interrupted
reconciliation: `imageGeneration` and `Extension(kind=image_gen.generation)`;
both still require exact thread/turn binding, a single completed image, a saved
file stem matching the native image item ID, scoped original bytes, and existing
hash/dimension validation.

## Deadline-bound V2 queue recovery

`bridge_wait` continues to query the frozen request and same remote task every
120 seconds, without spending the queue's generic attempt budget. The deadline
is surfaced from the exact persisted Bridge payload (currently one day after
admission), not recomputed on each retry. At or after that deadline, V2 stores a
failed run and failed queue record, marks the error nonretryable for automatic
dispatch, and makes the run leave the active queue. The error marks
`queue_reconciliation_required`. An owner-authorized `/resume` can requeue the
same V2 queue row only when this marker is present, retaining the same job,
frozen request, Bridge origin/task/attempt, and accounting identity. It cannot
create a replacement task or use the API route. If Bridge still reports unknown,
the same bounded check can be repeated manually; the prior execution is never
automatically restarted.

If an older Bridge response lacks a parseable timezone-qualified deadline, V2
fails closed into the same manual-reconciliation state immediately. It does not
guess a fresh deadline on every poll, which could accidentally recreate an
unbounded loop.

This is a bounded automatic-polling policy, not a claim that the external Codex
process was physically stopped. No journal, task ID, receipt, origin key, cache,
or debit record may be deleted or replaced to make progress.

This deadline-bound queue policy is limited to the V2 Bridge-primary worker's existing
retry directive. It does not change API-provider retry behavior, pre-admission
fallback, V1/V3/Lab queues, product review, output storage, or billing authority.

## Regression and acceptance

Offline regressions must verify:

- 500 ordinary Codex command-output deltas before a single bound image event do
  not abort the turn; original bytes/hash survive and the event summary contains
  counts only, not delta payloads.
- Both verified native image-item forms are accepted only with exact thread,
  turn, item, scoped file, and completed-turn evidence.
- Existing app-server size/complexity/timeout and approval failure cases still
  fail closed, and a prior started attempt is not launched a second time.
- Unknown V2 Bridge work stays active through its exact Bridge deadline without
  consuming generic queue attempts; after expiry it leaves the active queue and
  owner-authorized resume reopens the same queue row/job only. The resume
  regression checks the same Bridge key/unit and a single idempotent task
  identity. Billing finalization and debit idempotency remain covered by the
  existing billing recovery regressions; this particular resume test does not
  instrument the debit client.
- Existing V2 account isolation, cancellation, ACK, cache-retirement and
  post-restart same-task recovery tests continue to pass.

Passing these tests is phase acceptance only. It does not prove real CLI account
health, real image generation, review, or Veyra billing. The following phase is
one authorized real image call using the same prior content but a distinct new
Alchemy run/Bridge task/attempt; the earlier `execution_unknown` task remains
untouched. Success must include a bridge task/attempt/receipt correlation and
original SHA/dimensions. No GitHub PR is merged and no VPS deployment is part of
this local phase.

## Controlled local real CLI result (2026-10-26)

The authorized one-image replay completed through the loopback-only Bridge
HTTP API, manual Agent `run-task`, and the stable local `codex-cli 0.163.0`
executable, using model `gpt-6.1-sol`. The request was reconstructed from the
frozen V2 record with no references and new local run/job/unit identities; the
frozen V2 run, original Bridge task, queue journal, and debit records were not
modified. Alchemy candidate HEAD was `552bc5134dbcefcb258bff7b5c5fe2d56cbf8a43`;
Bridge candidate HEAD was `16e020e82f90da7f6f739642cf2fd66d7bcd926f`.

The result proves the narrow suspected Bridge failure mode is repaired for this
request shape: the completed Codex turn emitted 577
`item/commandExecution/outputDelta` notifications, followed by one completed
`imageGeneration` item and `turn/completed`. The Agent committed one artifact,
and the Bridge created exactly one task, one attempt, and one receipt. Alchemy
retrieved the same original PNG bytes recorded by the receipt: SHA-256
`3c7235f2bd631ef1e04ff4b726a1b7b7c51cef4d2fd15f3befee36e9d1f446ee`,
2,757,134 bytes, 941x1672. Route was `bridge_primary`; there was no API
fallback. The generation prompt inherited from the frozen V2 record retained
SHA-256 `526a12502eba4d1e1ff0e58e6787fc87dd0e613773a43131fcff9aa93eb74285`;
the Bridge wire prompt additionally included the existing negative-constraint
section, as `primary_request` specifies.

The result raises confidence that the historical 256-notification guard was a
cause of the prior interrupted V2 turn: this request passed 577 ordinary output
deltas before completion. It still cannot prove which exact historical event
crossed the old guard because the old Codex logs were sender-side only.

This was not a complete Alchemy V2 product run: the local Hatchet/Docker stack
was unavailable, so this controlled call did not exercise V2 queue scheduling,
Claude orchestration, product review, output registration, or Veyra settlement.
No Veyra debit occurred in this direct Bridge acceptance; Codex account usage
may be billable under its own account and its exact charge was not available.
The original unknown V2 task remains preserved for reconciliation. The raw
one-time local evidence and original image are retained under the candidate's
ignored `.runtime/real-single-acceptance-20261026/` directory.
