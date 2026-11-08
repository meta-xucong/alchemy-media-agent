# V3 review visibility and composition correction

## Objective and current phase

The product objective is usable V3 generation through Render Bridge with visible
results, including clearly labelled images requiring manual review. This phase
repairs the review-only projection and the generic composition retry decision.
It does not certify withheld images or replay an existing job.

## Incident evidence (2026-11-08)

At the incident, main, origin/main and the active VPS release were
`3744ed76658da3daf7776db292b1c8db9355306e`. Historical review optimizations were
uncommitted in the separate `v3-final-review-delivery-optimization` worktrees
based on `3a12bdff`; matching main did not deploy those changes.

Read-only audit run 42468098817 inspected project `project_c72a7decc9`, job
`job_b52c18f8e3`. The job generated four Render Bridge / codex-image outputs in
two attempts. Every inspection was verified and reported only
`composition_mismatch`. Each became `fail_retryable`. Vision provider elapsed
times were 29.071, 28.573, 27.465 and 28.474 seconds (113.583 seconds total).
The selected images' face-integrity attestations passed.

The job ran from 09:04:13.760 UTC to 09:24:21.531 UTC (1207.771 seconds):
47.573 seconds before generation, 477.365 seconds until finalizing, and
682.833 seconds in finalizing. Finalizing includes regeneration and review;
it is not an exclusive review timer. The persisted receipts do not separately
time every Brain/Bridge/queue operation, so those costs must not be invented.

The final review selected the original outputs `v3_output_0e57575ba703c3793b61`
and `v3_output_1997430473d1085dbf84`. They appear in `review_output_ids`, with
`delivery_preferred_output=true` and preference attempt 0. Attempt 1 was not
preferred. Formal `recommended_output_ids` was empty because of the review hold.

## Correction model before implementation

1. Expected: a review hold retains preview/download access to the selected
   review images, without formal delivery actions. Observed: no image cards.
2. Owning layers: shared visual review policy (Enhanced) and frontend read-only
   projection. Durable outputs and the canonical Job review remain authoritative.
3. Conflict: Project annotations derive superseded status from the formal
   delivery set, which is empty during a hold. Desktop also requires the final
   attempt number. Both overrule explicit canonical review IDs even when the
   review deliberately selects an earlier attempt. Mobile does not have that
   attempt/superseded exclusion, so it requires verification, not the same patch.
4. Authority: explicit current-Job `review_output_ids` controls review-only
   visibility; attempt/superseded annotations remain supporting fallback data.
   Current Job scope, usable media, explicit user rejection, requested-count
   bounds and the formal delivery gate remain intact. This narrows Doc341's
   attempt filtering; it does not promote review images to certified results.
5. The universal review prompt already separates generic composition from
   explicit delivery-role obligations. The retry table contradicts that rule.
   Restore the narrowly scoped Doc351 intent: composition-only findings become
   non-retryable warnings, including an overclaimed provider final-failure status.
   Explicit manual review, real hard failures, and `delivery_set_role_mismatch`
   retain their existing gates. No prompt recipes, thresholds or extra retries.
6. Regression first: reproduce the original-attempt review hold in the desktop
   production function, verify mobile still shows it, and exercise composition
   policy across portrait, product and landscape contexts plus true hard issues.

## Scope boundaries

Do not import the historical 17-file working-tree diff wholesale. Doc352's
short timeout proposal was superseded by Doc353. Timeout ownership, parallel
review scheduling, formal mixed-attempt delivery and role-targeted regeneration
are separate changes and are not needed to correct this incident. Preserve all
four existing outputs and their original review receipts; no new provider run
is needed to verify review-only visibility.

## Verification

- Before the fix, the desktop regression returned zero images and all 13 new
  review-policy cases failed. After the fix, 27 desktop/mobile tests and 55
  focused vision-policy/provider tests passed. The latter exercise the actual
  inspector, quality merger and Product API retry-signal consumer; composition
  advice produces `keep_with_warning` and no retry signal/decision.
- The broader legacy review test file was also attempted: 55 passed, 27 failed
  (including one temporary parameterized variant, subsequently removed). Its
  fake Brain stops before review at `remote_creative_brain_task_profile_invalid`.
  The unchanged HEAD version of the existing Doc118 warning test reproduces
  the same missing review metadata failure. Do not report the full suite green
  or weaken the production Brain contract to accommodate that old fixture.
- No live generation/review replay was run. Mocked scene cases verify policy
  scope, not actual image aesthetics. Deployment and existing-image visibility
  verification remain the next phase; the next user generation is acceptance
  of the changed policy on a new real run.
