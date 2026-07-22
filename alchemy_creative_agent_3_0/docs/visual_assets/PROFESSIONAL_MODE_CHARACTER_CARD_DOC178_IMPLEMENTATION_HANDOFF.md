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

Doc186 now governs renderer-prompt shape for later Character Card slots. This
handoff's "no prompt builder" rule remains unchanged: local code still cannot
rewrite prompts. The Remote Brain must instead sign reference-led slot-delta
prompts for later face views, Expression Set and Body Silhouette.

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
- Library lifecycle/read projections expose only module and slot state. The
  registered Character Card HTTP routes accept only the stage/module action
  plus the typed body source declaration (`observed`, `user_described`, or
  `brain_inferred`). Asset IDs are resolved server-side; prompt, candidate,
  provider, path, hash, and lineage details remain server-owned.
- Production stage routes are fail-closed unless an injected host explicitly
  advertises the existing shared V3 runtime and returns a verified shared
  review/retry/final-winner receipt. `CharacterCardPreparationService` remains
  an offline contract helper and cannot be used as a local production fallback.
- The historical first-release Face Identity wording in Doc173 remains a
  historical boundary; Doc178 is authoritative for the nested Character Card
  modules and does not change Standard Mode or the Visual Asset category.

## Verification

- Doc178 contract/orchestration plus HTTP/host regressions: 36 passed.
- Professional/Doc162/Doc165/Doc166/Doc173/Doc174/Doc178 and M0-M5
  compatibility subset: 146 passed.
- `compileall` and `git diff --check`: passed.
- A bounded full-V3 invocation was started but produced no progress for several
  minutes on this Windows worker and was stopped; it is not reported as a
  pass. The previously known `PersistentProjectStore` timeline temporary-file
  race remains outside the changed files and still requires mainline's normal
  full-suite environment to classify.

No real Provider/Vision run, M5 acceptance, Gate C/D, or production gate is
claimed by this branch.
