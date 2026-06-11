# 08. API 接口与前端集成

## 基本原则

2.0 复用同一个域名和前端入口，但 API 和业务模块独立。

推荐路由：

```text
Frontend:
  /v2
  /v2/templates
  /v2/runs/:runId

Backend:
  /api/v2/*
```

OpenAPI 规范见 [openapi.yaml](../specs/openapi.yaml)。

## 前端集成边界

前端可复用：

1. 登录态。
2. 顶部导航。
3. 基础布局。
4. 通用组件库。
5. 文件上传组件，前提是上传目的地独立。

前端不可复用：

1. 旧版生图任务 API。
2. 旧版 prompt 结构。
3. 旧版案例数据。
4. 旧版任务状态机。
5. 旧版 provider 列表。

## 主要页面

### /v2

工作台首页。

包含：

1. 输入框。
2. 模板入口。
3. 最近运行。
4. 当前 provider 健康状态。

### /v2/templates

模板库。

支持：

1. 搜索。
2. 分类筛选。
3. 风格筛选。
4. 用途筛选。
5. 授权筛选。
6. 模板详情。

### /v2/runs/:runId

创意运行详情。

展示：

1. 用户需求。
2. 召回案例。
3. prompt plan。
4. 生图 job。
5. 输出图。
6. 评价和反馈。
7. trace 摘要。

## 核心 API

### 创建创意运行

```http
POST /api/v2/creative/runs
POST /api/v2/creative/runs/async
```

用途：统一入口。模板定制和智能增强都走此接口。同步入口用于开发和轻量请求；异步入口保存 `planning` run 后入持久队列，前端用 `run_id` 轮询。

`assets` 支持两种兼容格式：

```json
{
  "assets": [
    "asset_legacy_string_id",
    {
      "asset_id": "asset_...",
      "role": "subject_reference",
      "constraint_strength": "required",
      "notes": "必须保留商品外观"
    }
  ]
}
```

如果同时存在 `template_case_id` 和 `assets`，后端会启用 Template Lock：手选案例继续作为最高优先级视觉模板，上传图只绑定到主体、Logo、人脸、背景、构图、色彩等可替换 slot，不允许覆盖模板构图、光影、版式、背景密度和整体视觉节奏。

### 查询运行

```http
GET /api/v2/creative/runs/{run_id}
```

用途：前端轮询或恢复页面。若业务 repository 中没有该 run，后端会尝试从持久任务队列的 queued/result 快照恢复。

前端轮询不得使用固定分钟数把任务判为失败。只要接口仍能返回非终态 run，就继续轮询并刷新阶段提示；只有 `completed`、`failed`、`cancelled`、`blocked_by_policy`、`waiting_for_user` 这类后端终态才能结束等待。临时网络错误只提示“读取状态重试中”，不改写为 Agent 失败。

异步任务在长流程中必须持续写入 run 快照，而不是只在创建和完成时写入。推荐阶段：

1. `planning`：构建初始检索和素材理解计划。
2. `retrieving_cases`：读取本地案例和上传素材画像。
3. `composing_prompt`：Claude Code 或 fallback 正在生成最终提示词。
4. `safety_checking`：检查安全策略、素材绑定和 provider 可执行性。
5. `generating`：已提交给生图 provider，等待图片返回。
6. `reviewing`：输出已返回，正在复检和入库。
7. `completed` / `failed`：后端明确终态。

### 中枢与队列状态

```http
GET /api/v2/orchestrator/status
GET /api/v2/task-queue/status
GET /api/v2/review-agent/status
```

用途：给运营和前端展示 Claude 中枢、VPS 队列和复检 agent 当前状态。

### 搜索案例

```http
POST /api/v2/prompt-cases/search
```

用途：模板库和 agent 检索共用。

### 上传图片素材

```http
POST /api/v2/uploads
PUT /api/v2/uploads/{asset_id}/content
POST /api/v2/uploads/{asset_id}/complete
GET /api/v2/uploads/{asset_id}
GET /api/v2/uploads/{asset_id}/content
```

