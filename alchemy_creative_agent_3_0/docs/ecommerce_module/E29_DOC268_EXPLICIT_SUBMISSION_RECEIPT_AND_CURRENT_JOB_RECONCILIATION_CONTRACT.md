# E29 / Doc268 Explicit Submission Receipt And Current-Job Reconciliation Contract

Status: Phase 0 observation and deterministic red-contract authority

## 1. Scope And Observed Mismatch

This document governs only an explicit Professional E-Commerce submission and
the browser's current-job projection after that submission. It is not a
Provider, product-truth, People-identity, continuation-channel, review, or
deployment change.

Production evidence for `project_65432102a2` established the following facts:

- The active product pool contained four current uploaded product originals,
  with the locked Six-Year-Old Child Professional Character Card and no
  selected continuation outputs.
- Earlier `job_770b54df53` is terminal
  `background_generation_request_invalid`.
- Later `job_e75abeb646` is a distinct fresh command with the correct frozen
  four-original pool, one real upstream `image_edit`, and terminal
  `provider_policy_blocked`.
- A later one-click reproduction created distinct fresh
  `job_4c86f8fb7b` with the same four originals and locked child asset. It
  reached durable terminal `blocked` with
  `image_edit_invalid_request_unattributed` and zero automatic resend. The
  browser nevertheless retained historic terminal content together with an
  active preparation control.
- Both durable request records have a blank `metadata.idempotency_key`.
  `_existing_ecommerce_command()` rejects a blank key, so empty-key command
  reuse cannot explain the incident.

The observable defect is therefore a stale-current-job projection, not proven
idempotency replay: a successful create response can be replaced by a historic
project job, then a terminal receipt can coexist with an active planning or
generation presentation.

## 2. Code-Trace Observation

The Phase 0 trace identifies these current owners:

1. Project Mode appends newly created job IDs to durable `project.job_ids`.
   Empty legacy idempotency keys do not match an existing E-Commerce command.
2. Desktop `createV3Job()` writes the create response to
   `v3State.currentJob`, then calls `refreshV3CurrentProject()`.
3. Desktop refresh unconditionally calls `restoreV3LatestProjectJob()`.
   `v3LatestProjectJobId()` first reverses the project timeline and chooses
   the latest `job_generated` item before considering `project.job_ids`.
   A historic generated job can consequently overwrite an explicit receipt.
4. Desktop terminal create responses do not first transition the V3 progress
   operation to a terminal state. The old planning stage therefore remains
   visible while `renderV3Job()` renders the receipt as stopped.
5. Mobile does not select from the timeline. `generateMobileV3Job()` writes
   and polls the returned job ID, but its later
   `refreshMobileV3ProjectDetail()` assigns `currentJob` from the project
   response's last `job_ids` entry. It has the same explicit-receipt retention
   boundary even though it has a different stale-selection mechanism.

## 3. Authority And Invariants

### 3.1 Explicit command receipt

Each deliberate user confirmation of a new E-Commerce image receives the
existing server-owned command receipt: the returned durable
`ProductJobStatus.job_id`, its linked `project.job_ids` entry, and its
lifecycle status. A later deliberate retry is a new command, never a hidden
replay.

Phase 0 does not add or assume a new server replay schema. Existing evidence
only proves that blank legacy `idempotency_key` values do not match a prior
command. It does not prove a distinct transport-retry field is required, where
such a field should be accepted, or how it should be bound. Any future protocol
work must trace that narrow question before adding a field. Until then, the
browser must not automatically resend a terminal response, and empty, legacy,
malformed, or untrusted client fields must not select a terminal historical job.

The create response's exact `job_id` is the auditable receipt for this phase.
That job must be newly linked to the current project or be an already verified
authoritative in-flight response in a future, separately evidenced replay
design. Returning a different historical terminal job is a
command-reconciliation failure, not successful creation.

### 3.2 Browser current-job ownership

