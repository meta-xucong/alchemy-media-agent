# Professional Mode View-Conditioned Evidence and Renderer Parity

Status: implementation specification for the independent Professional M5
acceptance branch. This document does not open a browser entry, a production
gate, or a second Provider/review/retry/storage path.

## 1. Why the previous M5 attempts remained blocked

The shared Vision review was correctly rejecting the three-quarter candidates;
lowering its thresholds would hide, rather than fix, identity drift. The
blocking causes were structural:

1. The supplementary stages reused a mostly frontal head-geometry crop. That
   crop preserved facial proportions but did not reliably carry the view
   evidence needed for ear visibility, nasal plane, jaw silhouette, neck and
   head direction. The renderer therefore had to invent unseen geometry.
2. The native image-generation handoff did not prove that the returned pixels
   matched the frozen rendering contract. A returned image with a different
   size, model, format, or unknown quality is non-counting M5 evidence.
3. A standalone MCP process had no server-owned People Asset resolver. A
   synthetic test resolver is useful for contract tests, but it is not an
   activated project asset and cannot certify an M5 run.

## 2. View-conditioned evidence compiler

The existing serial budget remains hard and unchanged:

| Stage | Provider reference inputs |
| --- | ---: |
| front | 2: root feature detail + root head geometry |
| three-quarter | 3: root view geometry + front winner feature detail + front winner view geometry |
| profile | 5: root view geometry + front winner feature detail/view geometry + three-quarter winner feature detail/view geometry |

The new `portrait_identity_pose_geometry_crop` is a provider-only derivative.
It replaces the old root geometry derivative in supplementary stages; it does
not add another image. It preserves the face contour together with enough
ear/neck/shoulder and head-direction evidence to condition the requested view,
while channel isolation still suppresses prompt-owned hair, wardrobe, light,
scene, and whole-image style. Generated winners receive a feature-detail and
pose-geometry pair. Standard Mode and ordinary identity jobs continue using
the existing feature-detail/head-geometry pair.

The compiler emits an auditable `view_conditioned_evidence` record in the
provider input plan. A supplementary stage is not provider-ready unless each
root/winner lineage has the scopes it requires. Missing or substituted scopes
fail before a Provider request; no local face reconstruction or static pose
recipe is permitted.

## 3. Readiness and renderer parity

Before a supplementary request can be counted, all of the following must be
true:

- the server-owned Professional binding is active, frozen, and matches the
  project/job/People Asset selectors;
- the serial root and reviewed-winner lineage is exact and has the compiled
  view-conditioned scopes;
- the Brain-signed canonical prompt and shared Human Realism signing receipt
  are present;
- the host returns a renderer parity receipt proving the actual model, size,
  quality, output format, and renderer match the frozen contract.

The native MCP remains conversation-only and never imports or certifies a
pixel. It therefore reports `awaiting_host_receipt` until the host supplies
the parity receipt. A mismatch or missing field is structured blocked evidence,
not a retry reason and not a Web Provider fallback.

## 4. Binding handoff

The MCP accepts only selectors. An embedding host may explicitly construct a
resolver from the existing metadata-only `PersistentVisualAssetCatalog`; the
catalog root is process configuration, never an MCP request field. If no
resolver is configured, Professional planning remains fail-closed. The
resolver only calls the existing `bind_professional_mode` contract and does
not own Brain, Provider, review, retry, or storage semantics.

## 5. Acceptance consequence

This change makes the root causes diagnosable and prevents invalid pixels from
reaching a counted stage. It does not by itself pass M5: a real active pack,
real GPT Image 2 output, shared Vision `pass` for each winner, exact parity,
and human comparison evidence are still required. Gate C/D, browser entry, and
production availability remain closed until those evidences exist.
