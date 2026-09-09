# Doc294 V3 Brain Source Projection and Module Restoration Development Specification

**Status:** implementation complete in the isolated feature worktree; focused audit passed; integrated acceptance pending

**Contract revision:** `v3_brain_source_projection_v1`

**Scope:** V3 foundation prompt-source projection and Brain finalization only

**External systems:** GitHub, VPS, Veyra, Sub2API, MCP, ImageGen and real
production projects are out of scope for this document.

## 1. User requirement

The recent V3 optimizations were intended to improve prompt ownership,
compression, human realism and provider stability. They must not make existing
visual modules ineffective. The required result is:

1. The detailed semantic results produced by the existing V3 modules remain
   effective in the final renderer prompt.
2. The Remote Brain remains the sole author of the final natural-language
   Provider prompt.
3. The Provider receives the exact Brain-approved prompt and does not append,
   trim, regex-match, or locally repair creative text.
4. Prompt compression removes duplication only when the final prompt is truly
   overlong; it must never be used as a substitute for missing source
   projection.
5. The solution is universal across materially different scenes and does not
   introduce a kidswear, ancient-style, portrait, ecommerce, or other narrow
   prompt recipe into shared runtime code.

The key distinction is:

```text
module activation metadata != executable renderer semantics
```

A module is not working merely because its ID, contract, receipt, or structured
profile is present in a job record. Its user-relevant semantic decision must be
available to the Brain finalizer and resolved inside the complete prompt sent to
the image Provider.

## 2. Non-goals and hard boundaries

This document does not authorize:

- Provider-local natural-language concatenation or restoration of the old
  prompt compiler;
- regex, keyword matching, phrase counting, substring checks, or fixed prompt
  fragments as semantic enforcement;
- a minimum prompt length, padding text, or a target character count for its
  own sake;
- changing the image model, route, API credentials, timeout, retry count,
  review score, review threshold, reference binding, output persistence,
  V1/V2, Veyra, Sub2API, frontend, GitHub or VPS;
- adding a second prompt summarizer, a second compression LLM, a second
  Human Realism module, or a scenario-specific prompt branch;
- moving reference ownership into Human Realism or moving specialized
  deliverables into General Template;
- rewriting historical frozen prompts or silently re-reviewing historical
  jobs;
- treating a passing structured receipt as proof that the Provider received
  all required rendering meaning.

## 3. Authority and compatibility model

The following authority order is fixed before implementation:

1. Explicit user intent and server-frozen hard facts.
2. Doc93 reference-channel ownership and prompt ownership governance.
3. Doc94 universal visual capability and anti-overfitting governance.
4. Doc76/77/78 shared foundation quality, visual review and beautiful realism
   authorities.
5. Doc95/96 portrait identity evidence and high-fidelity identity execution.
6. Existing shared capability contracts and Brain planning output.
7. This document's source projection and finalization binding.
8. Doc293's single final-prompt compression policy.
9. Provider transport validation, with no creative text rewrite.

The new source projection is an adapter between existing typed module output and
the Brain finalizer. It does not become a new creative owner. The Brain may
resolve conflicts semantically, preserving the user-owned channels and the
reference ownership ledger. The runtime may validate schema, identity, digest,
cardinality and frozen binding, but may not decide whether a word or phrase is
"good enough" for a visual concept.

## 4. Root-cause timeline

### 4.1 Brain-owned prompt cutover: `91c53bad`

The Brain-owned canonical prompt boundary was introduced for a valid reason:
two independent natural-language compilers could contradict each other. The
Provider then began returning the approved canonical prompt directly and
stopped appending the old local scene, camera, Human Realism and negative
guidance.

The migration was incomplete. The runtime finalization context projected the
Brain's `image_set_plan.shot_plan` and selected typed contracts, but did not
project the complete `prompt_guidance` package or the complete image-set
composition and quality guidance. The old local materializer was removed before
semantic parity had been proven.

