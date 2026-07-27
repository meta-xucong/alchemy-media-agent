# Doc259 — V3 Native E-Commerce Brain Transport Timeout Correction Model

Status: **live Professional identity/product binding passed; N=6 planning-only remains blocked at plan-stage contract rejection/transport trace; controlled real-image gate paused.**

Scope: Codex Local MCP / native planner, ScenarioRuntime Remote Brain transport diagnostics, and E-Commerce exact-count planning for the kidswear beach product set task.

Non-scope: shared Visual Capability, General Template behavior, Provider/MCP image rendering, route switching, prompt semantics, Formal Core, receipt/slot/activation, frontend, and real image generation.

Implementation note: this document started as the theory-first correction
model. It is now also the implementation closure record for the focused
transport-diagnostics, finite-budget, IPC result-return, Professional
identity/product binding, and product-truth selection milestones. The original
blocked facts remain historical evidence; the current active gate is the
fresh live N=6 Professional E-Commerce planning read-timeout in Section 13A.

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

Mainline commits now separate the original local program defects from
controlled product-image generation:

| Commit | Scope | Outcome |
| --- | --- | --- |
| `dffc02b` | Doc259 correction model and old-document authority markers | Documented the two-stage Brain timeout/root-cause model and marked conflicting old timeout/fallback wording. |
| `99d3fa9` | Brain transport diagnostics in provider, adapter, ScenarioRuntime, Local MCP projection, and focused tests | Implemented safe stage/transport timeout observability without changing Brain creative authority, exact N, prompt semantics, route, Provider rendering, Core, receipt, slot, or activation. |
| `cb4c787` | finite Brain budget repair | Historical N=1 budget repair: aligned the measured N=1 two-stage plan/finalizer latency with a finite 150s per-call cap, 320s shared logical budget, and 360s native outer deadline. This wording is superseded for the current live N=6 gate by Section 13A. |
| `8cd903c` | native planner IPC result return | Fixed the multiprocessing Queue feeder/join deadlock and proved N=1 planning-only through the real Local MCP entry point with mutation delta 0. |

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
- The post-`cb4c787` 360s timeout is now historical evidence. The trace showed
  the child had returned `planned`; the remaining defect was parent-side Queue
  result consumption order, fixed by `8cd903c`.

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
- **Historical/superseded by later evidence:** this was the active state after
  `99d3fa9`; it no longer describes the current gate after `cb4c787` and
  `8cd903c`.

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

After `c83c1d3`, a reviewer-authorized N=1 planning-only rerun with
`V3_BRAIN_STAGE_TRACE_FILE` set gave a more precise boundary. One invalid
runner instance was discarded append-only after a supervisor observed a script
materialization inconsistency; the replacement `rerun1` runner was hash-recorded
before launch and is the only accepted trace for this milestone.

Accepted `rerun1` result:

```text
status=blocked
code=codex_native_imagegen_remote_creative_brain_required_for_template
remote_brain_stage=plan
timeout_phase=read_timeout
timeout_seconds=120.0
elapsed_ms=120010
response_started=true
first_content_observed=true
complete_response_observed=false
json_parse_started=false
json_parse_completed=false
execution_budget.state=within_budget
execution_budget.remaining_ms≈139673
mutation_delta=0
```

Stage trace also showed that the request reached:

```text
native_planner_child -> ScenarioRuntime.plan_job -> capability_preparation
-> brain_adapter.semantic_plan_provider_call -> brain_provider.stream_response_started
-> repeated stream_first_content_observed
```

The trace did **not** reach plan `complete_response_observed`, JSON parse,
post-plan capability boundaries, or `provider_prompt_finalize`. Therefore the
current proven blocker at this milestone was the semantic plan stream read cap:
the remote model began returning content, but the complete JSON plan was not
received inside the 120s per-call transport cap.

The earlier full plan-stage streaming diagnostic remains decisive evidence:
the same real provider/model, full plan payload, `system_chars=20759`,
`payload_chars=10075`, `max_tokens=8000`, and `stream=true` completed in
`80820ms`, with `http_status=200`, `first_content_ms=42939`,
`done_ms=80819`, and `json_parse_ok=true`.

Therefore the current `301507ms` MCP timeout must not be generalized as
"external Brain plan is unavailable." The `c83c1d3` trace narrows the active
question further: distinguish whether the 120s read cap is too narrow for this
complete plan response versus whether the model/route is unstable even with a
small bounded extension.

