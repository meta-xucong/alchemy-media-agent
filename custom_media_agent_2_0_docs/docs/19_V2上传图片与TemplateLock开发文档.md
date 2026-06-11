# 19. V2 上传图片与 Template Lock 开发文档

> 当前状态：本文的 Template Lock 和上传素材意图原则仍是当前 V2 的硬约束。文中的 Claude Code Creative Orchestrator 指 Claude Code 创意决策中枢；模型源可以在 Claude Code 背后切换，但不能绕过 Template Lock、Asset Binding 和 V2 原生 provider input image 规则。

## 1. 目标

V2 需要具备上传图片、识图、提炼视觉信息、根据原图约束优化生图的能力，同时不能破坏当前已经调好的模板逻辑。

核心目标：

1. 支持用户上传图片作为风格、主体、Logo、人脸、背景、构图、色彩等参考。
2. 让 Claude Code Creative Orchestrator 统一读取案例证据和上传图证据。
3. 有手选案例时，保持案例最高优先级，上传图只能作为模板内变量。
4. 无手选案例时，Claude 可以自由融合上传图和自动召回案例。
5. 生图 provider 必须在能力允许时接收原始上传图作为 `input_images`，不能只靠文字描述硬猜。
6. 复检层必须验证上传图约束是否被遵守。

## 2. 最高原则

```text
有选中案例：案例主导，素材入模。
无选中案例：Claude 自由融合，素材和案例共同参与判断。
```

进一步展开：

1. 用户手选案例是最高视觉锚点。
2. Claude Code 是中枢裁判，但不能推翻手选案例的最高优先级。
3. 上传图片是证据和变量，不是默认的新模板。
4. 上传图可以替换主体、补充 Logo、保留人物身份、提供真实商品外观。
5. 上传图默认不能覆盖手选案例的构图、版式、光影、背景密度、空间层级、整体审美和色彩节奏。
6. 如果用户明确要求上传图覆盖模板风格，前端必须让用户切换到“无模板自由融合”或显式确认“解除模板锁定”。

## 3. 三方协作关系

### 3.1 手选案例

手选案例负责：

1. 构图骨架。
2. 空间层级。
3. 光影策略。
4. 背景密度。
5. 版式和信息结构。
6. 整体审美方向。
7. 色彩节奏和强调色使用方式。

手选案例不负责：

1. 真实商品身份。
2. 用户上传的 Logo 细节。
3. 用户上传的人脸身份。
4. 必须出现的自有素材内容。

### 3.2 上传图片

上传图片负责：

1. 真实商品外观。
2. Logo 和品牌元素。
3. 人脸或人物身份。
4. 用户指定背景。
5. 局部材质、色彩、构图参考。
6. 用户认为必须保留的视觉细节。

上传图片默认不负责：

1. 推翻手选案例的整体模板。
2. 改写模板构图。
3. 改写模板光影和背景密度。
4. 把模板风格替换成上传图风格。

### 3.3 Claude Code 中枢

Claude Code 负责：

1. 判断用户真实意图。
2. 阅读手选案例 `visual_signal_brief`。
3. 阅读上传图 `AssetBrief`。
4. 生成 `TemplateLockContract`。
5. 生成 `AssetBindingPlan`。
6. 输出最终 `CreativeOrchestratorDecision`。
7. 判断冲突并按规则降级或重写。

Claude Code 不允许：

1. 在有手选案例时改选其他案例作为主模板。
2. 让上传图覆盖手选案例的模板结构。
3. 把上传图背景当成新背景，除非素材角色明确是 `background_reference` 且用户要求替换背景。
4. 在最终 prompt 中泄漏 `case_id`、`asset_id`、`provider_id`、`source_url`、API 或仓库标识。

## 4. 模式定义

### 4.1 Template Lock 模式

触发条件：

```text
request.template_case_id 非空
```

规则：

