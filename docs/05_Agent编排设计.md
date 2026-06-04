# 05. Agent 编排设计

## 1. 设计原则

- 中枢不做所有事，只做判断、拆解、授权和汇总。
- 专业 agent 只负责一个清晰职责。
- 所有外部 API 调用必须通过受控 tool，不让 agent 直接持有密钥。
- 每个 agent 输出尽量结构化，减少口水话。
- 每个 handoff 都要有输入 schema 和失败回退。

## 2. 双层 agent 架构

### 2.1 Claude Code Orchestrator

定位：控制面中枢。

职责：

- 复杂需求拆解和多 agent 调度。
- 管理 `.claude/agents` 下的 subagent 定义。
- 通过 hooks 做安全审计、危险命令拦截、工具调用日志。
- 在开发期生成 provider adapter、测试和文档。
- 在生产低频复杂链路中调用 OpenAI Agents Runtime API。

不建议：让它直接处理每一个高频生图任务的全部细节，除非已经做好延迟、成本、权限隔离和供应商降级。

### 2.2 OpenAI Agents SDK Runtime

定位：用户请求运行面。

核心 agents：

| Agent | 职责 | 主要输入 | 主要输出 |
|---|---|---|---|
| RuntimeManagerAgent | 意图识别、路由、澄清、handoff | 用户消息、session、assets | task_type、handoff、response |
| MaterialAnalyzerAgent | 解析素材并总结视觉/文本/约束 | asset_ids | MaterialBrief |
| PromptArchitectAgent | 结构化生图提示词 | user_intent、material_brief | ImagePromptPlan |
| ProviderSelectorAgent | 选择模型与参数 | prompt_plan、budget、capabilities | ProviderDecision |
| ImageGenerationAgent | 调用图片 provider | prompt_plan、provider_decision | GenerationJob/Output |
| CriticAgent | 检查生成结果 | output、prompt_plan、assets | ScoreReport |
| RevisionAgent | 炼金修改 | selected_output、feedback | PromptPatch |
| BatchPlannerAgent | 批量拆解 | variables、count、assets | BatchPlan |
| VideoPlannerAgent | 视频任务预留 | video_intent、assets | VideoJobRequest |
| SafetyComplianceAgent | 内容/版权/隐私风控 | user_input、assets、outputs | SafetyDecision |

## 3. Handoff 规则

- `RuntimeManagerAgent -> MaterialAnalyzerAgent`：当用户上传素材或引用已有素材。
- `RuntimeManagerAgent -> PromptArchitectAgent`：当用户明确要生成图片。
- `PromptArchitectAgent -> ProviderSelectorAgent`：完成 prompt plan 后。
- `ProviderSelectorAgent -> ImageGenerationAgent`：确定 provider 后。
- `ImageGenerationAgent -> CriticAgent`：生成输出后自动评价。
- `RuntimeManagerAgent -> RevisionAgent`：用户对已有输出提出修改。
- `RuntimeManagerAgent -> BatchPlannerAgent`：用户要求多张、批量、变量矩阵。
- `RuntimeManagerAgent -> VideoPlannerAgent`：用户要求视频；MVP 返回“已预留/实验性”。
- 任意 agent -> SafetyComplianceAgent：发现风险或工具调用前置审核。

## 4. Tool 设计

| Tool | 调用方 | 功能 |
|---|---|---|
| `analyze_assets(asset_ids)` | MaterialAnalyzerAgent | 输出素材摘要、限制、风格标签 |
| `create_image_job(plan)` | ImageGenerationAgent | 创建单次/批量图片任务 |
| `edit_image_job(source_output_id, patch)` | RevisionAgent | 基于图片继续修改 |
| `create_video_job(request)` | VideoPlannerAgent | 创建视频任务，MVP 可返回 experimental |
| `get_provider_capabilities()` | ProviderSelectorAgent | 查询模型能力和限制 |
| `estimate_cost(plan)` | ProviderSelectorAgent | 估算费用 |
| `run_safety_check(payload)` | SafetyComplianceAgent | 内容安全、版权、隐私、敏感词 |
| `store_generation_output()` | Generation Service | 存储输出并写数据库 |
| `score_generation_output()` | CriticAgent | 自动评价图片/视频 |

## 5. 结构化输出 Schema 示例

```json
{
  "task_type": "image_generation",
  "needs_clarification": false,
  "intent_summary": "为咖啡新品生成小红书封面",
  "asset_requirements": ["use_brand_palette", "use_reference_layout"],
  "batch": {"count": 6, "variables": ["season", "background"]},
  "safety_flags": []
}
```

## 6. Agent 失败回退

| 失败点 | 回退策略 |
|---|---|
| 素材解析失败 | 显示可读错误，允许跳过该素材继续生成 |
| Prompt JSON 不合法 | 用 schema 修复 agent 或 fallback parser |
| Provider 不支持参数 | ProviderSelector 改参数或切模型 |
| 图片生成失败 | 自动重试 1-2 次，失败后换 provider 或降级质量 |
| 评价低分 | 自动提示用户可继续修改，不擅自无限重试 |
| 安全阻断 | 解释原因，提供安全替代表达 |

## 7. Claude Code subagent 建议

在 `claude_code/.claude/agents/` 中预置：

- `visual-product-architect`：检查产品/交互/生成流程。
- `provider-adapter-engineer`：生成和维护模型 adapter。
- `prompt-template-curator`：管理提示词模板和评测集。
- `security-compliance-reviewer`：审查密钥、版权、隐私、内容安全。
- `test-eval-engineer`：维护 mock、E2E、视觉回归和 golden cases。

## 8. 开源 agent 框架接入建议

优先级：

1. 首选自定义 specialist agents + OpenAI Agents SDK，最少依赖。
2. LangGraph 可作为需要强状态机、断点、人类审批的工作流层。
3. CrewAI 可用于离线研究、内容策划、多角色共创任务。
4. OpenManus 类项目可做实验性自动执行子系统，但不要进 MVP 主链路。
5. AutoGen 生态历史价值高，但需要确认维护状态和迁移路线；新项目不要重度绑定。

关键点：第三方 agent 框架只作为 tool 子系统，不反向控制主链路。
