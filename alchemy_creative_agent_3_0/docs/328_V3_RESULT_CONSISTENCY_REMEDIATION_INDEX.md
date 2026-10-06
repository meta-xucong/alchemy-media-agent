# Doc328 — V3 Result Consistency Remediation Pack: Index And Scope Freeze

Status: **IMPLEMENTATION DOC SET COMPLETE; Chapters 1–6 local acceptance passed for the tested worktree snapshot.** The code remains uncommitted and undeployed; the live image receipt is in Doc336 and does not replace the synthetic cross-step regression coverage.

Baseline: repository `main` at `1a66b245ce058062eece2c1519e6a10eaf3e55d1` (2026-10-03). At document preparation start, `HEAD` and local `origin/main` matched this commit. All source observations in this pack are pinned to that revision; line numbers are navigational and symbols/contracts are authoritative.

## 1. Objective

Prepare a bounded, test-first implementation package for seven confirmed V3 defects concerning the consistency of per-image review, best-result choice, user selection, Brand Memory, public status, Project output, export, desktop completion messaging, and Brain request construction.

The product objective is one coherent answer to “which exact images are approved for formal delivery?” All formal delivery projections must derive from the existing per-output review evidence and delivery authority. This pack does not introduce a new state framework.

## 2. Scope and non-goals

In scope:

1. Preserve the review evidence belonging to each retry candidate and expose the selected best candidates as final delivery.
2. Enforce per-image delivery eligibility at direct Product API selection and Brand Memory filtering.
3. Align V3 desktop terminal messaging, OpenAI Brain URL resolution, Anthropic version headers, and V3 E-Commerce export semantics with existing authority.
4. Add deterministic regressions before changing the owning code paths, then verify the integrated public surfaces.

Out of scope:

- V1 or V2 product behavior, storage, APIs, generation, or provider configuration.
- Redesigning the V3 review schema, adding a parallel state machine, changing quality thresholds, or widening retry budgets.
- Automatically deleting or rewriting historical Brand Memory, generated outputs, reviews, or export records.
- Real provider calls, real image generation, deployment, activation, or claiming production readiness during this documentation phase.
- Changing scenario deliverable maps or moving E-Commerce packaging into the shared Visual Capability Cluster.

## 3. Frozen operating contract

| Axis | Frozen value | Reason |
|---|---|---|
| Design ambiguity | D0 | The correction model follows existing per-output review and delivery contracts; no unresolved product choice is needed to prepare the plan. |
| Implementation difficulty | I2 | The primary defect spans review history, winner preference, Product API, Project projection, and export. A focused local fix may leave downstream surfaces inconsistent. |
| Audit risk | A1 | Acceptance depends on cross-module invariants and public read-only projections. The Brand Memory write is durable, so its no-write and exact-filter cases are mandatory. |
| Writer | One writer at a time | Future implementation uses a dedicated feature branch/worktree; no parallel edits to shared contracts. |
| Current stage | Documentation preparation | No implementation, tests, provider calls, deployment, commit, or push is included here. |

## 4. Finding ledger and frozen boundaries

| ID | Confirmed defect | Owning V3 boundary | Required correction |
|---|---|---|---|
| R1 | A better reviewed image from an earlier retry can disappear from formal delivery when the latest review package becomes the projection basis. | Product API review merge, best-result preference, final-delivery projection, Project output list, export. | Bind each candidate to its own review evidence; derive winners and every delivery view from that exact evidence. |
| R2 | Selecting one image can retain unselected candidate references in direct Product API Brand Memory updates; empty filters have all-items fallbacks. | Direct Product API selection → Brand Memory service. | Intersect selected candidate/source-asset identity with proposed accepted assets and reference records; empty match means skip, never restore all. |
| R3 | A passing image can open the task-level gate and allow an unqualified sibling or unknown selection through the direct selection endpoint. | Direct Product API selection. | Validate explicit selections against exact per-output eligibility before persistence; default to eligible outputs only; reject zero/unknown matches. Preserve non-delivery candidate browsing as a separate meaning. |
| R4 | Desktop completion can report `failed` or `not_found` with no output as completed/success. | V3 desktop polling and completion projection in shared shell. | Reuse one terminal/delivery classification; separate failed, not-found, partial delivery, held review, and complete delivery. |
| R5 | Default OpenAI Brain Chat streaming can construct `/v1/chat/completions` without a host when base URL is absent. | V3 LLM Brain OpenAI streaming adapter and availability check. | Resolve one canonical base URL for both configuration/availability and actual request; retain explicit gateway URLs. |
| R6 | V3 Brain’s Anthropic Messages request omits `anthropic-version`. | V3 LLM Brain Anthropic-compatible request builder. | Add the existing repository-supported version header and assert the final outbound request with mocked transport. |
| R7 | E-Commerce export manifests can list failed outputs as `ready_for_manual_review` and package state `metadata_ready`, losing the actual review outcome. | V3 Product API E-Commerce export manifest. | Formal delivery export includes eligible outputs only; if review history remains exportable, preserve and label its non-delivery purpose and real per-image review state. |

