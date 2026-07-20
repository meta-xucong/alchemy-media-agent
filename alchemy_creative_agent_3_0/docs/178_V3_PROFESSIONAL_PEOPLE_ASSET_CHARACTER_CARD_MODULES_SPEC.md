# Doc178 — V3 Professional People Asset Character Card Modules

## Status and authority

```text
AUTHORITATIVE_PROFESSIONAL_CHARACTER_CARD_EXTENSION
DOCUMENT_AND_CONTRACT_ONLY
NO_STANDARD_MODE_CHANGE
NO_AUTOMATIC_ASSET_ACTIVATION
NO_PRODUCTION_GATE
```

This document extends the Visual Asset Library / People Asset architecture. It
does not replace Doc173's library ownership and project binding, Doc174/177's
workspace and binding UX, Doc176's Face Identity source admission, or the
shared Doc93/95/96/97/100/101/121/128/134–140 execution contracts.

Where an earlier Professional document says that the first release contains
only Face Identity, or that body and expression dimensions are future work,
this document is the newer authority for the Character Card extension. The
earlier text remains historical context and compatibility guidance; it must not
be used to block the three sibling modules defined here.

## 1. Product definition

A **Character Card** is a structured set of independent visual-asset slots for
one People Asset. It is not one generated collage and it is not a new Provider,
Brain, review, retry, or storage system. A contact sheet may be rendered by the
UI for viewing, but every slot remains an independent image with its own
candidate history, review receipt, winner, provenance, and version.

```text
Visual Asset Library
└── People Asset
    ├── Face Identity
    ├── Expression Set
    └── Body Silhouette
```

The three modules are siblings in the asset model. Their creation lifecycle is
ordered because later modules depend on a complete identity foundation:

```text
Face Identity → Expression Set → Body Silhouette
```

An empty slot is a valid, visible state. It must never be silently filled by a
source image, an unreviewed candidate, a Standard Mode reference, or a local
synthetic placeholder.

## 2. Compatibility and boundaries

### 2.1 Standard Mode

Standard Mode is unchanged. It does not read Character Card slots, infer
Professional Mode from keywords, bind a People Asset, or fall back from a
Professional asset failure.

### 2.2 Existing Professional contracts

Doc173 remains authoritative for library-scoped ownership, explicit project
bindings, frozen job snapshots, and public asset lifecycle. Doc174 and Doc177
remain authoritative for workspace navigation and binding UX. Doc176 remains
authoritative for one primary plus one supplementary Face Identity source and
the bounded 2/3/5 evidence budget.

Character Card modules contribute typed, reviewed evidence only. Remote Brain
still owns the semantic task profile and final canonical Provider prompt.
Existing GPT Image 2 Provider materialization, shared Vision review, bounded
retry, winner selection, append-only history, and activation gates are reused.

No module may emit local prompt prose, negative-prompt recipes, keyword
activation, private scoring, private repair, or a private image store.

## 3. Standard Character Card template

Every People Asset may expose this template, regardless of whether all slots
have been generated:

### 3.1 Face Identity slots

```text
face.front
face.front_three_quarter       # approximately 45°
face.profile                   # approximately 90°
face.reverse_three_quarter     # approximately 135°
face.rear_head                 # approximately 180°
```

### 3.2 Expression Set slots

```text
expression.neutral             # references face.front winner
expression.smile
expression.anger
expression.sad                  # user-facing name: 悲伤
```

“悲伤” replaces “哭泣” in all new user-facing labels and contracts. The slot
means a believable sad emotional state; it does not require tears unless the
user explicitly requests them.

### 3.3 Body Silhouette slots

```text
body.front_full
body.side_full
body.rear_full
```

The template is a slot contract, not a requirement that every People Asset be
complete. The UI must show `未生成` / `待补齐` for empty slots and explain what
the slot enables.

## 4. Module-specific generation contracts

The modules share infrastructure but do not share one generic generation
algorithm. Each module has its own input ownership and reference policy.

### 4.1 Face Identity

