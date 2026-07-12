# PX Mainline Request: Trusted Photographer Profile Selection

## 1. Request Status

```text
request_id: PHOTOGRAPHY-MAINLINE-001
status: open - blocking
blocking_phase: P5 Named Photographer Catalog And UI
request_owner: Photography Module
implementation_owner: mainline public API / frontend / persistence owners
```

## 2. Current Mainline Behavior

`CreateCreativeJobRequest` has no typed photographer profile fields. The shared
frontend has no Photography profile catalog or deliberate selection control,
and project/job persistence has no immutable resolved `PhotographerProfileBinding`.
Using free-form `metadata` would not provide trusted selection provenance and
is explicitly rejected as a workaround.

## 3. Minimal Requested Change

Add these product-level request fields to the shared create-job contract:

```python
photographer_profile_id: str | None = None
photographer_profile_selection_source: Literal["user_explicit_ui"] | None = None
```

Add a read-only catalog route under the existing namespace:

```text
GET /api/v3/creative-agent/scenarios/photography/photographer-profiles
```

The shared frontend Photography workspace must render:

```text
General Photography (default)
Named photographer catalog (no implicit selection)
one deliberate click/confirmation before a named ID is submitted
clear unavailable/expired/region-restricted blocked state
```

The server, not the client, resolves and persists:

```python
binding_mode: Literal["general", "named"]
profile_id: str
profile_version: str
selection_source: Literal["user_explicit_ui"] | None
catalog_version: str
availability_decision: str
technique_package_checksum: str
pinned_at: str
```

These resolved fields are server-owned and must not be accepted as client
overrides.

## 4. Validation And Error Semantics

```text
profile_id is null -> bind General Photography; selection_source must be null
General profile ID -> bind General Photography; selection_source must be null
named ID + user_explicit_ui -> validate availability and pin exact version
named ID + missing/other source -> 422 named_profile_requires_explicit_ui_selection
unknown ID -> 422 photographer_profile_not_found
inactive/expired/suspended ID -> 409 photographer_profile_unavailable
region-restricted ID -> 403 photographer_profile_region_restricted
LLM/profile text proposal -> never changes the pinned binding
retry/profile mutation -> 409 photographer_profile_binding_immutable
new project job with historical binding only -> General unless explicitly reconfirmed
```

No invalid named selection may silently fall back to General.

## 5. API And Persistence Impact

The two request fields affect both the canonical
`/api/v3/creative-agent/jobs` path and compatible `/v3/creative-jobs` alias.
The resolved binding must be stored with the job and with any project
continuation snapshot used to generate or retry that job. History may display
the public profile name and version but must not expose internal provenance or
rights-review records.

Existing jobs and requests migrate with both new request fields absent and bind
General Photography. No backfill may infer a named profile from prompt text,
history, metadata or prior output appearance.

## 6. General And E-Commerce Isolation

The fields are inert unless the resolved Scenario Pack is Photography. General,
E-Commerce and every other Scenario Pack retain current request and output
behavior. The shared frontend must not show the selector outside Photography,
and the default Scenario Pack must not load the Photography catalog.

## 7. Required Mainline Tests

1. Request parsing accepts null defaults and rejects untrusted named sources.
2. Catalog route returns only public, available profile data.
3. UI submits `user_explicit_ui` only after a deliberate profile confirmation.
4. Prompt text and LLM output cannot set or mutate a binding.
5. Unknown and unavailable profiles block without General fallback.
6. Job generation, retry and selection preserve the exact pinned checksum.
7. A new project action defaults to General until the user reconfirms.
8. General and E-Commerce API/UI snapshots remain unchanged.
9. Persistence restore reproduces the exact resolved binding.

## 8. Acceptance Evidence Expected

```text
mainline commit hash
public contract tests
frontend interaction test or recorded acceptance
persistence round-trip test
General/E-Commerce isolation tests
documented migration/default behavior
```

## 9. Photography Work Paused

P5 named-profile catalog activation, profile technique compilation,
profile-aware review and any production Photography registration remain paused.
After the change lands, the Photography branch must fetch and rebase onto
`origin/main`, run mainline tests first, and only then resume P5.
