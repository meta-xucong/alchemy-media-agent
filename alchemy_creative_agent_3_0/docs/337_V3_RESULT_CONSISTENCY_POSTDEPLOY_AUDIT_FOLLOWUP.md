# Doc337 — V3 Result Consistency Post-Deployment Audit Follow-up

Status: **A1 follow-up corrections implemented and independently audited PASS; exact integrated-main acceptance passes and is pushed to GitHub. VPS release is waiting for local SSH key unlock.**

Baseline: `fb2dae1943f3e95402e94b006f65b079b6edec0a` (`main`, equal to `origin/main`).
Prior user files and other active worktrees are preserved.

## 1. Goal and boundary

Close the four bounded V3 regressions/edge cases reported in the post-deployment audit. Reuse Doc321 delivery eligibility and the per-output review evidence already introduced by Docs328–336. Do not add a new state framework, change image-quality thresholds, call a real image/model provider, alter V1/V2, or deploy before the corrected candidate passes focused and integrated acceptance.

Risk classification: **D0** (Doc329 already states the controlling behavior); **I2** (review, role projection, memory persistence, and desktop terminal presentation interact); **A1** (cross-surface result and retry invariants). One writer at a time.

## 2. Independent audit of the reported findings

An independent read-only A1 source audit on this exact baseline returned **FAIL** and confirmed the code paths for all four findings. It did not run tests and does not validate DOT's reported counts or exact reproductions. Main's bounded local checks at the same baseline found the existing single-role Photography retry test passes, confirming that it does not cover the old-winner/mixed-role boundary.

| Finding | Owning layer | Correction model |
|---|---|---|
| Photography role summary binds the latest retry candidate while Doc95 may select an older per-role winner | V3 Product final role projection | Build each certified role from the same preferred output and its own complete review receipt. Keep raw attempt history append-only. |
| A high-scoring `manual_review` or `fail_retryable` output may displace a `pass`/`warning` output | V3 best-result selection | Rank formally delivery-eligible outputs first; if none exist, keep the best pending result for review without making it deliverable. Reuse current Doc321 per-output eligibility. |
| Explicit `not_evaluated` candidate browsing can still persist its `MemoryUpdate` | Direct Product API persistence | Preserve browsing selection, but skip MemoryUpdate filtering/application unless selected assets belong to the exact formally eligible output set. |
| Desktop completion ignores backend `final_delivery.partial_delivery` and its positive output count | V3 desktop terminal projection | Recognize formal partial delivery from `metadata.final_delivery` plus positive eligible count and visible output, while preserving the legacy recovery path. Show a partial outcome, not success or no-output failure. |

## 3. Files in scope

- `alchemy_creative_agent_3_0/app/product_api/service.py`
- `src_skeleton/app/static/app.js`
- `alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py`
- `alchemy_creative_agent_3_0/tests/test_v3_photography_mainline_004.py`
- `alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py`
- `tests/v3_frontend_terminal_contract.test.mjs`
- This document and the existing result-consistency acceptance checklist.

No public schema additions are planned. If role/output identity cannot be proven from current records, fail closed instead of inferring from list position or a sibling candidate.

## 4. Required regressions

1. In a three-role Photography professional set, force a mixed retry outcome where at least one initial `pass` wins over a retry candidate. The final job, role summary, selected output, and exact review receipt must agree; valid delivery must not become blocked.
2. For the same role, give an earlier `pass` a lower score than a retry `manual_review`/`fail_retryable`; the earlier output must remain the formal winner. When no eligible candidate exists, retain a pending winner and keep delivery withheld.
3. Select a valid but `not_evaluated` candidate with `apply_memory_update=true`; browsing may succeed, but no memory application, accepted asset, or persisted reference may result. Existing eligible selection must continue to work.
4. Feed the desktop completion function the backend shape `final_delivery.partial_delivery=true`, `automatic_delivery_available=true`, `final_delivery_output_count>0`, fewer visible outputs than requested; the outcome must be partial with a warning. Full delivery, review-held, failed, and not-found outcomes remain distinct.

## 5. Acceptance gates

