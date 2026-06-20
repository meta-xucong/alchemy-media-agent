# Alchemy Lab 智能意图导演与参考约束规划开发文档

## 1. 背景结论

这条技术路线是正确的：

```text
Alchemy Lab 已有中枢大脑
  -> 继续负责判断与规划
  -> 不新增第二套 LLM/provider SDK
  -> 让上传图和纯文字输入都先经过同一个意图导演层
```

当前 `rare-style-explorer` 已经有：

- Lab-owned 上传模块。
- Lab-owned 参考图 policy。
- Lab-owned quality enhancement。
- `ask_llm_json_plan` 形式的 LLM JSON planning 中枢。

但现在缺一层：

```text
用户输入/上传图到底意味着什么？
这张图应该作为产品、主体、Logo、材质，还是构图参考？
哪些东西必须锁定？
哪些东西可以被稀有风格改变？
如果用户没传图，只写文字，系统应该如何理解这次探索的主题和随机范围？
```

本方案新增 **Lab Intent Director**：

```text
用户文字
  + 可选上传图
  + 可选用户手动设置
  -> Lab Intent Director
  -> Reference Policy / Style Routing / Prompt Composer / Quality Enhancement
```

它不是新 Agent，也不是 V2 Claude 编排。它只是 Alchemy Lab 内部的意图判断层，复用当前 Lab 的 LLM 中枢能力。

## 2. 产品目标

用户不用理解复杂 prompt，也不用手动写参考图约束。

上传图时，系统能自动判断：

- 这是什么类型的图。
- 它应该如何参与生成。
- 它要锁定哪些视觉信息。
- 稀有风格可以改哪些部分。
- 是否应该限制随机风格范围。

纯文字输入时，系统也要自动判断：

- 这是产品图、海报、人物、食物、包装、建筑、场景还是抽象风格探索。
- 是否是文字型任务。
- 随机风格应该更偏哪些 family。
- 需要避免哪些明显不兼容的风格方向。

短规则：

```text
Intent Director 先理解任务。
Rare Style Explorer 再探索风格。
Quality Enhancement 最后提高完成度。
```

## 3. 严格边界

### 3.1 必须做

- 复用现有 Lab LLM planning 中枢，例如 `ask_llm_json_plan`。
- 有图和无图都走同一个意图判断入口。
- 结果必须保存到 session、prompt metadata 和 Lab history 摘要。
- 用户手动指定的 role、strength、style 选择优先级高于 LLM 推荐。
- Intent Director 只做判断和约束规划，不直接调用 image provider。
- Director 失败不能阻断默认生成。

### 3.2 禁止做

- 禁止新增一套独立 LLM provider SDK 调用。
- 禁止把 Lab 路由到 V2 creative runs。
- 禁止复用 V2 upload runtime。
- 禁止让 Director 覆盖用户明确选择的 rare style。
- 禁止让 Director 把参考图变成全新创意。
- 禁止在最终 prompt、公共历史或 UI 中暴露 `asset_id`、`storage_path`、`source_url`、provider、API 或内部 repository 信息。
- 禁止假装“看见了图片”。如果当前 LLM adapter 只能接收文字摘要，必须在 metadata 中标记 `vision_source=local_brief_only` 或 `confidence=low`。

## 4. 架构位置

新增层放在 request normalize 之后、style resolve 和 prompt compose 之前：

```text
Explorer Request
  -> Request Normalize
  -> Lab Intent Director
       -> text-only intent planning
       -> reference-image intent planning
       -> style compatibility hints
       -> prompt constraint plan
  -> Reference Policy
  -> Style Resolver
  -> Base Rare-style Prompt Composer
  -> Lab Quality Enhancement
  -> Existing Image Generation Service
  -> Lab Session / Comparison Board / Lab History
```

推荐新增模块：

```text
src_skeleton/app/services/
    alchemy_lab_intent_director.py
```

该模块只调用现有 LLM planning adapter，不直接写 OpenAI、Anthropic、Kimi 或 image provider SDK。

