# Alchemy Lab 稀有风格探索器传图模块开发文档

## 1. 背景结论

`rare-style-explorer` 当前已经具备风格库、批量生成、质量增强、历史记录和对比展示能力。下一步可以加入传图能力，但它不能变成 V2 的模板生图，也不能让上传图覆盖稀有风格探索的核心价值。

本方案新增一个 **Lab-owned Reference Image Module**：

```text
用户想法
  -> 可选参考图
  -> 稀有风格选择或抽样
  -> Lab 自己的参考图意图解析
  -> Lab rare-style prompt composer
  -> Lab quality enhancement
  -> existing image generation service
  -> Lab session / comparison board / Lab history
```

关键结论：

- 适合加入传图能力。
- 传图必须是可选增强，不是默认必填。
- 上传图用于固定主体、产品、Logo、材质、色彩或局部视觉线索。
- 稀有风格仍然是每张图的主要变量。
- 后台必须独立模块化，不能运行时复用 V2 上传服务。

## 2. 产品定位

这个模块不是“V2 传图”的复制入口，而是：

```text
参考图引导的稀有风格探索
```

用户可以用一张或多张图来指定：

- 主体长什么样。
- 产品或包装外观不能丢。
- Logo 或文字标识需要进入画面。
- 某种材质、颜色、纹理或视觉气质可以作为辅助参考。

然后 `rare-style-explorer` 继续负责：

- 选择不同稀有风格。
- 让同一主体在不同风格下生成对比图。
- 保存每张图实际使用的 prompt、风格、参考图策略和结果状态。

## 3. 严格边界

### 3.1 必须独立

Alchemy Lab 的传图后台必须是 Lab 自己的模块。

允许做的事：

- 可以复制 V2 上传模块的代码结构、校验思路、状态机和局部实现。
- 可以参考 V2 的 role、constraint strength、asset brief、provider input plan 概念。
- 可以复用项目已有的通用能力，例如鉴权、配置、media storage、provider registry、image generation service。

禁止做的事：

- 禁止 Lab 运行时 import `custom_media_agent_2_0.app.services.uploaded_assets`。
- 禁止 Lab 前端调用 `/api/v2/uploads`。
- 禁止 Lab 后端调用 `/api/v2/creative/runs` 或 V2 Claude orchestration。
- 禁止让 Lab 默认走 V2 template lock、V2 prompt transform、V2 案例检索。
- 禁止把 Lab 上传素材写入 V1/V2 history 语义里。
- 禁止把用户上传源图公开到所有账户可见的 Lab 历史中。

短规则：

```text
代码可以借鉴。
模块必须独立。
运行时不依赖 V2。
```

### 3.2 稀有风格优先

参考图不能覆盖用户选择或系统抽样出的稀有风格。

正确关系：

```text
Rare style preset controls visual exploration direction.
Uploaded images fill subject, product, logo, texture, color, or material constraints.
```

如果用户上传一张摄影图并选择“浮世绘残片风格”，结果应该是：

```text
上传图的主体/产品/Logo 被保留
+ 浮世绘残片风格被强化
```

而不是：

```text
直接复刻上传图的摄影风格
```

## 4. 新增后台模块建议

保持当前项目结构，不强行迁移既有 `alchemy_lab.py`。新增 Lab 独立文件，逐步把传图逻辑放进去：

```text
src_skeleton/app/services/
    alchemy_lab.py                     # 现有 rare-style-explorer 编排
    alchemy_lab_uploads.py             # Lab 上传生命周期
    alchemy_lab_asset_vision.py        # Lab 上传图本地分析
    alchemy_lab_reference_policy.py    # Lab 参考图角色、强度、provider 输入计划
    alchemy_lab_reference_prompt.py    # Lab 参考图提示词约束拼装
```

API 入口仍放在现有 FastAPI app 中，但路径必须是 Lab 命名空间：

```text
POST /api/lab/uploads
PUT  /api/lab/uploads/{asset_id}/content
POST /api/lab/uploads/{asset_id}/complete
GET  /api/lab/uploads/{asset_id}
GET  /api/lab/uploads/{asset_id}/content
```

不要使用：

```text
/v1/assets/*
/api/v2/uploads/*
```

## 5. 数据模型

### 5.1 LabUploadedAsset

Lab 自己的上传素材对象。

建议字段：

