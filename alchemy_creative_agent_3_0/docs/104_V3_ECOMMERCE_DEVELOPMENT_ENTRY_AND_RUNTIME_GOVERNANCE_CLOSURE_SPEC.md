# 104 V3 E-Commerce Development Entry And Runtime Governance Closure Spec

Status: accepted development-entry specification; foundation Gates A and B are
implemented and regression-tested. Live-provider and browser acceptance remain
separate recorded gates.

Doc105 freezes the shared E-Commerce slot-continuation and final text-pixel
delivery contract. It does not activate either interface before the associated
runtime and live-acceptance gates pass.

This document defines the short foundation-closure phase that must run in
parallel with E-Commerce Template development. It does not redesign E-Commerce
deliverables, weaken General Template boundaries, or replace Doc101/102.

## 1. Decision

V3 is mature enough to begin E-Commerce Template design and isolated template
implementation. New V3 jobs now use the Doc101/102 enforced runtime by
default: a frozen plan controls selective capability execution and composed
provider/review/retry contributions. It is not yet correct to call the shared
runtime fully closed for production specialization until the live-provider and
browser acceptance gates in this document have been completed.

The governing decision is:

```text
Start E-Commerce work in an isolated worktree.
In parallel, close V3 runtime governance on the foundation branch.
Do not expose E-Commerce as a fully production-ready professional template
until both tracks pass their activation gates.
```

This is not a pause on product design. It is a boundary that prevents vertical
rules from becoming another always-on bundle inside General or the shared
Visual Capability Cluster.

## 2. Prerequisite Baseline

This specification assumes the target integration branch contains the accepted
Doc101 and Doc102 activation work:

```text
101_V3_EXTENSIBLE_CAPABILITY_ACTIVATION_AND_HOT_PLUG_VISUAL_MODULE_SPEC.md
102_V3_DOC101_RUNTIME_MIGRATION_AND_CAPABILITY_ISOLATION_IMPLEMENTATION_SPEC.md
app/shared_capabilities/activation/
tests/test_v3_doc102_*.py
```

If a worktree does not yet contain that baseline, this document may be written,
reviewed, and used for E-Commerce design, but its implementation gates cannot
be marked complete there. The Doc101/102 baseline must be integrated before
runtime-closure work is started.

The foundation mainline now contains that baseline. New jobs default to
`enforced`; an explicit `V3_CAPABILITY_ACTIVATION_MODE=legacy|shadow` remains
the controlled rollback mechanism, while an existing frozen plan preserves its
recorded execution mode for retries and continuation.

## 3. Authority And Scope

This document extends:

```text
Doc76   foundation versus specialized-template governance
Doc79   acceptance archive and remaining live-provider validation
Doc91   shared Human Realism Plugin ownership
Doc93   reference-channel and prompt-ownership policy
Doc94   shared-runtime anti-overfitting governance
Doc95   portrait evidence and reviewed-best-result closure
Doc96   high-fidelity identity execution
Doc101  extensible capability activation and hot plug governance
Doc102  runtime migration and capability isolation implementation order
Doc105  E-Commerce slot continuation and text-pixel delivery contract
```

It also governs the entry criteria for the active E-Commerce Template.

It does not change:

```text
Project -> Template -> Scenario Pack -> Job ownership
GPT Image 2 as the sole final-pixel renderer
General Template's scenario-neutral product scope
E-Commerce ownership of professional marketplace deliverable maps
V1/V2/Lab runtime isolation
append-only retry history and final-delivery result presentation
```

## 4. Why This Closure Is Required

E-Commerce may need product identity, product-on-person Human Realism,
typography/layout, scene continuity, commercial review, and suite direction in
the same project. Those capabilities must not be selected merely because they
exist, because a template names them, or because a legacy cluster field happens
to be present.

The required ownership chain is:

