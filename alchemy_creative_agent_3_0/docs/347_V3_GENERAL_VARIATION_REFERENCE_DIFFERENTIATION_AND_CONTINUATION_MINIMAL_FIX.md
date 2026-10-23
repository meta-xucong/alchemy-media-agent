# V3 General Variation: Reference Source and Direction Continuation

**Status:** Local implementation revision 7; focused and adjacent regression sets pass; independent code audit passed; deployed real-generation acceptance remains pending
**Scope:** V3 Foundation variation contract and General Template only
**Phase:** Local implementation and simulation complete. Do not treat this as release acceptance until independent audit and real V3 image acceptance pass.

## 1. Objective

Make a multi-image General Template task behave like one continuing set when the user requests more images later. The first output must follow the selected prompt and route. A later batch must continue through unused directions instead of restarting at the first role and producing a near-copy of the bound main image.

The bound main image has two distinct meanings:

| Bound main source | Meaning for route progress | First output / continuation |
|---|---|---|
| Uploaded original image | Reference evidence only; it occupies no generated direction | Start with the first direction required by the current prompt. Later tasks skip only directions represented by prior eligible generated deliveries. |
| V3-generated selected output | A previously delivered image, with persisted route provenance | In the same mode, count its persisted direction once and continue from the next uncovered direction. Across modes, do not translate the old route cursor; however, a delivery-suite first row must still carry a shot-changing axis so it does not recreate the generated anchor. |

The uploaded/generated distinction is by the system's recorded source provenance. An externally AI-generated picture uploaded by the user remains an uploaded reference; do not infer origin from image appearance.

## 2. Current Behavior and Root Cause

This is a General Template / foundation variation-planning defect, not a specialized-template deliverable-map change.

The existing mode role director creates per-output recipes and a variation execution contract. Its delivery-suite diversity helper starts its shot-change requirement at the second output (`target_index=1`), so the first generated output can remain close to the reference/anchor. Project General suite planning starts from the beginning for each task and does not feed prior formally delivered route directions into that selection. Consequently, requesting another batch can reuse the opening role.

Relevant existing structures already provide the ingredients for a small correction:

- Project references distinguish uploaded sources and selected generated outputs; selected outputs retain their originating `output_id` (`app/project_mode/contracts.py`, `ProjectReferenceAsset`; reference creation in `app/project_mode/service.py`).
- General mode planning is assembled in `_build_context()` and `_project_general_suite_role_plan()` in `app/project_mode/service.py`.
- Per-output role semantics are persisted as `mode_role_recipe` and exposed through output projections (`app/creative_core/central_brain.py`, `app/generation_router/providers.py`, and `app/product_api/service.py`).
- `_public_final_delivery_projection()` in `app/product_api/service.py` is the existing authority for which outputs were formally delivered.
- `build_variation_execution_contract()` and `_ensure_delivery_suite_minimum_diversity()` in `app/shared_capabilities/visual_cluster/mode_role_director.py` are the existing shared variation planning points.

The defect is therefore missing continuation evidence and first-output route semantics. It is not a need for a new progress database, image similarity detector, or quality gate.

## 3. Frozen Minimal Correction Model

### 3.1 One progress source

When building a General mode role plan, derive the already-used direction semantics from the project's complete job history: traverse every `job_id` in `ProjectRecord.job_ids`, use that job's formal final-delivery/review projection, then read the corresponding canonical OutputStore records. Reuse those existing records and `_public_final_delivery_projection()`; do not use a paginated/latest-N project output listing. Use each eligible output's persisted `mode_role_recipe` / route semantics, with its originating job's already stored per-output plan as supporting context where available.

Do not derive progress from a task sequence, requested image count, latest-N UI list, generation attempt, unreviewed candidate, retry-superseded output, failed job, or the currently bound image alone. The bound image is not the history authority: the uploaded-vs-generated distinction determines whether that reference itself can contribute a route, while all prior eligible project deliveries determine continuation.

