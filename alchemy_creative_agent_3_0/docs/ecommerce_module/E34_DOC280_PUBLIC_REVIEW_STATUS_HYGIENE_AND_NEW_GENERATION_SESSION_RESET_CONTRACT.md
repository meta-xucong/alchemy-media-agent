# E34 / Doc280 Public Review-Status Hygiene And New-Generation Session Reset Contract

## 1. Purpose

Doc280 closes two related public-state defects in V3 Professional E-Commerce:

1. Central Brain quality/retry audit strings can leak through a public Product
   API warning or browser surface even though they are neither a second Provider
   failure nor an actionable customer error.
2. A newly explicit Generate command can inherit stale terminal/recovery state
   from an earlier command while its own planning or generation progress starts.

This is an E-Commerce specialized consumer contract over shared V3 public
projection hygiene. It does not change durable audit evidence, Central Brain
retry policy, Provider routing, Product Truth admission, People identity,
Doc265 continuation selection, or the final Doc269 physical plan.

## 2. Authority And Isolation

1. Internal Brain/retry/Provider diagnostics remain durable private audit
   evidence. Public Product API, Project Mode, desktop, and H5 projections may
   never forward raw asset IDs, retry-budget counters, package/reject wording,
   file paths, hashes, upstream trace tokens, or Provider diagnostic text.
2. Public-safe text is selected server-side. A frontend must not parse warning
   text to decide whether a generated image is final, review-only, retryable,
   or actionable.
3. Canonical final-delivery, review package, and persisted output records own
   delivery/review truth. Browser `review_disposition`, warning, output,
   receipt, session, or operation fields are untrusted and cannot manufacture
   a review state.
4. E-Commerce consumes the specialized `review_disposition` below. General and
   Photography receive only the shared raw-warning redaction guard; they do
   not receive E-Commerce states, actions, session fields, or reference rules.
5. Docs263/264 remain product-original admission authority. Doc93/Doc269
   retain People identity and final physical-plan authority. Doc265 remains
   the only explicit selected-continuation authority. Docs276/277/278/279
   retain their existing terminal-operation precedence.

## 3. Shared Public Warning Hygiene

The following internal examples are prohibited from every public warning,
history label, job/project metadata projection, notice, status string, and
desktop/H5 DOM:

```text
asset <private-id> exhausted refine budget
asset <private-id> packaged with reject recommendation
```

The same prohibition covers an asset/output/reference ID joined with
`refine`, `retry`, `budget`, `package`, `reject`, `trace`, raw Provider error
detail, path, hash, or upstream token. This is a server projection rule, not
a frontend keyword filter. The original durable record remains readable only
through the internal audit boundary.

The public projection may emit a short stable explanation only when the
canonical final-delivery/review result requires it. A raw warning cannot
create or alter the explanation.

## 4. Typed E-Commerce Review Disposition

For an E-Commerce Job with canonical result/review records, Product API owns
one public-safe immutable projection:

```json
{
  "schema_version": "doc280_ecommerce_review_disposition_v1",
  "state": "final_delivery_available",
  "terminal": true,
  "pending": false,
  "next_actions": []
}
```

The exact allowed states are:

| State | Required canonical fact | Public effect |
| --- | --- | --- |
| `final_delivery_available` | verified final-delivery output(s) | no review/failure current operation; homepage may show only final delivery |
| `review_withheld_manual_confirmation` | pixels retained and final delivery requires manual confirmation | terminal; one `review_generation_history` action |
| `review_withheld_review_failure` | pixels retained but automatic review cannot certify final delivery | terminal; one `review_generation_history` action |
| `no_delivery_terminal` | no delivered pixels and an existing terminal Provider/input closure | taxonomy only: preserve the exact existing Doc271/264/265/277/278/279 remediation, action, and wording; never replace it with a generic `continue` route |
| `history_only` | superseded/process-only/review history is not the newest current result | never becomes a current review/failure operation |

`review_disposition` is rederived on every server response from the exact
current Job/result/output binding. A review package alone is insufficient:
each claimed resolution/inspection must bind one persisted readable output
record for that same Job, output ID, asset ID, and final-delivery fact. It is
derived only from those aligned final-delivery, review package, and persisted
output records. It is never inferred from warning text, a browser field, a
candidate label, or an unverified generated asset. An extra, forged,
malformed, foreign, missing, or mismatched receipt/output reference fails
closed to no review disposition; the server must not fall back to warning
text. Its public shape contains no output/source/reference IDs, hashes, paths,
receipt digests, retry counters, Provider evidence, or raw review rationale.

