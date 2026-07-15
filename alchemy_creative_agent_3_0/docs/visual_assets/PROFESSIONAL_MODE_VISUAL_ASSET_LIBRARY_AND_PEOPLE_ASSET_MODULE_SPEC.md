# Professional Mode Visual Asset Library And People Asset Module

## Independent Development Specification

> This is an unnumbered Professional Mode specification. It is intentionally
> outside the existing Doc numbering families. It defines a new visual-asset
> product boundary and must not be used to rewrite Standard Mode, General
> Template, E-Commerce, Photography, Central Brain, or the Web Provider path.

## 0. Status And Authority

Status:

```text
PROPOSED_ARCHITECTURE
DOCUMENT_ONLY
NO_STANDARD_MODE_CHANGE
NO_PRODUCTION_ASSET_GATE
```

This document is the preparation authority for:

```text
Professional Mode
  -> Visual Asset Library
      -> People Assets        [first module]
      -> Product Assets        [future sibling]
      -> Brand Assets          [future sibling]
      -> Other approved asset types [future siblings]
```

It does not activate Professional Mode, certify an identity provider, or make
any existing mode use a visual asset pack automatically.

## 1. Product Decision

Alchemy V3 will have two independent creation modes:

```text
Standard Mode
  -> current General / E-Commerce / Photography behavior
  -> current uploaded-reference and prompt ownership behavior
  -> current provider, review, retry, and delivery contracts

Professional Mode
  -> explicit use of a selected asset from the Visual Asset Library
  -> professional asset truth is authoritative for its assigned channels
  -> a selected People Asset is the only human-identity source
  -> current shared V3 planning, GPT Image 2, review, retry, and delivery
```

Professional Mode is an opt-in execution contract, not a replacement for
Standard Mode. A request must carry an explicit mode choice before any
Professional Mode asset is consulted.

The two modes may share implementation components, but they must not share
implicit state or silently change one another's semantics.

## 2. Standard Mode Is Frozen By This Document

When a request is in Standard Mode:

```text
no Visual Asset Library lookup is performed
no People Asset is required
no professional asset metadata is injected into the Brain request
no Professional Mode prompt or reference rule is appended
no professional-mode failure can block or reroute the request
```

The following remain unchanged in Standard Mode:

```text
General Template semantics
E-Commerce LLM-first and deliverable semantics
Photography LLM-first and role semantics
uploaded reference interpretation
Doc93 reference-channel ownership
shared provider routing
shared review/retry/final-delivery behavior
requested output count and public request schema
```

The Standard Mode branch must remain runnable if the entire Professional Mode
package is absent, disabled, unavailable, or removed.

## 3. Visual Asset Library Mother Boundary

The library is a project/account-scoped asset system, not a new image
generation template. Its initial conceptual layout is:

```text
visual_asset_library
  people_assets
    people_asset_record
    identity_anchor_pack
    identity_anchor_pack_version
    anchor_view
  product_assets             [future; not implemented here]
  brand_assets               [future; not implemented here]
  other_asset_types          [future; not implemented here]
```

The future runtime root may live under a dedicated visual-assets package, for
example:

```text
app/visual_assets/
  people_assets/
  product_assets/
  brand_assets/
```

No such future sibling is authorized by this document. The first implementation
must remain limited to People Assets and must not add product, brand,
marketplace, A+, or campaign-specific asset roles.

## 4. People Assets Scope

A People Asset represents a user-approved, reusable identity subject. It is
not merely a file and it is not a generated image candidate. It contains:

```text
the immutable root reference provenance
one or more verified identity anchor-pack versions
verified view/framing coverage
identity and review status
active/superseded state
source and consent provenance
```

The first People Asset implementation creates an Identity Anchor Pack through
an explicit preparation action:

```text
uploaded person reference, for image-to-image
or protected user prompt, for text-to-image character creation
  -> three neutral standard-front candidates
  -> existing identity/quality review
  -> best passing front anchor
  -> supplementary three-quarter/profile candidates as evidence permits
  -> per-view review
  -> whole-pack cross-view identity review
  -> activate one version only after the complete pack passes
```

The exact candidate counts for supplementary views remain a later module
design decision, but every supplementary view must use the same bounded
candidate, review, and best-result contract. There is no unbounded generation
loop.

The standard-front and supplementary images are full GPT Image 2 outputs. The
module must not create a face card through local face swapping, coordinate
warping, canvas overlays, deterministic facial reconstruction, or a private
pixel-repair path.

## 5. Root Truth And Anchor Authority

People Assets have a strict authority hierarchy:

```text
uploaded root portrait truth
  > verified generated anchor support
  > selected/generated continuation support
```

For a text-only character project with no uploaded portrait, the first approved
anchor version becomes the project's initial fictional-character root, but it
must be recorded as generated origin rather than misrepresented as uploaded
human truth.

An Identity Anchor Pack may improve view coverage and reduce reference-style
leakage. It may not silently replace an uploaded root portrait. Every later
Professional Mode generation must preserve the root truth relationship in its
provenance and final review.

