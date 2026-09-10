# V3 Mode Execution, Module Activation, and Result Projection Closure

Status: implementation complete; delivery_suite and selection_candidates real-provider acceptance passed; creative_exploration and format_layout_adaptation remain externally blocked in supplementary VPS validation

## 1. Scope and objective

This is V3 shared foundation/runtime closure work. It repairs the boundary
between the frozen Brain/Capability execution evidence and the Product API's
candidate, lifecycle, and public status projections. It also documents the
acceptance boundary between a one-image run and a multi-image mode contract.

The objective is not to make every optional capability active on every image.
The objective is that:

1. the server-owned execution decision is visible and consistent wherever a
   generated candidate is audited;
2. a canonical Provider prompt approved by the finalizer is not represented by
   a stale planning-level `prompt_review=blocked` in the same public lifecycle;
3. General multi-image mode contracts survive packaging and lifecycle/public
   projection;
4. General single-image runs remain valid without an invented variation
   receipt or fabricated role plan; and
5. optional capability differences remain evidence/policy-driven and are
   explained by a compact activation audit rather than forced by keywords.

This does not add a professional deliverable map to General Template and does
not change Aiself, the selected Brain model, Provider routing, image quality
thresholds, or prompt ownership.

## 2. Evidence and observed mismatches

The read-only audit of the VPS project used for the local comparison found six
completed jobs for the same project and source direction. All six carried the
correct requested/effective/continuation mode fields, used the remote DeepSeek
Brain without deterministic fallback, and reached an approved canonical
Provider prompt with complete semantic coverage. The route therefore proved
that the upstream Brain/finalizer path was functioning for those runs.

The remaining mismatches were:

| Evidence | Observed behavior | Owning layer |
| --- | --- | --- |
| Candidate lifecycle records | `mode_execution_policy`, `role_specific_generation_plan`, and `mode_quality_profile` were `{}` even when the frozen execution envelope contained the mode projection | Product API result-to-candidate projection |
| Candidate lifecycle `llm_brain` | `prompt_review.status=blocked` while the canonical Provider prompt was approved/complete | Product API public/lifecycle projection selected stale planning evidence |
| General multi-output candidate roles | A candidate could lose its role recipe or expose the semantic Doc59 role where the existing General contract requires the opaque frozen deliverable binding | Provider per-output role materialization plus Product API output-index projection |
| Repeated same-direction runs | Optional active capability sets differed between runs | Brain typed intent plus evidence-gated optional activation; not automatically a defect |
| One-image mode tests | No variation contract/role receipt | Expected under the General compatibility contract; one image has no set-level role separation |
| Mode semantics | Selection, creative, and format jobs carried distinct provider execution envelopes | Existing mode director/provider path is functioning; projection hid part of its evidence |

The optional-module observation must not be “fixed” by activating product,
scene, reference, or suite capabilities unconditionally. The General policy's
universal baseline and visible-person Human Realism requirement are the stable
foundation. Optional modules require typed intent, evidence, dependency,
budget, and conflict checks. Their absence is valid when the frozen plan says
they are not applicable. The repair exposes the frozen decision and its
requested/rejected evidence so a real omission can be distinguished from an
expected skip.

## 3. Theory-first correction model

### Intended authority chain

The authoritative path is:

```text
remote Brain canonical prompt
        +
server-frozen CapabilityExecutionEnvelope
        -> Provider request/candidate
        -> one Product API projection helper
        -> asset series, candidates, lifecycle, status audit
```

Creative text remains owned by the remote Brain canonical prompt. Capability
activation remains owned by the frozen activation plan and resolved constraint
ledger. Product API is a read/projection adapter; it must not recreate prompt
content or rediscover capability intent from user wording.

### Conflict decisions

1. An enforced job may project mode facts only from the atomic
   `resolved_constraint_ledger.provider_projection.capability_projection`.
   The envelope's outer visual cluster can contain dormant/inactive role data
   and is never a fallback. Legacy/non-enforced records may read one legacy
   visual-cluster source for compatibility, but fields are never mixed across
   sources. A non-empty existing Provider candidate field is retained and is
   never overwritten by an empty fallback; a non-empty mismatch is surfaced as
   a projection conflict.
2. A complete approved canonical Provider prompt is the public final prompt
   review authority. The earlier Brain planning review remains available as
   internal history, but it cannot be the only public status when finalizer
   evidence exists.
