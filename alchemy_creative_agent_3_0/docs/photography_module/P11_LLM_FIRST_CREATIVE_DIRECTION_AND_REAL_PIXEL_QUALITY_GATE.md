# P11: LLM-First Creative Direction And Real-Pixel Quality Gate

## Status

```text
authority: active Photography development correction
scope: shared-mainline request plus Photography acceptance rules
does not authorize: a Photography-private LLM, Provider, reviewer, retry loop, or renderer
runtime implementation: landed at fc3f5c2 (LLM-first fail-closed delivery) and db70c44 (review-certification projection and delivery withholding)
production gate: blocked pending a usable remote Central Brain and real-pixel acceptance evidence
```

## Why This Correction Exists

The prior implementation correctly isolated profiles, reference truth, role
execution, shared Provider routing, and final delivery. It nevertheless leaves
two unacceptable release risks:

1. deterministic keyword/default planning can become the creative source when
   the central LLM is unavailable; and
2. `metadata_only` review can prove workflow state but cannot prove image
   quality, identity continuity, role differentiation, or commercial readiness.

Neither risk may be addressed by accumulating more prompt fragments or
vertical-specific rule tables.

## Required Ownership

| Concern | Owner |
| --- | --- |
| Natural-language photographic interpretation and one direction per role | Central remote LLM |
| Explicit profile, rights, reference truth, role cardinality, safety and capability prerequisites | Photography Scenario Pack / shared contracts |
| Final pixels | shared GPT Image 2 route |
| Pixel quality, bounded retry and winner selection | shared review/retry/final-delivery path |
| Photography-specific role coverage and human acceptance matrix | Photography template |

## Production Contract

1. A Photography job freezes only non-creative constraints before Brain
   execution. The Brain must return one complete direction for each frozen
   role; its output is validated but never replaced with stock role prose.
2. The template may reject an incomplete or conflicting Brain response. It
   must fail closed rather than synthesize a local replacement direction.
3. The role contract is structural: role ID, count, requested distinction,
   profile checksum and reference truth. It is not a library of predefined
   creative sentences.
4. Shared review must use real pixels (`vision_model` or `hybrid`) for P10 and
   production. `metadata_only` has one allowed meaning: non-certifying record.
5. A professional set is deliverable only when every role reaches a terminal
   state and one eligible final winner is available for every role. Partial
   sets remain append-only history with a visible diagnostic block.
6. General and E-Commerce may never inherit Photography role taxonomy,
   profile binding, controls, prompt fragments, quality thresholds, or retry
   semantics. Photography may never inherit their suite or marketplace roles.

## Non-Goals

- No second Brain, Provider, reviewer, or result selector.
- No local image editing, OCR overlay, compositing, or workaround renderer.
- No broad style lock from an ordinary reference image.
- No automatic use of a named photographer profile.
- No hidden retry-budget increase to compensate for weak prompts.

## Acceptance Gate

Before reopening P10 quality certification, prove:

1. remote LLM unavailable -> Photography blocks with no deterministic creative
   fallback;
2. malformed or wrong-cardinality Brain output -> block with no role padding;
3. each of the four first-wave scenes receives Brain-authored directions that
   differ materially across the three professional-set roles;
4. `metadata_only` -> non-certifying block; `vision_model`/`hybrid` -> shared
   pixel verdict flows into bounded retry and final selection;
5. General/E-Commerce both show zero Photography capability, role, prompt and
   profile leakage; and
6. reference reshoot waits for the shared `/images/edits` high-fidelity path;
   it never downgrades to text-only generation.

## Implementation And Remaining Sequence

1. PX-MAINLINE-005 is implemented: active Photography fails closed without a
   valid remote creative result, and `fc3f5c2` binds one Brain-authored
   direction to each frozen role.
2. `db70c44` makes `metadata_only` non-certifying at the Project and Product
   API result surfaces. `vision_model` and `hybrid` certification is visible
   without exposing Provider internals.
3. Mainline and Photography contract/isolation regressions have been run; the
   production deployment gate remains closed.
4. Run the P10 text-only quality matrix only when the real remote Brain and
   shared real-pixel reviewer are both available, and preserve its provenance.
5. After `/images/edits` and Gate D, run the reference-reshoot and nonhuman
    identity matrix.
6. Only then request the production deployment gate.
