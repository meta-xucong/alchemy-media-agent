# V1 / V2 / V3 / Alchemy Lab API 与 MCP 统一最小适配开发方案

> **已废弃（历史方案，仅供沿革参考）**：本方案形成于统一适配落地之前，不再作为当前开发计划或实现状态依据。V1/V2/V3/Alchemy Lab 的当前落地范围与验收记录以 [`docs/47_V1V2V3AlchemyLab_API_MCP统一落地验收记录.md`](47_V1V2V3AlchemyLab_API_MCP统一落地验收记录.md) 和当前源码为准。本方案中的待开发阶段、审计结论及路由示例可能与现状不同；不要据此重复开发。

## 0. 文档定位

本方案沿用 V3 API/MCP 的最小化原则：

> API 复用已有 HTTP 入口；MCP 只是 API 的安全工具化适配；业务核心、计费、队列、审核、存储和版本运行时不重复建设。

本方案解决四个入口的一致接入：

- V1：`/v1/*`
- V2：`/api/v2/*`
- V3：`/api/v3/creative-agent/*`
- Alchemy Lab：`/api/lab/*`

本方案是统一接入层设计，不合并 V1、V2、V3 的业务内核，也不把 Alchemy Lab 改造成 V3 项目模式。

当前基线：

- V3 既有 API/MCP 适配方案：`docs/43_API与MCP统一接入架构方案.md`
- V3 产品工具实现：`services/alchemy_codex_local_adapter/product_tools.py`
- V3 MCP Server：`services/alchemy_codex_local_adapter/mcp_server.py`
- API Key 接入实现：目标功能分支 `75d090b4`

## 1. 当前审计结论

### 1.1 可以复用的内容

V1/V2 的历史设计仍可复用以下原则：

1. `builtin/http/process/mcp` 的适配器思想。
2. Agent、Tool Boundary、Domain Service、Provider Adapter 分层。
3. 结构化输入、结构化输出、超时、幂等、鉴权上下文、trace 和成本字段。
4. V1 的图像任务、素材和历史接口。
5. V2 的独立运行时、任务队列、素材绑定、案例检索和安全检查接口。
6. V2 的严格隔离规则：V2 不直接读取或写入 V1 的数据库、素材、历史、队列和 Provider 配置。

### 1.2 不能直接复用的内容

当前 Git 历史和本地工作树没有发现可直接启动的 V1/V2 MCP Server。V1/V2 的 `mcp` 依赖和 Agents SDK function tools 是工具边界或依赖预留，不等于已经有可用的 MCP transport、stdio 启动器或 Codex 工具注册。

因此本次采用：

```text
已有 V1/V2/Lab HTTP API
        ↓
统一本地 MCP HTTP Adapter
        ↓
现有 Codex MCP Server
```

不从历史文档重新恢复一套旧 MCP 业务运行时。

## 2. 总体结构

```text
API Key / 既有 Veyra Session
             │
             ▼
     统一访问边界与能力发现
             │
   ┌─────────┼─────────┬─────────┐
   ▼         ▼         ▼         ▼
 V1 API    V2 API    V3 API    Lab API
   │         │         │         │
 V1 Core   V2 Core   V3 Core   Lab Core
             │
             ▼
       统一本地 MCP Server
```

硬约束：

- MCP 不直接导入 V1/V2/V3 的 Provider、Store、Queue 或计费模块。
- MCP 不自行创建 Job、重试收费写请求、计算质量结论或写入 winner。
- API 和 MCP 必须使用相同账户、相同资源归属、相同计费链和相同业务状态。
- V1、V2、V3 继续使用各自版本的请求和响应字段，不强行改成一个伪统一 schema。
- 统一层只统一凭证、能力声明、错误外壳和工具命名。

## 3. API 统一方案

### 3.1 不新增平行业务 API

保留并开放现有路径：

| 能力 | 现有路径 | 处理方式 |
|---|---|---|
| V1 生图 | `/v1/*` | API Key 直接进入现有 V1 路由 |
| V2 生图 | `/api/v2/*` | 通过现有 V2 代理进入 V2 独立服务 |
| V3 产品模式 | `/api/v3/creative-agent/*` | 保留当前 API/MCP 实现 |
| Alchemy Lab | `/api/lab/*` | 复用现有 Lab 路由和服务 |

不新增 `/api/v4`、`/api/unified` 或第二套生图接口。

统一访问层只增加一个只读能力发现接口：

```text
GET /api/access/capabilities
```

