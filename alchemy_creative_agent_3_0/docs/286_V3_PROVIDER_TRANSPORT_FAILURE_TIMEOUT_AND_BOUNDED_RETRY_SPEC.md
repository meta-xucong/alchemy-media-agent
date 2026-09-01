# Doc286 - V3 Provider Transport Failure, Timeout, And Bounded Retry

Status: **implemented shared-foundation repair specification**. The repair is
implemented at the existing Provider and Router transport boundaries and has
passed deterministic local regression and static checks. GitHub push and an
Alchemy-only VPS rollout are separately authorized by the current change
request; Sub2API remains outside the scope of this document.

## 1. Objective

Prevent a normal V3 image request from waiting through a full long timeout for
an error that the upstream has already returned, while preserving successful
slow generations and avoiding duplicate upstream work.

The repair must provide:

1. immediate handling for explicit terminal provider failures;
2. bounded retries for explicit transient failures;
3. a separate, conservative path for timeout or transport outcomes whose
   upstream acceptance is unknown;
4. one logical retry budget per output, even when the provider adapter and
   shared router are both involved;
5. truthful terminal records with no phantom output, duplicate delivery, or
   quality-review retry;
6. reusable behavior for General and Professional V3 without scenario rules.

The intended retry limit is **three total upstream attempts** (initial request
plus at most two retries), not three retries after the initial request. The
limit applies only where the failure class permits a retry.

## 2. Observed Failure And Current Risk

The recent VPS success had this timing:

- Brain planning and finalization: about three minutes;
- first reference-edit Provider request: `TimeoutError` after the configured
  long edit deadline;
- a fresh Provider request then succeeded;
- pixels were saved and review passed;
- the complete user-visible flow took about twenty-one minutes.

The VPS had `OPENAI_IMAGE_EDIT_REQUEST_TIMEOUT_SECONDS=900`. The direct V3
path also had a shared-router retry budget, while the OpenAI-compatible image
adapter has its own bounded transport loop. Therefore, changing either loop
to three attempts in isolation would create a larger and potentially
duplicated budget.

The observed `TimeoutError` contained no upstream terminal status. It was not
an explicit provider rejection, and it cannot safely be treated like one.

## 3. Authority And Scope

| Decision | Authority | This repair must not do |
| --- | --- | --- |
| Creative plan and prompt | Remote Central Brain and the frozen V3 plan | rewrite prompts, add scene rules, or ask Brain to classify HTTP transport |
| Provider outcome | Provider adapter's typed exception/response facts | infer transport state from prompt text, filenames, or regular expressions |
| Direct-path transport retry | one V3 transport owner | let the adapter and router independently multiply attempts |
| Gateway-managed failover | configured gateway contract | change Sub2API or race gateway failover with V3 retry |
| Pixels and output identity | existing Output Store/Product API boundary | retry after pixels are persisted or trust provider-supplied IDs |
| Visual quality review | existing shared review path | convert a transport retry into a quality rerender |
| Public status | existing safe terminal projection | expose private provider bodies, URLs, prompts, or account data |

This is shared V3 foundation behavior. It does not change General, E-Commerce,
Photography, Doc269/Doc281 source authority, V2, MCP handoff semantics, or
Sub2API configuration.

## 4. Correction Model

### 4.1 Normalize one typed attempt outcome

Reuse the existing Provider exception detail and private retry audit rather
than adding a second persisted state machine. Each fresh upstream request must
be normalized at the Provider boundary into these facts:

```text
phase: image_generation | image_edit | materialization
request_state: not_started | accepted_unknown | terminal_failed | pixels_received
retryability: never | immediate_transient | status_required | exhausted
failure_code: stable provider/runtime code or null
status_code: typed HTTP status or null
retry_after_seconds: bounded value or null
elapsed_ms: private timing fact
```

The classification uses structured exception fields, typed Provider errors,
HTTP status, retry headers, and whether pixels were received. It must not add
substring tables, prompt matching, filename matching, browser metadata
matching, or regular-expression logic. Creative interpretation remains with
Brain; transport classification remains a technical Provider concern.

### 4.2 Failure handling

| Outcome | Action | Fresh-request budget |
| --- | --- | --- |
| `pixels_received` | persist once, then continue to review | stop immediately |
| explicit non-retryable error | close the Job with its safe failure code | one request |
| explicit transient error | retry immediately or honor bounded `Retry-After` | up to three total |
| timeout/connection with request not accepted | retry after a short bounded delay | up to three total when the adapter has a typed non-acceptance fact |
| timeout/connection with acceptance unknown | close as `accepted_unknown` / `status_required` without a blind replay | one request |
| local admission/configuration error | close before Provider retry | zero or one, according to existing owner |

