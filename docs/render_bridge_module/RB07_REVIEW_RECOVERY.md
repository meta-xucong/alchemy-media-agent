# RB07: native receipt and review continuation

## Correction model

A durable native candidate/result checkpoint proves registration, not completion
of its review. The old coordinator stopped at that checkpoint, and retry/status
returned it without resuming interrupted review. Ordinary Generate intentionally
holds Bridge plans, so it cannot repair this missing continuation.

Keep native registration identity, immutable receipt and accepted ACK unchanged.
Expose current review status separately; resume only the same committed native
checkpoint under the existing target lock, with review-only continuation and
current-target checks. Once committed, the exact receipt checkpoint is the review
authority. Native review writes two read-only request projections (mcp_review and
mcp_review_status); omit only those when comparing the frozen revision. Changed
generation inputs or project revisions still block continuation. Owner, project membership/activity,
cancellation, reference access and exact checkpoint binding remain checked. Never render, create another candidate, select or export.
Keep pending review in the existing bounded reconciler, honoring disabled/draining
lifecycle. Send accepted ACK once, independently of whether review passes.

On an authorized current-project task read, reopen an older registered mapping
whose persisted review outcome was finalizing/blocked and lacks a live review
projection. Do not scan unrelated native jobs. Terminal review failures are not
pending and must not loop. No frontend layout or default generation changes.

## Verification

Regression coverage must interrupt after the real native checkpoint save, then
restore review and prove same output/import/ACK identity, one review continuation,
no renderer/billing calls, and current UI status. Pending external review remains
pending without duplicate ACK; completed review stops reconciliation. Previously
registered mappings recover on owner/project read, while disabled mode stays off.
