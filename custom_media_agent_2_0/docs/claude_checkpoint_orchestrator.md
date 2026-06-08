# Claude Checkpoint Orchestrator Development Design

## 背景

Custom Media Agent 2.0 的核心优势是 Claude Code 作为创意中枢。当前 V2 通过 `claude -p` 做一次性非交互调用，由 `app/services/claude_orchestrator.py` 产出 `CreativeOrchestratorDecision`，再由 `app/services/prompting.py` 合成最终图片提示词。

近期 VPS 上出现的问题不是图片接口失败，而是 Claude Code 在单次调用中进入 extended thinking，尚未产出最终 JSON 时就触发：

```text
Claude's response exceeded the ... output token maximum
```

人工使用 Claude Code 时，长会话可以自动压缩历史上下文继续；但 V2 当前是一次性 `--no-session-persistence` 调用，且本次错误发生在单轮 response output cap，而不是历史 context cap。因此需要在 V2 内部实现一个自动分阶段、自动压缩、自动续跑的 Claude 编排控制器。

## 硬约束

1. 所有 V2 创意请求都必须调用 Claude Code。不能按题材跳过 Claude。
2. 不能通过禁用 thinking 来换稳定性。`CLAUDE_CODE_DISABLE_THINKING=1` 只能作为实验或紧急降级，不作为主路径。
3. 可以压缩 Claude 的最终可见输出，但不能削弱 Claude 的思考质量。
4. selected template 仍然是最高优先级视觉锚点。
5. Uploaded assets 仍然是模板 slot 的具体变量，硬身份素材必须保持 V2-native input images。
6. V2 backend 不能调用 V1 接口、读写 V1 storage 或依赖 V1 bridge。
7. 最终 prompt 不能泄露内部 `case_id`、`asset_id`、`provider_id`、API、仓库或存储标识。

## 目标

实现一个 checkpoint 式 Claude 编排器：

- 用户只提交一次提示词。
- 系统自动进行多轮 Claude 调用。
- 每轮 Claude 都有完整思考空间。
- 每轮只输出短 JSON checkpoint 或最终 decision。
- 如果某轮超限，系统自动缩小该轮任务并重试，不要求用户介入。
- 如果某轮接近软边界仍未产出紧凑 JSON，系统先压缩状态并切换到 micro/ultra-micro stage，而不是等用户可见超时。
- 成功后统一压缩最终 `CreativeOrchestratorDecision`。
- 全程保留可诊断 workspace，但不向前端暴露 raw thinking。

## 非目标

- 不尝试无损恢复 Claude 的原始 chain-of-thought。
- 不把 raw thinking 当作下一轮事实来源直接喂回。
- 不把本地 deterministic composer 作为 Claude 的替代中枢。
- 不为了避免超限而屏蔽某类题材。

## 现有框架

当前关键路径：

```text
app/agents/runtime.py
  -> orchestrate_creative_request(...)
      app/services/claude_orchestrator.py
        -> _invoke_claude_file_mode(...)
        -> _invoke_claude_inline_json(...)
        -> _normalize_decision(...)
  -> compose_prompt_plan(...)
      app/services/prompting.py
  -> image provider
```

当前特点：

- `claude_orchestrator.py` 同时负责 cache、workspace、Claude CLI 调用、schema parse、fallback。
- `tools=none` 时走 inline JSON。
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS` 已可通过 `V2_CLAUDE_ORCHESTRATOR_MAX_OUTPUT_TOKENS` 控制。
- `MAX_STRUCTURED_OUTPUT_RETRIES=1` 可降低 Claude Code schema 重试膨胀。
- 一旦 `claude_output_token_limit`，当前只能 fallback。

## 新架构

新增一个控制器层，建议命名：

```text
app/services/claude_checkpoint_orchestrator.py
```

它不替代 `claude_orchestrator.py` 的所有能力，而是把单轮 Claude 调用升级为多阶段 Claude 工作流。

```text
orchestrate_creative_request(...)
  -> if V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED:
       run_checkpoint_orchestration(...)
     else:
       run_single_shot_orchestration(...)
```

### 推荐模块边界

```text
app/services/claude_runner.py
  负责通用 Claude CLI 调用、env、timeout、stdout/stderr 保存、错误分类。

app/services/claude_checkpoint_orchestrator.py
  负责 stage 计划、checkpoint 合并、自动续跑、最终 decision 组装。

app/services/claude_orchestrator.py
  保留外部入口、cache、状态记录、fallback 兼容。

app/services/claude_decision_compressor.py
  负责最终 decision 的 deterministic schema 压缩和清洗。
