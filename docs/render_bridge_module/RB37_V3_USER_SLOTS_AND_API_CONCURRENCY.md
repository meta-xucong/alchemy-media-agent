# RB37: V3 User Slots and Bounded API Concurrency

Status: implementation contract, 2026-11-18.

## Goal

Keep the existing RenderBridge shared admission capacity (default 10) and its
safe pre-admission API fallback. For ordinary V3 Project Mode background jobs,
allow at most one submitted or running generation job per authenticated Alchemy
user. Different users may use the existing V3 worker pool concurrently. Direct
image API requests sharing the configured OpenAI-compatible credential have a
process-wide maximum concurrency of 5.

## Correction model

The current direct API provider uses one process-wide mutex, which serializes
all users. V3's background executor also defaults to one worker, so separate
users cannot overlap through the ordinary Project Mode frontend path. Once
those gates are relaxed, shared mutable provider retry diagnostics would mix
between concurrent requests unless kept request-local.

The owning layers are the V3 Project Mode background admission path and the
shared OpenAI-compatible image provider. Keep Bridge admission, V3 job
lifecycle, prompt/review/output/billing decisions authoritative as they are.
The smallest complete correction is one owner slot before V3 executor
submission, one shared five-request API gate, and request-local retry
diagnostics. Preserve the low-memory worker default; overlap is enabled only
when runtime capacity is configured above one.

## Existing authority that remains unchanged

- RB13 remains the route-ownership authority. Preserve all of its proven
  pre-admission API fallback cases: a capability preflight rejection, an
  unavailable Bridge, or an explicit capacity rejection, provided the request
  is proven not to have been admitted. An accepted or outcome-unknown Bridge
  unit stays Bridge-owned and must never trigger a second API generation.
- V3 planning, frozen prompts and references, image review, retries, output
  storage, billing and delivery remain unchanged.
- The API's existing requests-per-minute, outputs-per-minute, cooldown and
  retry rules remain in force. The new concurrency gate is an additional
  maximum-in-flight limit, not a rate-limit replacement.
- V2 stays isolated and is not changed by the shared V1/V3 Provider cap.

## Minimal implementation

### V3 owner slot

Use the authenticated `veyra_user_id` already placed in the server-owned V3
generation payload. Before submitting a Project Mode background job to the
existing `ThreadPoolExecutor`, reserve that owner's single slot. A second job
for the same owner remains in `planned` state in a small in-process pending
list and does not occupy a worker thread. Different owners can be submitted
independently and use the existing worker capacity.

When an owner job's worker actually exits, release its reservation and submit
the oldest pending job for that owner. Submission failure also releases the
reservation through the existing failure path. A watchdog timeout alone does
not release the owner slot while its worker may still be executing. Duplicate
submission of the same job remains idempotent.

The owner slot is process-local, matching the existing single-process V3
executor. This change does not add a distributed queue or change restart
recovery.

### API account cap

Replace the current global serial image-provider lock with one cross-event-loop
API semaphore capped at 5. Apply it to API image generation and editing for the
existing OpenAI-compatible provider. The user slot is enforced by V3 Project
Mode before submission; this shared provider cap does not add a separate
per-user policy to V1 or other callers. Keep the current local rate limiter and
upstream cooldown. RenderBridge calls do not acquire this API semaphore.

### Low-memory setting

Keep `V3_BACKGROUND_GENERATION_WORKERS` configurable and preserve its current
default of 1. The effective V3 user concurrency is bounded by the configured
worker count; a value greater than 1 is required to run different users at the
same time. Do not raise the repository default as part of this change. The
API provider cap remains 5 independently.

## Acceptance

1. Same-owner V3 jobs are serialized; a waiting same-owner job remains
   `planned` and does not occupy a worker thread.
2. Two different owners can overlap when the existing V3 worker setting is 2.
3. API calls from distinct owners can overlap but never exceed 5 active
   requests total. Generation and editing share this cap.
4. Each RB13-approved, proven pre-admission fallback selects the original API
   route exactly once. Accepted and outcome-unknown Bridge tasks never call
   API.
5. Existing prompt bytes, review decisions, generated-image presentation and
   billing semantics remain unchanged.
6. A controlled real-provider run confirms two distinct test owner IDs can
   overlap on the shared API provider and each receive one image. A separate
   real-executor test confirms V3 same-owner FIFO and cross-owner overlap.