## 6. Professional Mode Reference Contract

Professional Mode requires the caller to select an active People Asset or to
stop with a public-safe blocked state. It must never fall back to Standard Mode
because a People Asset is missing, stale, invalid, or below its review gate.

When Professional Mode is active:

```text
person identity, face geometry, age direction, and same-person continuity
  come only from the selected People Asset and its approved anchor pack

current prompt
  owns requested hair, makeup, clothing, pose, light, scene, camera, mood,
  composition, and style unless the user explicitly assigns those channels
  to another approved asset

other uploaded images
  may contribute only the explicitly assigned non-identity channels
```

An uploaded image that contains another person must not be sent as a complete
style or scene reference while claiming that its person is ignored. Full image
pixels can still carry face, body, clothing, and pose identity. The input
boundary must therefore do one of the following:

```text
use a verified non-person visual derivative;
use a safe channel-specific evidence representation;
or block that reference assignment when isolation cannot be proven.
```

Natural-language instructions alone are not sufficient to guarantee that an
unwanted person's pixels will be ignored.

## 7. User Experience Contract

The top-level UI exposes:

```text
Visual Assets
  -> People Assets
```

General, E-Commerce, Photography, and future Video surfaces expose only a
small mode choice:

```text
Standard Mode
Professional Mode: use Visual Assets
```

Standard Mode remains the default when no Professional Mode choice is made.
Professional Mode shows a People Asset selector. It must not expose internal
identity metrics, prompt sections, provider capability names, or biometric
terms in the beginner surface.

When the user explicitly selects Professional Mode but the selected People
Asset has no active valid pack, the UI may offer:

```text
Build this People Asset now
Choose another People Asset
Return to Standard Mode [explicit user action only]
```

Building a pack is a visible preparation stage. Its candidate images do not
count toward the requested formal delivery count. On failure, the system stops
and explains the next safe action; it must not silently continue in Standard
Mode.

The People Assets workspace additionally supports the professional workflow:

```text
create a People Asset
upload or declare its root source
build/rebuild an anchor-pack version
inspect coverage and review state
activate, supersede, or archive a version
set an asset as the current project character
```

## 8. Shared Capability Reuse

Professional Mode may call existing shared components, subject to their
current contracts:

| Existing capability | Professional Mode use |
| --- | --- |
| Doc93 reference-channel policy | Keep identity channels separate from prompt-owned style/scene channels. |
| Doc95 identity evidence | Build complementary feature-detail and head-geometry evidence; retain root truth. |
| Doc96 high-fidelity identity | Request high input fidelity where applicable; use ephemeral metrics, fused review, bounded repair, and best-result selection. |
| Doc97 subject continuity | Store generated anchors as reviewed support, retain uploaded root truth, route views adaptively, quarantine weak generated support. |
| Doc91/92 Human Realism | Improve human rendering without acquiring reference-channel ownership. |
| shared GPT Image 2 provider | Render anchor candidates and later Professional Mode images through the existing provider contract. |
| shared vision review/retry/history | Review every candidate, keep append-only attempts, and activate only the reviewed winner/pack. |

No People Asset implementation may create a second Brain, provider, review
system, retry system, asset store, or reference registry.

## 9. Ownership And Isolation

### 9.1 Visual Asset Library owns

```text
People Asset records
root-source provenance
anchor-pack versions
view coverage
pack activation and supersession
user consent and asset selection state
```

### 9.2 Existing creation modules own

```text
their current prompt and deliverable semantics
their current role/scene/package behavior
the explicit choice to run Standard or Professional Mode
the final user-facing creation result
```

### 9.3 Shared V3 foundation owns

```text
reference-channel ownership
identity/product/appearance evidence
provider transport
pixel review
bounded retry
final-result selection
```

The Professional Mode adapter may assemble these existing contracts, but it
must not redefine their meaning.

## 10. Conceptual Data Contracts

The eventual contracts should be additive and versioned. Names below are
conceptual and are not yet public API commitments.

```python
class PeopleAsset:
    people_asset_id: str
    project_id: str | None
    subject_kind: str                 # human_person | fictional_character
    root_sources: list[dict]
    active_pack_version_id: str | None
    status: str                       # draft | active | superseded | blocked
    provenance: dict

class IdentityAnchorPackVersion:
    pack_version_id: str
    people_asset_id: str
    status: str                       # preparing | review | active | failed | superseded
    anchor_views: list[dict]
    root_truth_ids: list[str]
    review_summary: dict
    source_provenance: dict

class AnchorView:
    view_id: str
    view_role: str                    # standard_front | three_quarter | profile | ...
    output_id: str
    source_candidate_ids: list[str]
    identity_scores: dict
    view_coverage: dict
    active: bool
```

These records may refer to existing Project/Job/Output/History identifiers;
they must not duplicate image storage or final-delivery records.

Forbidden in these contracts:

```text
persisted face embeddings or raw biometric vectors
provider credentials
private prompt bodies in user-facing asset cards
unreviewed candidate as active identity truth
unbounded retry state
mode-specific marketplace, A+, or photography role fields
```

