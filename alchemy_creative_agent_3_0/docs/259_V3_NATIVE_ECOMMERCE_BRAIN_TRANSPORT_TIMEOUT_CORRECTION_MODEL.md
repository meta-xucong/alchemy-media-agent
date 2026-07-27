# Doc259 — V3 Native E-Commerce Brain Transport Timeout Correction Model

Status: **transport diagnostics implemented; real-image gate remains blocked.**

Scope: Codex Local MCP / native planner, ScenarioRuntime Remote Brain transport diagnostics, and E-Commerce exact-count planning for the kidswear beach product set task.

Non-scope: shared Visual Capability, General Template behavior, Provider/MCP image rendering, route switching, prompt semantics, Formal Core, receipt/slot/activation, frontend, and real image generation.

Implementation note: this document started as the theory-first correction
model. It is now also the implementation closure record for the focused
transport-diagnostics milestone. The original blocked facts remain historical
evidence; the current active gate is the post-`99d3fa9` result in Section 1A.

## 1. Current blocked fact pattern

The user requested six Taobao/Xiaohongshu-style beach product photos using the existing child model and four blue skirted swimsuit product references. The task must use the V3 professional/native MCP planning path and preserve the E-Commerce exact-count contract.

The current validated state is blocked before any image operation:

- `865c2b3` fixed native planner timeout isolation and prevented orphan planning workers from creating late mutation.
- `4397c91` aligned the native planner outer deadline with the two-stage Brain budget.
- After `4397c91`, the reviewer-authorized N=1 planning-only probe returned in 122.351s:
  - `code=codex_native_imagegen_remote_creative_brain_required_for_template`
  - `remote_error_class=timeout`
  - logical budget remained `within_budget` with about 139858ms left
  - mutation remained zero for job, handoff/materialization, output, receipt, slot, and activation
- A tiny `/v1/chat/completions` health check returned HTTP 200 in about 2.66s, which proves only base route/model/credential reachability. It does not prove full planning availability.
- Offline fake-provider instrumentation showed both N=1 and N=6 take the same local two-stage path:

```text
plan -> provider_prompt_finalize
```

The fake-provider path completed locally without remote calls or image mutation, so the current evidence does not identify a local ScenarioRuntime contract-shape defect.

Evidence records:

- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-4397c91-summary.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/offline-brain-stage-payload-audit-20260727.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/final-blocked-decision-record-20260727.json`

## 1A. Implementation outcome and current gate

Two small mainline commits now separate the local program defects from the
remaining external Brain blocker:

| Commit | Scope | Outcome |
| --- | --- | --- |
| `dffc02b` | Doc259 correction model and old-document authority markers | Documented the two-stage Brain timeout/root-cause model and marked conflicting old timeout/fallback wording. |
| `99d3fa9` | Brain transport diagnostics in provider, adapter, ScenarioRuntime, Local MCP projection, and focused tests | Implemented safe stage/transport timeout observability without changing Brain creative authority, exact N, prompt semantics, route, Provider rendering, Core, receipt, slot, or activation. |

### Solved local program defects

- The native planner outer deadline is no longer the active blocker after
  `4397c91`; the child process is bounded and does not leave a late mutation
  worker.
- Brain transport timeout failures are no longer projected as an opaque
  `timeout` string only. They now carry public-safe stage/transport facts:
  stage, timeout phase, elapsed/cap, response-start flags, complete-response
  flag, and JSON-parse flags.
- The Local MCP blocked result can surface those safe facts while still
  suppressing endpoint URLs, credentials, raw prompts, provider bodies, file
  paths, internal stacks, and private IDs.
- Legacy generic provider-error projections remain stable: stage is emitted
  only when the new transport-diagnostic object exists.

### Verification completed for `99d3fa9`

- Focused regression: 68 passed, with only existing FastAPI deprecation
  warnings in Doc258 local-runtime discovery tests.
- `compileall` passed for the touched Brain provider, Brain adapter,
  ScenarioRuntime, and native planner files.
- `git diff --check` passed for the touched semantic files with Windows
  line-ending warnings only.
- Compatibility checks confirmed old generic provider-error exact assertions
  remain unchanged unless a typed transport diagnostic is present.

### Post-implementation N=1 planning-only probe

After `99d3fa9`, one corrected N=1 planning-only MCP probe was run with a
zero-mutation budget. It did not create any job, handoff/materialization,
output, project, visual asset, receipt, slot, or activation record.

Observed result:

```text
status=blocked
code=codex_native_imagegen_remote_creative_brain_required_for_template
remote_brain_stage=plan
transport_error_class=timeout
timeout_phase=unknown_transport_timeout
timeout_seconds=120.0
elapsed_ms=120014
response_started=false
first_content_observed=false
complete_response_observed=false
json_parse_started=false
json_parse_completed=false
execution_budget.state=within_budget
execution_budget.remaining_ms≈139788
mutation_delta=0
```

Current interpretation:

- The request reached the Local MCP planning facade and failed closed before
  any image operation.
- The local 300s outer planner did not kill the child.
- The shared logical Brain budget was not exhausted.
- The failure occurred during the first remote Brain `plan` stage.
- No response start, complete response, or JSON parse was observed before the
  120s per-call cap.

Follow-up diagnostic:

After the `99d3fa9` blocked probe, a no-image, no-job, remote-Brain-only
diagnostic reused the same N=1 plan-stage request shape and the same configured
provider/model/path family, but used Chat Completions streaming to observe
transport progress. It did not call Product API, MCP materialization, Provider
image rendering, slot, receipt, or activation.

Result:

```text
provider=deepseek
model=deepseek-v4-pro-260425
path=/v1/chat/completions
stage=plan
system_chars=20759
payload_chars=10075
max_tokens=8000
stream=true
http_status=200
first_event_ms=3670
first_content_ms=42939
done_ms=80819
content_chars=9843
json_parse_ok=true
mutation=none_remote_brain_only
```

Revised current active blocker after the streaming diagnostic:

```text
DeepSeek/OpenAI-compatible non-streaming Chat Completions integration waits for
the complete plan response opaquely and times out, while the same full plan
request can complete as a streamed JSON response inside the 120s cap.
```

This first proved a local Brain transport integration defect for the
DeepSeek/OpenAI-compatible chat path, not an external model outage. Commit
`58832e0` implemented the streaming collector and a same-provider minimal
stream smoke then returned a complete parseable JSON response in about 4.4s
with mutation delta 0.

However, a full N=1 MCP planning-only probe after `58832e0` still blocked at
the local MCP interaction boundary:

```text
code=codex_native_imagegen_planning_timeout
elapsed_ms=301507
mutation_delta=0
```

The earlier full plan-stage streaming diagnostic remains decisive evidence:
the same real provider/model, full plan payload, `system_chars=20759`,
`payload_chars=10075`, `max_tokens=8000`, and `stream=true` completed in
`80820ms`, with `http_status=200`, `first_content_ms=42939`,
`done_ms=80819`, and `json_parse_ok=true`.

Therefore the current `301507ms` MCP timeout must not be generalized as
"external Brain plan is unavailable." The active investigation shifts to the
post-plan boundary:

- whether `provider_prompt_finalize` is slow, repeated, or followed by an
  unapproved recovery/resign loop;
- whether local schema/contract validation or ScenarioRuntime capability
  preparation stalls after the plan response;
- whether the native MCP child, queue, or wrapper waits on the wrong object.

Real image generation remains prohibited until stage-trace evidence identifies
the exact boundary and a future N=1 planning-only probe returns schema-valid
two-stage Brain output with mutation delta 0.

Additional evidence:

- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-99d3fa9-corrected-summary.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-99d3fa9-startup-failure.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/brain-streaming-diagnostic-n1-plan-20260727.json`

## 2. Current authority rules

The following rules remain active and are not superseded by this incident:

1. Doc158/Doc175: real-image planning uses Remote Brain as the sole creative author and uses a finite two-stage shape:

   ```text
   remote Brain semantic plan
   -> frozen activation envelope / constraint ledger
   -> remote Brain provider_prompt_finalize
   -> exact Provider/MCP materialization
   ```

2. Doc175: `V3_LLM_BRAIN_TIMEOUT_SECONDS` is a per-remote-call cap; `V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS` is the logical preparation budget shared across stages.
3. E17: E-Commerce must not use local slot/camera/fallback recipes; the Brain must return complete natural-language intent for every requested output.
4. Doc133 specialized relay: `requested_image_count` is an exact-count contract. Six outputs are not silently replaceable by six unrelated one-image plans.
5. No local creative fallback, route/model switch, prompt deletion, context stripping, retry stack, detector-evasion wording, or Provider image operation may be used to mask a Brain planning failure.

