# 21. Claude Code 速度优化开发文档

> 当前状态：本文保留为 Claude Code 中枢优化记录。V2 当前总体架构以 `00_CURRENT_ARCHITECTURE.md` 为准：主链路是确定性业务流水线，`claude_orchestrator` 是 Claude Code 创意中枢实现，Kimi / 火山 / DeepSeek / 豆包是 Claude Code 的模型源或备用源，OpenAI Agents SDK 是可选 planner/tool/tracing 边界。

## 1. 背景与问题

本文写作时，V2 曾被描述为 `Claude Code Creative Orchestrator + OpenAI Agents SDK Runtime` 的双层架构。按当前纠偏口径，应理解为：CreativeManagerRuntime 承担确定性主链路；`claude_orchestrator` 是 Claude Code 创意中枢实现；模型换源只替换 Claude Code 背后的推理源；OpenAI Agents SDK 只作为可选 planner/tool/tracing 边界。

近期真实链路暴露了两个问题：

1. 同步 Claude 规划可能运行 1-4 分钟，极端情况下触发 240 秒 timeout。
2. 手选模板模式下，fallback 或补充案例进入最终 prompt 证据集，导致用户选中的案例被稀释。

本阶段不改大架构，不引入复杂 worker 拆分，也不把 prompt 扩写完全交给另一个外部 agent。目标是在不降智的前提下，把同步规划压到可接受预算内，并保证失败时继续稳定出图。

## 1.1 耗时根因拆解

只限制 Claude Code 时间不能真正提速。实际慢点主要来自 Claude 被要求阅读和输出了太多不必要内容。

对近期慢工作区复盘后，主要负担是：

1. `candidate_case_details.json` 曾经写入完整 prompt atoms、visual features、license、raw prompt excerpt 等重字段，单次可达 25-32KB。
2. inline payload 中的 `candidate_cases` 曾经把 3 个候选案例的多组视觉信号、关键词、背景色和 reusable principles 都给 Claude，普通智能增强样本约 5.2KB。
3. 模板 + 上传 Logo 场景中，`asset_binding_policy.provider_input_plan` 曾重复包含 asset id、placement_targets、provider contract 和 review expectations，Claude 其实只需要知道“有参考图、必须作为 input image、融合方式、目标表面”。
4. `template_lock_contract` 曾重复写入 locked case id、长 summary、完整 locked elements 和 replaceable slots；而 `template_case_id` 和规则已经提供了同类信息。
5. inline JSON schema 曾允许更长 `final_prompt`、`negative_prompt` 和 `quality_gates`，增加了 Claude 输出空间和结构化输出压力。

本阶段根因优化后的目标体积：

```text
模板无素材：约 3.5KB inline payload
模板 + Logo 素材：约 3.9-4.0KB inline payload
普通智能增强 3 案例：约 4.1KB inline payload
```

这类压缩比单纯缩短 timeout 更重要：Claude 需要读的证据少了、需要比较的分支少了、需要输出的字段少了，真实规划时间才会从源头下降。timeout 只作为防死锁的安全上限，不作为主要提速手段。

## 2. 设计原则

### 2.1 不改中枢地位

Claude Code 仍是 V2 的最高创意中枢。速度优化只减少无效输入、冗余输出和重复调用，不把 Claude 降级成普通规则匹配器。

### 2.2 OpenAI Agents SDK 仍是运行框架

OpenAI Agents SDK 继续负责：

1. `CreativeManagerAgent` 执行中枢决策。
2. tool/service 边界。
3. safety guardrail。
4. provider 调度。
5. review agent 边界。
6. trace/provenance。

Claude Code 只是最高控制面，不直接越权执行 provider 或读取密钥。

### 2.3 手选模板快路径

当 `template_case_id` 存在时：

1. 手选案例是唯一主模板。
2. Claude 的候选证据只保留该模板。
3. `selected_case_ids` 只保留该模板。
4. PromptComposer 的 `style_basis` 只保留该模板。
5. 上传素材只能填入模板 slot，不能改写模板结构。

这能同时解决风格稀释和 Claude 输入过长。

### 2.4 同步预算优先

同步 API/队列 worker 中的 Claude 规划默认使用宽松安全上限，并通过输入/输出压缩提速：

```text
V2_CLAUDE_ORCHESTRATOR_TIMEOUT_SECONDS=240
V2_CLAUDE_ORCHESTRATOR_MAX_ATTEMPTS=2
V2_CLAUDE_ORCHESTRATOR_MAX_OUTPUT_TOKENS=8192
V2_CLAUDE_ORCHESTRATOR_EFFORT=low
V2_CLAUDE_ORCHESTRATOR_TOOLS=none
V2_CLAUDE_ORCHESTRATOR_DISABLE_SLASH_COMMANDS=true
```