The reviewer-authorized direct plan-payload diagnostic has now completed. It
used the same real provider/model/route and the same captured N=1 product
constraints, with no business MCP entry point and mutation budget 0. The only
diagnostic change was a bounded 150s read cap:

```text
report=direct-brain-plan-payload-diagnostic-150s-20260727.json
stage=plan
timeout_seconds=150.0
elapsed_ms=105050
system_chars=20759
payload_chars=10075
max_tokens=8000
content_chars=9250
status=completed
json_parse_ok=true
transport_trace.complete_response_observed=true
transport_trace.json_parse_completed=true
mutation_delta=0
```

This proves that, for the same full plan payload, the 120s read cap can be too
narrow under the current upstream latency, while a small bounded diagnostic
extension to 150s can complete the JSON response. This was still not a
production timeout change until `provider_prompt_finalize` was also measured.

The reviewer-authorized finalizer diagnostic has now completed. It used the
same real provider/model/route. To avoid a business MCP run, the diagnostic
first obtained one bounded full plan response with mutation budget 0, replayed
that plan into local ScenarioRuntime to capture the resulting
`provider_prompt_finalize` request, and then called only that finalizer request
with the same bounded 150s read cap:

```text
report=direct-brain-finalizer-payload-diagnostic-150s-20260727.json
plan_setup.elapsed_ms=71216
plan_setup.system_chars=20759
plan_setup.payload_chars=10075
plan_setup.content_chars=11335
plan_setup.json_parse_ok=true
captured_request.stage=provider_prompt_finalize
captured_request.requested_image_count=1
finalizer.timeout_seconds=150.0
finalizer.elapsed_ms=52858
finalizer.system_chars=2179
finalizer.payload_chars=16083
finalizer.content_chars=1863
finalizer.json_parse_ok=true
mutation_delta=0
```

The measured two-stage diagnostic total is about `124074ms`
(`71216ms + 52858ms`) for this N=1 request, and both stages returned complete
JSON under the bounded 150s diagnostic cap. This supports a minimal finite
budget repair for the historical N=1 gate, but this exact `150/320/360`
authority is now **superseded for live Professional N=6 planning** by the
Section 13A `210/520/540` repair. The superseded N=1 repair required all
timeout authorities to change together:

1. Raise the per-call Brain transport cap from 120s to 150s.
2. Set the shared logical Brain execution budget default to 320s. This remains
   a finite two-stage budget and does not authorize local creative fallback.
3. Set the native MCP outer planning deadline default to 360s, leaving explicit
   local process/orchestration margin beyond `2 * 150s`.
4. Remove the native planner's hidden 120s clamp for
   `brain_transport_timeout_seconds` and replace it with the same 150s
   authority.
5. Keep prompt semantics, `max_tokens`, route/model, exact N, two-stage
   `plan -> provider_prompt_finalize`, and strict fail-closed behavior
   unchanged.

This repair must not be a single environment override. Focused invariants must
prove that the outer deadline remains greater than `2 * per_call_cap + margin`,
that a late/blocked child still cannot create job, handoff/materialization,
output, receipt, slot, activation, retry, or delivery state, and that the
direct diagnostics are not reported as final MCP/product success.

The remaining risk after this evidence is no longer "finalizer is unmeasured";
it is whether the production schema/provider/native clamps and the final
planning-only MCP wrapper all follow the same finite budget contract without
waiting on the wrong object.

### IPC result-return correction

The first production-entry planning-only probe after the finite budget repair
still returned `codex_native_imagegen_planning_timeout`, but the stage trace
proved a different local defect:

```text
child.scenario_runtime_plan_job_returned elapsed_ms=201609 terminal_reason=planned
parent.process_timeout elapsed_ms=360500 terminal_reason=local_mcp_planning_timeout
mutation_delta=0
```

Root cause: `_plan_job_in_process` waited for `process.join(timeout=...)`
before reading the `multiprocessing.Queue`. For a large successful planning
payload, the child could enter Queue feeder flushing after `result_queue.put`
while the parent waited for process exit, producing a classic join/queue
deadlock. The fix is to read the queue first within the planning deadline,
then perform a bounded join/terminate cleanup.

Commit `8cd903c` implements this IPC repair and focused regressions:

- large successful process payload returns before the outer deadline;
- exited-without-queue remains fail-closed;
- timeout and overlap paths still terminate/reject without late mutation.

Verification:

```text
test_codex_native_imagegen_planner_timeout.py: 12 passed
Doc130/Doc133/Doc175/Brain timeout/Doc258 focused set: 77 passed
compileall: passed
git diff --check: passed
```