它只返回当前凭证可用的 surface、工具名、是否写操作和是否可能产生费用，不返回账户密钥、Provider 信息或内部路径。MCP 的 `alchemy_list_capabilities` 直接复用该接口。

### 3.2 API Key 范围

现有 `alk_v3_` 密钥保持兼容，默认仅保留 V3 能力，避免历史密钥突然获得更大权限。

新建密钥改为中性前缀，例如 `alk_live_`，数据库增加能力范围字段：

```json
{
  "surfaces": ["v1", "v2", "v3", "lab"]
}
```

第一阶段用户界面默认创建全能力密钥；后续管理员可增加按模块勾选。无论是否启用范围 UI，服务端必须执行范围校验。

路由映射：

```text
/v1/                         -> v1
/api/v2/                     -> v2
/api/v3/creative-agent/     -> v3
/api/lab/                    -> lab
```

管理后台、Veyra 登录回调、内部调试接口和本地 MCP materialization 不属于产品 API Key 范围。

### 3.3 V2 身份桥

V2 是独立进程，不能把 `alk_live_` 原样作为 Veyra Session 透传。统一入口验证 API Key 后，向本地 V2 代理注入短生命周期的内部身份上下文：

```text
X-Alchemy-Access-User
X-Alchemy-Access-Surfaces
X-Alchemy-Access-Request
X-Alchemy-Access-Signature
```

要求：

- 只允许 loopback 或受信任内网链路接收。
- 使用独立内部密钥签名，包含 user_id、surface、method、path、issued_at、nonce。
- V2 只验证签名并映射为 `veyra_user_id`，不导入 V1 的 API Key Store。
- 直接访问 V2 的既有 Veyra Session 行为不变。
- 内部头不能由公网请求直接提供；公网同名头必须被覆盖或拒绝。

这是 V2 适配所需的最小跨进程身份桥，不是新的登录系统。

## 4. V1 API 最小开放面

V1 保留原路由和原字段，首批只包装一条完整生图闭环：

| MCP 工具 | 现有 API | 说明 |
|---|---|---|
| `alchemy_v1_create_session` | `POST /v1/sessions` | 创建 V1 会话，返回原 session_id |
| `alchemy_v1_upload_asset` | upload-url + content + complete | 读取用户明确授权的本地图片并走原上传流程 |
| `alchemy_v1_create_image_job` | `POST /v1/image/jobs` | 只提交一次，保留原 job_id |
| `alchemy_v1_get_image_job` | `GET /v1/image/jobs/{job_id}` | 查询，不创建任务 |
| `alchemy_v1_list_history` | `GET /v1/image/history` | 返回原历史和鉴权下载地址 |
| `alchemy_v1_revise_image` | `POST /v1/image/jobs/{job_id}/revise` | 沿用原 revision 语义 |

首阶段不包装 V1 Provider 设置、管理员设置、删除历史和批量控制；这些接口可以继续由 Web/API 直接调用，避免 MCP 工具面过大。

V1 生成写请求发生超时或结果不确定时，工具必须返回 `outcome_unknown=true`，要求调用者使用 job_id 查询，不自动重发。

## 5. V2 API 最小开放面

V2 继续使用独立服务的原始 `/api/v2/*` 契约。首批工具覆盖“创意运行”和“图像任务”两种已有入口：

| MCP 工具 | 现有 API | 说明 |
|---|---|---|
| `alchemy_v2_create_creative_run` | `POST /api/v2/creative/runs/async` | 使用 V2 中枢和队列，返回原 run_id |
| `alchemy_v2_get_creative_run` | `GET /api/v2/creative/runs/{run_id}` | 查询原状态和 next_actions |
| `alchemy_v2_upload_asset` | `/api/v2/uploads*` | 复用 V2 独立素材存储 |
| `alchemy_v2_create_image_job` | `POST /api/v2/image/jobs` | 直接进入 V2 图像任务接口 |
| `alchemy_v2_get_image_job` | `GET /api/v2/image/jobs/{job_id}` | 查询原 job_id |
| `alchemy_v2_list_history` | `GET /api/v2/image/history` | 按 V2 账户上下文过滤 |
| `alchemy_v2_search_cases` | `POST /api/v2/prompt-cases/search` | 只读案例检索 |
| `alchemy_v2_get_case` | `GET /api/v2/prompt-cases/{case_id}` | 只读案例详情 |