- Run the new regressions first and record the red result before implementation.
- Run focused Photography, review-selection, memory-selection, desktop Node VM, and JavaScript syntax checks after the bounded implementation.
- Run the full affected Python suite, desktop Node VM suite, VPS release guard suite, and `git diff --check` on the exact integrated commit.
- Obtain a separate read-only A1 audit of the frozen corrected revision.
- Do not start real generation or VPS activation while any focused, integrated, or audit gate fails. If all pass, continue the already-authorized GitHub and guarded VPS release path at the exact accepted SHA.

## 6. Evidence limitations

The four findings were confirmed by source tracing; DOT's reported 383-pass count, failing test, Chromium-dependent results, and live VPS SHA were not independently verified in this audit.

## 7. Corrected candidate implementation and verification

### 7.1 A1 follow-up correction model

Observed mismatch: result preference groups retries by `asset_id`. If a provider assigns a new asset ID to a retry of the same frozen role, the selector mistakes those outputs for unrelated assets and may fall back to whole-attempt selection. A high-scoring retry batch can then replace an older deliverable role output when another role in that batch is eligible.

Authority: the frozen specialized role execution record is the stable role authority. Its current and `previous_candidate_ids` form the append-only candidate lineage; each attempt's inspection/resolution/evidence receipt remains authoritative for that candidate's review. Output asset IDs are attempt-local storage identities and must not establish cross-attempt role identity.

Minimal correction: map inspection candidate IDs to their frozen `role_key` via current/previous candidate lineage, then rank and select independently per role before composing the final winner package. If an inspection candidate cannot be bound to a role, keep its existing asset/position fallback and never infer a role from list position. Add a two-role regression with changing asset IDs where the retry role is pending but a sibling retry role is eligible; the old eligible role must remain selected. Add an all-pending case proving the pending winner is retained without becoming deliverable.

The desktop legacy recovery fixture also used `failed` as a settled state, but production `v3JobDeliverySettled` accepts only `generated`/`selected`. Correct the fixture to use the real predicate and a generated job carrying the legacy partial-recovery marker. Keep separate failed/not-found zero-output cases.

This is a bounded refinement of the original implementation, not a new delivery-state framework. Do not perform real generation or deployment until these new red tests pass, the revised affected suite passes, and a fresh independent A1 audit approves the exact corrected candidate.

The implementation reuses the existing review receipt, candidate history, final-delivery projection, and desktop completion function as authorities. It adds no public schema, delivery threshold, provider integration, V1/V2 path, or historical memory cleanup.

- Photography role projection now resolves the preferred inspection through the role's current and append-only previous candidate IDs, then binds that candidate and its own inspection to the frozen role summary. Equal-scoring eligible retries prefer the newer attempt; a higher-scoring pending candidate cannot displace a formally eligible output.
- Retry selection validates each output's complete receipt, ready resolution, evidence-plan digest, real-pixel verification, Doc276 certificate when required, inspection status, and existing hard gates before ranking it as delivery-eligible. If none qualifies, the existing pending-result behavior remains available while delivery stays withheld.
- Explicit not-evaluated candidate browsing remains selectable, but skips Brand Memory update preparation/application. Existing formally eligible selection and Project Mode's disabled automatic memory write remain covered by the broad suite.
- Desktop completion recognizes formal partial delivery only with `partial_delivery=true`, automatic delivery enabled, a positive eligible output count, and visible output; the notice states how many eligible images were delivered.

Test-first evidence: the three-role mixed-retry test failed on the baseline with a blocked job; high-scoring pending retries displaced the eligible initial output; the not-evaluated browse selection applied Brand Memory; and the formal desktop partial-delivery fixture was classified as failure. The added regressions pass after correction.

Verification on the feature worktree at the current candidate:

- Affected Python suite from Doc331 §9: **339 passed, 2 deselected**. Both deselected cases are the parameterized desktop/mobile Playwright session-race test that launches Chromium; the other 23 Doc280 cases ran.
- Photography production and mainline suites: **20 passed**.
- Desktop terminal Node VM contract: **5 passed**; `node --check src_skeleton/app/static/app.js` passed.
- VPS release guards: **7 passed**; `git diff --check` passed.
- The two browser cases in Doc280 were not run because Chromium is not installed; the earlier boundary that cancelled browser setup remains in effect. No real image/model provider or VPS action was used for this follow-up.
- Python test tooling plus `httpx` and Playwright's Python package were installed into a system temporary directory for test execution only; no repository dependency file was changed. Chromium itself was not installed.

