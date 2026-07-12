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

```text
planning approval: accepted
foundation rules: drafted
master development specification: drafted
named-photographer governance: drafted
implementation: not started
mainline contract requests: none submitted yet
activation status: inactive
merge readiness: not ready
```

This milestone is documentation-only. It does not authorize runtime, schema,
provider, frontend, or shared-registry changes.

## 3. Authority Order

Photography development must follow this order when rules overlap:

1. Repository `AGENTS.md`.
2. Accepted V3 foundation authorities, especially Docs 76, 93-96, 100-102.
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