**Failure introduced:** modules remained active in planning metadata but lost
their complete renderer-facing semantic path.

### 4.2 Quality/sign-off tightening: `3803b749`, `a26c8c52`, `2e20e6a2`,
`233e913d`

These changes correctly moved more Human Realism, surface materiality, beauty,
facial light and expression decisions into Brain-owned semantic sign-off and
correctly prohibited local checklists or repair suffixes. The error was not the
ownership decision. The error was assuming that a typed contract plus long
system instructions could replace the missing first-pass source projection.

**Failure introduced:** the finalizer was told to author one complete direction,
but was not given all of the previously produced module direction that it had to
preserve. A semantic rewrite therefore had less source material than the old
path.

### 4.3 Lean request and deduplication: `684a8478` and `5f3b9f52`

The planning payload was intentionally made smaller and duplicated Human
Expression guidance was removed from one planning request. This is correct only
when the finalizer receives the complete source once through the right boundary.
The follow-up restored a short Human Realism planning instruction, but not the
complete prompt-guidance projection.

**Failure introduced:** the final result became more dependent on the finalizer
to reconstruct missing semantics from a short `shot_plan` and typed contracts.

### 4.4 Unified compression policy: Doc293

Doc293 correctly separates Brain request payload compaction from final renderer
prompt compression and removes local truncation. However, the initial policy
accepts Brain-declared `prompt_status=complete` and
`semantic_coverage=complete` without binding that claim to the complete module
source. A 312-character prompt can therefore pass `compression_decision=none`
even when the detailed module package was never projected to finalization.

**Failure introduced:** a source-projection defect was classified as a valid
short prompt instead of a missing semantic-source failure.

## 5. Observed evidence and classification

The current controlled local run is evidence for the source-projection problem,
not proof that every short prompt is invalid:

- the final Provider prompt was 312 Unicode characters;
- compression decision was `none` and no compression receipt was issued;
- the Brain planning and finalization path ran, with no local prompt append;
- the Provider received the canonical Brain text unchanged;
- the first Brain result contained a short shot direction, while its typed
  prompt-guidance fields were not fully present in the finalization context;
- the Provider later timed out while waiting for image pixels, which is a
  separate transport/provider issue and must not be used to explain the short
  prompt.

Local historical durable records currently observed in the feature worktree
contain several canonical prompts in the roughly 287-380 character range. That
does not disprove older 2,000-3,000-character prompts from other storage or
legacy paths, and character count alone is not the acceptance criterion. The
acceptance criterion is semantic delivery of the frozen source.

## 6. Module failure matrix

Each row is a separate required audit item. "Repair owner" is the layer that
may be changed. "Do not repair by" is a hard anti-regression constraint.

