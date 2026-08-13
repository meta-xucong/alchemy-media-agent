# Doc270 - V3 Project Source Library And Reference Matching Contract

Status: Phase 0 shared design and deterministic test-contract authority. It
does not change runtime behavior, provider inputs, historical projects, or
production deployment by itself.

## 1. Objective And Observed Gap

V3 currently has safe but incomplete reference handling:

- uploads have durable records, project membership, roles, readable files, and
  content SHA-256 values;
- Doc93 separates reference channels and preserves prompt ownership;
- Doc261/265 keep uploaded originals, bound visual assets, explicitly selected
  continuations, and generated/review history visibly and semantically
  separate;
- Doc263/269 validate a complete Professional E-Commerce product-truth pool,
  then freeze only the small per-output physical reference set sent to a
  renderer.

Those boundaries must remain. The missing capability is a common way to
understand a *set* of project originals and select the few original sources
that best support one requested output. Today an upstream planner can choose a
valid asset ID from a pool, but the pool has no durable, image-backed semantic
description of such facts as:

- a front, side, rear, angled, flat-lay, macro, or detail view of an object;
- a visible pattern, closure, material, label, packaging, or silhouette;
- a portrait, non-human subject, scene, logo, layout, or atmosphere source;
- which source can support a requested view while another source should remain
  project evidence only.

As a result, V3 can correctly avoid sending every original to the renderer,
yet still choose a semantically weak original for a planned output. The issue
is general: it applies to multi-view products, people, places, brand material,
and composite source sets. It is not an apparel-only or E-Commerce-only rule.

The objective is one shared, server-owned **Project Source Library** that
catalogs the user-uploaded originals and resolves a small, auditable reference
set for each output. General V3 and Professional V3 consume the same service;
their truth and failure policies differ only where their templates already
differ.

## 2. Correction Model

The authoritative path after implementation is:

```text
durable upload bytes and project association
  -> Project Source Library entry
  -> image-backed Source Evidence Profile
  -> Brain/template output Reference Requirements
  -> server-side Reference Matcher
  -> template-specific frozen reference projection
  -> existing provider-capacity and final physical-plan validation
  -> renderer and shared review
```

This is an additive decision layer, not a new asset store, alternate project
model, or provider route.

### 2.1 What the library is

The Project Source Library is a server-owned, project-scoped read model over
existing active uploaded-source associations. An entry always points to the
existing upload record and its actual bytes. It contains no copied image file
and does not replace `V3UploadedAssetStore`, `ProjectReferenceAsset`, the
Visual Asset Library, generated-output storage, or Product Truth admission.

Each entry binds at minimum:

- project ID, source association ID, upload asset ID, source type, and active
  state;
- actual readable content SHA-256, MIME type, dimensions when available, and
  analysis schema/model version;
- a versioned `SourceEvidenceProfile` and its digest;
- optional user-owned usage preferences, separately recorded from observed
  image evidence;
- creation/supersession provenance and a public-safe label.

The binding digest includes project association and actual bytes. An analysis
of matching bytes in another project is not permission to use that other
project's source.

### 2.2 What the library is not

The library must not:

- turn a generated result, timeline preview, review-withheld candidate, or
  failure image into an original input;
- create an implicit continuation selection;
- replace a bound Visual Asset or reclassify its face evidence as a project
  upload;
- treat a filename, upload order, browser metadata, or duplicate-content
  coincidence as image semantic evidence;
- create persistent biometric vectors, facial embeddings, or cross-project
  person identity indexes;
- silently add every original to a provider request, increase a provider cap,
  or trim a hard reference after it was frozen;
- delete global uploads, output files, historical jobs, or audit evidence when
  a project association is removed or deduplicated.

## 3. Authority And Compatibility

### 3.1 Existing authority that remains unchanged