3. A General variation contract applies only when the existing four-condition
   predicate is true: `general_creative`, `general_template`, the server-owned
   contract is enforced, and requested image count is greater than one.
4. For one image, mode identity may still be projected, but role separation and
   variation receipt are `not_applicable`; the system must not fabricate them.
5. Optional capability activation is not normalized across unrelated scenes.
   The audit surface reports active, inactive, requested, and rejected IDs from
   the frozen plan/Brain intent; no prompt keyword patch is introduced.

### Minimal complete repair

1. Add one pure Product API projection boundary that reads the frozen execution
   envelope first and recovers safe mode fields only when the authoritative
   source is non-empty.
2. Merge that projection into candidate metadata for asset-series, candidate,
   lifecycle, and mode-review consumers without copying raw prompt text or
   replacing Provider facts.
3. Add a finalizer-aware public `llm_brain.prompt_review` projection. It
   changes only the projected status/source and preserves the original
   planning review as a nested historical value when necessary. Approval
   requires a complete, unique canonical prompt index set exactly matching the
   requested count; an incomplete set remains blocked.
4. Add a compact `mode_execution_audit` and a public-safe activation-state
   projection. The public fields are limited to mode, count, contract status,
   source, activation mode, active IDs, and typed inactive/requested/rejected
   IDs. The richer activation audit remains an internal server-side diagnostic
   helper and is never exposed through ProductJobStatus. Neither surface is a
   creative instruction.
5. Add regression tests for all four modes, multi-image role projection,
   single-image non-applicability, stale prompt-review correction, empty-source
   preservation, and optional activation audit stability.
6. Re-run the focused Product API/Brain/provider matrix, then run a guarded
   real-image acceptance using the original comparison prompt. Inspect both
   the canonical prompt and the resulting pixels before any deployment.

The implementation phase below deliberately stops before a new Provider job:
the code audit identified a read/projection defect, and the existing Doc296
real-image acceptance already demonstrated the upstream Brain-to-Provider
path. A new remote render is an acceptance/deployment action, not an
exploratory debugger for this projection-only fix.

## 4. Non-goals and safety boundaries

- no local rewrite or truncation of the user's prompt;
- no bypass of canonical Brain/finalizer approval;
- no forced activation of optional capabilities;
- no change to the mode director's selection/creative/format semantics;
- no variation receipt for a single-image job;
- no new General Template ecommerce, photography, or campaign deliverable map;
- no changes to existing VPS records during diagnosis;
- no deployment before code audit, focused tests, integrated tests, and guarded
  visual acceptance pass.

## 5. Acceptance matrix

| Case | Required result |
| --- | --- |
| General, one image | Effective mode visible; `mode_execution_audit.contract_status=not_applicable`; no role/variation receipt invented |
| General, two or more images | Frozen mode policy, role plan, quality profile, and variation contract visible in candidate/lifecycle/public projections |
| Selection mode | `micro`, near-neighbor candidate policy, scene change disabled |
| Creative exploration | `broad`, concept-lane policy, scene/concept variation enabled |
| Format/layout adaptation | `layout_only`, format-role policy, scene change disabled |
| Finalizer-approved canonical prompt | Projected `prompt_review.status=approved` with source `canonical_provider_prompts`, only when all requested output indices are present and complete |
| Optional module skipped | Stable required baseline remains active; skip is represented by typed inactive/rejected evidence, not a forced prompt fragment |
| Public response | No raw provider prompt, file path, retry patch, or private execution trace is added by this repair |

## 6. Implementation, audit, and release record

### Implemented boundary

The Product API now uses one projection boundary for candidate, lifecycle,
series, mode-review, output-restore, ordinary status, and Doc270 Phase 3
views. Enforced records read mode facts atomically from
`resolved_constraint_ledger.provider_projection.capability_projection`;
missing or empty frozen projections fail closed and never fall back to a
dormant outer visual cluster. Mode/count audits prefer the frozen envelope,
and missing frozen counts cannot be replaced with stale result counts.

Role recipes are copied only when their `index`/`output_index` equals the
server-owned output position. Raw candidate/asset/package fallbacks are
removed from the mode-review payload when that binding is absent. Canonical
prompt approval requires remote Brain use, no fallback, a recognized finalizer
stage (`provider_prompt_finalize` or the existing
`provider_prompt_professional_capture_resign` terminal stage), complete unique
output indices, and—when enforced—non-empty matching plan, envelope, and
ledger bindings. Character-card slot-delta recovery remains explicitly
non-canonical and cannot be upgraded to approved by this adapter.

