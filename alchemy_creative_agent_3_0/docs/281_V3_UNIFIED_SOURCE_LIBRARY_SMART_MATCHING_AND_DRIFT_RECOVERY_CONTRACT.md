# Doc281 - V3 Unified Source Library Smart Matching And Drift Recovery Contract

Status: General source-selection and drift-recovery implementation authority.
This document does not authorize a real Provider/MCP/ImageGen call, create a
real validation job, or deploy a service.

## 1. Objective And Correction Model

V3 must make a project-owned library of user-uploaded originals useful to both
General and Professional commands. A project may contain several object views,
people and environment sources, or brand and scene material. For every new
explicit command, the server must select only the small set of suitable
originals for the requested output. A browser, file name, upload order, Brain
prose, generated thumbnail, review result, or historical Job must never choose
that set.

The implementation has two authorities. General uses a server-composed
source-selection Brain over reverified original images and binds only its
opaque handles. Professional E-Commerce retains its typed E31 product-truth
and physical-reference authority. Independently, an active historical
E-Commerce product association can drift after upload readiness or role
changes; Doc281 closes that association before persistence/planning and emits
one safe terminal operation.

The authoritative Phase 6 flow is:

```text
active project-upload association + actual readable bytes
  -> SHA/project-bound verified original candidates
  -> Brain sees the explicit command and reverified original images
  -> opaque-handle selection and immutable private server binding
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

### 2.1 Shared foundation owns verified evidence and binding

The V3 shared foundation owns the project-scoped original pool, readable-byte
verification, candidate eligibility, receipt integrity, and server binding.
General source selection is a Brain decision over the verified images; the
server never infers semantic meaning from filenames, order, browser fields, or
regular-expression branches. Every private receipt must bind all of these
facts:

- project ID and active association/reference ID;
- upload asset ID, source type, and current active state;
- actual current SHA-256 and readable-byte check;
- Brain authority, schema/version, command identity, output-plan binding, and
  receipt digest.

Matching bytes in another project, a self-digested browser object, or copied
metadata do not confer authority. The shared matcher is restricted to active,
project-scoped `uploaded` originals. It has no adapter for People/Visual
Assets, generated/review/history outputs, or implicit continuations.

For ordinary General V3, a named source-selection Brain receives only the
explicit command, the requested output count, and current reverified original
images represented by opaque candidate handles. It returns either prompt-only
or bounded opaque-handle selections. The server maps those handles to the
current project association and SHA, validates them, and freezes the private
output binding. The Brain's image analysis is the semantic authority; the
server performs integrity and scope checks only. There is no finite semantic
taxonomy, filename matcher, order heuristic, browser selector, or regex-based
fallback in the General path.

Professional E-Commerce remains the deliberate specialization: E31 may use
its existing typed product-truth and physical-reference evidence contracts,
and Doc263/Doc269 remain authoritative for the final product projection and
renderer plan. That specialized authority is not copied into General.

There is one production image-evidence/analyzer and matcher authority in the
shared foundation. General and E-Commerce consume its verified receipts; E31
may issue E-Commerce view requirements and activation policy but must not be
the implementation General depends on. A trusted server plan/command boundary
issues each requirement and binds template, project, command/plan, output,
nonce, snapshot, and canonical digest. Forged requirement, cross-project
binding, stale snapshot, and self-digested wrong evidence are invalid before a
source can be frozen.

The private General consumption protocol is
`doc281_general_source_registry_v2`, implemented through the named internal
`Doc281GeneralSourceRegistry` dependency. Its only operations issue one
`doc281_general_command_identity_v2` and read one
`doc281_general_registered_receipt_v2`; neither accepts browser metadata nor an
arbitrary Project Mode attribute. Registry lookup requires exact private
project/template/command/plan/output/nonce identity equality and returns the
immutable SHA-bound requirement/evidence receipt only for that identity. The
identity's canonical digest is a server record, not a caller-supplied public
key.

General activation uses the versioned packaged
`project_mode/policies/doc281_general_source_policy_v1.json` when no deployment
override is set. An explicit unreadable, malformed, or schema-open override
fails closed to ordinary prompt-only operation; it never falls back silently.
The policy is selector-free and declares only enabled state, authority/version,
and a bounded maximum source count. The General source-selection Brain receives
the command and reverified original images, not source IDs, filenames, browser
fields, SHA values, history, or hidden server metadata. It may return only
`prompt_only` or `selected` with opaque candidate handles. Malformed, partial,
unavailable, or unknown Brain responses are prompt-only and create no source
selection.

A persisted selection receipt is authoritative only when its exact schema,
identity/binding digest, command/snapshot/policy/count facts, selected-handle
resolution, output-plan binding, and receipt digest all validate. A present but
invalid, stale, or tampered receipt fails closed to prompt-only without Brain
retry or selected-original projection. A valid prompt-only receipt is replayed
as prompt-only rather than repeatedly calling the Brain.

### 2.2 Template authority remains narrow

General consumes a verified Brain selection receipt. E-Commerce, Photography,
Brand, and future templates retain their own typed requirements where their
specialized contracts require them. Templates neither own source bytes nor
accept browser-authored candidate facts. A selected original can support
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

An active product association that now has one of `upload_missing`,
`upload_not_ready`, `role_or_channel_invalid`, `file_missing`, or
`content_drift` is not absence of a product and must not make an E-Commerce
command prompt-only. `upload_missing` means the persisted project association
outlived its V3 upload record; it belongs to the same no-Job terminal closure
class as a missing or unreadable file. Before a new command tries to
persist/re-upsert that association, the server must:

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
replace it. This applies equally to a missing upload record, readiness,
role/channel, missing-file, and SHA/content drift.

Its private persistence namespace is
`doc281_source_association_terminal_receipts_v1`; the receipt schema is
`doc281_source_association_terminal_receipt_v1`. Each append-only receipt is
bound to the server-issued command identity (including its private canonical
digest) and current project association snapshot, never a public operation key.
A fresh Project Mode/service/store reader must rehydrate the same terminal
receipt and public-safe projection.

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
and cannot overwrite a newer command's view. The race test must hold an old
terminal `needs_input` response, start a newer explicit command/current
operation, then release the old response and prove the stale callback cannot
restore its action or progress. The source board stays at the four groups above
and adds only a safe per-output used-source category/label; it never leaks IDs,
hashes, paths, prompts, Provider fields, or history as a new original.

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
   one persistent, sanitized terminal operation instead of raw `ValueError`,
   with zero planning, Brain, materialization/dispatch, and review calls;
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
