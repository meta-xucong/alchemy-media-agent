# V1/V2/V3/Alchemy Lab API 与 MCP 统一适配落地记录

## 状态

本分支完成了统一接入层的最小代码落地、聚焦回归和确定性模拟测试。旧的 V3 API/MCP 契约保持兼容；V1、V2、Alchemy Lab 通过同一 API Key 和同一 stdio MCP 服务器补齐。

本次只改接入层、认证桥、Lab 权属和 MCP 出口，没有重写 V1/V2/V3 的生成、计费、队列、Provider 或审核核心。

## 统一认证模型

- 既有 `alk_v3_...` Key 继续有效，数据库迁移后仍只允许 V3。
- 新建 Key 使用 `alk_live_...`，默认表面为 `v1/v2/v3/lab`。
- Key 数据库增加 `surfaces` 列；老库自动补列并默认为 `["v3"]`。
- Key 仍只保存 SHA-256 摘要，不保存明文；明文只在创建响应返回一次。
- `GET /api/access/capabilities` 返回当前凭证可用的 API 表面和 MCP 工具，不返回密钥或 Provider 信息。

V2 是独立进程，不能共享 V1 的 Store。V1 网关验证账户和 API Key 后，向本机 V2 转发请求时发送短时 HMAC 身份头；V2 只接受 loopback 来源、校验路径/方法/用户/表面/时效和签名，并重新通过原 Veyra 账户桥读取账户角色。API Key、密码、Cookie 不会转发给 V2。

内部桥接需要网关和 V2 使用同一个环境变量：

```text
ALCHEMY_ACCESS_BRIDGE_SECRET=<same-random-secret>
```

该值不能进入 Git、MCP 配置、网页或日志。

## API 表面

保留原路径，不新增 `/api/v4` 或总路由：

```text
V1             /v1/*
V2             /api/v2/*
V3             /api/v3/creative-agent/*
Alchemy Lab    /api/lab/*
Capabilities   /api/access/capabilities
```

API Key 路由限制按表面执行；后台、管理员、运行时 Provider 设置和 V2 登录/计费路径不会被 API Key 放行。

## MCP 工具

原有五个 Native/handoff 工具和 V3 六个产品工具保留在前 11 个位置。新增统一出口总数为 34 个：

- V1：`alchemy_v1_create_session`、`alchemy_v1_upload_asset`、`alchemy_v1_create_image_job`、`alchemy_v1_get_image_job`、`alchemy_v1_list_history`、`alchemy_v1_revise_image`
- V2：`alchemy_v2_create_creative_run`、`alchemy_v2_get_creative_run`、`alchemy_v2_upload_asset`、`alchemy_v2_create_image_job`、`alchemy_v2_get_image_job`、`alchemy_v2_list_history`、`alchemy_v2_search_cases`、`alchemy_v2_get_case`
- Lab：`alchemy_lab_list_modules`、`alchemy_lab_list_styles`、`alchemy_lab_search_styles`、`alchemy_lab_upload_reference`、`alchemy_lab_create_session`、`alchemy_lab_get_session`、`alchemy_lab_list_history`、`alchemy_lab_update_favorites`
- 能力发现：`alchemy_list_capabilities`

MCP 仍使用：

```text
ALCHEMY_PRODUCT_API_BASE_URL
ALCHEMY_PRODUCT_SESSION_TOKEN
```

第二项可放新 `alk_live_` Key、旧 `alk_v3_` Key 或合法会话值，不带 `Bearer ` 前缀。适配器只做 HTTP 调用、参数校验、文件签名检查、响应裁剪和不确定写入保护，不做自动重试或业务状态重建。

## Alchemy Lab 权属修正

探索会话保存 `veyra_user_id`；历史记录同时保存 Lab 归属。普通账户只能读取、更新自己的会话、收藏和历史，管理员可以按原管理员权限读取；旧的无归属记录不会向已认证普通账户开放。Lab 图片下载也不再因为“Lab 来源”而绕过账户归属检查。

## 涉及文件

- `src_skeleton/app/services/api_keys.py`：Key 前缀、表面字段、旧库迁移。
- `src_skeleton/app/api_access.py`：表面路由授权、能力发现、API Key 状态注入。
- `src_skeleton/app/main.py`：V2 内部身份桥转发、Lab 资源权属。
- `src_skeleton/app/services/access_bridge.py`：V1 网关签名器。
- `custom_media_agent_2_0/app/services/access_bridge.py`：独立 V2 验证器。
- `custom_media_agent_2_0/app/config.py`、`app/main.py`：V2 桥配置和认证入口。
- `src_skeleton/app/services/alchemy_lab.py`：Lab 会话/历史归属过滤。
- `services/alchemy_codex_local_adapter/versioned_tools.py`：V1/V2/Lab HTTP MCP 出口。
- `services/alchemy_codex_local_adapter/mcp_server.py`：工具注册和分发。
- `src_skeleton/app/static/api-access.js`：兼容新 Key 格式。

## 验证结果

已完成：

- API Key、能力发现、旧 V3-only Key、路由表面限制：通过。
- HMAC 桥签名、篡改、过期、跨表面验证：通过。
- Lab 跨账户历史、会话和图片访问隔离：通过。
- MCP 旧工具兼容、新工具注册、模拟 HTTP 调用、错误不重试：通过。
- V2 原有独立测试：173 项通过。
- 本次相关聚焦回归：183 项通过。

当前全仓仍有 36 项基线失败：Doc134 专业电商/身体投影契约 35 项，V3 商业前端壳 1 项。这些失败不在本次代码变更范围内，也未被本次接入层修复；因此本分支可以进入 API/MCP 独立测试，但不能把全仓标记为零失败。

## 本地实盘验收门槛

1. 本地 V1 网关和独立 V2 服务都配置 `ALCHEMY_ACCESS_BRIDGE_SECRET`。
2. 本地 Veyra 账户桥可用；否则只能完成模拟验收，不能证明真实账户链路。
3. 先用新 Key 调 `GET /api/access/capabilities`、V1/V2/Lab 的只读接口。
4. 再用测试账户执行一次小规模、明确授权的生成；若 Provider/余额未配置，记录为环境阻塞，不修改代码绕过。
5. MCP 通过同一 Key 调能力发现、历史查询和一个受控生成入口；记录 Job/Run ID，不重复提交不确定写入。

本记录不包含任何测试账号、密码、Key、Cookie 或桥密钥。
