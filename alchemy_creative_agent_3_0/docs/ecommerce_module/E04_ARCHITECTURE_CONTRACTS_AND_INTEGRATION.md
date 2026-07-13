# E04 Architecture, Contracts, and Integration Map

## Runtime position

```text
Project
  → ecommerce_template
    → ecommerce Scenario Pack
      → commerce factual context + product truth
      → V3 Brain decides a product-specific output set
      → frozen capability plan
      → provider generation
      → review/retry/selection
      → commerce export manifest
```

The E-Commerce module is a specialized policy and deliverable layer. It does
not call providers directly and does not fork the central runtime.

Doc104 is the integration gate authority after this package is rebased onto the
current foundation: every production E-Commerce job must retain the frozen
capability activation plan supplied by the shared runtime. This module may
configure E-Commerce-owned factual context and versioned constraint evidence,
but may not locally author output recipes or alter activation, provider,
shared review, or retry semantics.

## Existing code ownership

| Existing location | E-Commerce responsibility |
| --- | --- |
| `app/scenario_packs/ecommerce/contracts.py` | commerce contracts |
| `product_truth.py` | immutable facts, unknowns, review obligations |
| `marketplace_rules.py` | versioned platform constraints with provenance |
| `commerce_brief.py` | seller-supplied audience, motivations, pain points, trust |
| `selling_point_planner.py` | historical-read compatibility only; no forward recipe planning |
| `copy_bridge.py` | approved literal-copy provenance only |
| `commerce_critic.py` | commerce review signals |
| `export_packager.py` | platform-aware export metadata |
| `app/project_mode/templates` | template activation and project gate |

## Required data flow

```text
user request + uploaded refs
→ product truth
→ commerce brief
→ platform/category factual context
→ remote Central Brain image-set decision
→ capability activation intent
→ frozen plan
→ generation/review/retry
→ selected delivery outputs
→ export manifest
```

## Contract rules

1. Public contracts remain product-level. No seed, sampler, provider, model,
   node graph, or low-level image-control fields.
2. The full user prompt remains lossless; only duplicated framework guidance
   may be compacted.
3. Product facts, platform profile version, category evidence version, opaque
   output IDs, Brain-returned intents, capability plan ID, review outcome, and
   export status are auditable. A legacy recipe ID is historical-read metadata
   only and is never a new-job creative input.
4. Template-specific fields are namespaced under the E-Commerce project profile.
5. Historical records without newer fields remain readable.
6. Every job requires a project ID and product reference or an explicitly
   confirmed text-only product brief.
7. Optional `commerce_profile.metadata.copy_locale` and
   `commerce_profile.metadata.approved_literal_copy` are E-Commerce-only
   factual signals. Historical `overlay_copy` remains readable but is not
   accepted for new work. Approved literal copy is passed to the LLM/provider as a
   provider-native requirement, never a local overlay; it remains subject to
   text policy and claim review. These signals do not add General Template
   semantics or renderer controls.

## Compatibility rule

Existing E-Commerce APIs and fields must remain readable. New jobs use factual
context and opaque output IDs. Legacy recipe/slot fields may be decoded for old
records only; they cannot enter the remote Brain or generation path. This keeps
General Template semantics unchanged.

## Forbidden integration patterns

- importing V1/V2/Lab runtime modules;
- provider calls from category/platform code;
- platform/category default slots, shot order, camera, crop, or promotional
  copy emitted as a forward creative plan;
- platform branches inside Central Brain;
- marketplace slot names inside General Template;
- category-specific rules inside Human Realism or Product Identity plugins;
- frontend-only activation of a locked or unavailable template;
- rewriting historical project records in place.
