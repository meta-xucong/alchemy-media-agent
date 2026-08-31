# Doc282 - V3 Professional Minimal Repair And Usability Audit Contract

Status: active repair proposal; does not replace Doc127 production gates.

## 1. Objective

Make the V3 Professional path usable with the smallest complete repair:

1. A user can select Professional E-Commerce or Photography.
2. The system can carry the user's request and approved references through one
   Brain-directed plan.
3. The plan is frozen before materialization.
4. A real provider output is either certified by shared pixel review and shown
   as final delivery, or is closed as blocked/withheld with a truthful reason.
5. Refresh, reopen, retry, and history cannot create a second authority or
   promote an old/generated/failed image into an original reference.

"Usable" here means the controlled current-build path is coherent and
diagnosable. It does not by itself enable the Doc127 E-Commerce Gate C/D or
Photography P10 production flags.

## 2. Authority And Boundaries

The repair follows the existing authority chain:

```text
user intent and module selection
  -> shared source/evidence facts
  -> remote Central Brain semantic plan
  -> frozen module plan
  -> provider materialization
  -> shared pixel review
  -> final delivery or durable withheld/blocked closure
```

Authority ownership is fixed:

| Decision | Authority | Not allowed |
| --- | --- | --- |
| User intent and module selection | Product API and selected module | Inferring a professional package from General text |
| Source meaning | Brain analysis over typed evidence | Filename, order, substring, regular-expression, or browser metadata matching |
| E-Commerce product truth and physical inputs | Doc263 and Doc269 | General, source matcher, or Provider rewriting the plan |
| Photography roles and set shape | Photography module | Shared runtime inventing photography deliverables |
| Prompt direction | Central Brain | Local prompt recipes or deterministic creative replacement |
| Output identity and count | server-issued Job/output bindings | Provider/client-supplied IDs or lexicographic ordering |
| Visual quality | shared `vision_model`/`hybrid` review | Metadata-only or local heuristic certification |
| Public status | persisted terminal receipt and exact output binding | Timeline guesses, stale history, or arbitrary metadata |

Hard facts such as file readiness, SHA, capacity, output identity, and plan
digests remain server-validated. The Brain may interpret semantic evidence and
choose safe actions; it cannot weaken those facts.

## 3. Current Audit Findings

The current mainline is `07a2180` and tracked-clean. Recent Professional core
regressions pass, including Doc281 source evidence, Doc269 planning, Doc270
General/E-Commerce activation, Provider output binding, ProductTruth,
Doc265 continuation, and Doc267 review closure.

The correctly-rooted full repository run produced `2693 passed, 80 failed`.
Those failures are not one repair list:

| Class | Evidence | Treatment |
| --- | --- | --- |
| Historical contract drift | old Doc109/136/139/162/166/178/181/182/184/245/246/248/252/66/77 assertions expect superseded fields, states, or prompt fragments | Reconcile each test to the current authority, or archive it; do not change runtime merely to satisfy stale wording |
| Fixture or persistence isolation | older Project Mode, Doc262, Doc268, and character-card resume failures | Reproduce in a fresh isolated store; repair runtime only if the current contract fails with a clean fixture |
| External Brain transport | SSL EOF and remote Brain failures | Fix configuration/transport observability and fail closed; never add a local creative fallback |
| Frontend contract drift | stale cache-bust/static version assertions and terminal projection assertions | Align the public contract and static version source once; do not add duplicate UI state |
| Professional acceptance gap | current-build E-Commerce Gate C/D and Photography P10 evidence is incomplete | Perform controlled real-pixel acceptance after local repair; historical passes do not count |

The historical Doc267 duplicate-review closure has deterministic coverage and
must not be reopened as a new code branch without a fresh reproduction.

## 4. Minimal Repair Model

### 4.1 One terminal outcome

Every professional attempt ends in exactly one persisted outcome:

| Outcome | Required evidence | User-visible result |
| --- | --- | --- |
| `ready` | real pixels, verified `vision_model`/`hybrid` pass or warning, exact winner binding | final delivery |
| `review_withheld` | pixels exist but review/finalization is incomplete or rejected | history/review-only, no delivery or automatic retry |
| `blocked` | Brain, admission, capacity, provider, or reference precondition fails before pixels | no candidate and one actionable reason |
| `failed` | an execution failure is terminal and safely classified | no candidate/delivery, retry only through a new explicit command |

