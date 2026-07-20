# Doc178 Character Card implementation handoff

## Scope

This branch implements the additive Professional Mode Character Card seams
specified by
`docs/178_V3_PROFESSIONAL_PEOPLE_ASSET_CHARACTER_CARD_MODULES_SPEC.md`.
Standard Mode, General, E-Commerce, and Photography remain unchanged and do
not infer Professional Mode from keywords.

The implementation keeps the existing shared Brain → Provider → Vision →
bounded retry → winner/history path. It adds no provider, prompt builder,
reviewer, retry engine, or image store.

## Implemented contract

- Face Identity preserves the historical three-view activation contract and
  exposes five visible slots. The `reverse_three_quarter` and `rear_head`
  slots opt into the existing serial `AnchorPackPreparationService` through
  `face_view_scope="character_card"`; the base three-view pack is not silently
  reclassified as a complete five-view card.
- Expression Set has `neutral` as an alias of `face.front`; `smile`, `anger`,
  and `sad` (`悲伤`) each use the same front winner and an independent bounded
  three-candidate request. Missing user/Brain expression intent blocks rather
  than inventing a local recipe.
- Body Silhouette is independent from Expression Set. It records
  `observed`, `user_described`, or `brain_inferred`, requires three Face
  continuity references, keeps neutral clothing unlocked, and refuses an
  observed source without body evidence and consent provenance.
- Slot states are explicit (`empty`, `preparing`, `reviewing`,
  `winner_selected`, `active`, `stale`, `blocked`). Preparation produces
  `winner_selected`; activation is a separate confirmed action. A Face update
  marks dependent Expression/Body slots stale while retaining append-only
  metadata history.
- Library lifecycle/read projections expose only module and slot state. New
  Character Card routes accept only the stage/module user action; prompt,
  candidate, provider, path, hash, and lineage details remain server-owned.

## Verification

- Doc178 focused contract and orchestration tests: 14 passed.
- Professional Face Identity/catalog/library/Doc173/Product API subset: 65
  passed.
- Character Card library/route/host subset: 51 passed.
- `compileall` and `git diff --check`: passed.
- Full V3: 1053 passed, 1 failed. The failure reproduces in isolation in the
  existing `PersistentProjectStore` timeline temporary-file write test and is
  outside the changed files; it is not a Character Card failure.

No real Provider/Vision run, M5 acceptance, Gate C/D, or production gate is
claimed by this branch.
