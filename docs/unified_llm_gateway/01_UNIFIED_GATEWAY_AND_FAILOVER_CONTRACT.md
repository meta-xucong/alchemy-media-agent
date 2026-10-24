# Unified Gateway and Automatic Failover Contract

Status: proposed implementation contract; subject to independent design audit.

## 1. Product contract

Every text-model request in V1, V2, V3, and LAB has one ordered model list:

```text
primary: Claude Sonnet 5.5
fallback order: Kimi K3, then GPT-6.1-sol
```

Each request selects the first model that returns a response accepted by the
request's existing schema and product contract. The chosen model and any
failover reason are visible in safe operational metadata.

### Reasoning strength

Preserve the current per-stage/work-intensity reasoning intent. The router
passes the same semantic effort request to each candidate and the model
protocol adapter translates it to supported controls. V1 keeps its
`swift/balanced/studio/atelier` effort behavior; LAB keeps its current low
planning effort; V2 keeps the configured Claude effort (`low` in the current
local configuration); V3 keeps its existing provider-specific effort
configuration. A provider that does not support a control must omit that
parameter, not turn a capability mismatch into a user-requested model failure.

### Model request parameter contract

Keep one semantic effort choice in the product, then serialize it at the
model adapter boundary. Do not forward a generic `temperature` value to every
candidate: the providers have different sampling and reasoning contracts.

| Model | Wire control | Effort mapping | Sampling fields |
| --- | --- | --- | --- |
| Claude Sonnet 5.5 | Anthropic Messages `output_config.effort` | `low`, `medium`, `high`, `xhigh`, `max`; omit when the product has no explicit effort | Omit `temperature`, `top_p`, and `top_k` |
| Kimi K3 | Chat Completions `reasoning_effort` | `low→low`, `medium→high`, `high→high`, `xhigh→max`, `max→max` | Omit fixed `temperature`, `top_p`, `n`, `presence_penalty`, and `frequency_penalty` |
| GPT-6.1-sol | Chat Completions `reasoning_effort` or Responses `reasoning.effort` | Preserve `low`, `medium`, `high`, `xhigh`, and `max` | Omit `temperature`, `top_p`, and other sampling controls while reasoning is enabled |

Kimi's ordered effort mapping is monotonic: the product's `medium` level maps
to Kimi's next available strength (`high`), while `xhigh` and `max` saturate
at Kimi's strongest supported level (`max`). This is a protocol translation,
not a prompt/schema change. If Kimi rejects its mapped effort, fail over using
the same frozen request; do not retry with a sampling parameter or silently
rewrite the prompt.

These controls apply at all four product outlets (V1, V2, V3, LAB). V2's
Claude Code-owned primary invocation keeps its CLI-native effort option; the
adapter rules above govern its direct OpenAI-compatible backup calls. LAB
vision routing remains separate: only a vision request already routed to
Claude/Kimi/GPT uses the corresponding model adapter.

