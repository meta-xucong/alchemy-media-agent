# Doc344 - Character continuity scope and first accepted project anchor

Status: implementation complete; independent design/code audits and deterministic
tests passed. Production visual acceptance remains pending user generation;
VPS deployment is outside this milestone.

## 1. Objective and correction model

V3 Foundation scope: preserve a character across requests using the existing
reference plan, final visual review, and single project-anchor binding service.
This is not a General Template deliverable definition or a new module.

The user approved three changes: a one-image character job may establish the
project anchor; character continuity also applies to illustrated/stylized
people; and the persistent anchor is the first formally accepted final image
in planned asset order, even if an earlier sibling did not pass review.

Observed mismatch: `_is_human_identity_suite_context()` combines character
classification, photo rendering, and multi-image count. The same predicate
also controls persistent-anchor candidacy. `_maybe_claim_continuity_anchor()`
then requires at least two assets, position zero, and only one stored original
record per asset. These batch transport conditions incorrectly constrain the
independent post-review project-binding decision.

Authority: the Brain's typed subject profile identifies character tasks;
Doc73/Doc287/Doc343 own temporary same-batch transport; the current canonical
final-delivery projection owns eligibility; Doc322's existing versioned binding
service owns the project mutation. Prompt words, output timestamps, candidate
scores, and provider return order are not selection authorities.

## 2. Minimal behavior

1. Add a small character-context predicate inside the existing Brain class.
   Reuse the current typed person/human/character/portrait entity set and
   E-Commerce exclusion. Do not require a rendering mode for continuity.
   Missing typed person evidence and product-only tasks remain ineligible.
2. The existing suite predicate becomes `character context AND count >= 2`.
   Use the character predicate without the count gate for Doc322 candidacy.
   Keep template opt-outs, non-mock requirements, reference precedence, and
   the frozen plan's active-anchor/manual-unbind rules.
3. Same-batch transport still uses only the original canonical position-zero
   Doc287 source. One-image jobs have no same-batch chain. No late review or
   persistent-anchor decision rewrites already submitted batch references.
4. At the existing post-review finalizer, obtain eligible output IDs from
   `_public_final_delivery_projection(result)`. Walk the original planned
   assets in plan order. Filter asset-pack entries by eligible output IDs
   before checking uniqueness for that asset (original/retry entries coexist).
   Zero matches means continue, multiple matches means stop promotion, and
   exactly one match means attempt that single binding. Normal finalization
   has already applied `_apply_reviewed_delivery_preference()` to select the
   authoritative per-asset winner. Do not repeat its scoring or selection.
   No history scan, newest-output selection, or extra review is introduced.
5. A selected, reviewed final retry/refinement may be the persistent anchor;
   superseded originals and unselected extra provider outputs cannot be chosen.
   This supersedes Doc322's original-only restriction for persistent binding,
   not Doc287's immutable temporary source. Canonical output identity, project
   ownership, file integrity, and review are still verified by the existing
   binding resolver. Do not duplicate those checks in a second gate.
6. Attempt at most one binding mutation. If it conflicts with a newer user
   action or the chosen output fails existing canonical checks, stop promotion.
   An existing anchor stays authoritative. Explicit unbind stays disabled.
   If no final output is eligible, create no anchor.
7. Illustration continuity must not force photography or skin-realism prompts.
   Human Realism activation and review rules are unchanged. Current prompts
   continue to own clothing, scene, mood, and rendering style under Doc93.
8. The normal and resumed-final-review completion paths must both invoke the
   existing anchor finalizer after winner selection and saving the result.
   Extract/reuse the existing callback wrapper inside Product API; preserve
   its warning-only failure behavior so anchor failure cannot erase delivery.

## 3. Compatibility and superseded rules

Doc344 supersedes only the count, photo-only, and position-zero/original-only
restrictions for persistent auto-binding in Doc322 sections 4 and 12.1. It
also widens the character style scope of the Doc73 suite predicate. Doc343's
frozen transport and separate advisory field remain unchanged. Historical
tests that reject a typed stylized character solely for rendering style must
be replaced with positive continuity tests; missing typed profiles still fail.

Existing bound/unbound projects, reference-plan schema, API/UI, E-Commerce
defaults, specialized template opt-outs, V1/V2/Lab, and Sub2API are unchanged.
No new retries, timeouts, thresholds, persistence fields, modules, migrations,
or provider calls are added. There is no background backfill of old jobs.

Production edits are bounded to `creative_core/central_brain.py`,
`project_mode/service.py`, and the existing finalizer call sites in
`product_api/service.py`. Existing tests and Doc322/Doc343 are updated alongside
this document. Expand that scope only if audit proves an owning-layer conflict.

## 4. Audit and deterministic acceptance

Before implementation, audit the rule ownership, selected-final mapping,
retry semantics, explicit override precedence, and style isolation above.
Write regressions that fail on the old implementation, then implement.

- One-image typed character: candidacy true, no temporary batch reference;
  reviewed output binds and appears in the next job's frozen plan.
- Photo, anime/stylized, and illustration profiles: character candidacy true;
  multi-image later requests keep one position-zero source with the existing
  receipt. Input profile/style stays unchanged; no photography gate is added.
- Product-only/missing character profile, mock, E-Commerce, or template opt-out:
  automatic chain/candidacy stays disabled as applicable.
- First failed, second passed: bind the second planned final output; if both
  pass, bind the first even when asset-pack/storage order is reversed.
- First selected retry passed while the original is retained: bind the final
  selected reviewed retry, never the superseded original or an extra output.
- All failed, missing canonical selected output, existing anchor, or stale
  completion after manual unbind: no unauthorized binding mutation.