An eligible generated output contributes its route once, identified by its canonical output record. If it is also the bound main, the same `output_id` must not be counted twice. Unbinding or rebinding does not erase delivered project history.

### 3.2 Source-aware start and continuation

- **Uploaded reference:** Do not add a completed direction for it. The first generated output starts from the selected prompt and the mode's first planned direction. Do not force a visual change that conflicts with the prompt.
- **Generated selected output:** Its own persisted route recipe is part of eligible project history and is treated as completed. Continue with the next uncovered direction. Binding it must not create a second copy of its completion.
- **Generated selected output from another mode:** Do not map its old mode-local role index or key onto the current mode. Still treat the selected generated image as an existing visual anchor: for `delivery_suite`, the first row of the new batch must carry a shot-changing axis (`viewpoint`, `pose`, `gesture`, or `context`) even when the current mode has no prior delivery. This is derived from the existing selected-output reference provenance; uploaded source images do not trigger it.
- **Prior eligible outputs:** Count the actual route semantics of all formally delivered outputs in the same project and same General mode, whether or not they remain selected as references.
- **Partial delivery:** Only outputs present in the formal final-delivery projection advance the route. A requested count or incomplete batch does not reserve directions that were not delivered.

### 3.3 Select from existing directions

Project Mode supplies only the existing project-scoped facts: the current General mode and concise completed route semantics for that mode. The existing `ModeAwareRoleDirector` in `ScenarioRuntime` remains the route-selection authority. It applies **expand first, filter second, renumber last**: obtain enough candidates from the current neutral role catalog and its existing deterministic extension rules to cover the requested batch after excluding completed directions; remove already-covered directions within the same mode; take the next `N` uncovered directions; then assign task-local output indices `1..N`. Do not build only `N` candidates and filter afterward, because that can leave a short or empty batch. Preserve the current mode's intent; project route progress must not be encoded by falsifying task-local output indices.

The one selected `RoleSpecificGenerationPlan` must generate the variation execution contract and `variation_execution_role_plan`, and be reused for `role_plan_for_binding`. `ScenarioRuntime` retains the selected plan and derives the neutral execution contract from it, including when rebinding a saved contract/plan pair. `GeneralSuiteDirector` projects the selected runtime plan into its suite-role representation rather than call the catalog again from the beginning. The frozen route is the single source for Brain materialization, provider output binding, and review semantics. Brain receives the requested prompt plus the selected per-output route instructions; a separate extra history prompt or LLM call is unnecessary.

For `delivery_suite` only, when the project already has formally delivered directions, the first row in the new batch must carry a shot-changing axis as well as its next unused route. The current Brain prompt treats batch output 1 as an unvarying baseline; that rule must be narrowed so a continuation's first row can execute its frozen route while preserving every non-conflicting user-prompt constraint. A first task with no prior generated delivery keeps the user's prompt as its opening direction; an uploaded reference alone does not trigger continuation treatment.

Prior output descriptions are semantic route evidence only. Do not feed prior full images to the provider as extra image inputs, or grant them new identity/style/composition ownership. Existing selected reference channels keep their current Doc93 ownership rules.

## 4. General Mode Boundaries

Continuation is scoped by project and General mode. A mode switch does not map one mode's route index onto another mode. When returning to a mode, continue that mode from its own persisted delivered role semantics. This continuation rule applies to all four modes; their creative intent remains distinct.

- `selection_candidates`: continue with comparable candidates not already represented in this mode; keep its near-neighbor intent while skipping previously delivered candidates.
- `delivery_suite`: continue with uncovered suite roles and shot directions.
- `creative_exploration`: continue with concepts not already represented in that mode's eligible deliveries.
- `format_layout_adaptation`: continue with formats/layouts not already represented in that mode's eligible deliveries.

