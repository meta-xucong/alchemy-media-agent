# Doc184 - V3 Character Card Face Identity Capture Scope Contract

## Authority

This document is the corrective authority for the geometric meaning of the
Character Card Face Identity module. It extends Doc178, Doc180, Doc182 and
Doc183. It does not replace their lifecycle, UI, bounded-failure, Provider/MCP
parity, shared Vision, lineage or activation rules.

Doc186 is the current prompt-minimization authority for later Character Card
slots. This document's face/head capture scope still governs geometric review;
Doc186 governs how later view slots should be rendered as Brain-signed
reference-led deltas rather than repeated full person-definition prompts. It
also governs the post-signing slot-scope gate: a signed Face Identity renderer
prompt may not leave face/head or upper-shoulder identity capture and become a
full-body, outdoor, wardrobe, lifestyle, height-estimation or Body Silhouette
scene.

Doc186 also supersedes any older ambiguity about Face Identity framing or
front-pose inheritance: every Face Identity slot uses a fixed
head-and-upper-shoulders reference crop, and `face.front` must normalize a
slightly angled source portrait into a true straight-on standard front card.
The source viewpoint is identity evidence only; it is not an owned reusable
card pose.

The shared execution path remains the same. The capture contract is different:

```text
ordinary Anchor Pack       -> anchor_pack (historical whole-person contract)
Character Card Face Identity -> character_card_face_identity (face/head evidence)
Body Silhouette             -> its own body_silhouette stage contract
```

## Problem corrected

Character Card originally reused the old Anchor Pack service through
`face_view_scope="character_card"`, but that scope did not change the old
whole-person geometry. Face candidates could therefore be reviewed as if they
were body/pose evidence. This created false failures for composition, pose and
body-proportion conditions before Expression Set or Body Silhouette had run.

## Binding

When the Character Card Face Identity route is selected, the server derives and
freezes `capture_scope=character_card_face_identity`. The value is transported
through the existing typed path:

```text
face_view_scope
 -> AnchorGenerationRequest.capture_scope
 -> professional planning metadata
 -> canonical_prompt_context.professional_anchor_view_decision
 -> Remote Brain typed receipt
 -> shared Vision review dimensions
```

The browser cannot submit prompt prose or choose this scope. The Remote Brain
still authors the complete canonical prompt. The scope means a clean
photographic head-and-upper-shoulders identity frame for the frozen angle:
head top margin, full face, neck and upper shoulders visible. It does not
authorize a local prompt suffix, a face-feature recipe, a big-head crop,
half-body/waist-up frame, or inherited source pose angle for the standard
front slot.

## Review boundary

Character Card Face Identity requires shared review, prompt/reference parity,
face localization and the existing identity/materiality/quality dimensions.
`pose_compliance` is not required for this face-only capture because body
geometry belongs to Body Silhouette. Ordinary Anchor Pack review continues to
require the historical pose dimension.

Because Face Identity images are reusable bases for the whole Character Card,
their commercial cleanliness bar is stricter than ordinary pass/warning
status. The shared review score card must meet the Doc186 face-card commercial
clarity floor for visual quality, technical finish and human realism; otherwise
the candidate remains rejected even when the ordinary shared review result is
verified.

## Superseded wording

- Doc178 section 4.1 remains authoritative for the five slots, candidate
  budget, serial evidence and completion gate, but its reference to the
  existing workflow must now be read with this face-only capture scope.
- Doc180 section 5 remains authoritative for the shared route and UI sequence;
  “reuses the existing Anchor Pack path” means shared infrastructure, not the
  old whole-person geometry contract.
- Doc182 resume behavior remains unchanged. A failed Character Card face pack
  resumes only its completed face views and never changes the scope to body or
  pose semantics.
- Doc183 Provider/MCP equivalence remains unchanged. Both channels carry the
  same capture scope and pass through the same Brain, Provider, Vision, retry,
  winner and storage contracts.
- Any older wording that treats "head/upper shoulder" as allowing big-head,
  chest-up, waist-up or half-body framing is superseded by the fixed
  head-and-upper-shoulders card crop in Doc186.

## Non-regression rules

- Standard Mode, General, E-Commerce and Photography do not receive this
  Character Card scope.
- Body Silhouette remains ordered after Face Identity and Expression Set and
  keeps its observed/user-described/Brain-inferred source contract.
- No second Provider, Brain, Vision reviewer, retry budget or storage path is
  introduced.
- No unreviewed pixel may fill a Face Identity slot or activate an asset.