| Module / capability | Observable failure after the bad optimization | Root cause | Repair owner and minimal repair | Do not repair by |
|---|---|---|---|---|
| Brain planning direction | The first Brain pass contains a usable direction, but the finalizer sees only a short shot direction. | `prompt_guidance` and full image-set guidance are not projected into finalization. | `ScenarioRuntime` source projection plus Brain finalizer input schema. Project the existing frozen fields once, with output binding and digest. | Re-running Brain repeatedly, adding a second planner, or copying text in Provider. |
| Human Realism | Skin, face, hands, contact, expression and camera materiality become generic or disappear. | Human Realism survives as typed contract/system context, but its first-pass direction and source guidance are not fully preserved at the finalizer boundary. | Shared capability projection and Brain finalizer. Let Brain resolve one holistic scene-aware direction from the existing contract and source guidance. | Face/skin keyword lists, regex, local repair suffixes, or a new human-specific Provider branch. |
| Surface materiality / anti-plastic | Images become waxy, oily, painted or over-smoothed even though the module is marked active. | Materiality obligations are audit metadata or broad instruction, not a complete renderer-facing decision tied to the user scene and light. | Brain finalizer source binding; retain Doc94/Doc78 semantic ownership. | Increasing negative words, post-processing, universal beauty filters, or forcing a minimum prompt length. |
| Beauty and realism balance | Attempts to add realism can make faces dull, harsh or less attractive. | The finalizer receives quality constraints without the full user-owned aesthetic and prior detailed direction in one source envelope. | Preserve user aesthetic and beauty intent in the finalizer source projection; Brain resolves materiality within it. | A global “more realistic” recipe or a scene-specific beauty preset. |
| Composition / camera / shot direction | Pose, framing, angle, focus, depth and action lose detail or drift. | Only `shot_plan` is projected; `composition_rules`, `layout_notes` and related guidance are omitted. | Project image-set composition rules, prompt layout notes and shot direction into one Brain-owned context. | Local camera strings, fixed coordinates, or provider-side camera append. |
| Lighting / palette / mood | The scene becomes brighter, darker, warmer, flatter or otherwise different from the user prompt. | Finalizer must invent missing scene resolution while Human Realism rules tell it to preserve mood; the complete original light/style guidance is not bound. | Project user-owned rendering semantics and existing style/layout guidance; preserve ownership through Brain sign-off. | Global brightening, color heuristics, theme-specific light branches, or image post-processing. |
| Quality bar / negative constraints | Unwanted props, generic smiles, over-polish, wrong material or scene drift return. | `quality_bar`, `hard_constraints` and `negative_prompt_addons` are not all available to finalization. | Pass them as semantic source facts; Brain resolves them in a natural complete prompt and receipt. | Appending a negative prompt locally or searching for forbidden words. |
| Reference and identity channels | A selected generated anchor or uploaded source is bound correctly in metadata but the final prompt under-expresses identity/continuity boundaries. | Reference binding is present, but creative direction and reference-owned channels are not reconciled with the full source prompt at finalization. | Keep Doc93/95/96 ownership ledger authoritative; project its resolved source and finalizer context together. | Making Human Realism own hair, wardrobe, light, scene or style; local identity phrases. |
| Historical generated anchor | Same-person continuation can lose the intended person or inherit the wrong visual channel. | The runtime distinguishes source lineage structurally, but the finalizer may receive only a short direction and opaque bindings. | Pass resolved anchor lineage and channel ownership as frozen semantic context; Brain writes the whole continuation direction. | Treating every historical output as an unrestricted style reference or copying old prompt text blindly. |
| Canvas / aspect ratio / size | A prompt ratio or explicit size can be preserved in metadata but not reflected in the final natural-language direction. | Canvas facts are split between structured provider metadata and Brain prompt context; source projection can omit the user-visible aspect intent. | Keep structured size authoritative and project explicit ratio/size intent to finalizer; Provider transports the negotiated canvas without rewriting creative text. | Parsing arbitrary prompt strings locally or letting the web selection overwrite explicit user intent. |
| Multi-output variation | Multiple outputs become near duplicates, or each output loses its distinct camera/action direction. | Per-output shot directions and variation contract are projected, but the wider prompt-guidance package is not consistently bound per output. | Bind each output's complete direction and variation contract to its one-based output index; Brain authors distinct whole-image prompts. | Random local suffixes, deterministic camera permutations, or post-hoc prompt mutation. |
| Product truth / apparel construction | Product facts may remain structurally admitted, while material, silhouette, label or garment interaction loses detail. | Product truth is carried as typed admission/reference metadata, but finalizer source projection may omit the creative materialization guidance. | Keep ProductTruth and Doc269 authority unchanged; project the existing resolved product/apparel guidance to Brain. | Allowing General to own ecommerce roles or appending product descriptions in Provider. |
| General Template | General can become too generic or accidentally inherit professional/scenario-specific recipes. | Missing shared source projection encourages local or specialized fallback text to compensate. | Keep General scenario-neutral; give Brain only shared semantic capabilities and user-owned direction. | Adding ecommerce, photography, kidswear or ancient-style branches to General. |
| E-Commerce / Photography adapters | Specialized deliverable roles are structurally correct but the visual direction is thin or duplicated. | Adapter contexts are deduplicated without proving that their creative source reaches finalization. | Adapter supplies frozen non-creative role facts and existing creative context; Brain owns final natural language. | Moving specialized role recipes into shared foundation or duplicating module guidance in Provider. |
| Provider materialization | Provider receives a short prompt and cannot recover the missing modules. | Exact canonical pass-through is doing what it was told; the missing meaning was lost upstream. | Keep exact pass-through; repair upstream source projection and validate the signed source binding. | Reintroducing the old local compiler, silent fallback, or text concatenation. |
| Review / quality gate | Review reports low realism or integrity even though the job is structurally complete. | Review is observing a thin rendering direction/output; it is not the source of the missing prompt semantics. | Do not change scores first. Restore source delivery, then reassess review evidence. | Lowering thresholds, disabling identity gates, or treating review failure as a prompt compiler. |
| Retry / finalizer recovery | Retry repeats a thin prompt or appends a local repair fragment. | Recovery is bound to the same incomplete context, and no complete source-projection receipt proves what it must preserve. | Reuse the same complete frozen source envelope; Brain rewrites the whole prompt once within the existing bounded recovery. | Infinite retries, local retry suffixes, or a second compression service. |

