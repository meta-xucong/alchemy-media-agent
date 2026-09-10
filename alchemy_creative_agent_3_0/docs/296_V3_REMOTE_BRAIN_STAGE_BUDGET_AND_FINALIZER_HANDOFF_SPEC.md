# V3 Remote Brain Stage Budget and Finalizer Handoff Integrity

Status: implementation complete; controlled real-image acceptance and release
verification are recorded below.

## 1. Scope

This is V3 foundation transport/runtime work. It covers the shared remote
Brain execution budget used by General Template and professional templates
before any renderer/provider operation. It does not change prompt ownership,
visual quality thresholds, template deliverable maps, or the selected Brain
model/provider. It also closes two adjacent foundation-boundary defects found
by the independent code audit: output-limit exceptions were allowed to carry
the default JSON-parse flag, and an ordinary Generate request could re-enter a
blocked, result-less planning receipt.

The same audit found a second, independent activation-boundary defect in the
General multi-output path. The runtime froze a server-owned variation contract
requiring `suite_direction`, but the remote Brain's typed intent could still
omit or downgrade that capability before the local activation planner ran. The
Product API then assumed every local activation failure carried a remote Brain
receipt, so the safe local failure could be lost during persistence. This
revision repairs that exact runtime-to-planner and public-projection boundary;
it does not make `suite_direction` globally required or add professional
deliverable logic to General Template.

The triggering validation was the same original adult-woman supermarket and
beverage-aisle direction used by Doc295. The corrected source projection and
typed capability routing reached the remote Brain, but the run stopped before
image generation with:

- `llm_used=true` and `fallback_used=false`;
- `remote_brain_stage=provider_prompt_finalize`;
- a `read_timeout` after only `65.379` seconds remained;
- the shared `520` second logical budget reported `exhausted`;
- no image Provider request was started.

This evidence means the upstream Brain route was reached and the fail-closed
boundary worked, but the local stage-budget guard did not preserve its own
declared finalizer handoff window. The audit also found that the public
diagnostic projection dropped safe serialization facts and that Product API
Generate could overwrite an earlier planning failure with a second failure.

## 2. Theory-first correction model

### Intended behavior

For an enforced real-image request:

1. Brain planning may use only the planning portion of the shared logical
   budget.
2. Streaming progress grace may extend a planning transport only inside that
   planning portion.
3. A fixed handoff reserve remains available for the canonical finalizer.
4. The canonical finalizer must complete before any image Provider request is
   permitted.
5. If the budget or finalizer fails, the job blocks with safe lifecycle facts;
   it must not invent a local prompt, silently shorten the user direction, or
   start a partial generation.

### Observed mismatch and owning layer

| Mismatch | Owner | Cause |
| --- | --- | --- |
| Planning could consume the finalizer reserve while tokens were still arriving | shared Brain provider transport | `_effective_timeout_seconds()` subtracted the reserve from the hard timeout, but `_call_with_timeout()` used the full logical deadline as its progress-grace ceiling |
| Finalizer received only the residual 65-second window | shared Brain budget boundary | repeated semantic progress could keep extending the planning worker up to the full execution deadline |
| No image was emitted | Product API / provider gate | correct fail-closed behavior; this is evidence to preserve, not a defect to bypass |
| Output-limit receipt could claim JSON parsing had started | Brain provider exception contract | BrainOutputTruncated inherited BrainInvalidJsonResponse's parse-started default |
| Ordinary Generate could probe a blocked plan | Product API lifecycle boundary | the generate path cleared failure metadata before entering the runtime without requiring an explicit continuation contract |
| Blocked status hid safe serialization facts | Product API public projection | runtime preserved the typed receipt, but Product API projected only transport and budget diagnostics |
| Frozen General multi-output contract was not enforced by the local planner | ScenarioRuntime activation boundary | Brain intent could omit or downgrade `suite_direction` even though the runtime had already frozen it as required |
| Local activation failure could raise while persisting its public status | Product API persistence boundary | persistence indexed `remote_creative_brain_outcome` unconditionally although capability failures have no remote receipt |

The upstream Aiself/Brain endpoint remains an external dependency. Its slow
response is allowed to cause a bounded block, but it must not defeat the local
handoff invariant.

The current activation defect had a different signature: the Brain returned a
valid semantic plan (`llm_used=true`, `fallback_used=false`), but the local
activation planner rejected it with
`general_variation_suite_direction_not_active`. The owner was the shared
ScenarioRuntime activation boundary, not Aiself. The frozen runtime contract
already carried `variation_execution_contract_enforced=true`, General Template
identity, and an effective image count greater than one; the planner simply did
not receive that server-owned requirement in typed form.

### Authority decisions

- The shared logical deadline remains the transport authority.
- The stage-aware planning ceiling is the authority for progress grace when a
  finalizer reserve applies.
- The remote Brain remains the only semantic author of renderer prompts.
- The existing one-shot recovery policy remains bounded by the same budget.
- Output-limit failures are transport-boundary failures and always report
  json_parse_started=false and json_parse_completed=false.