如果 Claude Code 或上游模型异常卡死，240 秒安全上限会触发 deterministic fallback 并继续生图。正常提速不靠缩短这个窗口，而靠减少 Claude 必须阅读和输出的内容。

## 3. 优化范围

### 第 1 章：Template Lock 优先级修复

后端行为：

1. Runtime 在模板模式下只把手选模板传给 Claude inline 证据包。
2. Runtime 在最终 PromptComposer 阶段只传手选模板作为 `full_cases`。
3. `deterministic-fallback` 在模板模式下只返回手选模板 id。
4. Claude 正常返回时，即使它输出其他案例，normalize 阶段也只保留手选模板。
5. PromptComposer 做二次保险：模板模式只用 primary case 生成 reusable elements、`style_basis` 和 explanation。

验收：

1. 手选模板 + Claude 超时 fallback：最终 `selected_cases` 只有手选模板。
2. `prompt_plan.style_basis` 只有手选模板。
3. prompt 中不得出现其他补充案例标题或视觉骨架。

### 第 2 章：模板视觉骨架提取

仅有 `style_tags` 和 `visual_features` 容易把具体模板压扁成泛泛风格。模板模式必须从原始案例 prompt 中抽取可迁移的具体视觉骨架。

抽取重点：

1. 背景与地面。
2. 构图方向和空间层级。
3. 排版/注释/卡片结构。
4. 主体尺度和位置。
5. 人物/商品关系。
6. 光影、反射、材质。

清洗规则：

1. 不复制原案例品牌名。
2. 不复制原案例具体广告文案。
3. 不泄漏 `case_id`、`asset_id`、`provider_id`、`source_url`。
4. 只保留结构与审美信息。

验收：

1. 大阪卫衣模板应保留浅蓝棚拍背景、反光地面、巨大服装主体、背景大字排版、人物靠在主体上的关系。
2. prompt 不应复制 `OSAKA SIX`、`006 REMAINS` 等原案例文案。

### 第 3 章：Claude inline 证据压缩

同步 inline payload 只保留 Claude 做决策必需的信息。

模板模式：

1. 只传 1 个候选案例。
2. 案例摘要、raw visual skeleton、visual signal brief 截断。
3. fallback `selected_case_ids` 只传模板 id。
4. `prompt_atoms` 在模板模式下不再重复传入；模板结构由 raw visual skeleton 和 visual signal brief 承载。
5. raw visual skeleton 不再直接截断原文，而是按背景、构图、排版、主体尺度、人物关系、光影等视觉关键词抽句。

智能增强模式：

1. 最多传 3 个候选案例。
2. 每个案例只传短摘要、少量 tags、prompt atoms 和压缩后的 visual signals。
3. visual signals 只保留强调色、材质、光影、构图和一个 reusable principle，不再重复背景色和泛关键词列表。

上传素材：

1. 只传 role、constraint、visual summary、provider input required、fusion mode、placement intent、target surface、review expectations。
2. 不把长 `prompt_instruction` 直接塞给 Claude inline。
3. 不把 provider input plan 的 asset id、placement target 明细和长 provider contract 塞给 Claude，只保留 reference count、requires reference、fusion modes 和少量 review expectations。

验收：

1. 模板模式 inline prompt 显著小于旧版 9k-10k 字符，并在常见模板场景压到约 3.5-4.0KB。
2. 智能增强模式仍保留足够案例 DNA，不退化为纯关键词匹配，并在 3 候选场景约 4.1KB。

### 第 4 章：输出契约压缩

Claude inline JSON schema 只要求：

1. `mode`
2. `selected_case_ids`
3. `final_prompt`
4. `negative_prompt`
5. `provider_parameters`
6. `prompt_rationale`
7. `quality_gates`
8. `confidence`

`prompt_directives`、`stage_commands`、长解释由本地兼容层或未来异步 worker 处理，不要求同步路径填写。

输出约束：

1. `final_prompt <= 1400` 字符。
2. `negative_prompt <= 320` 字符。
3. 总结构化输出建议 `< 1900` 字符。

验收：

1. `claude_output_token_limit` 不重试，立即 fallback。
2. Claude 成功时 `ImagePromptPlan.prompt` 直接使用 `final_prompt`。

### 第 5 章：缓存与失败控制

缓存策略：

1. exact cache：完全相同的 prompt、模板、输出参数、候选案例和上传素材复用。
2. semantic cache：只允许同模式、同模板、同输出参数、候选案例高度重合、文本 token 相似度高于阈值时复用。
3. 本次 schema 升级到 `claude_decision_v6_template_lock_fast_path`，避免旧缓存复用错误的多案例模板决策。