用途：V2 独立图片素材链路。当前只接受图片 MIME 类型。`complete` 会生成 `AssetBrief`，供 Claude Code 中枢、Template Lock、AssetBindingPlan、provider input images 和复检使用。

推荐角色：

1. `style_reference`
2. `subject_reference`
3. `logo_reference`
4. `face_reference`
5. `background_reference`
6. `composition_reference`
7. `color_reference`
8. `negative_reference`

约束强度：

1. `required`
2. `strong`
3. `soft`

### 获取案例详情

```http
GET /api/v2/prompt-cases/{case_id}
```

用途：展示模板详情和 prompt provenance。

### Provider 管理

```http
GET /api/v2/resource-providers
POST /api/v2/resource-providers/{provider_id}/sync
GET /api/v2/resource-providers/{provider_id}/sync-runs/{sync_run_id}
```

用途：运营后台和 agent 手动同步请求。

### 生图 Provider 能力

```http
GET /api/v2/provider-capabilities
GET /api/v2/runtime/model-settings
POST /api/v2/runtime/model-settings
```

`resource-providers` 表示案例/模板资源来源，例如 EvoLinkAI；`provider-capabilities` 表示实际生图模型通道，例如 OpenAI GPT image2、Gemini Image、mock。前端必须分开存储和渲染这两类 provider，不能混用。

模型卡片选择规则：

1. `runtime/model-settings.image_generation_provider` 是用户当前选择。
2. 如果当前选择未配置或 capability 返回 `configured=false`，前端应自动退到可用 provider，并禁用不可用卡片。
3. `provider_hint="auto"` 应继承当前运行时选择；只有当前运行时也是 `auto` 时，后端才按 OpenAI、Gemini、mock 的顺序自动挑选。
4. Gemini 只有在当前模型被判定为图像生成模型时才可选。只有 key 但模型只支持文本输出时，应显示“模型不可生图”。

### 生图 job

```http
POST /api/v2/image/jobs
GET /api/v2/image/jobs/{job_id}
```

通常由创意运行内部调用，前端可用于状态刷新。

## Veyra 账号桥与前端登录闭环

目标：Alchemy 不自建账号、密码、充值和余额系统，而是把 sub2api 作为唯一账号和资金来源。

### sub2api 入口页流程

Veyra Agent 首页由 sub2api 的自定义 portal 扩展提供：

```text
/                         -> Veyra Agent 总入口
/_veyra/*                 -> portal 静态资源
/_veyra/return?target=... -> 登录后的专用回跳页
```

入口页不读取数据库，不创建新 session。它只读取 sub2api 现有前端登录态：

```text
localStorage.auth_token
localStorage.auth_user
```

点击规则：

1. 未登录点击“聚合平台”：跳到 `/login?redirect=/_veyra/return?target=sub2api-console`。
2. 未登录点击“Alchemy”：跳到 `/login?redirect=/_veyra/return?target=alchemy`，H5 使用 `target=alchemy-mobile`。
3. 首页直接点“登录”：跳到 `/login?redirect=/_veyra/return?target=home`。
4. 已登录点击“聚合平台”：进入 sub2api `/dashboard`。
5. 已登录点击“Alchemy”：调用 `POST /api/veyra/login-ticket` 换一次性 ticket，再跳到 Alchemy。

sub2api 登录页保持原账号、邮箱、验证码、2FA 和 token 写入逻辑不变。唯一前端钩子是：当登录成功后的 `redirect` 以 `/_veyra/return` 开头时，用 `window.location.assign(...)` 重新请求 portal 页，而不是留在 Vue SPA router 内。

### sub2api Veyra 扩展 API

对 portal 公开：

```http
GET /api/veyra/portal/config
POST /api/veyra/login-ticket
```

`portal/config` 返回：

```json
{
  "alchemy_base_url": "https://alchemy.aiself.vip"
}
```

`login-ticket` 使用现有 sub2api JWT 中间件，要求：

```http
Authorization: Bearer <sub2api auth_token>
```

