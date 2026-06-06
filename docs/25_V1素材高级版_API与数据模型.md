# 25. V1 素材高级版 API 与数据模型

## 1. 目标

本文定义 V1 素材高级版需要新增或扩展的后端接口、请求字段、数据结构和状态机。它是 `11_API接口规范说明.md` 的补充，不替代现有 API。

兼容原则：

- 不破坏现有 `/v1/image/jobs`。
- `asset_mode` 缺省为 `basic`。
- 旧版 `asset_ids` 在基础版路径保持可用。
- 基础参数始终生效；高级版只是在基础参数上叠加图片素材增强。
- 高级版新增字段全部可灰度开关。

## 2. Image Job 请求扩展

### 2.1 基础版

```json
{
  "prompt": "生成一张咖啡海报",
  "image_provider": "openai_image",
  "image_model": "gpt-image-2",
  "asset_mode": "basic",
  "asset_ids": ["asset_001"]
}
```

基础版行为：

- 后端沿用当前逻辑。
- 可以读取素材摘要做弱提示。
- 不要求用户选择素材用途。
- 不生成高级版 `AssetPlan`。

### 2.2 高级版

```json
{
  "prompt": "生成一张咖啡海报",
  "image_provider": "gemini_image",
  "image_model": "gemini-2.0-flash-preview-image-generation",
  "asset_mode": "advanced",
  "asset_intents": [
    {
      "asset_id": "asset_001",
      "role": "style_reference",
      "priority": 80,
      "preservation": "loose",
      "strength": 0.65,
      "notes": "参考这张图的光线和高级感"
    },
    {
      "asset_id": "asset_002",
      "role": "logo_overlay",
      "priority": 100,
      "preservation": "exact",
      "placement": {
        "anchor": "bottom_right",
        "margin_ratio": 0.06,
        "width_ratio": 0.18,
        "opacity": 1.0
      },
      "consent": {
        "user_confirmed_rights": true
      }
    }
  ]
}
```

高级版行为：

- 后端必须校验所有素材已 `ready`。
- 当前阶段高级版只接受 `image/*` 素材；非图片文件在上传入口即拒绝。
- 后端必须校验每个素材有 `role`。
- 后端必须生成 `asset_plan`、`asset_vision_profile` 和 `prompt_plan`。
- Kimi/思考模型只能基于 `prompt + asset_intents + asset_vision_profile + provider_capability` 做规划；不能替代真实图片输入。
- 后端按 provider 能力决定是传参考图、走 image edit、做后处理，还是拒绝。
- 对 `style_reference`、`subject_reference`、`portrait_identity`、`background_reference`、`composition_reference` 等依赖图片的用途，支持 gpt-image-2 或等效 provider 时必须传入原始/规范化图片文件；不能只传文字提示。

## 3. AssetIntent Schema

