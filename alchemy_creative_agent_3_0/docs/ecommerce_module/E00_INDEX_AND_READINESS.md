# E-Commerce Module Documentation Set

Status: development preparation baseline with provider-native text correction
Document family: `E00-E11`, corrected by V3 Doc111
Branch: `codex/ecommerce-module-docs`

## Purpose

This directory is the isolated documentation authority for the V3 E-Commerce
specialized module. It defines the product boundary, platform and category
strategy, runtime contracts, UI, quality gates, roadmap, and test matrix.

It does not replace V3 foundation documents. It specializes them for
commerce-specific deliverables.

## Authority order

1. `AGENTS.md` repository safety and layer-boundary rules.
2. V3 foundation and capability authorities, especially Docs 76, 77, 91-103.
3. V3 template/project authorities, especially Docs 41-43, 57, and 60.
4. V3 Doc111 provider-native text and creative-direction correction.
5. This E-Commerce module family.
6. Implementation notes and examples.

If a commerce rule conflicts with a foundation safety rule, the foundation
rule wins. If a platform rule conflicts with product truth, product truth wins.

## Existing implementation audit

The baseline already contains:

- `app/scenario_packs/ecommerce/` with product truth, commerce brief,
  marketplace rules, selling-point planning, copy bridge, critic, and export.
- E-Commerce template registration and Project Mode routing.
- Product-level contracts and focused E-Commerce tests.
- Shared V3 capability, review, retry, provider, and project layers.

The module work therefore extends existing contracts and UI. It must not create
a second provider runtime, a second project store, or a V1/V2 bridge.

## Readiness classification

| Area | State | Meaning |
| --- | --- | --- |
| V3 foundation | baseline accepted for specialized work | consume, do not fork |
| General Template | active and broad | may support light product visuals only |
| E-Commerce Scenario Pack | existing skeleton | needs professional suite expansion |
| Platform profiles | partial | require versioned policy/config records |
| Category packs | partial | need first five category definitions |
| UI workspace | partial/iterative | needs commerce-specific beginner flow |
| Real-output acceptance | ongoing | required before production activation of new profiles |
| In-image copy | provider-native migration | no new local font, HTML/SVG/canvas, or deterministic text-pixel path |

Current upstream coordination authority: V3 Doc103. It permits this isolated
module work, while reserving frozen capability-plan runtime closure, live
provider acceptance, General browser continuation, and production template
activation for the shared foundation integration gates.

The historical E12-E16 handoffs on the documentation branch must not merge
unchanged: their deterministic compositor, font, safe-area, and multi-plan
contracts are superseded for new work by Doc111. Product facts, platform
evidence, output lineage, and final-pixel review remain valid inputs.

## Definition of preparation complete

Before implementation starts, the team must have accepted:

1. E01 scope and boundary.
2. E02 platform/localization model.
3. E03 category suite model.
4. E04 contracts and runtime integration map.
5. E05 UI flow.
6. E06 review/retry/export rules.
7. E07 milestones and commit boundaries.
8. E08 test and acceptance matrix.