```text
asset_id
feature_id
filename
mime_type
size_bytes
veyra_user_id
status
role
constraint_strength
intended_use
source_url
thumbnail_url
storage_path
brief
error
created_at
updated_at
```

状态值：

```text
upload_requested
stored
ready
rejected
failed
deleted
```

`feature_id` MVP 默认：

```text
rare-style-explorer
```

未来其他 Lab 模块可以复用 Lab 上传服务，但必须用各自 `feature_id` 隔离解释策略。

### 5.2 LabReferenceAssetInput

创建探索 session 时传入的参考图绑定。

```text
asset_id
role
constraint_strength
notes
```

`role` MVP：

```text
subject_reference          # 主体/人物/商品外观参考
product_reference          # 产品或包装参考
logo_reference             # Logo、品牌标识、文字标识
style_material_reference   # 材质、色彩、纹理、气质参考
composition_reference      # 构图参考，默认 soft，不能覆盖 rare style
negative_reference         # 反向参考，MVP 可先预留不开放
```

`constraint_strength`：

```text
required
strong
soft
```

### 5.3 ExplorationRequest 扩展

在 `ExplorationRequest` 中新增：

```text
reference_assets: list[LabReferenceAssetInput]
reference_mode: off | guided
```

默认：

```text
reference_assets = []
reference_mode = guided
```

如果没有上传图，行为必须与当前版本完全一致。

### 5.4 ComposedPrompt metadata 扩展

每个 prompt 要保存：

```text
reference_summary
reference_asset_roles
reference_policy
provider_input_plan
reference_warnings
```

注意：prompt metadata 和历史记录中不要暴露私有 `storage_path`、源图 URL、内部账户信息。

### 5.5 LabHistoryItem 扩展

Lab 历史当前是所有账户可见。传图后必须分清：

- 生成图片：可继续按 Lab 历史策略展示。
- 上传源图：默认仅上传者可见。
- 公共历史：只展示参考图摘要。

公共历史可显示：

```text
参考图：主体参考 1 张，Logo 1 张
```

公共历史不可显示：

```text
asset_id
source_url
thumbnail_url
filename
storage_path
```

上传者本人可在 session detail 中查看自己的参考图缩略图。

## 6. 上传生命周期

### 6.1 Create

`POST /api/lab/uploads`

请求：

```json
{
  "filename": "cake.jpg",
  "mime_type": "image/jpeg",
  "size_bytes": 832100,
  "feature_id": "rare-style-explorer",
  "role": "subject_reference",
  "constraint_strength": "strong",
  "intended_use": "保持蛋糕外观，探索不同视觉风格"
}
```

响应：

```json
{
  "asset_id": "lab_asset_xxx",
  "upload_url": "/api/lab/uploads/lab_asset_xxx/content",
  "headers": {
    "x-upload-mode": "json-base64"
  }
}
```

### 6.2 Store Content

`PUT /api/lab/uploads/{asset_id}/content`

只接受 image MIME。

MVP 限制建议：

```text
maxLabReferenceAssetBytes = 12MB
maxLabReferenceAssetCount = 4
acceptedMimeTypes = image/png, image/jpeg, image/webp
```

GIF 可以先拒绝，避免多帧语义不稳定。

### 6.3 Complete

`POST /api/lab/uploads/{asset_id}/complete`

完成时做：

- 文件存在检查。
- MIME 和真实图片解码检查。
- 基础尺寸读取。
- 本地视觉分析。
- role 兜底建议。
- `status = ready`。

如果本地分析失败，但图片本身可读，可以降级：

```text
status = ready
brief.warnings includes local_analysis_failed
```

不要因为本地分析能力弱而阻断用户传图，除非文件不可用。

## 7. 参考图意图策略

### 7.1 Role 行为

`subject_reference`

- 保留主体身份、轮廓、关键特征。
- 允许被 rare style 改变材质、光线、媒介和表达方式。
- 不允许完全变成另一个主体。

`product_reference`

- 保留产品外观、包装比例、核心识别点。
- 对电商、海报、菜单、包装设计非常重要。
- 推荐 `strong` 或 `required`。

`logo_reference`

- 区分两种情况：
  - Logo 成为画面中的物体表面元素。
  - Logo 成为海报或包装上的品牌标识。
- 不允许一律当作角标。
- 如果用户 notes 写明“印在衣服上”“放在瓶身上”“作为海报品牌标识”，必须进入 reference policy。