| Existing authority | Remains authoritative | Doc270 role |
| --- | --- | --- |
| Upload store and project association | bytes, readiness, SHA, rights, project membership, active state | library reads and binds them; it cannot repair or invent them |
| Doc93 reference-channel policy | what a reference may contribute and what remains prompt-owned | library describes usable evidence but cannot expand channel inheritance |
| Visual Asset Library / People chain | selected reusable identity, formal face evidence, and display-name authority | library presents it separately and never substitutes project originals for it |
| Doc261 and Doc265 | original/continuation/history separation and explicit selected-output admission | library contains originals only; a continuation remains a distinct explicit channel |
| Doc260 review evidence plan | which evidence is applicable and what qualifies a certified review | the selected receipt supplies exact source evidence; it does not turn missing evidence into a pass |
| Doc263 product-truth admission | complete canonical product pool, product rights, and full-pool validation | library may help choose from that pool but never reduces, rewrites, or substitutes it |
| Doc269 physical renderer plan | exact ordered physical inputs for Professional E-Commerce | matcher output is upstream; the final plan remains the only provider-input authority |

### 3.2 Decision split

One layer must not own every decision. The stable split is:

```text
Current prompt and selected template
  -> Brain: output intent and reference requirements

Project Source Library
  -> server analysis: image-backed evidence claims and uncertainty

Reference Matcher
  -> server: eligible candidates, ranking, insufficiency, and match receipt

Specialized template / Product API / Project Mode
  -> server: truth policy, final source binding, cap reservation, and terminal state

Provider
  -> verifies and consumes the frozen final plan only
```

The browser may request an upload, remove a current project association, state
a preference, or explicitly select a continuation. It cannot author observed
image evidence, role/channel authority, a match result, a digest, source
binding, provider capacity reservation, or a final renderer plan.

### 3.3 Resolving the one unavoidable semantic conflict

Doc263 currently allows the Remote Brain to return
`selected_product_truth_asset_ids` from the admitted pool. That safely proves
membership but does not prove that an ID is the best front, side, back, or
detail evidence for the output. Allowing both the Brain and a matcher to make
independent final ID choices would create two competing authorities.

Doc270 therefore adopts this migration rule:

1. The Brain remains owner of output intent and declares typed
   `reference_requirements`; it does not become the durable owner of source
   bytes.
2. The server matcher resolves only active project-upload original source IDs
   from image-backed evidence and emits a server-issued
   `ReferenceResolutionReceipt`. It never selects, ranks, or emits bound
   Visual Assets or selected continuations.
3. The specialized owner freezes final source IDs from that receipt. For
   Professional E-Commerce it then derives the existing Doc263
   `PhysicalProductReferenceProjection`, followed by the existing Doc269
   physical renderer plan.
4. During compatibility rollout, the current Brain-selected-ID contract stays
   valid only for commands outside the Doc270 version gate. The matcher first
   operates in observe-only and consistency-audit mode. No old job is rewritten
   and no historical click changes behavior.
5. Once the version gate enables matcher mode for a *new explicit command*, a
   verified `resolved` receipt is the sole original-source subset selector.
   Brain-selected IDs remain intent/compatibility evidence only; they cannot
   be a fallback, an override, or a competing final selection. An unresolved,
   ambiguous, or invalid receipt closes with the receipt-scoped terminal state
   or requests one new bounded Brain planning pass. It never silently falls
   back to the old IDs.
6. The active path may mark
   `product_truth_selection_source=project_source_library_matcher_v1`; legacy
   selection fields remain compatibility projections, not a second authority.

This is more coherent than making the matcher a weak after-the-fact override,
or forcing the renderer to accept every original. It retains creative intent
at the Brain and factual source binding at the server boundary.

## 4. Shared Typed Contracts

### 4.1 `SourceEvidenceProfile`

`SourceEvidenceProfile` is immutable for one exact source association and
content SHA. It is created only after readable bytes are available. It carries
image-backed observations, not inferred truth from its filename.

The initial schema must be bounded and extensible by typed vocabularies:

```text
evidence_state:
  observed | not_observed | uncertain | not_applicable | invalid

subject_kind:
  person | object_or_product | nonhuman_subject | scene_or_place |
  brand_or_graphic | mixed | unknown

view_kind:
  front | rear | left_side | right_side | three_quarter |
  overhead_or_flat_lay | detail_or_macro | packaging |
  environment_wide | portrait_close | unknown

affordance:
  person_identity | object_shape | object_surface | object_detail |
  object_back_or_structure | logo_or_mark | text_or_label |
  environment | composition | palette_or_style | negative_example
```