1. `selected_case_ids[0]` 必须是 `template_case_id`。
2. `TemplateLockContract.priority` 必须是 `highest`。
3. 上传图只能绑定到模板 slot。
4. Claude 输出 prompt 时必须显式保留模板结构。
5. 如果上传图风格与模板冲突，保留上传图身份信息，丢弃上传图风格信息。

示例：

```text
黑金香水模板 + 蓝白护肤品上传图
=> 保留黑金模板的棚拍、光影、构图、空间层级；
=> 主体替换成蓝白护肤品；
=> 蓝白包装颜色作为商品身份保留，但不把整张图改成普通蓝白电商图。
```

### 4.2 Free Agent 模式

触发条件：

```text
request.template_case_id 为空
```

规则：

1. Claude 可以自由判断上传图和召回案例的关系。
2. 上传图可以成为主要风格来源。
3. Claude 可以自动选择最合适案例辅助增强。
4. 如果上传图是硬约束素材，最终 provider 应接收对应 `input_images`。

## 5. 素材角色

V2 上传图片必须带角色。前端可以让用户手动选择，也可以让视觉理解 agent 先自动识别，用户再修改。

建议角色：

1. `style_reference`：风格参考，只影响色调、光线、质感和审美。
2. `subject_reference`：主体参考，如商品、包装、服装、物体。
3. `logo_reference`：Logo 或品牌元素。
4. `face_reference`：人物脸或身份参考。
5. `background_reference`：背景参考或背景替换。
6. `composition_reference`：构图、镜头角度、主体位置参考。
7. `color_reference`：色彩和强调色参考。
8. `negative_reference`：不要生成类似内容的反向参考。

约束强度：

1. `required`：必须遵守。
2. `strong`：强参考，冲突时仅次于手选模板。
3. `soft`：弱参考，只在不冲突时采用。

## 6. TemplateLockContract

当用户手选案例时，系统必须生成不可覆盖合同：

```json
{
  "contract_id": "tlc_...",
  "locked_case_id": "case_...",
  "priority": "highest",
  "locked_elements": [
    "composition",
    "spatial_hierarchy",
    "lighting",
    "background_density",
    "color_rhythm",
    "mood",
    "layout_structure",
    "typography_or_annotation_treatment"
  ],
  "replaceable_slots": [
    "main_subject",
    "product_identity",
    "logo",
    "face_identity",
    "copy_content",
    "minor_props"
  ],
  "conflict_policy": "preserve_template_structure_bind_assets_to_slots"
}
```

合同来源：

1. 手选案例的 `PromptCase`。
2. 手选案例的 `CaseProfile`。
3. 手选案例的 `visual_signal_brief`。
4. 用户输入中明确保留或替换的内容。

## 7. AssetBrief

上传图识别后生成 `AssetBrief`：

```json
{
  "asset_id": "asset_...",
  "role": "subject_reference",
  "constraint_strength": "required",
  "source_uri": "v2/uploads/...",
  "mime_type": "image/png",
  "image_size": {"width": 1200, "height": 1200},
  "visual_summary": "white and blue skincare bottle with rounded pump cap",
  "identity_requirements": [
    "preserve product shape",
    "preserve blue-white packaging color",
    "preserve readable logo shape if provider supports it"
  ],
  "style_signals": [
    "clean blue-white product identity"
  ],
  "detected_text": [],
  "usable_as_input_image": true,
  "provider_input_required": true
}
```

字段说明：

1. `visual_summary` 给 Claude 理解。
2. `identity_requirements` 给 prompt 和复检使用。
3. `style_signals` 只在允许影响风格时使用。
4. `provider_input_required=true` 表示最终生图不能只靠文字，必须把该图传给 provider。

## 8. AssetBindingPlan

Claude 输出或本地规则兜底生成 `AssetBindingPlan`：