No status may be inferred from an old timeline item, an empty candidate list,
or a client-provided label.

### 4.2 One frozen plan

Before the Provider call, persist one immutable plan containing only the facts
needed by the selected module:

- module and command identity;
- requested output count and output positions;
- approved reference roles, order, SHA, and source class;
- ProductTruth/Doc269 facts for E-Commerce, or Photography role facts;
- Brain plan digest and provider capability reservation;
- continuation/Job identity and source snapshot digest.

Central Brain and Provider only transport and revalidate this plan. A failed
retry, historical generated image, or review projection cannot rewrite it.

### 4.3 One diagnostic failure boundary

Every failure before pixels must expose a stable public family and retain the
private owner/fact record. At minimum:

```text
brain_unavailable
brain_invalid_plan
reference_not_ready
capacity_insufficient
provider_rejected
review_unavailable
review_failed
```

Provider-native detail may remain private. `provider_rejected` must not be
silently converted into a prompt rewrite or an automatic retry.

### 4.4 One shared review and delivery path

E-Commerce and Photography use the same pixel-review, bounded-retry,
finalization, and public projection path. They contribute only their typed
plan facts and deliverable roles. General remains scenario-neutral.

## 5. Minimal Acceptance Matrix

The following is the smallest gate for controlled usability:

| Gate | Required check | Pass condition |
| --- | --- | --- |
| A. Core contracts | Doc281, Doc269, Doc270, Doc263/265, Doc267, Provider binding | all focused suites pass from a fresh store |
| B. Failure closure | Brain unavailable/invalid, missing reference, capacity shortfall, provider rejection, review withholding | one terminal receipt, zero phantom Job/output/disclosure |
| C. E-Commerce smoke | current build, one authorized product case, one output, real Brain/provider/review | final output or truthful blocked/withheld closure; no historical replay |
| D. E-Commerce count | N=1, N=2, N=4, N=7 where capacity allows | exact count or structured pre-generation block; no truncation |
| E. Photography smoke | one hero and one professional-set role path with current Brain/provider/review | role plan, real pixel review, final/withheld projection are coherent |
| F. Refresh/reopen | refresh and fresh service reader for every terminal state | same persisted truth; no duplicate job or disclosure |
| G. Boundary isolation | General, E-Commerce, Photography, V2, and Sub2API | no scenario leakage or cross-product storage/config access |

Gates A/B/F/G are deterministic and must be green before any real run. Gates
C/D/E require a controlled deployment and restricted evidence package. Doc127
still governs production activation: E-Commerce requires Gate C plus Gate D,
and Photography requires the P10 matrix and human review.

## 6. Repair Order

1. Freeze the current mainline and create a clean test store/config snapshot.
2. Classify the 80 full-suite failures into the five classes in Section 3.
3. Add or repair only the smallest regression at the owning authority. Do not
   change shared behavior for a stale assertion or an unisolated fixture.
4. Make Gates A/B/F/G green and rerun the focused Professional matrix.
5. Run one controlled current-build E-Commerce smoke. Preserve payload-free
   provider diagnostics and the full terminal receipt.
6. Run exact-count E-Commerce checks and the minimal Photography smoke.
7. Update E19, P10/P11, E00/P00, and Doc127 evidence only from current runs.
8. Keep production flags closed until Doc127's higher acceptance is complete.

## 7. Explicit Non-Goals

This repair must not:

- add regular-expression, filename, ordering, keyword, or browser-selector
  matching for semantic source decisions;
- add kidswear, child, ancient, marketplace, or other scene-specific branches
  to shared runtime, General, Central Brain, or Provider;
- duplicate Brain guidance in E-Commerce, Photography, or Product API;
- loosen ProductTruth, Doc269, output-binding, review, or disclosure gates;
- replay historical jobs/images as current originals;
- modify V2, Sub2API, VPS, or deployment configuration as part of local repair.

## 8. Audit Receipt

Before implementation is accepted, record:

- current commit and clean-store/config fingerprint;
- focused suite results for Gates A/B/F/G;
- each full-suite failure's class and disposition;
- current-build E-Commerce and Photography evidence IDs, output bindings,
  review source, terminal state, and human decision;
- confirmation that no historical output entered source matching and no
  metadata-only result was certified.

The receipt must contain no secrets, raw provider bodies, private prompts,
source paths, or biometric vectors.
