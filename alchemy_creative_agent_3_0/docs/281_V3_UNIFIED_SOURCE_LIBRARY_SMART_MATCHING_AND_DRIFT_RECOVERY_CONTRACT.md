# Doc281 - V3 Unified Source Library Smart Matching And Drift Recovery Contract

Status: Phase 0 contract and deterministic red-test authority. This document
does not activate runtime behavior, dispatch a Provider, call MCP/ImageGen,
create a real job, or deploy a service.

## 1. Objective And Correction Model

V3 must make a project-owned library of user-uploaded originals useful to both
General and Professional commands. A project may contain several object views,
people and environment sources, or brand and scene material. For every new
explicit command, the server must select only the small set of suitable
originals for the requested output. A browser, file name, upload order, Brain
prose, generated thumbnail, review result, or historical Job must never choose
that set.

The current design is incomplete in two connected ways:

1. General's Doc270 activation capability, command identity, and receipt
   registry seams are disabled `return None` placeholders, so it cannot use a
   production server-owned analyzer/matcher path.
2. An active historical E-Commerce product association can drift after upload
   readiness or role changes. On the next command, reference persistence
   re-enters `_require_ready_uploaded_reference` and leaks a raw `ValueError`
   before the established Doc263/264 admission closure can project one safe
   terminal operation.

The authoritative Phase 6 flow is:

```text
active project-upload association + actual readable bytes
  -> SHA/project-bound SourceEvidenceProfile
  -> server-issued typed ReferenceRequirement for a new explicit command
  -> shared source matcher and immutable private resolution receipt
  -> template-owned activation and frozen source projection
  -> existing template final plan, provider-cap negotiation, and review
```

For drift, the authoritative flow is:

```text
active historical product association with current integrity drift
  -> server detects it before persistence/planning/Brain/provider
  -> one persisted, project-projected sanitized terminal current_operation
  -> browser terminal precedence clears local preparing state
```

No historical Job, generated output, review result, or old receipt is
rewritten by either flow.

## 2. Authority And Non-Authorities

### 2.1 Shared foundation owns evidence and matching

The V3 shared foundation owns an image-backed `SourceEvidenceProfile`, a
profile analyzer, candidate eligibility, ranking, receipt integrity, and the
source matcher. Every profile and receipt must bind all of these facts:

- project ID and active association/reference ID;
- upload asset ID, source type, and current active state;
- actual current SHA-256 and readable-byte check;
- analyzer authority, schema/version, profile digest, and analysis receipt;
- typed requirement issuer, command/plan/output binding, and receipt digest.

Matching bytes in another project, a self-digested browser object, or copied
metadata do not confer authority. The shared matcher is restricted to active,
project-scoped `uploaded` originals. It has no adapter for People/Visual
Assets, generated/review/history outputs, or implicit continuations.

`ReferenceRequirement` is server-issued and typed. A template/Brain boundary
may declare semantic output needs, but it cannot select an asset ID. The
requirement contains bounded source count, hard/preferred/optional strength,
required evidence, output binding, and Doc93 prompt-owned exclusions. The
server matcher is the one selector; it ranks image-backed facts and only uses a
recorded deterministic tie-break after semantic equivalence. Filename, upload
position, browser labels, and Brain prose are not ranking inputs.

There is one production image-evidence/analyzer and matcher authority in the
shared foundation. General and E-Commerce consume its verified receipts; E31
may issue E-Commerce view requirements and activation policy but must not be
the implementation General depends on. A trusted server plan/command boundary
issues each requirement and binds template, project, command/plan, output,
nonce, snapshot, and canonical digest. Forged requirement, cross-project
binding, stale snapshot, and self-digested wrong evidence are invalid before a
source can be frozen.

### 2.2 Template authority remains narrow

General, E-Commerce, Photography, Brand, and future templates can only issue
their typed requirement and consume a verified server receipt. They neither
own profiles nor supply a candidate snapshot. A selected original can support
only the channel contribution already permitted by Doc93. In particular,
selecting an uploaded portrait does not enlarge same-person identity, hair,
makeup, wardrobe, lighting, scene, camera, mood, or style inheritance. Those
remain respectively under Doc93, the People/Visual Asset authority, or the
current prompt.

Doc261/265 remain the only authority for an explicit generated continuation.
A selected continuation is a separate, explicit channel and never becomes an
original, SourceEvidenceProfile candidate, Product Truth member, or automatic
continuation merely because it exists in history.

## 3. General V3 Phase 6 Activation

For a new explicit General command, shared foundation must provide a real,
production-capable server-owned activation capability, command registry,
analysis/receipt registry, and matcher. The existing private seams named
`_doc270_general_activation_capability_lookup`,
`_doc270_general_command_identity_lookup`, and
`_doc270_general_phase2_receipt_registry_lookup` must cease to be disabled
placeholders. They may remain compatibility names only while delegating to the
single Phase 6 authority; they must not become a second General matcher.

The command identity is allocated before Job creation. It is project, template,
command, plan, output, capability-version, and coalescing-nonce bound. A
repeat click or transport replay returns the same frozen Job/receipt and never
analyzes or rematches. A distinct explicit command obtains a new identity and
first clears the prior command's terminal/progress presentation.

The analyzer and matcher outcomes are:

| Outcome | General action |
| --- | --- |
| `resolved` | Freeze the selected, bounded original projection for that output. |
| no originals, `not_applicable`, or optional uncertainty | Preserve prompt-only creation; no `needs_input`. |
| invalid, stale, or unavailable private evidence | Preserve a public-safe prompt-only/receipt-invalid state; no raw error. |
| hard exact-source requirement unsupported by qualifying evidence | Use the separately authorized hard-reference policy; Phase 6 must not silently invent a match. |