V2 的 `case_strategist_search`、`case_detail`、`case_profile`、`prompt_safety_check` 继续作为内部 Agents SDK function tools；如果以 MCP 暴露，必须走对应 V2 HTTP API 或 Domain Service 的公开安全投影，不直接把 Python function tool 对象注册成公共 MCP 工具。

V2 的运行时模型设置、Veyra billing settings、Provider 密钥、资源同步控制和管理员接口不开放给普通 API Key/MCP。

## 6. V3 保持现状并纳入统一能力表

现有 V3 产品工具继续保留：

- `alchemy_create_project`
- `alchemy_upload_asset`
- `alchemy_create_generation`
- `alchemy_get_generation`
- `alchemy_list_outputs`
- `alchemy_select_outputs`

现有 Native ImageGen、MCP handoff、materialization、nonce、Prompt hash 和 loopback-only 规则全部不变。

V3 工具不改名，避免破坏已安装的 Codex 配置。能力发现中将它们标记为 `surface=v3`。

## 7. Alchemy Lab 最小开放面

Alchemy Lab 已有 `/api/lab/*`，MCP 只包装现有模块，不在 MCP 中重建风格库或生图流程：

| MCP 工具 | 现有 API | 说明 |
|---|---|---|
| `alchemy_lab_list_modules` | `GET /api/lab/modules` | 查询已启用模块 |
| `alchemy_lab_list_styles` | `GET /api/lab/rare-style-explorer/styles` | 返回当前风格库 |
| `alchemy_lab_search_styles` | `POST /api/lab/rare-style-explorer/styles/search` | 只读检索 |
| `alchemy_lab_upload_reference` | `/api/lab/uploads*` | 复用 Lab 传图、授权和素材契约 |
| `alchemy_lab_create_session` | `POST /api/lab/rare-style-explorer/sessions` | 启动原 Lab 探索任务 |
| `alchemy_lab_get_session` | `GET /api/lab/rare-style-explorer/sessions/{id}` | 查询进度和结果 |
| `alchemy_lab_list_history` | `GET /api/lab/history` | 仅返回当前账户历史 |
| `alchemy_lab_update_favorites` | `POST /api/lab/rare-style-explorer/sessions/{id}/favorites` | 沿用原收藏语义 |

Lab 的生成仍由现有 `create_exploration_session()`、`submit_image_job()` 和原 Provider/Review 链执行。MCP 不直接调用 Provider，也不改变 Lab 的串行生成、重试和质量增强策略。

### 7.1 Lab 必须先补的归属校验

在接入 API Key/MCP 前，Lab 需要完成最小数据修正：

1. `ExplorationSession` 增加可选 `veyra_user_id`，兼容旧记录的 `null`。
2. `create_exploration_session()` 保存当前用户 ID。
3. `get_exploration_session()` 按用户 ID过滤，管理员才可跨账户读取。
4. `update_favorites()` 校验会话归属。
5. `list_lab_history()` 增加 `veyra_user_id`过滤参数。
6. Lab 历史记录统一从输出 metadata 或 Lab session 归属读取用户 ID。
7. 旧的 owner 缺失记录只能按既有兼容策略处理，不能因为 API Key 接入而默认暴露给所有账户。

这部分是安全闭环的必要修正，不是新增 Lab 业务功能。

## 8. 统一 MCP Server 设计

### 8.1 工具命名

V1、V2、Lab 使用显式前缀；V3 原有工具保持不变：

```text
alchemy_v1_*
alchemy_v2_*
alchemy_lab_*
alchemy_*                 # existing V3 compatibility names
```

新增只读工具：

```text
alchemy_list_capabilities
```

返回：

```json
{
  "surfaces": ["v1", "v2", "v3", "lab"],
  "tools": [
    {"name": "alchemy_v2_create_image_job", "surface": "v2", "write": true, "may_charge": true}
  ],
  "credential_type": "alchemy_api_key"
}
```

### 8.2 MCP 工具通用规则

- 工具输入只包含业务参数和用户明确选择的本地文件路径。
- 服务地址、API Key、内部密钥和存储路径来自进程配置，不来自模型参数。
- 本地上传工具读取文件字节，不把本机路径传给服务端。
- 写请求无自动重试；超时返回不确定结果和原 ID。
- 查询工具不得隐式创建任务。
- 工具返回原始业务 ID、状态、错误码和必要的下载相对地址。
- 不返回 Provider 密钥、服务器绝对路径、原始异常堆栈、内部 Prompt 或账户凭证。
- API 失败和 MCP 失败使用同一错误码，不重新定义业务成功状态。

