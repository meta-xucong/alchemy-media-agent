# 03. Runtime 设计：CreativeManager Pipeline 与 Claude Code 中枢

## 1. 当前运行时选择

当前 V2 运行时不是 SDK-first。

当前主链路：

```text
CreativeManagerRuntime.run()
  -> _run_deterministic_manager()
```

这个 pipeline 负责端到端业务编排，包括案例召回、素材绑定、模板锁、Claude Code 创意中枢、prompt plan、安全检查、生图、存储和历史。

OpenAI Agents SDK 当前只作为工具边界和未来 planner capsule 的预留能力。

## 2. 当前运行时图

```text
CreativeManagerRuntime
  |
  +-- build retrieval plan
  +-- retrieve candidate cases
  +-- prioritize selected template
  +-- build asset context
  +-- call Claude Code Orchestrator
  +-- compose prompt plan
  +-- run safety check
  +-- create running image job
  +-- create final image job
  +-- save CreativeRun snapshot
```

## 3. Claude Code Orchestrator

当前实现文件：

```text
app/services/claude_orchestrator.py
```

概念定位：

```text
Claude Code creative orchestrator with pluggable model sources
```

职责：

1. 输入用户需求、候选案例、模板、上传素材上下文。
2. 通过 Claude Code CLI 进行创意裁决。
3. 输出 `CreativeOrchestratorDecision`。
4. 在 checkpoint 模式下分阶段压缩：intent、visual_strategy、generation_decision。
5. 在上游慢、输出超限、结构化失败时继续压缩恢复。
6. 通过 Kimi / DeepSeek / Doubao / GLM 等模型源 fallback 保持创意规划可用。
7. 不直接执行生图、存储、扣费或数据库写入。

## 4. 模型源与备用源

当前模型换源不等于总管替换。

代码仍通过 Claude Code CLI 执行：

```text
claude
  --model <primary-model-source>
  --fallback-model <fallback-model-source>
  ANTHROPIC_BASE_URL=<compatible-base>
  ANTHROPIC_AUTH_TOKEN=<token>
```

因此：

```text
Kimi / DeepSeek / Doubao / GLM = Claude Code 背后的推理源
Claude Code Orchestrator = 创意中枢执行器
```

## 5. CreativeOrchestratorDecision

关键字段：

1. `provider`：当前成功 Claude Code 链路归一为 `claude-code`。
2. `mode`：`template_customize`、`smart_enhance`、`revision`、`batch`。
3. `selected_case_ids`。
4. `case_retrieval_plan`。
5. `final_prompt`。
6. `negative_prompt`。
7. `provider_parameters`。
8. `prompt_rationale`。
9. `prompt_directives`。
10. `generation_directives`。
11. `quality_gates`。
12. `fallback_reason`。
13. `invocation_status`。

设计原则：

```text
Claude Code 成功时，final_prompt 是下游 prompt 的首选输入。
Kimi / DeepSeek / Doubao 换源成功后仍归一为 claude-code provider。
```

## 6. Prompt Composer

当前 Prompt Composer 是确定性 service，不是 SDK agent。

职责：

1. 优先承接 Claude Code 成功输出的 `final_prompt`。
2. 清洗内部 ID、provider、source URL、API key 等泄漏风险。
3. 应用 Template Lock。
4. 应用 Asset Binding guard。
5. 应用 Visual Grammar Lock 和 Information Integrity。
6. 合并 negative prompt。
7. 合并 provider parameters。
8. 输出 `ImagePromptPlan`。

## 7. Safety Service

Safety 是 hard gate。

任何 agent、orchestrator、SDK planner 都不能绕过：

```text
run_safety_check()
```

当 safety 返回 blocked 或 need_user_confirmation，Generation Service 不得执行 provider 调用。

## 8. Generation Service

Generation Service 是唯一合法的生图副作用入口。

职责：

1. 选择 V2-native provider。
2. 准备 input images。
3. 处理 provider fallback / rate limit / timeout。
4. 保存 output storage。
5. 写 image history。
6. 执行 output review。
7. 写 Veyra usage metadata。

Claude Code、SDK agent 或模型源不允许直接调用 provider。

## 9. SDK Function Tools

当前已构建但不接管主链路的 SDK tools：

1. `case_strategist_search`
2. `case_detail`
3. `case_profile`
4. `prompt_safety_check`

这些 tools 的当前定位：

```text
future SDK planner/tracing capsule boundary
```

不是当前主执行链路。

## 10. 可选 SDK Planner Capsule

未来可以新增：

```text
CreativePlanningAgent
  -> SDK Runner.run()
  -> structured CreativeOrchestratorDecision
```

接入条件：

1. 输出必须是 `CreativeOrchestratorDecision`。
2. 不能直接调用 Generation Service 以外的 provider。
3. 不能写数据库。
4. 不能绕过 Template Lock / Asset Binding / Safety。
5. 失败时回到当前 deterministic pipeline。
6. 不能默认替代 Claude Code 中枢，除非产品明确改设计。

## 11. Handoff

当前不使用 SDK handoff 作为主链路。

未来允许 handoff 的场景：

1. 用户进入模板向导。
2. 用户围绕某张图连续修订。
3. 用户切换视频任务。
4. 用户进入品牌风格配置向导。

handoff 输出仍必须回到 V2 domain service，不允许直接执行副作用。

## 12. Tracing

当前 tracing 主要由业务记录承担：

1. `CreativeRun.trace_id`
2. `progress_events`
3. `progress_summary`
4. `orchestrator_decision`
5. `claude_stage_trace`
6. image job metadata
7. image history metadata

未来 SDK tracing 可以补充 agent/tool 级别的可观测性，但不是业务事实来源。

## 13. 配置口径

当前代码使用：

```text
V2_CLAUDE_ORCHESTRATOR_*
V2_CLAUDE_CHECKPOINT_*
```

这是合理的，因为配置的是 Claude Code 中枢。

需要明确：

```text
V2_CLAUDE_ORCHESTRATOR_MODEL = Claude Code primary model source
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODELS = Claude Code fallback model source queue
```

不建议当前阶段大规模重命名为 `V2_CREATIVE_ORCHESTRATOR_*`，以免误解成去 Claude Code 化。
