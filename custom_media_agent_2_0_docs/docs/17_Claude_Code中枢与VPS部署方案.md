# 17. Claude Code 中枢与 VPS 部署方案

> 当前状态：本文保留为 Claude Code 中枢与 VPS 部署参考。V2 当前总体架构详见 `00_CURRENT_ARCHITECTURE.md`：Claude Code 仍是创意决策中枢；Kimi / 火山 / DeepSeek / 豆包是 Claude Code 的模型源或备用源；Python 后端负责确定性执行；OpenAI Agents SDK 不接管当前主链路。

## 1. 结论

Claude Code 可以作为 2.0 的最高层中枢大脑继续推进。官方文档支持 Linux，包括 Ubuntu、Debian、Alpine，以及 x64/ARM64 处理器；也提供 macOS/Linux/WSL 安装脚本和 apt/dnf/apk 包源。因此最终部署到 VPS 不构成路线阻断。

2.0 的最终架构应调整为：

```text
Claude Code Creative Orchestrator
  最高权限审美与调度控制面
  输出 CreativeOrchestratorDecision

Claude Code model sources
  Kimi / Volcengine / DeepSeek / Doubao / GLM
  通过 --model / --fallback-model / ANTHROPIC_BASE_URL 换源

CreativeManagerRuntime
  承接 Claude Code 决策
  执行确定性业务流水线

Domain Services
  案例库、同步、提示词、生图、安全、历史、缩略图

OpenAI Agents SDK
  可选 planner/tool/tracing 边界
```

## 2. 为什么不是结构化匹配做大脑

结构化匹配只能解决召回和候选排序，不能成为最终创意中枢。

它适合做：

1. 从本地案例库召回候选。
2. 为 Claude 提供证据包。
3. 快速兜底。
4. 降低 token 和外部调用成本。

它不适合做：

1. 最终审美判断。
2. 多案例风格融合。
3. 判断客户真实商业意图。
4. 主动推翻候选。
5. 生成质量门禁和返工指令。

因此当前实现口径是：本地结构化检索是候选证据层；Claude Code 是最高裁决层。

## 3. 借鉴 Veyra 的原则

保留：

1. Claude 是最高权限控制面。
2. Claude 必须输出机器可执行 JSON。
3. 主系统执行 Claude 指令并审计。
4. Claude 可以大胆推翻本地草案。
5. Claude 不可绕过版权、安全、商用门禁。
6. Claude 不可要求人类中途阅读报告后再继续。
7. 外部 agent 必须有 timeout、fallback、health 和契约校验。

不照搬：

1. 不把 Veyra 的 PPT stage runner 搬到生图系统。
2. 不把 Claude CLI 当作唯一 executor。
3. 不让 Claude 直接读取密钥、数据库连接或对象存储凭据。
4. 不让 Claude 输出自然语言长文作为下游唯一输入。

## 4. 同步快速模式和文件工作区模式

当前已验证的本地实现采用两层模式。

### 同步快速模式

`v2-api` 内的同步请求默认使用：

```text
V2_CLAUDE_ORCHESTRATOR_TOOLS=none
```

主系统会把用户需求、少量候选案例摘要、必要视觉原子和输出要求压缩成一个小型规划包，通过 Claude Code CLI 的结构化输出能力取得 `CreativeOrchestratorDecision`。这种模式不让 Claude 在 HTTP request 内读写文件或调用工具，因此更适合本地测试和 VPS 初期部署。

同步快速模式仍会创建审计工作区，保存上下文、候选案例、stdout/stderr 和最终 decision，便于排查。

### 文件工作区模式

后台重型中枢 worker 可以启用文件工具模式：

```text
.v2_data/claude_orchestrator_runs/orc_xxx/
  MISSION.md
  context.json
  candidate_cases.json
  fallback_decision.json
  OUTPUT_CONTRACT.json
  decision_template.json
  decision.json
  claude_stdout.txt
  claude_stderr.txt
```

Claude 只需要完成一件事：写出 `decision.json`。

主系统只消费 `decision.json`，不会要求用户读取 `analysis.md` 或 stdout。