Exact broad command:

```powershell
$env:PYTHONPATH = Join-Path $env:TEMP 'codex-v3-pytest-tools'
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py alchemy_creative_agent_3_0/tests/test_v3_doc321_review_authority.py alchemy_creative_agent_3_0/tests/test_v3_project_mode.py alchemy_creative_agent_3_0/tests/test_v3_doc280_ecommerce_review_status_hygiene.py alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py alchemy_creative_agent_3_0/tests/test_v3_llm_brain_adapter.py tests/test_v3_frontend_generation_mode_contract.py -k 'not new_ecommerce_generation_session_discards_late_prior_recovery_and_renders_current_response' -q
```

Result: `339 passed, 2 deselected`. The dedicated Photography run was `20 passed`; terminal Node VM was `5 passed`; VPS release guard was `7 passed`.

Next gate: add the follow-up regressions first, implement the stable role identity correction, rerun the affected suite, then obtain a fresh read-only A1 review bound to the exact frozen code, tests, and document manifest. If it passes, integrate into the unique main checkout, rerun required integrated verification, then continue only through the already-authorized GitHub and guarded VPS release workflow. Do not claim total completion before those steps pass.

### 7.2 Independent A1 findings and bounded follow-up evidence

The first independent A1 review returned **FAIL** with one material selector gap: output `asset_id` changes across retry attempts, so using it as the role group can fall back to whole-attempt selection. The review also found that the legacy frontend recovery test's `failed` fixture was inconsistent with the production settled-status predicate. Both findings were incorporated into §7.1 before the follow-up implementation.

Red evidence: the strengthened two-role regression uses different asset IDs for both candidates across attempts, a pending/high-score retry for one role, and a separately eligible retry sibling. Against the first implementation it failed in both `manual_review` and `fail_retryable` cases by selecting `pending_retry` instead of `deliverable_initial`.

Follow-up implementation: candidate IDs from the frozen role's current/previous lineage now map each review output to a stable role key before per-role ranking. Ambiguous/unmapped candidate lineage does not guess a role. The desktop Node harness now models the actual `generated`/`selected` settled predicate; the legacy recovery case uses a generated job with visible partial output and its legacy marker.

Red/green evidence after this correction: the strengthened two-role, changed-asset-ID regression failed on both pending statuses against the first implementation, then passed after stable role-key binding. Focused selector + pending fallback **3 passed**; Photography winner binding **2 passed**; desktop Node VM **5 passed**. The full affected Python command in §7 passed again with **339 passed, 2 Chromium cases deselected**; Photography suites **20 passed**; VPS release guard **7 passed**; JavaScript syntax and `git diff --check` passed. The independent audit is still pending.

### 7.3 A1 acceptance assertions

The second read-only A1 review found no confirmed runtime defect but requested three explicit acceptance proofs. Those assertions are now added:

- The Photography retry test compares winner output IDs with the preferred output set and Project output list, then checks every role candidate against its inspection, ready resolution, and complete review evidence plan/digest set.
- The no-eligible retry fallback test now calls the final-delivery projection and asserts an empty eligible output set, automatic delivery disabled, and a zero final-delivery count while the pending winner remains selected.
- The desktop formal-partial Node test asserts that the user notice reports the exact delivered image count.

Focused checks for these additions pass: all-pending final projection **1 passed**; Photography role/output/receipt/Project equality **1 passed**; desktop terminal Node VM **5 passed**. Run the affected broad suite again and obtain a third A1 review before integration.

### 7.4 Job-status output projection correction model

Observed mismatch: the strengthened three-role regression finds three IDs in the final preferred/deliverable set and exactly those three IDs in Project outputs, while the generated job's `asset_series` contains only one. This is a real cross-surface mismatch, not a test fixture discrepancy.