Face Identity contains the existing approved workflow plus two additional face
coverage slots.

The base sequence remains:

```text
root source
→ front: 3 candidates → shared review → winner
→ front_three_quarter: 3 candidates → shared review → winner
→ profile: 3 candidates → shared review → winner
```

Only `face.reverse_three_quarter` and `face.rear_head` may continue the existing
serial face workflow: approved standard views are used as the next-stage
identity evidence together with the permitted root/derived evidence budget.
The exact evidence selection remains server-owned by the existing resolver;
the module must not hand-build prompt text or exceed the established budget.

The Face Identity module is complete only when all five requested face slots
have either a reviewed winner or an explicit user decision to leave the slot
empty. An unreviewed image is never a winner.

### 4.2 Expression Set

Expression generation is deliberately **not** a serial chain.

The only visual identity source for every generated expression is the final
selected `face.front` winner:

```text
face.front winner → smile candidates → smile winner
face.front winner → anger candidates → anger winner
face.front winner → sad candidates → sad winner
```

Each non-neutral expression is generated independently with three candidates,
shared Vision review, and at most one existing bounded repair. A generated
smile must never become the reference for anger, and anger must never become
the reference for sadness.

`expression.neutral` is an alias to the approved `face.front` winner; it does
not trigger another generation job.

Prompt-owned expression intent may describe intensity or emotional nuance, but
the module cannot add facial descriptions or local expression recipes. The
identity geometry, age direction, and person continuity remain anchored to the
front winner.

### 4.3 Body Silhouette

Body Silhouette is an independent body-modeling workflow. It is not a copy of
the Face Identity serial reference chain and it does not use Expression Set
outputs as body references.

Its inputs are, in priority order:

1. a user-authorized full-body reference, if supplied;
2. explicit user-authored height, weight, build, or proportion information;
3. if neither exists, a Brain-owned body direction inferred from the approved
   face identity, requested developmental stage, and current user intent.

The three approved Face Identity views — front, profile, and rear head — are
used only to establish that the body belongs to the same person and to keep
age/presentation continuity. They are not treated as precise measurements of
body proportions.

The source class is recorded as:

```text
body_source = observed          # full-body reference supplied
body_source = user_described     # explicit physical constraints supplied
body_source = brain_inferred     # no body information supplied
```

`brain_inferred` is a valid generated character direction but is not evidence
that the system recovered the user's real body. The UI and provenance must not
claim more precision than the source supports.

The body sequence is:

```text
freeze body_preparation_intent
→ front_full: 3 candidates → shared review → winner
→ side_full: 3 candidates → shared review → winner
→ rear_full: 3 candidates → shared review → winner
```

This sequence is body-specific: the body intent and body evidence package are
recomputed for the module, while the shared Provider, Vision, retry, and
append-only history services are reused. Default capture clothing is simple
and neutral so that it does not silently become a wardrobe lock. Clothing,
hair, accessories, and styling remain separate future asset dimensions unless
explicitly governed by another approved module.

## 5. Staged creation and completion modes

### 5.1 One-click full creation

“生成完整角色卡” is an orchestration request, not one giant image job. The
system executes and checkpoints:

```text
Face Identity
→ Expression Set
→ Body Silhouette
```

If a stage fails, completed winners remain append-only and the next stage does
not start. The user can resume from the first incomplete stage without
regenerating existing winners.

### 5.2 Incremental completion

The user may create only Face Identity first, then later add Expression Set and
Body Silhouette. Existing slots are read back from the server and skipped.
Only explicitly requested empty or stale slots are generated.

The public asset can therefore be:

```text
Face Identity: active
Expression Set: partial
Body Silhouette: empty
```

This is a partial Character Card, not a failed asset. A job that requires a
missing slot must ask the user to complete that module or clearly state that
the strict Character Card guarantee is unavailable; it must not silently use a
Standard reference or an unreviewed image.

## 6. State, versioning, and invalidation

Each slot and module has independent lifecycle state:

```text
empty | preparing | reviewing | winner_selected | active | stale | blocked
```