Each claim records applicability, confidence band, bounded observed attributes,
and the analysis receipt digest. It must distinguish "not visible" from
"analysis uncertain". It must never claim that a source is the same person or
same product as another source solely from a filename or a durable biometric
signature.

An observed `person_identity` affordance is not identity-channel authority and
does not grant an inheritance right. It may support an uploaded-original
requirement only where Doc93 already permits that contribution. A locked People
Visual Asset remains outside the Source Library and retains its exact
Doc267/269 face-evidence contract.

For grouping, the first release may use only explicit project grouping and
content identity. A short-lived, non-persistent visual comparison is allowed
only for a single request, must have clear user authorization, and must not
persist biometric vectors or silently create a cross-project identity link.

The existing `AssetRoleAnalyzer` may provide dimensions, color, composition,
and a role suggestion as supporting signals. It is insufficient on its own:
its filename and context heuristics must not certify a source view, hard truth,
or final match.

### 4.2 User usage annotations

The UI may let a user say, for example, "prefer this for the rear view",
"this is a material close-up", or "do not automatically use this source".
The server persists this as a separately typed, SHA-bound user annotation with
its own audit record. It is a preference or supplied intent, not an observed
evidence claim and not a replacement for rights, role, channel, or file
integrity validation.

An annotation may break an otherwise equal match tie or request a new analysis.
It cannot force a hard Professional E-Commerce product-truth projection when
the source is unreadable, inactive, outside the project, mismatched to its
receipt, or visually incompatible with a required hard proof.

### 4.3 `ReferenceRequirement`

Every planned output may declare a small ordered list of semantic needs for
**project-upload original sources only**. Bound identity is resolved solely by
Doc93 and the Visual Asset authority; explicit selected continuation is
resolved solely by Doc261/265. The owning template composes these already
authorized channels after matching. The matcher never selects, ranks, or
returns either non-original channel. An original-source requirement contains:

- output index and template/scenario owner;
- original-source channel and `no_reference` applicability only;
- required subject/affordance/view evidence and an optional negative condition;
- strength: `hard`, `preferred`, or `optional`;
- maximum sources, purpose, and whether a source is physical-renderer-required;
- prompt-owned exclusions required by Doc93;
- requirement digest and schema version.

Examples are semantic rather than vertical recipes:

```text
object main presentation: object_shape + front or three_quarter view
rear construction evidence: object_back_or_structure + rear view
surface proof: object_surface or object_detail + detail_or_macro view
same-person image: optional uploaded scene evidence; bound identity is resolved
  separately by its existing authority
place-inspired scene: environment evidence preferred; prompt owns composition
```

The General Template may omit all requirements and remain text-to-image. A
template may use an optional requirement without turning it into a mandatory
upload flow.

### 4.4 `ReferenceResolutionReceipt`

The matcher returns one immutable, server-issued receipt per planned output:

- exact project/job/output binding and source-library snapshot digest;
- requirement digest and matched ordered source association/asset IDs;
- actual source SHA-256 values, channel/purpose, evidence-profile digest, and
  match rationale codes safe for internal audit;
- `resolved`, `insufficient_evidence`, `ambiguous`, `invalid`, or
  `not_applicable` state;
- cap reservation and receipt digest.

The receipt is a source-selection decision, not the final provider plan. The
owning template must validate it and produce its existing final projection.
The final plan must bind the receipt digest so a later matcher result cannot
silently replace a reference after planning or during retry.

## 5. Matching And Failure Policy

### 5.1 Candidate eligibility before ranking

The matcher must reject a candidate before ranking when its association is
inactive, source type is wrong, bytes are unreadable, actual SHA differs,
rights/consent or template role requirements are absent, it belongs to another
project, it is a generated/review/history artifact, it exceeds a declared cap,
or its profile is invalid for the current bytes.

