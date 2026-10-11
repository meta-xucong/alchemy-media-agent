# PR #29 and V3 Mobile Integration Audit Follow-up

Date: 2026-10-11
Integration base: `main` at `5a33c05e3f54dbef786eb179973ec1407511b4e4`
PR #29 head reviewed: `c6d8bc2d9df52f3e404c3536581a895da262f5b7`
Local integration commit before follow-up fixes: `25a1f53bed6858e218222ccf9fa8cfaf8c09cc33`

## Scope

This follow-up combines PR #29's bounded V1/Lab/V2 history work with the local
V3 mobile project-entry repair, then records defects found by a read-only
independent review of the combined tree. It covers code correctness and
focused regression evidence; it does not certify production migration, VPS
capacity, or the entire application security posture.

## Correction model

Ordinary API reads must use already-prepared indexed state. Cold legacy JSON or
JSONL import belongs to explicit preparation and must not begin implicitly from
an item lookup, favorite mutation, reference-asset request, or deletion. Until
the relevant index is ready, the existing sanitized 503 is authoritative.

For media authorization, Lab history already treats
`alchemy_lab.veyra_user_id` as owner evidence when the top-level owner is
absent. Every durable history owner claim, including claims from duplicate
Lab records, must enter the same conflict ledger; the latest display record
cannot silently replace earlier ownership. Generic V1 media endpoints must
apply that evidence. Conflicting Lab and Job owner evidence fails closed;
canonical output ownership retains its existing precedence.

Index readiness is an operational precondition independent of caller identity.
A visibility helper that returns an empty set for an unauthenticated scope is
not a substitute for checking that the favorites index is prepared before a
destructive operation.

## Follow-up changes

- V2 item history lookup now opens the prepared-only read path.
- V2 favorite mutation, favorite-to-reference lookup, and history deletion
  require prepared indexes before writing or touching files.
- V1 global output-owner resolution includes nested Lab owner evidence and
  rejects conflicts across duplicate history rows or a different Job owner.
- Regression coverage exercises pending V2 history/favorites and nested-only
  Lab ownership, including conflicting Job metadata.

## Verification

- PR #29's original head had four successful GitHub checks before local
  integration: V1 retention, V2 queue retention, browser contracts, and
  Windows source fidelity.
- Combined frontend demand-history suite: 150 passed.
- Chromium mobile interaction probes at 390x844 passed for project detail,
  gallery routing, unknown-template read-only mode, loading-mask timing, and
  detail/home request interleaving.
- Python compilation for changed V1/V2 modules and tests passed.
- `git diff --check` and JavaScript syntax checks passed.
- Python pytest could not run in this local runtime because `pytest`, FastAPI,
  and httpx are unavailable. The new V1/V2 regression tests require execution
  in the repository's CI environment; this limitation must not be described as
  a local test pass.

## Remaining acceptance boundary

The audit found and corrected one V1/Lab cross-account media-authorization gap
and one V2 request-time cold-import gap. These focused fixes still require
their Python regressions to pass in CI. No VPS deployment or production data
migration was performed. Existing limits around long-term disk growth and
oversized individual legacy records remain as documented in the main design.