Provider references (reviewed 2026-10-21): [Claude Sonnet 5.5 migration
guide](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide),
[Kimi K3 API guide](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart),
[Kimi JSON mode](https://platform.kimi.ai/docs/guide/use-json-mode-feature-of-kimi-api),
[GPT-6 usage guide](https://developers.openai.com/api/docs/guides/latest-model).

## 2. Single text-gateway credential

- The canonical secret is `LLM_GATEWAY_API_KEY`, configured once per running
  deployment environment and reused for both selected models.
- The canonical gateway base is `LLM_GATEWAY_BASE_URL`; protocol adapters may
  derive the gateway's OpenAI-compatible and Anthropic-compatible endpoint
  paths from it.
- No model candidate owns an API key, token, or provider-specific secret.
- Existing provider-specific text credential fields are migration inputs only;
  they must not remain active routing authorities after migration.
- Protocol-specific headers are constructed in memory from the one canonical
  secret (`Authorization` / `x-api-key` as required). These derived request
  headers are never persisted or exposed in settings responses.
- Image-rendering credentials are outside this text-model contract. If the
  existing image renderer independently requires a credential, preserve that
  image-provider configuration and do not label it a text-model failover key.

### Model-to-protocol map

Use an explicit model catalog entry or a bounded classifier to map each
selected model to its compatible request adapter. At minimum, support the
current gateway routes for Claude Sonnet 5.5 over its Anthropic-compatible
messages endpoint and Kimi K3 / GPT-6.1-sol over its OpenAI-compatible endpoint. The
adapter is responsible for URL, headers, structured-output format, reasoning
controls, and omitting unsupported parameters. Never infer that a model
supports a protocol solely from its name without a tested catalog mapping.
V2's selector may offer only models with a tested route mapping: `claude-*`
uses the Anthropic-compatible adapter; `gpt-*`, `o1*`, `o3*`, `o4*`,
`deepseek-*`, `kimi-*`, and `doubao-*` use the gateway's OpenAI-compatible
adapter. An unknown model ID must fail with an attributable unsupported-route
error; it must not be sent speculatively through either protocol.

## 3. Configuration presentation

- Keep the current main-model and fallback-model selectors or equivalent
  fields. Set Claude Sonnet 5.5 as primary and use Kimi K3, then GPT-6.1-sol,
  as the ordered backup chain.
- In V1, both model-ID fields remain editable on desktop and mobile. Their
  selected IDs and corresponding adapter families are saved through the same
  unified-key settings API. The V2 fallback selector is a separate bounded
  model catalog, not the primary-model catalog.
- LAB text planning uses the same saved primary and backup model IDs as V1;
  LAB vision-provider/model settings remain independent.
- Remove backup API-key/token fields and per-model credential inputs from text
  settings screens and write APIs.
- Retain exactly one text-gateway API-key input in each product's runtime
  settings boundary. Shared deployment configuration may inject the same
  `LLM_GATEWAY_API_KEY` into each isolated backend process.
- A status response may expose whether the key is configured, never the secret
  value or a reversible representation.
- V2 remains an isolated backend product. It must not import V1 application
  modules to share the router; it implements the same contract in V2-native
  code.

## 4. Request lifecycle and time bounds

For a single logical text-planning request:

1. Freeze the complete request, schema, and product-owned context once.
2. Establish one monotonic logical deadline for the whole candidate sequence.
3. Attempt the primary once with a bounded connect timeout and bounded total
   response deadline. Do not let a stalled primary consume the fallback reserve.
4. On an eligible route failure, advance immediately to the fallback model with
   the same frozen request and the remaining logical budget.
5. Validate the result against the same schema/contract. A valid result returns
   with actual model, attempt count, and fallback reason.
6. If all configured candidates fail or the logical deadline expires, return a
   terminal, attributable failure. Do not report a generated image or a
   successful creative decision.

Initial timing defaults for implementation: connect timeout 8 seconds; V1/LAB
per-candidate hard wall-clock cap 90 seconds and logical request cap 210
seconds. The hard cap must wrap the full async provider call; HTTP client read
idle timeouts alone do not enforce it. Any same-candidate schema repair or
transport retry, if a product contract permits one, consumes the same
candidate deadline and cannot reset the timer or use the fallback's slice.
Divide any shorter remaining logical window among the candidates still
eligible so a slow primary cannot consume the fallback's slice. V2 keeps
its staged continuation/checkpoint deadlines and must bound the primary plus
fallback attempts within the existing stage/job deadline. No retry may reset a
logical deadline.

V3 keeps its existing shared Brain execution budget and existing downstream
handoff reservation. The code default is a 520-second logical execution
budget and a 220-second handoff/finalizer reserve. The checked-in local/VPS
deployment examples explicitly set 550 seconds while retaining the same
220-second reserve; tests must distinguish the code default from that deploy
override. Do not lower or silently
replace that reserve. For every remote Brain stage, allocate the available
stage window across the remaining model candidates: subtract all mandatory
downstream-stage reservations and existing transport grace first, then divide
the remaining stage window by the number of candidates still to try, capped by
the existing/configured per-call timeout. A primary timeout consumes only its
allocated slice; each remaining candidate receives its own reserved slice in route order. Do not give each model
the full transport timeout, and do not multiply the current same-model
transport retry by the fallback queue. Schema repair remains a separate
bounded same-model recovery only where the existing contract permits it, but
every repair call and same-candidate recovery attempt must consume that
candidate's allocated slice and the same monotonic stage deadline. A repair
cannot extend the primary slice, consume a later candidate's allocated slice, or reduce the
220-second downstream reserve. If
the remaining budget cannot fit the next candidate and required handoff
reserve, fail before dispatching that candidate with the existing budget
failure semantics. Settings may lower limits; they may not reset the shared
deadline or consume the required finalizer window.

These are failover controls, not promises that a provider always answers within
the cap. The current `300s` V3 per-call timeout must no longer consume the
entire opportunity to use Kimi K3 and GPT-6.1-sol.

## 5. Failure classification

### Advance to the next model

- DNS, connection, TLS, or socket failure.
- Connect/read/overall timeout, including an acceptance-unknown text request.
- HTTP 408, 425, 429, and retryable 5xx responses.
- Gateway/upstream overload, no available upstream account, or an explicit
  model-not-available/model-not-found response attributable to that candidate.
- A model-specific capability rejection only when the request adapter has
  exhausted its documented parameter normalization and the error is known to
  be candidate-specific.

LLM planning calls do not directly create an image or mutate a slot. Retrying
the same frozen planning request through another model is allowed, even when
the first response acceptance is unknown. Record that duplicate upstream work
may have occurred; do not replay image-generation calls as part of this router.

### Do not advance blindly

- A structured shared-credential rejection (including ordinary 401, or 403
  explicitly classified by the gateway as credential/account-wide): fail once
  with a credential/configuration error.
- A structured candidate-specific 403/model-access-denied or
  model-not-available response: advance to the next candidate. An unclassified
  403 is terminal; do not guess that it is either a shared-key or candidate
  failure.
- General malformed request/schema construction or protocol serialization
  errors: fix the adapter/request; do not disguise code defects as route outages.
- Safety refusal or policy block: do not use another model to evade it.
- V2 hard permission/policy boundaries: preserve existing authorization and
  fail-closed behavior.

### Structured response recovery

If the transport succeeds but JSON/schema output is invalid, use at most one
same-candidate constrained repair when the existing product contract permits
it. If that fails, try the next candidate with the unchanged logical request
and the same schema. All candidates' responses are validated identically.

## 6. Optional circuit breaker

Per-request bounded failover is the required resilience mechanism. A
per-model circuit breaker is an optional later optimization and is not required
for this implementation or its acceptance. If implemented later, maintain
per-model route health:

- Open a model circuit after 2 consecutive retryable transport/upstream
  failures within 60 seconds.
- Keep it open for 60 seconds; during that period requests start at the next
  candidate while retaining the configured candidate order.
- Permit one half-open probe after cooldown. A valid schema-shaped result
  closes the circuit; another retryable failure reopens it.
- Do not open circuits for 401/403, malformed local requests, policy refusals,
  or schema-invalid content alone.
- Keep state bounded and process-local initially; correctness must not depend
  on circuit state. Every request can still fail over based on its own result.

## 7. Product-specific invariants

- **V1:** keep the selected main model, then try Kimi K3 and GPT-6.1-sol in
  order (with any explicitly configured extra candidate between them). Fix the
  current path where `BACKUP_LLM_MODEL` is not used to build fallback
  candidates. Keep existing work-intensity levels and response provenance.
- **V2:** preserve Claude checkpoint compression/continuation whenever a
  checkpoint exists. A `claude_soft_timeout` is an internal continuation
  boundary: first run the bounded compressed/micro Claude stage, then use the
  ordered Kimi K3/GPT backup chain only if that continuation budget is exhausted.
  Other classified Claude route failures may advance through that chain with the same frozen stage request/schema,
  including the initial stage when no Claude checkpoint exists; this is the
  narrow exception required for the user's four-product automatic failover
  requirement. Kimi and GPT are model backups, never deterministic creative fallbacks.
  Preserve the configured semantic effort when a supported backup takes over, mapping it to
  the supported OpenAI-compatible `reasoning_effort` field and omitting it for
  models that do not support that control. The canonical ordered fallback
  list starts with Kimi K3 and GPT-6.1-sol; a legacy single-model fallback setting may be
  retained only after the configured ordered list so it cannot silently
  displace the default. Preserve refusal/permission boundaries, checkpoint
  state, and V2 strict backend isolation.
- **V3:** add Claude, Kimi K3, an optional configured additional candidate, and GPT candidates inside the remote Brain provider path, in that order.
  Every candidate must return the existing remote Brain contract. Preserve
  frozen request identity, execution budgets, sign-off ownership, and
  fail-closed behavior for required remote Brain decisions. No local
  deterministic prompt fallback is introduced. Eligible transport failure
  advances through Kimi K3 and then GPT after each candidate's allocated slice; it does not wait for a
  second full Claude transport attempt.
- **LAB:** text-only planning uses the same candidate order and unified key.
  Keep vision-specific routing outside this text-model change unless a LAB
  vision request also uses these text-only candidates; do not silently change
  image-model routing.

## 8. Safe provenance

Record only bounded non-secret fields: logical request ID, product/stage,
primary model, selected model, protocol adapter ID, attempt index, elapsed
time, failure class, fallback-used flag, and terminal outcome. Include the
bounded attempt summary on both success and terminal failure so a three-model
failure remains diagnosable. Do not record API keys, authorization headers,
full prompts, or raw upstream bodies. Redact provider errors before
user-facing responses.