General multi-output has two deliberate role identities. The asset-series view
keeps the human-readable Doc59 role (`cover_hero`, `subject_focus`, and so on),
while the Provider candidate carries the opaque
`TemplateDeliverablePlan.deliverable_id` plus its explicit output index. The
Provider still receives the complete role direction; only the lineage key is
opaque. Photography and E-Commerce keep their own specialized semantic role
contracts. Product API accepts either identity only through the same exact
output-index binding and never substitutes an adjacent output's recipe.

The full activation audit remains an internal helper for server-side
diagnostics only. Every `ProductJobStatus` path, including ordinary status,
lifecycle, partial recovery, and Doc270 Phase 3, receives the separate
public-safe activation-state projection containing only activation mode and
capability state lists; plan IDs, fingerprints, evidence IDs, source digests,
and rationale details remain private. A canonical finalizer list without a
known requested count is also blocked for both enforced and legacy records.

### Changed files

| File | Purpose |
| --- | --- |
| `app/product_api/service.py` | Frozen execution projection, finalizer approval gate, role binding, activation audit, and Doc270 public-safe projection |
| `app/generation_router/providers.py` | Restores the General Provider candidate's opaque deliverable binding while retaining full per-output role direction |
| `app/shared_capabilities/visual_cluster/vision_inspector.py` | Settled Vision timeout retry with fail-closed protection for still-running review workers |
| `tests/test_v3_doc297_mode_execution_projection.py` | Regression coverage for all four modes, single-image semantics, frozen-source precedence, recovery storage, role binding, finalizer evidence, and Doc270 privacy |
| `tests/test_v3_post_generation_vision_review.py` | Regression coverage for settled versus uncooperative Vision timeout recovery |
| `docs/297_V3_MODE_EXECUTION_MODULE_ACTIVATION_AND_RESULT_PROJECTION_CLOSURE_SPEC.md` | This correction model, acceptance matrix, and evidence record |

### Independent audit outcome

Rawls and Leibniz independently confirmed the original cross-layer defect was
in Product API result/public projection rather than an Aiself or upstream
Brain prompt-generation failure in the audited VPS records. The iterative
audit also caught and corrected multiple P1 classes: incomplete early-return
coverage, stale result/job overrides, General role identity/index drift,
private activation-audit leakage, and under-specified finalizer cardinality;
canonical approval now additionally requires a known request count.
Meitner's final read-only cross-audit after those corrections returned PASS
with no P0/P1/P2 findings and confirmed that empty enforced ledgers block
stale mode projection, General Provider bindings retain opaque deliverable
IDs, and all ProductJobStatus paths expose only the public activation state.

### Test evidence

The current main worktree passed:

| Command / scope | Result |
| --- | --- |
| `test_v3_doc297_mode_execution_projection.py` | 20 passed |
| `test_v3_project_public_projection.py` | 1 passed |
| `test_v3_doc293_unified_prompt_compression.py` + `test_v3_doc294_brain_source_projection.py` | 39 passed |
| `test_v3_doc295_human_led_suite_and_source_closure.py` | 25 passed |
| `test_v3_llm_brain_adapter.py` | 47 passed |
| `test_v3_mode_aware_role_director.py` | 8 passed, including the General opaque deliverable binding regression |
| `test_v3_general_prompt_deproductization.py` | 16 passed |
| variation compatibility + public projection | 59 passed |
| Product API minimal UX public-state subset | 5 passed, 42 deselected (the prior full baseline was 47 passed) |

The initial combined Doc293/294/295 run also passed 64 tests. A final
post-fix run separately passed 39 Doc293/294 tests, 25 Doc295 tests, and 16
General de-productization tests; variation compatibility plus public
projection passed 59 tests. The local
environment cannot collect the legacy Doc290 suite because its virtualenv is
missing `playwright`; this is an environment dependency failure, not a
product assertion failure. Compileall and `git diff --check` passed.

## 7. Controlled real-provider acceptance (2026-09-10)

