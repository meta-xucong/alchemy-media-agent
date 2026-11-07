# Alchemy 图片模型统一选择：文档索引与决策记录

状态：提案，文档阶段；不代表代码已经实现或生产网关已提供相应模型。

基线：`origin/main` / `569dffea4381bcd4175a44c50f3c76d0ebc46246`。

范围：Alchemy V1、V2、V3、Alchemy Lab，以及其 Web、HTTP API、HTTP-backed product MCP 入口。Codex Native ImageGen 与 frozen/materialized handoff 工具的执行路径不变，不纳入 AISelf 选型承诺。只讨论 Alchemy 如何使用 AISelf 图片统一网关；AISelf 自身的改造在另一个任务设计。

## 1. 总体目标与本阶段目标

**总目标**：让用户在 Alchemy 的各图片生成功能中选择同一个 AISelf 网关已开放且经过 Alchemy 能力校验的具体图片模型；密钥和上游路由留在服务端；每个任务准确记录实际请求模型，维持各产品原有提示词、素材、审核、交付、权限和计费流程。

**本阶段目标**：冻结 Alchemy 侧的产品、路由、能力、兼容、安全、迁移、测试和上线设计，提供可直接执行的开发文档，接受独立审计并提交 Draft PR。此 PR 不改运行代码、不声称真实模型已接通、不合并、不部署。

## 2. 文档索引

| 文档 | 用途 |
|---|---|
| [01 产品与架构方案](01_PRODUCT_AND_ARCHITECTURE.md) | 当前问题、统一目标、用户体验、模型目录和路由原则 |
| [02 请求、配置与历史契约](02_REQUEST_CONFIG_AND_HISTORY_CONTRACT.md) | API 字段、模型能力记录、优先级、任务快照、向后兼容 |
| [03 分阶段开发计划](03_IMPLEMENTATION_PLAN.md) | 可执行章节、文件边界、依赖、最小实现顺序与回滚 |
| [04 测试、审计与发布验收](04_ACCEPTANCE_AND_RELEASE.md) | 跨版本测试矩阵、费用/安全/故障验收与放行标准 |

## 3. 基线证据

本方案针对源码核验到的现状，而不是假设四个产品已有同一种模型选择：

- V1 `ImageGenerationRequest` 和 `CreateImageJobRequest` 接受 `provider_preference`；模型主要从服务端运行时设置按 provider 解析。设置接口中有默认模型及 OpenAI、Doubao、Gemini 的模型字段。V1 因而具有部分 provider 选择，但任务请求没有统一、可信的精确模型字段。
- V2 的生成请求 `CreateCreativeRunRequest.output` 是结构化生成参数，`CreateRevisionRunRequest` 含 `provider_hint`；V2 图片 Provider 注册表按 provider 选择，模型 ID 从 V2 自己的运行时模型设置读取。V2 必须继续独立实现，不得导入 V1 backend 或其存储/provider。
- Alchemy Lab 请求使用 `provider_preference`，生成由现有 Lab/session/image service 链路处理；需把模型偏好作为 session/variant 的明确参数，而不是只看全局默认。
- V3 Doc100 当前规定 GPT Image 2 (`gpt-image-2`) 为唯一正式 renderer；生产 router 在代码里构造这个固定模型。要支持用户选模型，必须正式修订 Doc100 的模型选择决策，同时保留它关于真实审核、最佳图、bounded retry、无静默 renderer fallback 的其余约束。
- 桌面与移动页面已经暴露若干管理员 provider/model 设置字段，但普通任务提交端主要传 provider/provider hint，不能据此认定用户能逐任务选择任一型号。

## 4. 固定设计决策

1. **一个 Alchemy 图片 Provider 逻辑入口**：`aiself_image_gateway`。Alchemy 不按 GPT、Grok 或上游厂牌建立多个凭据入口；模型选择使用 AISelf 明确提供并由 Alchemy 启用的精确 `model_id`。
2. **一个服务端网关凭据**：仅管理员/部署环境可配置。普通用户只选型号，不能读取或提交网关密钥、base URL、上游 account/channel/provider。
3. **不信任裸 `/v1/models` 作为能力证明**：模型 ID 发现与图像能力声明分开。Alchemy 仅展示处于 enabled 且通过 capability profile 校验的模型。发现到但能力未知的 ID 默认不可选。
4. **能力过滤先于提交**：任务先解析所需操作与素材条件，再筛选支持该任务的型号。用户明确选了不兼容型号时，返回清晰校验错误，不暗中删参考图、降级操作或换型号。
5. **请求快照优先**：每个新网关 Job 固定 `requested_model_id`、能力 profile revision 和非敏感 route/config revision；普通禁用仅阻止新准入，旧任务沿用快照，安全撤销或原路由不可用时才阻断执行。历史读取/幂等回放不重新准入或触发生成。
6. **不静默切换模型或重复不确定付费调用**：重试/续跑沿用原型号。旧 provider 的重试规则不变；新 AISelf 调用若超时后是否已接单未知，没有经验证的上游去重保障就不得自动重发。任何换型号均是用户确认的新任务/新修订。
7. **兼容优先**：所有省略 `image_model_id` 的请求均保留原模块解析，包括同时省略 legacy provider 的请求；不猜客户端新旧。新选择器必须显式提交具体型号，包括默认值和唯一选项；旧历史不回写成 AISelf 路由。
8. **职责隔离**：共用的是公开请求语义和目录字段定义；V1/V3/Lab 的旧运行链与 V2 backend 不因此合并。V2 必须用 V2-native adapter 实现相同 contract，并单独验证配置版本和有界撤销新鲜度。
9. **首期响应最小化**：新 AISelf adapter 只接收经过大小/MIME/解码校验的同步 inline base64 图片响应；拒绝图片 URL，不下载。AISelf 是否支持此形状尚未确认；不支持时保持模型禁用，不能自动扩展为下载/轮询模式。

