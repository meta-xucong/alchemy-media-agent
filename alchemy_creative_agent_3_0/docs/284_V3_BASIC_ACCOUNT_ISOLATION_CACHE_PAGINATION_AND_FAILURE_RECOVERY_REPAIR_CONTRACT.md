# Doc284 - V3 Basic Account Isolation, Cache, Pagination, And Failure Recovery Repair Contract

Status: active local repair contract. This document extends the current V3
foundation and does not replace the existing Brain, Provider, review, V2,
Sub2API, or deployment authorities.

## 1. Objective

Make the ordinary V3 path usable and safe under the authenticated Veyra
runtime with the smallest complete repair:

1. A Veyra account can only read or mutate its own V3 projects, Jobs, outputs,
   and uploaded source files.
2. Refresh, account switching, request failure, deletion, and reopen do not
   show stale or cross-account browser data.
3. Project history can actually load older projects instead of only revealing
   the first bounded page.
4. Project listing remains responsive as history grows.
5. A rejected background submission cannot leave a durable Job stuck in a
   misleading generating state.
6. The existing Brain-first generation, source evidence, ProductTruth,
   output-binding, review, retry, and disclosure authorities remain intact.

The target is basic V3 usability and boundary correctness. This is not a new
creative module, provider, prompt recipe, or visual-quality system.

## 2. Scope And Non-Goals

In scope:

- V3 HTTP ownership checks and server-owned upload ownership.
- V3 desktop and H5 cache namespace and failure-state behavior.
- Cursor or equivalent stable pagination for the V3 project list.
- Bounded project summary projection and request-local reuse of expensive
  output state.
- Background executor submission rollback.
- Regression tests, static checks, and a read-only audit receipt.

Out of scope:

- V1, V2, Sub2API, MCP, ImageGen, VPS, deployment, or provider configuration.
- Brain prompt interpretation, visual realism, scene logic, or image review
  thresholds.
- Regular expressions, filename matching, keyword matching, browser metadata,
  or client-supplied ownership as a decision authority.
- Automatically deleting or rewriting historical business records.

## 3. Authority Model

| Decision | Authority | Supporting evidence | Forbidden shortcut |
| --- | --- | --- | --- |
| Account identity | authenticated Veyra request on the server | session/token resolution | browser cache, request metadata, UUID secrecy |
| Project/Job/output access | server-owned owner binding plus project/Job relation | persisted record | direct ID lookup alone |
| Upload access | server-owned upload owner binding | persisted upload record | client metadata or asset ID secrecy |
| Browser display | current successful server response | short-lived account-scoped cache | stale cache after auth/API failure |
| History continuation | server cursor and stable ordering | `next_cursor` | increasing a local render limit |
| Creative plan and image quality | existing Brain/Provider/review chain | existing typed receipts | this repair document |

Authenticated V3 requests must not treat an absent owner as public. Existing
ownerless legacy records remain readable only in an explicitly unauthenticated
local mode; under Veyra authentication they are quarantined from normal
account views until a server-side migration assigns ownership. No historical
output becomes a source reference through this repair.

## 4. Single Terminal Behavior For Access Failures

The public boundary must return one safe not-visible result for a missing,
foreign, or ownerless authenticated record. It must not reveal whether the
identifier exists. The operation must have no planning, generation, selection,
export, upload mutation, or browser cache side effect.

Project-scoped endpoints retain their current project check and must also
validate that the supplied Job belongs to that project. Direct Job endpoints
must apply the same owner check before status, export, generation, or selection.

## 5. Chapter Plan

### Chapter 1 - Server Ownership Boundary

Repair the direct V3 Job routes and raw upload routes at the HTTP/service
boundary. Inject the authenticated user only from the server context. Persist
the upload owner in a typed server-owned field or equivalent protected record
fact; client metadata must never overwrite it. Reject foreign and ownerless
records when Veyra auth is enabled. Keep project-scoped relation validation.

Required regressions:

- Two authenticated users cannot read, export, download, generate, select, or
  overwrite each other's Jobs.
- Two authenticated users cannot read, complete, or read content from each
  other's uploads.
- Client-provided owner metadata cannot change ownership.
- Ownerless legacy records remain available only in local unauthenticated
  compatibility tests and are hidden under authenticated requests.
- Existing same-account and auth-disabled tests remain green.

### Chapter 2 - Browser Cache And Output State