## 5. 中枢大脑复用方式

当前最小开发路线：

```text
alchemy_lab_intent_director.py
  -> app.services.work_intensity.ask_llm_json_plan(...)
```

这与 `alchemy_lab_quality.py` 的方式一致。

### 5.1 为什么这是最小正确路线

- 现有配置已经有默认 LLM provider、fallback provider、timeout、JSON parsing。
- 现有质量增强层已经证明 Lab 可以用 JSON planner 做稳定结构化输出。
- 不需要新增密钥、不需要新增 provider router、不需要前端暴露复杂设置。
- 后续如果要支持真正 multimodal LLM，只需要扩展 `ask_llm_json_plan` 的输入能力，而不是改 Lab 业务层。

### 5.2 图像理解的真实边界

要特别注意：

```text
LLM reasoning != LLM vision
```

如果当前中枢只能收到 JSON 文字，它只能基于：

- 本地图片尺寸。
- 颜色 palette。
- 用户 notes。
- 文件名。
- 已有 `LabUploadedAsset.brief`。

这不足以稳定判断复杂图片风格。

因此开发时应分两级：

```text
Level 1：text + local brief director
  用现有 brief 和用户文字做约束判断，低成本可上线。

Level 2：vision evidence director
  在同一个 LLM adapter 里增加可选 image evidence 能力，或接入项目已有 vision captioner。
  Lab 业务层仍只调用 Intent Director，不直接碰 provider SDK。
```

验收时不能把 Level 1 说成“精确看图”。如果没有视觉模型参与，metadata 必须清楚记录：

```json
{
  "vision_source": "local_brief_only",
  "confidence": "low"
}
```

如果有真实图像理解能力，记录：

```json
{
  "vision_source": "llm_vision",
  "confidence": "medium|high"
}
```

## 6. 统一输入：有图与无图

Intent Director 永远运行，区别只是证据来源不同。

### 6.1 有上传图

输入：

```text
idea
reference_assets
asset brief
user selected role/strength
user notes
mode/family/aspect/quality settings
selected styles or auto style selection intent
```

输出：

```text
每张图的用途判断
推荐 role
推荐 constraint_strength
必须保留项
允许变化项
禁止变化项
provider input requirement
style compatibility hints
```

### 6.2 无上传图

输入：

```text
idea
mode/family/aspect/quality settings
selected styles or auto style selection intent
```

输出：

```text
target_use
subject_kind
main_subject
text_intent
preferred style families
avoid style families
prompt constraints
quality hints
```

无图时不生成 reference policy，但仍生成 `intent_plan`，用于：

- 自动选择更合理的随机风格范围。
- 给 prompt composer 更清晰的主体边界。
- 给 quality enhancement 更稳定的上下文。

## 7. 数据结构

### 7.1 LabIntentPlan

建议结构：

```json
{
  "source": "llm_intent_director",
  "applied": true,
  "input_mode": "text_only | text_plus_reference",
  "vision_source": "none | local_brief_only | llm_vision",
  "confidence": "low | medium | high",
  "target_use": "product | poster | portrait | food | packaging | logo | scene | material | abstract | image_exploration",
  "subject_kind": "natural-language subject type",
  "main_subject": "natural-language main subject",
  "user_goal_summary": "short user-facing summary",
  "reference_directives": [],
  "style_routing": {},
  "prompt_constraints": {},
  "quality_hints": {},
  "warnings": []
}
```

### 7.2 ReferenceDirective

每张参考图一个 directive：

```json
{
  "role": "product_reference",
  "recommended_role": "product_reference",
  "constraint_strength": "strong",
  "recommended_strength": "strong",
  "role_source": "user | llm | upload_default | fallback",
  "lock_constraints": [
    "保留白色塑料瓶身比例",
    "保留瓶盖结构",
    "保留标签区域位置和品牌识别"
  ],
  "allow_transformations": [
    "背景",
    "光线",
    "版式",
    "稀有风格媒介语言"
  ],
  "forbidden_changes": [
    "不要改成玻璃瓶",
    "不要改变品牌识别",
    "不要改变产品比例"
  ],
  "provider_input_requirement": "required | preferred | optional | brief_only",
  "compatibility_note": "风格应作用于场景与视觉语言，不覆盖产品本体。"
}
```