Owning layer: V3 Product API public job-status projection. `_asset_series` currently walks the frozen `series_plan.assets` and looks up packaged candidates by the original asset ID. Retry winners can be attached to a distinct candidate/output binding while the final per-output review package and Project output store correctly expose the winners. Therefore the task status can remain tied to the original plan projection.

Authority: the exact eligible output ID set from `_public_final_delivery_projection`, with each winner's own complete inspection/resolution/evidence-plan receipt. The append-only `asset_pack` and output store provide concrete file metadata; frozen role execution and candidate lineage provide role identity. `series_plan` remains a request/planning record and must not override final winner identity.

Minimal correction: build the gated public `asset_series` from the eligible winner bindings and their concrete packaged output records, preserving available asset-spec display fields by stable role/candidate binding. Do not surface superseded or pending candidates as delivery. When delivery is not gated, keep the current legacy projection. The final status IDs, Photography role winners, complete review evidence, Project outputs, and actual output records must agree exactly in the mixed-retry regression.

This correction affects final output projection in the same V3 Product API; it adds no status framework or V1/V2 behavior. Add/keep the three-role regression red before changing this projection, then rerun the complete affected suite and obtain a fresh independent audit. Do not integrate, push, or deploy until it passes.

### 7.5 Final output projection correction and verification

The three-role assertion was run against the pre-correction implementation and failed with three preferred outputs and three matching Project outputs but only one output in the job status `asset_series`. This confirmed the §7.4 hypothesis.

The gated `_asset_series` projection now binds each listed packaged asset to the exact eligible `output_id` and its own inspected `asset_id`, then recovers display fields from the frozen plan by stable `mode_role_key` (or exact asset ID for non-role outputs). It emits the packaged winner's asset ID. It does not infer identity by list position and fails closed when the receipt binding or display-spec match is missing. The ungated candidate/history projection remains unchanged.

The three-role mixed-retry regression now asserts equality across role winners, complete per-output receipt facts, preferred IDs, status `asset_series`, and Project outputs. It passed after failing before the correction. An existing held-candidate projection test also verifies a nonmatching output ID remains hidden.

Final feature-worktree verification after this correction:

- Affected Python suite: **339 passed, 2 deselected** (only the Chromium-dependent parameterized session-race cases).
- Photography mainline and production-activation suites: **20 passed**.
- Desktop terminal Node VM: **5 passed**; `node --check src_skeleton/app/static/app.js` passed.
- VPS release runtime guards: **7 passed**.
- `git diff --check` passed. No provider generation, real model calls, or deployment was performed.
- Photography mainline contract collection was attempted separately but could not start because this temporary Python environment lacks `fastapi`; this file was outside the successful 20-test focused Photography command. The two browser cases remain unverified because Chromium is not installed, consistent with the previously cancelled browser setup.

The new cross-surface correction still requires a fresh independent read-only A1 review of the exact candidate manifest. Integration, GitHub push, and VPS deployment remain gated on that review and the exact-main acceptance run.

### 7.6 Candidate-summary exact binding correction

The independent A1 audit returned **FAIL** after confirming that `_candidate_summaries` received both eligible output and asset ID sets but filtered only by output ID. A stale package row could therefore be presented with an `accept` recommendation even when its packaged asset ID differed from the unique inspection binding. The ordinary generation path mismatch was not demonstrated; this is a confirmed fail-closed projection gap because the public projection contract must preserve exact output/asset identity.

Test-first evidence: a focused regression paired eligible output ID `good` with packaged asset `stale_asset` while its review inspection certified `asset_good`. Before the code change, `_candidate_summaries` returned that candidate with `recommendation="accept"`; the test failed as expected.

The projection now builds an output-to-asset binding only when exactly one inspection row exists for that eligible output, requires the packaged candidate asset ID to match it, and enforces `visible_asset_ids` when supplied. Ambiguous output inspections fail closed. No score, recommendation, or selected state is produced for a mismatched row because the candidate is omitted entirely.

Verification after this correction: affected Python suite **340 passed, 2 deselected**; Photography mainline/activation **20 passed**; desktop Node VM **5 passed**; VPS release runtime guards **7 passed**; JavaScript syntax and `git diff --check` passed. The two Chromium-dependent browser cases remain unverified. The fresh independent A1 result is recorded in §7.7; integration and release remain gated on exact-main acceptance.