```json
{
  "template_lock_contract_id": "tlc_...",
  "bindings": [
    {
      "asset_id": "asset_...",
      "role": "subject_reference",
      "binding_slot": "main_subject",
      "allowed_to_override": [
        "product_shape",
        "packaging_details",
        "logo_appearance"
      ],
      "not_allowed_to_override": [
        "template_composition",
        "template_lighting",
        "template_mood",
        "template_layout",
        "template_background_density"
      ],
      "provider_input_required": true,
      "prompt_instruction": "Replace the original template subject with this uploaded product while preserving the selected template's composition and lighting."
    }
  ],
  "conflicts": [
    {
      "type": "style_conflict",
      "resolution": "keep asset identity, ignore asset overall style because selected template is locked"
    }
  ]
}
```

### 8.1 AssetIntentProfile 与融合策略

V2 不允许只根据 `role` 粗暴处理上传素材。每个 `AssetBinding` 必须补充一层结构化融合策略：

```json
{
  "fusion_mode": "logo_product_surface",
  "placement_intent": {
    "mode": "scene_surface",
    "target_surface": "apparel_chest_or_surface",
    "target_label": "衣服胸口或服装表面",
    "source": "user_prompt",
    "instruction": "Fuse the uploaded asset into 衣服胸口或服装表面 as a real element inside the generated scene."
  },
  "review_expectations": [
    "uploaded_logo_visible_on_scene_surface",
    "no_canvas_corner_logo_unless_requested",
    "no_invented_logo_text"
  ]
}
```

判断优先级：

```text
用户素材备注 > 用户提示词 > 上传素材视觉摘要 > role 默认规则
```

关键规则：

1. `logo_product_surface`：Logo 要进入衣服、包装、瓶身、设备、墙面、招牌等画面内物体表面，必须作为真实参考图传给 provider，不得放成角标、水印、页脚或独立贴片。
2. `logo_canvas_brand_mark`：Logo 作为海报品牌区、页眉、页脚或角标，可在画布品牌区出现，但仍不得由模型虚构。
3. `subject_identity`：上传主体是商品/人物/物体身份约束，必须进入 provider input images。
4. `style_signal`、`composition_signal`、`color_signal`：只提供兼容的审美信号；有模板锁时不得覆盖模板结构。
5. `background_identity`：只有用户明确要求使用或替换背景时才可强绑定背景；否则降级为背景氛围参考。

Claude Code 必须读取并遵守这些字段。它可以优化提示词、补充审美语言和案例融合方式，但不能把结构化融合意图改写成另一个用途。

## 9. Claude 工作区输入

Claude workspace 需要新增：

```text
uploaded_assets.json
template_lock_contract.json
asset_binding_policy.json
```

Claude prompt 必须包含规则：

```text
If template_case_id is set, the selected template is the highest-priority visual anchor.
Uploaded assets must be bound into replaceable template slots.
Uploaded assets may preserve identity, product shape, logo, face, and required details.
Uploaded assets must not override the selected template's composition, lighting, mood, layout, background density, or overall visual rhythm unless the user explicitly unlocks the template.
fusion_mode, placement_intent, target_surface and review_expectations are hard asset-intent constraints.
```

## 10. Provider 调用

最终生图请求必须分两类处理：

1. `prompt-only`：上传图只是软风格参考，且 provider 不需要原图。
2. `prompt + input_images`：上传图包含商品、Logo、人脸、背景等硬约束。

规则：

1. `provider_input_required=true` 的素材必须进入 provider input images。
2. 如果当前 provider 不支持 input images，后端必须返回可解释错误或提示用户切换 provider。
3. Claude 的 `final_prompt` 只负责描述融合策略，不能替代原图输入。
4. 历史记录必须保存使用了哪些 asset、角色、约束强度和 provider input 状态。

## 11. 复检机制

V2 视觉复检 agent 需要检查：

1. 手选模板结构是否保留。
2. 上传主体是否出现。
3. Logo 或关键品牌元素是否出现。
4. 人脸/人物身份是否合理保留。
5. 上传图是否错误覆盖了模板风格。
6. 最终图是否偏离用户需求。

Template Lock 模式下，复检优先级：