Keep the server response authoritative. Namespace the optional desktop and H5
quick-open cache by the verified account identity, clear the V3 cache on
logout/account change or authenticated failure, and render an empty/loading
state rather than another account's local data. A failed project-output request
must not be marked as a successful empty result. The existing first visible
thumbnail wait remains, but it must not block on unrelated history.

Required regressions:

- Account A's cache is never read for Account B.
- A 401/403/bridge failure does not render cached projects or outputs.
- A deleted project cannot return through a failed-refresh fallback.
- A failed output request remains retryable and does not claim that the
  project has zero images.
- Desktop and H5 keep the same behavior.

### Chapter 3 - Real Project Pagination

Add one stable server pagination contract using a bounded page size and an
opaque cursor based on server ordering. The ordering must be deterministic
with a tie-breaker and must not use client render state. The response returns
`has_more` and `next_cursor` (or an equivalent existing contract). Desktop and
H5 append and de-duplicate server pages when the user selects “加载更多”.

Required regressions:

- More than one page returns all projects exactly once.
- New updates between page requests do not duplicate or silently reorder the
  already loaded page.
- Deletion and owner filtering are applied on every page.
- A malformed/expired cursor fails safely without exposing records.
- Existing first-page response compatibility remains intact.

### Chapter 4 - List Cost And Summary Projection

Keep detail-level output reconciliation on project open. The list endpoint
must use a bounded summary path and avoid re-reading the same Job/output state
multiple times for one request. Reuse persisted summary facts or a single
request-local batch snapshot; do not add a second business-state cache or
duplicate delivery authority. The full output projection remains unchanged.

Required regressions:

- Project list does not invoke detail-only output projection per project.
- Summary counts and first thumbnails remain correct after generation,
  deletion, retry, and refresh.
- A large synthetic history completes within the agreed local budget without
  changing output truth.
- Project detail still returns the same strict delivery/review projection.

### Chapter 5 - Background Submission Failure

If executor submission fails after a Job is marked generating, cancel any
watchdog, release the in-memory claim, and persist one terminal failure
projection with a stable public reason. Do not fabricate an output or retry.
Startup recovery remains a secondary safety net, not the normal rollback.

Required regressions:

- A rejected executor leaves no stuck generating Job or orphaned claim.
- A successful worker still follows the current generation/review path.
- Duplicate concurrent submissions remain idempotent.
- Refresh and fresh-service readback show the same terminal state.

### Chapter 6 - Contract Reconciliation And Final Audit

The existing `post_generation_review` field is part of the public Basic V3
status contract. General source activation must not remove it merely because
the source receipt is private. The implementation reuses the existing
`_public_post_generation_review`, `_public_visual_auto_retry_summary`, and
`_public_final_delivery_projection` functions; it does not copy the private
review package, source receipt, provider payload, prompt, path, or raw issue
evidence into the public status. The existing General review regression and
the Product API public-projection redaction regression are the Chapter 6
compatibility gates.

The General safe status remains a source-safe boundary: it exposes only the
allowlisted review/retry/delivery summaries and the sanitized activation state.
It does not make a second delivery decision, re-run review, or change source
selection authority.

Run the focused security/cache/pagination/background suites, the existing V3
foundation and adjacent suites, Python/JavaScript static checks, and a
read-only diff/state audit. Do not commit, push, deploy, or create a real
provider generation until all chapters pass.

## 6. Acceptance Matrix

| Gate | Pass condition |
| --- | --- |
| A. Ownership | Cross-account Job/upload access is denied; same-account behavior passes |
| B. Legacy boundary | Ownerless authenticated records are hidden; local compatibility remains explicit |
| C. Cache | No cross-account/stale fallback after auth or API failure |
| D. Pagination | All pages load once, securely, with stable cursor behavior |
| E. Performance | List uses bounded summary work; detail projection is unchanged |
| F. Failure recovery | Executor rejection produces one terminal failure and no claim leak |
| G. Contract | Existing public status and review projections are explicitly reconciled |
| H. Regression | Focused plus adjacent suites and static checks pass |

## 7. Evidence Requirements

Record for each chapter:

- commit/base and tracked status;
- correction model and owning layer;
- exact tests and results;
- changed-file list and diff check;
- confirmation that no V1/V2/Sub2API/Brain/provider/VPS path was changed;
- no secrets, raw provider bodies, prompts, source paths, or private account
  data in the evidence.

The final acceptance statement must distinguish production-code fixes,
test-fixture corrections, compatibility decisions, and remaining risks.