文件工具模式适合未来接入更多外部 agent、批量评审、复杂返工和多阶段调度，不建议长期阻塞同步 API。

## 5. 输出契约

`CreativeOrchestratorDecision` 核心字段：

1. `mode`
2. `selected_case_ids`
3. `case_retrieval_plan`
4. `final_prompt`
5. `negative_prompt`
6. `provider_parameters`
7. `prompt_rationale`
8. `prompt_directives`
9. `stage_commands`
10. `generation_directives`
11. `quality_gates`
12. `confidence`

`final_prompt` 是 Claude 深度思考后的最终生图 prompt，必须精简、可直接交给 gpt-image-2 或兼容 ImageProvider。同步快速模式建议控制在 1800 字符以内；它不需要包含 Claude 的完整推理过程，只保留对成图有用的视觉指令。

### 视觉证据包

Claude Code 中枢不直接面对未经整理的 700+ 案例原文。主系统会先通过 OpenAI Agents SDK 工具链和本地服务把候选案例压缩成证据包，其中包括：

1. `candidate_cases.json`：轻量摘要和召回理由。
2. `candidate_case_details.json`：prompt atoms、visual features、截断原 prompt、授权策略和 `visual_signal_brief`。
3. `visual_signal_brief`：系统从案例文本和 visual features 中提炼出的视觉 DNA，包括背景氛围、关键点缀色、材质、光影、构图和审美方向。

Claude 的职责是基于这些证据做最高层判断，而不是机械复述本地规则。尤其要注意：

1. 手选模板时，保留模板的版式结构、空间层级、强调色和材质处理。
2. 自动匹配时，判断哪些视觉信号与用户需求真正相关，允许推翻本地 fallback 选择。
3. 不要只看主背景色；小面积金色、墨绿、玻璃高光、金属边缘、深色对比等经常是案例质感来源。
4. 最终 `final_prompt` 不得泄漏内部 `case_id`、`asset_id`、`provider_id`、`source_url`、API 或仓库标识。

`negative_prompt` 建议控制在 400 字符以内；主系统会补齐固定安全负向词。`provider_parameters` 用于数量、质量、画幅、provider hint、输出格式等参数。`prompt_rationale` 是给前端和审计看的短解释，不参与生图。

`prompt_directives` 继续保留，但用途从“下游主 prompt 合成原料”调整为：

1. 前端解释本次中枢提炼了哪些风格策略。
2. 审计 Claude 为什么选择这些案例。
3. Claude 失败或旧缓存缺少 `final_prompt` 时，本地 PromptComposer 的兜底输入。

下游消费规则：

1. `selected_case_ids` 控制最终使用哪些案例做启发。
2. 当 Claude 成功且 `final_prompt` 合约有效时，`ImagePromptPlan.prompt` 直接采用 `final_prompt`。
3. `negative_prompt` 直接进入 `ImagePromptPlan.negative_prompt`，主系统追加固定安全负向词。
4. `provider_parameters` 优先覆盖数量、质量、画幅、provider hint。
5. `generation_directives` 保留为旧字段和阶段调度参数；与 `provider_parameters` 冲突时，`provider_parameters` 优先。
6. `quality_gates` 进入后续输出复检和自动返工。
7. `stage_commands` 作为未来多 agent 调度和重跑依据。

## 6. VPS 部署

推荐 Linux 发行版：

1. Ubuntu 22.04/24.04。
2. Debian 12。
3. Alpine 3.19+ 也可用，但需额外注意 musl/ripgrep 依赖。

推荐服务拆分：

```text
v2-api
v2-worker
v2-sync-worker
v2-claude-orchestrator-worker
v2-scheduler
```

当前已从 FastAPI 单进程 `BackgroundTasks` 迁移到 SQLite 持久任务队列：

1. `POST /api/v2/creative/runs/async` 只保存 `planning` run 并入队。
2. `POST /api/v2/outputs/{output_id}/revisions/async` 也入同一队列。
3. `GET /api/v2/creative/runs/{run_id}` 可从业务内存或队列结果快照恢复 run。
4. 本地开发可启用 API 内联 worker。
5. VPS 推荐关闭 API 内联 worker，独立运行 `python -m app.workers.task_queue_worker`。
6. GitHub/ResourceProvider 更新检查推荐独立运行 `python -m app.workers.resource_sync_worker --mode auto`。