Explicit non-retryable examples include invalid parameters, unsupported
operation, missing/invalid credentials, capability mismatch, policy rejection,
and malformed reference input. A `400` response is not automatically
non-retryable when the Provider has already supplied a typed transient gateway
classification; the typed result remains authoritative.

Timeout handling is intentionally different. A client timeout proves only
that V3 stopped waiting. It does not prove that the gateway did not accept the
request. A retry is safe only when the existing gateway/provider contract
confirms non-acceptance or supplies an idempotent request/status mechanism.

### 4.3 One retry owner

The current code has an OpenAI image adapter loop and a shared router loop.
They must be reconciled before changing any numeric limit:

- For a direct OpenAI-compatible request, the Provider adapter owns fresh
  upstream transport attempts because it sees typed response and header facts.
  The shared router must not replay a terminal error already returned as
  `exhausted` by that adapter.
- If the adapter returns an unconsumed typed retryable outcome to the shared
  router, the router may consume the remaining logical budget once. The
  private audit must show one cumulative request count, not two independent
  counters.
- When gateway-managed failover is enabled, V3 sends one logical request and
  the gateway owns line selection, retry, and backoff. V3 must not add a
  competing transport loop.
- MCP explicit handoff/resume remains outside ordinary Provider transport
  retry. It must not receive a fabricated image retry index or a new job.

The implementation may use the existing methods in
`alchemy_creative_agent_3_0/app/generation_router/providers.py` and
`src_skeleton/app/providers/openai_image.py`; a new retry subsystem is not
required.

### 4.4 Split the time budget

The existing long edit timeout must not be the default wait for every failure.
The implementation uses three distinct concepts:

1. **attempt deadline**: the maximum time allowed for an ambiguous upstream
   operation;
2. **retry delay**: a short bounded delay for a known transient error, or the
   provider's bounded `Retry-After` value;
3. **logical Job deadline**: the outer background watchdog derived from the
   actual cumulative transport policy plus finalization margin.

An explicit terminal error bypasses the attempt deadline. A retryable `5xx`,
rate limit, or connection error must not sleep until the full edit timeout.
The background watchdog and the Provider retry audit must consume the same
policy so that a hidden second timeout cannot extend the Job beyond the
recorded budget.

The first implementation must reuse existing timeout settings and existing
defaults where possible. It must not introduce arbitrary scene- or provider-
specific constants. The VPS value of 900 seconds is a deployment setting to be
reviewed against measured route latency; changing that value is a separate
configuration action, not a reason to add another retry layer.

### 4.5 Stop after pixels

Once the Provider returns pixels, V3 must not issue another transport request
because review, saving, thumbnail creation, or public projection is slow.
Those stages use their existing bounded local recovery and terminal
projection. A persisted output remains append-only and is never duplicated by
a transport retry.

## 5. Private Audit And Public Projection

Keep the existing `provider_failure_retry` and
`reference_input_execution` projection shape compatible, while extending
private attempt entries only with the normalized facts needed to diagnose
latency:

- attempt start/end and elapsed time;
- request state and typed classification;
- status code and bounded retry-after when present;
- cumulative fresh upstream request count;
- whether the failure was explicit or acceptance-ambiguous;
- final terminal code and safe message.

The public result may expose only the existing safe retry summary and stable
user-facing failure family. It must not expose raw provider bodies, endpoint
URLs, credentials, request headers, full prompts, account selection, or private
IDs.

The UI may continue using the existing generating/retrying/failed states. A
new visible transport dashboard is out of scope; the essential requirement is
that a terminal failure is surfaced promptly instead of remaining in a long
opaque wait.

## 6. Minimal Implementation Surface

Expected production changes are limited to the existing transport boundaries:

1. `alchemy_creative_agent_3_0/app/generation_router/providers.py`
   - consume normalized outcome facts before sleeping or replaying;
   - reconcile adapter and router attempt counts;
   - preserve current gateway-managed and MCP branches;
   - keep output-plan, Job, and disclosure bindings unchanged.
2. `src_skeleton/app/providers/openai_image.py`
   - preserve typed status/header/acceptance facts for the shared router;
   - distinguish explicit terminal failure from timeout/acceptance-unknown;
   - retain existing capability-negotiation behavior as a separate bounded
     compatibility replay.
3. `src_skeleton/app/main.py`
   - retain the existing background watchdog and ensure it does not create a
     second transport retry loop; no new Doc286 loop is added here.
4. `src_skeleton/app/config.py` and `.env.example` only if an existing
   setting needs a documented bound; no new provider or gateway configuration
   is required for the first repair.

