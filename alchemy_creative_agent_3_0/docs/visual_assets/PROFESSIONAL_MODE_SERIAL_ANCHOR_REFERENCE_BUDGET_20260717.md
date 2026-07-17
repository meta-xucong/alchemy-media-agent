# Professional Mode Serial Anchor Reference Budget

Date: 2026-07-17  
Status: implementation proposal on the Professional M5 feature branch; view-conditioned derivative details are superseded by the 2026-07-18 companion specification
Strategy id: `serial_anchor_pack_root_reuse_v1`

## Purpose

The user-facing Face Identity workflow remains unchanged:

```text
root portrait → 3 front candidates → front winner
root + front winner → 3 three-quarter candidates → three-quarter winner
root + front winner + three-quarter winner → 3 profile candidates → profile winner
```

Every stage still generates three candidates and selects one likeness-first
winner. The change is only the internal reference packing sent to the image
renderer. It does not create additional views or additional AI-generated
identity images.

## Root reuse rule

The original upload is immutable identity truth, but it is not repeatedly sent
as an unfiltered full-frame style reference. The front stage prepares the
provider-only root identity evidence once. Later serial stages reuse one
geometry-preserving root anchor from that preparation; they do not recrop or
regenerate the original source.

The root anchor is identity-only. It must not grant ownership of the source
hair, wardrobe, lighting, background, camera, color grade, or whole-image style.
Those channels remain owned by the current Brain-authored prompt unless the
reference policy explicitly assigns them.

## Reference budget by stage

| Stage | Provider reference set | Count |
| --- | --- | ---: |
| `standard_front` | root feature-detail + root head-geometry | 2 |
| `three_quarter` | reused root view-geometry anchor + front winner feature-detail + front winner view-geometry | 3 |
| `profile` | reused root view-geometry anchor + front winner feature-detail/view-geometry + three-quarter winner feature-detail/view-geometry | 5 |

The profile stage therefore fits the current five-reference transport limit
without dropping a selected view and without splitting one stage into extra
generation rounds. Each of the three profile candidates receives the same
five-reference bundle and the same frozen canonical prompt.

## Implementation boundary

The shared provider materializer owns the bounded derivative policy. The
Professional relay marks the stage and strategy in server-owned metadata; the
MCP caller cannot choose derivative paths, provider settings, or a replacement
reference policy. Standard Mode and ordinary Professional jobs without this
strategy retain the existing complementary two-derivative behavior.

For Professional supplementary serial stages, the materializer emits one
`portrait_identity_pose_geometry_crop` derivative for the uploaded root and a
feature-detail/view-geometry pair for each reviewed generated winner. This
replaces a derivative kind; it does not add an input. The source image is never
modified. The selected/dropped derivative IDs and source hashes remain part of
the shared reference provenance. Standard Mode and ordinary Professional jobs
continue using the existing feature-detail/head-geometry pair.

## Quality and future expansion

The immutable root anchor prevents identity drift from accumulating across
generated winners, while the current and previous winners provide the angle
specific evidence needed for the next view. This is a transport-budget change,
not a likeness-score change: the existing shared review, retry, and
likeness-first winner selection remain authoritative.

Future expression, body, or pose evidence must use the same bounded budget
manager. Task-specific evidence may replace an optional derivative only when
the shared review contract records the substitution; no module may silently
increase the provider reference count or create a private generation path.