### 7.7 Final independent A1 result

The independent read-only A1 review returned **PASS** against all six SHA-256 hashes in the frozen manifest above. The reviewer confirmed the four original findings and both cross-surface projection corrections align across source and regressions. The reviewer did not rerun tests or provider calls; test receipts are from the feature worktree as recorded in §§7.5–7.6.

Remaining implementation limit: the reviewer found no ordinary Generic retry path that changes asset IDs; if a future non-role runtime changes an asset ID without a role key, the current projection fails closed and needs authoritative lineage before such a path can be supported. After the audit, the existing browser setup was found in the local Playwright cache; both previously omitted cases passed without installing dependencies or changing browser configuration. No real model/image generation, GitHub push, or VPS deployment occurred in this audit.

### 7.8 Browser and complete affected-suite acceptance

The two parameterized browser session-race cases were run directly using the existing local Playwright Chromium cache: **2 passed, 23 deselected** in that focused invocation. Then the complete affected Python command from §7 ran without exclusions: **342 passed in 187.15s**. This includes both browser cases.

The current feature-worktree evidence is therefore: affected Python **342 passed**; Photography mainline/production activation **20 passed**; desktop Node VM **5 passed**; VPS release runtime guards **7 passed**; `node --check` and `git diff --check` passed. The independent A1 audit returned PASS against the frozen source/test manifest. The remaining required gates are latest-main synchronization, exact integrated-main verification, and then the already-authorized GitHub/VPS release sequence.

### 7.9 Exact integrated-main acceptance

The accepted feature commit `80ad30a08ab5a2de4e20fec414c57b29c1235033` was fast-forwarded into the unique main checkout at `D:\AI\Alchemy Media Agent System`. On that main checkout, before any release push:

- Full affected Python suite, including both Playwright Chromium cases: **342 passed in 310.96s**, no deselections.
- Photography mainline and production-activation suites: **20 passed in 109.26s**.
- Desktop terminal Node VM: **5 passed**; `node --check src_skeleton/app/static/app.js` passed.
- VPS release runtime guards: **7 passed**.
- `git diff --check` passed.

All code and test files match the A1-audited manifest. `origin/main` was confirmed at baseline `fb2dae1`, then pushed through integrated-main commit `75d605776be1b9b74205859d10f0d5398f2153d3`; local `HEAD` and `origin/main` matched afterward. The main checkout's pre-existing untracked user document remains untouched.

VPS release preflight is currently held before remote execution. The required encrypted SSH key passphrase was not available in the current or user-level `POLYMARKET_SSH_PASSPHRASE` environment, so the wrapper could not authenticate. No remote command ran and no VPS state changed. Resume the governed release script only after the passphrase is made available locally; do not send the secret in chat. The release must target the then-current exact `origin/main` SHA, including this acceptance record.

Frozen A1 candidate manifest (SHA-256):

| File | SHA-256 |
|---|---|
| `alchemy_creative_agent_3_0/app/product_api/service.py` | `46523196096FFC380B751FFA4C6C107EB115C3B6488A1E6C5B052BFFEC92832D` |
| `alchemy_creative_agent_3_0/tests/test_v3_photography_mainline_004.py` | `A2BA882613FBA3EBCB0EEA793DB187266D009C631D1AA6A98F23B74AC986396E` |
| `alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py` | `C4D38429FD7BC27EAFAE9CF13AD2AC7629755E3EE8B0ADD2BA664AEF3A004CD5` |
| `alchemy_creative_agent_3_0/tests/test_v3_doc321_review_authority.py` | `93A800DF1F2C283657D383123EC5D32230F3B3A98C35D0075DA7E646C6B451F1` |
| `src_skeleton/app/static/app.js` | `34E91FD9A0CCA3D3C44E890EF4FE4A6B068FEF9289DF302F45A29BEE2C5F6800` |
| `tests/v3_frontend_terminal_contract.test.mjs` | `A018E65A879E8E768ECCFCC61D0D6C25CC6369F136C293AEF1A14D6883CB88EC` |

## 8. Follow-up audit on baseline `5a249d60`

### 8.1 Findings and authority