Eligible candidates are ranked using matching evidence claims, declared user
preferences, confidence, and the current output requirement. Upload order,
filename, an opaque browser field, or a generated thumbnail is never a primary
selection factor. A deterministic tie break is allowed only after candidates
are semantically equivalent and must be recorded in the receipt.

### 5.2 Hard, preferred, and optional needs

| Requirement strength | No suitable candidate | Required system behavior |
| --- | --- | --- |
| `hard` | no reliable match | matcher reports insufficiency; server either closes with one sanitized receipt-scoped `needs_input` state before Brain/Provider dispatch, or starts one bounded new Brain planning pass that alone owns revised output intent |
| `preferred` | no reliable match | proceed only when the template can honestly deliver without it; record omission in the receipt and keep prompt ownership intact |
| `optional` | no candidate | omit the reference without treating it as failure |

For a professional hard-truth output, a front view must not silently be
substituted for a missing rear-structure proof. For ordinary General V3, a
missing optional scene inspiration must not block a valid prompt-only image.

The matcher and template never independently alter creative deliverables. The
public state names the actionable kind of missing evidence, such as
"a clearer rear or detail original would help this requested view", without
leaking asset IDs, paths, hashes, provider payloads, or internal classifier
codes. Every analysis failure, ambiguous/invalid resolution, and final-plan
validation failure binds to the exact project/job receipt, is terminal with
`loading=false` and `busy=false`, retires any progress timer/recovery owner,
and exposes one sanitized action only. It sends no automatic retry, resubmit,
or Provider call. Desktop/mobile polling reads that receipt and terminal server
state always wins over a stale browser "preparing" surface.

### 5.3 Reference-cap policy

Selection happens before the final physical plan, but it does not loosen
provider constraints. A requirement has an explicit maximum source count. The
template combines:

```text
matched original sources
+ separately required bound visual-asset evidence
+ explicit selected continuation, if any
<= negotiated provider reference cap
```

If hard inputs do not fit, the command closes or the server starts one bounded
new Brain planning pass; it does not silently drop identity, product truth, or
a matched source. Doc269 remains the E-Commerce physical-plan authority.
General and Photography retain their own capability negotiation and do not
inherit E-Commerce's five-input rule.

## 6. Template-Specific Integration

### 6.1 General V3

General V3 receives the same source-library catalog and matcher. It may use
person, object, non-human, scene, graphic, composition, palette, or negative
evidence as allowed by Doc93. Its default policy is low-friction:

- no source-library entry is required merely because a project exists;
- the absence of a weak/optional match falls back to prompt-owned generation;
- selected generated output still requires explicit continuation selection;
- a hard user request for exact source truth invokes the existing strong
  reference policy rather than being weakened by a generic match.

### 6.2 Professional E-Commerce

E-Commerce uses the generic catalog and matcher but adds its existing hard
contract:

- every product original stays in the complete Doc263 ProductTruthAdmission
  pool for validation and review;
- a product presentation, rear structure, or detail deliverable declares its
  view-specific product requirement;
- the matcher emits only the product-source cardinality already accepted by
  the current approved Doc263/Doc269 final-plan schema. Under the current
  locked-People path this is exactly one selected product original; two-source
  product matching requires a separately reviewed Doc263/Doc269 schema and
  capacity migration and is not authorized by Doc270;
- Product API freezes the selection into the existing Doc263 projection and
  Doc269 plan; unselected product originals remain pool evidence only;
- locked People visual assets remain separate identity evidence and cannot be
  selected as product originals;
- explicit generated continuation enters only through Doc265 and never repairs
  a missing product view by becoming product truth.

### 6.3 Photography, Brand, and future templates

Photography may request portrait, scene, styling, or composition support while
Doc93 retains prompt ownership. Brand may request logo/packaging/layout
evidence with its own exactness rules. A future template defines its output
requirements and hard-proof policy; it must not add a vertical-specific
taxonomy to the shared matcher. Shared terms remain orthogonal: subject,
affordance, view, detail, environment, composition, and channel.

## 7. Public UX Contract

All V3 project workspaces use one source model while retaining template
language where it is useful:

1. **Project original source library** shows only active user-uploaded
   originals. Each card can show public-safe analysis labels such as
   "object front view", "rear/structure view", "detail view", or
   "scene reference", plus uncertainty when analysis is inconclusive.
