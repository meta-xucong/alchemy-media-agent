# Doc262 - V3 E-Commerce Product Reference Dedup And Continuation Contract

## 1. Scope

This correction belongs to V3 Project Mode E-Commerce reference authority. It
does not change provider prompts, ImageGen routing, visual-asset identity
binding, generated-output continuation, or review gates.

## 2. Correction Model

An uploaded product reference is product truth by image content, not by the
latest browser upload id. If the same image bytes are uploaded again, the new
asset id is duplicate transport evidence and must not become a second active
product fact.

The browser also must not keep consumed `File` objects or upload fingerprints
when a project is opened or after a job request has accepted those uploads.
Continuation without selecting new files must use the project's persisted
source truth, not silently re-upload stale local files.

## 3. Authoritative Behavior

1. Active E-Commerce product references are canonicalized by `content_sha256`.
2. The earliest active project reference for a digest remains the canonical
   product truth reference.
3. A duplicate uploaded product reference is soft-suppressed by leaving upload
   files intact and keeping history append-only; it is not an active project
   product fact.
4. Legacy `uploaded_asset_refs` are read-compatible, but E-Commerce product
   candidate collection must also dedupe them by content digest.
5. `ProjectContextPackage.uploaded_reference_assets` exposes `content_sha256`
   for uploaded references so public grouping can remain stable without
   exposing private paths beyond the existing context contract.
6. Desktop and mobile clear pending upload state on project open and after a
   job request consumes uploads.

## 4. Recovery Rule

For an existing polluted project, repair is non-destructive: mark duplicate
active project references inactive or exclude duplicate legacy entries from
active projections. Do not delete upload directories, generated outputs,
timeline entries, or previous failed jobs.

## 5. Acceptance Criteria

1. Two uploaded product assets with the same `content_sha256` yield one active
   E-Commerce product reference.
2. A continuation job freezes one canonical product-truth pool entry per image
   digest.
3. Reopening a project and clicking continue without selecting files sends no
   stale uploaded files.
4. The fix does not affect non-product references or generated-selected
   continuation references.
