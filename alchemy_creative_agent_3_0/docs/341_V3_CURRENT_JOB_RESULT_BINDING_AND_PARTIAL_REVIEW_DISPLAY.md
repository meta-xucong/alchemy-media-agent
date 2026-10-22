# Doc341 — V3 Current-Job Binding and Partial Review Display

## Goal and current phase

Make a V3 regeneration result belong visibly to the exact operation and Job
created by that click, then show generated images from the current Job up to
the requested count. A review-held image must be visible with a review badge;
it must not be represented as certified delivery. Retry-superseded images stay
out of the result board and remain in project history.

Current phase: local implementation, deterministic regression tests, and
independent read-only A1 audit. After those pass, commit and push `main`, then
use the guarded VPS candidate/activation workflow for the exact accepted SHA.
No real image/provider request is part of this phase.

## Baseline and evidence

- Main checkout: `D:\AI\Alchemy Media Agent System`, branch `main`.
- Baseline: `84f462d80f8419379a567742c69eeb1fe7984a2a`, equal to
  `origin/main` before edits.
- The VPS read-only release link resolves to
  `/opt/alchemy-media-agent-releases/doc276-277-84f462d80f84`, matching this
  baseline.
- Existing server source already serves a no-store shell with a content-hash
  version for `app.js`; current source also polls the exact planning-operation
  ID and fetches its returned Job ID (`recoverV3PlannedJob`). A page that was
  already open during deployment retains its old JavaScript until reloaded.
- The observed project requested two outputs. The completed Job had one
  automatically eligible output and one `manual_review` output from the
  latest retry attempt. Project history also retained earlier retry outputs.
- Browser image-fetch evidence after completion contained image IDs associated
  with an earlier Job and no fetches for the completed Job's two latest output
  IDs. This is consistent with a long-lived page retaining pre-update
  JavaScript/result state. The request evidence does not reveal the browser's
  actual DOM, so it is not treated as direct proof of which cards were shown.
- Independent source finding: the current result board reads only
  `final_delivery` outputs. `v3ReviewOnlyJobImageItems` returns no partial
  Job's review-held sibling unless the entire Job delivery is withheld. Thus a
  fresh page can be bound to the correct Job but still display only one image
  from a two-image request.

## Correction model

### Intended behavior

1. A planning response is followed only through its exact
   `operation_id`; the completed operation's exact `job_id` is fetched and
   becomes the current Job. Older project Jobs cannot satisfy this binding.
2. The current result board may show formal delivery images plus review-only
   images from that same Job, capped by the request's `requested_image_count`.
3. Every review-only image is visibly marked for review. It is not counted as
   formal delivery and gets no select-as-continuation or remove-from-project
   action from the formal delivery board.
4. Review outputs superseded by a later retry are not shown as current results.
   They remain available in existing history/review projections.
5. If the user requested two and the latest attempt contains one delivery and
   one manual-review image, show those two current-attempt images. If evidence
   cannot bind a review image to the current Job or current attempt, omit it.

### Authority and layer

- Exact `operation_id` then returned `job_id` is the current-generation
  identity authority. Project-wide latest-job guessing is not a substitute.
- The existing per-output `delivery_state`, `delivery_attempt_index`,
  `delivery_final_attempt_index`, and `retry_superseded` annotations identify
  delivery eligibility and retry lineage. A review output is bound to the
  final attempt only when its attempt index equals the final attempt index, or
  when its identity appears in that exact Job's
  `metadata.post_generation_review.review_output_ids`. Missing retry lineage
  without that exact-job review-package identity is insufficient evidence and
  the item is omitted. Review status remains authoritative for the review
  badge.
- Owning layer: V3 desktop result projection. Do not change provider behavior,
  retry behavior, review thresholds, or backend delivery certification.

### Minimal complete fix

- Keep the exact-operation recovery path already present.
- Extend the existing review-only output helper to include current-Job
  partial-delivery siblings, while excluding superseded or mismatched-attempt
  records.