### 8.3 MCP 配置

保持现有 `alchemy-codex-local-mode` 启动方式，只增加版本和 Lab HTTP Adapter，不新增四套 MCP Server：

```text
ALCHEMY_PRODUCT_API_BASE_URL
ALCHEMY_PRODUCT_SESSION_TOKEN
```

支持 API Key 后，`ALCHEMY_PRODUCT_SESSION_TOKEN` 可以填 API Key 或既有 Veyra Session。工具内部统一使用 Bearer 发送，配置值不包含 `Bearer ` 前缀。

旧配置继续支持 V3；增加 V1/V2/Lab 工具不改变旧工具名称和旧参数。

## 9. 实施顺序

### 阶段 A：契约和鉴权基础

- 扩展 API Key 记录的能力范围。
- 保留 `alk_v3_` 兼容行为。
- 增加中性新 Key 前缀和能力发现。
- 扩展 `key_allows()` 到 V1、V2、V3、Lab。
- 增加 V2 内部身份桥及反伪造测试。

### 阶段 B：V1/V2 HTTP 适配

- 先补 API Key 直达 V1。
- 再补 V2 代理身份映射。
- 逐个验证上传、创建任务、查询、历史和不确定写请求。
- 不修改 V1/V2 Provider、任务队列和存储核心。

### 阶段 C：Lab 归属闭环

- 增加 Lab session owner。
- 修正历史、会话和收藏的用户过滤。
- 用 API Key 验证单账户可见性和跨账户拒绝。

### 阶段 D：统一 MCP 工具

- 把 V1/V2/Lab 工具加入现有 `mcp_server.py`。
- 保留 V3 现有工具及 Native/handoff 工具。
- 增加 `alchemy_list_capabilities`。
- 每个写工具只调用一个原有写入口，不自动补发。

### 阶段 E：最终闭环验收

- 同一账户分别用 Web、API、MCP 创建任务。
- 比较 task/job/run ID、状态、输出、历史和费用。
- 检查跨账户资源拒绝、过期 Key、撤销 Key、V2 内部头伪造、Lab 越权读取。
- 真实付费生成只做每个版本各一次受控验收，不用于探索性调试。

## 10. 允许修改与明确不做

允许修改：

- API Key Store 的能力字段和兼容解析。
- 统一 API Key 路由白名单。
- V2 代理身份桥。
- Lab session/history owner 过滤。
- 现有 MCP Server 的工具注册和 HTTP Adapter。
- 对应测试、调用文档和能力发现响应。

明确不做：

- 不重写 V1/V2/V3 生图核心。
- 不合并 V1/V2 数据库、存储、Provider 或队列。
- 不建立新的计费、余额、审核、重试或任务状态机。
- 不把 V1/V2 的内部 Agents SDK function tools 直接当作公共 MCP 业务实现。
- 不开放管理员配置、Provider 密钥、V3 本地 handoff 或内部 materialization。
- 不创建远程 MCP 网关，不改变生产监听地址和反向代理拓扑。

## 11. 验收矩阵

| 编号 | 验收项 | 通过条件 |
|---|---|---|
| R1 | V1 API | API Key 可创建会话、上传、生成、查询、历史和修图 |
| R2 | V2 API | API Key 经身份桥进入 V2，账户和任务归属正确 |
| R3 | V3 API | 原有六个 V3 产品工具和 API 全部回归通过 |
| R4 | Lab API | API Key 可搜索风格、上传、创建 session、查询和收藏 |
| R5 | MCP 发现 | Codex 能发现 V1/V2/V3/Lab 工具和能力信息 |
| R6 | MCP 闭环 | 每个版本至少完成一次上传/生成/查询闭环 |
| R7 | 身份隔离 | 跨账户资源、撤销 Key、过期 Key、错误内部头全部拒绝 |
| R8 | 状态一致 | Web、API、MCP 使用同一原始 ID 和状态，不重复创建任务 |
| R9 | 计费一致 | 只经过原有收费链，适配层不重复扣费 |
| R10 | 范围控制 | 无新增业务核心、计费系统、队列、Store 或 Provider 分支 |

## 12. 最终交付判断

完成阶段 A-E 后，才可以称为“V1/V2/V3/Alchemy Lab 的 API 与 MCP 统一接入完成”。

仅完成 V3 六个产品工具、API Key 页面或 MCP 握手，不能作为全版本完成证明。
