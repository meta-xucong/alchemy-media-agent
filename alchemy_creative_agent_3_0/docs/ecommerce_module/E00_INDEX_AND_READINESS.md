# E-Commerce Module Documentation Set

Status: LLM-native pre-acceptance closure; real Provider Gate C/D is blocked
pending authorized reference material and an enabled controlled visual-review
deployment
Document family: `E00-E11`, corrected by V3 Doc111 and extended by E17-E19
Branch: `codex/ecommerce-module-docs`

## Purpose

This directory is the isolated documentation authority for the V3 E-Commerce
specialized module. It defines the product boundary, platform and category
strategy, runtime contracts, UI, quality gates, roadmap, and test matrix.

It does not replace V3 foundation documents. It specializes them for
commerce-specific deliverables.

## Authority order

1. `AGENTS.md` repository safety and layer-boundary rules.
2. V3 foundation and capability authorities, especially Docs76, 91, 93, 94,
   100-103, 111, 113, and 117.
3. V3 template/project authorities, especially Docs41-43 and Doc105
   continuation. Docs57, 59, and 60 are historical compatibility material only.
4. V3 Doc111 provider-native creative-direction correction.
5. V3 Doc113 execution truth and Doc117 Provider/no-pixel closure.
6. E17 LLM-native E-Commerce architecture correction.
7. E18 LLM-native pre-acceptance closure and evidence record.
8. E19 real Provider Gate C/D acceptance record.
9. This E-Commerce module family.
10. Implementation notes and examples.

If a commerce rule conflicts with a foundation safety rule, the foundation
rule wins. If a platform rule conflicts with product truth, product truth wins.

## Existing implementation audit

The baseline already contains:

- `app/scenario_packs/ecommerce/` with product truth, seller-fact brief,
  versioned marketplace evidence, historical-read compatibility shims, critic,
  and export metadata.
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
| E-Commerce Scenario Pack | pre-acceptance closure | factual context to Central Brain; no static suite fallback |
| Platform profiles | evidence only | retain versioned constraints; do not generate default slots or image recipes |
| Category packs | evidence only | retain buyer questions; do not generate shot orders or category recipes |
| UI workspace | partial/iterative | needs commerce-specific beginner flow |
| Real-output acceptance | ongoing | required before production activation of new profiles |
| In-image copy | provider-native migration | no new local font, HTML/SVG/canvas, or deterministic text-pixel path |

Current upstream coordination authority: V3 Doc103. It permits this isolated
module work, while reserving frozen capability-plan runtime closure, live
provider acceptance, General browser continuation, and production template
activation for the shared foundation integration gates.

The historical E12-E16 handoffs on the documentation branch must not merge
unchanged: their deterministic compositor, font, safe-area, and multi-plan
contracts are superseded for new work by Doc111. E17 additionally supersedes
active deterministic platform/category slot direction. Product facts, platform
evidence, output lineage, and final-pixel review remain valid inputs.

The same reading rule applies to root Docs57, 59, and 60: no static platform
suite, default marketing copy, category shot order, prompt recipe, or local
text/overlay mechanism may be restored. E-Commerce enters only after explicit
template selection. The template freezes requested count and factual acceptance
constraints; the remote Brain supplies one natural-language image direction per
requested output; GPT Image 2 supplies the complete pixels; the shared runtime
owns review, bounded retry, and append-only delivery.

E18 is the current execution checklist for the pre-acceptance stage. It
requires strict remote-Brain failure closure, exact output-count behavior,
General/Photography isolation, queryable provenance, project-recovery wording,
and an evidence record. It does not waive the real Provider Gate C/D.

E19 records the real gate without turning its preparatory material into a
claim of readiness. As of 2026-07-14 it records a controlled preflight block:
the current process has no authorized watermark-free product reference and its
shared visual inspection feature is not enabled. No desktop demonstration image
may be treated as an acceptance fixture without an explicit rights record.

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
9. E17 LLM-native architecture correction.
10. E18 pre-acceptance closure evidence record.
11. E19 real Provider Gate C/D evidence record, with a passing real run only
    when the documented external prerequisites exist.
