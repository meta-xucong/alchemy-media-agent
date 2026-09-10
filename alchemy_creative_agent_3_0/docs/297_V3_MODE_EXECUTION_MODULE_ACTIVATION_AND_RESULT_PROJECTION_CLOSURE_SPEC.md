# V3 Mode Execution, Module Activation, and Result Projection Closure

Status: implementation complete; real-provider/VPS revalidation remains a separate acceptance phase

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
| `tests/test_v3_doc297_mode_execution_projection.py` | Regression coverage for all four modes, single-image semantics, frozen-source precedence, recovery storage, role binding, finalizer evidence, and Doc270 privacy |
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

### Remaining acceptance dependency

No new VPS mutation or remote Provider generation was performed in this
documentation/code/test phase. Doc296 remains the latest
guarded real-image acceptance for the original comparison prompt; a new
original-prompt render and VPS deployment should be run as an explicitly
authorized follow-up after this commit is available. A passing unit-test phase
is not a substitute for that visual acceptance: total production completion
still requires canonical prompt comparison, module activation review, pixel
review, commit/push verification, and VPS health confirmation.
