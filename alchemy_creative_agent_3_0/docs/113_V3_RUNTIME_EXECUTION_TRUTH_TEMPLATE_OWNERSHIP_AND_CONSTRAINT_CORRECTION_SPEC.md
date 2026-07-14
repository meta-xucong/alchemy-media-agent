# Doc113 V3 Runtime Execution Truth, Template Ownership, and Constraint Correction

Status: corrective implementation authority after Docs 100--103 and Doc111

Scope: V3 Foundation, General Template boundary, E-Commerce Template boundary,
and every V3 entry path. Doc100 remains authoritative: GPT Image 2 is the only
production final-pixel renderer.

This document is the mainline-numbered import of the audit authority formerly
prepared as `104_V3_RUNTIME_EXECUTION_TRUTH_TEMPLATE_OWNERSHIP_AND_CONSTRAINT_CORRECTION_SPEC.md`.
It does not replace the existing mainline documents numbered 104 and 105.
References to the former audit runtime-correction document in this imported
authority mean **Doc113**; references to its apparel follow-up mean **Doc114**.

Doc117 reconciliation: this document remains the execution-truth authority.
Doc117 extends it only at the real-reference Provider boundary: a derived
admission/result projection and a narrow no-pixel failure classifier reuse the
same normalized intent, envelope, ledger, Provider result, retry record, and
Job lifecycle. They must not create another planner, envelope, prompt format,
or lifecycle. The remote Brain still owns complete natural-language creative
direction; the shared runtime still owns factual constraints and truthful
execution status.

## 1. Purpose and authority

V3 must have one execution truth for every job:

```text
one NormalizedV3JobIntent
  -> one immutable CapabilityExecutionEnvelope
  -> one template-owned TemplateDeliverablePlan
  -> one ResolvedConstraintLedger
  -> one provider materialization
  -> one review/retry contract consuming the same frozen evidence
```

Doc113 extends Docs 76, 91, 93, 94, 100, 101, 102, 103, and 111. It wins where
older code or documents give two layers ownership of execution consistency,
template delivery ownership, constraint resolution, count resolution, or review
truthfulness. It does not alter Project -> Template -> Scenario Pack -> Job
ownership, V1/V2 isolation, GPT Image 2 production rendering, append-only
history, or shared Human Realism ownership.

The work is ordered deliberately: first remove split execution and ownership,
then repair contract data flow, and only then permit visual capability work.
Prompt tuning is not a substitute for a missing contract.

## 2. Corrected audit findings

### F1. A frozen enforced plan must not downgrade

New V3 jobs default to `enforced`; retain that behavior. A persisted plan's
mode is immutable, including `enforced`. A resume under a conflicting runtime
mode must either execute the frozen mode or return the structured
`capability_execution_mode_mismatch` block. It must never emit an enforced plan
while executing shadow/legacy behavior.

### F2. Specialized templates own professional deliverable maps

Foundation may add reusable quality information to an already-selected role. It
must not create E-Commerce main/feature/scenario/detail/trust/cover roles,
slot maps, retry language, or marketplace delivery packages. General remains
generic and must not acquire E-Commerce vocabulary.

For new E-Commerce work, E17 and Doc111 remain in force: no static suite,
camera, crop, scene, default copy, or fixed recipe may be restored. The single
E-Commerce `TemplateDeliverablePlan` is a count-bounded binding of the remote
Central Brain's natural-language `image_set_plan` output to opaque delivery
identities and factual acceptance constraints. It is not a local replacement
for the Brain's creative decision.

### F3. All entry paths need one input truth

Project Mode, Product API, and direct ScenarioRuntime entry must normalize
requested count, size, aspect, explicit role/slot request, visible-text policy,
source-truth locks, and provenance before a planner reads them. Root metadata is
edge compatibility only; downstream code consumes the normalized intent.

### F4. Prompt assembly must resolve conflicts before materialization

String append/de-duplication cannot decide conflicts. Each generation-relevant
constraint must have a channel, owner, strength, precedence, resolution, and
provenance. For example, no-visible-text wins over a template preference for
copy space; the resolved result may request blank negative space, never a
headline/CTA plus a prohibition on visible text.

### F5. Review must state what was actually verified

`metadata_only` is non-certifying/manual review and must remain so. Local file
heuristics may verify file integrity only. They cannot semantically approve
hard identity, product truth, person/anatomy, visible-text, or role-diversity
contracts. Those contracts require real or hybrid pixel review; otherwise the
result is `manual_review` / `unverified`, not visually passed delivery.

### F6. Shared code uses universal facts, not vertical vocabulary

Human Realism uses `product_on_person_detected`, not
`ecommerce_human_model_detected`. Product-on-person, age fidelity, texture,
exposure, anatomy, material separation, and reference evidence are generic
facts. No kidswear, child, marketplace, or E-Commerce Human Realism plugin,
provider route, shared prompt recipe, or shared deliverable map is permitted.
Legacy child issue aliases may be read at a Product API boundary but cannot
construct a direct retry prompt or bypass the envelope.

### F7. No second selection/materialization path

E-Commerce policy must not activate `suite_direction`. Accepted executor
results are authoritative after enforced execution; ScenarioRuntime cannot
discard them through `_selected_capability_ids()` or another legacy selector.
In enforced mode Provider, Review, and Retry consume the envelope and ledger
only. Legacy Visual Capability Cluster data is available solely through an
explicit labelled legacy-to-envelope adapter, never as fallback.

### F8. Count is a resolved contract

Remove hidden `ECOMMERCE_MAX_REQUESTED_IMAGES = 4` behavior. The effective
maximum comes only from declared template/platform/provider capability and
records provenance. A request up to seven is preserved if supported; an
unsupported explicit count blocks or requests a choice instead of silently
truncating. Critics evaluate final effective count and the selected plan, never
`len(recipes) >= 5`.