This follow-up is limited to the two new residual findings reported against `5a249d60b9a57e62acd2c1b1ddca1947f65eaee7`. It does not reopen the earlier seven-item scope or change V1/V2 behavior.

**D/I/A:** D0 because Docs329/331 and the existing formal delivery projection define the expected behavior; I2 because the second finding crosses provider-attempt history, per-role winner selection, final delivery, and Project output reconciliation; A1 because both findings concern cross-surface/retry invariants.

| Finding | Owning layer and authority | Minimal correction model |
|---|---|---|
| Desktop completion calls `v3JobHasRecoverablePartialDelivery` without the request's `expectedCount`. The helper also compares visible output count to its inferred default before checking the backend's formal partial-delivery receipt. | V3 desktop terminal projection. A positive `final_delivery_output_count` with `partial_delivery=true` and automatic delivery enabled is authoritative; the request count is supplemental for legacy recovery heuristics. | Pass the completion's `expectedCount` to the helper. After requiring settled status and visible output, recognize the formal backend partial receipt before applying the expected-count heuristic. Keep legacy partial-recovery checks subject to the existing count comparison. Test the same formal response both with `expectedCount=2` and with the count omitted. |
| Photography may select an earlier, certified winner after the latest provider attempt for that role failed, but the role terminal summary keeps the latest failed status/error and marks the project incomplete. | V3 Product role projection. The exact preferred output plus its own eligible inspection/resolution/evidence receipt determines the effective final role; append-only `specialized_role_execution` and retry records remain the authority for attempt history. | Resolve the winning inspection and its output/asset binding first. Only when that exact winner is in `_public_final_delivery_projection`'s eligible output and asset sets should the projected role take generated/certified status and clear active error fields. Derive `missing_role_keys` after that resolution. Preserve the failed retry in raw attempt history. Pending or ambiguous winners must remain withheld. |

### 8.2 Required regressions and non-goals

1. Node VM: a settled generated job with one visible/formally eligible image and `final_delivery.partial_delivery=true` must show “已交付 1 张合格图片” both when `expectedCount=2` reaches completion and when it is omitted. Include a guard proving completion forwards an explicitly supplied count.
2. Offline Photography flow: produce three initial role outputs where one retryable review failure triggers retry; on that retry, the provider fails for a role whose old output was eligible, while the other roles succeed and pass review. The final task, role summary, `asset_series`, final delivery, and Project outputs must contain all three winning outputs; the role summary must bind the old candidate's pass evidence and show generated/certified. The raw latest-attempt record must still show that provider failure and retain candidate lineage.
3. Preserve existing permanent role failure behavior: if a role has no eligible previous winner, it remains incomplete and delivery stays blocked.

No public schema, new status framework, retry policy, review threshold, provider behavior, historical cleanup, real provider/model call, deployment, or V1/V2 edit is in scope.

### 8.3 Verification and release gates

Add both regressions first and record their failing baseline result. Then implement the bounded corrections, run focused tests and the affected suite, freeze the exact candidate, and obtain an independent read-only A1 audit. Integrate/push only after exact-main tests and audit pass. This follow-up request does not itself authorize VPS deployment; no remote action is part of this correction.

### 8.4 Bounded implementation and verification

Both new regressions failed against the unmodified `5a249d60` baseline:

- Desktop formal-partial Node VM case returned `failed` instead of `completed` with the one-image partial-delivery notice.
- Three-role offline Photography flow returned `blocked`, although the review package had three eligible outputs and Project output storage had all three winners.

The desktop helper now accepts the formal backend partial receipt before its legacy expected-count inference, and `completeV3GeneratedJob` forwards its request `expectedCount`. The Node regression covers both an explicit count of two and an omitted count and observes the forwarded helper argument.

Photography role projection now consults the existing `_public_final_delivery_projection` output/asset sets. When the role's exact preferred inspection belongs to those eligible sets, the effective public role is generated from that winner and its receipt, with attempt-local failure fields omitted from the winner projection. Raw `specialized_role_execution` is left intact and continues to retain the latest provider failure and previous candidate lineage. A permanent failure without an eligible earlier winner remains blocked.

Verification on the isolated feature worktree:

