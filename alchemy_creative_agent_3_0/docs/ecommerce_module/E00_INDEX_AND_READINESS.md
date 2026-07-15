# E-Commerce Module Documentation Set

Status: Doc127 Phase 4 acceptance preparation; one historical controlled Gate C
case is recorded, while current-release Gate C re-certification and Gate D
remain pending
Document family: `E00-E11`, corrected by V3 Doc111 and extended by E17-E20
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
   100-103, 111, 113, 117, and 127.
3. V3 template/project authorities, especially Docs41-43 and Doc105
   continuation. Docs57, 59, and 60 are historical compatibility material only.
4. V3 Doc111 provider-native creative-direction correction.
5. V3 Doc113 execution truth and Doc117 Provider/no-pixel closure.
6. E17 LLM-native E-Commerce architecture correction.
7. E18 LLM-native pre-acceptance closure and evidence record.
8. E19 real Provider Gate C/D acceptance record.
9. E20 Doc127 Phase 4 execution pack.
10. This E-Commerce module family.
11. Implementation notes and examples.

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
| Real-output acceptance | current-release pending | historical Gate C evidence exists; Doc127 requires a frozen-build rerun and Gate D before production activation |
| In-image copy | provider-native migration | no new local font, HTML/SVG/canvas, or deterministic text-pixel path |

Doc127 is the active campaign/runbook authority. It preserves E17-E19 as the
E-Commerce implementation and evidence authority, while reserving shared
runtime changes, frozen capability-plan closure, live Provider acceptance,
General browser continuation, and production template activation for the
mainline controlled-release campaign.

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

E19 records one bounded historical controlled Gate C case and its earlier
preflight. It does not certify the current release build, Gate D, multilingual
text, the exact-count matrix, or production readiness. Doc127 requires a new
current-build Gate C run, then the N=1/2/4/7 browser and human-review matrix.
E20 supplies the non-sensitive operator manifest and checklist for that work.
An old desktop example remains ineligible unless the material owner provides
an explicit rights record for the current evaluation.

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
11. E19 real Provider Gate C/D evidence record, with a passing current-build
    run only when the documented external prerequisites exist.
12. E20's manifest and browser checklist, followed by the restricted evidence
    package and human decision required by Doc127 Phase 4.
