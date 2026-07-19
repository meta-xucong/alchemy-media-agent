# Professional Mode Document Set Index

## Status And Scope

```text
DOC173_LIBRARY_FIRST_RECONSTRUCTION_AUTHORITATIVE
LEGACY_PROJECT_SCOPED_COMPATIBILITY_RETAINED_READ_ONLY
FRONTEND_RECONSTRUCTION_REQUIRED
NO_STANDARD_MODE_CHANGE
NO_PRODUCTION_ASSET_CLAIM
```

This is the index for the independent Professional Mode document set. The set
is intentionally unnumbered and lives under `docs/visual_assets/`. It does not
rename, edit, supersede, or reinterpret the existing numbered V3 documents.

The forward product model is **Visual Asset Library first**: users build and
explicitly activate reusable assets in a dedicated library, then optionally
bind one or more compatible assets to a normal template project. It is not a
new General Template mode, E-Commerce slot system, Photography role system, or
second image-generation product. “Professional Mode” is retained as a
historical name for the Face Identity/Anchor Pack capability, not a required
new-project toggle.

The first release intentionally implements only Face Identity. Future body,
hair, styling, or other identity dimensions must enter as independently
versioned modules with their own channel ownership, evidence, review, and
activation contracts.

## Document Inventory

### Current Forward Authority — Doc173

`../173_V3_VISUAL_ASSET_LIBRARY_FIRST_PROFESSIONAL_WORKSPACE_RECONSTRUCTION_SPEC.md`

Defines the authoritative forward architecture:

```text
library-scoped Visual Assets rather than project-owned assets
People Asset / Face Identity as the first asset type
explicit project VisualAssetBindingSet and immutable Job snapshot
dedicated Visual Asset Library workspace plus project binding modal
legacy project-scoped read compatibility and explicit promotion only
Brain-owned canonical prompt and shared Provider/Review/Retry reuse
future multi-asset composition without a product/scene implementation today
```

All new implementation must use Doc173. It does not invalidate historical M5
or Provider evidence, and it does not open a production gate.

### Primary Product Contract

`PROFESSIONAL_MODE_VISUAL_ASSET_LIBRARY_AND_PEOPLE_ASSET_MODULE_SPEC.md`

Defines:

```text
original Standard/Professional separation and Face Identity boundary
Visual Asset Library mother boundary
historical project-scoped People Asset and mode-toggle design
modular People Asset structure with Face Identity as the first module
Identity Anchor Pack preparation and activation
root truth and prompt-owned channel rules
shared-module reuse and non-duplication boundaries
future Video compatibility boundary
```

It remains the source for inherited Face Identity, Anchor Pack and shared-path
invariants. Its project-scoped ownership, explicit creation-mode and forward
frontend sections are superseded by Doc173.

### Implementation And Acceptance Handoff

`PROFESSIONAL_MODE_IMPLEMENTATION_HANDOFF_AND_ACCEPTANCE.md`

Defines:

```text
implementation milestones
shared-runtime integration seam
isolation and compatibility tests
pack-building evidence requirements
review/retry/final-delivery gates
mainline handoff and production-claim limits
```

It is subordinate to the primary product contract and must not invent a second
runtime contract.

### Standard-Change Impact Review Protocol

`PROFESSIONAL_MODE_STANDARD_CHANGE_IMPACT_REVIEW_PROTOCOL.md`

Defines the repeatable handoff, impact classification, append-only register,
and audit procedure to run after Standard Mode changes. It is the operating
mechanism for deciding whether the Professional Mode/Face Identity documents
need a compatible adaptation.

### Asset Channel Authority And Reference Admission

`PROFESSIONAL_MODE_ASSET_CHANNEL_AUTHORITY_AND_REFERENCE_ADMISSION_SPEC.md`

Defines:

```text
Visual Asset owned-channel claims and future module extensibility
Professional Asset Binding Set semantics
automatic reference-channel admission and authority conflict resolution
safe suppression of competing identity channels
Provider/Reviewer evidence parity and fail-closed behavior
backend-first implementation and test gates before frontend work
```

It is the backend authority for keeping Professional Mode invisible during
normal use while preventing non-selected references from overriding an active
Visual Asset's owned channels.

