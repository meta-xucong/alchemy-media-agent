# Professional Mode Persistent People Asset Lifecycle And Controlled Runtime Handoff

## Status

```text
FORMAL_LIFECYCLE_ENTRY_ADDED
PERSISTENT_CATALOG_INJECTED_IN_CONTROLLED_APP
M5_PIXEL_ACCEPTANCE_STILL_BLOCKED
NO_PRODUCTION_GATE_CHANGE
```

This document records the minimum runtime seam required to make a project
scoped People Asset resolvable after a controlled-service restart. It does not
certify any pixels and does not activate a pack by metadata alone.

> **Forward lifecycle replacement.** The persisted catalog, ready-upload
> admission and shared `AnchorPackPreparationService` described here remain
> reusable. Its project-scoped ownership and routes are legacy compatibility
> only after Doc173. New assets are library-scoped, new projects receive
> explicit bindings, and new Jobs freeze that binding set as defined in Doc173
> §§3–4. This historical handoff must not be used to introduce new
> `/projects/{project_id}/people-assets` writes.

## Root cause of the pre-Provider block

The Professional contracts and `AnchorPackPreparationService` already existed,
but only injected test/host code could call them. The deployed Product API
constructed its default `V3ProductApiService` with an in-memory visual-asset
catalog, and it exposed no formal People Asset lifecycle routes. A restart
therefore discarded the catalog and `_bind_professional_mode()` correctly
returned `professional_people_asset_not_found`.

## Formal lifecycle now available

> The following routes are retained for historical reads and controlled
> promotion only. Doc173 defines their replacement public surface.

The additive Product API seam is:

```text
POST /api/v3/creative-agent/projects/{project_id}/people-assets
  -> create a project-scoped draft People Asset
  -> requires a V3 uploaded image whose status is `ready`, explicit
     consent_reference, and one complete user-authored preparation_intent
  -> freezes preparation_intent immutably; it is Remote Brain input, not a
     locally authored renderer prompt or structured visual recipe

GET /api/v3/creative-agent/projects/{project_id}/people-assets
GET /api/v3/creative-agent/projects/{project_id}/people-assets/{people_asset_id}

POST /api/v3/creative-agent/projects/{project_id}/people-assets/{people_asset_id}/prepare
  -> invokes an explicitly injected shared AnchorPackPreparationHost
  -> accepts an empty public payload; Brain plan, canonical prompt, references,
     Provider calls, and Vision review remain server-owned
  -> fails closed with `professional_anchor_pack_prepare_unavailable` when no
     shared host is configured
  -> fails closed when a legacy People Asset has no frozen preparation_intent;
     the empty payload cannot supply or replace one

POST /api/v3/creative-agent/projects/{project_id}/people-assets/{people_asset_id}/activate
  -> requires an existing complete reviewed pack_version_id and an injected
     shared activator; the activator changes review -> active
  -> requires confirm_activation=true
  -> updates the People Asset and Face Identity active pointers
  -> appends catalog history
```

Pack preparation remains the existing injected `AnchorPackPreparationService`
contract. It must produce all nine bounded candidates, shared review decisions,
serial root/front/three-quarter/profile evidence, and a `review` pack before
`activate()` can make the pack active. No route accepts arbitrary candidate
metadata as a substitute for that service.

Every bounded view candidate receives the exact frozen preparation intent as
its Product API `user_input`. The server-owned `view_role`, candidate ordinal
and serial reference chain remain typed metadata. The host must not replace the
intent with a generic front/three-quarter/profile sentence or append a local
quality recipe; Remote Brain authors the complete final prompt for each view.

The prepare/activation route is only a formal shared-service seam; it is not a
local generator or a metadata switch. The
controlled app intentionally leaves the host unset until the authenticated
runtime wires the existing shared Brain/Provider/Vision adapters. Therefore a
prepare request cannot silently fall back to General, MCP-only planning, a
synthetic pack, or a private review/retry path.

The route resolves `root_source_asset_id` through the existing Product API upload
store and fails closed unless the upload has completed image validation. A raw
path, temporary pytest catalog record, historical image, or caller-claimed
provenance cannot create a draft binding.

## Persistence and binding

> For new paths, `PersistentVisualAssetCatalog` is a physical persistence
> mechanism, not proof that ownership remains project-scoped. New resolvers
> must resolve a library asset then a project binding/frozen snapshot.

The controlled app now injects `PersistentVisualAssetCatalog` into the V3
Product API. Its root is `V3_VISUAL_ASSET_CATALOG_ROOT` when configured, or the
deployment-local `.media_storage/v3_visual_assets` directory by default. The
catalog stores metadata and append-only lifecycle history only; image bytes
remain in the existing V3 asset/output stores.

At generation time the existing `_bind_professional_mode()` resolver reads the
project-scoped active People Asset and active Face Identity pack, validates
project/asset/module/pack ownership and user activation, then freezes the
sanitized binding before Brain planning. Standard Mode never consults this
catalog.

## Acceptance boundary

This seam makes a real binding possible; it does not create a passing pack.
The supplied child source still needs a fresh real run through:

```text
front: 3 candidates -> shared Vision -> winner / one bounded repair
three-quarter: root + front winner -> 3 candidates -> winner
profile: root + front + three-quarter winner -> 3 candidates -> winner
```

Until all stages pass with prompt/reference parity and append-only provenance,
Professional M5, Gate C/D, P10, and production availability remain blocked.