If a selected AI output came from a different General mode, its normal reference/identity channels remain available, but its old mode-local position must not be translated into a cursor for the new mode. Its route is counted under the mode recorded by its original delivery only. Separately, its generated-image provenance still activates the first-row shot-change requirement for a new `delivery_suite` batch; this avoids copying the anchor without inventing a cross-mode route mapping.

Specialized template plans and their scenario-specific deliverable maps remain untouched. No General Template behavior may leak into E-Commerce, Photography, Brand, or New Media role planning.

## 5. Minimal Implementation Boundary

The implementation should be limited to:

1. At `_project_general_suite_role_plan()`, traverse all `ProjectRecord.job_ids`, obtain each job's formal final-delivery/review projection, and collect eligible output route semantics from canonical records. Keep Project Mode's existing simple suite-role view as a projection/summary; it does not choose the runtime route.
2. Pass the already collected completed direction semantics through the existing project context to `ScenarioRuntime` and its call to `ModeAwareRoleDirector.build()`.
3. In the director, expand from the existing neutral catalog/extension rules, exclude same-mode delivered directions, select the next `N`, and reindex the current batch `1..N`. Reuse that single role plan for the variation contract and `role_plan_for_binding`.
4. Have `GeneralSuiteDirector` project the frozen runtime role plan into its suite roles, then preserve it through Brain planning/materialization, binding, and review.
5. Correct delivery-suite first-output semantics so the first generated frame follows the first **selected** route in this batch. On continuation, give that first row a shot-changing axis; on an initial task, preserve the opening prompt direction. Do not silently treat each batch's first output as another copy of the generated reference/baseline. Honor the user's prompt and current mode; add no scene-specific role or unconditional “must differ” rule.

Do not add a table, migration, persistent cursor, duplicate route metadata, new status flag, new route catalog, similarity model, image-level duplicate detector, extra LLM/provider/review call, retry, or validation gate. Do not change public APIs or specialized templates. No pixel-level non-similarity guarantee is implied; the contract is to continue semantic directions.

If an older formally delivered output lacks a reliable stored route identity, use only route semantics available from its existing persisted plan/receipt. Do not guess a route from its ordinal or add a new failure gate. Such legacy output must not falsely mark an arbitrary current route as complete.

## 6. Implementation Acceptance Criteria

The implementation phase should add focused regression coverage before code changes and pass these cases:

1. Uploaded main reference, first task: first output receives the prompt's first route; the uploaded reference consumes no route.
2. Uploaded main reference, subsequent task: prior formal deliveries are skipped and the next uncovered routes are selected.
3. AI-generated main from a prior delivery: its persisted route is skipped exactly once and the next route is selected.
4. Binding/unbinding/rebinding the same generated output does not change project route progress.
5. A failed, pending, retry-superseded, or non-delivered candidate does not consume a route; a partially delivered job advances only by eligible delivered outputs.
6. Switching between the four General modes does not cross-contaminate route progress; returning to a mode resumes that mode.
7. The frozen continuation role plan reaches Brain materialization and is reused for binding/review, while historic images are not added to provider inputs.
8. Specialized template role plans and output contracts remain unchanged.
9. The requested user prompt remains authoritative, and no extra generation, retry, review, or similarity-validation call is introduced.
10. A selected AI output from a different General mode does not advance the current mode's route cursor, but does give the first `delivery_suite` output a shot-changing axis; an uploaded original does neither.

After focused tests and independent code audit, perform a guarded local real-generation acceptance only when its mutation boundaries are explicit. Compare output route semantics and actual images for the first batch and continuation; semantic planning success alone is not final visual acceptance.

## 7. Audit and Phase Receipt

