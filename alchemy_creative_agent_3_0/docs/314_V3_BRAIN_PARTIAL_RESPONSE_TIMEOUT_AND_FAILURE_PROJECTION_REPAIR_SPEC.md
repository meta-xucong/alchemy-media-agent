# Doc314 — V3 Brain Partial-Response Timeout and Failure Projection Repair

**Status:** contract-frozen development specification  
**Date:** 2026-09-16  
**Task:** `brain-timeout-repair-20260916`  
**Contract revision:** `v1.3.1-route-guard`  
**Implementation worktree:** `D:\AI\w\brain-partial-response-timeout`  
**Mainline/VPS:** out of scope for this task

## 1. Objective and phase boundary

The total objective is to repair the V3 foundation Brain transport and its
safe failure projection so that the last same-type Vertical magazine cover
failure on the VPS does not wait for an unnecessarily long remote stream and
does not report a pre-dispatch or generic cause after a response has already
started. The main controller will deploy and perform real VPS acceptance after
this branch is audited; this branch must not modify the VPS or push a remote
branch.

The current implementation phase is **contract-frozen code and focused
regression repair**. It is complete only when the focused tests pass, the
feature commit is local, and a freeze report is handed to the main controller.
Real deployment, provider generation, image-quality review, and final VPS
acceptance remain a later phase owned by the main controller.

## 2. Evidence and correction model

The governing authorities are Doc175, Doc288, Doc290, Doc296, and Doc299.
Their common contract is that Remote Brain is the only creative author, the
shared execution budget and stage ceiling are authoritative, and a missing or
incomplete Brain plan must block image-provider admission. Existing provider
retry and public receipt schemas are compatibility contracts.

The observed implementation mismatch is two-layered:

1. In `app/llm_brain/providers.py`, stream semantic progress is counted only
   when a non-empty reasoning or content block is received. The existing
   `_STREAM_PROGRESS_GRACE_SECONDS` is applied when the current deadline is
   reached and a new semantic count is noticed. There is no independent
   deadline measured from the last semantic block. After a first segment (or
   reasoning block) followed by a silent/stalled stream, a request can therefore
   remain alive until the per-call/stage boundary plus the existing bounded
   grace behavior.
2. The server already carries safe response/first-content facts through the
   timeout receipt, but the V3 desktop and mobile planning messages primarily
   branch on the coarse failure code. A dispatched Brain response that started
   can consequently be described using the same generic wording as a request
   that never reached the upstream.

The responsible layers are therefore:

- **Foundation transport:** add a semantic-idle watchdog in the existing
  worker/cancellation path. It is a shorter bound, never a new creative stage
  or fallback.
- **Failure projection/UI:** retain the existing closed schema and timeout
  class, but use already-safe response/first-content facts to distinguish
  “response incomplete/timeout” from pre-dispatch/auth/contract failures.
- **Core admission:** unchanged. No valid complete Brain plan means zero image
  Provider calls.

No prompt, JSON, or creative decision is permitted in the local repair.

## 3. Frozen transport contract

### 3.1 Configuration

Add one foundation transport setting:

`V3_LLM_BRAIN_STREAM_IDLE_TIMEOUT_SECONDS`

- default: `45.0` seconds;
- accepted operational range: finite `0.1` through `45.0` seconds;
- invalid, missing, NaN, infinite, or out-of-range values resolve to the safe
  bounded default/clamp behavior defined by the implementation;
- the setting is read by the transport watchdog, not exposed in a public
  receipt and not copied into prompt or provider payload metadata.

The existing `_STREAM_PROGRESS_GRACE_SECONDS` remains the compatibility grace
boundary. The new setting is an independent **idle** boundary, not another
retry or another stage budget.

### 3.2 Semantic progress authority

Only a non-empty reasoning block or a non-empty user-visible content block
counts as semantic progress. The collector must continue to update the
existing semantic count for these blocks and also record an in-memory
`last_semantic_progress_at` timestamp.

The following never count and never reset semantic idle:

- SSE comments, blank lines, transport chunks, and heartbeat data;
- role-only deltas or empty `content`/`reasoning` deltas;
- `[DONE]` itself;
- malformed/no-op transport fragments that do not produce a semantic block.

