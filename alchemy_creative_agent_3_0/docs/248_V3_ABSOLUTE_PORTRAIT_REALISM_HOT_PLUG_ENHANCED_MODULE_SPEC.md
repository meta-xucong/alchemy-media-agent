# Doc248 — V3 Absolute Portrait Realism Hot-Plug Enhanced Module

## Purpose

This document defines a hot-pluggable Enhanced module for professional human
portraits whose goal is **real photographed human presence without reducing
commercial beauty**.

The module addresses the failure pattern observed in front-facing portrait
conversions: once a generated subject is normalized into a clean front model
card, small AI-rendering artifacts become easier to notice. Typical signals are
misaligned gaze, overly perfect facial symmetry, pasted-looking hair edges,
poreless plastic skin, simplified ear anatomy, and flat studio light response.

The module is not a detector-evasion feature. It must not claim that an image is
"undetectable" or optimize against a named classifier. It improves visible
photographic evidence that a human reviewer can inspect.

## Layering

### Core

Formal slot completion remains unchanged:

```text
three real reviewed candidates -> shared review -> explicit ranking -> winner -> per-slot FormalSlotReceipt
```

Doc248 must not change `FormalSlotAcceptanceCore`, candidate count rules,
winner authority, activation validation, public projection, MCP recovery, or
existing Face / Expression / Body receipt semantics.

### Enhanced

Absolute Portrait Realism is an optional Enhanced profile. It may supply
candidate-level `FormalSlotCandidateEnhancedProofSummary` evidence to a slot
that explicitly requires it.

It evaluates only public-safe, structured, visible-image evidence:

- eye gaze and eyelid consistency;
- natural facial micro-asymmetry without identity redesign;
- photographed skin micro-texture and non-plastic highlight response;
- hair strand randomness, flyaways, and believable hairline/ear-side blending;
- ear anatomy clarity when visible;
- natural light/shadow transitions and camera texture;
- accessory / hand / clothing local integrity when present;
- beauty preservation: realism cannot make the subject uglier, duller, muddy,
  older, tired, or less commercially polished.

### Auxiliary

Provider choice, MCP handoff, retry, old evidence migration, and comparison
against prior outputs remain adapters. They may feed structured evidence into
Doc248, but they cannot override slot acceptance or fabricate proof.

## Hot-plug contract

The module is activated only by an explicit profile id such as:

```text
absolute_portrait_realism_v1
```

No V3 path receives this gate by default. A professional template can opt in for
front-card portraits, headshots, or model-card closeups where high realism is a
hard deliverable.

The module returns:

1. a public-safe realism proof summary;
2. an optional formal enhanced proof for the candidate;
3. safe issue codes when it fails.

The proof must be explicit. Missing evidence is not treated as pass.

## Beauty-preserving realism rule

The module must reject "fake realism" repairs that rely on:

- low resolution, compression artifacts, random noise, grain, or blur;
- dirty skin, harsh unflattering shadows, muddy color, or tired expression;
- facial geometry changes that make the person less attractive;
- accidental hair, wardrobe, lighting, or scene inheritance from a reference
  when Doc93 says those channels are prompt-owned.

Commercial beauty remains a requirement. Realism comes from photographed detail,
not degradation.

## Initial target seams

Phase 1: pure contract module and tests.

- Add a module-neutral proof model and evaluator.
- Prove fail-closed behavior for missing evidence, weak dimensions, unsafe
  fields, and beauty degradation.
- Prove it can produce `FormalSlotCandidateEnhancedProofSummary` without
  importing or changing Formal Core.

Phase 2: professional portrait candidate adapter.

- Let eligible portrait slots opt in.
- Feed Doc248 proof as candidate-level Enhanced evidence.
- Keep Face / Expression / Body winner logic unchanged.

Phase 3: controlled visual validation.

- Use the original reference image to generate exactly three front-facing
  candidates.
- Score candidates for realism and beauty.
- Select the strongest via the existing three-candidate winner path.
- Compare against the previous front-facing output. The new result must improve
  visible realism and must not reduce beauty or commercial model-card quality.

## Acceptance

Development acceptance:

- Pure tests pass.
- Formal Core tests pass unchanged.
- Source inspection proves the module imports no Provider/MCP/route/slot
  lifecycle code and contains no detector-evasion objective.

Visual acceptance:

- Three candidates are generated only after code acceptance.
- The winner shows materially improved eyes, hair, skin, ear/edge structure,
  light response, and natural asymmetry.
- Beauty/commercial polish is equal or better than the previous output.
- The report names visible improvements and any remaining limitations.