The read-only design review confirmed separate uploaded/generated provenance, generated references' `created_from_output_id`, formal delivery projection, and persisted per-output route recipes. It required complete `ProjectRecord.job_ids` history and expansion before exclusion so a continuation batch still yields `N` outputs. A subsequent source trace corrected the route authority: Project Mode provides history facts; `ScenarioRuntime` selects and freezes the route with `ModeAwareRoleDirector`; the suite director and `role_plan_for_binding` reuse that frozen plan. Revision 2 superseded the initial proposal's “Project Mode owns route selection” wording. Revision 3 also applies continuation to `selection_candidates`, consistent with the user's requirement that other modes continue without repeating earlier options. Revision 4 narrows the old output-1-baseline prompt contract for `delivery_suite` continuations so the first row can carry the next route away from a previously generated main image.

**Design review disposition:** The original proposal was `INSUFFICIENT_EVIDENCE`; findings were incorporated before implementation. Agent route provenance was not independently available (`ROUTE_UNVERIFIED`).

**Implementation and local verification:** Implemented the project-history route projection, expand/filter/renumber continuation, first-row continuation axis, saved-plan reuse, and contract derivation from the frozen role plan. The first independent code audit found that legacy jobs without canonical final-delivery IDs could be inferred as completed; implementation now skips those jobs. The second code audit found the possibility of contract/role-plan semantic drift; implementation now derives the contract from the role plan. Both audit reports had `ROUTE_UNVERIFIED` provenance. The final independent re-audit could not be dispatched because the agent thread limit was reached, so no final independent `PASS` is claimed.

The focused implementation tests pass **8/8**. The combined safe regression selection passes **54**, with **39 deselected** because those cases were outside the focused selection or included remote/runtime behavior. Changed Python files compile, and `git diff --check` passes. One older test named `test_product_api_mock_generation_persists_distinct_doc59_roles` unexpectedly attempted a remote LLM HTTP request; it was interrupted and excluded from regression evidence.

**Real-generation acceptance:** Not run. The existing V3 page at `https://alchemy.aiself.vip/` is blocked by a saved browser-origin permission. The browser tool explicitly disallows using another surface or lower-level access to bypass that setting. No real image was generated.

**Phase result:** Local implementation and deterministic regression phase passed.
**Still required for total acceptance:** re-run an independent read-only code audit, obtain authorized access to the V3 page for a guarded real-image first-batch/continuation check, then push to GitHub and use the repository's guarded VPS candidate/activation workflows. No commit, push, or VPS deployment was performed because those acceptance gates did not pass.

### Revision 6 — cross-mode generated anchor closure

The 2026-10-23 VPS run `job_9303f22720` exercised release `e6639f4c`, while the earlier local revision 5 changes were still uncommitted and absent from the release. The run's selected main output was a prior `format_layout_adaptation` delivery; the new request used `delivery_suite`. Its first output was `hero_subject` with only `subject scale`, and its second was `detail_focus` with `detail/crop/angle/pose`; both referenced the same selected main output. This matches the reported near-copy on output 1. The output review also recorded `output_review_metadata_only`, so it did not visually catch the similarity.

The local correction carries existing selected-output provenance into the frozen role plan. Same-mode route history still controls which role key is skipped. A generated selected output from another mode does not consume a role in the new mode, but it activates the existing delivery-suite first-row shot-change axes. Uploaded references leave that behavior off. Follow-up audit found a legacy metadata fallback defect: the delivery projection intentionally removes mode metadata, so old route recipes without their own mode could be missed. The fix retains the original Job status for that one route-mode fallback while all delivery eligibility remains based on the projected canonical status. Added regression coverage both for this fallback and for the cross-mode selected-output path from project route plan through Runtime's first-row contract.

The focused suite passes **11/11**; it plus adjacent variation/source-closure regressions passes **70 tests**. Python compilation and `git diff --check` pass. One Windows temporary-directory cleanup warning was emitted by pytest; all test assertions passed. The independent follow-up audit returned **PASS** for local code and deterministic regressions, with no new blocking issue. The auditor independently reran the focused 11 tests; the 70-test adjacent selection was not rerun by the auditor. The VPS remains on `e6639f4c`; no output from the corrected local code has been generated yet, so visual outcome and deployment acceptance remain open.
