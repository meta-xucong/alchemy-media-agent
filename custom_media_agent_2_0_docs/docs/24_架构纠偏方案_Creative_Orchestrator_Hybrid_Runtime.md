# 24. 架构纠偏方案：Claude Code 中枢 + 可替换模型源

## 1. 修正背景

第一次审计指出 V2 偏离早期 OpenAI Agents SDK-first 设计，这个方向判断是对的。

但进一步核实代码后，需要把结论修正得更精准：

```text
当前不是 DeepSeek / Doubao / Volcengine 绕开 Claude Code 自己当总管。
当前是 Claude Code 仍然作为创意中枢，Kimi / DeepSeek / Doubao / GLM 作为 Claude Code 的模型源或备用源。
```

因此，这次纠偏不是“去 Claude Code 化”，而是：

1. 保留 Claude Code 创意中枢地位。
2. 明确模型换源只是 Claude Code 背后的推理源替换。
3. 明确 Python 后端是确定性执行层。
4. 明确 OpenAI Agents SDK 不是当前主执行引擎。

## 2. 代码事实

### 2.1 主业务链路

```text
CreativeManagerRuntime.run()
  -> _run_deterministic_manager()
```

Python 后端负责：

1. retrieval plan。
2. candidate cases。
3. template lock。
4. asset context。
5. prompt composer。
6. safety check。
7. image job。
8. storage/history/review。

### 2.2 创意裁决链路

```text
_run_deterministic_manager()
  -> orchestrate_creative_request()
  -> claude_orchestrator.py
  -> claude CLI
```

Claude Code 仍然是创意裁决入口。

### 2.3 模型换源机制

代码使用：

```text
--model
--fallback-model
ANTHROPIC_BASE_URL
ANTHROPIC_AUTH_TOKEN
ANTHROPIC_API_KEY
```

把 Kimi / 火山 / DeepSeek / Doubao 等 Anthropic-compatible 模型源接到 Claude Code CLI 后面。

这不是 Python 直接调用 DeepSeek / Doubao 当总管。

### 2.4 成功决策归一

`_normalize_decision()` 会返回：

```python
CreativeOrchestratorDecision(provider="claude-code", ...)
```

这意味着 Kimi / DeepSeek / Doubao 换源成功后，业务层仍视为 Claude Code orchestrator 的成功输出。

## 3. 当前真正的架构

```text
FastAPI /api/v2
  |
  v
CreativeManagerRuntime
  |
  +-- deterministic business pipeline
  |
  v
Claude Code Orchestrator
  |
  +-- Claude Code CLI
  +-- primary model source
  +-- fallback model source queue
  +-- checkpoint compression
  +-- semantic cache
  |
  v
Prompt Composer
  |
  v
Safety Service
  |
  v
Generation Service
  |
  v
V2-native Provider / Storage / History / Review
```

## 4. 对上一版纠偏方案的修正

上一版建议把 `claude_orchestrator` 重命名为 `creative_orchestrator`。现在修正为：

```text
不建议立即重命名。
```

原因：

1. 当前代码中 Claude Code 确实仍是创意中枢执行器。
2. DeepSeek / Doubao 是 Claude Code 的模型源，不是独立 orchestrator。
3. 过早改名可能误导后续开发者以为要去掉 Claude Code 中枢。

更准确的文档表达应是：

```text
Claude Code Orchestrator with pluggable model sources
Claude Code 中枢 + 可替换模型源
```

## 5. 纠偏目标

1. 不改回 SDK-first。
2. 不去掉 Claude Code 中枢。
3. 不把 DeepSeek / Doubao 做成默认独立总管。
4. 保留 Python 确定性执行层。
5. 文档明确模型换源边界。
6. 部署文档强调必须启用 Claude orchestrator 开关。

## 6. 分阶段实施方案

### Phase 0：暂停功能扩张

当前已执行。

1. 暂停 Veyra/sub2api 正式合并。
2. 暂停 SDK-first 重构。
3. 暂停把模型源改造成独立 orchestrator。
4. 先让文档和当前代码事实对齐。

### Phase 1：文档修正

当前阶段。

需要更新：