## 7. Corrected end-to-end model

The repaired flow must be exactly:

```text
user request + frozen facts
  -> first Brain planning
  -> existing shared capability execution
  -> complete typed Brain source package
       (prompt_guidance + image_set_plan + active contracts
        + ownership/reference/context facts)
  -> one server-owned source projection with output binding/digest
  -> Brain canonical finalizer
       (semantic reconciliation, natural prompt, semantic receipt)
  -> unified Doc293 length decision
  -> Provider admission and transport validation only
  -> exact prompt to image Provider
```

The source projection is not an additional prompt author. It is a lossless,
server-owned handoff of already-authorized semantic facts to the one final
author. It must preserve the full meaning of existing fields without sending
internal IDs, review codes, storage paths, or implementation checklists as
renderer wording.

For each output, the source binding must include:

- output index and requested count;
- frozen user-intent/source digest;
- Brain planning result digest;
- projected prompt-guidance/image-set digest;
- active capability contract digest;
- reference/channel ownership digest where applicable;
- policy revision and finalizer stage;
- finalizer semantic coverage result;
- self-binding receipt digest.

These fields prove which source was handed to Brain. They do not claim that a
keyword appeared in the prompt. Semantic coverage remains a Brain decision, and
the runtime only rejects missing, stale, malformed or mismatched bindings.

## 8. Minimal implementation plan

### Phase 0: pre-development inventory

Before editing:

1. Confirm unique main path and feature worktree path.
2. Record HEAD, branch, `git status --short`, untracked evidence and existing
   uncommitted Doc293 changes.
3. Confirm no other writer owns the feature branch/worktree.
4. Read Doc76/77/78/93/94/95/96 and Doc293; record conflict decisions.
5. Freeze `CONTRACT_REV=v3_brain_source_projection_v1` and
   `COMPLEXITY_GATE=ESCALATE_REQUIRED`.
6. Freeze the single writer, audit owner, allowed files and test matrix.
7. Do not call a real Provider, create jobs, deploy, or touch external services
   until offline evidence passes.

### Phase 1: source projection

Allowed implementation area:

- `app/scenario_runtime/runtime.py`: project the existing complete Brain result
  into the canonical finalizer context, per output and without local prose;
- existing Brain contracts/adapter owners: define the smallest typed source
  envelope and validate its digest/binding;
- `app/llm_brain/prompts.py`: consume the envelope and instruct the Brain to
  resolve the complete natural-language direction without exposing internal
  fields.

The implementation must carry, at minimum, the fields listed in the module
matrix. It must not add a local semantic fallback.

### Phase 2: completeness and compression boundary

