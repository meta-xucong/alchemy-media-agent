# Alchemy API 与 MCP 统一接入架构方案

> 文档状态：方案设计，供开发评审和后续拆解使用。
>
> 核心结论：API 是面向用户和第三方应用的产品入口，MCP 是面向 Codex 的适配入口；二者必须共用同一个 V3 业务核心，不能各自维护一套生成、审核、存储和任务状态逻辑。

## 一、结论摘要

当前项目已经具备较完整的 MCP 能力，包括本地 stdio MCP、Codex Native ImageGen 规划、冻结计划适配、V3 MCP handoff、nonce/hash 校验、中断恢复，以及提交回 V3 后继续进入输出、审核、候选和项目生命周期。

因此，MCP 设计不应该废弃，也不应该重新设计成公网 API。它应该继续服务“让 Codex 直接使用 Alchemy”这一目标。

推荐整体结构：

    第三方用户 / SDK / 自动化程序
                    |
                    v
              Alchemy Public API
                    |
                    v
             V3 Product Service
                    |
          +---------+----------+
          v                    v
       Provider          MCP Materialization
          |                    ^
          +---------+----------+
                    ^
                    |
              Local MCP Adapter
                    ^
                    |
                  Codex

一句话：API 负责产品化，MCP 负责 Codex 化，V3 Product Service 负责唯一业务事实。

## 二、当前 MCP 基线

当前主要实现位于：

- services/alchemy_codex_local_adapter/mcp_server.py
- services/alchemy_codex_local_adapter/materialized_bridge.py
- plugins/alchemy-codex-local-mode/
- alchemy_creative_agent_3_0/app/generation_router/mcp_materialization.py
- alchemy_creative_agent_3_0/app/product_api/
- src_skeleton/app/main.py 中的 V3 MCP 路由

### 2.1 对话式规划 MCP

现有工具包括：

- prepare_native_imagegen_plan
- prepare_frozen_specialized_native_imagegen_plan
- prepare_frozen_professional_native_imagegen_plan

这类工具为 Codex ImageGen 准备最终 Prompt、画布和允许使用的引用素材路径，但不创建完整的 V3 交付记录。结果应标记为 conversation-only，不能伪装成已经完成的 Alchemy 正式交付。

### 2.2 V3 Materialization MCP

现有工具包括：

- prepare_shared_mcp_materialization
- submit_shared_mcp_materialization

这条链路已经包含 handoff_id、nonce、canonical prompt hash、reference asset hashes、rendering contract fingerprint、pending/submitted/consumed 状态、跨进程锁、恢复和重复提交保护，并且可以进入共享的 V3 输出、审核、候选和选择流程。

这不是历史废代码，而是当前 V3 的正式内部能力。但它应该继续保持“本地 Codex 渲染交接”的定位。

### 2.3 当前边界

V3 MCP handoff 路由要求本机访问，Local MCP 还会校验本地运行时描述文件、运行时身份和素材目录。当前边界应保持为：

    本地 Codex MCP = 可信的本机适配器
    公网用户调用   = Public API

## 三、目标与非目标

### 3.1 目标

