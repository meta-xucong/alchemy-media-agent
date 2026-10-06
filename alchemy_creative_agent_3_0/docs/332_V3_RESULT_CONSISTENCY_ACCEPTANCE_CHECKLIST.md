# Doc332 — V3 Result Consistency Acceptance Checklist

Status: **Chapters 1–6 pass for the corrected candidate.** The expanded regression suites pass and independent A2 source audit returned PASS for manifest `48682e31dca5ae78c42a9313aebb9108b6d6f1320a7d3f3b87c07ff44951ae76`. A later bounded real run on the same corrected code diff generated one real image, obtained a verified `hybrid` pixel-review PASS, and produced a `ready` final-delivery closure for that exact output ID. Latest-main integration, commit/push, and VPS release remain open.

Baseline for this planning packet: `1a66b245ce058062eece2c1519e6a10eaf3e55d1`. Use the implementation branch’s actual base and frozen result revision for later evidence.

## A. Documentation preparation gate

- [x] Seven defect descriptions are tied to V3 owners and bounded triggers.
- [x] Per-output correction model reuses Doc321 and existing review/delivery records.
- [x] Implementation order and dependencies are explicit.
- [x] Regression scenarios include negative, recovery, and no-side-effect cases.
- [x] Historical Brand Memory is explicitly read-only in this scope.
- [x] Independent documentation A1 audit passes against the frozen seven-document revision.
- [x] Mainline integrator records docs-only phase result and remaining code objective in the task report.

The checked items above record the completed documentation-preparation milestone. Implementation evidence and its current status are recorded in Sections B–F below; external provider/release gates remain separate.

## B. Implementation preflight gate

- [x] Confirm unique main checkout is `main` at `origin/main`; record exact baseline hash `1a66b245ce058062eece2c1519e6a10eaf3e55d1`.
- [x] Preserve all pre-existing tracked/untracked files and active worktrees.
- [x] Create one scoped feature branch/worktree from current `origin/main`.
- [x] Freeze the implementation TaskSpec, allowed files, D/I/A, test commands, and stop conditions.
- [x] Re-read current code/docs; refreshed symbols at the fixed baseline.
- [x] Confirm no real provider, image-generation, persistent-data cleanup, or deployment step is part of this authorization.

## C. Test-first correction gate

- [x] R4 red regression demonstrates `failed`/`not_found` + no valid delivery cannot produce completed/success.
- [x] R5 red regression demonstrates missing OpenAI base URL produces invalid relative URL today.
- [x] R6 red request-capture regression proves Anthropic version header is absent today.
- [x] R1 red regression demonstrates best-per-role `{old A, new B}` is lost/mismatched downstream.
- [x] R3 red regression demonstrates invalid explicit sibling/unknown ID cannot be selected.
- [x] R7 red regression demonstrates full-failure E-Commerce export has no formal file entries and retains truthful history status.
- [x] R2 red regression demonstrates selecting A cannot persist B reference/accepted ID.
- [x] Existing Doc321/Doc280 positive and fail-closed controls remain represented.

## D. Focused code acceptance gate

- [x] R4 terminal states `failed`, `not_found`, and `blocked` display failure; partial, review-held, full, and missing delivery remain distinct at the completion-function boundary.
- [x] R5 no base URL resolves to an absolute official URL; `/v1`, trailing slash, and custom gateway cases work without path duplication.
- [x] Availability and request construction share one OpenAI URL resolver. Malformed query/fragment base URLs are not separately rejected by this phase.
- [x] R6 final Anthropic request includes the repository-supported version and retains auth/path/body; the version header is provider-gated to Anthropic.
- [x] R1 winners retain exact per-output review evidence; retries stay append-only; Product status and Project output agree in the integrated old-A/new-B fixture.
- [x] R3 default selection is eligible-only; explicit mixed, failed, and unknown selections reject atomically; no zero-match success.
- [x] R2 only selected eligible source/candidate associations persist; conflicting dual associations are rejected; empty intersection skips the update; Project Mode remains non-automatic.
- [x] R7 formal export equals the eligible winner set; real per-image statuses remain intact in history.
- [x] No delivery predicate, manual-review state, certification, or quality threshold was relaxed.

## E. Integrated behavior gate

Use the same fixture/job revision across all three read surfaces. For automatic delivery (no explicit user subset), compare the winner set exactly; with an explicit subset, separately verify `selected ⊆ eligible` and preserve each surface’s existing eligibility-versus-selection meaning.

