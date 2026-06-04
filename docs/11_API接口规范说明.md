# 11. API 接口规范说明

完整 OpenAPI 草案见 `specs/openapi.yaml`。

## 1. 认证

推荐：

```http
Authorization: Bearer <app_user_jwt>
X-Org-Id: <org_id>
X-Project-Id: <project_id>
```

模型供应商 API Key 不暴露给前端。

## 2. 会话与消息

### 创建会话

`POST /v1/sessions`

用途：创建一个类 ChatGPT 会话。

### 发送消息

`POST /v1/sessions/{session_id}/messages`

请求可包含：文本、asset_ids、目标类型、生成偏好。

返回：assistant message、可能的 task/job id。

### 流式事件

`GET /v1/sessions/{session_id}/events`

SSE 事件类型：

- `message.delta`
- `asset.status`
- `job.status`
- `generation.output`
- `safety.warning`
- `error`

## 3. 素材上传

### 创建上传

`POST /v1/assets/upload-url`

返回签名上传 URL。

### 确认上传

`POST /v1/assets/{asset_id}/complete`

触发扫描与解析。

### 查询素材

`GET /v1/assets/{asset_id}`

返回状态、缩略图、Material Brief。

## 4. 图片生成

### 创建图片任务

`POST /v1/image/jobs`

支持单次和批量。

### 修改图片

`POST /v1/image/jobs/{job_id}/revise`

输入选中 output_id 和用户反馈。

### 查询任务

`GET /v1/image/jobs/{job_id}`

返回状态、输出、错误、成本。

### 下载输出

`GET /v1/outputs/{output_id}/download`

开发环境返回本地存储文件；生产环境应返回权限校验后的短期签名下载或受控文件流。

## 5. 视频预留

### 创建视频任务

`POST /v1/video/jobs`

未配置 provider 时返回：

```json
{
  "status": "provider_not_configured",
  "experimental": true,
  "message": "视频生成 provider 尚未配置，但已保存 VideoJobRequest。"
}
```

### 查询视频任务

`GET /v1/video/jobs/{job_id}`

## 6. 模型与 provider

### 获取可用模型

`GET /v1/providers`

返回 provider 能力、可用性、默认模型。

### 更新项目默认 provider

`PATCH /v1/projects/{project_id}/provider-settings`

仅管理员可用。

## 7. 错误码

| code | 说明 |
|---|---|
| `asset_not_ready` | 素材仍在解析 |
| `provider_not_configured` | 未配置供应商 key |
| `provider_capability_mismatch` | 模型不支持该参数 |
| `safety_rejected` | 内容安全拒绝 |
| `quota_exceeded` | 额度不足 |
| `generation_failed` | 生成失败 |
| `output_expired` | provider URL 已过期，需要重新生成或找归档 |

## 8. Webhook 预留

对视频 provider 支持 webhook 的情况：

`POST /v1/provider-webhooks/{provider}`

所有 webhook 必须校验签名，转换成内部 job status event。