返回短期、一次性 ticket：

```json
{
  "ticket": "opaque-ticket",
  "intent": "alchemy",
  "expires_at": "..."
}
```

给 Alchemy 后端内部调用：

```http
POST /api/veyra/internal/login-ticket/exchange
GET  /api/veyra/internal/users/{user_id}/account
POST /api/veyra/internal/billing/debit
```

全部使用 `X-Veyra-Internal-Token`，不暴露给浏览器。

### Alchemy 前端 ticket 接收

Veyra portal 跳转目标：

```text
Desktop: https://alchemy.aiself.vip/?ticket=<ticket>
Mobile:  https://alchemy.aiself.vip/h5?ticket=<ticket>
```

Alchemy 桌面和 H5 前端在初始化时：

1. 读取 URL `ticket`。
2. 调用 `POST /api/v2/veyra/login`。
3. 保存返回的本地 Alchemy session token 到 `localStorage.alchemy_veyra_access_token`。
4. 清理 URL 里的 `ticket`。
5. 后续 `v2Request(...)` 自动附加 `Authorization: Bearer <alchemy_veyra_access_token>`。

如果没有 token，本地开发和匿名兼容路径仍可读公开历史接口；正式启用 `VEYRA_AUTH_ENABLED=true` 后，创意运行和直接 image job 会由后端要求有效 Veyra session。

### Alchemy 账户与扣费闭环

Alchemy 后端提供：

```http
POST /api/v2/veyra/login
GET  /api/v2/veyra/me
GET  /api/v2/veyra/history
GET  /api/v2/veyra/usage
```

生成请求的账户来源只允许来自 `Authorization` 里的 Alchemy Veyra session。即使浏览器请求体里传了 `veyra_user_id`，正式启用认证时也会被后端覆盖。

扣费规则：

1. `VEYRA_AUTH_ENABLED=true`。
2. `VEYRA_GENERATION_CHARGE_AMOUNT > 0`。
3. 当前生成请求解析到有效 sub2api 用户。
4. 生成前调用 sub2api debit API，幂等键为当前 job/run 派生值。
5. 余额不足返回失败任务，不调用生图 provider。
6. 生成成功后记录 Alchemy 本地 usage JSONL 和输出 metadata。

### 反馈

```http
POST /api/v2/outputs/{output_id}/feedback
```

用途：保存用户对结果的选择、喜欢、不喜欢、问题标记和修订意图。

### 返工

```http
POST /api/v2/outputs/{output_id}/revisions
POST /api/v2/outputs/{output_id}/revisions/async
```

用途：基于某个输出的 review、原 prompt、原案例和用户反馈生成新的 revision run。异步入口同样进入持久队列。

## 前端状态

前端只持有展示状态。业务真相以 `/api/v2` 返回为准。

推荐状态字段：

1. `run.status`。
2. `run.mode`。
3. `run.selected_cases`。
4. `run.prompt_plan`。
5. `run.generation_jobs`。
6. `run.outputs`。
7. `run.next_actions`。

## 图片预览

1. 1.0 与 2.0 历史图都使用缩略图渲染列表，单页预加载 48 张。
2. 点击缩略图必须打开同一个图片预览弹层，不跳转新页面。
3. 弹层展示原图、下载入口、提示词入口。
4. 完整提示词放入可滚动文本框，必须允许用户选择和复制。
5. 2.0 生成结果区和 2.0 历史区复用同一套弹层交互。
6. 顶部“生成历史”轮播必须按当前标签页切换数据源：V1 标签只展示 V1 历史，V2 标签只展示 V2 历史。早期 V2 bridge 记录如果物理文件仍在 V1 输出目录，可保留 V1 下载/缩略图 URL 作为兼容引用，但记录归属仍以 V2 历史为准。

## 与旧版共存

反向代理示例：

```text
/api/v1/* -> old backend
/api/v2/* -> v2 backend
/v2/*     -> same frontend app, v2 route
```

如果 2.0 后端不可用，前端应该只降级 2.0 页面，不影响旧版页面。