## 3. Responsibility layers that must not be collapsed

The present failure was previously visible only as `remote_error_class=timeout`. That label is not enough for a safe repair. The correction model must distinguish:

| Layer | Question | Current evidence |
| --- | --- | --- |
| Native planner lifecycle | Did the local MCP outer deadline kill the child too early? | No after `4397c91`; N=1 returned at 122.351s under a 300s outer deadline. |
| Brain call stage | Did `plan` or `provider_prompt_finalize` time out? | Not currently exposed in the public Local MCP blocked projection. Adapter code records `remote_brain_stage`, but the safe outcome projection strips it. |
| Transport connect | Did the client fail to connect or acquire a route? | Tiny health request returned 200; full call still unknown. |
| TTFB / first token | Did the remote model start responding but not complete JSON? | Not observable with the current non-streaming SDK call. |
| Read / full response | Did a partial response arrive but exceed the cap before full JSON? | Not observable with the current non-streaming SDK call. |
| JSON parse / schema | Did complete text arrive but fail JSON/schema validation? | Current live probe reports timeout, not parse/schema; fake provider schema path passes. |
| Remote model / upstream queue | Did the model/gateway spend >120s before completing the first planning response? | No longer the leading hypothesis for the plan stage: the full plan payload streamed to valid JSON in 80.820s. Finalizer/upstream latency remains unproven. |

Stage-trace instrumentation is now the next bounded diagnostic. It must record
only safe component/stage/elapsed/terminal events and must not record URL,
credentials, prompt text, file paths, provider bodies, job IDs, handoff IDs, or
output IDs.

The next code work, if authorized, must improve this layer distinction before attempting another real probe.

## 4. Payload and budget measurements

Offline instrumentation measured the payload shape without network or image mutation:

| Count | Stage | System prompt | User payload | Return schema |
| ---: | --- | ---: | ---: | ---: |
| 1 | `plan` | ~20.8KB | ~10.1KB | ~2.9KB |
| 1 | `provider_prompt_finalize` | ~2.2KB | ~14.6KB | ~0.9KB |
| 6 | `plan` | ~20.8KB | ~10.0KB | ~2.9KB |
| 6 | `provider_prompt_finalize` | ~2.2KB | ~16.1KB | ~0.9KB |

Runtime defaults:

- provider: `deepseek`
- model: `deepseek-v4-pro-260425`
- per-call cap: 120s
- logical execution budget: 260s
- max output tokens: 8000

Interpretation:

- The `plan` system prompt is the heaviest fixed context.
- The finalizer payload grows with output count but is not the observed live failure yet.
- Payload length is a suspect to measure, not a proven root cause.
- There is no current authority to delete Human Realism, reference ownership, E-Commerce exact-count, or shared foundation context merely because the full planning stage is slow.

## 5. Rejected shortcuts

These attempts are explicitly rejected unless a future, reviewed authority changes the contract:

1. **Do not split N=6 into six hidden N=1 plans.** That would break set-level exact-count and coherent suite planning.
2. **Do not use local fallback wording.** E-Commerce specifically retired local recipe/fallback creative direction.
3. **Do not switch Provider/route/model as an implementation shortcut.** A provider capability task may be opened separately, but this correction model does not authorize it.
4. **Do not remove shared planning context by intuition.** Context can only be compacted if a focused simulation proves the removed section is redundant under existing Doc158/175/E17 authority.
5. **Do not expand timeout blindly.** A larger cap is only valid if trace evidence proves the complete remote decision regularly exceeds 120s while finite-budget invariants remain intact.
6. **Do not generate images from a blocked/fallback plan.** `fallback_used=true` is a fail-closed planning outcome, not success.

## 6. Minimal complete repair model

The smallest safe repair is not image generation; it is **transport observability and bounded classification**.

### Phase A — Stage-visible blocked outcome

Add safe, non-secret failure projection so a blocked Local MCP planning result can show:

- Brain stage: `plan` or `provider_prompt_finalize`
- timeout class: `connect_timeout`, `ttfb_timeout`, `read_timeout`, `complete_response_timeout`, `json_parse_error`, `schema_invalid`, or `unknown_transport_timeout`
- elapsed time
- configured per-call cap
- logical budget remaining
- whether any response bytes/tokens were observed