- Photography mainline and production-activation suites: **21 passed**.
- Affected cross-module Python suite from §7.9: **342 passed in 354.71s**, including the browser cases present in that command.
- Desktop terminal Node VM: **5 passed**.
- JavaScript syntax check and `git diff --check`: passed.
- VPS release runtime guards (`tests/test_vps_release_runtime.py`): **7 passed**.
- The new red/green regressions were also run individually; each failed before the implementation and passed afterward.

No actual image/model provider, external API, GitHub push, or VPS deployment was used. Independent A1 review of the exact frozen diff passed; exact-main integration acceptance and any subsequent release remain separate gates and are not claimed here.

### 8.5 Independent A1 review receipt

An independent read-only A1 audit of the frozen §8 candidate returned **PASS**. The auditor found no blocking issue in the two fixes, checked that only the five scoped files changed, and confirmed that the permanent-failure/no-eligible-winner path remains blocked. The auditor independently ran the Node VM suite (**5 passed**), the retry-provider-failure and permanent-role-failure Photography tests (**2 passed, 13 deselected**), and `git diff --check`. The 342-case affected Python suite, 21-case Photography suite, JavaScript syntax check, and 7 release-guard tests in §8.4 are author-run evidence and were not rerun by the auditor.

Frozen source/test SHA-256 values checked by the auditor:

| File | SHA-256 |
|---|---|
| `alchemy_creative_agent_3_0/app/product_api/service.py` | `0BEFBF42083AB85E2ED7AF48597C6ABC9843380B93C74A9C891E64EDDA119BFA` |
| `alchemy_creative_agent_3_0/tests/test_v3_photography_mainline_004.py` | `30444CE8809F76322D161260C0B255C7BCE45F43E9A53991CC54B405C3C270C6` |
| `src_skeleton/app/static/app.js` | `57766E1254ADE0DF809EA2327EF71F5E98C9C0E551C7F90DB8640A82179354CC` |
| `tests/v3_frontend_terminal_contract.test.mjs` | `47558E7C4A65C339FE45EC1BE3C13343F3F8979A91FCDF795E8B948D03D46B7A` |

The auditor's Doc337 input had SHA-256 `6F8D4910DA15157BDFA52F8896FF6567B7752CF36493E213D8670C8B9AB049B1`; this receipt is appended afterward, so the current document hash necessarily differs. **ROUTE_UNVERIFIED:** no real HTTP dispatch was made; the Photography regression uses the service-level trusted continuation seam, and the route-handler-to-service link was checked statically. Browser DOM/toast wiring was not separately exercised by the auditor. No real model/image call, deployment, or VPS state change occurred. Integration/release acceptance remains separate from this isolated feature-worktree PASS.

## 9. Mobile partial-delivery notice and live image check

### 9.1 Correction model

Observed mismatch: the mobile generation path treats a successful terminal job with one formally eligible output as ordinary completion, even when `metadata.final_delivery.partial_delivery=true` says another requested image was held. The image set is correct; the missing behavior is an honest terminal notice.

Authority: the existing backend `metadata.final_delivery` projection. A formal partial notice requires `partial_delivery=true`, automatic delivery available, and a positive `final_delivery_output_count`. Keep terminal status and visible outputs unchanged. For the formal partial case, show the exact eligible count and state that remaining requested images were withheld or require manual confirmation. Ordinary full success, review-held delivery, and terminal failure keep their current messages.

Minimal fix: add a small V3 mobile notice helper beside the existing final-delivery projection, use it in both progress and status text after terminal failure/review-held checks, and test it with the backend response shape. No backend/schema change, shared status framework, or V1/V2 change.

### 9.2 Regression and acceptance

Add a Node VM regression that feeds a terminal `generated` payload containing two reviewed outputs, `partial_delivery=true`, automatic delivery enabled, and a final-delivery count of one. Assert the production mobile notice helper reports one eligible image and that the mobile completion path uses that message for progress and status. Also assert full delivery and review-held states do not get mislabeled partial.

