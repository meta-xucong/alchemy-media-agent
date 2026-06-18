# Alchemy Lab 质量增强与智能文案层级开发文档

## 1. 背景结论

Alchemy Lab 的 `rare-style-explorer` 当前已经能完成核心任务：

- 同一个创意可以生成多种稀有风格方向。
- 风格库、批量生成、对比网格、历史记录和收藏链路已经具备。
- 生成图片有风格差异，但精美度、商业完成度和文字设计稳定性不够。

当前主要问题不是图像 provider 失效，而是 Lab prompt composer 仍以规则拼接为主：

```text
idea
  -> rare style directives
  -> anti-drift constraints
  -> existing image generation service
```

这条链路能带来“风格”，但缺少一层真正的视觉导演判断：

- 画面主次不够明确。
- 材质、光线、色彩、镜头、版式没有被统一策展。
- 部分风格 prompt 可能重复、泛化或像关键词堆叠。
- 海报、菜单、包装、封面、活动邀请等带文字的图像，没有通用的智能文字层级规划。

本方案新增一个 **Lab-owned Quality Enhancement Layer**，放在 rare-style prompt composer 和现有图像生成服务之间。

## 2. 产品目标

目标不是让 Lab 变成 V2，也不是替代 rare-style-explorer。

目标是让 rare-style-explorer 从“风格探索工具”升级为：

```text
风格探索
  + 视觉精修
  + 大模型智能文字层级
  + 可解释对比记录
```

用户感知目标：

- 图片依然有明显风格差异。
- 结果更像完整作品，而不是风格关键词实验。
- 海报、封面、包装、菜单、邀请函等文字型创意更干净、更高级。
- 用户不需要学习 prompt engineering。

## 3. 严格边界

### 3.1 必须保留

- Lab 仍是独立于 V1/V2 的实验区。
- `rare-style-explorer` 仍是 Alchemy Lab 的第一个子模块。
- 图像生成仍复用现有 image generation service。
- 最终 prompt 必须保存在 session、variant 和历史记录中。
- 成功和失败 variant 都必须保留。

### 3.2 禁止事项

- 禁止把 Alchemy Lab 默认改成 V2 template lock。
- 禁止让 Lab 后端直接调用图像 provider SDK。
- 禁止把 V2 prompt transform 当成 Lab 的强依赖。
- 禁止为“海报文字层级”写固定公式，例如固定拆成标题、时间、地点、口号。
- 禁止用关键词规则硬编码：看到“本周五”就当时间、看到“大学生活动中心”就当地点。
- 禁止为了精致度牺牲用户明确要求的主体、产品、人物身份、活动信息或品牌信息。

## 4. 新增架构位置

新增层放在 `_compose_prompt` 之后、提交图像生成之前：

```text
Explorer Request
  -> Style Resolver
  -> Base Rare-style Prompt Composer
  -> Lab Quality Enhancement Layer
       -> Prompt Hygiene
       -> LLM Visual Art Direction
       -> LLM Smart Text Hierarchy
       -> Prompt Assembly
  -> Existing Image Generation Service
  -> Session / History / Comparison Board
```

这层是 Lab 自己的质量层，不是 V2 专用链路。

如果项目已有可复用 LLM planning service，应通过现有服务调用；如果没有，应先封装 Lab 内部文本规划适配器，再接入已有 LLM 配置。不要在 Lab 模块里散落 provider SDK 调用。

## 5. 质量增强模式

在 `ExplorationRequest` 中新增可选字段：

```text
quality_enhancement: auto | off | balanced | curated
```

默认：

```text
auto
```

模式含义：

| 模式 | 用户含义 | 后端行为 |
| --- | --- | --- |
| `off` | 原样探索 | 只使用 rare-style base prompt，不做质量增强 |
| `auto` | 自动增强 | 按任务类型、文字复杂度和批量规模决定是否调用 LLM |
| `balanced` | 精修增强 | 每个 style variant 做轻量质量增强 |
| `curated` | 策展增强 | 先让 LLM 统一规划整组方向，再生成每个 style 的精修 prompt |