No changes are authorized in Brain creative planning, visual review rules,
Doc269/Doc281 source matching, professional deliverable maps, V2, Sub2API, or
the frontend unless a regression proves an existing public projection is
incorrect.

## 7. Required Regression Matrix

Use deterministic fake Provider responses and a monotonic test clock; tests
must not wait through real seconds.

### Provider outcome behavior

- explicit invalid request, credential, capability, policy, and reference
  failures finish without a timeout wait and issue one upstream request;
- explicit transient 408/429/5xx/connection outcomes retry within the bounded
  policy and stop on the first success;
- `Retry-After` is honored only within the existing configured cap;
- three means three total fresh upstream requests, never three retries per
  layer;
- repeated transient failure produces one final failed terminal record;
- timeout with confirmed non-acceptance follows the bounded retry policy;
- timeout with acceptance unknown does not blindly create an unbounded replay;
- gateway-managed failover sends one V3 request;
- MCP handoff/resume does not enter ordinary Provider retry.

### Persistence and projection

- pixels received on attempt two are persisted once;
- a save/review delay does not issue another Provider request;
- no output, Job, disclosure, or delivery record is fabricated after a
  terminal failure;
- retry metadata remains private-safe and cumulative;
- refresh and fresh-service reads return the same terminal truth;
- existing output-plan binding, review, continuation, and historical-source
  exclusion tests remain green.

### Latency and compatibility

- the background watchdog uses the same calculated budget as the retry audit;
- the former 900-second explicit-failure wait is impossible in the fake
  transport test;
- existing General, E-Commerce, Photography, Doc203/MCP, V2, and Sub2API
  isolation suites remain unchanged and passing;
- Python compile, JavaScript checks, and diff checks pass.

## 8. Acceptance And Rollout

The repair is locally acceptable only when all of the following hold:

1. the focused transport matrix passes from a fresh store;
2. the current V3 foundation and Professional adjacent suites pass;
3. the former timeout timeline is reproduced with deterministic responses and
   completes within the new cumulative policy;
4. one controlled real run confirms explicit failures return promptly and a
   transient failure can succeed without duplicate outputs;
5. private timing evidence contains no secrets or raw prompts;
6. no V2, Sub2API, gateway, review, Brain, or source-authority behavior has
   changed.

The local acceptance matrix below is the gate for the current implementation.
After it passes, the separately authorized Alchemy-only VPS preflight and
controlled deployment may proceed. A real image run is an acceptance check,
not a debugging loop; Sub2API must remain untouched.

## 9. Non-Goals And Stop Conditions

This repair must not:

- tune visual prompts, quality thresholds, human-realism guidance, or review
  scores to hide transport latency;
- add regular expressions, substring matching, filenames, browser selectors,
  or scenario-specific failure rules;
- add a local creative fallback when Brain or the Provider is unavailable;
- make all errors retryable merely because a retry sometimes succeeds;
- add a second gateway/client retry loop;
- change timeout values on VPS, Sub2API, or another service in the code phase;
- delete historical records or reinterpret failed outputs as current sources.

Stop and return to theory-first audit if the fix requires duplicate retry
counters, a new persisted lifecycle state, client metadata, a prompt rewrite,
or a blind retry after an acceptance-unknown timeout.

## 10. Implementation Receipt

For the completed implementation, record:

- base and feature commit, tracked status, and changed-file list;
- the correction model and owning transport boundary;
- deterministic attempt timeline and cumulative request counts;
- focused and adjacent test results;
- former timeout reproduction result;
- confirmation that no Provider, MCP, ImageGen, VPS, Sub2API, or external
  generation call occurred during local implementation;
- confirmation that no secrets, raw prompts, endpoints, account IDs, paths,
  or private request bodies entered the evidence.

The current receipt is the commit and test record accompanying this document;
temporary validation evidence remains outside the repository.

Local implementation receipt for this change:

- base checkout before the change: `2aa448bf71ec26cab51408677a448756ddbb367e`;
- focused Doc286, project-detail, V3 foundation, Professional, MCP, and
  provider-contract matrix: `572 passed`, 2 existing FastAPI deprecation
  warnings;
- Python compilation, desktop/H5 JavaScript syntax checks, and
  `git diff --check`: passed;
- no Provider, MCP, ImageGen, VPS, Sub2API, or external generation call was
  made during local implementation;
- no secret, raw prompt, endpoint, account identifier, or private request body
  was added to repository files or validation evidence;
- a broader historical suite remains independently blocked by the existing
  unmodified Doc193 `mcp_review_pending` versus
  `required_supplementary_view_failed` contract mismatch. It is kept outside
  this transport change and is not represented as a Doc286 failure.