1. 用户可以通过稳定 HTTP API 创建图片生成任务。
2. 用户可以上传素材、查询任务、获取输出、选择结果和继续任务。
3. 用户可以通过 API Key 使用 Alchemy，不依赖 Veyra 浏览器会话。
4. Codex 可以通过 MCP 使用同一套 Alchemy 能力。
5. API 和 MCP 的任务、审核、存储、计费和权限语义一致。
6. 现有 Web 前端和 V3 /api/v3/creative-agent/* 调用保持兼容。
7. Provider、MCP、Web、Codex 的差异只存在于传输层，不改变核心产品状态。

### 3.2 非目标

- 不建立第二套生图引擎。
- 不让 MCP 绕过 V3 Brain、Provider、Vision、审核或选择流程。
- 不把 Provider ID、模型 ID、服务器路径、原始 Prompt 或内部 handoff 合同暴露给普通用户。
- 不把当前本地 MCP handoff 直接改成公网匿名接口。
- 不让 API 调用者直接写入 v3_outputs、v3_jobs、v3_projects 或 MCP handoff 文件。
- 不在本阶段同时实现所有语言 SDK、OAuth 和远程 MCP。

## 四、权威边界

### 4.1 唯一业务权威

V3ProductApiService 及其现有生命周期服务作为业务核心，负责项目、上传素材、Job、候选图片、选中结果、输出记录、审核与重试、导出、项目上下文和素材绑定。

API 和 MCP 都不能复制这些逻辑。

### 4.2 三种传输适配器

    PublicApiAdapter      HTTP / JSON / API Key / Webhook
    WebFrontendAdapter    当前浏览器 / Veyra Session
    CodexMcpAdapter       stdio MCP / 本地运行时 / Codex 工具调用

适配器只负责输入校验、身份解析、权限映射、调用 V3 Product Service、公共投影和传输格式转换，不负责 Provider 选择、图片审核、候选选择或直接文件操作。

### 4.3 MCP 的两条路径

    Codex Planning MCP
      只生成冻结计划和 Provider 级输入
      结果：conversation-only

    Codex Materialization MCP
      提交 Codex 图片到已有 V3 handoff
      结果：进入 V3 输出/审核/选择生命周期

不允许对话式规划工具隐式创建任务，也不允许 Materialization 工具变成独立的生成入口。

## 五、Public API 设计

### 5.1 命名空间

新增稳定的第三方入口：

    /api/v1/...

现有接口保持不变：

    /api/v3/creative-agent/...
    /v1/...
    /api/v2/...

新 API 不直接复用所有前端内部字段。现有 V3 路由继续作为兼容层，新 Public API 使用面向产品的稳定合同。

### 5.2 最小资源模型

生成任务：

    POST /api/v1/generations
    GET  /api/v1/generations/{generation_id}
    POST /api/v1/generations/{generation_id}/cancel
    GET  /api/v1/generations/{generation_id}/outputs

创建请求只表达产品需求：

    {
      "prompt": "用户的创作要求",
      "project_id": "optional_project_id",
      "asset_ids": ["asset_xxx"],
      "template": "general",
      "quality_mode": "standard",
      "image_count": 2,
      "size": "1024x1024",
      "metadata": {"client_request_id": "optional-client-id"}
    }

不接受 provider、model、internal prompt、brain checkpoint、mcp handoff id、local file path、review receipt、candidate winner 和 storage path。这些字段属于服务端权威状态。

项目：

    POST  /api/v1/projects
    GET   /api/v1/projects
    GET   /api/v1/projects/{project_id}
    PATCH /api/v1/projects/{project_id}
    GET   /api/v1/projects/{project_id}/timeline
    GET   /api/v1/projects/{project_id}/outputs

简单调用者可以只使用 generations，由服务端创建短生命周期项目上下文；需要长期维护创作上下文的用户使用项目 API。

上传素材：

    POST /api/v1/assets
    PUT  /api/v1/assets/{asset_id}/content
    POST /api/v1/assets/{asset_id}/complete
    GET  /api/v1/assets/{asset_id}
    GET  /api/v1/assets/{asset_id}/content

优先复用当前上传服务和内容存储。大文件支持预签名上传或分片上传，完成时校验类型、大小、哈希和归属。

输出与选择：

    GET  /api/v1/outputs/{output_id}
    GET  /api/v1/outputs/{output_id}/download
    POST /api/v1/generations/{generation_id}/selection
    GET  /api/v1/generations/{generation_id}/export

输出下载使用短期签名 URL 或服务端鉴权流，不暴露物理路径。

### 5.3 公开状态机

内部状态很多，Public API 只暴露稳定投影：

    queued
    planning
    running
    reviewing
    completed
    partial
    failed
    canceled

Brain 阶段、Provider 重试、MCP handoff、候选状态和审查细节放入受控 debug 或管理员视图，不直接成为公开合同。

### 5.4 异步、幂等和回调

所有生成请求默认异步，不让 HTTP 请求长时间等待 Provider。

必须支持：

- Idempotency-Key 请求头；
- 保存幂等键、用户、请求摘要和最终任务 ID；
- 同一用户、同一幂等键、请求摘要一致时返回同一任务；
- 请求摘要不一致时返回冲突错误；
- 轮询接口；
- 可选 Webhook；
- Webhook HMAC 签名、重试和去重；
- 任务超时、取消和失败原因。

建议事件：

    generation.created
    generation.started
    generation.reviewing
    generation.completed
    generation.partial
    generation.failed
    generation.canceled

Webhook 只发送公共任务投影，不发送 Prompt 原文、服务器路径、Provider 响应或内部审查全文。

## 六、认证、隔离和计费

### 6.1 身份场景

    浏览器前端       Veyra Session / Cookie / Bearer Session
    Public API        Alchemy API Key，未来可增加 OAuth
    本地 Codex MCP    本机信任边界 + 本地运行时校验
    远程 MCP（未来） API Key 或 OAuth

Public API 不把 Veyra 浏览器 Session 当作长期开发者 API Key 使用。

### 6.2 API Key

- Key 只在创建时完整显示一次；
- 数据库只保存哈希，不保存明文；
- 使用固定前缀，例如 alk_live_、alk_test_；
- 记录创建者、租户、作用域、创建时间、过期时间、最后使用时间；
- 支持撤销和轮换；
- 支持 generation:write、generation:read、asset:write、project:write 等最小作用域；
- 所有资源查询以服务端解析的 owner / tenant 为准，不接受请求体中的 owner_id。

### 6.3 计费和配额

计费位于任务创建和实际 Provider 消耗的统一服务层，不放在 API 路由或 MCP 工具中。API 和 MCP 使用同一套扣费结果。

至少记录 request_id、generation_id/job_id、owner/tenant、provider strategy、实际模型调用次数、成功/失败/取消/重试、估算成本和扣费状态。

MCP 不允许因为是本地工具而绕过余额或额度检查。

## 七、MCP 优化适配方案

### 7.1 保留现有 MCP

保留本地 stdio、运行时发现、Codex Native ImageGen、Frozen Plan、Materialization handoff、nonce/hash/fingerprint、中断恢复和共享 V3 输出审核链路。这些是当前 MCP 最有价值的部分，不应推倒重做。

### 7.2 新增产品级 MCP 工具

在保留底层规划工具的同时，增加面向 Codex 的高层产品工具：

    alchemy_create_project
    alchemy_upload_asset
    alchemy_create_generation
    alchemy_get_generation
    alchemy_list_generation_outputs
    alchemy_select_outputs
    alchemy_get_project
    alchemy_export_generation

这些工具应满足：

- 参数使用产品语言，不暴露 Provider 和存储细节；
- 返回任务 ID、状态、下一步动作和安全的输出 URL；
- 长任务返回可继续查询的任务 ID；
- 需要人工选择时返回 next_actions；
- 持久化动作最终调用 V3 Product Service；
- 工具输出使用安全公共投影。

### 7.3 MCP 禁止事项

MCP 工具不允许直接调用 Provider、直接写媒体目录、直接修改候选 winner、绕过共享 Vision Review、接收用户自行构造的内部 handoff 合同、接收任意服务器文件路径、通过提示词覆盖模板/素材/身份权威，或在 Provider 失败时偷偷切换到未经批准的本地生成逻辑。

### 7.4 本地 MCP 与远程 MCP

第一阶段继续使用 stdio 和 loopback HTTP，服务 Codex Desktop 和本地开发环境。这样可以访问用户主动授权的本地素材路径，并保持清晰的安全边界。

只有在出现远程 Codex、团队代理或第三方 Agent 的真实需求后，再增加远程 MCP。远程 MCP 应使用 Streamable HTTP 或当前 MCP 推荐的远程传输，强制 API Key/OAuth、租户隔离、限流和审计，不允许传递本地文件路径，只能使用素材 ID 或短期上传 URL。

远程 MCP 不能简单地把当前本地 mcp-materializations 路由暴露到公网。

## 八、API 与 MCP 对照表

| 产品能力 | Public API | MCP | 业务权威 |
| --- | --- | --- | --- |
| 创建项目 | POST /api/v1/projects | alchemy_create_project | V3 Project Service |
| 上传素材 | POST /api/v1/assets | alchemy_upload_asset | V3 Asset Service |
| 创建生成任务 | POST /api/v1/generations | alchemy_create_generation | V3 Product Service |
| 查询任务 | GET /api/v1/generations/{id} | alchemy_get_generation | V3 Job Store |
| 获取结果 | GET /api/v1/generations/{id}/outputs | alchemy_list_generation_outputs | V3 Output Store |
| 选择候选 | POST /api/v1/generations/{id}/selection | alchemy_select_outputs | V3 Selection Service |
| 导出 | GET /api/v1/generations/{id}/export | alchemy_export_generation | V3 Export Service |
| Codex 本地渲染交接 | 不直接暴露 | 内部 Materialization MCP | MCP Handoff Store |
| Provider 选择 | 不公开 | 不公开 | 服务端策略 |

## 九、推荐代码分层

继续复用：

- alchemy_creative_agent_3_0/app/product_api/
- alchemy_creative_agent_3_0/app/generation_router/
- alchemy_creative_agent_3_0/app/visual_assets/
- src_skeleton/app/services/
- services/alchemy_codex_local_adapter/

建议新增：

    src_skeleton/app/public_api/
      routes.py
      schemas.py
      auth.py
      idempotency.py
      webhooks.py
      projections.py

    services/alchemy_codex_local_adapter/
      product_tools.py
      product_projections.py

职责划分：

- public_api/routes.py 只处理 HTTP；
- public_api/auth.py 只处理 API Key、租户和作用域；
- public_api/idempotency.py 只处理重复请求；
- public_api/projections.py 把内部状态转换成稳定公共状态；
- product_tools.py 把 MCP 工具映射到同一套 Product Service；
- product_projections.py 生成适合 Codex 继续对话的简洁结果。

不要新增 MCP 专用生成服务、API 专用 Provider Router、API 专用输出存储、MCP 专用审核器或两套独立 Job 状态机。

## 十、实施阶段

### Phase 0：合同冻结和现状映射

不改行为，只确认边界：V3 Product Service 调用图、API/前端/MCP 字段映射、公共状态机、身份边界、错误码、幂等合同，以及 MCP 工具的 legacy/internal/product 分类。

验收：现有 Web、V3 API、Local MCP 回归测试不变，并明确所有不能进入 Public API 的字段。

### Phase 1：只读 Public API

实现 API Key、项目查询、任务查询、输出查询、短期下载 URL、OpenAPI、request_id 和结构化错误。

验收：跨用户读取隔离、无 API Key 拒绝、不暴露本地路径/Prompt/Provider/handoff，并保证 API 与 Web 对同一任务返回一致状态。

### Phase 2：Public API 异步生成闭环

实现素材创建、上传、完成、POST /api/v1/generations、轮询、幂等、取消、输出列表、候选选择、统一计费和配额。

验收：同一幂等键不会产生两个任务；失败、超时、取消和部分成功都有稳定公共状态；任务只经过现有 V3 生成、审核和存储链路。

### Phase 3：产品级 MCP 工具

实现 alchemy_create_project、alchemy_upload_asset、alchemy_create_generation、alchemy_get_generation、alchemy_list_generation_outputs、alchemy_select_outputs 和 alchemy_export_generation。

验收：API 和 MCP 创建的任务可以在同一项目中互相查询，且不产生重复扣费、重复 Job 或重复输出。

### Phase 4：按需扩展

只有在出现真实第三方需求后再做 Webhook 管理、Python/TypeScript SDK、OAuth、组织和服务账号、远程 MCP 网关以及更细的配额审计。

## 十一、测试与验收

API 合同测试覆盖 OpenAPI、API Key 生命周期、作用域、跨用户隔离、输入边界、非法状态、幂等键和 Webhook 签名。

API/MCP 一致性测试使用同一份产品请求分别执行，验证 owner、素材归属、任务状态、Provider/MCP 策略、审核、候选、输出投影、计费和审计记录一致。

MCP 专项测试覆盖本地运行时发现、非 loopback 拒绝、handoff nonce、Prompt hash、素材 hash、重复提交、并发提交、中断恢复、一次性消费和不绕过共享审核。

生产验收还必须确认：日志不记录完整 API Key，不泄露 Prompt/素材路径/Provider 密钥，所有外部请求有 request_id，所有任务都能通过 API、Web 或 MCP 找到唯一状态。

## 十二、最终决策

### 保留

- 本地 Codex 直接调用；
- Native ImageGen Prompt 规划；
- Frozen Plan；
- MCP Materialization；
- nonce/hash/fingerprint 校验；
- 中断恢复；
- 与 V3 Provider 共用审核、输出和候选生命周期。

### 调整

- 不再把 MCP 看作唯一产品入口；
- 不把 MCP handoff 直接当公网 API；
- 不让 MCP 承担 API Key、配额、Webhook 和计费；
- 不为 MCP 复制一套生成服务和状态机；
- 不让本地 Codex 路径代表所有第三方调用场景。

最终架构：

    V3 Product Service       唯一业务权威
    Public API               面向用户、SDK 和第三方应用
    Web Frontend             面向现有浏览器产品
    Local MCP                面向 Codex 的本地适配器
    Remote MCP（可选）       面向未来远程 Agent 的协议适配器

## 十三、可直接转发给开发同事的总结文案

建议采用 API-first、MCP-adapter 的整体架构。

当前项目的 MCP 不是废弃设计，已经具备 Codex Native ImageGen、冻结 Prompt、素材引用约束、MCP handoff、nonce/hash 校验、中断恢复，以及回到 V3 输出和审核链路的能力。这些能力继续保留，主要服务“让 Codex 直接使用 Alchemy”。

后续不要把 MCP 继续扩展成公网业务接口，而是新增稳定的 /api/v1 Public API，负责第三方用户和应用的 API Key、用户隔离、素材上传、异步生成、任务查询、输出下载、候选选择、Webhook、配额和计费。

API 和 MCP 都必须调用同一个 V3 Product Service，不能各自实现生成、审核、存储和任务状态。API 是产品化入口，MCP 是 Codex 适配入口，Web 前端是现有浏览器入口；三者共享同一个项目、素材、Job、输出和审核生命周期。

当前本地 mcp-materializations 保持 loopback-only，不直接开放到公网。未来如果有远程 Agent 需求，再单独增加带 API Key/OAuth、租户隔离和限流的远程 MCP 网关。

实施顺序建议：先冻结 API/MCP 共同产品合同，再做只读 Public API，之后做异步生成闭环，再增加产品级 MCP 工具，最后按真实需求增加 Webhook、SDK 和远程 MCP。这样能最大限度复用现有代码，避免重复建设和架构分叉。