After regression passes and an independent A1 review accepts the exact candidate, run one real V3 image request from this source revision using the Doc336 boundary: one isolated test project/job, `require_real_images=true`, hybrid pixel review requested, no uploaded assets or Brand Memory update, maximum one requested image, preserve the evidence folder, and no deployment or cleanup. Require a real provider route plus a verified pixel-review receipt and `final_delivery=ready`; otherwise record the exact gap and do not claim complete live visual-review acceptance. This one image verifies the generation path only; it is not a live test of the mobile browser's rendering or every generation mode.

### 9.3 Implementation, independent review, and real image receipt

The mobile helper now reads the formal `metadata.final_delivery` projection and returns a partial-delivery notice only when the backend explicitly marks partial delivery, automatic delivery is available, and the eligible count is positive. The terminal completion path uses that message in both progress and status text, after failure and review-held handling. It does not change output rendering or selection.

Regression results on the exact candidate:

- Red baseline: `node --test tests/v3_mobile_terminal_contract.test.mjs` failed before the helper was added.
- Node terminal suites: **7 passed** (`tests/v3_frontend_terminal_contract.test.mjs` and `tests/v3_mobile_terminal_contract.test.mjs`).
- Mobile JavaScript syntax check: passed.
- V3 frontend generation-mode Python contract: **11 passed**.
- `git diff --check`: passed.

An independent read-only A1 reviewer returned **PASS** for the mobile change. The reviewer verified that the partial notice uses the backend's formal final-delivery authority, that terminal failure and review-held branches retain precedence, and that output rendering is unchanged. The reviewer ran the mobile Node regression (**2 passed**), `node --check`, and `git diff --check`. The combined 7-case Node suite and 11-case Python suite above were run by the implementation agent, not independently by the auditor. Frozen A1 hashes:

| File | SHA-256 |
|---|---|
| `src_skeleton/app/mobile_static/mobile.js` | `3AF5917284A5D7A0F880EF8E601969A6B127D79FCC645EED0F3E3B461202DDE9` |
| `tests/v3_mobile_terminal_contract.test.mjs` | `1D9DA89B41FE9D29569FFD5E0B1647878CD7BDC197F9DF6148F23D66DF81D4FE` |
| Auditor's Doc337 input | `C8E42A3CBCD5179E620FCAB8198BC0311CFC6AA2E85BE4AE5F81433E394DDDC9` |

One real image was generated from the feature worktree before integration. No mock output was used. The runtime read the existing local `.env` in process only; no secret value was printed or copied. The run created one isolated project and one job, requested one image with `require_real_images=true`, disabled visual retry, used no uploaded assets, made no selection or Brand Memory update, and made no deployment or cleanup.

| Check | Result |
|---|---|
| Source under test | `codex/v3-result-consistency-remediation` at `fc8dd60801119537331ff6bdc78692b56dd7c72e` plus the mobile working-tree change reviewed above |
| Job / result | `job_0615a4ed3e`, status `generated`; final delivery `ready`, automatic delivery available, 1 reviewed / 1 delivered |
| Provider | `openai_gpt_image`, model `gpt-image-2`, strategy `default_image_provider`; mock flag false |
| Output | `v3_output_34c91ca32ddf435bbdb9`, 1024×1536 PNG, 2,102,349 bytes, SHA-256 `a3778e97f67e82e5b16de39ddc2ff5f10785187859757086f88b5d7a1087d1af` |
| Review evidence | A project visual-review event was persisted, recommended output set contains the same output, and durable closure receipt is `complete`; however, the event's `inspection_count` is null and a verified hybrid pixel-inspection status is not recoverable from durable evidence |
| Human visual check | Lamp, ivory ceramic, brass stem, limestone plinth, and natural interior are present; no visible text/logo or obvious rendering defect |
| Evidence root | `C:\Users\T14S\AppData\Local\Temp\alchemy-v3-mobile-terminal-real-774529aa`; image, project records, closure, and `acceptance_receipt.json` are preserved |

The real-provider generation and ready-delivery checks pass for this single output. The durable record does **not** prove that a hybrid pixel inspection completed, so this run is not claimed as full live visual-review acceptance. No mobile browser DOM/toast session was run; mobile behavior is covered by the actual-helper Node regression and source review. The real image check does not cover other generation modes or V1/V2 paths.