公开 metadata 不得包含源图内部路径或私有 asset id。内部 plan 可以保存内部 id，但 public view 必须脱敏。

### 7.3 StyleRoutingPlan

```json
{
  "manual_styles_respected": true,
  "auto_selection_scope": "full_library | compatible_families | user_family",
  "preferred_families": ["product", "photography", "graphic"],
  "avoid_families": ["character"],
  "style_strength_guidance": "rare style remains primary; keep product recognizability",
  "reason": "产品参考图强约束，随机风格应优先抽产品、摄影、平面、材质相关方向。"
}
```

重要规则：

- 用户手动选了 styles 时，不允许 Director 删除或替换。
- 用户没有手动选 styles 时，Director 可以影响自动抽样范围。
- 用户指定 `style_family` 时，Director 只能给 warning 或排序建议，不能硬覆盖。

### 7.4 PromptConstraintPlan

```json
{
  "must_keep": [
    "主体身份",
    "产品比例",
    "Logo/标签位置"
  ],
  "may_change": [
    "背景",
    "光线",
    "稀有风格表达",
    "材质氛围"
  ],
  "avoid": [
    "风格覆盖主体识别",
    "随机无关文字",
    "改变产品包装结构"
  ],
  "director_summary": "参考图决定产品边界，稀有风格决定视觉语言。"
}
```

## 8. 优先级规则

### 8.1 手动设置优先

冲突时优先级：

```text
1. 用户明确文字要求
2. 用户手动 role / strength / selected styles
3. Intent Director 推荐
4. 上传素材默认 role / strength
5. 当前确定性 fallback
```

如果用户手动把图设为“材质/色彩参考”，Director 不能擅自改成“产品参考”。它只能提示：

```text
系统判断这张图也可能是产品参考，但已按你的选择作为材质参考使用。
```

### 8.2 稀有风格优先

Director 不能让所有结果都变成上传图原始风格。

正确关系：

```text
参考图锁定主体边界。
稀有风格决定视觉变化。
质量增强让融合更精致。
```

### 8.3 Quality Enhancement 不重复判断

Intent Director 负责“这次任务是什么、约束是什么”。

Quality Enhancement 负责“怎么让每个风格结果更像成片”。

因此 `alchemy_lab_quality.py` 的 LLM payload 应加入 `intent_plan`，避免它重新发明一套参考图含义。

## 9. 后端接入点

### 9.1 ExplorationRequest

新增可选字段：

```text
intent_director: auto | off
```

默认：

```text
auto
```

说明：

- `auto`：默认执行。
- `off`：开发/调试或用户明确不需要时关闭，走当前旧流程。

前端 MVP 不一定要暴露这个开关，可以只在高级设置或调试信息中显示。

### 9.2 create_exploration_session

推荐执行顺序：

```text
normalize_request()
intent_plan = await plan_lab_intent(request, reference_assets)
reference_plan = build_lab_reference_plan(..., intent_plan=intent_plan)
selected_styles = resolve_styles(..., intent_plan=intent_plan)
base_prompt = compose_prompt(..., intent_plan=intent_plan, reference_plan=reference_plan)
enhanced_prompt = enhance_lab_prompt(..., intent_plan=intent_plan)
run_batch()
```

### 9.3 alchemy_lab_reference_policy.py

需要支持：

```text
build_lab_reference_plan(..., intent_plan=None)
```

应用规则：

- 如果用户显式传入 role/strength，用用户值。
- 如果用户没有显式设置，用 Director 推荐。
- 如果 Director 没有推荐，用上传 asset 默认。
- 如果仍没有，用当前 fallback。

### 9.4 style resolver

自动抽样时应用 Director：

```text
if no selected_styles and intent_plan.style_routing.preferred_families:
    sample from compatible families first
else:
    current behavior
```