Each module version records its dependency versions. A new Face Identity
version marks dependent Expression Set and Body Silhouette versions `stale`;
it does not delete their append-only history. Replacing an expression does not
invalidate Face Identity. Replacing Body Silhouette does not invalidate the
face or expression modules.

Activation is explicit and versioned. Face Identity may be activated as the
base module; Expression Set and Body Silhouette can be activated only after
their prerequisites and their own review evidence are complete.

## 7. Reference, provenance, and review invariants

For every candidate and winner, retain:

```text
slot and module version
source class and consent provenance
admitted reference IDs and budget receipt
canonical prompt/reference parity receipt
candidate/review/retry/final-winner lineage
shared Vision verdict and issue codes
```

The source root and generated standard images are references, not prompt text.
No module may expose raw prompt, hash, Provider, or internal job identifiers in
the beginner-facing surface.

The three candidate rule is a bounded quality contract, not permission to
generate unbounded alternatives. Existing review thresholds and production
gates remain unchanged.

## 8. Conflict audit and precedence

The following earlier statements conflict with this extension only on module
scope or sequencing:

| Earlier document | Conflicting statement | Doc178 resolution |
| --- | --- | --- |
| Doc173 | “第一阶段只开放 People Asset / Face Identity”; first release only declares Face Identity | Keep Doc173 for library/binding/freeze; Doc178 supersedes the future-module limitation once Character Card work is approved. |
| Doc174 | Current phase only creates/selects People Asset / Face Identity | Keep workspace/navigation rules; the People Asset detail workspace now exposes the Character Card template and staged slots. |
| Doc176 | “For the first Face Identity release” and its two-source / 2/3/5 contract | Keep source admission and Face Identity budget; Doc178 adds no new initial source and does not alter 2/3/5. |
| Doc177 | First picker offers only the active People Asset category | Keep picker and binding semantics; Character Card is a module state inside People Asset, not a new asset category. |
| `PROFESSIONAL_MODE_VISUAL_ASSET_LIBRARY_AND_PEOPLE_ASSET_MODULE_SPEC.md` | First release contains only Face Identity; body is future; Face Identity has only front/three-quarter/profile | Keep library, consent, Brain-first, and shared-runtime rules; Doc178 supersedes only module coverage and staged creation. |
| `PROFESSIONAL_MODE_IMPLEMENTATION_HANDOFF_AND_ACCEPTANCE.md` | M0–M5 implement Face Identity only; body/style are not inferred or activated | Keep historical M0–M5 acceptance records; new implementation follows Doc178's sibling modules and ordered gates. |
| `PROFESSIONAL_MODE_DOCUMENT_SET_INDEX.md` | Professional capability is described as Face Identity-only | Update the index to list Doc178 as the Character Card extension authority. |

No conflict exists with Standard Mode, General/E-Commerce/Photography
semantics, Doc93 reference ownership, Brain prompt ownership, the shared
Provider, shared Vision, retry, final delivery, or production-gate rules.

## 9. Implementation and acceptance plan

Implementation must be additive and independently testable:

1. add the slot/module contracts and empty-slot readback;
2. route Face Identity's two additional views through the existing face host;
3. add the independent Expression Set preparation contract using only the
   front winner;
4. add the independent Body Silhouette preparation contract and source-class
   provenance;
5. add ordered lifecycle gates and stale dependency handling;
6. add Professional-only UI states, resume behavior, and cross-mode isolation;
7. run shared review/retry/parity tests and real-pixel acceptance separately.

Required negative tests include:

```text
expression chaining from smile → anger or anger → sadness is rejected
body generation before Face Identity or Expression Set completion is rejected
empty slots are never filled by Standard uploads or synthetic records
brain_inferred body is never presented as observed body truth
old Face Identity references cannot override a newer active module version
Standard/General/E-Commerce/Photography never acquire Character Card semantics
```

This document authorizes design and implementation planning only. It does not
declare any Character Card module, real Provider run, M5, Gate C/D, or
production visual-asset capability complete.