UI 文案建议：

```text
质感增强：自动 / 关闭 / 精修 / 策展
```

默认 UI 只露出 `自动`，其余放进高级设置。

## 6. 智能文案层级原则

这部分是本方案最重要的规则。

海报文字、菜单文字、包装标签、封面标题、活动邀请信息、优惠券信息、招牌文字、社交媒体卡片文案，都必须走同一个 **Smart Text Hierarchy Planner**。

不要做“海报专用公式”。

### 6.1 为什么不能套公式

用户输入可能是：

- 活动海报。
- 食物菜单。
- 产品包装。
- 品牌广告。
- 展览主视觉。
- 公众号封面。
- 直播预告。
- 商场导视。
- 节日贺卡。
- 游戏卡牌。

这些场景都包含文字，但文字的作用不同。有些需要精确可读，有些只需要视觉化文字块，有些应该减少文字，有些应建议后期排版。

所以不能固定拆成：

```text
Title:
Subtitle:
Time:
Location:
CTA:
```

这会把创意压扁，也会让非海报类任务变得僵硬。

### 6.2 正确做法

统一让大模型判断：

```text
用户真正需要哪些文字被看见？
哪些文字必须精确？
哪些文字只表达视觉层级？
哪些文字应该缩短？
哪些文字会破坏画面？
哪些信息应该作为画面说明，而不是直接要求模型画出来？
```

确定后，再把判断注入最终 prompt。

### 6.3 LLM 输出不是固定公式

工程上可以要求 LLM 返回结构化 JSON，便于保存和测试。

但 JSON 里的角色、数量、文案和层级必须由 LLM 自己判断，不允许代码固定标题、时间、地点、口号这些槽位。

建议输出：

```json
{
  "has_text_intent": true,
  "text_strategy_summary": "一句自然语言总结这张图里的文字该如何服务画面。",
  "text_roles": [
    {
      "role_name": "由大模型生成的语义角色名",
      "content": "建议出现的短文本或视觉文字意图",
      "importance": "primary | secondary | tertiary | decorative",
      "rendering_policy": "exact | semantic | decorative | avoid_rendering",
      "placement_intent": "自然语言描述，不使用固定版式公式",
      "reason": "为什么这样处理"
    }
  ],
  "avoid_text": [
    "不建议直接画进图里的文字或长句"
  ],
  "postprocess_recommendation": "如果模型不适合直接生成文字，给出后期排版建议"
}
```

注意：

- `role_name` 由 LLM 生成，不是固定枚举。
- `text_roles` 可以是 0 到 6 个，不固定数量。
- `placement_intent` 是自然语言，不是固定九宫格。
- `rendering_policy` 是工程枚举，用于保护可读性和后续 UI 展示。

## 7. LLM 规划输入

Smart Text Hierarchy Planner 的输入至少包含：

```text
original_idea
normalized_idea
style_preset_snapshot
base_rare_style_prompt
exploration_mode
aspect_ratio
target_use_hint
language_hint
user_required_text_candidates
avoid_generic
```

`target_use_hint` 可以由 LLM 或轻量启发式判断，例如 poster、packaging、menu、cover、signage、social-card、portrait、product、scene。

启发式只允许作为提示，不允许直接决定文字拆分结果。

## 8. LLM 规划要求

LLM 必须完成三类判断。

### 8.1 视觉完成度判断

判断这张图要更精致，需要补足哪些艺术指导：

- 视觉中心。
- 前景、中景、背景关系。
- 主要材质与次要材质。
- 光线方向与光质。
- 色彩关系。
- 版式留白。
- 摄影或插画完成度。
- 画面密度。
- 风格与主体的冲突点。

### 8.2 风格边界判断

判断 rare style 应该如何应用：