SQLite 队列适合低并发 VPS 初期生产化。后续如果进入高并发或多机部署，可把 `task_queue` service 替换为 Redis/RQ、Celery、Arq 或数据库队列表，但 API 和 worker 契约不应变化。

## 7. 环境变量

```text
V2_CLAUDE_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_ORCHESTRATOR_CLI=claude
V2_CLAUDE_ORCHESTRATOR_MODEL=
V2_CLAUDE_ORCHESTRATOR_TIMEOUT_SECONDS=240
V2_CLAUDE_ORCHESTRATOR_MAX_OUTPUT_TOKENS=8192
V2_CLAUDE_ORCHESTRATOR_EFFORT=low
V2_CLAUDE_ORCHESTRATOR_DISABLE_SLASH_COMMANDS=true
V2_CLAUDE_ORCHESTRATOR_TOOLS=none
V2_CLAUDE_ORCHESTRATOR_PERMISSION_MODE=bypassPermissions
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODEL=
V2_CLAUDE_ORCHESTRATOR_WORKSPACE_DIR=/var/lib/alchemy/v2/claude_orchestrator_runs
V2_CLAUDE_ORCHESTRATOR_CACHE_ENABLED=true
V2_CLAUDE_ORCHESTRATOR_SEMANTIC_CACHE_ENABLED=true
V2_CLAUDE_ORCHESTRATOR_SEMANTIC_CACHE_THRESHOLD=0.92
V2_CLAUDE_ORCHESTRATOR_CACHE_PATH=/var/lib/alchemy/v2/claude_orchestrator_cache.json
V2_CLAUDE_ORCHESTRATOR_MAX_ATTEMPTS=2
V2_CLAUDE_ORCHESTRATOR_RETRY_DELAY_SECONDS=2
V2_TASK_QUEUE_DB_PATH=/var/lib/alchemy/v2/task_queue.sqlite3
V2_TASK_QUEUE_INLINE_WORKER_ENABLED=false
V2_TASK_QUEUE_POLL_INTERVAL_SECONDS=1
V2_TASK_QUEUE_CLAIM_TIMEOUT_SECONDS=900
V2_TASK_QUEUE_MAX_ATTEMPTS=3
V2_SYNC_GITHUB_ON_STARTUP=false
V2_ENABLE_REMOTE_GITHUB_SYNC=true
V2_RESOURCE_SYNC_INTERVAL_MINUTES=360
V2_OUTPUT_REVIEW_AGENT_ENABLED=true
V2_OUTPUT_REVIEW_AGENT_MODEL=
```

`V2_CLAUDE_ORCHESTRATOR_TOOLS=none` 是同步 API 的推荐默认值。`default` 或其他工具配置只建议在 `v2-claude-orchestrator-worker` 中启用。

同步快速模式必须保持短输出：

1. inline 调用使用 Claude CLI 的 `--output-format json` 和 `--json-schema`。
2. `V2_CLAUDE_ORCHESTRATOR_MAX_OUTPUT_TOKENS` 默认 8192，通过 `CLAUDE_CODE_MAX_OUTPUT_TOKENS` 传给 Claude CLI。最终 `final_prompt` 仍由 JSON schema 和本地清洗控制在短 prompt 范围内。
3. inline schema 只要求 `final_prompt`、`negative_prompt`、`provider_parameters`、`prompt_rationale`、`selected_case_ids` 和 `confidence`；`prompt_directives` 可由主系统从最终 prompt 反推解释，避免 Claude 花时间填写冗余字段。
4. 同步快速模式默认传入 `--bare`、`--disable-slash-commands`、`--tools none`、`--effort low`，减少 Claude Code 启动、插件、slash command 和工具系统开销。
5. Claude 可以在内部充分思考，但结构化输出只保留最终 prompt 包、短理由和必要参数，不输出长篇分析。
6. 如果 Claude 返回 `claude_output_token_limit`，这是结构化输出长度失控，不做重复重试，立即 deterministic fallback，并在 `fallback_reason` 记录 `claude_invoke_error:claude_output_token_limit`。
7. 这类 fallback 不应影响真实生图；它只说明本轮中枢规划未成功。