```text
Central Brain activation intent
-> Activation Planner evidence/dependency/template-policy validation
-> frozen CapabilityActivationPlan for this job
-> active capability contributions only
-> composed generation contribution
-> GPT Image 2
-> review and bounded retry under the same plan
```

The following are defects in enforced mode:

- an inactive person capability adds face, skin, attractiveness, or anatomy
  instructions to a product-only, building, scene, or stylized-art job;
- an inactive product capability adds label, packaging, or marketplace rules
  to General Template;
- Provider scans raw visual-cluster fields instead of the composed generation
  contribution;
- Review or retry introduces domain-specific issue codes that were absent from
  the frozen plan without a recorded plan amendment;
- a specialized template delivers its professional slot map through General.

## 5. Parallel Workstreams

### 5.1 Foundation Workstream: Runtime Governance Closure

This workstream owns Doc102 implementation and acceptance. It must use one
shared execution registry and preserve existing Project Mode, Product API,
Scenario Pack, provider, and Visual Capability Cluster ownership.

Required results:

1. Central Brain or deterministic fallback emits a task profile and capability
   activation intent before evidence-gated visual execution.
2. The planner validates manifests, template policy, evidence, dependencies,
   conflicts, and budgets, then freezes one plan for the job.
3. Provider receives only the composed generation contribution for enforced
   jobs and records plan ID plus active capability IDs in internal audit data.
4. Review builds its issue/score contract from universal rules plus active
   capability contracts only.
5. Retry reuses the same plan. New evidence may create only an explicit,
   versioned, bounded plan amendment.
6. Legacy and shadow compatibility remain readable until the Doc102 removal
   gate passes.

### 5.2 E-Commerce Workstream: Isolated Design And Contract Preparation

This workstream may proceed in its own worktree and scoped branch. It may:

- define marketplace/platform profile contracts;
- define product category and suite-role recipes;
- design E-Commerce Template UI and project workflow;
- define E-Commerce-owned data structures and API namespaces;
- write fixture-based product, listing, A+, lifestyle, and export tests;
- implement template-local behavior that does not modify shared activation,
  provider, review, retry, public component, or dependency contracts.

It must not:

- rewrite Central Brain, ScenarioRuntime, the activation planner, or the
  shared provider path;
- add marketplace suite roles to General Template;
- copy Human Realism, product identity, reference policy, or review logic into
  E-Commerce code;
- bypass Template -> Scenario Pack -> Job -> frozen activation plan;
- claim production activation before the gates in Section 10 pass.

## 6. General Template Light-Commerce Boundary Acceptance

General Template is allowed to create a single, neutral product visual when a
user asks for it. It is not an E-Commerce suite director.

The following requests must remain valid General work:

```text
Give this cup a summer background.
Generate one atmospheric product image.
Create one social-media cover featuring this product.
Show this product in a tabletop use scene.
```

For these requests, General may activate product identity only when evidence
requires it and may activate Human Realism only when a real visible person,
hand, skin, or product-on-person scene is verified. It returns one requested
visual output or a neutral General continuation mode.

The following must never be inferred or emitted by General:

```text
Amazon/Ozon/Taobao marketplace suite
platform-specific selling-point sequence
size chart or garment-detail set
A+ page asset map
listing export package
marketplace language or platform compliance recipe
professional E-Commerce slot completion promise
```

Required tests must cover the four allowed requests and assert all of the
following:

- `template_id` remains `general_template`;
- no E-Commerce Scenario Pack or professional slot map is selected;
- no marketplace/platform profile is serialized into General prompt, review,
  retry, or public metadata;
- optional product identity remains evidence-gated;
- a product reference does not activate portrait identity or Human Realism
  without verified visible-person evidence.

## 7. Real Product Provider Acceptance

This is a provider/runtime validation, not a fixture-only test. Run it only
after the image upstream has confirmed the relevant `images.generate` model,
size, quality, and output-format combinations.

Use one owned product reference image and a controlled product project. Keep a
record for every run containing:

```text
provider/model and exact supported transport parameters
reference-image count and input operation
frozen activation-plan ID and active capability IDs
final provider prompt character count and contribution provenance
review status, issue codes, retry count, and final selected output IDs
project/job terminal status and output locations
```

Minimum live cases:

1. Product identity: change background and lighting while retaining silhouette,
   material, color, packaging, logo, and readable required label regions.
2. Product lifestyle: change scene and camera while preserving product truth;
   Human Realism is active only if a visible person is explicitly requested.
3. Product-on-person: verify that product identity and Human Realism both run
   under one frozen plan without crossing ownership boundaries.
4. Text/artifact failure: verify detection, one bounded retry when eligible,
   append-only failed attempt storage, and final-delivery-only presentation.
5. Provider failure: verify a structured failed/blocked project state, no false
   success image, preserved diagnostics, and no unbounded retry.

Manual acceptance is required for product truth and commercial usability.
Automated tests verify contracts, ownership, state transitions, and the result
surface; they do not replace visual inspection.

## 8. General Project Continuation Browser Acceptance

Before E-Commerce is production-active, manually verify this General user path
with browser-level evidence:

```text
new project
-> generate image
-> select a result
-> continue in the selected direction
-> upload a new reference
-> mark a direction as disliked/rejected
-> return to project list/detail
-> continue generation
```

Acceptance conditions:

- selected outputs become positive project context only through the documented
  selection action;
- rejected directions are retained as negative project context and do not
  silently reappear as preferred anchors;
- new reference ownership follows Doc93 channels and does not overwrite
  prompt-owned scene, style, lighting, wardrobe, or camera by default;
- project restoration preserves outputs, context, selection, rejection, and
  terminal job status after restart;
- retry-superseded candidates remain in folded history while the requested
  delivery count shows final outputs only.

## 9. E-Commerce Interface Freeze

Freeze the following integration envelope before detailed E-Commerce work is
merged. This is a coordination contract, not a freeze on template-local design.

```text
Template -> Scenario Pack -> Project Job remains the only E-Commerce entry.
TemplateCapabilityPolicy is the capability-selection authority.
E-Commerce owns platform profiles, category suite roles, export manifests, and
professional acceptance profiles.
Shared capabilities expose contributions through the frozen plan only.
Provider/model routing, shared review/retry contracts, and General public
interfaces cannot be changed by E-Commerce without foundation-owner agreement.
```

Any change to a shared schema, manifest contract, provider parameter, review
issue vocabulary, retry contract, public component interface, dependency, or
lock file requires coordination between the two workstreams before merge.

Doc105 further freezes the only future per-slot continuation interface. It
creates an append-only E-Commerce child job, inherits the parent frozen plan
by default, and uses shared generation/review/retry. It is not implemented by
selection, deletion, or automatic retry, and no slot-redo control may appear
before that route, lifecycle, resolver, and browser tests exist.

Doc105 also separates E-Commerce copy planning from final text pixels. Platform
profiles may plan allowed copy and safe areas, while deterministic typography,
OCR, overflow/spelling/claim checks, and bounded recovery remain shared-runtime
work required for live activation.

When an OpenAI-compatible gateway explicitly owns line failover, retry, and
backoff for an individual image request, the foundation owner may enable
`OPENAI_IMAGE_GATEWAY_MANAGED_FAILOVER`. This is a shared provider-runtime
mode, not an E-Commerce feature: each logical output keeps one request in
flight, the gateway receives its full bounded opportunity to select a line, and
the V3 outer runtime records its terminal result instead of replaying the same
request. The effective client budget is capped at the configured managed
failover timeout (240 seconds by default), with a small local finalization
margin; direct providers retain their normal retry behavior unless explicitly
opted in.

## 10. Activation Gates

### Gate A: Doc102 Enforced Runtime

Pass only when new V3 jobs in `enforced` mode prove:

- a Brain/fallback activation intent exists;
- one immutable plan is stored before generation;
- active capability IDs, executed builders, prompt contributions, review issue
  codes, and retry sources all match the plan;
- inactive capabilities have zero provider, review, retry, and public-result
  contribution;
- only an explicit bounded plan amendment may change retry capability scope;
- General and E-Commerce policies remain isolated.

Current foundation evidence: the Doc102 activation suite covers the frozen
plan, selective execution, contribution composition, provider isolation,
review/retry alignment, amendment safety, and cross-domain isolation. A
default-mode regression test proves that a new job is `enforced` without an
environment override.

### Gate B: General Light-Commerce Boundary

Pass only when the tests in Section 6 pass in enforced mode, including negative
assertions that General never constructs E-Commerce suite, marketplace, or
export contracts.

Current foundation evidence: General regression cases cover a summer
background replacement, product atmosphere image, social cover, and tabletop
use scene. Each remains one `generic_social` image on the General path with no
suite-direction capability or marketplace deliverable vocabulary.

### Gate C: Live Product Provider And Review

Pass only when every case in Section 7 has an evidence record, manual visual
acceptance, bounded terminal behavior, and no provider-parameter incompatibility
left unexplained. Where a selected E-Commerce delivery role requires final
text pixels, the Doc105 deterministic layout, OCR, safe-area, locale, and
bounded-recovery acceptance matrix is also mandatory; copy planning alone is
not sufficient evidence. For a gateway-managed failover provider, the evidence
must additionally prove that an upstream terminal failure creates no duplicate
fresh request for the same logical output and becomes a bounded Project Mode
job result.

### Gate D: General Browser Continuation

Pass only when the Section 8 path is recorded against a live General project
and its restored state is correct.

Current preflight evidence: a browser-driven General project can be created in
isolated local storage, opened into its compose workspace, returned to its
project detail, reopened from the project list, and navigated back to the V3
home. The home control is an explicit route link so it remains reliable even
when transient workspace state is being cleared. The final select, reject,
upload, and continuation-after-real-render steps remain pending Gate C because
they require a real provider output rather than a fabricated browser fixture.

### Gate E: E-Commerce Template Activation

The E-Commerce Template may be presented as production-ready only when Gates A
through D pass and its own template activation gate validates its declared
capability policy, required product evidence, professional suite ownership, and
E-Commerce-specific acceptance tests. This includes the Doc105 slot
continuation and text-pixel contract tests whenever those public capabilities
are implemented.

## 11. Completion Definition

The foundation is not described as “100% closed” merely because unit and
contract tests pass. The correct completion claim is:

```text
V3 foundation is production-governed for specialization when Doc102 enforced
runtime, General boundary, live provider/review, and browser continuation gates
all pass with recorded evidence.
```

Until then, use this accurate status:

```text
V3 foundation can safely host specialized-template development, while runtime
governance closure and live acceptance continue in parallel.
```

## 12. Implementation Order And Commit Boundaries

1. Integrate the Doc101/102 baseline into the foundation branch. Completed.
2. Complete and commit Doc102 phases in small independently verifiable units.
   Completed for the default enforced-runtime closure.
3. Add General light-commerce boundary tests without changing General UI scope.
   Completed.
4. Record live product/provider acceptance after upstream compatibility is
   verified.
5. Record browser continuation acceptance.
6. Rebase the E-Commerce branch onto the latest foundation branch, resolve only
   on the E-Commerce branch, and run the complete activation-gate matrix before
   enabling E-Commerce production entry.

Each milestone must include focused tests, diff review, a commit, and push
status. Never commit generated images, logs, caches, contact sheets, or ad-hoc
evaluation directories unless they are deliberate repository assets.

## 13. Final Rule

```text
Foundation makes every image better through governed reusable capabilities.
General remains simple and scenario-neutral.
E-Commerce owns professional commerce deliverables.
No template bypasses the frozen activation plan.
```