```json
{
  "asset_id": "asset_001",
  "role": "style_reference",
  "priority": 80,
  "preservation": "loose",
  "strength": 0.65,
  "notes": "希望参考它的色调",
  "placement": null,
  "mask_id": null,
  "consent": {
    "user_confirmed_rights": true,
    "portrait_identity_allowed": false,
    "logo_or_trademark_allowed": false
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `asset_id` | string | 是 | 已上传素材 ID |
| `role` | enum | 是 | 素材用途 |
| `priority` | int | 否 | 1-100，默认 50 |
| `preservation` | enum | 否 | `loose`、`medium`、`strict`、`exact` |
| `strength` | number | 否 | 0-1，影响提示词强度 |
| `notes` | string | 否 | 用户补充说明 |
| `placement` | object | 否 | Logo、主体、文本等位置要求 |
| `mask_id` | string | 否 | 局部修改用 mask |
| `consent` | object | 条件必填 | 人脸、Logo、商标、版权素材必须确认 |

## 4. Role 枚举

```text
style_reference
subject_reference
logo_overlay
portrait_identity
background_reference
composition_reference
local_edit
negative_reference
```

## 5. Preservation 枚举

| 值 | 中文 | 含义 | 典型用途 |
|---|---|---|---|
| `loose` | 宽松参考 | 只参考感觉，不要求一致 | 风格、氛围 |
| `medium` | 中等参考 | 主要特征接近 | 背景、构图 |
| `strict` | 强保真 | 主体、人物或商品需要明显接近 | 商品、人像 |
| `exact` | 精确保留 | 像素级或图形级保留 | Logo、二维码、指定标识 |

## 6. Placement Schema

```json
{
  "anchor": "bottom_right",
  "margin_ratio": 0.06,
  "width_ratio": 0.18,
  "height_ratio": null,
  "opacity": 1.0,
  "safe_area": true
}
```

`anchor` 可选：

```text
top_left
top_center
top_right
center_left
center
center_right
bottom_left
bottom_center
bottom_right
custom
```

`custom` 时额外传：

```json
{
  "x_ratio": 0.72,
  "y_ratio": 0.82
}
```

## 7. Consent Schema

```json
{
  "user_confirmed_rights": true,
  "portrait_identity_allowed": true,
  "logo_or_trademark_allowed": true,
  "commercial_use_allowed": true,
  "source_note": "用户自有品牌素材"
}
```

强制规则：

- `portrait_identity` 必须 `portrait_identity_allowed=true`。
- `logo_overlay` 必须 `logo_or_trademark_allowed=true`。
- 商业用途下建议 `commercial_use_allowed=true`。
- 未确认权利时，高级版可以保存素材，但不能进入生成任务。

## 8. AssetPlan Schema

```json
{
  "asset_mode": "advanced",
  "job_id": "imgjob_123",
  "assets": [
    {
      "asset_id": "asset_001",
      "role": "style_reference",
      "priority": 80,
      "preservation": "loose",
      "resolved_asset_type": "image",
      "material_brief_used": true,
      "vision_profile_used": true,
      "provider_input_mode": "reference_image",
      "reference_image_url": "/v1/assets/asset_001",
      "provider_file_id": "file_abc",
      "prompt_constraints": [
        "Use warm premium studio lighting."
      ],
      "negative_constraints": [],
      "postprocess_steps": []
    }
  ],
  "provider_requirements": {
    "needs_image_reference": true,
    "needs_image_edit": false,
    "needs_mask_edit": false,
    "needs_postprocess": false
  },
  "warnings": []
}
```

`provider_input_mode` 可选：

```text
none
material_brief_only
reference_image
edit_source
mask_edit_source
postprocess_only
```

## 9. AssetVisionProfile Schema

`AssetVisionProfile` 是素材的视觉画像。它用于提示词规划和复检，不替代 provider 真实图片输入。

```json
{
  "asset_id": "asset_001",
  "status": "ready",
  "analyzer_provider": "kimi_vision",
  "analyzer_model": "kimi-vision-or-compatible",
  "summary": "暖色棚拍咖啡产品图，主体居中，浅色背景，高级极简质感。",
  "subjects": [
    {
      "type": "product",
      "description": "玻璃杯咖啡饮品，顶部奶泡明显",
      "position": "center",
      "confidence": 0.88
    }
  ],
  "style": {
    "palette": ["warm beige", "coffee brown", "soft white"],
    "lighting": "soft studio lighting",
    "texture": "clean glossy product photography",
    "mood": "premium minimal"
  },
  "composition": {
    "orientation": "portrait",
    "framing": "central subject with negative space",
    "camera_angle": "front three-quarter",
    "text_safe_areas": ["top", "bottom_right"]
  },
  "detected_text": [],
  "logo_candidates": [],
  "faces": [],
  "risks": [],
  "recommended_roles": ["style_reference", "subject_reference", "composition_reference"],
  "created_at": "2026-06-06T10:00:00Z"
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `status` | `pending`、`ready`、`failed`、`skipped` |
| `analyzer_provider` | 视觉分析 provider，例如 Kimi vision、OpenAI vision、Gemini vision 或 local |
| `summary` | 给用户和 prompt planner 使用的短摘要 |
| `subjects` | 主体列表，用于主体参考和复检 |
| `style` | 色彩、光线、材质、情绪 |
| `composition` | 构图、镜头、留白、安全区域 |
| `detected_text` | 图片中文字，用于避免乱码或保留文案 |
| `logo_candidates` | 疑似 Logo/标识区域 |
| `faces` | 人脸数量与风险摘要，不直接暴露敏感身份推断 |
| `recommended_roles` | 仅作为推荐，不自动强制生效 |

强制规则：

- `AssetVisionProfile` 可以失败，但失败时必须记录状态和错误摘要。
- Kimi/思考模型使用它来生成 PromptPlan。
- gpt-image-2 仍必须收到图片文件作为 reference/edit 输入，不能只收到 `summary`。

## 10. PromptPlan Schema

```json
{
  "original_prompt": "生成一张咖啡海报",
  "asset_mode": "advanced",
  "vision_profile_summary": "暖色棚拍咖啡产品图，主体居中，浅色背景，高级极简质感。",
  "style_block": "Premium minimalist studio lighting, warm highlights.",
  "subject_block": "Keep the product shape close to the uploaded reference.",
  "layout_block": "Reserve clean lower-right negative space for logo overlay.",
  "safety_block": "Do not invent fake brand marks or unreadable text.",
  "provider_input_plan": {
    "operation": "images.edit",
    "reference_image_asset_ids": ["asset_001"],
    "postprocess_only_asset_ids": ["asset_002"]
  },
  "negative_prompt": "distorted logo, unreadable text, cluttered layout",
  "final_prompt": "Create a premium minimalist coffee poster with warm studio lighting..."
}
```

生成规则：

- `final_prompt` 必须由后端模板拼装，不直接拼用户任意 JSON。
- `original_prompt` 永远保留。
- 与素材强相关的约束进入独立 block，方便历史展示和调试。
- Logo 的真实出现优先走后处理，提示词只要求预留空间。
- `provider_input_plan` 必须明确图片是否会以 reference/edit 形式传入 provider。
- `final_prompt` 要精简高信号，不需要把 Kimi 的全部思考过程塞给 gpt-image-2。

## 11. VisualReview Schema

生成完成后可附加复检结果：

```json
{
  "review_status": "ready",
  "review_provider": "vision_review_agent",
  "overall_score": 0.82,
  "checks": {
    "style_alignment": 0.86,
    "subject_preservation": 0.74,
    "composition_alignment": 0.79,
    "logo_integrity": 0.95,
    "text_legibility": 0.88
  },
  "issues": [
    {
      "code": "subject_drift",
      "severity": "medium",
      "message": "主体轮廓与参考图有偏移。"
    }
  ],
  "retry_recommendation": {
    "should_retry": false,
    "prompt_delta": "increase subject preservation and reduce camera angle drift"
  }
}
```

第一阶段只展示复检结果；自动重试必须单独开关控制。

## 12. Asset 生命周期扩展

现有生命周期：

```text
uploaded -> scanning -> stored -> extracting -> analyzed -> ready
```

高级版建议细化为：

```text
created
-> upload_requested
-> uploaded
-> scanning
-> stored
-> normalized
-> derivatives_ready
-> vision_analyzed
-> ready
```

失败状态：

```text
scan_failed
normalize_failed
analysis_failed
unsupported_type
policy_blocked
```

## 13. 派生文件

每个图片素材建议生成：

```json
{
  "thumbnail_url": "/v1/assets/asset_001/derivatives/thumb",
  "preview_url": "/v1/assets/asset_001/derivatives/preview",
  "normalized_url": "/v1/assets/asset_001/derivatives/normalized",
  "alpha_mask_url": null,
  "provider_file_refs": [
    {
      "provider": "openai_image",
      "file_id": "file_abc",
      "expires_at": "2026-06-06T00:00:00Z"
    }
  ]
}
```

说明：

- `thumbnail` 给前端列表用。
- `preview` 给用户确认用。
- `normalized` 给 provider 调用用，尺寸、格式、方向统一。
- `provider_file_refs` 允许缓存 provider 侧 file_id，但必须处理过期。

## 14. 新增或扩展接口

### 14.1 创建上传

`POST /v1/assets/upload-url`

新增可选字段：

```json
{
  "filename": "logo.png",
  "content_type": "image/png",
  "declared_role": "logo_overlay",
  "intended_use": "image_generation",
  "consent": {
    "user_confirmed_rights": true,
    "logo_or_trademark_allowed": true
  }
}
```

规则：

- `content_type` / `mime_type` 必须是 `image/png`、`image/jpeg`、`image/webp` 等允许的图片类型。
- 非图片文件返回空 `upload_url` 或明确错误码 `unsupported_asset_type`。

### 14.2 确认上传

`POST /v1/assets/{asset_id}/complete`

返回：

```json
{
  "asset_id": "asset_001",
  "status": "analyzed",
  "thumbnail_url": "/v1/assets/asset_001/derivatives/thumb",
  "material_brief": {
    "summary": "透明背景品牌 Logo",
    "detected_roles": ["logo_overlay"],
    "visual_style": {
      "palette": ["#111111", "#FFFFFF"]
    },
    "risks": []
  }
}
```

### 12.3 设置素材用途

`PUT /v1/assets/{asset_id}/intent`

用途：用户先上传素材，再单独保存高级版用途配置。

```json
{
  "role": "style_reference",
  "preservation": "loose",
  "strength": 0.6,
  "notes": "参考光线和构图"
}
```

说明：

- 该接口是可选能力。
- 如果前端只在生图时传 `asset_intents`，也可以不实现。

### 12.4 创建图片任务

`POST /v1/image/jobs`

新增字段：

```json
{
  "asset_mode": "advanced",
  "asset_intents": []
}
```

响应新增：

```json
{
  "job_id": "imgjob_123",
  "status": "queued",
  "asset_mode": "advanced",
  "asset_plan_id": "assetplan_123",
  "prompt_plan_id": "promptplan_123"
}
```

### 12.5 查询图片任务

`GET /v1/image/jobs/{job_id}`

高级版新增字段：

```json
{
  "asset_mode": "advanced",
  "asset_plan": {},
  "prompt_plan": {},
  "postprocess_steps": [
    {
      "type": "logo_overlay",
      "status": "succeeded"
    }
  ],
  "provenance": {
    "requested_provider": "gemini_image",
    "actual_provider": "gemini_image",
    "requested_model": "gemini-2.0-flash-preview-image-generation",
    "actual_model": "gemini-2.0-flash-preview-image-generation"
  }
}
```

### 12.6 创建局部编辑 Mask

`POST /v1/assets/{asset_id}/masks`

```json
{
  "mask_type": "polygon",
  "points": [
    {"x": 0.2, "y": 0.2},
    {"x": 0.8, "y": 0.2},
    {"x": 0.8, "y": 0.7},
    {"x": 0.2, "y": 0.7}
  ],
  "label": "replace background"
}
```

返回：

```json
{
  "mask_id": "mask_001",
  "mask_url": "/v1/assets/asset_001/masks/mask_001"
}
```

## 13. 数据表建议

### assets

| 字段 | 说明 |
|---|---|
| `id` | asset id |
| `tenant_id` | 租户 |
| `owner_user_id` | 上传用户 |
| `asset_type` | image/pdf/video/document |
| `status` | 生命周期状态 |
| `storage_key` | 原文件对象存储 key |
| `thumbnail_key` | 缩略图 key |
| `normalized_key` | 规范化图 key |
| `material_brief_json` | 素材摘要 |
| `consent_json` | 授权记录 |
| `created_at` | 创建时间 |

### asset_intents

| 字段 | 说明 |
|---|---|
| `id` | intent id |
| `asset_id` | 素材 |
| `job_id` | 关联任务，可为空 |
| `role` | 用途 |
| `priority` | 优先级 |
| `preservation` | 保真级别 |
| `strength` | 强度 |
| `placement_json` | 位置 |
| `mask_id` | mask |
| `notes` | 用户备注 |
| `consent_snapshot_json` | 生成时授权快照 |

### image_job_plans

| 字段 | 说明 |
|---|---|
| `job_id` | 图片任务 |
| `asset_mode` | basic/advanced |
| `asset_plan_json` | 素材计划 |
| `prompt_plan_json` | 提示词计划 |
| `provider_requirements_json` | provider 能力要求 |
| `warnings_json` | 降级或风险提示 |

### output_provenance

| 字段 | 说明 |
|---|---|
| `output_id` | 输出图片 |
| `job_id` | 任务 |
| `original_prompt` | 原始提示词 |
| `final_prompt` | 最终提示词 |
| `requested_provider` | 用户选择 provider |
| `actual_provider` | 实际 provider |
| `requested_model` | 用户选择模型 |
| `actual_model` | 实际模型 |
| `provider_fallback` | 是否 fallback |
| `postprocess_json` | 后处理记录 |

## 14. Job 状态机扩展

基础版可保持当前状态。高级版建议：

```text
created
-> validating_assets
-> planning_assets
-> building_prompt
-> provider_dispatching
-> generating
-> postprocessing
-> evaluating
-> ready
```

失败状态：

```text
asset_validation_failed
provider_capability_failed
generation_failed
postprocess_failed
evaluation_failed
```

状态事件建议通过现有轮询接口或 SSE 输出：

```json
{
  "event": "job.status",
  "job_id": "imgjob_123",
  "status": "planning_assets",
  "message": "正在根据素材用途规划生成方式"
}
```

## 15. Provider Capability API

`GET /v1/providers` 建议返回：

```json
{
  "image_providers": [
    {
      "id": "openai_image",
      "label": "GPT Image",
      "models": [
        {
          "id": "gpt-image-2",
          "capabilities": [
            "text_to_image",
            "image_reference",
            "image_edit",
            "mask_edit"
          ],
          "advanced_asset_roles": [
            "style_reference",
            "subject_reference",
            "local_edit",
            "logo_overlay"
          ]
        }
      ]
    }
  ]
}
```

前端展示选项时只根据该接口决定能力，不写死 provider。

## 16. 兼容与迁移

- 旧历史记录没有 `asset_mode` 时按 `basic` 展示。
- 旧素材没有 `material_brief` 时可在首次访问时异步补分析。
- 高级版相关字段可以先存在 JSON 字段中，等稳定后再拆表。
- mock provider 必须支持高级版 schema 的回显，方便本地测试。

## 17. 配置项

```env
V1_ADVANCED_ASSETS_ENABLED=true
V1_ADVANCED_ASSET_MAX_COUNT=6
V1_ADVANCED_REFERENCE_MAX_COUNT=3
V1_ADVANCED_UPLOAD_MAX_MB=25
V1_ADVANCED_REQUIRE_CONSENT=true
V1_ADVANCED_ENABLE_LOGO_POSTPROCESS=true
V1_ADVANCED_ENABLE_MASK_EDIT=false
```

## 18. 最小可落地版本

第一版可以只实现：

- `asset_mode`。
- `asset_intents`。
- `style_reference`、`subject_reference`、`logo_overlay`。
- `AssetPlan` 和 `PromptPlan` 保存。
- Logo 先只做“提示词预留区域”，真实叠加进入下一阶段。
- 历史展示原始提示词、最终提示词、高级素材用途。

这样可以最快形成可测试闭环，同时不破坏现有基础版。
