# Doc334 — V3 Result Consistency Implementation Handoff TaskSpec

Status: **FROZEN IMPLEMENTATION TASKSPEC**. The user’s 2026-10-06 request authorizes sequential implementation under this scope. This document is not a test receipt or a source-fidelity migration. It packages the reviewed findings and bounded coding scope.

## 1. Goal

At one fixed V3 job revision, ensure the exact best eligible per-output set and its own review evidence govern formal selection, Brand Memory updates, Product status, ordinary Project results, E-Commerce formal export, and desktop completion messaging; repair two bounded V3 Brain request construction defects.

## 2. Non-goals

- No V1/V2 product/backend/provider/storage changes.
- No new generalized status/state framework or persistent eligibility store.
- No review threshold, retry budget, image quality prompt, or visual generation change.
- No automatic cleanup of historical Brand Memory, outputs, or exports.
- No real LLM/image provider use, paid call, production deployment, or activation under this task.
- No redesign of E-Commerce output roles, General Template, or Central Brain vertical knowledge.

## 3. Baseline and source manifest

Frozen planning baseline: `main@1a66b245ce058062eece2c1519e6a10eaf3e55d1`. The implementation branch must revalidate `origin/main` and either rebase/re-freeze if it has moved or stop and revise source mappings.

Primary symbols at the planning baseline:

| Finding | Source symbol(s) | Existing focused test area |
|---|---|---|
| R1 | `V3ProductApiService._merge_post_generation_review_chain`, `_apply_reviewed_delivery_preference`, `_public_final_delivery_projection`, `_status_from_record`; Project Mode `_delivery_annotations_for_records` and `_canonical_final_delivery_output_ids`. | `test_v3_post_generation_vision_review.py`; `test_v3_project_mode.py`; `test_v3_doc321_review_authority.py`. |
| R2 | `V3ProductApiService.select_result`, `_memory_update_for_selection`; BrandProfileService update; Project Mode selection request. | `test_v3_brand_memory.py`; `test_v3_product_api_minimal_ux.py`; `test_v3_project_mode.py`. |
| R3 | `V3ProductApiService.select_result`, `_selected_assets`, `_public_final_delivery_projection`. | `test_v3_post_generation_vision_review.py`; `test_v3_scenario_runtime_and_product_api.py`. |
| R4 | `completeV3GeneratedJob`, `runV3GenerationWithRecovery`, `recoverV3GeneratedJob`, `v3JobHasTerminalOutcome`. | Existing V3 frontend contract/shell tests; add executable actual-function regression if absent. |
| R5 | Brain availability/config path, `_credentials`, `_chat_completions_url`, default chat streaming request. | `test_v3_llm_brain_adapter.py`. |
| R6 | `V3RemoteBrainProvider._run_anthropic_compatible`. | `test_v3_llm_brain_adapter.py`; repository Anthropic clients as version precedent. |
| R7 | `export_job`, `_ecommerce_runtime_export_package`, `_ecommerce_export_manifest`, `_generated_asset_records`; Doc280 review disposition. | E-Commerce export tests; `test_v3_doc280_ecommerce_review_status_hygiene.py`; `test_v3_doc321_review_authority.py`. |

Refresh exact file paths, symbol names, and test ownership against the implementation baseline before editing. Do not treat line numbers in the prior audit as stable interfaces.

## 4. Allowed files and owner boundaries

Expected, test-driven write set:

- `alchemy_creative_agent_3_0/app/product_api/service.py`
- `alchemy_creative_agent_3_0/app/project_mode/service.py` only for a proven remaining projection mismatch.
- `alchemy_creative_agent_3_0/app/llm_brain/providers.py`
- `src_skeleton/app/static/app.js`, limited to V3 functions.
- Narrow regression tests for these owners.

One writer owns the implementation branch. No other worktree may edit the branch. Before a shared contract change, record its compatibility impact, exact migration path, and isolation tests, then return for a new contract revision.

### User-approved bounded Project Mode admission addendum (2026-10-06)

The user approved allowing an explicitly submitted E-Commerce job to reuse an active project-owned uploaded reference with canonical `use_policy=product`, even when the reference was originally saved under General. This is a scoped admission correction, not a general cross-template inheritance rule. It authorizes a minimal `app/project_mode/service.py` change and focused tests in `test_v3_project_mode.py`.