While an explicit command receipt is active in a browser tab, that receipt is
the sole owner of polling, terminal rendering, and progress closure. Project
refresh, timeline recovery, output recovery, and history loading may enrich
history but cannot replace the current receipt with an older same-project job.
The browser must retain the exact returned job ID and its current-project
binding. Foreign or non-member response hardening is a separate follow-up only
when code evidence identifies such a response path.

Only the job fetched by the exact receipt ID may surface a terminal provider
failure for that action. In particular, the fresh `provider_policy_blocked`
outcome of an `e75`-style job must not be replaced by an older `770`-style
`background_generation_request_invalid` failure. Conversely, a historic
terminal job remains visible only through deliberate history navigation.

Desktop and mobile must preserve this invariant using their real owners:
desktop must fence its timeline-first restore path; mobile must fence its
post-poll project-detail refresh path. A stale project snapshot that arrives
after a known receipt is a distinct test fixture from normal durable
`project.job_ids` ordering. This is not a requirement to make their
implementation identical.

### 3.3 Terminal operation closure

For a receipt whose exact job reaches `blocked`, `failed`, or `not_found`, the
browser must atomically stop the current operation: clear active busy state,
progress timer, recovery timer and recovery counter; record a terminal progress
state; and render only terminal next actions for that receipt. It must not show
preparing, generating, recovering, elapsed polling, or automatic retry copy.

Normal in-flight polling remains unchanged. Terminal closure does not submit a
new request, promote an output, hide a provider-policy failure, or disguise it
as success. A user may deliberately submit another attempt through the normal
explicit-command flow.

### 3.4 Public terminal sanitization

The exact receipt may retain a durable provider failure classification for
server-side diagnosis. Its public terminal projection must instead use one
sanitized actionable message. It must not render provider failure codes such as
`image_edit_invalid_request_unattributed`, raw exception text, job IDs, output
IDs, paths, digests, or hashes. This does not reinterpret a provider block as
success and does not retry it; it makes the terminal outcome safe to show.

## 4. Compatibility And Security

- Product originals remain product truth only. Locked People visual assets,
  selected continuation directions, and generated/review history retain the
  Doc263-267 channel authority and are neither rebuilt nor reclassified here.
- Historical records remain append-only and readable. Their terminal state is
  history, never proof that a new command was accepted.
- General and Photography do not acquire E-Commerce command-receipt rules
  through this document.
- Public UI must expose sanitized lifecycle meaning only. It must not reveal
  provider internals, durable paths, digests, hashes, job/output IDs, prompts,
  or raw exception text.

## 5. Phase Boundaries

Phase 0 adds this document and local deterministic red contracts only. It does
not modify runtime, browser scripts, storage, project records, jobs, Provider,
MCP, ImageGen, VPS, or `main`.

Phase 1 may implement the minimum browser-only receipt-retention and terminal
state-convergence boundary after audit approval. No Product API or server
change is implied by this phase unless separate code evidence proves a distinct
server defect. A guarded production acceptance is separate and must compare
the existing historical records read-only; it must not replay
`job_770b54df53` or `job_e75abeb646`.

## 6. Acceptance Matrix

1. A fresh create response returns its existing durable `job_id`, which is
   newly linked to the same project and is not a historical terminal job.
2. Empty or legacy idempotency input does not select a historical terminal job.
3. A desktop timeline containing an older `job_generated` item cannot replace
   a newer explicit receipt during create, refresh, recovery, or output sync.
4. A mobile project-detail refresh cannot replace the explicit receipt with an
   older project job.
5. A fresh exact provider-policy block is the only terminal failure shown for
   that receipt; stale `background_generation_request_invalid` history is not
   rendered as the current action.
6. Every exact terminal receipt closes busy/progress/recovery atomically; no
   request is automatically submitted and normal in-flight polling still works.
7. A terminal provider failure renders one sanitized actionable public message
   without provider code, raw exception, durable identifier, path, digest, or
   hash leakage.

The precise safe-retry correlation protocol remains a separate future
investigation, not a Phase 0 schema decision.