- 是主风格，还是表面纹理。
- 是否适合主体。
- 是否需要降低强度。
- 哪些风格特征不能覆盖主体可读性。
- 哪些关键词应从 final prompt 中移除或降权。

### 8.3 文字层级判断

判断文字应该如何服务画面：

- 是否需要文字。
- 哪些文字必须精确。
- 哪些文字应缩短为视觉文案。
- 哪些文字只作为图像语义，不要求模型画成可读字。
- 是否需要提示“保留干净文字区域，后期排版”。

这一步必须由 LLM 完成，不能用固定提取公式替代。

## 9. 最终 Prompt 组装规则

最终 prompt 由四部分组成：

```text
1. 用户创意与主体
2. rare style 方向
3. LLM 质量增强艺术指导
4. LLM 智能文案层级与避免项
```

要求：

- 不要重复同一句风格描述。
- 不要堆叠过多抽象形容词。
- 不要把内部 metadata、style id、session id、provider id 写进 prompt。
- 不要把长段活动说明原样塞给图像模型。
- 对必须精确的文字，明确标记为 exact text。
- 对不适合直接生成的长文案，要求画面保留清晰排版空间。

## 10. 数据结构扩展

### 10.1 ExplorationRequest

新增：

```text
quality_enhancement?: auto | off | balanced | curated
```

### 10.2 ComposedPrompt.prompt_metadata

新增：

```json
{
  "quality_enhancement": {
    "mode": "auto",
    "applied": true,
    "strategy": "balanced",
    "llm_provider": "existing-runtime-llm",
    "llm_model": "model-name-if-available",
    "text_hierarchy": {},
    "art_direction_summary": "",
    "prompt_hygiene": {
      "deduplicated": true,
      "removed_generic_lines": []
    },
    "error": null
  }
}
```

### 10.3 Lab History

历史记录应保存：

```text
quality_enhancement_mode
quality_enhancement_applied
text_hierarchy_summary
art_direction_summary
```

UI 展示可以简化为：

```text
增强：自动 · 已精修
文案：已智能整理
```

## 11. 失败策略

质量增强失败不能直接导致整组生图失败，除非用户选择了未来可能增加的强制精修模式。

默认策略：

```text
LLM quality pass failed
  -> record metadata
  -> use base rare-style prompt
  -> continue generation
```

但对于文字层级，禁止用固定公式兜底。

如果 LLM 不可用，只能：

- 保留用户原始文字意图。
- 做基本去重和长度保护。
- 记录 `text_hierarchy.applied=false`。
- 不生成伪造的标题/时间/地点结构。

## 12. UI 调整

### 12.1 桌面端

在 Alchemy Lab rare-style-explorer 的高级设置里新增：

```text
质感增强
自动 / 关闭 / 精修 / 策展
```

说明文案：

```text
自动会让系统判断是否需要精修画面和整理画中文字；策展会更慢，但更适合海报、包装、封面等成片方向。
```

结果卡片详情中新增：

```text
质感增强：自动 · 已精修
文字层级：已由大模型整理
```

### 12.2 H5

H5 不新增复杂区域。

建议放在现有参数控制区里，用一行分段控件或折叠项：

```text
质感：自动
```

点开后显示四档。

## 13. 后端开发任务

### 13.1 新增质量增强服务

建议位置：

```text
src_skeleton/app/services/alchemy_lab_quality.py
```

职责：

- 输入 `ExplorationRequest`、`StylePreset`、base `ComposedPrompt`。
- 调用 prompt hygiene。
- 按模式决定是否调用 LLM。
- 调用 Smart Text Hierarchy Planner。
- 返回 enhanced prompt 和 metadata。

如果实现者认为单文件更稳，也可以先放在 `alchemy_lab.py` 内部，但必须保持函数边界清楚，避免 `_compose_prompt` 继续膨胀。

### 13.2 接入点

在 `create_exploration_session()` 中：