- Render those siblings after the eligible delivery cards, with an explicit
  review-only badge and no formal-delivery actions. Bound the combined cards by
  the current Job's requested count.
- Add a regression containing an old Job output, a current Job's delivered
  image, a current-attempt review image, and superseded, mismatched-attempt,
  and missing-lineage review images. Assert that only the current Job's
  evidenced current-attempt review outputs appear. Also verify the bounded
  renderer integration contract and the absence of formal-delivery actions.

## Scope and constraints

### Allowed files

- `src_skeleton/app/static/app.js`, V3 result projection functions only.
- `tests/v3_doc341_current_job_result_projection.test.mjs`.
- This document.

### Non-goals

- No changes to API schema, Job persistence, review scoring, review thresholds,
  retry count, provider calls, image generation, project history deletion,
  V1/V2/Lab behavior, or General/specialized template semantics.
- No automatic reload mechanism for tabs already open during a deployment.
  Such tabs need a reload to receive the versioned current script.
- No real provider calls or exploratory production mutations.

## Risk classification and acceptance

- **D0:** the expected behavior follows the exact Job identity and existing
  delivery/review authority.
- **I2:** exact Job identity, retry attempt annotations, formal delivery, and
  frontend projection interact across recovery branches.
- **A1:** cross-layer Job binding and per-output review visibility require
  independent read-only review.
- One writer; one separate A1 auditor reviewing a frozen diff.

Acceptance requires:

1. The new Node VM/helper and result-board contract regressions fail before
   implementation and pass afterward.
2. Focused current-job/result projection tests, JavaScript syntax check, and
   `git diff --check` pass.
3. Independent A1 audit returns PASS for the exact frozen code/test/document
   revision.
4. The unique main checkout passes the required focused acceptance before
   commit/push.
5. The guarded VPS release is activated only at the accepted GitHub SHA and
   verified healthy. If the guard fails, stop before activation and report the
   exact gate.

## Expected side effects

- A current Job with a partial automatic delivery may display additional
  review-only images up to the originally requested image count.
- The user can inspect but cannot accidentally promote these review-only cards
  through the formal result actions.
- Old retry outputs remain stored and are not removed.

## Evidence ledger

Implementation, red/green results, frozen revision, independent audit receipt,
commit/push status, and VPS activation evidence are appended here after each
gate. No completion claim is made until the required phase and final release
gates have passed.

## Implementation and local verification

The desktop projection now reads review-only records for a partially delivered
current Job, requires the record to belong to a review projection/review ID,
and filters records marked superseded or bound to an earlier retry attempt.
Attempt lineage must positively match the final attempt; if either index is
missing, the exact Job's `post_generation_review.review_output_ids` must bind
the item. Otherwise the image is omitted.
Formal and review-only cards are capped together at the Job's requested count.
Review-only cards carry an explicit badge and have no formal-delivery actions.
The existing exact operation-ID recovery path was left unchanged.

The new regression was run against the baseline before the implementation:
both assertions failed (review list was empty; the renderer had no bounded
review-card path). After implementation:

- `node --check src_skeleton/app/static/app.js`: passed.
- `node --test tests/v3_doc341_current_job_result_projection.test.mjs tests/v3_frontend_terminal_contract.test.mjs`: **9 passed**.
- `python -m pytest -q tests/test_v3_frontend_generation_mode_contract.py alchemy_creative_agent_3_0/tests/test_v3_doc284_frontend_cache_contract.py`: **13 passed**.
- `python -m pytest -q alchemy_creative_agent_3_0/tests/test_v3_project_mode.py -k project_outputs_mark_retry_superseded_and_final_delivery_group`: **1 passed, 84 deselected**.
- `git diff --check`: passed.

The browser-only Playwright package is not installed in the available local
Python test environment. The new regression therefore executes the real
review projection helper in Node VM and checks the renderer source's bounded
integration contract; it does not simulate a browser DOM. No live browser or
provider was used.