- Normal and resumed final-review completion both call the same finalizer;
  repeated completion cannot replace a newer binding or explicit unbind.
- Existing Doc73 source immutability, Doc322 reference materialization,
  next-job reuse, version conflicts, and mode isolation remain passing.

Code audit follows implementation and precedes final test reporting. Tests
use existing local provider/review fixtures with real local image bytes and
explicit review receipts, with no external model calls. The unrelated
brand-export test with a live Brain fixture remains excluded (Doc343 section 8).

The user will assess image appearance during normal generation; extra real
image generation is not required for this milestone. Passing this milestone
means the requested code and deterministic behavior are ready for user trial,
not that new production visuals were reviewed. GitHub integration follows the
repository policy; VPS deployment is not part of this request.

## 5. Design audit record

Initial independent audit found two items, incorporated before implementation:
filter by canonical eligible IDs before asset uniqueness (append-only retry
history), and invoke the existing finalizer at the resumed-review completion
exit as well as normal completion. No new decision authority is introduced.
Independent re-audit: PASS. Ready for implementation and focused regressions.

## 6. Implementation and acceptance record (2026-10-23)

Implemented only the three approved production files:

- Brain: reuse typed character detection independently of rendering style;
  retain image-count gating for the temporary batch chain only.
- Project: filter append-only assets by canonical reviewed eligible output IDs,
  select in original plan order, then use the existing binding resolver/CAS.
- Product API: reuse the existing warning-only finalizer at both normal and
  resumed-review successful completion, after saving the reviewed result.

Independent read-only code audit: PASS. No blocking finding. Existing explicit
unbind, ownership, canonical output, file-integrity and version authorities
remain in the original resolver. No new module, review rule or state was added.

Regression-first record: the initial two-file suite against the old runtime
reported 19 failed / 29 passed, exposing the count/style/selection/resume gaps.
After implementation, three multi-output cases revealed a fixture issue:
`certify_output` rebuilt metadata from planning and removed the generation-only
candidacy flag. The final assembled fixture now restores and asserts that flag;
production logic was not changed to accommodate the fixture.

Final deterministic run: **130 passed, 1 deselected in 28.87 seconds** using
Python 3.12 and pytest. Executed suites:

- `test_v3_doc322_reference_plan.py`
- `test_v3_doc322_project_workflow.py`
- `test_v3_doc73_first_output_identity_anchor.py`
- `test_v3_doc322_continuity_binding.py`
- `test_v3_doc322_reference_isolation.py`
- `test_v3_doc322_reaudit.py`
- `test_v3_body_review_resume_package_predicate.py`
- `test_v3_review_resume_timeout_propagation.py`
- `test_v3_doc94_universal_visual_governance.py`
- `test_v3_photography_mainline_004.py::test_professional_set_t2i_executes_three_frozen_roles_without_generated_image_edit_chain`

The command used `-k 'not explicit_brand_export' -q --tb=short`; the excluded
brand-export fixture can invoke a real Brain and is unrelated to this change.
The E-Commerce continuity-exclusion test sets the already-built context's
scenario explicitly to isolate this predicate from remote E-Commerce planning.
The professional photography test separately covers its real template opt-out.

Coverage includes single-image and next-job binding; photo studio, anime city,
and illustrated forest character profiles; unchanged input rendering intent;
first-failed/second-passed; reversed pack order; retained original plus selected
retry; ambiguous and all-failed non-promotion; mock/missing-profile/product/
E-Commerce/template exclusions; unbind/CAS; resumed successful/pending/error
outcomes; and reference/mode isolation. `git diff --check` passed.

No external provider generation, new visual comparison, historical backfill,
or VPS deployment was performed. This passes the requested development and
offline-test phase only. Next acceptance is the user's normal generation and
inspection of same-person appearance after deployment; that remains unclaimed.

## 7. Integrated acceptance follow-up (2026-10-23)

The user requested completion of local real acceptance, including persistent
reuse, explicit unbind, and replacement. The offline milestone above is not
the final acceptance gate.

Independent read-only audit of `779ca0ca`: PASS for first eligible planned
winner selection, persistent frozen references, manual action/version
precedence, and normal/resumed completion. The focused suite was rerun with
external calls blocked: **130 passed, 1 deselected** (35.97 seconds).

HTTP fixture correction model: the foreign-owner read test expected 404 but
received `veyra_auth_misconfigured` (503). The owner-or-admin read policy must
resolve the foreign caller's account role; the fixture supplied a user ID but
no account provider. This is a missing test dependency, not a continuity or
authorization runtime defect. Supply an async ordinary-user account double
inside that test. Keep owner-or-admin reads, owner-only writes, and production
authentication errors unchanged. An isolated discriminating run with only
that double passed. Six local browser cases and the shared-shell static case
also passed; the prior browser launch errors came from the temporary runner's
subprocess guard, not application code.

The repository fixture correction was independently audited and rerun without
the temporary account injection: **1 passed, 7 deselected** (2.94 seconds).
Responses were `200, 200, 409, 400, 200, 404, 404`; no network guard denials.
No production runtime changed in this follow-up.

Real acceptance uses a new isolated persistent project/job/upload/output root,
the actual configured Brain, production image provider, and visual reviewer.
The observer retains canonical final-delivery review and exact physical input
receipts. Its gates require five final accepted outputs across initial pair,
next-job reuse, unbound generation, and active-source replacement; existing
bounded retry attempts are counted separately. Fresh processes read back the
binding ledger. The observer was independently audited before launch. Final
real acceptance remains pending until those gates complete.
