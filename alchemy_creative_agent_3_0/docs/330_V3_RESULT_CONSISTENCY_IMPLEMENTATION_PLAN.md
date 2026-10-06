# Doc330 — V3 Result Consistency Implementation Plan

Status: **PASS — Phases A–D and the user-approved Project Mode admission follow-on passed inclusive regression and current-snapshot A1 review.** This closes the local implementation scope only; real-provider validation, commit/push, merge, and deployment remain separate gates. Follow repo `AGENTS.md`: one writer owns a feature branch/worktree; keep the unique main checkout at `origin/main`; never edit another worktree’s branch.

Baseline and correction authority: Doc328 and Doc329.

## 1. Execution strategy

Use one dedicated feature branch/worktree for the seven related corrections because the three delivery defects must converge on one output-scoped authority. Do not parallelize work on the shared `service.py`, public contracts, result selection, or delivery helper. If the patch is later split into independent branches, coordinate first and freeze the shared contract before dispatch.

Before coding:

1. Confirm project root is on `main`, equals `origin/main`, and has no unrelated tracked changes. Preserve any existing untracked files.
2. Create a feature branch/worktree based on current `origin/main`; record the exact base commit and allowed write set.
3. Re-read the relevant source and tests at the new baseline. This plan’s source line numbers refer only to `1a66b245` and must be refreshed if the base has advanced.
4. Write the correction model from Doc329 into the issue/task ledger, including explicit stop conditions for any contract conflict.
5. For each issue, add or modify a failing deterministic regression before the owning code change.

## 2. Dependency graph and order

```text
Phase A: R4 desktop terminal classification ─┐
         R5 OpenAI default endpoint          ├─> focused regression/audit
         R6 Anthropic version header         ┘

Phase B: R1 winner + source review evidence
              ↓
         canonical per-output eligible set
          ├─> R3 direct formal selection
          ├─> R7 formal E-Commerce export
          └─> Project/status consistency
              ↓
Phase C: R2 selected-only Brand Memory persistence
              ↓
Phase D: integrated regression + independent A1 audit
              ↓
Any later user-authorized real/provider/deployment gate (not implied here)
```

The sequence follows the user’s preferred priority: R4/R5/R6 first; R1/R3/R7 as one result-consistency group; R2 last. R2 comes after formal selection semantics are fixed, so the persistence boundary can consume the authoritative selected eligible set.

## 3. Phase plan

### Phase A — isolated transport and desktop defects

**Phase A acceptance evidence (2026-10-06): PASS.** Added fail-first tests, then completed bounded fixes. `tests/test_v3_frontend_generation_mode_contract.py` plus `alchemy_creative_agent_3_0/tests/test_v3_llm_brain_adapter.py`: 66 passed. `node --test tests/v3_frontend_terminal_contract.test.mjs`: 4 passed. `node --check src_skeleton/app/static/app.js` and `git diff --check`: passed. Independent read-only A1 audit: PASS. It noted that malformed base URLs with query/fragment components are not fully structurally rejected; live provider behavior was not tested. No network/provider calls or deployment occurred.

**R4 — desktop terminal result classification**

- Add an executable regression for `failed` and `not_found` with zero outputs through the actual V3 recovery/completion functions.
- Cover `blocked`, partial recoverable delivery, full valid delivery, review-withheld output, and poll recovery.
- Reuse the existing V3 status helpers and backend projection. Avoid duplicating another mobile/desktop state map.
- Success tone requires the corresponding valid delivery condition; a bare terminal response is not success.

**R5 — OpenAI URL resolution**

- Locate the default chat-stream path and the availability predicate.
- Add cases for absent base URL, canonical `/v1`, trailing slash, custom gateway, and full path edge.
- Introduce or reuse one small existing resolver only if required; both availability and transport must consume that result.
- Ensure the final HTTPX URL is absolute and `/v1` is not duplicated.

**R6 — Anthropic version header**

- Add mocked transport interception of the final outbound request.
- Add the repository’s existing version header to the current request builder.
- Assert path, `anthropic-version`, `x-api-key`, JSON content type, and payload; assert OpenAI remains unchanged.

### Phase B — one per-output delivery authority across surfaces

**R1 — retain winning outputs with their evidence**

- First reproduce the A/B flip case against actual merge, winner, projection, and public Project output functions.
- Represent the final delivery set as per-role best eligible outputs from append-only attempts.
- Keep each output’s exact original review inspection/resolution and receipt binding; do not copy one review status over another.
- Verify status, ordinary Project image list, and formal export all expose the same winning IDs.
- Preserve malformed/missing/duplicate evidence fail-closed behavior already required by Doc321.

**R3 — direct formal selection**

- Use the existing exact eligible candidate/output set from the canonical projection.
- Explicit mixed eligible/ineligible request: reject the whole selection before any persistence or memory write.
- Unknown ID and zero match: no `selected` success.
- Empty request: select eligible only.
- Preserve explicit unreviewed candidate browsing as a non-delivery path only where existing contracts allow it; do not elevate it to final output.

**R7 — E-Commerce export**

