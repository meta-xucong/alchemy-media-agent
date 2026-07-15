# Doc128 — Shared Human Realism Constraint And Review Closure

## Status

Implementation authority for the forward V3 Human Realism path.

Doc128 implements the ownership rules already established by Docs91, 93, 94,
113, 117 and 124. It supersedes the forward-runtime prompt-atom and casebook
mechanisms in Docs68–72. Those documents remain historical evidence and may be
read to explain old records, but their casebook fragments, named demographic
branches and retry wording must not be emitted for a new V3 job.

## Problem Being Closed

The old implementation mixed useful quality lessons with a large, static
casebook of positive prompts, negative prompts, role overlays, review labels,
and retry strings. The result could override a Brain-authored direction,
overfit to historical portrait and kidswear examples, and leak internal review
vocabulary into a Provider prompt. That is incompatible with the V3 execution
truth contract:

```text
user intent / permitted reference truth / remote Brain direction
  -> frozen CapabilityExecutionEnvelope + ResolvedConstraintLedger
  -> GPT Image 2 whole-image materialization
  -> real-pixel review + one bounded shared retry + append-only winner history
```

Human Realism remains a shared foundation capability. It is neither a child,
kidswear, East-Asian, ecommerce, General, nor Photography delivery module.

## Forward Contract

### 1. Activation

- The shared activation planner decides whether Human Realism is active.
- A visible, non-stylized real person is a required activation invariant.
- A stylized person may be inactive when the frozen intent says the output is
  not a real photograph.
- An explicit young-person direction is only an auxiliary safety-sensitive
  signal under Doc124. It never creates an age classifier, a vertical route, or
  a child-specific prompt recipe.
- Product-only or flat-lay requests do not activate Human Realism merely
  because a garment is associated with children.

### 2. Resolved constraint contribution

An active capability contributes at most these shared, owner-labelled concepts:

| Channel | Capability contribution | Owner / precedence |
| --- | --- | --- |
| `human_rendering` | physically credible photographed person; no synthetic beauty rendering | Human Realism, below user/Brain art direction |
| `identity_age_fidelity` | preserve explicit or reference-backed identity and age direction | evidence / user intent, hard where applicable |
| `physical_coherence` | believable anatomy, material response, light, depth and contact | Human Realism, quality guard |
| `reference_boundary` | improve rendering without widening reference-owned channels | Doc93 reference policy, hard boundary |
| `young_person_safety` | age-appropriate, fully dressed, family-friendly ordinary context | Doc124, only when explicit evidence exists |

The materializer receives the resolved ledger entry, not a casebook, role
recipe, keyword-derived age label, raw reviewer code, or concatenated prompt
stack. The contribution must remain concise and must preserve the requested
mood, styling and creative direction.

### 3. Review and retry

Real-pixel `vision_model` or `hybrid` review uses only these forward shared
dimensions when Human Realism is active:

```text
human_rendering_artifact
human_anatomy_or_proportion
human_age_or_identity_fidelity
human_skin_or_retouch
human_scene_coherence
```

They map to the common `human_realism` score dimension. A visual result that is
only metadata or local heuristic evidence remains non-certifying under Docs113
and 118.

The one shared bounded retry consumes a resolved repair intent such as
“repair photographic naturalness and physical coherence without changing
user-owned direction.” It must not serialize raw vision output, old issue-code
names, anatomy micro-instructions, beauty language, or a child-specific patch.

### 4. Compatibility

- Historical jobs and retry records remain readable.
- Older human issue identifiers are read through an explicit alias map into one
  of the five forward dimensions; they are not re-emitted on new jobs.
- Old casebook metadata is read-only historical provenance. New plans must not
  carry `doc68_casebook_recipe`, `casebook_recipe_library`, prompt-atom fields,
  or the former Doc70–72 library markers.
- No legacy alias may cause a capability to activate, alter a reference channel,
  or bypass an enforced envelope/ledger decision.

## Non-goals

Doc128 does not add a children’s visual module, a fashion/kidswear route,
template roles, local typography, an OCR loop, a Provider fallback, or prompt
recipes for any demographic. Apparel truth remains Product Identity evidence;
photographic creative direction remains with the remote Brain; professional
deliverables remain owned by their specialized template.

## Required Regression Matrix

1. Adult portrait, explicit young person, product-on-person, stylized person,
   product-only flat lay, and non-person product prove correct activation.
2. All active paths expose only the five forward review dimensions and concise
   resolved guidance; no casebook marker or historical child issue code reaches
   a Provider contribution or review contract.
3. A legacy review payload normalizes to a forward dimension without changing
   job lineage or becoming a new prompt fragment.
4. General, E-Commerce and Photography keep their own template/creative
   ownership; the shared capability has no scenario-specific delivery syntax.
5. Vision/hybrid certification, append-only retry history and final-winner
   delivery continue to use the existing shared lifecycle.

## Acceptance and release boundary

Source and unit regressions can certify the contract migration. Real Provider
quality remains a controlled acceptance requirement: the current P10-01 run
ended with a Provider timeout before pixels, review or delivery, so it is
non-counting. No production gate opens until a new, independent controlled run
has a real-pixel `vision_model` or `hybrid` verdict and certified final winner.