### 不降智加速策略

Claude Code 仍然是最高裁决层，但不应重复做已经做过的同一件事。当前采用三层加速：

1. exact cache：用户 prompt、输出参数、候选案例完全一致时直接复用 Claude 决策。
2. semantic cache：同模式、同模板、同输出参数、候选案例高度重合，并且归一化文本 token 相似度超过 `V2_CLAUDE_ORCHESTRATOR_SEMANTIC_CACHE_THRESHOLD` 时复用。默认阈值 `0.92`，只覆盖近重复和轻微标点/措辞变化。
3. minimal inline contract：Claude 仍做审美判断和案例选择，但只输出最终 prompt 包；解释字段由 `prompt_rationale` 和本地反推补齐。

semantic cache 不用于跨产品、跨画幅、跨 provider 或候选案例差异大的请求，避免为了速度牺牲创意判断。

如果 Claude Code 通过 sub2api 接入 Kimi，日志中的 `Post "https://api.kimi.com/coding/v1/messages?beta=true": context canceled` 通常更像下游客户端或网关提前取消，而不是 Kimi 稳定返回业务 502。2.0 侧已把这类错误归类为 `kimi_context_canceled` 并进入有限重试；但生产稳定性仍应在 sub2api/Kimi 侧把客户端 timeout 提到 20-30 秒以上，并为 Kimi 配备用账号或稳定出口。

生产安全要求：

1. Claude 工作区不得包含 `.env`、API key、数据库密码。
2. 工作区只写入脱敏上下文和候选案例摘要。
3. 所有调用必须有 timeout。
4. 所有失败必须 fallback。
5. `bypassPermissions` 只应在受限容器/受限目录中使用。

## 8. 降级策略

Claude 不可用时，系统必须继续可用：

1. `claude` 命令不存在 -> deterministic fallback。
2. Claude 超时 -> deterministic fallback。
3. Claude 输出不是 JSON -> deterministic fallback。
4. Claude 选择不存在的 case -> 过滤无效 case，并补充本地召回。
5. Claude 要求绕过安全门禁 -> 忽略相关字段，保留 safety gate。

## 9. 当前落地状态

已落地：

1. `CreativeOrchestratorDecision` schema。
2. Claude Code 同步快速适配器和审计工作区。
3. `V2_CLAUDE_ORCHESTRATOR_*` 配置。
4. `CreativeManagerRuntime` 消费 Claude 决策。
5. Prompt 组合可优先消费 Claude `final_prompt` 包，并在缺失时回退到 `prompt_directives` 本地合成。
6. Claude 失败时自动 fallback。
7. 单元测试验证 Claude 决策可影响 case selection、final prompt、negative prompt、provider parameters 和 output count。
8. 兼容 Claude 返回 `selected_cases + generation_directives.prompt` 的旧结构，并转成正式 final prompt 包。
9. Claude 中枢状态接口、缓存、有限重试、Kimi/sub2api context canceled 诊断。
10. 前端 2.0 中枢分析面板。
11. 规则型输出复检与 revision directives。
12. SQLite 持久任务队列、独立 worker 入口和轮询模型。
13. 基于 output review 的 revision run 入口。
14. `CreativeManagerAgent` 已注册 OpenAI Agents SDK tools：案例检索、案例详情、安全检查。
15. `VisualCriticAgent` 已接入复检边界，当前默认使用 provider metadata 和 prompt evidence，未来可在同一边界接入真实视觉/LLM Runner。

未落地但应进入下一阶段：

1. 把 `stage_commands` 接入更多 provider/agent 调度。
2. 为 VPS 增加 systemd/docker 部署脚本。
3. 为 Kimi provider 增加备用账号、代理出口和网关级超时配置。
4. 把 `VisualCriticAgent` 从 metadata fallback 升级为真实视觉模型复检。