手动选 styles 时：

```text
preserve selected styles
record compatibility warnings only
```

### 9.5 prompt composer

最终 prompt 需要有一段自然语言约束：

```text
意图导演约束：参考图锁定产品外观、白色材质、瓶盖结构和标签区域；稀有风格只改变背景、光线、版式和视觉媒介语言。
```

禁止写入内部 id。

## 10. 可选 API：意图预览

为了让网页用户在生成前看到系统判断，可以新增：

```text
POST /api/lab/rare-style-explorer/intent-preview
```

请求：

```json
{
  "idea": "以参考图中的白色工业瓶生成高端产品海报",
  "reference_assets": [
    {
      "asset_id": "lab_asset_xxx",
      "role": "auto",
      "constraint_strength": "auto",
      "notes": ""
    }
  ],
  "mode": "product",
  "style_family": "auto",
  "aspect_ratio": "portrait"
}
```

响应只返回脱敏结果：

```json
{
  "summary": "系统判断：产品参考 · 强约束",
  "must_keep": ["瓶身比例", "白色材质", "瓶盖结构", "标签位置"],
  "may_change": ["背景", "光线", "版式", "稀有风格语言"],
  "avoid": ["不要改成玻璃瓶", "不要丢失品牌识别"],
  "recommended_style_scope": "产品、摄影、平面、材质相关风格优先",
  "confidence": "medium",
  "warnings": []
}
```

MVP 可以不先做 preview endpoint，直接在 session 创建时运行 Director。但如果要让用户“确认系统理解是否正确”，这个 endpoint 很有价值。

## 11. 前端设计

### 11.1 桌面版

在参考图片区域和创意描述下方显示一块轻量摘要：

```text
智能判断
产品参考 · 强约束

保留：瓶身比例、白色材质、瓶盖结构、标签位置
可变：背景、光线、版式、稀有风格语言
避免：改成玻璃瓶、丢 Logo、改变产品比例
```

操作：

```text
重新判断
采用判断
手动调整
```

如果没有上传图：

```text
智能判断
产品海报 · 适合产品/摄影/平面风格
```

不要做成长篇解释卡片。默认显示 1 到 2 行摘要，点击展开查看详情。

### 11.2 H5

H5 采用卡片式：

```text
智能判断
产品参考 · 强约束
```

点击进入详情页或弹层：

- 保留项。
- 可变项。
- 避免项。
- 手动调整入口。

H5 不要把所有约束平铺在主页面，避免页面过长。

## 12. LLM Prompt 设计

### 12.1 System Prompt 要点

```text
You are Alchemy Lab's Intent Director for rare-style image exploration.
Return JSON only.
Do not reveal chain-of-thought.
Decide what the user wants, how uploaded references should be used, and how random rare-style selection should be scoped.
Do not replace the user's selected styles.
Do not invent internal ids or expose storage paths.
Rare style remains the exploration variable; references constrain subject/product/logo/material/composition only.
```

### 12.2 User Payload

```json
{
  "idea": "...",
  "mode": "product",
  "style_family": "auto",
  "aspect_ratio": "portrait",
  "selected_styles": [],
  "reference_assets": [
    {
      "declared_role": "auto",
      "declared_strength": "auto",
      "user_notes": "",
      "brief": {
        "visual_summary": "...",
        "image": {"width": 1448, "height": 1086},
        "palette": []
      }
    }
  ],
  "required_json_shape": {
    "target_use": "product|poster|portrait|food|packaging|logo|scene|material|abstract|image_exploration",
    "subject_kind": "string",
    "main_subject": "string",
    "user_goal_summary": "string",
    "reference_directives": [],
    "style_routing": {},
    "prompt_constraints": {},
    "quality_hints": {},
    "warnings": []
  }
}
```

## 13. 失败策略

Director 失败时：

```text
record metadata
use current deterministic reference policy
use current style resolver
continue generation
```

metadata：