2. **Visual assets** remains a separate panel. It shows the catalog-owned
   display name and locked identity/brand purpose, never a generated fallback
   identifier.
3. **Selected continuation directions** contains only explicit user selections
   from delivered outputs, per Doc261/265.
4. **Generated and review history** remains inspection/history and is never
   considered by automatic original-source matching.
5. A planned or delivered output can show a compact "references used for this
   image" disclosure: purpose labels and public source labels only. It must
   not expose hashes, local paths, provider payloads, or hidden prompt data.
6. Users can change a usage preference, request re-analysis, remove an
   original from current automatic use, or explicitly select a continuation.
   The next command receives a new server-issued binding; no in-flight or
   historical command mutates.

Desktop and mobile consume the same server-owned source-library projection and
exact terminal job receipt. A terminal input state closes the busy surface
immediately, retires its local timer/recovery owner, and offers the applicable
single action. The UI must never say both "stopped" and "preparing" for the
same command.

## 8. Persistence, Migration, And Idempotency

1. New profiles are append-only, SHA-bound records associated with existing
   uploads. Do not alter old upload bytes or rewrite historical jobs.
2. A profile is invalidated only for the association/current-byte binding; it
   is never silently reused across projects or after file drift.
3. Existing projects without a profile retain their present behavior during
   rollout. They must not be reclassified into broken input merely because
   Doc270 analysis is unavailable. Existing jobs, retries, review/finalization,
   selected continuations, and historical project navigation consume their
   frozen existing receipts. They never create a profile, rematch a source, or
   change a physical plan.
4. Only a new explicit command admitted by the Doc270 version gate may create
   or refresh analysis before planning. Coalescing and generation
   reconciliation bind to the existing server-issued, same-project Doc268 job
   receipt, never to a browser-authored idempotency key. Repeated click, tap,
   reload, or timeout returns the one exact admitted `job_id` and its current
   receipt; it must not substitute a historical job or create another command.
5. A reference resolution is frozen into that job/output receipt. Retry,
   refresh, and final review read that receipt; they do not rerun matching and
   silently change reference sources.
6. A user explicitly changing source preferences or original associations
   creates a new current library snapshot and requires a new explicit,
   server-issued command receipt. It does not mutate the prior command.

## 9. Phased Delivery

### Phase 0: Contract and red tests

Add this document and deterministic tests. No provider, MCP, ImageGen, VPS,
or historical-project mutation. Tests first prove the current gap: a generic
valid-ID projection cannot establish that a rear/detail requirement matched
the correct original.

### Phase 1: Read-only library and analysis receipts

Add typed Source Library/Profile storage over existing uploads and server-side
file-binding analysis. The Profile must explicitly mark semantic fields as
`not_observed`/`unknown` until a versioned image-semantic analyzer has issued
evidence; use policy, filenames, upload order, or Brain output must not fill
view or affordance claims. Phase 1 may issue only a
`SourceLibraryBindingReceipt`: it proves that an already-authoritative Doc263
selected original remains bound to one active project-upload association and
its current SHA/profile/analysis receipt. It is not a
`ReferenceResolutionReceipt`, must state `bound_observe_only`, and must not
claim a view, affordance, ranking, or semantic match when analysis evidence is
unavailable. Surface public-safe availability/uncertainty in project views.
Run in observe-only mode: no planner selection or provider behavior changes.
The receipt is frozen into a new job/output. Project Mode may expose only a
server-owned enable signal to the Product API; after ProductTruthAdmission and
any Doc264 re-attestation complete, the Product API reads one fresh snapshot
through the trusted Project Mode callback, persists that exact private snapshot
with the job, and binds the receipt from it. Browser-supplied or pre-admission
snapshot payloads are ignored. `get_project` may recompute the current read
model but must never rewrite historical job bindings. Prove
legacy project compatibility and General/Professional isolation.