The previously incomplete acceptance was resumed after commit
`b6533903877ddd4f4a78e8bef0bf4b56ae6f9756` was deployed to the governed VPS
release. The exact comparison prompt was read from the VPS project's
`project.json` and verified before planning:

- project: `project_200ef57976` (the woman crouching in a warehouse
  supermarket to pick up an amber bottle);
- prompt: 2,196 UTF-8 characters, 5,420 bytes;
- prompt SHA-256: `f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7`;
- generation signal: `v3_user_initiated_generation=true`, so the run could not
  be mistaken for an idempotent replay of an old terminal job;
- job: `job_28e023b228`; planning 268.442 seconds, generation 561.704 seconds;
- result IDs: `planning_result_6b1b5ccc82`,
  `generation_result_6b1b5ccc82`, `asset_pack_856ae3f705`.

The run completed with two requested and two delivery-ready outputs. The
server-owned audit reported `delivery_suite`, requested count `2`, active
contract, and `suite_direction_active=true`. The public-safe activation audit
reported `activation_mode=enforced`, the required baseline plus suite
direction active, and `inactive=[]`; optional portrait identity and scene
continuity were also active for this record. The finalizer produced four
canonical prompt receipts (two initial candidates and two bounded retry
outputs), all approved, complete, semantically complete, and marked
`user_direction_lossless=true`:

| Output | Prompt length | Prompt SHA-256 | Final image SHA-256 |
| --- | ---: | --- | --- |
| initial 1 | 651 | `97d5b506287fe30f6a1d79263bba9c216a9f465ccee49674066abd9369ae6315` | — |
| initial 2 | 519 | `6ef9abc5fd03a0f8bfa547fcbdaf1abe24d76049a0f72817e742af35a74c9dfa` | — |
| retry/final 1 | 687 | `a189376b1e7c7624217b29e4114d0860d415d5e94ac67833c85463859da5d5f2` | `b8a56e2b88a493e8989e5152496401082142b2584d24c5d93e177726c385e0cb` |
| retry/final 2 | 390 | `f1345a40649e9462437998415e09c63e15a43e1ca18413685e1939aea7642e78` | `cc405f54ee4fec03edf84072c91c8be54037ea2047f4c79cdf717842dc84dd0e` |

Both final outputs were 1024x1536, passed hybrid and real-pixel review, had
no detected issues, were recommended for delivery, and made the automatic
delivery surface ready. One bounded visual retry was executed for the initial
composition/uncanny-detail findings; retry records remained append-only and
the public result contained only the two final outputs. Visual inspection
confirmed the requested adult East Asian woman, low crouch, amber bottle held
with both hands, red warehouse shelving, aisle context, bag, heels, and EXIT
sign, with a credible phone-photo look.

The first exploratory POST without the fresh-generation signal intentionally
reused the existing terminal job under the product's idempotency contract; it
was preserved as evidence and excluded from acceptance. The official fresh
signal then created the new job above. This confirms the earlier apparent
"no response" behavior was an invocation/idempotency distinction, not a
remaining Brain or Aiself prompt-loss defect.

The acceptance was executed inside the deployed container with the real
DeepSeek Brain (`deepseek-v4-pro`), real image provider, Vision review, and
V3 storage. `VEYRA_AUTH_ENABLED=false` was scoped to the isolated TestClient
acceptance process only; the running public service remained protected. The
post-acceptance VPS health check reported all three V2 services active, V1
health 200, V2 health 200, and public V2 health 200.

Evidence: `.controlled-validation/doc297-vps-real-20260910/run-output.txt` and
the final-output thumbnails in the same append-only evidence directory.

## 8. Audit correction and rerun gate

The independent final audit found that the first remote run was not yet a
release-grade acceptance receipt. Its compact evidence proved the lifecycle,
counts, review gate, and final delivery, but did not prove the real Brain and
Provider flags, bind each final output to its final prompt and output index, or
bind each output to its mode role. It also reproduced a P2 shadow/legacy edge
case in `_authoritative_mode_execution_projection`: an empty
`provider_projection.capability_projection` could return an uninitialized
local. The minimal correction initializes that projection to an empty mapping
while preserving atomic no-fallback behavior; a focused regression test was
added. The prior remote output remains provisional evidence and is not counted
as final acceptance until the corrected release is deployed and the evidence
is re-collected with these bindings.

The legacy Doc290 collection remains unavailable in the current local
environment solely because its virtualenv lacks `playwright`.

