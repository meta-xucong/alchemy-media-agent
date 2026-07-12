# P10 P6 Real Provider Acceptance Matrix

## Purpose

This is the Photography-owned, human-reviewed quality matrix for the P6 gate.
It prepares real front-end evaluation without creating a Photography Provider,
pixel reviewer, retry loop or final-result selector.

The executable module contract is
`PhotographyProviderAcceptanceDirector`.  It creates two frozen matrices:

```text
P6 single-hero provider baseline
  Available only after the gated mainline-003 Photography path is enabled.
  Four scenes x text-to-photo/reference-reshoot = 8 cases.

P6 professional-set provider release
  Four scenes x text-to-photo/reference-reshoot = 8 cases.
  Requires PHOTOGRAPHY-MAINLINE-004; do not present a single-hero fallback as
  a professional set.
```

## Front-End Execution Sequence

For every case, use the Photography workspace only after its deployment gate
is deliberately enabled in the approved environment:

1. Create a new Photography job/project; no historical named profile carries
   over automatically.
2. Leave named profile at General Photography unless a separately approved
   profile is manually selected and confirmed in the UI.
3. For reference cases, upload evidence with the matrix role and preservation
   policy. The animal reference must use `nonhuman_identity_reference`.
4. Generate via the existing shared V3 path. Do not call a provider directly.
5. Save every attempt and the selected final result. Review raw renderer,
   foundation-only and foundation-plus-Photography outputs blind where
   possible.
6. For professional-set cases, require one final winner per frozen role and
   leave retry-superseded attempts in history.

## Required Review

All cases assess brief fidelity, composition, physical lighting, perspective,
depth/focus, color/texture, natural moment, retouch restraint, artifacts,
reference truth and professional direct-use readiness. Scene checks add:

```text
portrait: identity, face/body realism, expression, pose, skin finish
landscape: depth, atmosphere, foliage/water/sky/material realism
still life: material, edge, reflection, surface and set-light control
animal: individual identity, anatomy, behavior, motion and surface detail
```

The selected photographer technique score is additive. It cannot excuse a
reference-truth, anatomy, artifact, safety or explicit-prompt failure.

## Hard Stops

```text
animal high-fidelity conditioning absent or unsupported -> block; no text fallback
named profile not explicitly reconfirmed                -> block; no General fallback
professional_set before mainline-004                   -> unavailable/blocked; no single-hero substitution
review/retry/final delivery outside shared V3 path      -> reject the run
```

No generated images, contact sheets, secret credentials or Provider response
bodies belong in the repository. Human-reviewed evidence should be attached to
the approved acceptance record outside Git.