The shared catalog lists every current-project active `uploaded` original,
including entries that cannot currently be used automatically. Each entry
therefore exposes only public-safe binding facts plus an availability state
(`ready_verified`, `upload_not_ready`, `file_missing`, `file_unreadable`, or
`content_drift`) and eligibility flags. Visual Assets, generated/review
history, and implicit continuations never enter the catalog. Only the
E-Commerce consumer further requires a `ready_verified` entry with project
use policy `product`, upload role `product_reference`, and the authoritative
`product_truth` channel before it may compare the subset to Doc263 admission.
An invalid product association remains visible as non-eligible; it must not
make an E-Commerce command silently become prompt-only. Existing Doc263
admission owns the command-time `needs_input`/invalid closure. Upload role,
channel, and project use policy are binding facts in the analysis receipt,
never semantic evidence.

### Phase 2: Requirements and matcher in shadow mode

Add `ReferenceRequirement` and `ReferenceResolutionReceipt`. Have Brain and
templates declare requirements; compare current selection against matcher
recommendations in deterministic tests and internal audit. Do not override
current selected IDs or alter production dispatch yet.

### Phase 3: General V3 activation

Activate matcher-issued original-source projections for new, version-gated
General V3 commands with eligible uploaded originals. Preserve prompt-only
fallback only for no-source, optional, and uncertain requirements that the
Brain/template has already declared non-hard. Verify standard, mobile, reload,
the exact returned job receipt, and explicit-continuation behavior.

### Phase 4: Professional template activation

Activate E-Commerce first only for new, version-gated commands behind the
existing Doc263/269 boundaries: full admission first, matcher-selected subset
second, frozen physical plan last. Add view-aware product requirements without
changing People identity or selected-continuation authority. Photography/Brand
activation requires their own isolated acceptance gates.

### Phase 5: Guarded production acceptance

After local and browser suites pass, deploy through the normal release gate.
Verify new and legacy projects, desktop and mobile projections, no-provider
closure states, and a bounded real-provider acceptance run only with explicit
mutation boundaries. Do not use a real generation call as exploratory
debugging.

## 10. Required Test Matrix

1. Four originals with front, side, rear, and detail evidence produce a
   common source-library catalog; a front, rear, and detail requirement each
   resolve the appropriate limited source set rather than every original.
2. The same tests use a non-apparel object, a portrait-plus-environment set,
   and a scene/brand-material set to prove the shared taxonomy is not an
   apparel recipe.
3. Filename, upload order, browser-supplied view labels, stale SHA, unreadable
   file, cross-project association, and generated/history candidates cannot
   produce an authoritative match.
4. User usage annotations are SHA-bound preferences; they cannot bypass hard
   file, rights, project, channel, or visual-evidence validation.
5. General V3 can generate prompt-only with no sources and can omit an
   optional uncertain source without a false error.
6. Professional E-Commerce validates the entire product-truth pool, chooses
   the appropriate selected source subset, preserves locked People evidence,
   and passes the exact Doc269 physical-plan sequence without unselected
   originals leaking into renderer inputs.
7. A missing hard rear/detail source causes feasible replanning or one
   actionable terminal input state before provider dispatch, never an incorrect
   substitution or an indefinite preparing state.
8. Generated/review history remains excluded unless a user has an explicit,
   valid continuation receipt; a selected continuation cannot become product
   truth or original-source evidence.
9. Repeated desktop/mobile click, reload, polling, and analysis retry preserve
   one command identity and one terminal public operation.
10. Doc93 channel ownership, Doc260 review evidence, Doc261/265 UX grouping,
    Doc263/269 E-Commerce tests, Visual Asset display-name tests, Generic, and
    Photography regressions remain green.

## 11. Acceptance And Rollback

The upgrade is accepted only when all relevant phase tests pass, the final
integrated `main` is pushed, desktop/mobile views show the separated source
groups and per-output disclosure, and the guarded VPS release verifies the
exact static/runtime revision without replaying a historical job.

Rollback is feature-gated consumption of matcher receipts, not deletion of
profiles or source history. Existing source records remain auditable. If a
profile-analysis path is unavailable, the system follows the documented
compatibility behavior for that phase; it must not invent a match, inject all
originals, promote history, or leave the user in a nonterminal busy state.
