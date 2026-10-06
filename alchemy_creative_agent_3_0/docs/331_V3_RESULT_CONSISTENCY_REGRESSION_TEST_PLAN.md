# Doc331 — V3 Result Consistency Regression Test Plan

Status: **The corrected candidate passes the expanded 338-test affected Python suite, Node VM cases, and VPS release guards. Independent A2 source audit passed for manifest `48682e31dca5ae78c42a9313aebb9108b6d6f1320a7d3f3b87c07ff44951ae76`.** Keep tests deterministic. No real LLM/image provider or network call is permitted in these tests.

Baseline: `1a66b245ce058062eece2c1519e6a10eaf3e55d1`. Read with Docs 328–330 and the existing Doc321 / Doc280 tests.

## 1. Test principles

1. Exercise the real owning function or route handler with controlled fixtures; avoid a duplicate toy implementation of the production predicate.
2. Assert both returned response and absence of side effects: no selected result write, no Brand Memory write, no export item, and no false-success notification as applicable.
3. Bind evidence to exact `job_id`, `output_id`, `asset_id`, candidate, attempt, receipt, and content identity. Never make the test pass by reusing a sibling’s review status.
4. Preserve append-only attempts and review-history visibility while separately asserting formal-delivery filtering.
5. Mock HTTP transport for Brain requests; assert the final URL, headers, and body without dispatching a real request.
6. Use one positive control and adversarial negative controls for each gate.

## 2. R1 — retry winner and review evidence

### Required regression

Create outputs A0/B0 on attempt 0 and A1/B1 on attempt 1. Bind unique output and asset IDs. Supply complete, verified review evidence with:

| Attempt/output | Review | Expected |
|---|---|---|
| A0 | eligible `pass` or `warning`, highest eligible score for role A | Winner for role A |
| B0 | `fail_final` | Not eligible |
| A1 | `fail_final` | Not eligible; must not overwrite A0 evidence |
| B1 | eligible `pass` or `warning` | Winner for role B |

Assert that:

- Best-result preference is `{A0, B1}`.
- Each preferred output resolves to its own original review row/receipt and asset binding.
- The final delivery projection returns exactly `{A0, B1}`.
- B0/A1 remain available only in permitted review/history views and carry their original failure status.
- No code assumes the last retry package is the sole source of all final inspections.
- E-Commerce `review_disposition` remains derived from the exact winner package when superseded attempts remain append-only in OutputStore. A valid immutable output closure binds all current review winners while eligible IDs name the formal-delivery subset; individual output delivery facts follow each image's inspection, while batch state follows the shared delivery projection. Without a matching closure, unexpected extra records still fail closed.
- `user_visible_summary` is recomputed from the selected winner inspections. Assert Product status and Project review-timeline summaries describe the same winner set rather than the latest attempt.

Product status, ordinary Project output, and formal export consumers must each be checked with their real read paths under R3/R7 and integrated acceptance. Do not infer cross-surface equality from this R1 projection test.

### Adversarial closure cases

- Missing, partial, stale, duplicate, or mismatched inspection/receipt for A0 prevents A0 from becoming eligible.
- Two output rows with the same output ID fail closed under existing Doc321 rules.
- A held sibling does not erase an independently certified output.
- A worse unreviewed retry cannot replace a reviewed initial result.
- Existing specialized atomic-batch contracts remain enforced.

The exact equality assertions above are for automatic delivery with no explicit user-selected subset. Test explicit subset selection separately under R3: selected IDs must be an eligible subset of the winner set, and each projection must preserve its existing meaning (eligible/available versus user-selected). Do not force eligibility and user selection to be equal.

## 3. R2 — Brand Memory exact selection

Fixture: proposed update contains accepted assets A/B and two reference records associated with candidate/source IDs A/B. User selects only eligible A.

Assert:

- Accepted set contains only the existing proposed accepted ID for A; it does not synthesize an accepted ID when the intersection is empty.
- `new_reference_assets` contains only the reference bound to selected candidate/source A.
- B is absent from the update passed to `apply_memory_update` and from the durable resulting profile.
- Candidate IDs and source asset IDs both match through their actual existing association fields, not a generated reference record ID.
- A reference carrying conflicting selected `candidate_id` and unselected `source_asset_id` (or the reverse) is excluded; it cannot be accepted merely because one ID matches.
- If no reference matches the selection, the memory update is skipped entirely; no “empty means all” behavior.
- An explicit `apply_memory_update=False` has no write.
- A rejected formal selection has no memory write even if the request also asked to apply one.
- Project Mode normal selection still does not automatically apply Brand Memory; its explicit confirmation route remains independently covered.

## 4. R3 — direct Product API selection

Use one complete review package with a verified eligible A and verified `fail_final` B.