```text
base_prompts = [_compose_prompt(...)]
enhanced_prompts = [enhance_lab_prompt(...)]
session.prompts = enhanced_prompts
```

必须发生在 variant 创建前。

### 13.3 LLM 调用适配

使用已有运行时 LLM 配置。

优先级：

1. 项目现有 LLM planning service。
2. 项目现有 work-intensity / prompt-planning 能力。
3. Lab 内部最小 LLM planner adapter。

禁止直接在多个函数里手写 provider SDK 调用。

### 13.4 Prompt Hygiene

可以确定性处理：

- 去掉重复行。
- 删除空行。
- 限制 final prompt 长度。
- 合并重复 negative directives。
- 移除内部 id。

不可以确定性处理：

- 文案层级拆分。
- 活动信息归类。
- 哪些文字该大、哪些该小。
- 哪些文字应该保留、缩短或后期排版。

这些必须交给 LLM。

## 14. 测试计划

### 14.1 单元测试

新增测试：

- `quality_enhancement=off` 时 prompt 与 base composer 等价。
- `quality_enhancement=balanced` 时会产生 quality metadata。
- LLM planner 输出的 `text_roles` 数量不固定。
- 文字层级 planner 不依赖固定 title/time/location 字段。
- LLM 失败时不会阻断生成，且不会套用固定文字公式兜底。
- prompt hygiene 会去重，但不会删除用户明确要求。

### 14.2 API 测试

新增测试：

- `/api/lab/rare-style-explorer/sessions` 接受 `quality_enhancement`。
- session response 的 `prompts[].prompt_metadata.quality_enhancement` 可见。
- history 中保存增强状态。
- 原有 batch cap、partial success、favorite、history isolation 不回归。

### 14.3 实盘测试

至少跑三组：

1. 活动海报：

```text
生成一个万圣节南瓜派对海报，本周五18:30，大学生活动中心
```

预期：LLM 自主决定文字层级，不固定拆槽；画面更干净。

2. 食物海报：

```text
草莓奶油蛋糕新品上市海报，甜美精致风格
```

预期：减少无意义长字，强化主视觉、材质、色彩和留白。

3. 产品包装：

```text
一款青柠薄荷气泡水包装设计，适合夏季便利店货架
```

预期：文字层级按包装逻辑处理，而不是按海报公式处理。

每组至少对比：

```text
quality_enhancement=off
quality_enhancement=balanced
quality_enhancement=curated
```

## 15. 验收标准

后端验收：

- `quality_enhancement` 字段被 API 接收、校验、保存。
- base prompt 和 enhanced prompt 都可追踪。
- Smart Text Hierarchy Planner 由 LLM 完成。
- 没有固定 title/time/location 公式。
- LLM 失败不阻断默认生成。
- 历史记录展示增强状态。

前端验收：

- 桌面端能选择质感增强模式。
- H5 能选择质感增强模式，控件不拥挤。
- 结果卡能显示增强状态和文案层级状态。
- prompt 详情能看到最终 prompt。

质量验收：

- 同一组 idea 下，`balanced` 通常应比 `off` 更完整、更干净。
- `curated` 通常应比 `balanced` 更统一、更像成片方向。
- 文字型任务不能出现明显公式化拆解痕迹。
- 非文字型任务不能被强行塞入文字层级。

## 16. 推荐开发顺序

1. 扩展 schema 和 Pydantic request。
2. 新增 prompt metadata 字段。
3. 实现 prompt hygiene。
4. 实现 LLM Smart Text Hierarchy Planner。
5. 实现 Lab Quality Enhancement Layer。
6. 接入 `create_exploration_session()`。
7. 更新历史记录 metadata。
8. 更新桌面和 H5 UI。
9. 增加单元、API 和前端静态测试。
10. 用海报、食物、包装各跑一组 off/balanced/curated 对比。

## 17. 最终原则

```text
rare style 决定探索方向。
质量增强决定作品完成度。
文字层级由大模型判断，而不是代码公式拆槽。
```