For retained review-only pixels:

- final homepage thumbnails and normal final-result lists contain only
  `final_delivery` media;
- review-only media is visible only in the E-Commerce generated/review history
  group;
- the output remains append-only and cannot become a continuation reference
  without the existing explicit Doc265 user selection.

Doc276 `review_withheld_face_integrity` remains the shared withheld-review
owner. An E-Commerce output subject to that gate has one compatible public
review disposition and one `review_generation_history` action, never a second
parallel Doc280 current operation. Historical/process records remain readable
as history but cannot replace a newer accepted command's current disposition;
in particular, an older face-integrity-withheld result cannot supply a
disposition to a newer planned or no-output Job.

## 5. E-Commerce Current-Operation Precedence

Project Mode must project at most one current E-Commerce terminal operation.
A review disposition with retained pixels may project only its exact
`review_generation_history` action. It must not coexist with a stale
`failed_no_delivery`, `planning_failed`, `needs_input`, stopped, or preparing
operation from an earlier command.

When Project Mode accepts a newer explicit command, its server-owned planning
operation/job identity supersedes a prior terminal review projection in the
public read model. The older Job, review package, and operation remain
append-only history. A later read must never delete or rewrite them merely to
clear the current surface.

No-output Doc271, Doc278, Doc279, Doc264, Doc277, and Doc276 operations retain
their documented precedence and wording. Doc280 neither creates a retry nor
reclassifies an opaque or policy failure.

## 6. New Explicit Generate Session Ownership

Before upload or POST, desktop and H5 create a new local E-Commerce generation
session for the current project. The session has a monotonically advancing
opaque local epoch and is not browser/API authority. The shell may keep this
behind private helpers such as `v3StartEcommerceGenerationSession` /
`v3EcommerceGenerationSessionOwns` and their H5 equivalents, but the ownership
check is mandatory on the real submit and recovery paths. Starting it must
atomically:

- retire the preceding session's recovery/poll ownership;
- clear local busy, progress, notices, terminal receipt, current Job/result,
  and stale current-operation presentation for that project;
- preserve project assets, output/review history, and server history;
- bind subsequent local rendering only to the exact server planning
  operation/job identity returned for this session.

Every awaited upload, POST, project refresh, job poll, recovery delay, and
terminal callback verifies session ownership after the await and before a
write. A late prior-session response may be discarded but must not set a
notice, progress state, Job, result, review action, or current operation.
The Phase 0 browser contract drives an actual delayed prior recovery/POST
response after a new session has started: it must not overwrite the new
`currentJob`, progress stage/detail, action buttons, terminal presentation, or
notice, while the current response is allowed to render normally.

The server remains authoritative: it records accepted latest command/current
operation identity and masks a prior terminal public operation only when that
newer command is accepted. The browser cannot invent a session identity,
receipt, current operation, review disposition, selected output, or Job.

Desktop and H5 terminal settlement must clear busy/loading, progress detail,
progress/recovery timers, and stale submission receipt before rendering one
server-owned terminal action. A prior stopped/review/needs-input state may
never appear beside a new preparing/generating state.

## 7. Phase 0 Contract Tests

Phase 0 uses only deterministic local Product/Project stores, fake result
records, and Playwright browser fixtures. It proves:

1. raw refine/reject diagnostics remain internal but are absent from public
   Job/Project and desktop/H5 surfaces;
2. the typed review disposition is exact for final delivery, manual review,
   review failure with retained pixels, no-output terminal closure, and
   history-only/process records;
3. forged browser review/warning/disposition fields cannot create a review
   state;
4. homepage/final results exclude review-only media while generated/review
   history retains it;
5. a newer accepted command masks an older terminal review operation without
   deleting history;
6. desktop/H5 begin an owned new E-Commerce session before POST, synchronously
   retire old review/failed/needs-input notices, actions, recovery, and
   progress state, and ignore a delayed prior-session recovery/POST response
   after the current session is active;
7. Doc276 face-integrity withholding remains one compatible review history
   action, and an older withheld result cannot project onto a newer planned or
   no-output Job.

Phase 1 may add the narrow shared Product API warning sanitizer, the
E-Commerce disposition projector, Project Mode current-operation ordering, and
desktop/H5 session ownership. It must not alter retry count, Provider routing,
prompt truth, source/reference binding, General behavior, or Photography
behavior.