No General path may use every upload as a fallback, block a normal command for
optional uncertainty, or create a stuck `preparing`/`needs_input` state. A
frozen projection has only association/asset/SHA/receipt bindings privately;
public projection exposes source category and safe label only.

## 4. Professional E-Commerce And Historical Drift

E-Commerce retains the required order of authority:

```text
Doc263/264 full ProductTruthAdmission and re-attestation
  -> Phase 6 matcher selects a small appropriate product-original subset per output
  -> Doc269 frozen physical renderer plan supplies exact provider inputs
```

The full Product Truth pool remains mandatory. People/Visual Asset evidence,
product truth, selected continuation, and exact provider capacity remain
separate; a matcher receipt cannot weaken any of them. The current Doc269
physical plan remains the only authority for exact provider input order and
count.

An active product association that now has one of `upload_not_ready`,
`role_or_channel_invalid`, `file_missing`, or `content_drift` is not absence of
a product and must not make an E-Commerce command prompt-only. Before a new
command tries to persist/re-upsert that association, the server must:

1. inspect the association and current upload/file/SHA facts;
2. create or return the same idempotent terminal receipt for the current
   command identity;
3. persist one private diagnostic and one public-safe `current_operation`;
4. project a single actionable terminal state with `loading=false`, `busy=false`,
   no timer/recovery owner, and no Brain, planning, provider, or review work.

The closure occurs before `plan_job`, Brain invocation, materialization,
Provider dispatch, or review. It creates no Job ID and leaves `project.job_ids`
unchanged. Repeated delivery of the same command returns the one persisted
terminal receipt, including after constructing a new service/store reader.
Only a relevant repaired product original and a new explicit command may
replace it. This applies equally to readiness, role/channel, missing-file, and
SHA/content drift.

The public operation must not expose raw exceptions, IDs, hash, file path,
prompt, provider detail, or analyzer code. It identifies an actionable source
class such as "a product original needs attention" and the approved repair
action. A later new command removes the old terminal state before evaluating
its own current facts. Historical Jobs stay immutable and no retry changes an
old selected source set.

## 5. Isolation, UI, And Public Disclosure

The public reference board has exactly four conceptual groups:

1. Project original source library;
2. People/Visual Assets;
3. explicitly selected continuation direction;
4. generation and review history.

The board may show a safe source category and public label for each actual
source used by an output, for example `project original`, `visual asset`, or
`selected continuation`. It must not display internal ID, SHA/digest, path,
profile, matcher rationale, private state, prompt, or provider payload.
Generated/review/failed outputs never appear in the first group. An explicit
continuation remains in group three even when the output appears in group four.

Desktop and H5 obtain terminal/progress state from the server projection. A
terminal result always clears and wins over a stale local "preparing" surface;
the UI must not show contradictory preparing/stopped text. A new command clears
the old operation before rendering its own status. Local retry/repair actions
must be idempotent and cannot create a new selection from history.

Both clients must test this at DOM level: a terminal input closure clears an
already-running progress state, displays exactly its applicable repair action,
and cannot overwrite a newer command's view. The source board stays at the
four groups above and adds only a safe per-output used-source category/label;
it never leaks IDs, hashes, paths, prompts, Provider fields, or history as a
new original.

General, E-Commerce, and Photography must remain isolated:

- General uses the shared matcher and stays prompt-owned outside a verified
  original projection.
- E-Commerce adds ProductTruthAdmission and Doc269 only; it never teaches the
  shared matcher apparel-specific rules.
- Photography gets no E-Commerce Product Truth, product closure, cap, or
  provider-plan behavior without its own activation contract.

## 6. Deterministic Acceptance Matrix

Phase 6 implementation is accepted only after deterministic tests prove:

1. object multi-view/detail, person-plus-environment, and scene/brand sources
   resolve only a bounded appropriate original with server-held evidence;
2. browser fields, filename, upload order, Brain prose, cross-project records,
   SHA drift, generated/review history, and implicit continuation cannot select;
3. a new General explicit command uses a real server registry/analyzer path,
   while no source or optional uncertainty remains prompt-only and non-blocking;
4. selected General portrait originals do not extend any Doc93 inheritance
   channel;
5. E-Commerce completes full Doc263/264 admission before matching and Doc269
   remains exact final physical-plan authority;
6. `not_ready` and `role_drift` historical active product associations produce
   one persistent, sanitized terminal operation instead of raw `ValueError`;
7. file/SHA drift, replay, reload, current-command reset, Desktop/H5 terminal
   precedence, and explicit continuation/history isolation remain correct; and
8. General/Professional/Photography isolation and the four public reference
   groups remain intact without private leakage.
9. Object multi-view, person-plus-environment, and scene/brand fixtures yield
   different bounded General projections. Prompt wording, filename/upload
   order, source order, and browser metadata cannot change the server-held
   evidence selection.

Phase 0 changes only this contract, the minimal Doc270 cross-reference, and
deterministic red tests. It is not permission to implement runtime behavior,
change providers, create a real generation, or deploy. The next phase starts
only after a PRE-IMPLEMENTATION AUDIT authorizes a bounded runtime design.

## 7. Relationship To Existing Authorities

Doc270 remains the source-library foundation and phased delivery history.
Doc93 retains reference-channel and prompt ownership. Doc261/265 retain
original/continuation/history separation. Doc263/264 retain E-Commerce Product
Truth admission and legacy recovery. Doc269 retains E-Commerce physical
renderer planning. Doc281 resolves only the unfinished shared activation and
historical-drift recovery needed to make those existing authorities coherent.