## 9. Vision-review timeout correction model (2026-09-10)

The corrected release was deployed and a fresh real run reached the remote
Brain, the GPT Image Provider, and the shared Vision reviewer. That run
produced real pixels, but one Vision call timed out and the other returned a
valid pixel review without the required Doc276 face-integrity attestation. A
separate fresh run was blocked in Brain planning by an upstream HTTP error;
neither event indicates prompt loss or image-provider substitution. The
records are retained as non-acceptance evidence.

The owning defect is in the shared Visual Capability Cluster review adapter:
`_vision_provider_attempt_limit()` declares two attempts for hard semantic
pixel contracts, while `_vision_model_report()` returned immediately on a
`TimeoutError`. This made the implementation contradict its own bounded
review-recovery contract and needlessly converted a transient Vision outage
into a manual-only result.

The correction authority is the shared review lifecycle, not Brain prompt
composition, Provider rendering, or public projection. A Vision timeout is
safe to retry only after the previous inspection worker has stopped; an
uncooperative worker must remain fail-closed and must not be overlapped by a
second request. Missing, malformed, or `not_verifiable` Doc276 attestations
remain non-certifying and are never relaxed or converted into a pass. The
repair therefore consists of a typed timeout outcome carrying worker-settled
state, a bounded retry only for a settled timeout within the frozen attempt
budget, and attempt provenance in the internal inspection evidence. No retry
creates an image job, changes a prompt, or bypasses the face-integrity gate.

Regression coverage must prove both branches: a settled transient timeout is
retried once and can certify a subsequent valid review, while a still-running
worker is held manually without a concurrent second inspection. Real VPS
acceptance remained pending until a later fresh job had complete
Brain/provider receipts, two exact output bindings, two verified pixel reviews
including Doc276 evidence, and automatic final delivery. That gate was
satisfied by the acceptance record in section 10.

## 10. Corrected release real-provider acceptance (2026-09-10)

The corrected implementation was deployed from commit
`9ef8e91d8ef1694874beb361a8a306c51dbe8219`, verified at `origin/main`, and
the running V2 service resolved to:

`/opt/alchemy-media-agent-releases/v3-release-governed-20260910T131323Z-9ef8e91d8ef1/custom_media_agent_2_0`

The fresh acceptance used the same VPS comparison project and its original
prompt, with `v3_user_initiated_generation=true`:

- project: `project_200ef57976` (the woman crouching in a warehouse
  supermarket to pick up an amber bottle);
- prompt: 2,196 UTF-8 characters, 5,420 bytes;
- prompt SHA-256:
  `f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7`;
- job: `job_a16185ba8d`;
- planning: HTTP 200, `planned`, 353.152 seconds;
- generation: HTTP 200, `generated`, 372.685 seconds.

The server-owned execution contract was `delivery_suite`, active for two
outputs, with `suite_direction_active=true`, frozen projection source
`resolved_constraint_ledger.provider_projection.capability_projection`, and
mode-differentiation review `pass` with complete role coverage. The public
activation projection was `enforced`; its required baseline and optional
intent-driven capabilities were active, `inactive=[]`, and the two roles were
covered. `commercial_quality` appears as an active required baseline even
though it is not part of the optional Brain-requested list; the planner's
baseline authority remains intact.

The Brain/provider chain was real and canonical:

- Brain: DeepSeek `deepseek-v4-pro`, `llm_used=true`, `fallback_used=false`,
  `creative_fallback_executed=false`;
- remote Brain canonical Provider prompts were received and both variation
  execution receipts were signed;
- output 1 prompt: 673 characters, 1,947 bytes,
  `7be12ccae111d0a68b1ab132b4cc4cbc51fff2fa0900a03e23684f27a11cb7d3`;
- output 2 prompt: 466 characters, 1,362 bytes,
  `9c37ecc6e44a43ad3f4176b7f86dd261dbc2e17212d724deb4f8285a5ae6e727`;
- both prompt receipts were approved, complete, and semantically complete,
  with user-direction integrity preserved.

The image Provider was real `openai_gpt_image` / `gpt-image-2`, with one
reference image admitted for each output and pixels received. The two final
outputs were bound to the corresponding prompt and suite role:

| Output | Provider prompt index | Mode role | Review |
| --- | ---: | --- | --- |
| `v3_output_68e5b7d8c9aa41808b72` | 1 | Output 1 / cover hero | hybrid, verified, pass |
| `v3_output_e6604650aaf9404388c3` | 2 | Output 2 / subject focus | hybrid, verified, pass |

Both Vision inspections used one review attempt, passed real-pixel
certification, carried a passing Doc276 face-integrity attestation, and had
no detected issue codes. The review receipt was `complete`; automatic final
delivery was `ready`, with two reviewed and two final outputs and no manual
confirmation requirement. Visual auto-retry remained enabled but executed
zero retries because the accepted outputs passed the shared review gate.

The earlier fresh jobs remain preserved but are excluded from the final
acceptance count: `job_0d117e0235` and `job_6d66023714` stopped before Provider
execution on transient upstream Brain HTTP errors, while `job_8ff5cc5e11`
correctly withheld delivery after a Vision timeout and missing Doc276
attestation under the pre-correction behavior. The latest job demonstrates
that the bounded settled-timeout correction did not weaken the fail-closed
Doc276 gate and that the complete Brain-to-Provider-to-Vision-to-delivery
path now closes successfully.

Evidence is append-only under
`.controlled-validation/doc297-vps-real-20260910/`, including the corrected
acceptance manifest, current read-only review/provider/binding captures, and
the original run output. The helper-level commit field in the original
compact capture was stale; the manifest binds this acceptance to the verified
`origin/main` commit and VPS release path, so no additional generation was
issued merely to rewrite that field.

## 11. Supplementary single-image mode validation (2026-09-10)

To verify that the earlier failures were not limited to the delivery-suite
path, the same original VPS project and exact user prompt were run again with
one requested image in the previously unsuccessful general modes. Every run
used the corrected release `9ef8e91d8ef1694874beb361a8a306c51dbe8219`,
`v3_user_initiated_generation=true`, the real DeepSeek Brain, the real image
Provider, and mock generation disabled. The prompt remained lossless: 2,196
UTF-8 characters, 5,420 bytes, SHA-256
`f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7`.

| Mode | Fresh job(s) | Planning/Brain | Provider pixels | Vision/final delivery | Result |
| --- | --- | --- | --- | --- | --- |
| `selection_candidates` | `job_cf55d0976f` | completed with real DeepSeek; no fallback | received | `pass/verified`, no issue codes; one recommended output `v3_output_94012182189b44c3882d` | technical acceptance passed |
| `creative_exploration` | `job_c8d31c50ea`, `job_98f3267125`, `job_a0d5c89155` | two plans completed with canonical Brain prompts; one stopped on `remote_brain_unavailable` | both completed plans stopped on `non_retryable_provider_failure: provider_timeout` | no pixels, so no Vision or final-delivery acceptance | not accepted in this window |
| `format_layout_adaptation` | `job_10d83db215`, `job_9e9774dd0a` | one stopped on `remote_brain_unavailable`; one plan completed with a canonical Brain prompt | completed plan stopped on `non_retryable_provider_failure: provider_timeout` | no pixels, so no Vision or final-delivery acceptance | not accepted in this window |

The successful selection run preserved the requested mode through the
request, effective mode, continuation mode, and variation mode fields. Its
real-pixel review was complete and verified, which rules out the earlier
mode-field loss and prompt-truncation hypothesis for that path. The two other
modes also preserved their mode fields and produced canonical Brain prompt
receipts when planning completed; their failures occurred at intermittent
remote Brain availability or image-provider transport, before any image was
available for review. Aiself `/v1/models` and minimal DeepSeek chat probes
returned HTTP 200 during diagnosis, but that only proves basic endpoint
availability, not stability for the much longer production request.

These are non-acceptance records, not successful image results. The provider
transport guard correctly treats an unknown request outcome as non-replayable
to prevent duplicate upstream jobs, so each retry was a new fresh job rather
than an unsafe replay of the same request. No new code change is justified by
these records alone: the mode routing and prompt-preservation contract are
observed working, while the remaining failure is an external availability
problem that needs provider/Brain observability and a later guarded rerun.

Evidence: `audit-mode-jobs-current-9ef8e91d8ef1694874beb361a8a306c51dbe8219.json`,
`selection-cf55-review.json`, `selection-cf55-provider.json`, and
`selection-cf55-bindings.json` under
`.controlled-validation/doc297-vps-real-20260910/`.