1. `00_CURRENT_ARCHITECTURE.md`
2. `02_系统架构_OpenAI_Agents_SDK优先.md`，保留历史文件名，但内容改为当前 Claude Code 中枢口径
3. `03_Agent运行时设计.md`
4. `11_部署配置与运行模式.md`
5. `14_Agent提示词与结构化输出模板.md`
6. `16_开发前ReadyChecklist.md`
7. `18_稳定化可观测与质量闭环开发文档.md`
8. `19_V2上传图片与TemplateLock开发文档.md`
9. `20_V2彻底独立模块化重构开发文档.md`
10. `21_Claude_Code速度优化开发文档.md`
11. 架构图和时序图。

验收：

1. 文档明确 Claude Code 是创意中枢。
2. 文档明确 Kimi / DeepSeek / Doubao 是 Claude Code 模型源。
3. 文档明确 Python 后端执行所有副作用。
4. 文档不再建议立即把 `claude_orchestrator` 改名为 `creative_orchestrator`。

### Phase 2：部署配置确认

上线或本地验收前必须检查：

```text
V2_CLAUDE_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_ORCHESTRATOR_MODEL=<primary source>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_BASE_URL=<optional compatible base>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN=<optional token>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODELS=<fallback queue>
```

如果 `V2_CLAUDE_ORCHESTRATOR_ENABLED=false`，系统实际走 deterministic fallback，不是 Claude Code 中枢模式。

### Phase 3：状态展示优化

状态接口和前端可以展示：

```text
orchestrator: Claude Code
source_provider: kimi / claude-code-primary / claude-code-model-fallback
model: deepseek-v4-pro / doubao-seed / ...
```

这样既保留 Claude Code 中枢，又清楚显示当前模型源。

### Phase 4：未来可选 SDK planner capsule

只有在明确需要时做。

形态：

```text
OpenAI Agents SDK planner
  -> CreativeOrchestratorDecision
  -> Python deterministic pipeline
```

这个 planner 不能替代 Claude Code 默认中枢，除非后续产品明确改设计。

## 7. `final_prompt` 风险重新定性

上一版把这个列为高优先级：

```text
_should_use_claude_final_prompt()
只接受 provider == "claude-code"
```

修正后：

```text
当前不是高风险。
```

原因：

1. Kimi / DeepSeek / Doubao 换源成功后，`_normalize_decision()` 会把 provider 归一为 `claude-code`。
2. 因此当前 `compose_prompt_plan()` 会使用这些换源结果的 `final_prompt`。

未来只有当系统新增“绕开 Claude Code 的独立 planner provider”时，才需要改为：

```text
成功 invocation_status
+ 无 fallback_reason
+ final_prompt 有效
```

## 8. 风险清单

### R1：运行配置未启用 Claude Code

优先级：高。

如果 `V2_CLAUDE_ORCHESTRATOR_ENABLED=false`，实际不会走 Claude Code 中枢。

### R2：模型换源被误解为总管替换

优先级：高。

后续 Codex 可能误把 DeepSeek / Doubao 写成独立 orchestrator。文档必须明确禁止。

### R3：旧 SDK-first 文档诱导重构

优先级：中。

旧 SDK-first 设计保留为历史参考，不作为当前实现入口。

### R4：过早重命名造成误解

优先级：中。

当前不建议全局改 `claude_orchestrator` 命名。

## 9. 不建议做的事

1. 不建议把 `CreativeManagerRuntime.run()` 改成 `Runner.run()`。
2. 不建议重写 `claude_orchestrator.py`。
3. 不建议把 DeepSeek / Doubao 做成默认独立总管。
4. 不建议现在全量改名为 `creative_orchestrator.py`。
5. 不建议让 SDK agent 直接调用 provider、storage、queue、billing。

## 10. 当前推荐决策

推荐路线：

```text
文档修正
-> 部署配置确认
-> 状态展示区分 Claude Code 中枢和模型源
-> 保留 SDK planner capsule 为未来选项
```

不推荐路线：

```text
SDK-first 重写
-> 去 Claude Code 化
-> DeepSeek / Doubao 独立总管
-> agent 接管 provider/queue/storage
```

## 11. 判断标准

后续所有开发先问：

1. 这是否保留 Claude Code 创意中枢？
2. 这是否只是替换 Claude Code 背后的模型源？
3. 这是否仍让 Python 后端执行副作用？
4. 这是否守住 Template Lock / Asset Binding / Safety？
5. 这是否保持 V1/V2 严格隔离？

如果新方案让模型源绕过 Claude Code 自己当默认总管，必须先得到明确产品决策。