This must not expose endpoint URLs, API keys, raw prompts, raw provider payloads, file paths, hidden reasoning, or internal stack traces.

### Phase B — Transport instrumentation

Keep the existing complete JSON contract. Add instrumentation that can distinguish at least:

1. request constructed and client call entered;
2. remote response started / first byte or first content delta observed, when supported;
3. complete response received;
4. JSON parse completed;
5. schema validation completed.

Implementation options:

- For non-streaming SDK calls, record only `entered_call`, `completed_call`, and timeout elapsed. This is safe but may leave `unknown_transport_timeout`.
- For OpenAI-compatible chat completions, evaluate a streaming collector that preserves the same complete JSON contract while recording first-delta and read-completion timing. Streaming must return the same final JSON object and must fail closed if the collected text is incomplete or malformed.

### Phase C — Decision based on evidence

Only after Phase A/B evidence exists:

- If connect/TTFB never happens, classify as upstream route/model/gateway latency/unavailability.
- If first token arrives but full JSON exceeds cap, consider streaming-aware read budget or schema/output-size optimization.
- If complete text arrives but JSON/schema fails, fix schema or contract parsing with focused tests.
- If the full response is valid but >120s, evaluate a finite transport cap adjustment aligned with Doc175, not an unbounded timeout.

## 7.方案比较

| Option | Benefit | Risk | Current decision |
| --- | --- | --- | --- |
| A. Observability-only stage/failure projection | Minimal; makes next failure actionable; no creative contract change | Does not itself make Brain faster | Recommended first code step |
| B. Streaming JSON collector for chat completions | Distinguishes TTFB/read/full JSON; may avoid SDK complete-response opacity | Must preserve full JSON and schema; provider compatibility must be tested | Candidate second step after tests |
| C. Increase per-call cap beyond 120s | May let slow model complete | Hides queue/slowness and length defects; worsens user wait | Not allowed without new trace evidence |
| D. Payload/schema compaction | May reduce latency | Can delete required authority/context if done blindly | Only after proof of redundant sections |
| E. Split six outputs into serial one-image tasks | Easier short calls | Breaks Doc133 exact-count/set-level contract unless redesigned | Rejected for current task |
| F. Route/model fallback | Could bypass current provider latency | Changes authority/capability surface | Out of scope; separate capability task only |

Post-`58832e0` decision: Option B has already been implemented and verified as
the correct transport repair for the DeepSeek/OpenAI-compatible Chat
Completions path. The streaming collector preserves one remote request, collects
until `[DONE]`, and then parses/validates the same complete JSON object that the
non-streaming path expected.

The remaining failure is no longer "the full plan stage cannot respond." A
full plan-stage streaming diagnostic using the same real provider/model and
full plan payload returned valid JSON in 80.820s. Therefore the active repair
is now **stage-boundary instrumentation after semantic plan returns**:

- record native planner parent/child lifecycle without leaking private request
  material;
- record ScenarioRuntime semantic-plan return, slot-delta recovery, professional
  profile binding, active capability execution, frozen capability validation,
  constraint ledger/envelope construction, and canonical finalizer call/return;
- record Brain provider stream request/response/JSON-parse milestones;
- keep every trace line public-safe: no URL, key, prompt text, file path,
  provider body, job ID, handoff ID, output ID, stack trace, or raw exception
  text.

This instrumentation is diagnostic only. It must not alter Brain prompts,
requested N, max token budget, route/model selection, Product API, Provider
rendering, Formal Core, receipt/slot/activation, E-Commerce deliverable
contracts, or real-image generation gates.

## 8. Focused tests required before any real probe

The code milestone must include focused tests proving:

1. native planner child still cannot leak late job/handoff/output/receipt/slot/activation mutation after timeout;
2. overlap/reentry remains controlled;
3. `plan -> provider_prompt_finalize` and exact N are unchanged;
4. blocked projection includes safe stage and timeout classification;
5. no raw prompt, endpoint, key, path, provider payload, internal job/handoff/output IDs, stack trace, or hidden context leaks into public Local MCP failure output;
6. streaming/non-streaming paths both preserve complete JSON-only semantics and fail closed on incomplete JSON;
7. no local creative fallback appears when Remote Brain is required;
8. relevant Doc130/133/158/175/E17 behavior remains intact;
9. no hidden localhost/browser/service dependency such as port `8017` or `8772` is introduced into the native planner or Brain transport path;
10. Doc258/frontend/storage/shared Visual Capability files remain untouched.

