# 00. 当前真实架构与纠偏基线

## 1. 修正后的结论

当前 Alchemy Media Agent V2 不是早期文档里的 **OpenAI Agents SDK-first multi-agent runtime**。

但也不能说它已经变成“DeepSeek / Doubao / Volcengine 各自绕开 Claude Code 当总管”。

更准确的当前架构是：

```text
Python 确定性执行流水线
+
Claude Code 创意中枢
+
可替换模型源 / 备用模型源
+
SDK-compatible tool boundary
+
V2-native provider/storage/history/review
```

短句：

```text
Claude Code 负责创意裁决。
Kimi / 火山 / DeepSeek / 豆包是 Claude Code 背后的模型源或备用源。
Python 后端负责确定性执行。
OpenAI Agents SDK 是可选 planner/tool/tracing 边界。
```

所以，现在不建议“改回 SDK-first”，也不建议把 DeepSeek / Doubao 做成绕过 Claude Code 的独立总管。正确纠偏是：文档明确 **Claude Code 中枢 + 可替换模型源**，并继续保留 Python 后端的确定性执行边界。

## 2. 当前代码事实

当前主入口：

```text
custom_media_agent_2_0/app/agents/runtime.py
```

真实行为：

```python
async def run(self, request):
    return await self._run_deterministic_manager(request)
```

这说明端到端业务执行没有由 `Runner.run()` 接管。

但在 `composing_prompt` 阶段，主链路会调用：

```python
orchestrate_creative_request(...)
```

这进入：

```text
custom_media_agent_2_0/app/services/claude_orchestrator.py
```

该模块仍通过 Claude Code CLI 执行创意编排。Kimi / DeepSeek / Doubao / GLM 的角色是模型源和备用源，不是另起一个 Python planner。

关键证据：

1. `ClaudeSourceSelection` 选择的是 Claude Code source。
2. fallback 仍调用 `_invoke_claude_stage_json(command=claude, ...)`。
3. fallback 通过 `--model`、`--fallback-model`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN` 换源。
4. `_normalize_decision()` 会把成功的 Claude orchestrator 输出归一成：

```python
provider="claude-code"
```

因此，当前代码里 DeepSeek / Doubao 不是独立 provider 决策者，而是 Claude Code 调用链背后的模型源。

## 3. “总管”要分层理解

Claude Code 是：

```text
创意决策总管
```

职责包括：

1. 审美判断。
2. 案例取舍。
3. 提示词策略。
4. 模板锁理解。
5. 上传素材融合判断。
6. 生成参数建议。
7. 质量门禁策略。

Claude Code 不是：

```text
整个后端执行总管
```

后端确定性执行仍由 Python service 负责：

1. 检索案例。
2. 构建 asset context。
3. 应用 Template Lock / Visual Grammar Lock。
4. prompt plan 清洗。
5. safety hard gate。
6. provider 调用。
7. output storage。
8. image history。
9. Veyra 余额和扣费桥。
10. task queue。

这个分层是合理的。图片生成产品必须让可审计代码守住素材、安全、存储、扣费和 provider 边界。

## 4. 为什么看起来像“改岔”

### 4.1 早期 SDK-first 文档没有及时更新

旧文档仍写着：

```text
OpenAI Agents SDK-first
Runner.run(CreativeManagerAgent)
SDK runtime 承接执行
```

但当前代码事实是 Python pipeline 主执行，Claude Code 做创意裁决，SDK 保留边界。

### 4.2 模型源名称容易造成误解

fallback model list 包含：

```text
deepseek-v4-pro
deepseek-v4-flash
doubao-seed
glm
```

如果只看这些名字，容易误以为系统把 Claude Code 换成了 DeepSeek / Doubao 总管。

但代码实际是：

```text
Claude Code CLI
  -> --model / --fallback-model
  -> ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN
  -> Kimi / DeepSeek / Doubao / GLM model source
```

### 4.3 `claude_orchestrator_enabled=false` 时不会走 Claude Code

设计上 Claude Code 是创意中枢；运行上必须开启：

```text
V2_CLAUDE_ORCHESTRATOR_ENABLED=true
```

否则 `orchestrate_creative_request()` 会直接返回 deterministic fallback decision。

所以生产部署必须确认该开关，而不是只看代码设计。

## 5. 当前合理架构

```text
Frontend / H5
  |
  v
FastAPI /api/v2
  |
  v
CreativeManagerRuntime
  |
  +-- retrieval plan
  +-- case intelligence
  +-- uploaded asset binding
  +-- template lock / visual grammar lock
  |
  v
Claude Code Orchestrator
  |
  +-- Claude Code CLI
  +-- Kimi / Volcengine / DeepSeek / Doubao / GLM model sources
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
  +-- V2-native image provider registry
  +-- OpenAI GPT Image
  +-- Gemini image
  +-- Mock image
  |
  v