| Request | Expected result |
|---|---|
| Explicit A | Select A only; record that user-selected set is a subset of the eligible winner set. |
| Explicit B | Reject with a stable actionable reason; no `selected_result` or job-state write. |
| Explicit A+B | Reject entire formal selection; do not silently drop B or substitute another image. |
| Empty selection | Default to exact eligible set A only. |
| Unknown candidate/asset ID | Reject; never return successful `selected` with an empty set. |
| Explicit unreviewed candidate when status is `not_evaluated` | Preserve only existing candidate-browsing semantics; assert final delivery remains `not_evaluated`, no certification, no Brand Memory write absent an allowed acceptance path. |
| Entire batch fail/held | Preserve existing job-level withheld/confirmation behavior. |
| Eligible plus manual-review sibling | Permit only A as formal delivery; B remains review-only. |

Assert failed selection leaves both job status/selected result and Brand Memory unchanged. For a valid explicit subset, assert selection-dependent projections do not claim other eligible IDs were user-selected; preserve whether each existing surface reports eligibility or the chosen subset. Run existing Project Mode selection tests to prove its stronger continuity checks and no-automatic-memory behavior remain intact.

## 5. R4 — desktop terminal/polling outcome

Exercise the actual `completeV3GeneratedJob` function through a Node VM harness, passing the terminal payload returned by polling/recovery. Keep `recoverV3GeneratedJob` recovery transport itself mocked; do not create jobs or call providers.

| Polled job | Visible output | Expected UI state/tone |
|---|---:|---|
| `failed` | 0 | Failed/warning or error; never completed/success. |
| `not_found` | 0 | Missing/unrecoverable failure; never completed/success. |
| `blocked` | 0 | Blocked failure/warning. |
| failed terminal | eligible partial set, recovery facts present | Partial delivery warning; show eligible outputs only. |
| `generated`/`selected` with valid full eligible set | Full expected set | Completed/success. |
| Generated pixels but final delivery withheld | Review-held warning; no success tone. |
| Poll initially pending, then complete | Valid complete set | Recovery ends in success only after valid delivery evidence appears. |

Also assert no stale previous job or success notice leaks across recovery sessions.

Chapter 1 harness: `tests/v3_frontend_terminal_contract.test.mjs`. It loads the production completion function and stubs only its browser/project boundaries, then checks failed, not-found, blocked, missing delivery, partial recovery, review-held, and complete delivery states.

## 6. R5 — OpenAI default Chat URL

Test resolver and intercepted outbound request. Expected canonical URLs:

| Configured base | Expected endpoint |
|---|---|
| Missing | Absolute official host with one `/v1/chat/completions` path. |
| `https://gateway.example/v1` | `https://gateway.example/v1/chat/completions`. |
| `https://gateway.example/v1/` | Same, without doubled slash. |
| `https://gateway.example` | `https://gateway.example/v1/chat/completions`. |
| Explicit compatible gateway / path | Preserve configured authority and avoid duplicate `/v1`; define any full-path support from existing configuration contract before coding. |

Assert availability and request construction consume the same resolver; the final URL is absolute; configured custom hosts are not overwritten; HTTPX is not asked to send a relative URL.

## 7. R6 — Anthropic outbound request

Use a mocked transport to capture the final request and assert:

- Path is the existing Messages path.
- `anthropic-version` is `2023-06-01`.
- `x-api-key`, `content-type: application/json`, model, token budget, system text, and user message body are preserved.
- Response parsing remains unchanged.
- OpenAI Chat requests do not acquire Anthropic-only headers.
- No live network or provider credential is required.

## 8. R7 — E-Commerce export and true review state

Test `export_job` and its JSON download payload using canonical job/output/review fixtures.

| Review/delivery state | Formal export expectation |
|---|---|
| All outputs `fail_final`; zero eligible | No formal image file entries; manifest truthfully reports no deliverable set. Review history remains available only in its explicitly non-delivery surface. |
| A eligible, B `fail_final` | Formal export contains only A; history can show B with original `fail_final`. |
| Old A winner and new B winner after retry | Export is exactly `{old A, new B}` and equals status and ordinary Project outputs. |
| Eligible + manual-review output | Only eligible image is in formal export; held output’s history state remains `manual_review`. |
| No real review receipt / `not_evaluated` | No output is represented as certified/formal delivery. |

Assert `ready_for_manual_review` never replaces a persisted `fail_final`, and `metadata_ready` is not used as a substitute for image approval. If a separate history export is retained, assert its label/purpose is unambiguous and it preserves each real outcome.

## 9. Focused test manifest

Re-evaluate names against the implementation base before execution. Expected starting suites include:

- `alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py`
- `alchemy_creative_agent_3_0/tests/test_v3_doc321_review_authority.py`
- `alchemy_creative_agent_3_0/tests/test_v3_project_mode.py`
- `alchemy_creative_agent_3_0/tests/test_v3_doc280_ecommerce_review_status_hygiene.py`
- `alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py`
- `alchemy_creative_agent_3_0/tests/test_v3_llm_brain_adapter.py`
- Existing frontend contract/shell tests that exercise the V3 app bundle; add a targeted executable test if no existing harness calls the actual terminal completion functions.
- A new focused V3 result-consistency test module if the existing suites do not provide a clean owner.

## 10. Implementation evidence (2026-10-06)

- R1/R3/R7 focused review and export suites: **81 passed**, including an offline A/B retry case whose Product status, ordinary Project outputs, formal export files, and generated-asset manifest all equal `{old A, new B}` and preserve each winner's `warning` review status.
- The persistent Project Store test initially failed under this deeply nested Windows worktree because its generated temp-file path was 278 characters. The test helper now places its isolated store under a short system-temp root; the previously failing test passes in isolation.
- The formerly excluded `test_project_mode_accepts_ready_saved_product_reference` failed before its approved scope extension: explicit E-Commerce product truth returned `user prompt` instead of the saved active product upload. After the bounded admission fix, this test passes inclusively.
- Approved follow-on control tests: **5 passed**. Controls cover inactive reference, non-Product reference (including forged client template metadata), missing upload record fail-closed behavior, and preserved General-job behavior.
- Full `test_v3_project_mode.py`: **82 passed**. Broad affected Python suite (all named files in section 9, no exclusions): **338 passed**. Desktop Node VM completion tests: **4 passed**. VPS release guards: **7 passed**. `git diff --check` passed.
- Broad Python command: `uv run --with pytest --with httpx --with pydantic python -m pytest alchemy_creative_agent_3_0/tests/test_v3_post_generation_vision_review.py alchemy_creative_agent_3_0/tests/test_v3_doc321_review_authority.py alchemy_creative_agent_3_0/tests/test_v3_project_mode.py alchemy_creative_agent_3_0/tests/test_v3_doc280_ecommerce_review_status_hygiene.py alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py alchemy_creative_agent_3_0/tests/test_v3_llm_brain_adapter.py tests/test_v3_frontend_generation_mode_contract.py -q` — **338 passed, exit 0**.
- Desktop Node VM completion tests: **4 passed**. `git diff --check` passed. No real provider, network, generated user job, historical Brand Memory scan, or deployment was used.
- Independent A1 review of the current snapshot including the Project Mode admission addendum passed. The inclusive broad suite is **336 passed with no exclusions**; Chapter 5 local code acceptance is complete. The separate Project Mode admission behavior is a user-approved follow-on, not a new R1–R7 finding.
- Independent read-only A2 source audit of the corrected 20-file candidate returned **PASS** for manifest `48682e31dca5ae78c42a9313aebb9108b6d6f1320a7d3f3b87c07ff44951ae76`. The auditor reviewed the recorded test evidence but did not rerun it. Route provenance, corrected-candidate live image acceptance, latest-main rebase/integrated verification, and VPS deployment remain separate gates.

### Approved Project Mode admission follow-on

The user approved a narrow scope extension in Docs 330/334: an explicitly selected E-Commerce job may reuse a still-valid, active project-owned uploaded reference with canonical product policy that was saved while the project used General. The fix and tests are implemented. The formerly excluded `test_project_mode_accepts_ready_saved_product_reference` now passes inclusively; inactive/non-product/missing-upload and unchanged General controls pass. This follow-on is not one of R1–R7 and must be reported separately.

Exact latest verification commands/results:

- `uv run --with pytest --with httpx --with pydantic python -m pytest alchemy_creative_agent_3_0/tests/test_v3_project_mode.py -k "accepts_ready_saved_product_reference or does_not_reuse_inactive_saved_product_reference or does_not_promote_saved_non_product_reference or rejects_saved_product_reference_when_upload_record_is_missing or saved_product_reference_keeps_general_job_binding" -q` — **5 passed**.
- `uv run --with pytest --with httpx --with pydantic python -m pytest alchemy_creative_agent_3_0/tests/test_v3_project_mode.py -q` — **82 passed**.
- Broad affected Python suite listed in §9 — **338 passed, no exclusions**.
- `node --test tests/v3_frontend_terminal_contract.test.mjs` — **4 passed**.
- `git diff --check` — passed (Git emitted only existing LF-to-CRLF working-copy notices).

Do not run the entire suite merely to declare “complete” before the focused tests and integrated surface assertions pass. The implementation handoff should list exact commands, exit codes, and test files actually run.
