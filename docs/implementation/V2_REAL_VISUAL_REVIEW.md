# V2 real visual review

## Correction model

V2 currently labels live provider metadata as `pass / 0.86`. Its Agent boundary
never calls a vision model. The reference-intent and file/contract guards are
already integrated; V3's real review is a separate implementation. The owning
layer is V2 output review, with a misleading frontend projection.

Preserve generation, bytes, billing, Bridge identity, 10-second healthy polling
and the 300-second upstream tolerance. Persist the original completed job and
generation success checkpoint first. Execute a single bounded asynchronous
vision request outside the queue transaction, then save the review on the
same job/outputs and refresh the checkpoint. Existing history images remain
available; no new review field is added to history cards. Pending review projects as `reviewing`
while the queued task is active, so existing pictures remain available and the
browser keeps polling. Recovery of a completed job/checkpoint continues only
pending review; terminal review results are reused without generation or debit.

The V2 gateway receives final pixels, declared reference images, the effective
prompt and a compact review contract. Follow V3's single-request/no transport
retry approach, compact JSON reply and reference thumbnails. Keep original
output pixels intact. Judge visible defects and explicit requirements, not
subjective art direction; do not introduce automatic image repair. Preserve
hard file/source-evidence guards. Required text fields may be certified only
when the source evidence is ready and the model explicitly verifies every
required field ID actually supplied with a value. Unknown IDs prove nothing.
Unavailable/invalid review is `needs_review` (or a preserved stricter guard),
never a fabricated pass, and never removes an image.

The public review schema gains optional timing/model evidence, preserving old
records. UI labels distinguish actual vision results, pending/unavailable
review and old metadata checks; percentages are removed. No V3 runtime import
or V1 storage dependency is added.

Review calls use the existing V2 unified gateway and review model setting,
supporting its OpenAI-compatible and Claude routes without an SDK execution
dependency. Each output has one request and no automatic retries; at most two
independent output reviews overlap. Full final generation prompts and original
output pixels are retained; only reference representations and reply verbosity
are bounded. The request timeout is 300 seconds by default, matching the
existing stability preference. Review elapsed time/model and field-verification
receipts are persisted, without storing source copy in those receipts.

## Acceptance

Offline tests must cover actual pixel/reference payloads, compact response
validation, unavailable/timeout behavior, conservative reference guards,
unchanged image bytes and visibility, terminal result reuse, active pending
projection, claim fencing and checkpoint recovery. HTTP must run outside the
queue lock. Frontend tests cover old and new review records without hiding
images. Independent audit precedes guarded deployment. A bounded real review
of an existing completed output verifies the configured route without creating
a new generation or replacing the existing result.

## Offline verification

198 distinct relevant backend cases passed, including 16 new real-review
cases, reference/intent contracts, Bridge caching, task fencing/checkpoints,
strict product isolation and 45 API cases. Desktop/mobile labels passed two
JavaScript tests; both bundles parse. The first queue run inherited this
machine's enabled Bridge control file; rerunning in a child process with an
isolated absent control file restored the intended offline provider fixtures.
No production control or queue guard changed to accommodate those tests.

Independent read-only implementation audit and scope review passed. The
candidate's real gateway review and production deployment remain required
before operational acceptance; offline tests do not prove upstream readiness.