`style_material_reference`

- 只借鉴材质、色彩、纹理、颗粒、光感、工艺感。
- 不能覆盖 rare style preset。
- 默认 `soft` 或 `strong`，不建议 `required`。

`composition_reference`

- 只作为构图启发。
- 在 Rare Style Explorer 中默认 soft。
- 如果和 rare style 的视觉语言冲突，rare style 优先。

`negative_reference`

- MVP 可以只定义数据模型，不开放 UI。
- 后续用于“不要像这张图”的对照参考。

### 7.2 参考图和稀有风格冲突规则

冲突优先级：

```text
1. 用户明确文字要求
2. required 级别的主体 / 产品 / Logo 约束
3. rare style preset
4. quality enhancement
5. soft 级别的 composition / material 参考
```

重要规则：

- `style_material_reference` 不能让 style preset 失效。
- `composition_reference` 不能让全部风格都变成同一张图的版式复刻。
- `logo_reference` 必须根据用户 notes 判断用途。
- 如果 provider 不支持 input image，required/strong 参考图不能静默降级成纯文字。

## 8. Provider 输入计划

Lab reference policy 输出 `provider_input_plan`。

建议结构：

```json
{
  "operation": "image_generation_with_reference_images",
  "requires_image_reference": true,
  "reference_image_count": 2,
  "reference_asset_ids": ["lab_asset_xxx", "lab_asset_yyy"],
  "roles": ["subject_reference", "logo_reference"],
  "unsupported_provider_policy": "fail_or_reroute"
}
```

执行规则：

- OpenAI/Gemini 等支持 input image 的 provider 可以使用真实图片输入。
- Doubao 这类不支持 reference image 的 provider，遇到 required/strong 参考图必须提前失败或自动切到支持图片输入的 provider。
- soft 参考图可以在用户确认后降级为 brief-only，但 MVP 不建议静默降级。

推荐策略：

```text
有 reference_assets:
  优先选择支持 reference images 的 provider
  如果用户强选不支持的 provider:
    required/strong -> 返回明确错误
    soft -> 可返回警告并允许 brief-only
```

## 9. 与现有 image generation service 的连接方式

Lab 不直接调用 provider SDK。

推荐新增一个窄适配层：

```text
alchemy_lab.py
  -> alchemy_lab_reference_policy.build_lab_reference_plan()
  -> submit_lab_reference_image_job()
  -> existing image generation service
```

`submit_lab_reference_image_job()` 需要解决两件事：

1. 复用现有 billing、safety、provider registry、output storage。
2. 不把 Lab 上传素材塞进 V1/V2 上传服务。

推荐实现方向：

```text
新增 asset_mode = lab_reference
或新增 external_asset_plan / lab_reference_plan 参数
```

要求：

- 对现有 `basic`、`advanced` 行为零影响。
- provider adapter 最终能拿到 Lab 上传图的本地路径。
- history 中标记 `source = alchemy_lab`、`feature = rare-style-explorer`。
- V1/V2 历史和 Lab 历史仍按现有边界过滤。

不推荐实现方向：

```text
Lab 上传后再伪装成 /v1/assets
Lab 直接调用 /api/v2/uploads
Lab 直接调用 provider SDK
```

## 10. Prompt 组合规则

参考图模块加入后，最终 prompt 必须同时保留：

- 用户 idea。
- 稀有风格 preset。
- 质量增强结果。
- 参考图约束。

推荐组装顺序：

```text
Subject / Intent:
{用户想法}

Rare Style Direction:
{style preset directives}

Reference Image Guidance:
{Lab reference policy 自然语言摘要}

Quality Direction:
{quality enhancement 输出}

Avoid:
{anti-drift + reference warnings}
```

关键禁令：

- 不要在 prompt 中泄露 `asset_id`、`storage_path`、URL、内部 provider 信息。
- 不要让 LLM 把参考图改写成全新创意。
- 不要让质量增强层覆盖 rare style。

示例：

```text
参考图约束：保持上传产品的主要轮廓、包装比例和可识别品牌色；Logo 需要作为包装表面的一部分自然融入。稀有风格仍以当前 preset 为主，参考图只固定产品识别点。
```

## 11. 前端交互设计

### 11.1 桌面版

在 Rare Style Explorer 详情页中，放在“创意描述”下方或高级设置上方。

默认折叠：

```text
参考图片（可选）
```

点击展开后显示：

