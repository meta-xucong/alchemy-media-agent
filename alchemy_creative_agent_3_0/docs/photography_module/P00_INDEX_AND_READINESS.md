# Photography Module Document Index And Readiness

## 1. Document Family

This directory is the independent planning and implementation authority for the
Alchemy Creative Agent V3 Photography Module.

```text
module: Photography / 摄影师模块
scenario_id: photography
template_id: photography_template
vertical_agent: PhotographyAgentFamily
route_hint: /creative-agent-v3/photography
document_family: P00-P99
feature_branch: codex/photography-module
```

The Photography document family is intentionally isolated from the numbered V3
foundation documents and from the E-Commerce document family. Photography work
must not add photography-specific deliverable maps to the General Template or
reuse E-Commerce suite ownership.

## 2. Current Status

> Update: Mainline 001-004 are landed. `1578cbc` provides independent
> professional-set role execution and complete-set aggregation; `364a1c8`
> preserves specialized Photography role prompt ownership. The deployment gate
> stays off by default. P10 execution closure is verified, but real-pixel
> review and visual-quality acceptance remain required. P11 records the
> LLM-first and real-pixel production correction before further release work.
> Current shared-boundary note (Docs113/117): a P10 terminal image is not a
> photography quality pass unless its result surface shows `vision_model` or
> `hybrid` provenance and a certifying final verdict. `metadata_only`,
> `manual_confirmation_required`, and every no-pixel Provider failure remain
> non-certifying. Photography does not add a second review/retry state or a
> local creative recipe to compensate.

```text
planning approval: accepted
foundation rules: accepted for module development
master development specification: accepted for phased implementation
named-photographer governance: drafted
implementation: P1-P6 complete; professional-set execution and continuation landed
mainline contracts: 001-005 and shared review-certification projection landed
activation status: production closed; controlled P10 acceptance is evidence-only
merge readiness: runtime contracts integrated; real-provider quality certification blocked externally
```

P0 was documentation-only. P1 adds module-local contracts, an inactive Scenario
Pack, an inactive profile catalog, inactive scene/technique descriptors and an
unregistered vertical-agent skeleton. It does not change production runtime,
public schemas, providers, frontend behavior or shared registries.

P1 verification:

```text
Photography focused tests: 11 passed
Scenario Pack / vertical / E-Commerce regressions: 29 passed
full V3 suite: 530 passed
root suite: 144 passed, 1 unrelated pre-existing Alchemy Lab failure
shared file changes: none
production registration: none
```

P2/P3 continuation status:

```text
P2 mainline audit: documented in P05
P3 scope: module-local General Photography shadow planner only
P3 verification: 19 Photography focused, 29 isolation regression and 544 full V3 tests passed
P3 audit repairs: keyword boundaries, general-scene fallback, domain isolation and Doc93 prompt ownership
P3 publication: feature-branch milestone 450137f, rebased and verified on current origin/main
production activation: still disabled
```

P4 continuation status:

```text
P4 scope: module-local Portrait, Landscape, Still Life and Animal scene contributions
P4 verification: 28 Photography focused, 132 isolation regression and 553 full V3 tests passed
P4 publication: implementation milestone 507a9b3
real-output acceptance: paused until shared production hooks exist
P5 status: complete on landed trusted profile selection contract
specific-animal identity: consumes landed shared nonhuman_subject_identity capability
P6 status: module-owned planning and shared production execution landed
```

## 3. Authority Order

Photography development must follow this order when rules overlap:

1. Repository `AGENTS.md`.
2. Accepted V3 foundation authorities, especially Docs76, 91, 93-96, 100-103,
   111, 113, and 117.
3. `P01_PHOTOGRAPHY_MODULE_FOUNDATION_RULES.md`.
4. `P03_NAMED_PHOTOGRAPHER_PROFILE_AND_RIGHTS_GOVERNANCE.md`.
5. `P02_PHOTOGRAPHY_MODULE_MASTER_DEVELOPMENT_SPEC.md`.
6. `P04_ROADMAP_TESTS_ACCEPTANCE_AND_MAINLINE_COORDINATION.md`.
7. Later Photography implementation notes and experiments.

If a Photography document conflicts with the V3 foundation renderer, reference
ownership, identity, retry, activation, or isolation contract, the foundation
contract wins and Photography work pauses for an explicit design decision.

## 4. Document Index

| Document | Purpose | Status |
| --- | --- | --- |
| P00 | Index, authority, readiness and merge gate | Active |
| P01 | Non-negotiable Photography development rules | Active |
| P02 | Product model, architecture, contracts and UX | Active |
| P03 | Named-photographer manual selection and rights governance | Active |
| P04 | Roadmap, tests, acceptance and mainline coordination | Active |
| P05 | P2 mainline integration audit and P3 shadow boundary | Active |
| P06 | P4 first-wave scene director implementation audit | Active |
| P07 | P5 named-profile implementation audit | Active |
| PX Mainline 001 | Trusted photographer profile selection contract request | Landed on mainline |
| PX Mainline 002 | Non-human subject identity foundation request | Landed on mainline |
| P08 | Mainline-003 gated central-runtime activation handoff | Historical; superseded for set execution by 1578cbc |
| P09 | P6 professional-set and continuation implementation audit | Historical; execution blocker resolved by 1578cbc |
| PX Mainline 004 | Photography set execution and continuation contract | Landed at 1578cbc / 364a1c8 |
| P11 | LLM-first creative direction and real-pixel quality correction | Landed at `fc3f5c2` / `db70c44`; real-provider certification pending |
| PX Mainline 005 | LLM-first Photography and real-pixel quality gate request | Historical request; fulfilled by `fc3f5c2` / `db70c44` |
| PX Mainline 006 / Doc116 | Review-certification projection and delivery withholding | Landed at `db70c44`; real P10 evidence remains pending |

Future documents must remain in this directory and use the `Pxx_` number
family. Do not continue the root V3 document number sequence for Photography.

## 5. Product Decision Summary

Photography is a specialized professional template, not a General mode and not
an E-Commerce sub-mode.

Its task model is:

```text
what to photograph
x why the photograph is commissioned
x how it should be photographed
x what reference truth must remain unchanged
```

It supports:

```text
text-to-photo
ordinary-photo-to-professional-reshoot
single hero photograph
professional photographic set
```

Named photographer profiles are a separate, explicit product control:

```text
no frontend selection -> General Photography Profile
explicit frontend selection -> exactly that pinned named profile
LLM inference or automatic named-profile choice -> forbidden
selected profile unavailable -> transparent block, never silent substitution
```

## 6. Readiness Gates

Photography may become active only after all of the following pass:

1. Dedicated contracts and module manifests are implemented.
2. General and E-Commerce isolation tests pass.
3. Named-profile manual-selection tests pass at API, Brain, runtime and UI layers.
4. Text-only and reference-conditioned flows pass real-output review.
5. Four first-wave scene directors pass their own acceptance matrices.
6. Photography review and bounded rerender use the same frozen activation plan.
7. Rights and availability metadata are present for every named profile.
8. Required mainline contract changes have landed on `origin/main` and the
   Photography branch has rebased onto them.
9. Full V3 and root regression suites pass.
10. The resulting integrated state is reviewed before merge.

## 7. Merge Rule

The Photography branch remains isolated until development and acceptance are
complete. It must not be merged piecemeal merely to obtain missing shared
fields or hooks. Shared-contract needs follow the coordination protocol in P04.

Final merge preparation must report:

```text
affected scope
tests and real-output evaluations
commit hashes
push status
mainline dependencies
known limitations
rollback path
```