### M5 Real-Pixel Acceptance Record

`PROFESSIONAL_MODE_M5_REAL_PIXEL_ACCEPTANCE_BLOCKED_20260717.md`

Records the superseded non-counting Provider pre-flight. It does not certify
pixels or open a production gate.

`PROFESSIONAL_MODE_M5_REAL_PIXEL_PROVIDER_RUN_20260717.md`

Records the later user-authorized V3 default-Provider run: one real GPT Image 2
artifact and its reference/output fingerprints, followed by a bounded shared
review timeout. It remains non-counting M5 evidence and does not open a
production gate.

### M5 View-Conditioned Evidence and Renderer Parity

`PROFESSIONAL_MODE_VIEW_CONDITIONED_EVIDENCE_AND_RENDERER_PARITY_SPEC_20260718.md`

Defines the bounded 2/3/5 view-conditioned evidence compiler, the
pre-Provider readiness gate, the host renderer-parity receipt, and the
explicit metadata-only binding resolver. It does not weaken shared Vision,
create a second renderer, or certify M5 pixels.

`PROFESSIONAL_MODE_M5_REAL_BINDING_PREFLIGHT_20260718.md`

Records the current real-pixel preflight: no server-owned active People Asset
and Face Identity anchor pack was available, so M5 correctly stopped before
Provider materialization. It is non-counting evidence and does not open any
production gate.

`PROFESSIONAL_MODE_M5_CHILD_REAL_PIXEL_RERUN_20260718.md`

Records the fresh rerun using the earlier child reference. The real Brain and
GPT Image 2 Provider produced three front candidates plus one bounded retry;
shared Vision still rejected all of them for human-skin/AI-polish defects, so
the serial chain stopped before three-quarter and profile. It is non-counting
evidence and does not open any production gate.

### Doc165 Technical M5 And Doc166 Quality Reopening

`../165_V3_PROFESSIONAL_ANCHOR_VIEW_SIGNOFF_AND_STAGE_REPAIR_BUDGET_SPEC.md`

Records the completed local serial M5 execution, unchanged identity/view gates,
shared review, bounded repair, winner persistence and explicit activation. This
remains valid technical evidence for that exact run.

`../166_V3_SHARED_DEVELOPMENTAL_AGE_COHERENCE_AND_PROFESSIONAL_NEUTRAL_ANCHOR_QUALITY_SPEC.md`

Reopens the narrower approximately-six-year-old visual-quality claim after
side-by-side human review found developmental-age drift, adult gaze/styling,
yellow/muddy skin, synthetic texture and inconsistent grey capture conditions.
It keeps the same architecture and requires a shared, Brain-owned age-coherence
refinement plus a Professional-only neutral evidence-capture objective. It does
not invalidate Doc165 lifecycle evidence, add a child module or open production.

`PROFESSIONAL_MODE_M5_PROVIDER_EQUIVALENT_CLOSEOUT_20260719.md`

Records the model-ready fresh Product API run, the complete five-reference
profile materialization receipt, and three canonical-prompt MCP profile
candidates reviewed through the shared Professional Vision contract. Under the
operator-approved Provider/MCP equivalence rule, image-channel quality is
accepted. The record does not import MCP pixels, activate a Product API pack or
open the Professional production gate.

### Persistent People Asset Lifecycle And Controlled Runtime Handoff

`PROFESSIONAL_MODE_PERSISTENT_ASSET_LIFECYCLE_AND_CONTROLLED_RUNTIME_HANDOFF_20260718.md`

Records the historical project-scoped create/read/activate routes, explicit
user-confirmation boundary, append-only catalog history, and controlled app's
`PersistentVisualAssetCatalog` injection. The persistence and Anchor Pack
seam may be reused, but new writes/UX are superseded by Doc173's library and
binding contracts.

## Compatibility Authority

The effective authority is selected by the execution mode:

| Execution context | Authority | Allowed effect |
| --- | --- | --- |
| Asset-free project | Existing numbered V3 documents and current implementation | Current Standard path; no Visual Asset lookup or implicit block. |
| Asset-bound project / Job | Doc173 for library/binding/freeze, plus existing shared V3 documents for execution | Use one or more explicitly bound, active, non-overlapping asset versions; first release UI exposes one People Asset only. |
| Explicit invalid binding | Doc173 | Block safely; never silently discard the selected asset or run as asset-free. |
| Shared Provider / review / retry / delivery | Existing Doc93/95/96/97/100/101/121/128 contracts | No replacement provider, registry, reviewer, retry loop, or storage. |
| Shared Brain semantic/prompt gates | Existing Doc134/135/136/137/138/139/140 contracts | Face Identity supplies typed evidence only; missing profile, activation intent, canonical prompt/hash, or required Human Realism sign-off blocks. |

The Professional Mode set may narrow or strengthen an existing shared contract
for the selected asset, but may not weaken, bypass, or globally rewrite it.

## Existing Documents Kept Intact

The following remain unchanged and continue to apply:

```text
Doc93  reference-channel policy and prompt ownership
Doc95  portrait identity evidence and best-result closure
Doc96  high-fidelity identity measurement and bounded shared rerender
Doc97  subject continuity package and adaptive reference routing
Doc100 GPT Image 2 sole-renderer governance
Doc101 capability activation and frozen-plan governance
Doc121 review/reference evidence continuity
Doc128 shared Human Realism constraints and review closure
Doc134 semantic ownership and heuristic retirement
Doc135 forward creative-logic eradication and document authority
Doc136 Human Realism semantic sign-off and lean review closure
Doc137 Human Realism Brain semantic preflight and re-signing
Doc138 Human Realism natural-presence Brain deliverable
Doc139 independent Human Realism Brain re-signing
Doc140 complete Remote Brain semantic task-profile requirement
```

The current integration target is the post-Doc140 shared forward path:

```text
sanitized frozen VisualAssetBindingSet + asset evidence
  -> complete Remote Brain semantic task profile and activation intent
  -> frozen CapabilityActivationPlan
  -> complete signed canonical Provider prompt and hashes
  -> Human Realism preflight/re-signing when active
  -> exact Provider prompt materialization
  -> shared real-pixel review, bounded retry, and final delivery
```

The People Asset/Face Identity documents add lifecycle and evidence binding to
this path. They do not author prompt prose, perform local semantic fallback,
create a second reviewer/provider, or change the asset-free Standard path.

Standard Mode's existing `ProjectIdentityAnchor`, `SubjectIdentityCard`,
`auto_batch_identity_anchor`, and Doc97 continuity records remain valid. They
are not automatically converted into People Assets.

## Non-Negotiable Set Boundaries

```text
Do not edit or renumber old documents to make this mode fit.
Do not put Visual Asset Library or asset-binding semantics into General
variation_mode or a vertical role.
Do not add a second reference registry, image store, Provider, Brain, review,
  retry, or final-delivery system.
Do not send a synthetic white-background face card as unrestricted Provider
  evidence; use the existing Doc95 evidence preparation path.
Do not use local face swap, canvas compositing, or private pixel repair.
Do not claim Provider Gate, Gate C/D, P10, or production readiness from pack
  creation alone.
Do not let Standard Mode UI, defaults, keyword heuristics, or local prompt
fragments become implicit Professional Mode behavior.
```

## Change-Management Rule

Future Professional Mode decisions should add or revise files in this
directory. A change is compatible only when it:

1. leaves Standard Mode behavior unchanged;
2. identifies the Professional Mode scope in the document itself;
3. names which existing shared authority remains responsible;
4. preserves frozen activation, shared review/retry, and append-only history;
5. adds an isolation regression before any runtime implementation.

6. records every Standard Mode impact audit in the append-only impact register;
7. treats shared-contract changes as `REVIEW_REQUIRED`, `ADAPT_REQUIRED`, or
   `BLOCKED` until inspected, rather than assuming they are Standard-only.

Shared-capability changes in Standard Mode are reviewed for Professional Mode
impact. If a shared contract changes, the adapter records the supported
contract version and either adapts explicitly or returns a structured
incompatibility block; it never silently migrates or reinterprets an active
People Asset.

If a future change would require changing Standard Mode or a shared numbered
contract, it must first be proposed as a separate architecture decision. It
must not be smuggled into a People Asset document.