After `8cd903c`, the reviewer-authorized N=1 mutation=0 planning-only MCP
probe completed through the real entry point:

```text
report=mcp-planning-only-probe-n1-after-8cd903c-ipc-fix-summary.json
status=planned_for_codex_native_imagegen
outputs=1
elapsed_ms=172734
child.scenario_runtime_plan_job_returned elapsed_ms=170609 terminal_reason=planned
parent.process_queue_payload_received elapsed_ms=171672
parent.process_exited exitcode=0 elapsed_ms=171891
mutation_delta=0
```

This is the first schema-valid real-entry planning proof for the N=1 product
task after the Brain transport and IPC fixes. It is still not a product-image
result and does not authorize six-image generation by itself; the next step
requires reviewer approval for the controlled real product-image task.

The previous rule, "wait for a future N=1 planning-only probe," is now
historical/superseded by the post-`8cd903c` proof. Real image generation is
still not automatically authorized by this document: it requires a separate
controlled generation gate, fixed mutation budget, and reviewer/user approval.
Planning pass proves only that the Local MCP planning chain can return a
schema-valid one-output plan with mutation delta 0; it does not mean the
six-image product set has been generated or accepted.

Additional evidence:

- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-99d3fa9-corrected-summary.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-99d3fa9-startup-failure.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/brain-streaming-diagnostic-n1-plan-20260727.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-c83c1d3-stage-trace-invalid-runner.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-c83c1d3-stage-trace-rerun1-summary.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/direct-brain-plan-payload-diagnostic-150s-20260727.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/direct-brain-finalizer-payload-diagnostic-150s-20260727.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-cb4c787-finite-budget-summary.json`
- `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z/reports/mcp-planning-only-probe-n1-after-8cd903c-ipc-fix-summary.json`

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

- `8cd903c` is the current known-good planning-only repair after the finite
  budget and IPC result-return fixes.
- Any future real-generation patch must be a small, separately revertible
  commit or append-only validation step.

Immediate stop conditions:

- any real probe creates job/handoff/output/receipt/slot/activation;
- a code change touches Provider/MCP image rendering, Formal Core, receipt/slot/activation, shared Visual Capability, General Template, or frontend;
- a test proves exact N or two-stage Brain ownership changed;
- failure output leaks prompt/path/provider payload/credential/internal IDs;
- reviewer rejects the correction model.

The reviewed code fix and one successful planning-only probe now exist.

## 12. Controlled N=6 real materialization attempt — historical host output safety blocker

After `e3f3b56`, a reviewer-approved controlled N=6 real task was run through
the frozen specialized planning relay:

- evidence root:
  `.controlled-validation/kidswear-beach-product-set-mcp-20260726T172035Z`;
- planning summary:
  `reports/mcp-real-n6-product-set-plan-after-e3f3b56-summary.json`;
- requested output count: `6`;
- Remote Brain stages: `plan -> provider_prompt_finalize`;
- `remote_brain_call_count=2`;
- planning status: `planned_for_codex_native_imagegen`;
- business mutation during planning: `0` jobs, handoffs, V3 outputs,
  receipts, slots, or activations.

The first host materialization attempt accidentally produced one combined
six-panel preview image. That file is retained append-only as a
`host_combined_contact_sheet_invalid_for_exact_n6_delivery` record, but it does
not count as six output bindings or as product-set delivery.

Per Doc132/P13 review, the same frozen N=6 plan may be materialized by calling
the Codex built-in ImageGen host once per frozen output binding, as long as no
Brain re-planning, prompt editing, role reordering, or independent N=1 planning
occurs. Under that corrected host policy:

- `codex_native_output_6ddc39a02a_1` was materialized and saved under
  `native_imagegen_outputs/`;
- `codex_native_output_6ddc39a02a_2` was blocked by the host ImageGen output
  safety gate with `code=moderation_blocked`,
  `moderation_stage=output`, `category=other`;
- business mutation remained `0` for job, handoff, V3 output, receipt, slot,
  and activation;
- no retry, route switch, fallback, local prompt rewrite, or Brain re-plan was
  performed.

Current classification:

```text
host_materialization_blocked_before_exact_n6_completion
```

This is a host output safety gate result, not a Brain/MCP planning, slot,
receipt, or Formal Core defect. A plausible but unproven hypothesis is that the
second output's dynamic beach play / walking or skipping semantics triggered a
conservative output-stage safety decision. That hypothesis must not be reported
as proven.

The old N=6 plan and its partial host evidence are now historical append-only
evidence. If work continues, it must start a new, separately recorded N=6
planning attempt through Remote Brain. The new attempt may ask Remote Brain to
sign safer commercial-catalog constraints such as static posing, normal
kidswear catalog composition, beach setting, product fidelity, and no
running/playing/sitting-on-ground action semantics. It must not reuse the old
materialized output as a product-set member, edit the old canonical prompts
locally, or bypass the host safety system.

The six-image product set remains incomplete.

Historical/superseded gate note: this safety blocker is no longer the first
active blocker. Later audit found that the same attempt used the Specialized
Native ImageGen endpoint rather than the Professional Native ImageGen endpoint,
and the frozen outputs admitted only product-truth references while their
prompts described a generic girl. That means the run was not bound to the
server-owned Professional Character Card identity, so its partial materialized
evidence cannot be continued or certified as the requested product-on-model
task.

## 13. Professional product-model identity/product binding repair

### Observed mismatch

The controlled N=6 plan used `prepare_frozen_specialized_native_imagegen_plan`.
The request carried an identity-looking field, but the resulting output
contracts admitted only product-truth crops and the canonical prompts described
a generic child model rather than the selected Professional model. This is an
identity-binding mismatch, not a product prompt, Core, slot, receipt, or host
rendering defect.

Additional storage evidence showed that two current stores were not connected:

- the active Character Card asset lives in
  `.media_storage/v3_visual_asset_library/library/local_default/visual_assets.json`;
- the old Professional native resolver looked for
  `PersistentVisualAssetCatalog` people assets and active packs, but the
  current `.media_storage/v3_visual_assets/.../people_assets.json` is empty;
- `.codex-local-professional-catalog-path` may still point at a stale worktree,
  so runtime discovery must not silently fall back to a raw output path or the
  Specialized endpoint;
- the active library asset records
  `root_source_provenance.source_asset_id=v3_asset_054b1c4728614187`, while the
  current `.media_storage/v3_uploads` store may not contain that upload unless
  it has been reconciled from verified append-only evidence.

The verified root upload evidence found in controlled validation has:

```text
source_asset_id=v3_asset_054b1c4728614187
sha256=afe6ac2e7b116e0b1802cf44d63790dc51fe32a686796204476db70b0991b35d
role=face_reference
status=ready
consent_reference=user-authorized-local-reference-20260722-mcp-standard-modeling
```

That evidence may be used only as reconciliation evidence. It must not make
`.controlled-validation/` an implicit production resolver root.

### Current authority

Professional product-on-model planning must use the Professional Native
ImageGen entry point and server-owned binding evidence:

```text
project_id + people_asset_id + professional_identity_view_ids
```

The selected identity asset must be resolved through an explicit
ProjectVisualAssetBinding snapshot. The asset's original modeling
`provenance.project_id` is historical modeling context; it is not a substitute
for joining the asset to an arbitrary product project.

Reference inputs are now separated by authority:

1. server-owned Professional identity chain:
   immutable root portrait (`portrait_identity`) plus one or more approved
   Character Card winners (`selected_identity_reference`);
2. user/product-owned product truth inputs (`product_truth`).

Both classes must be admitted by the provider materialization contract. Missing
ProjectVisualAssetBinding, missing verified root upload manifest, missing
active Character Card winner, missing product truth, or a materialization plan
that drops either class must fail closed before image generation.

### Product-model reference pool and final renderer-capacity authority

Superseded historical note: the immediately previous repair model treated all
`product_truth` inputs as hard provider inputs and therefore described
`root + winner + up to three product_truth images` as the active capacity
boundary. That model is now superseded for Professional E-Commerce
product-on-model planning.

Current authority: product references form a frozen product-truth pool. The
Remote Brain must choose, per frozen output, the product truth asset IDs that
are relevant to that output role. The native relay and Provider materializer
must then admit only:

```text
identity: immutable root portrait + active standard-front Character Card winner
product truth: selected_product_truth_asset_ids for that one output
```

The complete product pool remains audit evidence, not provider-facing
`uploaded_assets` or `reference_assets`. Each output must record:

1. `product_truth_pool_asset_ids` and `product_truth_pool_source_sha256`;
2. `selected_product_truth_asset_ids` from frozen structured
   generation/deliverable metadata;
3. `omitted_product_truth` with `not_selected_for_this_frozen_deliverable`;
4. final source hashes and admitted source IDs; and
5. derivative IDs separately from source IDs.

Selection is fail-closed:

- missing, empty, duplicate, or unknown selected product IDs are blocked;
- selected product IDs must be a subset of the frozen product pool;
- product selection must come from structured frozen metadata, never prompt
  text, filenames, list order, shared adaptive selection, or content dedupe;
- unselected product truth may not leak into final provider refs.

The Provider limit is enforced after canonical materialization, because the
shared materializer may expand one source into multiple renderer inputs. The
current identity strategy expands the immutable root and active winner into
two identity derivatives each. Therefore:

```text
root source + winner source + one selected product source
=> 2 root derivatives + 2 winner derivatives + 1 product_truth_crop
=> 5 final renderer image inputs
```

Selecting two product truth images for a single output would materialize more
than five renderer inputs under the current route and must be blocked before
any ImageGen operation. The selected product truth uses a focused
`product_truth_crop`; the product full frame is suppressed for the provider in
this product-model seam so background/composition from the product photo does
not become an unintended scene reference.

The user's four swimsuit references are all valid product-pool evidence:
front full, front print/detail, rear straps, and another front full view. They
should not be content-deduped or globally rejected merely because there are
four images. Different N=6 outputs may select different single product truth
assets from that pool while keeping the same identity chain.

Rejected alternatives for this milestone:

- Do not drop the immutable root silently. That would require a separate
  Doc95/Professional product-model authority explaining why a generated winner
  alone can replace root truth for this seam.
- Do not silently trim product images through Doc97/adaptive reference
  selection. Product selection belongs to the Professional E-Commerce frozen
  deliverable/plan contract, not the shared Visual Capability selector.
- Do not raise `max_provider_reference_images` without an explicit Provider
  capability negotiation proving the current route can accept more final
  renderer inputs.
- Do not infer selected product truth from prompt text, filename, upload order,
  image content, or local ecommerce heuristics.

If a future task needs two or more product truth images in the same rendered
output, it must first prove either a higher final renderer-input capability or
an approved product-model identity strategy with fewer identity derivatives.
Until then, the active safe behavior is per-output selection from the full
product pool, with one selected product truth admitted alongside the immutable
root and active winner.

### Runtime-source boundary

Production Professional binding resolution must not scan
`.controlled-validation/`, glob historical runs, or guess IDs from raw
`v3_output.../original.png` paths. Correct source options are:

1. reconcile the verified root upload into the current server-owned
   `.media_storage/v3_uploads/<source_asset_id>/` store with an append-only
   manifest recording source evidence path, target path, SHA-256, asset.json
   fields, and timestamp; or
2. inject an explicit trusted source-root resolver/config for a controlled
   validation run, with the descriptor recording that source root.

The default repository runtime reads the current server-owned media root only.
Tests must simulate a complete runtime store under a temporary `.media_storage`
tree and must not require the production resolver to search evidence roots.

### Real-runtime pre-generation gate

The focused tests prove the contract with a complete temporary runtime store.
They do not prove the current live `.media_storage` store is ready for product
generation. Before any new real MCP planning or ImageGen materialization, the
live runtime must show both of these server-owned facts:

1. `ProjectVisualAssetBinding` exists for the target consuming product project,
   the selected `visual_asset_id`, the selected active version, asset type
   `people`, status `active`, and owner scope. The historical/modeling
   `asset.provenance.project_id` is not accepted as this binding.
2. `.media_storage/v3_uploads/v3_asset_054b1c4728614187/original.png` and
   `asset.json` exist and match the verified root evidence:
   `source_asset_id=v3_asset_054b1c4728614187`,
   `sha256=afe6ac2e7b116e0b1802cf44d63790dc51fe32a686796204476db70b0991b35d`,
   `status=ready`, `role=face_reference`, and non-empty consent reference.

Historical live-store audit indicated both live preconditions were missing:
the existing `project_bindings` frozen job bindings are empty, and the current
`.media_storage/v3_uploads/v3_asset_054b1c4728614187` directory is absent.
This statement is **superseded for the current run** by
`.controlled-validation/live-bind-20260727T075231Z/reports/live-binding-readiness-report.json`
and
`.controlled-validation/live-bind-20260727T075231Z/reports/resolver-root-path-proof.json`:
the verified root upload is now present in current `.media_storage`, the
consumer project `project_6c885b14a3` was created through
`V3ProjectModeService`, the active Character Card asset is bound through
`PersistentProjectVisualAssetBindingService`, and the Professional resolver
returns current `.media_storage/v3_uploads/.../original.png` rather than
following historical `asset.json.file_path` evidence.

This gate must not be bypassed by:

- using the modeling/preparation project id as the consuming project binding;
- passing raw `v3_output.../original.png` paths as identity inputs;
- making the resolver scan `.controlled-validation/`;
- using the Specialized Native ImageGen endpoint as a fallback;
- omitting product-truth inputs or treating product images as identity-chain
  views.

### Implemented repair boundary

The focused repair keeps Brain, route/model, exact N, prompt semantics, Core,
receipt, slot, activation, and host rendering unchanged. It changes only the
Professional binding/projection seam:

- VisualAssetLibrary-backed Professional resolver reads the current library
  root, requires an active ProjectVisualAssetBinding, freezes a binding
  snapshot, validates the immutable root upload manifest, and validates the
  active Character Card winner output manifest.
- Professional Native ImageGen product-model planning accepts server-owned
  identity references separately from product-truth references.
- The provider materialization strategy
  `visual_asset_library_product_model_v1` preserves server-owned identity
  references and product truth references while allowing internal provider
  evidence derivatives; parity is checked by admitted source IDs, not by raw
  derivative path count.
- Runtime discovery ignores stale local catalog pointers when the repo-root
  VisualAssetLibrary exists, and records the selection through the existing
  launcher boundary rather than by scanning validation evidence.

Focused regression must prove:

- product-truth references do not infer a serial Professional identity stage;
- VisualAssetLibrary resolver requires a verified root upload manifest;
- VisualAssetLibrary resolver requires an active ProjectVisualAssetBinding;
- stable view selectors resolve to root + approved Character Card winner;
- Professional E-Commerce plan includes identity sources and product-truth
  pool evidence while admitting only the selected product truth per output;
- Professional E-Commerce product-model keeps the identity chain and the
  selected product truth through adaptive/provider selection, blocks when the
  final materialized renderer refs exceed the five-image Provider capacity,
  and separately records source IDs and derivative IDs;
- N=6 Professional E-Commerce can use a four-image product pool by selecting
  different product truth assets per output without passing the whole pool to
  the Provider;
- missing root, missing winner, missing binding, missing identity winner, or
  missing product truth fails closed with no business mutation.

## 13A. Live N=6 plan-stage follow-up timeout correction

After live binding readiness passed, the reviewer authorized one fresh
Professional Native N=6 frozen-planning run using:

- consumer project `project_6c885b14a3`;
- active people asset
  `visual_asset_0000_professional_card_rebuild_fresh_20260726`;
- active version `version_professional_card_rebuild_fresh_20260726`;
- four user-provided product-truth images as the product pool; and
- no ImageGen, MCP materialization, job, candidate, output, receipt, slot, or
  activation mutation.

Evidence:

- `.controlled-validation/live-n6-20260727T081000Z/reports/pre-call-checkpoint.json`
- `.controlled-validation/live-n6-20260727T081000Z/reports/brain-stage-trace.jsonl`
- `.controlled-validation/live-n6-20260727T081000Z/reports/fresh-professional-n6-planning-report.json`

Observed result:

- status `blocked`;
- elapsed `263264ms`;
- mutation delta zero for job, candidate, handoff, output, formal receipt,
  slot, and activation;
- no ImageGen/materialization invocation;
- product truth selection, selected/unselected product leakage checks,
  final-reference cap, root identity, and active front winner identity all
  passed;
- exact N and two-stage completion did not pass because the remote Brain plan
  stage failed before producing the complete frozen plan.
- Any `fallback_used=true` flag in this blocked result is outcome bookkeeping
  for a fail-closed planning path. It is not a local creative fallback, not a
  prompt repair, and not authorization to materialize images.

Stage evidence narrows the responsible layer:

- The first plan call returned in about `112015ms`.
- The adapter validated schema but recorded
  `remote_contract_rejected_count=1`, then made a second Remote Brain call
  within the same plan stage. This is recorded as observed trace behavior, not
  as a newly introduced recovery capability.
- The second plan-stage stream dispatched at about `113172ms`, response started at
  about `115515ms`, and first content was observed around `235702ms`.
- The second plan-stage call then hit the `150s` per-call read cap before
  complete JSON was observed; the failure was fail-closed and did not mutate
  business state.

This is not a binding, product-pool, Provider capacity, runner, queue, slot, or
ImageGen problem. It is a finite remote Brain transport-budget mismatch for a
valid N=6 planning shape where the observed plan stage may require an
additional Brain-owned follow-up call after a contract rejection. This section
does not add local recovery behavior or deterministic creative fallback.

Historical finite-budget repair implemented by `ce925e8`:

1. Keep Doc133 exact N, Doc158/175 two-stage Brain ownership, E17 complete
   output-intent requirements, and the Professional product-model reference
   contract unchanged.
2. Do not delete context, shrink product/identity constraints, rewrite prompt
   semantics, split N=6 into six independent N=1 Brain plans, switch route or
   model, or add retry stacking.
3. Increase the bounded per-call Brain transport cap from `150s` to `210s`.
   The number is finite and evidence-based: the failed N=6 follow-up call had
   first content at roughly `122s` after dispatch but needed more than the old
   150s read window to complete JSON.
4. Increase the shared logical Brain preparation budget from `320s` to `520s`
   so the initial plan call, one observed Brain-owned plan-stage follow-up call
   after contract rejection, and one final `provider_prompt_finalize` call can
   complete without turning the budget into an infinite wait.
5. Increase the native MCP outer planning deadline from `360s` to `540s`,
   keeping a hard process deadline and process termination semantics. The
   invariant remains finite: the outer deadline must exceed
   `2 * per_call + 120s` and must not be used to hide queue/join or late
   mutation defects.

This finite-budget repair was necessary to test the live N=6 shape, but the
subsequent `live-n6-20260727T082732Z` probe proved it is not sufficient by
itself. The correct behavior after that result is another fail-closed planning
block with sharper contract evidence, not further timeout expansion or real
image generation.

## 13B. Live N=6 post-`ce925e8` probe: product pool passed, first rejection field was not preserved

Evidence:

- `.controlled-validation/live-n6-20260727T082732Z/reports/pre-call-checkpoint.json`
- `.controlled-validation/live-n6-20260727T082732Z/reports/brain-stage-trace.jsonl`
- `.controlled-validation/live-n6-20260727T082732Z/reports/fresh-professional-n6-planning-report.json`

Observed facts:

- The runner entered the real Professional native planner; this was not a
  wrapper/startup failure.
- Business mutation remained zero: no job, candidate, handoff, output, formal
  receipt, slot, or activation was created.
- The Professional identity/product pool contract passed at the planning
  admission layer: each output had selected product-truth IDs from the frozen
  pool, final provider-facing references stayed within the current cap, root
  and active front-winner identity references were server-owned, and unselected
  product-truth inputs did not leak into provider-facing refs.
- The first plan-stage Remote Brain response completed JSON at about
  `107.7s`, then the adapter recorded `remote_contract_rejected_count=1`.
- The trace/report did not preserve the exact rejected section name; the safe
  blocked outcome later showed `remote_contract_rejected_sections=[]` because
  the second plan-stage call timed out and overwrote the earlier diagnostic
  context.
- The second plan-stage call dispatched at about `108.3s`, observed an HTTP
  response at about `271.0s`, observed no first content, produced no complete
  JSON, and failed closed at the `210s` read cap. The overall child returned a
  blocked value through the native planner queue; the queue/join IPC repair
  remained effective.

Correction model:

1. Do not raise the timeout again. The `210/520/540` budget was a finite live
   hypothesis and did not complete the N=6 frozen plan.
2. Do not generate images, split the six-image request into six independent
   Brain plans, remove product/identity context, switch model/route, or use a
   local creative fallback.
3. The immediate owning-layer fix is diagnostic and contract-boundary focused:
   record safe `remote_contract_rejected_sections` in the stage trace and
   preserve the initial rejected sections in the safe runtime/native blocked
   outcome even if a later same-stage Remote Brain follow-up times out.
4. The compact plan schema does not require `canonical_provider_prompts`; those
   are owned by the later `provider_prompt_finalize` stage. Deterministic
   regression must therefore prove:
   - a valid compact N=6 plan without `canonical_provider_prompts` is accepted
     without a second plan call;
   - if `canonical_provider_prompts` is present in the plan response but has
     invalid shape/cardinality, it remains rejected and safely traced; and
   - `provider_prompt_finalize` still strictly requires a complete canonical
     prompt set.
5. Only after the exact rejected section is known from a safe trace may a
   further minimal code fix be designed. If the only rejected section is
   `canonical_provider_prompts`, the fix is to keep plan-stage absence valid
   and reject only malformed present prompt drafts while leaving finalizer
   validation unchanged.

Current gate:

- Planning-only: blocked until the contract rejection can be safely identified
  and the deterministic regression suite passes.
- Real-image generation: still prohibited. A passing unit test or improved
  trace is not a six-image product delivery.

## 13C. Post-`d93e307` live N=6 trace result: rejected section is `image_set_plan`

Evidence:

- `.controlled-validation/n6-trace-20260727T085000Z/reports/fresh-professional-n6-planning-report.json`
- `.controlled-validation/n6-trace-20260727T085000Z/reports/brain-stage-trace.jsonl`
- `.controlled-validation/n6-trace-20260727T085000Z/reports/planning-only-rejection-summary.json`

Startup note:

- The first wrapper attempt in this evidence root was invalid and is recorded
  as `planner_invoked=false`: the outer launcher split the workspace path and
  Python attempted to open `D:\AI\Alchemy`.
- The corrected PowerShell native invocation passed the Python executable and
  runner script as separate arguments, entered the runner, and returned exit
  code 0. This second invocation is the only valid planning-only evidence in
  this root.

Observed facts from the valid planning-only run:

- The real Professional native planner was invoked with the live consuming
  project, active Character Card identity binding, and the four user product
  truth images.
- No ImageGen, MCP materialization, job, candidate, output, formal receipt,
  slot, or activation mutation occurred.
- The planning result remained blocked:
  `codex_native_imagegen_remote_creative_brain_image_set_plan_invalid`.
- Safe trace now records the exact first rejected section:
  `remote_contract_rejected_sections=["image_set_plan"]`.
- The deterministic `Doc259` focused regression proved the compact plan stage
  does not require finalizer-only `canonical_provider_prompts`; missing
  canonical prompts are accepted in the plan stage and remain strictly required
  only in `provider_prompt_finalize`.

Root-cause update:

- `canonical_provider_prompts` absence is not the live N=6 blocker.
- The current owning layer is the Remote Brain compact `image_set_plan`
  contract. The observed rejection means the returned first-stage plan failed
  exact-count/schema validation before a valid frozen N=6 plan could be built.
- The next fix must inspect and test the exact `image_set_plan` shape expected
  by `_matches_image_set_cardinality` and the E-Commerce compact schema. If the
  Remote Brain response is missing the required dict, `image_count`, or exactly
  six whole-image `shot_plan` entries, the correction belongs in the plan
  prompt/schema contract or adapter validation diagnostics, not in timeout,
  product-pool selection, identity binding, Provider capacity, or ImageGen.

Current gate:

- Planning-only remains blocked.
- Before any retry, write deterministic regression for the `image_set_plan`
  mismatch class and implement the smallest owning-layer correction.
- Real-image generation remains prohibited.

## 13D. Image-set plan numeric diagnostics before any schema fix

After the live `image_set_plan` rejection was identified, the next allowed
step is observability at the owning validation boundary, not another upstream
call.

Implemented diagnostic model:

- At the adapter `image_set_plan` cardinality rejection boundary, record only
  public-safe numeric fields:
  - `expected_image_count`;
  - `remote_image_count` as an integer or `null`;
  - `remote_shot_plan_count` as the count of non-empty string directions; and
  - `cardinality_valid`.
- The diagnostic must never record shot-plan text, prompt text, file paths,
  source IDs, output IDs, product IDs, provider payloads, URLs, or credentials.
- Stage trace and blocked outcome may carry the same safe numeric fields.
- This is a diagnostic improvement only. It does not make the live N=6 plan
  valid, does not relax exact N, and does not authorize ImageGen.

Deterministic regression coverage:

- valid compact N=6 plan without finalizer-only
  `canonical_provider_prompts` is accepted without a same-stage re-answer;
- malformed present `canonical_provider_prompts` remains rejected and traced;
- `provider_prompt_finalize` still requires a complete canonical prompt set;
- `image_set_plan` non-dict response, wrong `image_count`, and wrong
  non-empty `shot_plan` count all fail closed with only safe numeric
  diagnostics; and
- compact schema/recovery payload preserve the same requested N=6 contract.

Next gate:

- Use the numeric diagnostic only after reviewer approval for another
  mutation=0 planning-only trace.
- If the trace shows missing/wrong `image_count` or `shot_plan` count, repair
  the compact plan schema/prompt/adapter diagnostics at the owning layer.
- Do not raise timeout, split N, remove context, switch route/model, or
  generate images.

## 14. Old-document conflict index

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