```

## 多阶段流程

### Stage 0: Task Pack

本地构造极简输入包，不调用 Claude：

```json
{
  "request": {},
  "mode": "smart_enhance | template_customize | revision | batch",
  "template_lock_contract": {},
  "asset_binding_policy": {},
  "candidate_cases": [],
  "output": {}
}
```

要求：

- 原始用户提示保留，不丢信息。
- 模板锁规则显式写入。
- 上传素材意图显式写入。
- 候选案例只放 compact fields。

### Stage 1: Intent Checkpoint

Claude 任务：理解用户真实需求，输出短 checkpoint。

输出 schema：

```json
{
  "stage": "intent",
  "mode": "smart_enhance",
  "primary_subject": "",
  "scene_goal": "",
  "must_keep": [],
  "must_avoid": [],
  "asset_requirements": [],
  "risk_notes": [],
  "confidence": 0.8
}
```

### Stage 2: Visual Strategy Checkpoint

Claude 任务：选择案例、构图、光影、视觉层级。

输出 schema：

```json
{
  "stage": "visual_strategy",
  "selected_case_ids": [],
  "composition": "",
  "lighting": "",
  "palette": "",
  "spatial_hierarchy": "",
  "template_lock_notes": "",
  "asset_fusion_notes": "",
  "confidence": 0.8
}
```

### Stage 3: Generation Decision

Claude 任务：基于前两个 checkpoint 输出最终 creative decision。

输出 schema 与现有 `CLAUDE_INLINE_DECISION_SCHEMA` 兼容：

```json
{
  "mode": "smart_enhance",
  "selected_case_ids": [],
  "final_prompt": "",
  "negative_prompt": "",
  "provider_parameters": {},
  "prompt_rationale": "",
  "confidence": 0.8
}
```

### Stage 4: Deterministic Compressor

本地执行，不调用 Claude：

- `final_prompt` 压缩到配置字数。
- `negative_prompt` 压缩到配置字数。
- `prompt_rationale` 压缩到配置字数。
- 清除内部 ID、URL、API、存储路径。
- 重新校验 selected template 优先级。

这一步只压缩 Claude 的最终输出形态，不替代 Claude 思考。

## 自动续跑机制

### 基本原则

如果某一 stage 接近软边界、超限或输出膨胀，不直接失败，也不直接喂回 raw thinking。控制器应当：

1. 保存该 stage 的 stdout/stderr 和错误分类。
2. 保留前面已完成的 checkpoint。
3. 将失败 stage 拆成更小的 substage。
4. 重新调用 Claude 完成缺失部分。
5. 最多自动续跑 `N` 次。
6. 若 Claude 是必需中枢且完全没有 recoverable checkpoint，停止 run，不能继续 deterministic-only 出图。

### 为什么不喂 raw thinking

raw thinking 可能是：

- 未完成的推理。
- 重复推理。
- 不稳定的自我纠错过程。
- 过长且会导致下一轮继续膨胀。

因此下一轮只能使用结构化 checkpoint，而不是 raw thinking 原文。

### Substage 示例

如果 Stage 2 超限，可拆成：

```text
2A: choose selected_case_ids only
2B: describe composition only
2C: describe lighting/palette only
2D: describe asset/template conflicts only
```

每个 substage 都调用 Claude，但输出很短。

### 首轮就超限怎么办

如果 Stage 1 在没有任何 checkpoint 前超限：

1. 改用 `intent_micro` stage。
2. 只要求 Claude 输出 5 个字段以内。
3. 保留完整 thinking，不设置 `CLAUDE_CODE_DISABLE_THINKING`。
4. 如果仍然失败且没有任何 Claude checkpoint，标记 `claude_thinking_overrun_unrecoverable`，不得继续出图。
5. 如果已经拿到任一 Claude checkpoint，保留该 checkpoint，压缩可见状态，再进入更短 Claude recovery stage；recovery 仍失败时，只能基于已有 Claude checkpoint 组装压缩决策，不能切到 deterministic-only creative fallback。

### Claude 自动压缩继续原则

V2 的 Claude 中枢必须模仿人类使用 Claude Code 时“接近边界就压缩上下文继续”的行为：

- `claude_timeout`、`claude_output_token_limit`、结构化输出重试耗尽、上游 context cancellation 都是压缩续跑触发器，不是绕过 Claude 的理由。
- 每个 stage 允许 Claude 完整思考，但可见输出必须是短 JSON/checkpoint，并受 `V2_CLAUDE_FINAL_PROMPT_MAX_CHARS`、`V2_CLAUDE_NEGATIVE_PROMPT_MAX_CHARS`、`V2_CLAUDE_RATIONALE_MAX_CHARS` 控制。
- 一旦已有 `intent` 或 `visual_strategy` checkpoint，后续失败必须继续使用压缩 checkpoint；最终 prompt 必须来自 Claude 输出或 Claude checkpoint 压缩结果。
- deterministic fallback 只能用于 Claude 完全未开始、无 checkpoint 可用且任务不得继续出图的失败解释，不得作为已启动 Claude 中枢后的创意替代。

## Stream-json 的用途

`stream-json` 可用于监控，但不应作为主路径直接展示 thinking。

用途：

- 记录 stage 是否卡在 thinking。
- 捕获最终 JSON 一旦出现就保存。
- 计算耗时、事件数、输出类型。
- 作为硬兜底，在接近 timeout 或 output cap 时终止并转 substage。

注意：

- stream 中可见 thinking delta 不应进入前端。
- 默认不持久化完整 raw thinking。
- 调试模式可以保存截断后的流事件样本。

## 配置项

建议新增：

```text
V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_CHECKPOINT_MAX_ROUNDS=4
V2_CLAUDE_CHECKPOINT_MAX_STAGE_RETRIES=2
V2_CLAUDE_CHECKPOINT_STAGE_TIMEOUT_SECONDS=180
V2_CLAUDE_CHECKPOINT_SOFT_STAGE_TIMEOUT_SECONDS=60
V2_CLAUDE_CHECKPOINT_SAVE_STREAM_EVENTS=false
V2_CLAUDE_FINAL_PROMPT_MAX_CHARS=1400
V2_CLAUDE_NEGATIVE_PROMPT_MAX_CHARS=320
V2_CLAUDE_RATIONALE_MAX_CHARS=180
V2_CLAUDE_ORCHESTRATOR_MAX_OUTPUT_TOKENS=32000
MAX_STRUCTURED_OUTPUT_RETRIES=1
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MAX_MODELS_PER_STAGE=3
V2_CLAUDE_ORCHESTRATOR_FALLBACK_STAGE_TIMEOUT_SECONDS=25
V2_CLAUDE_ORCHESTRATOR_FALLBACK_BASE_URL=https://aiself.vip
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODELS=deepseek-v4-pro-260425,deepseek-v4-flash-260425,deepseek-v3-2-251201,doubao-seed-2-0-lite-260428,doubao-seed-2-0-lite-260215,doubao-seed-1-6-lite-251015,glm-4-7-251222,doubao-lite-128k-240428,doubao-lite-32k-240328,doubao-lite-4k-240328
```

不建议主路径设置：

```text
CLAUDE_CODE_DISABLE_THINKING=1
MAX_THINKING_TOKENS=0
```

这些只能作为人工诊断或紧急降级。

### Claude Code Model Fallback

When the Claude Code route is available, it remains the only creative brain that V2 calls. The fallback does not call a separate OpenAI-compatible executor from the V2 backend. It re-invokes Claude Code for the same checkpoint stage with a different `--model` and optional `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` overrides.

This keeps the external V2 framework unchanged: same Claude checkpoint prompts, same JSON schema, same visual grammar lock, same uploaded-asset fusion policy, same output caps, and same selected-template priority. Model order is deliberately strongest-first:

```text
deepseek-v4-pro-260425
deepseek-v4-flash-260425
deepseek-v3-2-251201
doubao-seed-2-0-lite-260428
doubao-seed-2-0-lite-260215
doubao-seed-1-6-lite-251015
glm-4-7-251222
doubao-lite-128k-240428
doubao-lite-32k-240428
doubao-lite-4k-240328
```

If Kimi returns temporary upstream failures such as quota exhaustion, no available accounts, 502, context cancellation, timeout, or structured-output exhaustion, the controller tries the next Claude Code model in the queue. Secrets must not be committed; set `V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN` in the service environment, or use `OPENAI_API_KEY` / Codex auth on local machines.

## Workspace 文件布局

建议每次 orchestration workspace 写入：

```text
context.json
candidate_cases.json
candidate_case_details.json
template_lock_contract.json
asset_binding_policy.json
uploaded_assets.json