## 11. Runtime Integration Boundary

The intended execution seam is:

```text
Professional Mode selection
  -> resolve selected People Asset
  -> inject approved anchor references into existing V3 capability input
  -> run existing planning / provider / review / retry / delivery path
  -> preserve Professional Mode provenance and selected asset version
```

The Standard Mode seam remains unchanged:

```text
Standard Mode selection or absence of mode selection
  -> existing V3 capability input
  -> no Professional Mode records or references
```

Mode identity must be carried as an internal execution boundary, not as
E-Commerce slot fields, Photography role fields, General Template recipe
fields, or new Brain prompt prose. The public request schema remains stable.

The Professional Mode bridge must fail closed for:

```text
missing selected People Asset
inactive or superseded pack version
pack review not complete
root provenance missing where required
reference-channel isolation failure
provider/review failure during pack creation
```

There is no automatic Professional-to-Standard fallback. A user may
explicitly switch modes and resubmit.

## 12. Future Video Compatibility

The first implementation does not build a video generator, temporal tracker,
character rig, or storyboard package.

It only makes the People Asset contract reusable by a future Video module:

```text
Video selects People Asset + active pack version
Video chooses an approved anchor view for a shot
Video retains root truth provenance
Video adds its own temporal consistency and motion review later
```

A still-image anchor pack is necessary identity input for future video but is
not by itself evidence of temporal or frame-to-frame consistency.

## 13. Implementation Phases

### Phase A — Documentation And Mode Boundary

```text
freeze Standard/Professional mode separation
define Visual Asset Library and People Asset ownership
define no-fallback and no-raw-person-reference rules
add isolation contract tests before runtime work
```

### Phase B — People Asset Records And Pack Lifecycle

```text
add additive project-scoped People Asset records
add pack-version state and provenance
reuse existing output/history storage
add active/superseded/failed handling
```

### Phase C — Anchor Pack Preparation

```text
explicit root-source intake
three standard-front candidates
existing identity/quality scoring and winner selection
supplementary view generation using root + selected front anchor
per-view and whole-pack review
activate only a complete passing pack
```

### Phase D — Professional Mode Consumers

```text
add Professional Mode selection to General, E-Commerce, and Photography
consume only the selected People Asset in Professional Mode
keep Standard Mode byte/contract compatible
prove no raw person reference leaks into Professional Mode provider inputs
```

### Phase E — Real Acceptance And Video Handoff Contract

```text
cross-scene image acceptance
cross-view pack acceptance
project continuation acceptance
document the stable asset interface for future Video
```

No phase authorizes a production claim before the existing real provider,
review, and template gates pass.

## 14. Required Isolation Tests

At minimum:

```text
Standard Mode with no People Asset behaves exactly as before.
Standard Mode cannot read Professional Mode asset metadata.
Professional Mode requires an active selected People Asset.
Professional Mode never silently falls back to Standard Mode.
Professional Mode uses only the selected asset for human identity.
An uploaded second person cannot enter as a full style reference.
Style/scene references retain their allowed non-identity channels.
Pack candidates remain append-only and only active winners enter routing.
Root truth remains in every strict Professional Mode identity review.
E-Commerce and Photography role semantics remain unchanged in both modes.
General remains scenario-neutral in both modes.
No public request or Brain schema gains asset-library internals.
```

## 15. Acceptance Criteria

The Professional Mode foundation is not ready to integrate until:

```text
1. Standard Mode regression passes with Professional Mode disabled and enabled
   in the same deployment.
2. A People Asset can build a three-candidate standard-front stage.
3. Only a passing front candidate can seed supplementary views.
4. Supplementary views are evaluated against both root truth and the selected
   front anchor.
5. The complete pack is rejected if any required view or cross-view identity
   gate fails.
6. Active packs are versioned, provenance-bound, and reversible.
7. Weak, failed, or superseded candidates cannot enter provider inputs.
8. Professional Mode prevents unwanted human identity pixels from other
   uploaded references.
9. Standard, E-Commerce, Photography, and future Video consumers can select
   the same asset contract without duplicating identity logic.
10. No production or Provider Gate claim is made solely from pack creation.
```

## 16. Non-Goals

This specification does not authorize:

```text
changing existing Standard Mode behavior
changing General Template semantics
changing E-Commerce or Photography deliverable contracts
building an A+ module or marketplace asset package
building a Video module
adding a second image provider or sidecar
local face swap, face compositing, font/OCR, or pixel overlay
storing biometric embeddings
automatic professional-mode activation
silent fallback from Professional Mode to Standard Mode
```

## 17. Architectural Summary

```text
Standard Mode remains the current product.

Professional Mode is a separate opt-in contract.

Visual Asset Library is the Professional Mode mother boundary.

People Assets are the first child module.

Identity Anchor Packs are versioned, reviewed identity support assets.

Existing V3 foundation modules remain the implementation machinery.

The mode boundary controls whether those assets are consulted; it does not
rewrite the existing foundation contracts.
```
