# 06. Tools 与 Domain Services 契约

## 基本原则

Agent 不能直接访问数据库、密钥、文件系统或供应商 API。所有真实动作必须通过后端 Domain Services 执行。SDK function tools 是未来 planner capsule 的工具边界，不是当前主链路的副作用执行入口。

```text
Agent or Planner -> Tool Boundary -> Domain Service -> Provider Adapter -> Vendor or Storage
```

## Tool 设计要求

每个 tool 必须有：

1. 明确输入 schema。
2. 明确输出 schema。
3. 超时。
4. 幂等键。
5. 鉴权上下文。
6. 结构化错误。
7. trace event。
8. 安全策略。

## 核心 Tools

当前 `CreativeManagerAgent` 已按 OpenAI Agents SDK 注册第一批 function tools：

1. `case_strategist_search`：调用 `CaseIntelligenceService` 检索案例。
2. `case_detail`：返回单个案例详情和 license/risk 信息。
3. `case_profile`：返回单个案例的结构化画像，用于中枢判断可复用主体、风格、用途、材质、色彩、光影、构图和风险。
4. `prompt_safety_check`：调用 `SafetyService` 对草稿 prompt 做硬门禁。

这些工具先作为 SDK-compatible tool boundary 和未来 planner/tracing capsule 接入点存在；当前端到端主流程由 `CreativeManagerRuntime` 的确定性 pipeline 承担。

### search_prompt_cases

用途：检索案例。

输入：

1. `query_text`。
2. `category_filters`。
3. `style_filters`。
4. `use_case_filters`。
5. `risk_filters`。
6. `limit`。
7. `diversity_level`。

输出：

1. `cases`。
2. `ranking_explanation`。
3. `index_version`。

### get_prompt_case

用途：获取单个案例详情。

要求：必须返回 license 和 risk 信息。

### get_case_profile

用途：获取单个案例画像。

输出：

1. `source`：画像来源，`rules` 或 `claude-code`。
2. `model`：画像来源模型。
3. `subject_tags`。
4. `style_tags`。
5. `use_case_tags`。
6. `material_tags`。
7. `color_tags`。
8. `lighting_tags`。
9. `composition_tags`。
10. `reusable_principles`。
11. `suitable_for`。
12. `caution_tags`。

### request_resource_sync

用途：请求某个 provider 检查更新。

限制：只创建后台同步任务，不在 agent 运行中执行长同步。

### analyze_assets

用途：分析用户上传素材或案例预览图。

输出：

1. 主体。
2. 色彩。
3. 构图。
4. OCR。
5. 风险标记。

### run_safety_check

用途：对输入、prompt plan、素材、输出解释做硬门禁。

输出：`SafetyDecision`。

### select_image_provider

用途：根据任务需求选择图像供应商、模型和参数。

考虑：

1. 画质。
2. 成本。
3. 尺寸。
4. 文字能力。
5. 编辑能力。
6. SLA。

### create_image_job

用途：创建生图任务。

要求：

1. 必须先通过 safety check。
2. 必须记录 prompt plan。
3. 必须记录 case provenance。
4. 返回 job ID，不阻塞等待所有输出。

### score_generation_output

用途：对生成结果打分。

评分维度：

1. 用户目标匹配。
2. 构图。
3. 光影。
4. 色彩。
5. 文字可读性。
6. 品牌安全。

当前实现对应 `VisualCriticAgent` 和 `OutputReviewService`。未配置真实视觉模型时，agent 只基于 provider metadata、prompt plan、错误状态和 mock/live 标记生成 `ImageReviewDecision`，并在 `analysis_mode` 标记为 `sdk_agent_metadata_fallback` 或 `metadata_rules`。

### store_feedback

用途：保存用户反馈。

反馈类型：

1. 选中。
2. 下载。
3. 喜欢。
4. 不喜欢。
5. 继续修改。
6. 标记问题。

## Domain Services

### ResourceSyncService

职责：同步、解析、索引 provider。

### CaseIntelligenceService

职责：案例结构化、特征提取、embedding、检索。

### PromptService

职责：保存 prompt plan、版本、变量和最终执行 prompt。

### GenerationService

职责：创建生图 job，调用 ImageProvider，保存输出。

### SafetyService

职责：确定性安全和授权判断。

### EvaluationService

职责：自动评分和评测集运行。

### FeedbackService

职责：用户反馈、案例权重和召回优化。

## 错误格式

所有 tool 错误统一：

```json
{
  "error_code": "provider_timeout",
  "message": "Provider request timed out.",
  "retryable": true,
  "user_visible": false,
  "safe_fallback": "Use cached index version 2026-06-04T08:00:00Z."
}
```

Agent 可以解释错误，但不能伪造成功结果。