Minimum validation commands after implementation should include:

```text
python -m pytest alchemy_creative_agent_3_0/tests/test_codex_native_imagegen_planner_timeout.py -q
python -m pytest tests/test_doc130_codex_native_prompt_parity.py tests/test_doc133_codex_native_specialized_relay.py alchemy_creative_agent_3_0/tests/test_v3_llm_brain_provider_timeout.py -q
python -m compileall alchemy_creative_agent_3_0/app/llm_brain/providers.py alchemy_creative_agent_3_0/app/llm_brain/adapter.py alchemy_creative_agent_3_0/app/scenario_runtime/runtime.py services/alchemy_codex_local_adapter/native_planner.py
git diff --check -- <touched files>
```

If new files are added, the command list must be narrowed to the actual touched layer.

## 9. Real-probe gate

A real N=1 planning-only probe may resume only after:

1. this correction model is reviewed;
2. code changes are implemented, tested, committed, and pushed;
3. the probe has an explicit mutation budget of zero for job/handoff/output/receipt/slot/activation;
4. the expected public diagnostic fields are defined before the call;
5. reviewer/user authorizes the single probe.

The probe succeeds only if both Brain stages complete and return schema-valid planning output. A stage-visible timeout still means blocked; it must not trigger generation.

## 10. Visual benchmark note for later product-photo acceptance

The user-provided reference folder `C:\Users\T14S\Desktop\case\图像\童装\假AI` is only a later visual benchmark, not proof of this run.

Current qualitative benchmark:

- product/clothing/beach-pool atmosphere: about 68/100
- person realism: about 16/40
- strengths: stable blue outfit, silhouette, print, beach/pool atmosphere, front/back coverage
- weaknesses: overly smooth skin and facial features, doll/illustration face, synthetic fingers/toes and local limb details

Because this V3 MCP task has produced no new product photo outputs, no score may be assigned to the current work. Later acceptance must compare matching views on:

1. person realism;
2. product fidelity;
3. beach light and atmosphere;
4. commercial composition;
5. set consistency.

The first visual target is to avoid plastic/doll face and hand/foot artifacts while preserving the product and beach-commerce feel.

## 11. Rollback and stop conditions

Rollback point:

- `4397c91` remains the current known-good local deadline repair.
- Any future transport-observability patch must be a small, separately revertible commit.

Immediate stop conditions:

- any real probe creates job/handoff/output/receipt/slot/activation;
- a code change touches Provider/MCP image rendering, Formal Core, receipt/slot/activation, shared Visual Capability, General Template, or frontend;
- a test proves exact N or two-stage Brain ownership changed;
- failure output leaks prompt/path/provider payload/credential/internal IDs;
- reviewer rejects the correction model.

Until a reviewed code fix and one successful planning-only probe exist, the six-image product set remains incomplete and blocked.

## 12. Old-document conflict index

This correction model does not delete historical documents. The following
markers identify only proven conflict risk for the present Brain
runtime/timeout/planning contract:

| Document | Marker | Current handling |
| --- | --- | --- |
| Doc101 — Extensible Capability Activation | Superseded for enforced real-image fallback wording | Deterministic Brain/activation fallback language remains historical compatibility text. Current real-image specialized and Native MCP planning must fail closed when Remote Brain is unavailable, timed out, malformed, or fallback. |
| Doc102 — Runtime Migration and Capability Isolation | Superseded for fallback implementation wording | Fallback activation migration details do not authorize Local MCP/E-Commerce creative fallback, prompt repair, route switch, or hidden serial splitting. |
| Doc104 — E-Commerce Runtime Governance Closure | Conflict-limited provider timeout section | Section 9's 600/660 second gateway-managed timeout applies to image Provider gateway calls, not Remote Brain planning transport. |
| Doc139 — Human Realism Independent Brain Re-signing | Already marked historical / forward invocation superseded by Doc158 | The old separate re-sign stage remains readable; current forward jobs use combined `provider_prompt_finalize`. |
| Docs133/158/175/E17 | Current authority | Exact N specialized relay, two-stage Brain, finite budget, and no local E-Commerce fallback remain authoritative. |

Out-of-scope note: the user-provided `假AI` product image examples are later
visual benchmark evidence only. They do not define shared Visual Capability,
General Template, Brain timeout, or E-Commerce planning rules.