- Doc293 remains the only final-prompt compression policy.
- `<= 6000` means keep the Brain-signed text exactly as returned.
- `> 6000` permits one Brain semantic rewrite toward the existing target.
- Length is never used to infer whether a module is present.
- A short prompt is accepted only when Brain semantic coverage is complete and
  the source projection binding is valid.
- A missing or mismatched source binding blocks before image request; it must
  not fall back to old local prompt assembly.

### Phase 3: Provider and adapter audit

Verify that Provider code:

- reads exactly one approved canonical prompt;
- does not append local Human Realism, scene, camera, product or negative text;
- does not trim, split, regex-match or reorder creative text;
- still transports structured size, references and output metadata separately;
- does not receive internal source IDs as renderer prose.

### Phase 4: test implementation

Add focused regressions for the source envelope, one output and multiple
outputs, short and long prompts, missing/stale binding, and exact Provider
pass-through. Update only assertions that conflict with the corrected
authority model; do not weaken semantic requirements.

## 9. Pre-development checklist

### Contract and authority

- [x] User requirement is preserved verbatim in the task record.
- [x] Doc294 does not override Doc93/94/95/96 or Doc293 outside its scope.
- [x] Brain is the only final natural-language author.
- [x] Provider remains a transport/admission boundary.
- [x] No regex, keyword, phrase count or prompt substring is proposed.
- [x] No minimum prompt length is proposed.

### Scope and governance

- [x] Only the feature worktree is used for source edits.
- [x] Existing uncommitted changes are recorded and not overwritten.
- [x] Main, GitHub, VPS, Sub2API, Veyra and real production projects are frozen.
- [x] No new provider, model, product dependency, configuration secret or service is
  introduced.
- [x] General remains scenario-neutral.
- [x] Specialized modules keep their deliverable ownership.

### Source completeness

- [x] `prompt_guidance` fields are inventoried.
- [x] `image_set_plan` fields are inventoried.
- [x] Shared capability contracts are inventoried.
- [x] Reference/channel ownership is inventoried separately from Human Realism.
- [x] Product truth and apparel facts remain server-frozen.
- [x] Per-output binding and cardinality are defined.
- [x] Semantic receipt is source-bound, not keyword-bound.

### Validation safety

- [x] Offline contract tests pass before any real image request.
- [x] Failure paths are tested before success paths are claimed.
- [x] A provider timeout is recorded separately from prompt-source failure.
- [x] No unexpected jobs, outputs, review records or project mutations exist.
- [x] Test evidence is bound to a fixed version and excludes caches/evidence
  artifacts from source commits.

## 10. Regression and acceptance matrix

### 10.1 Source projection tests

1. Full `prompt_guidance` and full `image_set_plan` survive into the finalizer
   context with the same semantic values and a stable digest.
2. Missing, stale, swapped, malformed or cross-output source envelopes fail
   closed before Provider request.
3. Internal IDs and contract keys are not emitted as renderer wording.
4. A valid short prompt is not padded; a rich prompt is not silently reduced to
   its shot-plan sentence.

### 10.2 Module preservation tests

Run at least three materially different scenes:

- a single adult portrait/lifestyle scene;
- an adult group or multi-person scene;
- a non-portrait product or environment scene.

For each, verify by Brain-owned semantic receipt and captured final prompt that
the active module meaning reaches finalization. Do not assert literal keywords;
use deterministic fake Brain responses/receipts and inspect structured source
binding plus exact final text where the fixture owns it.

### 10.3 Cross-layer regressions

- General remains neutral and supports ordinary image requests.
- E-Commerce keeps ProductTruth/Doc269 role and reference authority.
- Photography keeps its specialized role authority.
- Human Realism applies to visible people without owning scene/style/reference
  channels.
- Reference and historical-output anchors preserve Doc93/95/96 ownership.
- Explicit size/aspect intent remains higher priority than web selection.
- Multi-output count, per-output direction and variation binding remain stable.
- Retry rewrites the whole prompt from the same complete source; no local suffix.
- Provider receives the exact signed canonical prompt and no extra creative text.