```json
{
  "source": "local_fallback",
  "applied": false,
  "error": {
    "type": "TimeoutError",
    "message": "..."
  }
}
```

不要因为 Director 失败阻断生图。

例外：

- 用户上传了 required/strong 参考图。
- provider 不支持 input image。

这种情况仍应按照 reference policy 返回明确错误或 reroute，不能静默文本降级。

## 14. 测试计划

### 14.1 单元测试

- `intent_director=auto` 且无图时会生成 text-only intent plan。
- 有产品参考图 brief 时，fake LLM 推荐 `product_reference / strong`，reference policy 使用该推荐。
- 用户手动 role/strength 覆盖 LLM 推荐。
- 用户手动 selected styles 不被 Director 删除。
- 自动抽样时，Director 的 preferred families 能影响随机范围。
- Director 失败时，当前流程继续，metadata 记录 fallback。
- Director 不向 public history 泄露 asset id、source_url、storage_path、filename。

### 14.2 API 测试

- session response 包含 `intent_director` metadata。
- comparison board card 可显示 intent summary。
- public Lab history 只显示脱敏摘要。
- `intent-preview` endpoint 如果实现，返回脱敏摘要并不触发生成。

### 14.3 前端静态测试

- 桌面端存在智能判断摘要 UI。
- H5 存在智能判断卡片 UI。
- 上传图后 session payload 可携带 role/strength/notes 与 Director 预览状态。
- 无上传图时也不会跳过 intent flow。

### 14.4 实盘测试

至少跑四组：

1. 产品参考图：白色工业瓶，随机 4 张稀有风格。
2. 人像参考图：虚构成人肖像，随机 4 张风格。
3. 无图文字：端午节祝贺海报，随机 4 张竖图。
4. 无图文字：青柠薄荷气泡水包装设计，随机 4 张。

判断标准：

- 上传图核心约束可见。
- 稀有风格差异仍明显。
- 无图输入能选到更合理的随机范围。
- Director 摘要与最终 prompt 一致。
- 失败时仍能继续生成或给出明确错误。

## 15. 开发顺序

1. 新增 `alchemy_lab_intent_director.py`。
2. 定义 `LabIntentPlan` 的 Pydantic 或 dict contract。
3. 用 `ask_llm_json_plan` 实现 text-only 与 text-plus-reference planner。
4. 将 intent plan 接入 `create_exploration_session()`。
5. 改造 `build_lab_reference_plan(..., intent_plan=...)`。
6. 改造 style resolver，使自动抽样可读取 compatible families。
7. 将 intent plan 注入 prompt composer 和 quality enhancement payload。
8. 持久化 session、prompt、variant、history 中的脱敏 metadata。
9. 增加桌面/H5 智能判断摘要 UI。
10. 增加单元、API、前端静态和实盘测试。

## 16. 验收标准

后端：

- 有图和无图都能生成 intent plan。
- Director 复用现有 Lab LLM 中枢，不新增散落 provider SDK。
- 用户手动设置优先于 Director 推荐。
- Director 能影响自动随机风格范围，但不能覆盖手动选风格。
- Reference policy 能使用 Director 推荐生成更准确的约束。
- Quality enhancement 能读取 Director 输出，不重复发明参考图含义。
- LLM 失败不阻断默认生成。
- 公共历史不泄露上传源图信息。

前端：

- 用户能看到系统对参考图或文字任务的简短判断。
- 用户能手动调整系统判断。
- 桌面端整洁，不平铺大量解释。
- H5 采用卡片式详情，不拉长主页面。

质量：

- 产品参考图测试中，系统能自动形成“产品参考/强约束/保留产品外观/允许风格改背景和媒介语言”的判断。
- 无图文字测试中，系统能自动判断目标类型和随机风格范围。
- 稀有风格依然是视觉探索变量，不被参考图或增强模块覆盖。

## 17. 最终原则

```text
用户不需要写约束。
Intent Director 替用户理解约束。
Reference Policy 执行约束。
Rare Style Explorer 负责风格探索。
Quality Enhancement 负责作品完成度。
```