失败策略：

1. `claude_timeout` 不重试。
2. `claude_output_token_limit` 不重试。
3. `kimi_context_canceled` 可有限重试。
4. 其他异常最多 2 次后 fallback。

验收：

1. Claude 超时不导致生图失败。
2. fallback 有明确 `fallback_reason`。
3. 旧缓存不会污染新 Template Lock 行为。

## 4. 实施步骤

### Step 1：Runtime 模板快路径

修改文件：

```text
custom_media_agent_2_0/app/agents/runtime.py
```

动作：

1. 在 retrieval 后提前读取 `template_case`。
2. 模板存在时，Claude 候选证据集只保留模板。
3. 模板存在时，最终 `full_cases=[template_case]`。
4. 非模板模式保持原智能检索和补充逻辑。

### Step 2：PromptComposer 二次保险

修改文件：

```text
custom_media_agent_2_0/app/services/prompting.py
```

动作：

1. 模板模式只使用 primary case 生成 reusable elements。
2. 模板模式只输出 primary case 到 `style_basis`。
3. 增加 `_template_raw_visual_skeleton()`。
4. 增加品牌/文案清洗。

### Step 3：Claude inline 压缩与预算

修改文件：

```text
custom_media_agent_2_0/app/services/claude_orchestrator.py
custom_media_agent_2_0/app/config.py
```

动作：

1. 默认 timeout 保持 240 秒宽松安全上限，避免正常复杂规划被过早打断。
2. 默认 max attempts 从 3 改为 2。
3. 模板模式 fallback 和 normalize 都只保留模板 id。
4. inline payload 规则压缩。
5. `_compact_inline_cases()` 支持 `template_case_id`，模板模式只传 1 个案例。
6. `_CLAUDE_DECISION_CACHE_SCHEMA` 升级。

### Step 4：文档与部署配置

修改文件：

```text
custom_media_agent_2_0_docs/README.md
custom_media_agent_2_0_docs/docs/11_部署配置与运行模式.md
custom_media_agent_2_0_docs/docs/17_Claude_Code中枢与VPS部署方案.md
custom_media_agent_2_0_docs/docs/18_稳定化可观测与质量闭环开发文档.md
custom_media_agent_2_0/deploy/systemd/alchemy-v2.env.example
```

动作：

1. 增加本开发文档。
2. 同步默认 timeout/max attempts。
3. 说明 2-6 秒 Kimi 断开仍应优先看上游网关 timeout，不是本应用 240 秒 subprocess timeout。

### Step 5：测试

最小测试：

```powershell
$env:PYTHONPATH='custom_media_agent_2_0'
pytest custom_media_agent_2_0\tests\test_v2_api.py -q -k "template_customize or template_lock or claude_timeout or output_token_limit or semantic_cache"
```

完整 V2 测试：

```powershell
$env:PYTHONPATH='custom_media_agent_2_0'
pytest custom_media_agent_2_0\tests -q
```

静态检查：

```powershell
$env:PYTHONPATH='custom_media_agent_2_0'
python -m compileall custom_media_agent_2_0\app
node --check custom_media_agent_docs\src_skeleton\app\static\app.js
```

模拟验收：

1. 手选 `Editorial Osaka Six Sweatshirt Ad`。
2. 输入高端深绿色 POLO 衫海报需求。
3. 强制 Claude 超时或关闭 Claude，走 fallback。
4. 检查最终 prompt 保留该模板的具体骨架，而不是混入其他 5 个案例。
5. 检查 `selected_cases` 和 `style_basis` 只有手选模板。

## 5. 回滚策略

1. 如 Claude 短预算影响质量，可临时设置：

```text
V2_CLAUDE_ORCHESTRATOR_TIMEOUT_SECONDS=300
V2_CLAUDE_ORCHESTRATOR_MAX_ATTEMPTS=2
```

2. 如 semantic cache 误命中，可设置：

```text
V2_CLAUDE_ORCHESTRATOR_SEMANTIC_CACHE_ENABLED=false
```

3. 如 Claude 中枢整体异常，可设置：

```text
V2_CLAUDE_ORCHESTRATOR_ENABLED=false
```

系统仍会 deterministic fallback 并继续调用 V2-native ImageProvider。

## 6. 非目标

本阶段不做：

1. 引入新的外部 prompt agent。
2. 把 Claude 文件工具模式作为同步默认路径。
3. 大改任务队列。
4. 接入真实视觉复检模型。
5. 改 V1。
6. 放宽 V2 与 V1 的隔离原则。