- [x] In automatic delivery with no explicit user selection, API `final_delivery` IDs equal ordinary Project final-output IDs in the retry A/B fixture.
- [x] In automatic delivery with no explicit user selection, E-Commerce formal export IDs equal API/Project final IDs in the same fixture.
- [x] Best-output preference resolves to those exact final IDs, each with the correct original evidence.
- [x] Explicit selection cannot add an ID outside that set.
- [x] Brand Memory references are a subset of selected eligible IDs and carry the exact source/candidate binding.
- [x] Review history retains intended append-only records and preserves failure/manual/unreviewed/superseded statuses in focused fixtures.
- [x] Desktop tone and notice distinguish failure, not-found, partial, withheld, and full completion at the completion-function boundary.
- [x] No stale polling recovery/session result overrides the current job in the Node VM cases.

## F. Regression and independent audit gate

- [x] Chapter 1 focused suites pass: Python 66 passed; Node VM 4 passed; desktop JS syntax and `git diff --check` pass.
- [x] Relevant broader V3/Product API/Project/Frontend/Brain regression suites pass without exclusions or failures: 336 passed, 0 deselected.
- [x] User approved and implementation completed for the bounded Project Mode admission extension: active, valid saved Product references can be reused by an explicit E-Commerce job even when originally saved under General. Docs 330/334 capture the extension; tests cover invalid, inactive, non-Product, and unchanged General behavior.
- [x] The nested-worktree Windows path-length failure in the persistent Project Store test fixture was corrected by using a short isolated system-temp root; that test now passes in isolation.
- [x] Formerly excluded `test_project_mode_accepts_ready_saved_product_reference` passes in the inclusive 336-test broad run.
- [x] After the bounded R1 audit correction, the expanded affected Python suite passes: 338 passed, no exclusions; Node VM: 4 passed; VPS release guard: 7 passed; `git diff --check` passed.
- [x] `git diff --check` passes for Chapter 1; changed-file scope is confined to the two Brain/desktop owners and their focused tests.
- [x] Chapter 1 diff does not touch V1/V2 modules/configuration/storage.
- [x] Independent read-only A1 auditor reviewed the frozen Chapter 1 diff and returned PASS, with URL-shape and live-provider limitations recorded separately.
- [x] Independent read-only A1 auditor reviewed the prior snapshot, including the Project Mode admission follow-on, and returned PASS. A later independent audit found the R1 gaps recorded in Doc335; this earlier pass is not the final candidate audit.
- [x] Correct the R1 disposition and winner-summary gaps and pass the expanded integrated regressions.
- [x] Obtain a fresh independent audit bound to the corrected snapshot: A2 PASS for manifest `48682e31dca5ae78c42a9313aebb9108b6d6f1320a7d3f3b87c07ff44951ae76`.
- [x] Any audit correction creates a new frozen revision with affected tests rerun and a new audit.
- [x] Route provenance, Hook status, code acceptance, and real-provider validation are reported as separate facts.

## G. Later release and total acceptance gate

- [x] The user-authorized real-provider acceptance passed for the **pre-correction source snapshot only**; the real output, review evidence, and final-delivery projection are recorded in Doc336. The first mock setup attempt is preserved and explicitly excluded.
- [x] A bounded real generation and explicit `hybrid` pixel review ran on the corrected candidate. Review status is `pass`/`verified`; the ready delivery closure names the same output ID. See Doc336 for the output hash and preserved receipt.
- [x] Complete corrected-candidate pixel review and final-delivery acceptance. Job `job_cae8fab1aa` records one verified `hybrid` PASS and a ready delivery closure for the same eligible output ID; see Doc336 §7.
- [ ] Rebase onto the latest `origin/main`, freeze the merge candidate, and run required integrated verification on that exact candidate.
- [ ] Deployment has separate approval, data-preserving release steps, health checks, and post-deploy acceptance. No VPS deployment has occurred.
- [ ] Do not describe a phase-level pass as product readiness, module activation, or total completion until all required phases and integrated acceptance pass.

## H. Final implementation report must state

- Affected V3 scope and files.
- Exact tests/commands run, results, and exclusions.
- Frozen commit/hash and audit result.
- Commit hash and push status if later authorized/performed.
- Whether any real provider or deployment action occurred.
- Remaining integration or total-acceptance dependency.