The admission must revalidate exact project ownership, active uploaded-reference status, current V3 upload readiness, and product-reference upload role; establish server-owned E-Commerce provenance using the existing trusted persistence path before canonical pool projection; and fail closed for invalid inputs. Client-supplied metadata cannot grant E-Commerce eligibility. Inactive, foreign-project, generated-selected, non-product, missing, non-ready, and wrong-role references remain excluded/rejected. General jobs, public schemas, persistence schemas, all other templates, Brand Memory, and V1/V2 remain unchanged. There is no historical migration or cleanup.

Acceptance requires the saved-General-reference → explicit-E-Commerce-job test to pass, controls for inactive/non-product/invalid references and default General behavior, a source-bound diff review, relevant regression suites, and a fresh independent A1 audit. This exception does not widen the seven named issue fixes beyond that exact admission path.

Risk/route record for this follow-on: **D0** after the user explicitly resolved the product-portability decision; **I1** for the bounded admission implementation using existing typed references and strict persistence; **A1** for the Project/Product provenance boundary and cross-template negative controls. One writer owns the existing isolated feature branch. Model/effort route provenance is not required for this functional scope and remains `ROUTE_UNVERIFIED` if unavailable; Hook state is reported separately.

Prior-snapshot receipt: saved-reference positive case, inactive/non-Product/missing-upload/General controls **5 passed**; complete `test_v3_project_mode.py` **82 passed**; broad affected Python suite **336 passed with no exclusions**; desktop Node VM **4 passed**; independent A1 **PASS**. A later independent A2 found two R1 public-projection gaps, so that receipt is historical. Corrected-candidate receipt: expanded affected Python suite **338 passed**; desktop Node VM **4 passed**; VPS release guard **7 passed**; `git diff --check` passed. Independent A2 source audit returned **PASS** for manifest `48682e31dca5ae78c42a9313aebb9108b6d6f1320a7d3f3b87c07ff44951ae76`; the auditor reviewed but did not rerun tests. The corrected candidate then passed a bounded real V3 image run with explicit `hybrid` pixel review and a ready final-delivery closure for the reviewed output. No user-data migration, commit, push, or deployment occurred.

## 5. Frozen implementation order

1. R4/R5/R6: isolated terminal and request-construction fixes with deterministic tests.
2. R1: exact best-per-role output/evidence set and downstream final delivery projection.
3. R3/R7: direct selection and formal export consume that same per-output set.
4. R2: only the selected eligible set can flow to a requested Brand Memory update.
5. Integrated Project/status/export/desktop consistency tests and independent A1 audit.

## 6. Acceptance evidence required from the writer

- Reproducer tests fail on unmodified implementation, then pass after the bounded fix.
- Complete test list, exact commands, exit status, and any exclusions.
- Fixed revision identifier, changed-file list, and diff review against this TaskSpec.
- R1 integrated output IDs with proof each winner retains the correct original inspection.
- R1 retry output IDs, E-Commerce review disposition, Product review summary, and Project timeline summary all agree with the winner set while superseded attempt outputs remain append-only; an immutable closure binds all current review winners and the eligible formal-delivery subset when extra stored attempts exist. Partial delivery preserves each output's own review disposition.
- R2 attempted update data showing only selected associations and a no-match/no-write control.
- R3 response and job/Brand Memory records showing rejection is atomic.
- R4 result state/tone evidence for failure, not-found, partial, held, and full delivery.
- R5 intercepted absolute URL variants; R6 captured final mocked Anthropic request.
- R7 formal manifest IDs/status and history projection state for all-fail, partial, and old-winner cases.
- V1/V2 isolation evidence. Original implementation-scope note: real-provider activity was excluded from the implementation chapters; this was superseded for Chapter 6 only by the user's later authorization and the bounded receipts in Doc336. No deployment occurred.
- Independent A1 AuditReceipt/result bound to the exact final source revision/diff.

## 7. Main stop and return rules

Return to Main without extending scope if:

- Source behavior at the implementation baseline differs materially from the frozen findings.
- A required output cannot be bound to exact review evidence.
- Correct behavior requires a new public schema/status or durable migration.
- Project Mode or specialized atomic contracts conflict with the shared correction.
- Existing tests fail for unrelated reasons or a focused implementation does not repair the invariant in theory.
- A validation path would call a live provider, mutate historical memory, create uncontrolled jobs/outputs, or deploy.

No fallback prompt tweak, threshold relaxation, extra retry, or new copy of delivery metadata may be used to hide an authority mismatch.

## 8. Mainline and total objective boundary

The writer must follow repository branch/worktree and milestone integration rules. This TaskSpec alone does not authorize commits, pushes, PR creation, live acceptance, data cleanup, or deployment. A passing implementation phase advances the plan; it is not total completion without the final integrated acceptance specified in Doc332.