```text
模板结构保留 > 硬素材身份保留 > 用户主题满足 > 风格细节优化
```

## 12. 前端交互

V2 前端建议：

1. 在 V2 生图区域增加上传图片入口。
2. 每张上传图展示角色选择和约束强度。
3. 用户选中案例后，前端显示“模板已锁定，上传图将作为模板内素材使用”。
4. 如果用户希望上传图覆盖模板风格，必须提供“解除模板锁定/改为自由融合”的明确操作。
5. 不要让用户在一个隐蔽选项里无意破坏模板优先级。

推荐提示文案：

```text
已选案例会作为最高优先级视觉模板。上传图片将用于替换主体、补充 Logo、人脸或细节，不会覆盖模板构图和整体风格。
```

## 13. 数据模型新增建议

新增实体：

1. `UploadedAsset`
2. `AssetBrief`
3. `TemplateLockContract`
4. `AssetBindingPlan`
5. `AssetReviewResult`

`CreateCreativeRunRequest` 新增：

```json
{
  "assets": [
    {
      "asset_id": "asset_...",
      "role": "subject_reference",
      "constraint_strength": "required"
    }
  ],
  "template_lock": {
    "enabled": true,
    "unlock_confirmed": false
  }
}
```

`ImagePromptPlan.user_variables` 记录：

1. `template_lock_enabled`
2. `locked_case_id`
3. `asset_binding_plan_id`
4. `provider_input_asset_ids`
5. `asset_conflict_resolutions`

## 14. 开发步骤

### 第 1 章：数据与上传

1. 新增 V2 独立上传 API。
2. 保存图片到 V2 独立存储路径。
3. 生成 `UploadedAsset`。
4. 只允许图片 MIME 类型。

### 第 2 章：视觉理解

1. 增加 `AssetVisionService`。
2. 生成 `AssetBrief`。
3. 识别角色建议、主体、Logo、人脸、背景、色彩和材质。
4. 判断是否需要 provider input image。

### 第 3 章：Template Lock

1. 根据 `template_case_id` 生成 `TemplateLockContract`。
2. 把合同写入 Claude workspace。
3. 在 Claude inline prompt 中压缩传入合同。
4. Claude 输出后校验是否违反合同。

### 第 4 章：素材绑定

1. 生成 `AssetBindingPlan`。
2. 把素材绑定到模板 slot。
3. 冲突时执行 `preserve_template_structure_bind_assets_to_slots`。
4. 记录冲突解决结果。

### 第 5 章：生图 provider

1. 扩展 V2 image job schema，支持 `input_images`。
2. 接入 gpt-image-2/Gemini 的图片输入能力。
3. provider 不支持时返回明确错误。
4. 历史记录展示原始 prompt、最终 prompt、使用素材和模板锁定状态。

### 第 6 章：复检

1. 增加 `AssetReviewAgent`。
2. 检查模板保留和素材遵守。
3. 输出可重试建议。
4. 后续支持自动返工。

## 15. 验收标准

必须通过：

1. 选中案例 + 上传商品图：最终 prompt 保留案例构图和光影，商品图作为主体输入。
2. 选中案例 + 上传风格图：风格图不能覆盖案例模板，只能作为弱补充。
3. 选中案例 + 上传 Logo：Logo 作为素材约束进入 provider input images。
4. 未选案例 + 上传风格图：Claude 可自由找案例并融合风格图。
5. 未选案例 + 上传商品图：Claude 自动找案例增强，但商品图身份保留。
6. Claude 输出包含“改成上传图背景/风格”时，若模板锁定，系统自动重写或 fallback。
7. provider 不支持图片输入时，硬约束素材不能静默降级为纯文字 prompt。

## 16. 非目标

当前阶段不做：

1. 视频素材理解。
2. 多轮精细抠图编辑。
3. 训练 LoRA 或私有模型。
4. 让上传图覆盖手选模板的默认行为。
5. 把 V1 的素材实现直接复制进 V2。