The findings are confirmed at the pinned source revision. Their suggested P2 priority is a planning input, not an independently measured frequency or severity rating. None is claimed to affect all routes.

## 5. Document set

| Document | Purpose |
|---|---|
| Doc328 (this file) | Index, fixed baseline, scope, D/I/A, authority map, and stage status. |
| [Doc329](329_V3_PER_OUTPUT_DELIVERY_AUTHORITY_AND_CORRECTION_MODEL.md) | Product correction model and per-output authority contract. |
| [Doc330](330_V3_RESULT_CONSISTENCY_IMPLEMENTATION_PLAN.md) | Ordered implementation phases, ownership, boundaries, dependencies, and handoff sequencing. |
| [Doc331](331_V3_RESULT_CONSISTENCY_REGRESSION_TEST_PLAN.md) | Deterministic regression scenarios and focused test manifest. |
| [Doc332](332_V3_RESULT_CONSISTENCY_ACCEPTANCE_CHECKLIST.md) | Phase gates, integrated acceptance, evidence, and release checklist. |
| [Doc333](333_V3_RESULT_CONSISTENCY_CHANGE_IMPACT_AND_DATA_SAFETY.md) | Compatibility, durable-data, historical Brand Memory, rollback, and prohibited side effects. |
| [Doc334](334_V3_RESULT_CONSISTENCY_IMPLEMENTATION_HANDOFF_TASKSPEC.md) | Frozen coding TaskSpec and implementation-ready traceability ledger. |
| [Doc335](335_V3_RESULT_CONSISTENCY_CHAPTERED_CODE_OPTIMIZATION_PLAN.md) | Sequential implementation plan and chapter progress ledger; real-image acceptance is Chapter 6. |
| [Doc336](336_V3_RESULT_CONSISTENCY_REAL_IMAGE_ACCEPTANCE_PLAN_AND_RECEIPT.md) | User-authorized live-image acceptance boundary, read-only preflight receipt, and resume criteria. |

## 6. Authority map

The implementation must reuse these current authorities where applicable:

- Repo `AGENTS.md`: theory-first correction; code-first workflow audit; Core/Enhanced/Auxiliary layering; one main writer; preserve V1/V2 boundaries; phases are not total acceptance.
- V3 Doc321, `321_V3_OUTPUT_SCOPED_REVIEW_AUTHORITY.md`: output-scoped review; exact eligible output IDs; one passing output survives a held sibling; malformed or incomplete evidence fails closed.
- V3 Docs 95/96: compare reviewed attempts and keep the best eligible output; retries remain append-only; do not let a newer attempt automatically win.
- V3 Doc280 / Ecommerce E34: public review disposition and Project review history are derived from canonical job/review/output facts; historical pixels are not formal delivery.
- V3 Doc276: applicable face-integrity certification is part of per-output eligibility when required.
- V3 Doc48/50: LLM Brain adapter owns request transport and checkpoint reasoning; it does not own image review or output curation.
- V3 Brand Memory contracts and Project-to-Brand confirmation spec: persistent brand updates must reflect user-approved selection; Project Mode’s explicit confirmation boundary remains intact.

## 7. Cross-surface invariant

For a job with a canonical review/delivery gate, define `W` as the best eligible output IDs from existing exact per-output review evidence, receipt closure, required certifications, and retry comparison. If the user explicitly selects a subset, define `U` as those selected IDs and require `U ⊆ W`. Then:

```text
eligible image and its bound evidence
  -> best-result set W (per role/output, across append-only attempts)
  -> optional explicit formal selection U, where U is a subset of W
  -> optional Brand Memory update (selected asset/candidate associations in U)
  -> Product / Project / export projections state whether they expose W or U
```

These are projections of the same facts, not separately authored status decisions. In the automatic-delivery case (no explicit user subset), status, ordinary Project final outputs, and formal export must agree on `W`. When an explicit selection exists, no surface may claim an ID outside `U` is user-selected; a surface may report the broader `W` only when it labels that set as eligibility/available delivery rather than the user’s selected subset. Review history may retain rejected, superseded, unreviewed, or manually held pixels for inspection. It must not present them as formal delivery. The desktop may report partial delivery only when the server-projected eligible set contains deliverable images and the job contract permits partial results.

## 8. Stage status and acceptance boundary

This packet is complete when the seven documents pass independent read-only audit for scope, source mapping, testability, and consistency with existing V3 authorities. That is **documentation phase acceptance only**.

Documentation phase result: **PASS** — the independent read-only A1 review found no blocking conflict after the ID-domain and winner/subset clarifications. No source code or tests were changed or run as part of this phase.

Total objective remains open until the implementation phase adds failing regressions first, applies bounded fixes, passes focused and integrated tests, receives a new independent A1 audit bound to the fixed code revision, and satisfies any later user-authorized release gates. A phase pass does not claim deployment or V3 production readiness.
