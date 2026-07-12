# Photography Roadmap, Tests, Acceptance And Mainline Coordination

## 1. Delivery Strategy

Photography development proceeds in isolated, independently verifiable phases.
The branch must rebase onto the latest `origin/main` before each new milestone
and before integration.

## 2. Phase P0 - Governance And Contracts

Deliver:

```text
P00-P04 document family
four-axis task model
manual named-profile selection rule
module ownership boundary
proposed contracts
test and acceptance matrix
mainline coordination protocol
```

Gate:

```text
documentation diff only
no shared runtime changes
no General or E-Commerce behavior changes
branch and worktree isolation verified
```

## 3. Phase P1 - Inactive Module Skeleton

Deliver module-owned files only:

```text
Photography Scenario Pack manifest
Photography internal contracts
inactive profile catalog
PhotographyAgentFamily skeleton
module-local scene and technique registries
unit tests for local contracts
```

The card remains inactive and no production generation path changes.

Gate:

```text
module imports independently
removal test passes
no V1/V2 dependency
no direct provider call
no public contract change
```

## 4. Phase P2 - Mainline Integration Requests

Before implementing shared integration, audit whether existing extension points
are sufficient. Likely mainline needs may include:

```text
trusted frontend photographer profile selection fields
catalog-list/read API contract
job and project persistence for pinned profile binding
template policy lookup for photography_template
global capability catalog compatibility for photography_template
scenario card and shared shell registration hook
review issue ownership registration hook
```

Do not assume all requests are necessary. Prefer existing typed extension
points when they preserve audit, validation and compatibility.

## 5. Mainline Integration Request Protocol

When blocked by a shared need, create a Photography document named:

```text
PX_MAINLINE_REQUEST_<short_name>.md
```

It must contain:

```text
request ID and status
blocking Photography phase
current mainline behavior
minimal requested change
exact fields, types and defaults
validation and error semantics
API and persistence impact
backward compatibility
General/E-Commerce isolation impact
migration behavior
focused tests required on mainline
acceptance evidence expected
Photography work that must remain paused
```

Then:

1. Stop only the dependent Photography work.
2. Send the request summary and file path to the user.
3. Do not implement a parallel contract or encode the field in an unrelated
   metadata escape hatch merely to avoid coordination.
4. After the user confirms the mainline change has landed, fetch `origin/main`.
5. Rebase `codex/photography-module` onto the new mainline commit.
6. Verify the mainline tests first, then resume the Photography phase.

## 6. Phase P3 - General Photography Runtime

Deliver:

```text
General Photography default binding
photography brief director
camera, lighting, composition, color and retouch contributions
single-hero text-to-photo flow
Photography professional review profile
```

No named profile activates in this phase.

Gate:

```text
null profile selection is deterministic
Brain cannot introduce a named profile
General and E-Commerce regression unchanged
real-output baseline comparison recorded
```

## 7. Phase P4 - First-Wave Scene Directors

Implement sequentially:

```text
portrait
landscape
still life
animal
```

Each scene must pass focused unit, prompt-ownership, real-output and leakage
tests before the next scene begins.

The first-wave matrix covers:

```text
text only
ordinary uploaded reference
single hero
professional set
General Photography
faithful/professional/creative reshoot where applicable
```

## 8. Phase P5 - Named Photographer Catalog And UI

Deliver:

```text
operator-reviewed catalog
frontend manual selector
explicit selection source
immutable profile binding
availability validation
profile technique compiler
profile-aware review
clear blocked states
```

Activation remains disabled until every P03 test passes.

## 9. Phase P6 - Professional Set And Continuation

Deliver:

```text
shot-list role director
meaningful shot differentiation
set-level color and profile coherence
reference and identity continuity
project continuation with explicit profile reconfirmation
best-set selection and delivery packaging
```

## 10. Phase P7 - Cross-Template Reuse

Only after Photography is stable, propose reusable capability adoption by other
templates. Cross-template use must occur through shared manifests and template
policies, never direct Scenario Pack imports.

Potential reusable candidates:

```text
photographic_capture_realism
camera_optics_direction
lighting_direction
nonhuman_subject_identity
```

Each shared candidate must prove value across at least three materially
different scenes and pass inactive-plugin zero-contribution tests.

## 11. Unit And Contract Tests

Required focused test families:

```text
test_photography_contracts.py
test_photography_scenario_pack.py
test_photography_activation_policy.py
test_photography_named_profile_binding.py
test_photography_profile_catalog.py
test_photography_reference_ownership.py
test_photography_scene_directors.py
test_photography_shot_list_direction.py
test_photography_review_retry.py
test_photography_cross_template_isolation.py
test_photography_hot_plug_removal.py
```

## 12. Manual Named-Profile Test Matrix

| Input state | Expected binding | Expected behavior |
| --- | --- | --- |
| No profile field | General | Generate normally |
| Null profile plus photographer name in text | General | Optional UI confirmation, no named activation |
| Valid ID plus `user_explicit_ui` | Exact pinned profile | Generate with that profile |
| Valid ID plus LLM/inferred source | None | Reject named activation |
| Unknown ID | None | Block clearly |
| Disabled or expired ID | None | Block clearly |
| Region-restricted ID | None | Block clearly |
| LLM proposes a different ID | Original pinned profile | Ignore and audit LLM change |
| Retry requests a different ID | Original pinned profile | Reject retry mutation |
| New project action with previous profile history only | General | Require new explicit confirmation |

## 13. Scene Test Matrix

For each first-wave scene, test:

```text
clear text-only brief
underspecified text-only brief
ordinary low-quality reference
strong identity/scene/object reference
conflicting style and reference truth
single output
multi-output set
General profile
one valid explicit named profile
profile incompatible with scene
LLM available
LLM unavailable fallback
```

## 14. Photography Review Dimensions

Universal dimensions:

```text
brief fidelity
composition and visual hierarchy
lighting plausibility and exposure integrity
perspective, depth and focus logic
color, tone and texture
natural moment and subject direction
retouch restraint
AI artifact severity
reference truth fidelity
professional direct-use readiness
```

Scene-specific dimensions:

```text
portrait: identity, face/body realism, expression, pose and skin finish
landscape: depth, atmosphere, foliage/water/sky realism and viewpoint
still life: material, edge, reflection, surface and set-light control
animal: species anatomy, specific identity, behavior, motion and fur/feather/scale
```

Named-profile technique fidelity is additive and never replaces these quality
gates.

## 15. Baseline Benchmark

Every major Photography release compares:

```text
A. raw GPT Image 2 request
B. V3 foundation-only request
C. V3 foundation + Photography General
D. V3 foundation + explicitly selected named profile, when applicable
```

Use blind pairwise review across both input modes and all first-wave scenes.

Initial target proposals:

```text
C preferred over A across the full matrix: >= 65%
no first-wave scene below: 55%
named-profile manual-selection violations: 0
silent profile substitutions: 0
cross-template leakage failures: 0
```

Targets should be recalibrated from recorded pilot results, not lowered to hide
objective regressions.

## 16. Required Regression Tests

Before each merge-ready milestone:

```text
Photography focused tests
Doc101/102 activation and isolation tests
Doc93 reference channel tests
Doc100 provider/renderer tests
General Template tests
E-Commerce tests
Project Mode tests
full V3 test suite
root test suite
compile checks
frontend syntax checks
git diff --check
```

## 17. Real-Output Acceptance

Real-output review must use stable fixtures and preserve:

```text
input prompt
reference roles
profile binding
capability plan
provider request summary
all generated attempts
review reports
selected best result
reviewer decision
```

Do not commit generated scratch images, contact sheets, caches or evaluation
directories unless they are intentionally accepted repository fixtures.

## 18. Stop Conditions

Stop the phase when:

```text
a named profile activates without explicit frontend selection
an unavailable profile silently falls back
LLM output changes a pinned profile
selected style overwrites identity or required truth
Photography logic leaks into General or E-Commerce
a module calls the provider directly
the implementation requires a missing shared contract
retry switches profiles or resets quality budgets
GPT Image 2 is no longer the sole renderer
objective-related regression tests fail
```

## 19. Merge Completion Criteria

Photography is merge-ready only when:

1. All P00 readiness gates pass.
2. Every mainline dependency has landed and the branch is rebased.
3. The named-profile catalog and UI satisfy explicit-selection governance.
4. Both input modes work for all first-wave scenes.
5. Review, retry and best-result selection are production-verified.
6. General and E-Commerce output contracts remain unchanged.
7. Full tests and real-output acceptance pass.
8. The branch has a clean diff with no temporary artifacts.
9. The final commit is pushed and the integration report is complete.

## 20. Milestone Report Format

Every milestone report states:

```text
phase and affected scope
foundation/Photography ownership classification
files changed
tests and results
real-output evidence when applicable
commit hash
push status
mainline requests or remaining dependencies
next safe step
```
