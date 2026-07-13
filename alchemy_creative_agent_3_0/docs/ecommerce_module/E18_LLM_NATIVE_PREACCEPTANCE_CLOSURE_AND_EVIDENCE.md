# E18 LLM-Native Pre-Acceptance Closure and Evidence

Status: active pre-acceptance authority

## Purpose

This document closes the verifiable work that does not need a live production
provider. It is deliberately not a substitute for real-image acceptance.

New E-Commerce work has one permitted path:

```text
product facts + explicit seller constraints + versioned platform evidence
-> Central Brain
-> exactly N natural-language complete-image intents
-> shared GPT Image 2 generation, review, bounded retry, and delivery history
```

No local component may invent a shot, platform suite, semantic slot, camera,
crop, selling point, copy phrase, type treatment, or fallback image.

## Pre-acceptance invariants

1. Only an explicit `ecommerce` template/scenario enters the E-Commerce
   vertical. General remains General even when the request contains a product
   name, marketplace name, Amazon, Taobao, Ozon, or similar words.
2. `llm_used != true`, `fallback_used == true`, an unavailable Brain, a
   missing plan, an empty plan, an incomplete plan, or a count mismatch is a
   blocked result. It never becomes a local recipe or a partial static set.
3. A request for N images produces exactly N Brain intents, planned assets,
   provider outputs, and export records. If a platform/provider declares a
   lower capacity, the job is blocked with a reason code; it is not sliced.
4. E-Commerce context is factual: product truth and reference bindings,
   seller-supplied constraints, approved literal copy, category evidence
   questions, and versioned platform constraints. It has no visual answer.
5. General and Photography Brain requests contain no E-Commerce creative
   context, platform profile, platform suite, or E-Commerce role semantics.
6. Historical recipe, overlay, CopyRenderPlan, text-pixel, and semantic-slot
   fields are read-compatible data only. They are scrubbed from all new
   E-Commerce runtime/Brain/prompt inputs. A historical job without valid
   opaque-slot lineage cannot obtain a new slot continuation.
7. Every E-Commerce record persists `ecommerce_runtime_provenance`: factual
   context identifiers and sources, versioned platform evidence, seller input
   field names, ignored historical execution fields, stage status, and any
   fail-closed reason code. It is queryable from the restored job status.
8. The UI reports a blocked remote-Brain/count contract in plain language and
   says that no local fallback was generated. It also keeps the production
   gate visible until an explicit readiness result exists.

## Implementation boundary

The E-Commerce branch may change factual-context preparation, E-Commerce
vertical binding/presentation, its UI, its documentation, and its tests. A
minimal shared Brain-contract validation is allowed only when it protects the
generic policy flag `requires_remote_creative_brain`; it must not alter
General/Photography direction or shared provider/review/retry ownership.

It must not implement fonts, OCR, canvas/SVG/HTML composition, coordinates,
safe areas, deterministic text repair, private retry loops, provider routing,
or a second project store.

## Required automated evidence

Run and retain the command output for:

```powershell
pytest -q alchemy_creative_agent_3_0/tests/test_v3_ecommerce_doc26_scenario_pack.py `
  alchemy_creative_agent_3_0/tests/test_v3_ecommerce_e10_workspace_delivery_panel.py `
  alchemy_creative_agent_3_0/tests/test_v3_ecommerce_slot_continuation_runtime.py `
  alchemy_creative_agent_3_0/tests/test_v3_doc102_brain_activation_checkpoint.py `
  alchemy_creative_agent_3_0/tests/test_v3_doc113_template_ownership.py

pytest -q alchemy_creative_agent_3_0/tests
```

The focused run must prove the invariant list above. The full V3 run must
remain green after rebase. Store command, commit hash, branch, main base, and
pass count in the record below; do not commit logs or generated images.

## Evidence record template

| Field | Record |
| --- | --- |
| Date / operator | |
| E-Commerce branch / commit | |
| Rebased `origin/main` commit | |
| Focused test command and result | |
| Full V3 command and result | |
| 1/2/4/7 exact-count evidence | |
| Declared-capacity block evidence | |
| unavailable/fallback/empty/incomplete/mismatch evidence | |
| General/Photography isolation evidence | |
| legacy-field non-replay evidence | |
| project restore / blocked UI evidence | |
| reviewer and decision | |

## Deferred real-provider gate

The following are intentionally **not accepted** by this document:

- real supplied-product reference fidelity and identity stability;
- final commercial quality, differentiated usefulness, and platform fitness;
- literal English, Chinese, or Russian text correctness in final pixels;
- production delivery readiness.

They require the shared `/v1/images/edits` reference-image path and General
Gate D to be complete, followed by real GPT Image 2 Provider Gate C/D runs
with retained product fixtures and human review. Until then, the E-Commerce
workspace must not label a set, a text image, or a product-reference workflow
as production accepted.