The timestamp and an internal watchdog-trigger marker may exist in the
in-memory transport trace used by the worker and focused tests. They must not
be added to the public transport-failure schema, public lifecycle metadata,
warnings, prompt, URL, request body, credentials, or persisted raw provider
details.

### 3.3 Deadline equation and lifecycle

Let:

- `D_call` be the existing per-call deadline;
- `D_stage` be the existing stage-aware ceiling after finalizer reserve;
- `D_shared` be the shared execution-budget deadline;
- `T_idle` be the bounded configured idle timeout;
- `t_last` be the timestamp of the most recent non-empty reasoning/content
  block.

Before any semantic block arrives, the existing hard/stage/shared deadlines
remain authoritative. Once semantic progress has been observed, the
effective deadline is:

`min(D_call/grace, D_stage, D_shared, t_last + T_idle)`

where “call/grace” means the current implementation’s hard deadline and its
existing progress-grace extension. A new semantic block refreshes `t_last`;
continuous semantic progress can therefore continue to the existing
hard/stage/shared ceiling. The idle deadline can shorten a deadline but can
never extend or borrow time from any budget or reserve.

When `t_last + T_idle` is reached without a new semantic block, the transport
must:

1. invoke the existing cancellation object so response/client close callbacks
   run;
2. join the worker within the existing bounded stop behavior and preserve the
   worker-stopped evidence;
3. raise the existing `BrainTransportTimeoutError` with the existing safe
   `read_timeout` compatibility phase and accurate response/first-content
   flags;
4. allow only the existing single bounded transient retry path, if the shared
   budget still permits it. A retry cannot reset or escape the shared/stage
   budget and no additional retry is introduced.

The watchdog applies to a stream after semantic progress. A stream that never
produces semantic content remains governed by the existing connect/TTFB/read
and stage/shared deadlines; the idle setting must not turn a no-content request
into a new public error class.

## 4. Frozen failure/projection contract

No new public error code or timeout phase is needed. Keep the existing
`timeout` remote error class, `read_timeout` phase, reason/outcome classes,
request acceptance values, transport-attempt fields, and closed allowlists.
The existing safe receipt must continue to preserve only aggregate facts:

- Brain request acceptance/dispatch;
- response started;
- first content observed;
- complete response and JSON parse flags;
- bounded attempts/recovery facts;
- safe stage and timeout class/phase/durations.

For a timeout after dispatch and response/first-content, public state must
continue to say that the **image Provider request was not started**, while
also retaining that the **remote Brain request did start**. The user-facing
desktop/mobile planning projection may say “响应未完成/超时” only from these
safe typed facts. It must not infer a provider outage, authentication failure,
contract failure, or image-quality failure from a generic warning.

Authentication, contract-invalid, unavailable, pre-dispatch, and legacy
failure projections retain their existing messages and fields. Unknown or
malformed public receipts fail closed and do not reveal untrusted values.

## 5. Scope and non-goals

### In scope

- `alchemy_creative_agent_3_0/app/llm_brain/providers.py`;
- `alchemy_creative_agent_3_0/app/llm_brain/contracts.py` only if a typed
  transport setting is proven necessary (expected: no change);
- the focused Brain, Doc175, and minimal-product-UX regression tests;
- `src_skeleton/app/static/app.js` and
  `src_skeleton/app/mobile_static/mobile.js` for the safe message distinction;
- `alchemy_creative_agent_3_0/app/scenario_runtime/runtime.py` and
  `alchemy_creative_agent_3_0/app/product_api/service.py` only if focused
  projection evidence proves an existing safe response/first-content fact is
  lost. The preferred correction is to preserve the existing schema without a
  server contract expansion;
- this development specification.

### Explicitly out of scope

- local creative, JSON, prompt, or deterministic image fallback;
- relaxing Remote Brain availability or the complete-plan admission gate;
- new/multiple/infinite retry, generation-mode/template changes, or image
  quality changes;
- V1, V2, MCP/VPS configuration, deployment, remote generation, or historical
  data;