- Determine from current route/contracts whether `export_job` is formal delivery manifest or history. Under the current route name/response, formal file entries must use the canonical eligible winner set.
- Preserve the actual review disposition per file. Never rewrite `fail_final` as `ready_for_manual_review`.
- If the existing product needs review history, retain it through its existing history surface or explicitly separate/label that manifest scope; do not silently mix failed outputs into formal export.
- A zero-eligible job must not yield an apparently deliverable file set. `metadata_ready` may remain packaging metadata status only and cannot signal approval.

### Phase C — Brand Memory write containment

**R2 — exact selected associations**

- Add regression for A and B references with only A selected, including candidate-only and source-asset-only mappings.
- Intersect both accepted IDs and references against selected eligible assets/candidate IDs.
- Remove “candidate_id exists” as a keep predicate and remove both empty-to-all fallbacks.
- No reference match means skip application entirely; keep Project Mode’s current automatic-update-off behavior.
- Test `apply_memory_update=False`, explicit opt-in, and that failed selection makes no durable write.
- Historical contamination, if any, remains a separate read-only inspection; this phase does not clean existing profiles.

### Phase D — integrated closure

- Run every focused suite named in Doc331, then the repository’s required broader relevant suites.
- Review all diffs and statuses for scope leaks, temporary files, generated artifacts, V1/V2 edits, contract changes, and provider/network side effects.
- Obtain an independent read-only A1 audit against the exact frozen diff, tests, and evidence.
- If the audit fails, correct only the bounded finding, freeze a new revision, rerun affected regressions, and re-audit that revision.
- Only after all required code-phase gates pass may the mainline integrator consider integration. Follow repository commit/push policy and current explicit user authorization.

## 4. Expected write set

Allowed only as supported by a failing test:

- `alchemy_creative_agent_3_0/app/product_api/service.py`
- `alchemy_creative_agent_3_0/app/project_mode/service.py` only if the ordinary Project output projection fails the cross-surface invariant after the core Product API fix.
- `alchemy_creative_agent_3_0/app/llm_brain/providers.py`
- `src_skeleton/app/static/app.js`
- Focused tests under `alchemy_creative_agent_3_0/tests/` and existing root frontend-contract test locations.

### User-approved scope addendum — explicit E-Commerce reuse of a saved product reference (2026-10-06)

The user approved closing the pre-existing `test_project_mode_accepts_ready_saved_product_reference` gap after the seven-issue implementation. This is a bounded Project Mode admission correction, separate from R1–R7; it does not add a general cross-template inheritance rule.

- On an explicitly submitted E-Commerce job only, an active project-owned uploaded reference whose canonical `use_policy` is `product` may be reused even if it was saved while the project used General.
- Revalidate the exact project association and current V3 upload record/readiness/product role at that E-Commerce admission boundary. Establish E-Commerce provenance through the existing trusted Project reference persistence path before reading the canonical E-Commerce product pool.
- Inactive, foreign-project, generated-selected, non-product-policy, missing, non-ready, or wrong-role references must not be admitted. Invalid product references fail closed; they must not silently become a text-to-image job.
- Do not trust client reference metadata as a template binding. Do not change default General generation behavior, public schemas, reference storage schemas, Product API brand-memory behavior, other templates, or global project reference predicates.
- Test the authorized saved-reference flow, explicit E-Commerce boundary, inactive/non-product/invalid controls, and unchanged ordinary General behavior. No migration, live provider call, historical record sweep, or deployment.

This addendum expands the expected write set to permit the smallest necessary `app/project_mode/service.py` admission-path change and focused tests in `test_v3_project_mode.py`. No other Project Mode changes are in scope.

Implementation evidence: at the explicit E-Commerce job boundary, active project-owned uploaded references with canonical Product policy are revalidated through `_persist_job_uploaded_references(..., strict=True)` before canonical product-pool projection. This records server-owned E-Commerce template provenance without changing the broad `_is_ecommerce_product_reference` predicate. Added passing controls for inactive references, non-Product references even with client template metadata, missing current upload records, and unchanged General-job binding.

Any public request/response schema, persistent data model, shared dependency, lockfile, V1/V2 file, or unrelated UI change is outside this frozen write set. Stop and return to Main for an explicit compatibility-impact revision before changing it.

## 5. Per-milestone evidence

For every independently verifiable milestone, attach:

1. The specific failing regression result before correction.
2. The focused passing regression result after correction.
3. `git diff --check` and changed-file list.
4. A short before/after output-ID set or mocked-request transcript with secrets removed.
5. Confirmation that no real image provider, LLM provider, paid call, or deployment occurred.

Test outputs and task scratch artifacts stay out of committed source unless intentionally designed as repository assets.

## 6. Stop conditions

Stop only the affected path and record evidence if:

- Existing Doc321, Doc280/E34, Doc95/96, Doc276, Brand Memory, or public API contracts conflict with the proposed behavior.
- A source review receipt cannot be tied to the exact output/asset identity.
- The fix needs a new public enum/schema, persistent field, migration, wider retry policy, or an undocumented scenario-specific rule.
- A focused fix leaves a second cross-layer mismatch. Apply the repo theory-first escalation and audit the full flow before another patch.
- A test would perform network/provider calls or mutate persistent user data in a way not expressly isolated by its fixture.

## 7. Code-phase completion is not total acceptance

Passing unit and integration tests permits the work to advance to a later acceptance phase only. This packet does not authorize live LLM/image generation, export of real assets, production deployment, or module activation. The total objective remains open until every user-required phase and final integrated acceptance are separately evidenced.