- 上传区域。
- 已上传图片小卡片。
- 每张图的用途选择。
- 参考强度。
- 简短备注。
- 权利确认提示。

桌面 UI 不能做成大面积平铺，避免挤压风格库和历史区域。

建议布局：

```text
创意描述
参考图片（可选） [展开]
生成数量 / 每风格数量 / 间隔 / 画幅 / 质感增强
风格筛选与风格库
生成结果
```

### 11.2 手机版 H5

不要沿用桌面平铺。

H5 使用 V2.0 那种卡片式交互：

```text
参考图片（可选）
  -> 点击卡片
  -> 弹出或展开紧凑内容
  -> 上传 / 选择用途 / 查看已上传
  -> 返回探索器
```

H5 上默认只显示：

```text
参考图片：未添加
```

添加后显示：

```text
参考图片：2 张 · 主体参考 + Logo
```

### 11.3 角色文案

面向小白用户的文案：

```text
主体/商品
Logo/标识
材质/色彩
构图参考
```

高级含义可用 tooltip 或辅助说明：

- 主体/商品：保持主要对象像上传图。
- Logo/标识：让标识出现在画面或物体表面。
- 材质/色彩：只借鉴质感，不覆盖风格。
- 构图参考：只参考大致布局，风格仍由所选稀有风格决定。

## 12. 批量生成限制

传图会增加 provider 压力，尤其是多图输入和批量生成。

MVP 建议：

```text
maxLabReferenceAssets = 4
maxLabReferenceImagesPerProviderCall = provider cap, but no more than 4
defaultTargetCountWithReferences = 4
maxTotalImagesWithReferences = 8
maxConcurrentGenerations = 1
defaultGenerationIntervalSeconds = 8
```

如果用户选择 8 张以上并带 required 参考图，UI 应显示提示：

```text
带参考图会逐张生成，速度会更慢，也更容易触发上游限制。
```

后端仍必须串行执行，沿用当前 batch cooldown 和 backoff 规则。

## 13. 安全、权限与隐私

### 13.1 权限

开启 Veyra 鉴权时：

- 创建上传必须绑定 `veyra_user_id`。
- 读取源图必须校验 owner 或 admin。
- 创建 session 时必须校验每个 `reference_assets.asset_id` 对当前用户可见。

未开启鉴权时：

- 本地开发可以允许读取。
- 仍不能把源图 URL 放进公共历史。

### 13.2 权利确认

上传时至少确认：

```text
user_confirmed_rights
portrait_identity_allowed
logo_or_trademark_allowed
commercial_use_allowed
```

小白 UI 可以合并为一句：

```text
我确认有权使用上传图片及其中的人像、Logo 或商品素材。
```

后端仍要保存结构化 consent。

### 13.3 公共历史脱敏

Lab 历史所有账户可见时，必须做脱敏。

公共历史可以显示：

- 使用了几张参考图。
- 用途摘要。
- 是否应用了参考图约束。

公共历史不能显示：

- 上传源图缩略图。
- 上传文件名。
- asset_id。
- source_url。
- storage_path。
- 用户账号信息。

## 14. 开发顺序

### 阶段 1：文档与契约

- 更新 `docs/alchemy_lab/03_data_contract.md`。
- 更新 `docs/alchemy_lab/04_execution_contract.md`。
- 更新 `specs/alchemy_lab/rare_style_explorer.schema.json`。
- 新增上传相关 acceptance tests。

### 阶段 2：Lab 上传后台

- 新增 `alchemy_lab_uploads.py`。
- 新增 `alchemy_lab_asset_vision.py`。
- 新增 `/api/lab/uploads/*` endpoints。
- 保存到 Lab 自己的 storage namespace。
- 实现权限校验和 MIME/大小校验。

### 阶段 3：参考图策略层

- 新增 `alchemy_lab_reference_policy.py`。
- 新增 `alchemy_lab_reference_prompt.py`。
- 将 `reference_assets` 注入 prompt metadata。
- 处理 provider input plan。
- 处理 unsupported provider policy。

### 阶段 4：生成链路接入

- 在 rare-style-explorer session creation 中接受 `reference_assets`。
- 生成每个 variant 时传入 Lab reference plan。
- 保持串行生成和 cooldown。
- 保持 partial success。
- 保持 final prompt 可查看。

### 阶段 5：前端

