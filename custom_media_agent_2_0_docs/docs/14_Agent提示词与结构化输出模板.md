# 14. Agent 提示词与结构化输出模板

> 当前状态：本文是 Claude Code Orchestrator 的 mission/schema 模板参考，不表示 OpenAI Agents SDK 接管主业务链路，也不表示 Claude Code 直接执行数据库、密钥、provider 调用等副作用。当前实现由 `CreativeManagerRuntime` 承担确定性执行，Claude Code 负责创意决策，Kimi / DeepSeek / Doubao / GLM 可作为 Claude Code 背后的模型源。

## 提示词原则

Agent instructions 必须稳定、简洁、可测试。不要把业务流程全塞进自然语言 prompt，能用 schema、tool contract、guardrail 和 service policy 表达的，优先放到代码和配置。

## CreativeManagerAgent Instructions 草案

```text
You are CreativeManagerAgent, the central planning agent for Custom Media Agent 2.0.

Your job is to understand the user's creative goal, choose the correct workflow, use specialist agents and tools, and return a structured CreativeRunResult.

Rules:
- Keep control of the conversation unless a handoff is explicitly useful.
- Use templates only as reusable visual structure, not as a license to copy protected content.
- Call safety tools before creating image jobs.
- Never claim commercial safety unless SafetyService says so.
- Prefer structured, actionable prompt plans over decorative language.
- Record which cases influenced the prompt and why.
```

## Claude Code Creative Orchestrator Mission 草案

Claude Code 中枢采用文件工作区模式，每轮运行至少包含：

1. `MISSION.md`
2. `context.json`
3. `candidate_cases.json`
4. `fallback_decision.json`
5. `OUTPUT_CONTRACT.json`
6. `decision_template.json`
7. `decision.json`

核心 mission：

```text
你是 Custom Media Agent 2.0 的创意决策中枢，不是普通检索器，也不是后端副作用执行器。
你的任务是审美判断、案例取舍、提示词策略、生成调度和质量门禁。
本地结构化检索只提供候选证据；最终选择和组合由你裁决。
你必须直接输出最终生图 prompt 包：final_prompt、negative_prompt、provider_parameters。
你可以充分思考，但不要输出推理长文；final_prompt 应精简、可执行、适配 gpt-image-2。
输出必须是机器可执行 JSON，写入 decision.json。
不得要求人类中途阅读报告后再继续。
不得绕过版权、安全和商用风险门禁。
```

## CreativeOrchestratorDecision

核心字段：

```json
{
  "mode": "smart_enhance",
  "selected_case_ids": ["case_..."],
  "case_retrieval_plan": {
    "query_text": "luxury perfume black gold ecommerce hero",
    "category_filters": [],
    "use_case_filters": ["ecommerce"],
    "style_filters": ["luxury"],
    "risk_filters": ["exclude_protected_ip", "exclude_unlicensed_logo"],
    "limit": 6,
    "diversity_level": "medium"
  },
  "final_prompt": "Create a premium ecommerce hero image for a fictional luxury perfume bottle named Noir Halo. Use a centered black-gold glass bottle with warm amber refraction, crisp edges, controlled negative space for copy, refined studio reflections, soft key light, dramatic gold rim highlights, shallow depth of field, and a polished commercial finish. Use the selected references only as abstract evidence for lighting, composition, material handling, and premium product staging; do not copy their exact products, logos, text, layouts, or props.",
  "negative_prompt": "crowded background, watermark, logo, celebrity face, protected character, unreadable text, distorted packaging, low-resolution artifacts, direct reference reproduction",
  "provider_parameters": {
    "count": 1,
    "quality": "high",
    "aspect_ratio": "1024x1536",
    "provider_hint": "openai_gpt_image"
  },
  "prompt_rationale": "The selected cases supply premium product lighting and black-gold material cues; the final prompt keeps the user's fictional perfume as the only concrete subject.",
  "prompt_directives": {
    "visual_strategy": "premium black-gold hero product composition",
    "case_selection_rationale": "selected cases provide lighting, composition, and material cues",
    "reusable_prompt_atoms": ["dramatic rim light", "glass refraction", "controlled negative space"],
    "composition": "centered hero bottle with copy-safe margin",
    "lighting": "soft studio key light with gold rim highlights",
    "color_palette": "black, gold, amber",
    "negative_prompt_additions": ["avoid crowded background"],
    "safety_notes": ["use cases as visual structure only"]
  },
  "stage_commands": [
    {
      "stage": "retrieve_cases",
      "action": "run",
      "priority": 90,
      "reason": "candidate pool is evidence, Claude makes final selection",
      "payload": {}
    }
  ],
  "generation_directives": {
    "count": 1,
    "quality": "high",
    "aspect_ratio": "1024x1536"
  },
  "quality_gates": {
    "no_raw_case_image_copying": true,
    "premium_finish_required": true
  },
  "confidence": 0.9
}
```

## CaseStrategistAgent Instructions 草案

```text
You create case retrieval plans.

Return categories, filters, query text, diversity strategy, and risk constraints.
Do not query the database yourself.
Do not ignore user-selected template cases.
If the user selected a template, make it the primary case and only recommend supplementary cases when useful.
```

## PromptComposerAgent Instructions 草案

```text
You create ImagePromptPlan objects from the central orchestrator decision, user intent, and retrieved cases.

When CreativeOrchestratorDecision.final_prompt is present and valid:
- Use it as the ImagePromptPlan.prompt.
- Use CreativeOrchestratorDecision.negative_prompt, then append required safety negative terms if missing.
- Merge CreativeOrchestratorDecision.provider_parameters into provider_parameters.
- Record prompt_source=claude_final_prompt.

When final_prompt is absent, invalid, or the orchestrator fell back:
- Compose a local prompt from user intent, selected cases, prompt_directives, and safe reusable visual atoms.
- Avoid copying protected brands, characters, faces, and long raw prompt text.

Return a structured ImagePromptPlan.
```

## VisualCriticAgent Instructions 草案

```text
You review prompts and generated images against the user's goal.

Score visual clarity, composition, lighting, color, text readability, brand fit, and safety.
Return concise revision recommendations.
Do not approve outputs that conflict with safety decisions.
```

## CreativeRunResult

核心字段：

```json
{
  "run_id": "run_...",
  "mode": "smart_enhance",
  "intent_summary": "Create a premium ecommerce hero image for a skincare product.",
  "selected_cases": [],
  "prompt_plan": {},
  "safety_decision": {},
  "generation_jobs": [],
  "next_actions": []
}
```

完整示例见 [creative_run_result.example.json](../templates/creative_run_result.example.json)。

## ImagePromptPlan

核心字段：

```json
{
  "prompt": "A premium ecommerce hero image...",
  "negative_prompt": "avoid distorted packaging...",
  "style_basis": [],
  "user_variables": {},
  "provider_parameters": {},
  "risk_notes": []
}
```

完整示例见 [image_prompt_plan.example.json](../templates/image_prompt_plan.example.json)。

## 输出要求

Agent 对用户的可见说明应该包含：

1. 它理解的目标。
2. 使用了哪些案例作为灵感。
3. 提炼了哪些视觉要素。
4. 哪些内容因为安全或授权被替换。
5. 下一步可以如何微调。

Agent 的机器输出必须符合 schema，不能只返回自然语言。

## Prompt 版本管理

每次生成都保存：

1. `prompt_plan_version`。
2. `source_case_ids`。
3. `raw_user_input`。
4. `final_prompt`。
5. `negative_prompt`。
6. `provider_parameters`。
7. `safety_decision_id`。

修订时创建新版本，不覆盖旧版本。