## 3. Required contracts and invariants

```python
class NormalizedV3JobIntent:
    request_id: str
    scenario_id: str
    template_id: str
    explicit_requested_image_count: int | None
    explicit_requested_image_size: str | None
    explicit_requested_aspect_ratio: str | None
    suite_slot_request: list[str]
    visible_text_policy: str  # required | allowed | forbidden | unspecified
    user_constraints: list[dict]
    source_truth_locks: list[dict]
    provenance: list[dict]

class CapabilityExecutionEnvelope:
    plan: CapabilityActivationPlan
    execution_mode: str
    catalog_version: str
    contribution_fingerprint: str
    active_capability_ids: list[str]
    provider_contract_fingerprint: str | None
    review_contract_fingerprint: str | None

class TemplateDeliverablePlan:
    owner_template_id: str
    scenario_id: str
    requested_count: int
    effective_count: int
    slots: list[dict]
    template_acceptance_contract: dict

class ResolvedConstraintLedger:
    intent_id: str
    entries: list[dict]
    conflicts: list[dict]
    provider_projection: dict
    audit_summary: dict
```

Required invariants:

1. A new production V3 job has one enforced envelope from planning through
   review and retry.
2. A persisted plan cannot silently mode-downgrade.
3. Only active capabilities contribute generation, review, retry, or memory
   data.
4. Exactly one template owns a job's final delivery plan.
5. The three entry paths normalize equivalent requests identically.
6. One requested output creates one delivery binding, never an implicit suite.
7. User no-text policy cannot be overridden by copy-space preference.
8. Shared modules have no vertical role/package taxonomy.
9. Uninspected output is never reported as semantically verified.
10. No child/kidswear-specific module or provider route is added.
11. Enforced paths have no post-plan selector or direct legacy-cluster fallback.
12. Count is resolved once, with capability provenance and no silent cap.

## 4. Implementation phases

### Phase 0 -- red regressions and boundary freeze

Add tests before production changes for: default enforced behavior; immutable
enforced resume; entry parity for count/size/text/slot; one E-Commerce plan;
no `suite_direction`; no post-execution selector loss; no enforced legacy
fallback; non-certifying metadata/local-only hard contracts; count 1/2/4/7;
and effective-count-based CommerceCritic review.

### Phase 1 -- immutable envelope and execution propagation

Create the immutable `CapabilityExecutionEnvelope`; frozen mode overrides the
environment or fails with `capability_execution_mode_mismatch`. Remove the
enforced post-execution selector. Propagate the same envelope fingerprint to
Provider, Review, Retry, and public job provenance. Migrate old metadata only
through explicit edge adapters.

### Phase 2 -- template ownership and shared de-verticalization

Remove E-Commerce maps, recipe bridges, slot/retry wording, and production
dependencies from `ModeAwareRoleDirector`, `GeneralSuiteDirector`, and shared
Visual Capability Cluster paths. Remove `suite_direction` from E-Commerce
policy. E-Commerce Scenario Pack owns the one Brain-bound deliverable plan;
General uses only generic modes. Rename shared Human Realism evidence to the
generic product-on-person fact.

### Phase 3 -- normalized intent and cardinality contract

Normalize every public request once. The E-Commerce pack consumes only the
intent and its declared capability contract. Preserve explicit count up to the
declared limit; block unsupported count with provenance. Apply a single
effective size/aspect projection. Make critic coverage relative to final count
and plan. Preserve E17's LLM-native output intent ownership.

### Phase 4 -- resolved constraint ledger

The activation composer becomes an active-capability proposal filter. A ledger
resolver applies channel precedence and records winners, rejected clauses,
translations, and user choice needs. Provider receives protected user direction
plus one resolved role, text policy, size/aspect, product truth, and generic
Human Realism projection. A compact audit contains ledger ID, count, size,
aspect, text policy, deliverable owner, and applied/translated/rejected IDs.

### Phase 5 -- envelope-bound truthful review

Review reports `verification_state` as `verified`, `locally_checked`,
`unverified`, or `unavailable`, separately from review status. Hard identity,
product, person/anatomy, visible text, and role contracts in the envelope or
ledger require real/hybrid pixels to be semantically verified. Otherwise retain
the append-only candidate for manual review; do not falsely pass or endlessly
retry. Retry ownership must match an active capability or the owning template.

## 5. Mandatory verification matrix

| Case | Required result |
| --- | --- |
| E-Commerce count 1 | one Brain-bound delivery binding, critic complete |
| E-Commerce count 2 with explicit intent IDs | two bindings only, same across all entry paths |
| E-Commerce count 7 on declared support | seven bindings, no hidden four-cap |
| Unsupported explicit count | structured block with provider/platform provenance |
| Explicit vertical intent | one identical resolved effective projection across entry paths |
| General count 2 | two generic outputs, no E-Commerce vocabulary |
| Enforced resume under shadow environment | frozen enforced execution or structured mismatch |
| Hard semantic contract with local-only review | manual/unverified, never semantic pass |

Source-boundary tests must also prove there is no General -> E-Commerce
leakage, no kidswear-specific runtime, no post-plan selector, and no enforced
legacy metadata read outside the adapter.

## 6. Non-goals and stop condition

Doc113 does not authorize child/apparel visual tuning, a local renderer,
static E-Commerce visual recipes, a real-vision requirement for every low-risk
image, V1/V2 changes, or prompt shortening as an alternative to resolution.

After Phases 0--5 are green, stop. Doc114 governs any later apparel-on-child
or garment-truth capability work and must be opened as a separate task.
