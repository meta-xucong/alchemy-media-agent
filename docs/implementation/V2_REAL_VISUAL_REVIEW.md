# V2 real visual review

## Correction model

V2 previously labelled live provider metadata as `pass / 0.86` without calling
a vision model. Real review now exists in V2. The follow-up correction aligns
model selection with the Brain, fixes hidden confirmation notices in simple mode
and history, and distinguishes explicit user requirements from automatic case inspiration.

Preserve generation, bytes, billing, Bridge identity, 10-second healthy polling
and the 300-second upstream tolerance. Persist the original completed job and
generation success checkpoint first. Execute bounded asynchronous
vision review outside the queue transaction, then save the review on the
same job/outputs and refresh the checkpoint. Existing history images remain
available. History pages attach the current canonical output review in one bounded,
read-only lookup for the visible page, matching both job and owner identity.
They do not create another authoritative verdict or rewrite historical images.
Pending review projects as `reviewing`
while the queued task is active, so existing pictures remain available and the
browser keeps polling. Recovery of a completed job/checkpoint continues only
pending review; terminal review results are reused without generation or debit.

The V2 gateway receives final pixels, declared reference images, the effective
prompt and a compact review contract. Follow V3's compact JSON reply and
reference thumbnails. Keep original
output pixels intact. Judge visible defects and explicit requirements, not
subjective art direction; do not introduce automatic image repair. The original
user request and explicit template lock remain acceptance authorities. The
full effective generation prompt is supporting context. Automatic retrieved
case names are not supplied visual references; missing those case images does
not make an otherwise valid result fail. Approximate angles and occupancy ratios
are visual guidance, not precise measured thresholds. Preserve
hard file/source-evidence guards. Required text fields may be certified only
when the source evidence is ready and the model explicitly verifies every
required field ID actually supplied with a value. Unknown IDs prove nothing.
Unavailable/invalid review is `needs_review` (or a preserved stricter guard),
never a fabricated pass, and never removes an image.

The public review schema gains optional timing/model evidence, preserving old
records. UI labels distinguish actual vision results, pending/unavailable
review and old metadata checks; percentages are removed. No V3 runtime import
or V1 storage dependency is added.

Review calls use the existing V2 unified gateway and configured Brain model queue,
supporting its OpenAI-compatible and Claude routes without an SDK execution
dependency. The configured multimodal primary handles pixels; the same ordered
fallback list and legacy tail used by planning supply later candidates. GPT
candidates are stably moved to the end. Persisted runtime configuration remains
authoritative over environment defaults. The old independent review-model field
is readable for compatibility but no longer selects the reviewer; the UI displays
the inherited primary read-only.

Each candidate is called at most once. Only invocation/response failures advance
the queue; an accepted needs_review verdict is final, and authorization or explicit
refusal stops rotation. At most two independent output reviews overlap. Full final generation prompts and original
output pixels are retained; only reference representations and reply verbosity
are bounded. One total 300-second deadline covers an output's complete review,
including fallback calls; the primary is not cut into shorter time slices.
Review elapsed time/model attempts and field-verification
receipts are persisted, without storing source copy in those receipts.

Simple and professional completion notices, result/history cards and image
lightboxes share the review status. Confirmation is a warning alongside the
image, with expandable existing review advice, never a hidden or rejected image.

## Acceptance

Offline tests must cover actual pixel/reference payloads, compact response
validation, unavailable/timeout behavior, conservative reference guards,
unchanged image bytes and visibility, terminal result reuse, active pending
projection, claim fencing and checkpoint recovery. HTTP must run outside the
queue lock. Frontend tests cover old and new review records without hiding
images. Independent audit precedes guarded deployment. A bounded real review
of an existing completed output verifies the configured route without creating
a new generation or replacing the existing result.

## Initial implementation verification (historical)

198 distinct relevant backend cases passed, including 16 new real-review
cases, reference/intent contracts, Bridge caching, task fencing/checkpoints,
strict product isolation and 45 API cases. Desktop/mobile labels passed two
JavaScript tests; both bundles parse. The first queue run inherited this
machine's enabled Bridge control file; rerunning in a child process with an
isolated absent control file restored the intended offline provider fixtures.
No production control or queue guard changed to accommodate those tests.

Independent read-only implementation audit and scope review passed. The
candidate's real gateway review and production deployment subsequently passed.
The first monitored frontend run used a real reviewer (62.290 seconds), with a
needs_review result. Follow-up routing/presentation changes require their own
focused regression, audit and guarded deployment evidence.
