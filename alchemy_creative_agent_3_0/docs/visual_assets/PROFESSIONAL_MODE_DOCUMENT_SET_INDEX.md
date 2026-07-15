# Professional Mode Document Set Index

## Status And Scope

```text
PROPOSED_ARCHITECTURE
DOCUMENT_ONLY
NO_STANDARD_MODE_CHANGE
NO_PRODUCTION_ASSET_CLAIM
```

This is the index for the independent Professional Mode document set. The set
is intentionally unnumbered and lives under `docs/visual_assets/`. It does not
rename, edit, supersede, or reinterpret the existing numbered V3 documents.

Professional Mode is an explicit opt-in asset-source mode. It is not a new
General Template mode, E-Commerce slot system, Photography role system, or
second image-generation product.

The first release intentionally implements only Face Identity. Future body,
hair, styling, or other identity dimensions must enter as independently
versioned modules with their own channel ownership, evidence, review, and
activation contracts.

## Document Inventory

### Primary Product Contract

`PROFESSIONAL_MODE_VISUAL_ASSET_LIBRARY_AND_PEOPLE_ASSET_MODULE_SPEC.md`

Defines:

```text
Standard Mode / Professional Mode separation
Visual Asset Library mother boundary
project-scoped People Assets and multiple-asset selection
modular People Asset structure with Face Identity as the first module
Identity Anchor Pack preparation and activation
root truth and prompt-owned channel rules
shared-module reuse and non-duplication boundaries
future Video compatibility boundary
```

This is the product and architecture authority for the Professional Mode
overlay.

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

## Compatibility Authority

The effective authority is selected by the execution mode:

| Execution context | Authority | Allowed effect |
| --- | --- | --- |
| Standard Mode | Existing numbered V3 documents and current implementation | No People Asset lookup, no Professional Mode metadata, no new block or fallback. |
| Professional Mode with an active selected People Asset | This document set for asset selection/lifecycle, plus existing shared V3 documents for execution | Use exactly one selected project People Asset and its active Face Identity module/pack version in the first release. |
| Professional Mode without a valid asset/pack | This document set | Block safely; never silently run Standard Mode. |
| Shared Provider / review / retry / delivery | Existing Doc93/95/96/97/100/101/121/128 contracts | No replacement provider, registry, reviewer, retry loop, or storage. |

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
```

Standard Mode's existing `ProjectIdentityAnchor`, `SubjectIdentityCard`,
`auto_batch_identity_anchor`, and Doc97 continuity records remain valid. They
are not automatically converted into People Assets.

## Non-Negotiable Set Boundaries

```text
Do not edit or renumber old documents to make this mode fit.
Do not put Professional Mode into General variation_mode or a vertical role.
Do not add a second reference registry, image store, Provider, Brain, review,
  retry, or final-delivery system.
Do not send a synthetic white-background face card as unrestricted Provider
  evidence; use the existing Doc95 evidence preparation path.
Do not use local face swap, canvas compositing, or private pixel repair.
Do not claim Provider Gate, Gate C/D, P10, or production readiness from pack
  creation alone.
```

## Change-Management Rule

Future Professional Mode decisions should add or revise files in this
directory. A change is compatible only when it:

1. leaves Standard Mode behavior unchanged;
2. identifies the Professional Mode scope in the document itself;
3. names which existing shared authority remains responsible;
4. preserves frozen activation, shared review/retry, and append-only history;
5. adds an isolation regression before any runtime implementation.

If a future change would require changing Standard Mode or a shared numbered
contract, it must first be proposed as a separate architecture decision. It
must not be smuggled into a People Asset document.