stage_01_intent_prompt.txt
stage_01_intent_stdout.json
stage_01_intent_stderr.txt
stage_01_intent_checkpoint.json

stage_02_visual_strategy_prompt.txt
stage_02_visual_strategy_stdout.json
stage_02_visual_strategy_checkpoint.json

stage_03_generation_decision_prompt.txt
stage_03_generation_decision_stdout.json
stage_03_generation_decision.json

compressed_decision.json
orchestration_trace.json
```

`orchestration_trace.json` 记录：

```json
{
  "stages": [
    {
      "stage": "intent",
      "status": "success",
      "duration_ms": 12000,
      "failure_code": null,
      "stdout_chars": 1200
    }
  ],
  "final_status": "success"
}
```

## 状态与错误码

新增 invocation statuses：

```text
checkpoint_success
checkpoint_cache_hit
checkpoint_partial_retry
checkpoint_fallback
checkpoint_failed
```

新增 failure reasons：

```text
claude_stage_output_token_limit:intent
claude_stage_output_token_limit:visual_strategy
claude_stage_timeout:generation_decision
claude_checkpoint_missing:intent
claude_checkpoint_schema_error:visual_strategy
claude_thinking_overrun_unrecoverable
```

## Cache 策略

当前 cache 可以保留，但 key 需要升级：

```text
claude_decision_v8_checkpoint_orchestrator
```

缓存内容建议包含：

- compressed final decision
- stage checkpoints
- cache metadata
- schema version

语义 cache 仍可使用，但必须包含：

- template_case_id
- asset roles and fusion policy summary
- output aspect ratio
- prompt n-grams

## 与模板锁的关系

`template_customize` 时：

- Stage 1 不能改变 `template_case_id`。
- Stage 2 的 `selected_case_ids[0]` 必须是 template case。
- Stage 3 的 `final_prompt` 必须保留模板构图、布局、光影、视觉节奏。
- Compressor 必须再次检查 selected case priority。

## 与上传素材的关系

Stage 1 必须读取并输出素材约束摘要：

```json
{
  "asset_requirements": [
    {
      "role": "logo_reference",
      "fusion_mode": "logo_product_surface",
      "target_surface": "apparel_chest",
      "provider_input_required": true
    }
  ]
}
```

Stage 3 不得把 hard identity 资产退化为纯文本描述。最终 provider input images 仍由 V2-native asset pipeline 提供。

## 测试计划

### Unit Tests

- Stage prompt builder preserves template lock.
- Stage prompt builder preserves asset fusion intent.
- Compressor removes internal IDs.
- Compressor enforces char limits.
- Output token limit in Stage 2 triggers substage retry.
- Stage 1 first-attempt overrun triggers `intent_micro`.
- No code path skips Claude when orchestrator is enabled.

### Integration Tests With Fake Claude Runner

- Full success path: 3 stages -> compressed decision.
- Stage 2 overrun -> split substages -> success.
- Stage 3 schema error -> retry once -> success.
- Repeated overrun -> `checkpoint_failed`.
- Cache hit returns same compressed decision.

### VPS Smoke Tests

Use `provider_hint=mock_image` to avoid real image cost:

- Template customization with selected case.
- Smart enhance fantasy battle prompt.
- Uploaded logo/product reference prompt.
- Batch count with OpenAI image rate limits still active.

## Implementation Plan

### Phase 1: Documentation and Test Fixtures

- Add this design doc.
- Add fake Claude runner fixtures.
- Add checkpoint schema models or TypedDicts.

### Phase 2: Extract Claude Runner

- Move subprocess invocation from `claude_orchestrator.py` into `claude_runner.py`.
- Keep existing single-shot behavior unchanged.
- Add common env:
  - `CLAUDE_CODE_MAX_OUTPUT_TOKENS`
  - `MAX_STRUCTURED_OUTPUT_RETRIES=1`

### Phase 3: Add Stage Builders

- Implement `build_intent_stage_prompt`.
- Implement `build_visual_strategy_stage_prompt`.
- Implement `build_generation_decision_stage_prompt`.
- Write stage outputs to workspace.

### Phase 4: Add Checkpoint Controller Behind Flag

- Add `V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED`.
- When disabled, current single-shot path remains.
- When enabled, run staged flow.

### Phase 5: Retry and Substage Logic

- Detect stage output token limit.
- Split failed stage into smaller subtasks.
- Merge substage checkpoints.
- Cap retry rounds.

### Phase 6: Final Compressor

- Deterministic schema compression.
- Prompt sanitization.
- Template lock assertion.
- Asset intent assertion.

### Phase 7: Observability

- Extend `/api/v2/orchestrator/status` with checkpoint stats.
- Add recent stage failure counts.
- Add workspace id and trace path for diagnostics.

### Phase 8: Deployment

- Ship to local.
- Run full V2 tests.
- Deploy to VPS without touching media storage.
- Run VPS tests and mock-image smoke.
- Push to GitHub.

## Rollback

Rollback must be simple:

```text
V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED=false
```

The old single-shot Claude orchestrator remains available until checkpoint mode has enough production confidence.

## Open Questions

1. 是否允许保存截断后的 stream event samples 供诊断？
2. 每个 stage 的最大自动续跑次数应为 1、2 还是 3？
3. `final_prompt` 字符上限采用 1100 还是 1400？
4. 是否需要把 checkpoint trace 暴露给管理端 UI？
5. 是否需要为不同 mode 配不同 stage plan？

## Recommended First Version

第一版建议保守实现：

- 默认启用 checkpoint mode only on VPS after local tests.
- 先支持 `smart_enhance` 和 `template_customize`。
- 每个 stage 最多 retry 1 次。
- Stage 超限时只拆成一个 micro stage，不做复杂树状规划。
- raw thinking 不保存，只保存 stdout summary 和 final JSON/checkpoint。
- 如果 checkpoint mode 连续失败，回退 single-shot Claude 一次，而不是跳过 Claude。