- 桌面版新增折叠式“参考图片（可选）”。
- H5 新增卡片式“参考图片（可选）”。
- 上传完成后展示小卡片、用途、强度、备注。
- session 创建时带上 `reference_assets`。
- 结果卡和历史卡展示参考图摘要。

### 阶段 6：回归与上线

- 跑全量 smoke tests。
- 跑 V1/V2 isolation tests。
- 本地生成 4 张带参考图的 rare-style 对比图。
- VPS 部署前确认源图不出现在公共历史 payload。

## 15. 测试验收

### 15.1 后端测试

必须覆盖：

- Lab upload create/store/complete 成功。
- 非图片 MIME 被拒绝。
- 超大小图片被拒绝。
- 未确认 rights 被拒绝。
- 非 owner 不能读取源图。
- `ExplorationRequest.reference_assets` 校验。
- invalid asset id 被拒绝。
- not-ready asset 被拒绝。
- required reference + unsupported provider 返回明确错误或 reroute。
- soft reference 可以带 warning 降级。
- final prompt 保存 reference summary。
- session metadata 保存 provider input plan。
- Lab public history 不泄露 `asset_id`、`source_url`、`storage_path`。

### 15.2 隔离测试

必须有静态或单元测试证明：

- Lab 上传服务不 import V2 uploaded asset service。
- Lab 前端不调用 `/api/v2/uploads`。
- Lab 后端不调用 `/api/v2/creative/runs`。
- V1/V2 原有上传和生成测试仍通过。

### 15.3 前端测试

必须覆盖：

- 桌面版参考图面板默认收起。
- H5 参考图卡片默认收起。
- 上传后显示图片数量和用途摘要。
- 角色切换会更新 session payload。
- 传图失败显示友好错误。
- 带参考图生成时按钮状态、进度和结果网格正常。

### 15.4 实盘测试

至少跑三组：

1. 商品参考图 + 4 个稀有风格。
2. Logo 参考图 + 海报创意 + 4 个稀有风格。
3. 材质/色彩参考图 + 抽象创意 + 4 个稀有风格。

判断标准：

- 上传图的核心约束可见。
- 每张图仍有明显 rare style 差异。
- 没有全部变成上传图原始风格。
- 历史记录能看到参考图摘要但不泄露源图。

## 16. 验收标准

可以交付的标准：

- 没有上传图时，rare-style-explorer 行为与当前版本一致。
- 有上传图时，用户能完成上传、选择用途、设置强度、生成对比图。
- 上传图约束和 rare style 可以共存。
- 传图生成仍走 Lab session、Lab comparison board、Lab history。
- Lab 传图后台独立于 V2 上传后台。
- 公共 Lab 历史不会泄露用户上传源图。
- 桌面和 H5 都能使用，且 UI 不冗长、不破坏现有 Lab 结构。
- 相关测试通过。

## 17. Codex 落代码指令

```text
Implement the Alchemy Lab reference-image module for rare-style-explorer.

Read first:
- docs/alchemy_lab/00_overview.md
- docs/alchemy_lab/01_product_spec.md
- docs/alchemy_lab/02_architecture.md
- docs/alchemy_lab/03_data_contract.md
- docs/alchemy_lab/04_execution_contract.md
- docs/alchemy_lab/05_ui_flow.md
- docs/36_AlchemyLab质量增强与智能文案层级开发文档.md
- docs/37_AlchemyLab稀有风格探索器传图模块开发文档.md

Hard rules:
- Lab backend must be modular and independent.
- Do not call V2 upload endpoints.
- Do not import V2 uploaded asset services at runtime.
- Do not route Lab generation through V2 creative runs.
- Do not use V2 template lock or V2 prompt transform as Lab dependencies.
- Do not expose uploaded source images in public Lab history.
- Rare style preset remains the primary exploration variable.
- Uploaded images only constrain subject/product/logo/material/composition intent.

Implementation goal:
Add optional reference-image uploads to rare-style-explorer while preserving the existing no-upload flow.

Build order:
1. Add Lab upload models and service.
2. Add /api/lab/uploads endpoints.
3. Add Lab reference policy and prompt integration.
4. Add request/schema/session/history metadata.
5. Add provider-input bridge through the existing generation service without V1/V2 upload coupling.
6. Add desktop and H5 UI.
7. Add unit, smoke, isolation, and real-generation tests.

Stop only when the acceptance criteria in this document pass.
```