V2 storage / history / review / usage
```

## 6. OpenAI Agents SDK 的新定位

OpenAI Agents SDK 不再是当前主执行引擎。

它适合做：

1. 可选 `CreativePlanningAgent`。
2. function tool schema 边界。
3. structured output contract。
4. tracing。
5. future review / critique agent。
6. future interactive handoff。

它不负责：

1. 文件存储。
2. image provider 调用。
3. 任务队列。
4. 数据库写入。
5. 幂等与重试。
6. 安全硬门禁。
7. 权限隔离。
8. 成本扣费。
9. 上传素材文件处理。

短句：

```text
Agent/Claude Code 负责想。
Service 负责干。
Guardrail 负责不准乱干。
```

## 7. 对上一版纠偏结论的修正

上一版文档里有一个过度修正：

```text
Claude Code 只是当前 adapter。
```

这个说法不够准确。

应改为：

```text
Claude Code 仍是创意中枢执行器。
Kimi / 火山 / DeepSeek / 豆包是 Claude Code 的可替换模型源或备用源。
```

因此，后续开发不应把 DeepSeek / Doubao 做成独立 orchestrator，除非明确另开一个新的 planner capsule，并且它仍必须输出 `CreativeOrchestratorDecision`，再交回 Python 确定性 pipeline。

## 8. 当前实现债

### 8.1 文档债

需要把所有“SDK-first 主链路”改成当前分层口径：

```text
Python deterministic pipeline
+ Claude Code creative orchestrator
+ pluggable model sources
+ optional SDK boundary
```

### 8.2 命名债

当前 `claude_orchestrator.py` 命名基本仍可接受，因为 Claude Code 确实是创意中枢。

但需要在文档里解释：

```text
V2_CLAUDE_ORCHESTRATOR_* 配置的是 Claude Code 中枢。
其中 Kimi / DeepSeek / Doubao 是 Claude Code 的模型源，而非独立总管。
```

不建议现在大规模改名成 `creative_orchestrator.py`，以免误导成“去 Claude Code 化”。

### 8.3 运行配置债

生产要确认：

```text
V2_CLAUDE_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED=true   # 如果要使用 checkpoint 链路
V2_CLAUDE_ORCHESTRATOR_MODEL=<primary model source>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_BASE_URL=<optional compatible base>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN=<optional token>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODELS=<fallback model queue>
```

### 8.4 `final_prompt` 风险重新定性

上一版我把 `_should_use_claude_final_prompt()` 的 provider 判断列为高风险。

修正后应定性为：

```text
当前风险较低。
```

原因：成功的 Claude Code orchestrator 链路会被 `_normalize_decision()` 归一成 `provider="claude-code"`，所以 Kimi / DeepSeek / Doubao 换源结果仍会使用 `final_prompt`。

只有未来新增“绕开 Claude Code 的 SDK planner / OpenAI-compatible planner”时，才需要把判断改成“成功状态 + 无 fallback + final_prompt 有效”，而不是绑定 `provider == "claude-code"`。

## 9. 建议实施顺序

### P0：文档修正

当前阶段。

1. 明确 Claude Code 是创意中枢。
2. 明确 Kimi / 火山 / DeepSeek / 豆包是模型源或备用源。
3. 明确 Python 后端是确定性执行层。
4. 明确 SDK 不是当前主执行引擎。

### P1：部署配置确认

上线前必须验证：

1. Claude Code 中枢开关已启用。
2. checkpoint 是否按预期启用。
3. 主模型源和 fallback 模型源可用。
4. `/api/v2/orchestrator/status` 能正确展示 source/model/fallback 状态。

### P2：状态展示优化

前端或状态接口可以继续显示 Claude Code，但应补充模型源：

```text
Claude Code Orchestrator
source: kimi / claude-code-primary / claude-code-model-fallback
model: deepseek-v4-pro / doubao-seed / ...
```

### P3：未来可选代码修复

仅当引入非 Claude Code planner 时，再修改：

```text
_should_use_claude_final_prompt()
```

当前不作为阻塞项。

## 10. 当前禁止项

1. 禁止把 DeepSeek / Doubao 直接实现成绕开 Claude Code 的默认创意总管。
2. 禁止把主链路改成 SDK-first `Runner.run()`。
3. 禁止让 SDK agent 直接调用 image provider。
4. 禁止绕过 Template Lock / Asset Binding / Safety。
5. 禁止恢复 V1 bridge。
6. 禁止为了命名整洁做大规模文件重命名。

## 11. 验收口径

文档修正完成后，应满足：

1. 新开发者知道：Claude Code 是创意总管。
2. 新开发者知道：Kimi / DeepSeek / Doubao 是 Claude Code 模型源。
3. 新开发者知道：Python 后端负责确定性执行。
4. 旧 SDK-first 文档不会再被理解为当前实现。
5. 不再把“模型换源”误读成“总管替换”。