## 5. 关键非目标

- 不在本 PR 改 AISelf、404token、网关上游分组、模型路由或计价。
- 不将任意网关模型 ID 全量开放给终端用户。
- 不把 LLM/Brain 模型选择与图片 renderer 选择混成一个设置。
- 不改变 V1/V2/V3/Lab 的素材语义、业务模板、review/交付资格、任务队列、项目权限或模块隔离。
- 不把 GPT Image 2.5 的别名、未分类 `gpt-image-2.5` 或 Grok 名称推断成能力；必须由精确目录项和能力验证决定。
- 不承诺每个网关模型都支持编辑、参考图、遮罩、特定尺寸、质量等级、批量数、透明背景或产品既有审核要求。

## 6. 上游前提与待对接接口

Alchemy implementation assumes a server-to-server OpenAI-compatible image route supplied by AISelf. Exact `base_url`, header/auth format, catalog endpoint, model IDs, synchronous/asynchronous behavior, edit multipart shape, response usage fields, and prices remain external contract facts to be confirmed against the separate AISelf design before implementation. This proposal does **not** invent those values.

Minimum integration facts to freeze before gateway implementation/enablement (only offline M0 inventory/schema work may precede them):

- Alchemy can authenticate using one server-held secret and one configured base URL.
- Exact IDs used in the request are routable by the gateway; the adapter does not rewrite a selected ID silently.
- Generation and edit/reference operations have documented request/response formats.
- The gateway can return a request/trace identifier and, if available, served model/usage/cost metadata.
- Alchemy has a curated allowlist/capability profile even if the gateway only exposes ordinary `/v1/models`.
- AISelf supports the selected synchronous inline base64 response contract, with exact field names and byte/pixel/MIME limits. This remains unverified; response URLs and async/polling are disabled in the initial adapter.
- Timeout/accepted-but-unknown outcomes, upstream idempotency scope and TTL, polling/cancellation availability, error and charge semantics are documented. A client Job key alone does not prove upstream deduplication; absent that proof, do not repeat an uncertain paid call.
- V2 receives versioned protected config and fresh security revocations through an existing supported bridge/mount, with a concrete maximum staleness bound frozen at M0. No new configuration service is introduced.

If one of these facts is unavailable, hold the affected gateway implementation/operation at G0. Offline M0 inventory/schema tests may proceed without credentials, network calls or enablement; they do not pass G0. Do not guess from model naming or silently broaden the initial response contract.

## 7. Review state

- Design risk: `A2` — public request contracts, credentials, user-visible model routing, and billing evidence.
- Implementation difficulty: `I2` — four independently implemented product paths must retain their own state and quality semantics while sharing the model-selection contract.
- Design direction is fixed at Alchemy scope: use AISelf as the sole new gateway and require exact model IDs. Endpoint mappings, V2 delivery/freshness bounds and external gateway facts remain M0/G0 preconditions; this is not a claim of zero remaining implementation ambiguity.
- This version is for independent design audit. Any audit-driven contract change requires a new frozen revision before implementation.

## 8. 审计修订记录（2026-10-12）

修订对象是产品/请求契约层的矛盾，不是运行代码：省略字段却区分新旧客户端、普通禁用却阻断冻结任务、宽泛 MCP 承诺、未冻结的 URL/异步响应与不确定付费重试。最小修正分别由 02 的兼容/幂等顺序、快照与新鲜撤销分离、HTTP-backed MCP 范围及同步 inline-only 契约统一约束；01/03/04 同步采用这些规则。V2 直接 image-job 与 creative-run 字段位置分开盘点，回滚区分 feature flag 与旧二进制。

本文仅记录已纳入的设计修正，未宣称独立复审 PASS、功能实现、真实 AISelf 可用或发布通过。未定的接口映射与外部事实仍须满足 03 的 M0 和 04 的 G0 退出条件。
