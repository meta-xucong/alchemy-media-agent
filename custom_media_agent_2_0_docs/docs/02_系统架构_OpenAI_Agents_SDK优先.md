# 02. 系统架构：从 SDK-first 到 Claude Code 中枢 Hybrid Runtime

## 0. 状态说明

本文原本描述的是早期 **OpenAI Agents SDK-first** 目标方案。

当前代码已经演化为：

```text
Python deterministic pipeline
+
Claude Code creative orchestrator
+
pluggable model sources
+
SDK-compatible tool boundary
```

当前实现以：

```text
docs/00_CURRENT_ARCHITECTURE.md
```

为准。

## 1. 为什么不再坚持 SDK-first

Alchemy V2 是图片生成生产系统，不是单纯聊天 agent。

图片生成生产系统更需要确定性控制：

1. 选中模板必须优先。
2. 上传素材必须按意图进入 provider input images 或确定性后处理。
3. 模板构图、灯光、空间层级不能被 LLM 随意覆盖。
4. safety、权限、扣费、存储、队列不能交给 agent 自由执行。
5. provider 参数、失败重试、历史记录必须可追踪。

这些能力适合由 Python 后端 service 保证，而不是由 SDK agent graph 接管。

## 2. 当前总体结构

```text
Frontend Shell
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
  +-- V2-native image providers
  +-- V2-native storage
  +-- V2-native history
  +-- V2-native review
```

## 3. Claude Code 中枢的位置

Claude Code 是当前 V2 的创意决策总管。

它负责：

1. 审美判断。
2. 案例取舍。
3. prompt strategy。
4. 模板锁理解。
5. 上传素材融合判断。
6. provider 参数建议。
7. 质量门禁策略。

它不负责：

1. 直接调用 image provider。
2. 写数据库或 history。
3. 操作扣费。
4. 绕过 safety。
5. 读取密钥或生产配置。

## 4. 可替换模型源

Kimi / 火山 / DeepSeek / Doubao / GLM 的位置是：

```text
Claude Code CLI 的模型源或备用源
```

不是：

```text
绕开 Claude Code 的独立总管
```

当前代码通过：

```text
--model
--fallback-model
ANTHROPIC_BASE_URL
ANTHROPIC_AUTH_TOKEN
ANTHROPIC_API_KEY
```

让 Claude Code 使用不同推理源。

成功输出统一归一为：

```text
CreativeOrchestratorDecision(provider="claude-code")
```

## 5. OpenAI Agents SDK 的当前位置

SDK 当前不是主链路执行引擎。

当前代码中 SDK 做：

1. 构建 `CreativeManagerAgent`。
2. 注册 function tools，如 case search、case detail、case profile、prompt safety check。
3. 保留未来 planner capsule、tracing、structured output 的边界。

当前代码中 SDK 不做：

1. 不接管 `CreativeManagerRuntime.run()`。
2. 不直接调用 image provider。
3. 不写数据库。
4. 不处理文件存储。
5. 不处理扣费。
6. 不绕过 safety hard gate。

## 6. Domain Services 的职责

业务后端负责所有副作用：

1. 鉴权。
2. Veyra 登录与扣费桥。
3. ResourceProvider 同步。
4. Case index 持久化。
5. 上传素材存储。
6. Provider input image 准备。
7. Prompt plan 保存。
8. Safety hard gate。
9. Image provider 调用。
10. V2 history/storage/review。
11. 任务队列与 worker。

## 7. SDK 未来可用方式

如果未来重新引入 SDK runtime，不应改回全链路 SDK-first，而应做局部 capsule：

```text
CreativePlanningAgent
  -> tools
  -> structured CreativeOrchestratorDecision
  -> deterministic pipeline
```

SDK planner 可以参与：

1. 高层创意规划。
2. 案例取舍策略。
3. prompt plan 候选。
4. 视觉复检建议。
5. tracing。

SDK planner 不允许：

1. 直接调用 provider。
2. 写数据库。
3. 读取密钥。
4. 修改扣费状态。
5. 绕过 Template Lock / Asset Binding / Safety。

## 8. 当前必须修正的旧表述

以下旧表述不再代表当前实现：

```text
OpenAI Agents SDK 是 2.0 的主 agent runtime
API -> SDK Runner.run(CreativeManagerAgent)
SDK runtime 承接 Claude 指令并执行全链路
```

当前正确表述：

```text
CreativeManagerRuntime 是主业务流水线。
Claude Code Orchestrator 是创意决策总管。
Kimi / DeepSeek / Doubao 是 Claude Code 的模型源。
OpenAI Agents SDK 是可选工具/规划/tracing 边界。
Domain Services 执行所有副作用。
```

## 9. 开发原则

1. 继续保持 V2 与 V1 严格隔离。
2. 不为架构洁癖重写主链路。
3. 不把模型源实现成绕开 Claude Code 的默认总管。
4. 新创意规划能力统一输出 `CreativeOrchestratorDecision`。
5. 新工具必须通过 service 边界执行副作用。
6. SDK 只能增强规划能力，不能削弱确定性守护。