- A blocked job without a PlanningResult or GenerationResult is terminal for
  ordinary Generate. Only an explicit server-owned resume path may re-enter
  it; the first Body MCP planning-required receipt remains a dedicated
  fail-closed exception.
- Public serialization diagnostics may contain only the versioned safe
  schema, stage, bounded attempt count, recovery booleans, and parse booleans.
- The runtime-frozen multi-output contract is authoritative for
  `suite_direction` only when all of these conditions hold: the scenario is
  `general_creative`, the template is `general_template`,
  `variation_execution_contract_enforced=true`, and the effective requested
  image count is greater than one. Under that narrow contract the runtime
  promotes or inserts `suite_direction` as required and removes a contradictory
  remote rejection; the Brain remains the creative author of the suite.
- A local capability-activation failure is projected as the stable public
  `capability_activation_blocked` lifecycle category. Internal activation
  codes and raw exceptions remain private, and persistence attaches a remote
  receipt only when one actually exists.
- No retry, prompt truncation, threshold relaxation, or local creative
  fallback is added to make a real run appear successful.

## 3. Minimal complete repair

1. Compute the plan/generate hard timeout and its absolute stage ceiling from the
   same budget snapshot.
2. Pass that ceiling into the outer transport deadline guard.
3. Keep the full logical deadline as the ceiling only for stages without a
   reserved downstream handoff, including the canonical finalizer itself.
4. Make the output-limit exception enforce its pre-parser state and project
   safe serialization receipts through Product API.
5. Make ordinary Generate return the existing blocked planning receipt without
   clearing metadata or entering ScenarioRuntime; preserve explicit MCP/review
   continuation paths and the first Body MCP planning-required receipt.
6. Add deterministic regression tests proving semantic progress cannot cross
   the reserved handoff and that existing no-reserve grace behavior remains
   intact.
7. Bind the runtime-frozen General multi-output variation contract into the
   typed activation intent immediately before planning, and include the same
   exact predicate in required-capability validation. Keep the binding out of
   single-image General jobs and specialized template policy.
8. Project local capability activation failures through the Product API's safe
   lifecycle schema and persist that schema without indexing a remote receipt
   that is not present.
9. Re-run the full Doc295 offline matrix, then repeat one guarded local
   real-image run with the exact original prompt and inspect the prompt
   receipts, module activation, provider request boundary, and pixels.

## 4. Non-goals and safety boundaries

- no change to Aiself credentials, endpoint, model, or reasoning policy;
- no local prompt author or keyword-based prompt acceptance;
- no reduction of Brain output requirements or visual review thresholds;
- no bypass of canonical prompt sign-off;
- no deletion or cleanup of prior validation evidence;
- no deployment until the candidate SHA passes offline audit and controlled
  real-image validation.
- no change to the provider's existing 1024x1536 compatibility canvas mapping;
  the acceptance target here is activation, prompt preservation, generation,
  and review closure.

## 5. Acceptance evidence

The final record must include the changed files, independent read-only audit,
focused and broader test results, exact prompt hash and length, local real
run outcome, finalizer/provider boundary facts, visual inspection, commit SHA,
GitHub push verification, and governed VPS release/health verification.

The implementation must preserve General Template neutrality and the Doc295
typed-product-fact boundary while repairing only the shared Brain transport
budget, activation, and lifecycle/projection boundaries.

### Independent audit conclusion

The read-only audit traced the failure from the frozen project contract through
Brain planning, typed intent, capability planning, provider entry, and public
status projection. It found no evidence that Aiself had dropped the user's
meaning in the accepted run. The decisive pre-fix sequence stopped after
`activation_plan_build_call`; no image Provider request was started. The
minimal correction therefore belongs in ScenarioRuntime and Product API, not
in prompt keyword patches, provider retries, or a new General Template
deliverable map.

The audit also checked the neighboring finalizer-budget, output-truncation,
blocked-Generate-reentry, typed profile, canonical prompt, review, and output
projection paths. Existing fixes remain covered by their focused regression
sets, and the new activation bridge is guarded by the exact four-condition
predicate above.

### Current deterministic evidence

The final post-audit focused groups pass as follows:

- Product API minimal UX and lifecycle persistence: 47 passed;
- shared capability, constraint/review, provider output, Product API, and MCP
  handoff extension: 287 passed;
- Brain/provider timeout, adapter, transient recovery, Doc175, and provider
  evaluation coverage: 93 passed with the global remote-disable test guard;
- the declared-DeepSeek availability case: 1 passed separately with that
  guard removed.

The offline guard intentionally makes the configured DeepSeek availability
case false; it is not counted as a product failure. A larger Doc270 collection
remains unavailable in this local environment because its legacy transitive
fixture imports playwright. The direct static frontend collection also retains
two pre-existing cache-busting expectation mismatches against the runtime
`__STATIC_APP_VERSION__` placeholder; neither file is in this repair scope.

### Controlled local real-image acceptance

The exact original user direction was loaded losslessly from
`.media_storage/v3_projects/project_f49cb9b5da/project.json`:

- UTF-8 source length: `2196` characters;
- source SHA-256: `f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7`;
- evidence root:
  `.controlled-validation/doc296-local-real-20260910-final-fix`;
- project/job: `project_1cc7cdc531` / `job_58b216ca33`;
- planning/generation receipts:
  `planning_result_53c6d58620` / `generation_result_53c6d58620`;
- asset pack: `asset_pack_271d7029c5`.

The patched local service completed the guarded path through
`semantic_plan_returned`, `semantic_plan_schema_validated`,
`remote_brain_requirement_validation_returned`,
`professional_task_profile_bind_returned`,
`activation_plan_build_returned`, frozen-capability validation, constraint
ledger, execution envelope, and canonical finalizer before the provider call.
The job finished `generated` with two candidates and two delivered outputs.
The active capability dependency order was:

```text
visual_grammar -> universal_visual_quality -> commercial_quality ->
human_realism -> asset_understanding -> reference_inventory ->
reference_channel_policy -> portrait_identity -> product_identity ->
suite_direction
```

The runtime-frozen contract recorded
`variation_execution_contract_enforced=true`,
`variation_execution_mode=delivery_suite`, requested count `2`, and
`variation_execution_suite_direction_authoritative=true`. `suite_direction`
was active as `required` with reason
`runtime_bound_variation_contract`. This proves the previously omitted module
now survives the full Brain-to-planner boundary.

Both canonical provider prompts were sourced from the remote Brain and kept the
user direction semantically lossless. Their final prompt receipts were:

| Output | Prompt length | Prompt SHA-256 | Provider audit |
| --- | ---: | --- | --- |
| `v3_output_3fd1048c...` | 595 | `e39f950e2badb81023c54763431d01c8bb95a4bd082d6c2a6bee27241c397558` | `user_direction_lossless=true`, semantic status `preserved` |
| `v3_output_eaf678924...` | 466 | `ff5e672b51bab7c761cdcb6cd47a70be57eba72922d0de6d80636bc83e333a17` | `user_direction_lossless=true`, semantic status `preserved` |

For both outputs the prompt audit reported source `remote_brain_canonical`,
zero internal-guidance chars after canonical materialization, and no budget
warning. Negative constraints were embedded in the canonical positive prompt,
as required by the current provider materializer; no local creative fallback
was used.

Provider/review closure passed: two provider candidates, two quality-review
reports with `status=pass`, two visual inspections with `status=pass`, both
outputs recommended, no hidden outputs, no auto-retry executed, and a complete
review-evidence receipt. The user-facing review summary reported no clear
visual issue.

The delivered pixels were visually inspected as a coherent two-image set:
the first is a wider full-body crouching supermarket aisle view; the second is
a closer knees-up/detail view. Both preserve the adult East Asian woman,
beige cardigan, black lace skirt, black heels, black quilted chain bag, amber
bottle held with both hands, red warehouse shelving, labels/price context,
green EXIT sign, concrete floor, phone-camera realism, warm skin against cool
store lighting, and anti-plastic texture direction.

| Output | Local file | Dimensions | SHA-256 |
| --- | --- | --- | --- |
| 1 | `.media_storage/v3_outputs/v3_output_3fd1048c1fe741f98b03/original.png` | `1024x1536` | `97c014f066ce9d41a5b8a92eaeaac52eac149d46c9dbe271c9bdaafa2726118f` |
| 2 | `.media_storage/v3_outputs/v3_output_eaf6789245ac494c80d5/original.png` | `1024x1536` | `d908e703ffeae4de89fa34fb92a11e8d9ca3987cb34a430a6e82b2439b0ba358` |

The earlier 65-second finalizer block and the pre-fix activation block remain
append-only evidence under `.controlled-validation`; neither was overwritten
or treated as a successful run.

### Release verification

The candidate implementation commit was pushed to GitHub and deployed through
the governed release-layout script:

- candidate GitHub SHA: `1a1ac3168692b96682569037344edb467f42afc6`;
- GitHub `origin/main`: verified at the same SHA;
- VPS release path:
  `/opt/alchemy-media-agent-releases/v3-release-governed-20260910T031333Z-1a1ac3168692`;
- VPS release worktree HEAD: verified at the candidate SHA;
- release worktree status: clean;
- all three services (`alchemy-v2-api.service`,
  `alchemy-v2-worker.service`, and `alchemy-v2-sync-worker.service`):
  `active`;
- running service cwd for each unit: the candidate release's
  `custom_media_agent_2_0` directory;
- local `/healthz`, local `/api/v2/health`, and public
  `https://alchemy.aiself.vip/api/v2/health`: all returned HTTP success and
  the expected V2 isolation payload.

The remote repository's historical `/opt/alchemy-media-agent-repository`
main worktree reports pre-existing deletion entries; it was not modified or
used as the release truth. The clean detached release worktree, its symlink,
and service cwd are the governed runtime authorities. After this evidence
appendix is committed, the same release procedure is rerun against the final
GitHub `origin/main` SHA so the VPS remains exactly aligned with the final
documentation commit.