- dependency/lockfile upgrades and unrelated refactoring;
- persistence of timestamps, raw stream data, prompt, URL, body, credentials,
  biometric data, or provider payloads.

## 6. Invariants and audit checks

The implementation is acceptable only if all of these remain true:

1. Every accepted semantic block refreshes idle; an ongoing semantic stream is
   not killed merely because the original call deadline was reached while
   bounded progress continues.
2. Transport noise, role-only events, empty deltas, comments, and `[DONE]` do
   not refresh idle.
3. Idle termination is no later than the effective shared/stage deadline and
   cannot consume the finalizer reserve or create a new stage.
4. Cancellation closes the active response/client and the worker stops; no
   detached transport thread is left as a successful continuation.
5. One existing transient retry remains the maximum; its total elapsed time is
   bounded by the same execution scope.
6. A Brain timeout or incomplete response yields no complete Brain plan and
   therefore zero image Provider calls.
7. Existing timeout/auth/contract/error receipts continue to validate under
   their old schema and closed allowlists.
8. Public output contains no prompt, URL, body, credential, raw response,
   internal path, timestamp, or retry-worker detail.
9. Desktop and mobile show the response-incomplete wording only for the safe
   started-response/first-content timeout facts; old pre-dispatch and auth/
   contract wording remains stable.

## 7. Focused regression matrix

The following tests are the minimum bounded evidence before the branch is
ready for audit:

| Area | Regression | Required evidence |
| --- | --- | --- |
| transport | first semantic block, then stall | terminates inside the configured idle window; does not cross call/stage/shared ceiling; cancellation and worker-stop evidence present |
| transport | continuous semantic chunks | no false idle timeout; complete response still parses |
| transport | role/heartbeat/comments/empty events after a semantic block | noise does not reset semantic idle; no-content and role-only events do not inflate semantic count |
| transport | retry | at most the existing one retry; total work remains within one shared execution scope |
| transport | trace/projection | internal timestamp/trigger is absent from safe public receipt |
| Brain/runtime | incomplete remote response | blocked outcome; no complete plan; image Provider call count is zero |
| projection | dispatched + response/first-content timeout | `remote_error_class=timeout`, safe flags retained, image-provider-started remains false, no private fields |
| compatibility | auth, contract-invalid, old timeout/transport receipts | old reason/outcome classes and closed allowlists still pass/fail as before |
| UI | desktop and mobile planning failure | response-incomplete copy for started response; existing auth/contract/pre-dispatch copy unchanged |

The implementation may add only the smallest test fixture needed to represent
these states. Tests must use local deterministic fakes and must not call a real
MCP/provider, create real jobs outside their fixture stores, or mutate VPS
state.

## 8. Real acceptance matrix for the main controller

This branch does not perform real acceptance. After independent audit and
deployment, the main controller should record append-only evidence for:

1. one guarded Vertical magazine cover request whose Brain emits a first
   reasoning/content segment and then stalls;
2. the observed termination duration and the safe public lifecycle receipt,
   confirming `remote_brain_request_started=true`,
   `provider_request_started=false`, and no prompt/URL/body/credential;
3. one request with continuing semantic chunks, confirming it is not killed
   by idle while it remains inside the configured/shared/stage ceilings;
4. one authentication/contract-invalid compatibility case;
5. image Provider request count equal to zero for every incomplete-Brain case;
6. no extra retry beyond the existing bounded recovery behavior.

The controller must compare the deployed commit with this branch’s local
commit and report deployment/real-validation status separately from this
phase’s test and freeze status.

## 9. Milestones and stop condition

1. **M0 — document freeze:** this file committed before code changes.
2. **M1 — transport:** implement the bounded semantic-idle watchdog; run the
   provider timeout regression file and inspect the diff.
3. **M2 — projection/UI:** add only the necessary safe started-response message
   projection; run focused Doc175/product tests and inspect the diff.
4. **M3 — integrated focused validation:** run the complete agreed focused
   test set, inspect status/diff for unrelated files and artifacts, and create
   one local feature commit.
5. **Ready-to-audit:** stop all writes and provide the main controller with
   commit SHA, changed files, every test command/result, known limitations,
   push status (`not pushed`), and the remaining real-acceptance dependency.