### 10.4 Compression tests

- `<= 6000` is unchanged and has no compression receipt.
- `> 6000` invokes at most one Brain semantic rewrite under Doc293.
- Compression cannot remove the source binding or change user-owned channels.
- Compression failure blocks image request rather than falling back to legacy
  local assembly.

### 10.5 Static and hygiene checks

- Python compile for touched Python files.
- Node syntax checks only if frontend files are touched.
- `git diff --check`.
- No evidence, cache, generated image, credential or temporary file in the
  intended change set.
- Final status and commit/hash are recorded before independent audit.

## 11. Independent audit checklist

The audit owner must inspect the fixed version independently and return only
`符合`, `不符合` or `证据不足` for each requirement.

1. Compare the finalizer input schema with the actual Brain result schema;
   confirm no prompt-guidance field is silently dropped.
2. Trace one complete output from planning through finalizer to Provider.
3. Confirm Provider has no active local creative append path for new jobs.
4. Confirm source digest binds the exact frozen source and output index.
5. Confirm semantic receipts are Brain-owned decisions, not local keyword
   checks.
6. Confirm no scenario-specific branch entered shared foundation code.
7. Confirm no old test was weakened merely to hide a regression.
8. Confirm short/long, simple/rich, human/non-human, single/multi-output and
   reference/no-reference coverage.
9. Confirm static checks and worktree evidence hygiene.
10. Confirm external systems were not touched.

Any `不符合` or `证据不足` on a required item blocks implementation acceptance.
The audit owner must not edit the implementation or its tests.

## 12. Failure routing and rollback

- Source projection failure: block before image request; preserve the public
  structured reason and frozen evidence.
- Brain semantic coverage failure: use the existing bounded same-context
  finalizer recovery once; if it still fails, block.
- Compression failure: block; do not use legacy local prompt assembly.
- Provider timeout or upstream failure: classify independently and do not
  rewrite source-projection evidence.
- Review failure after pixels: preserve pixels and review evidence; do not
  lower the review gate as a prompt fix.
- Historical records: remain immutable; only new explicit commands use the new
  source projection contract.

## 13. Task record

```text
Task: restore effective V3 module semantics after Brain-owned prompt migration
Goal: implement and audit the minimal source-projection repair
Non-goal: no provider, model, review, V1/V2, Sub2API, VPS or deployment change
Baseline main: 62422dad6a36a05bb24f502afc9f94ae65a02c90
Feature worktree: D:\AI\w\doc293-unified-prompt-compression
Feature HEAD: 62422dad6a36a05bb24f502afc9f94ae65a02c90
Existing changes: Doc293 implementation edits and evidence were the pre-existing baseline;
                  Doc294 implementation is now included in the isolated feature change set
CONTRACT_REV: v3_brain_source_projection_v1
COMPLEXITY_GATE: ESCALATE_REQUIRED
Unique writer: main controller in the feature worktree
Audit owner: independent read-only audit after document freeze
External actions: no external Provider, deployment, VPS, GitHub or production mutation
Acceptance: implementation, focused tests, source audit and exact-prompt regression pass;
             integrated mainline acceptance remains pending
```

## 14. Implementation acceptance gate

This document's implementation gate is passed when:

- every failure row identifies an owning layer and a non-regex repair;
- the plan restores semantic delivery without restoring Provider-local prose;
- all existing authority documents remain compatible or their conflict is
  explicitly narrowed;
- pre-development, implementation, test and independent-audit checklists are
  present;
- General/specialized isolation and V1/V2/Sub2API boundaries are explicit;
- no real external action is implied by a passing offline document audit.
- the intended commit excludes validation evidence, caches, generated images,
  credentials and unrelated pre-existing worktree changes.

The focused implementation gate is now passed. The remaining acceptance step is
integration into the unique main checkout, followed by the integrated test set.
