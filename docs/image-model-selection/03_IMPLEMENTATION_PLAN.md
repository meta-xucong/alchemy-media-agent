# Alchemy 图片模型选择：分阶段开发计划

状态：提案，仅供实施前审计。

实施原则：一次只改一层；每章先添加失败测试，再实现最小契约；不可把本计划当作代码已存在。

## 1. 边界与前置条件

### 范围

- V1、V2、V3、Alchemy Lab 图片生成/修订入口。
- 桌面和移动 Web、现有 HTTP API、HTTP-backed product MCP 调用表面；Native ImageGen 与 frozen/materialized handoff 的执行路径不变，拒绝其不支持的 AISelf 选型字段。
- 一个服务端配置的 AISelf 图像统一网关；按精确模型 ID 路由。
- 能力兼容校验、任务模型快照、可靠状态/费用元数据、旧请求兼容。

### 不在范围

- AISelf Gateway 本身、404token/Sub2API、其上游账号/渠道分组和模型购买。
- 改 LLM/Brain 选择、模板业务职责、提示词质量策略、视觉审核阈值、生成数量默认值。
- 另建用户 BYOK、租户凭据系统、计费台账、队列、模型市场、自动模型 fallback 或复杂性能缓存。
- 仅为提供选择器而重写 V1/V2/V3 的 job schema、store、历史或 provider 架构。

### 开工硬门槛

G0 前在 `AISelf Integration Facts` 表中冻结独立网关工作的结果：base URL/auth、generation/edit 请求形状、reference/multipart、同步 inline base64 响应、大小/MIME/像素限制、错误、request ID、served model 和 usage/cost 字段。还必须确认 timeout/accepted-but-unknown、上游 idempotency scope/TTL、poll/cancel 是否存在及其终态/费用含义。首期不启用图片 URL 下载或 async/polling，不能因 AISelf 的合同不同而自动扩大适配范围。

还必须确认 Alchemy 的一个逻辑 secret 和一份受版本控制的目录如何安全供应给独立 V2 进程，及其 schema/config/revocation revision、最大陈旧时间、失效与刷新验证；不允许两处重复录入 key 或增设配置服务。模型 ID 和能力需使用 AISelf 已有验证证据；本次文档修订不发起付费验证，名称猜测或模型页面截图不能作为能力证明。

若外部事实暂不可用，只允许 M0 只读盘点、无网络 catalog/schema 骨架及确定性测试。该例外不代表 G0 已通过，不允许实现/接通真实网关执行、启用模型或部署；后续 M1–M6 必须等待 G0 的独立审计及外部合同前提满足。

## 2. 里程碑

### M0 — 契约锁定与影响盘点

1. 将 01/02 文档审计意见收敛成固定接口映射表。
2. 核对每个 product 的确切 endpoint + method + schema + JSONPath、Job 持久化字段、重试/恢复、revision、幂等原意图及身份/owner/session 校验顺序；记录 Web/mobile/MCP 到 provider 的透传链。
3. 确认 AISelf 同步 inline base64 字段、每种 edit/reference 输入的真实样例以及不确定接单/去重/费用事实；未确认的响应模式保持禁用。
4. 更新冻结清单：基线 SHA、数据库/历史兼容、文件白名单、审计等级、回滚点。

退出条件：没有未定的公开字段位置/密钥来源/请求路由事实；V2 的投影版本和撤销新鲜度有具体界限与验证方法；各模块 owner 和测试目录确定。以下是已核验的现有入口及本方案映射边界，不是假称新字段已实现；所有“待冻结”项必须在 M0 退出前解决。

| 已核验的现有入口（均为 POST） | 现有结构 / MCP 对应 | 字段决定与 M0 必须完成的映射 |
|---|---|---|
| `/v1/image/jobs` | `src_skeleton/app/schemas.py::CreateImageJobRequest`; `alchemy_v1_create_image_job` | 新增顶层 `image_model_id`；核实幂等原意图、准入与持久化 |
| `/v1/image/jobs/{job_id}/revise`；`/v1/sessions/{session_id}/messages` | `ReviseImageRequest`；session message 路径；`alchemy_v1_revise_image` | revision/session 的精确字段与继承/新准入映射待冻结，不猜现有字段 |
| `/api/v2/creative/runs`；`/api/v2/creative/runs/async` | `CreateCreativeRunRequest.output`; `alchemy_v2_create_creative_run` | `output.image_model_id`；两入口归一并透传至 V2-native Job |
| `/api/v2/image/jobs` | `CreateImageJobRequest` 只有 `prompt_plan`、`provider_hint`、`input_images` 等，无 `output`；`alchemy_v2_create_image_job` | 新增顶层 `image_model_id`；不得错误写入 `output.image_model_id` 或让 provider 参数覆盖它 |
| `/api/v2/outputs/{output_id}/revisions`；`/api/v2/outputs/{output_id}/revisions/async` | `CreateRevisionRunRequest` 有 `output` 与 `provider_hint` | 精确 JSONPath、显式换型号与复用原任务的边界待冻结 |
| `/api/lab/rare-style-explorer/sessions` | `alchemy_lab.py::ExplorationRequest`; `alchemy_lab_create_session` | session 选择与内部 variant/job 快照透传待冻结；不假设独立 variant override endpoint 已存在 |
| `/api/v3/creative-agent/projects/{project_id}/jobs`；`/api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/generate` | `CreateProjectJobRequest`、`auto_generate`、`GenerateJobRequest`; `alchemy_create_generation` | create/auto-generate/后续 generate 的唯一选型权威、具体 JSONPath 与冻结时点待冻结 |
| `/api/v3/creative-agent/jobs`；`/api/v3/creative-agent/jobs/{job_id}/generate` | 非 project product API | 核实与 project 路径等价的字段/准入/快照映射 |
| `/api/v3/creative-agent/projects/{project_id}/jobs/{parent_job_id}/ecommerce-slots/{slot_id}/continuations`；`/api/v3/creative-agent/projects/{project_id}/jobs/{parent_job_id}/photography-roles/{role_id}/continuations` | 既有专业任务 continuation | 冻结继承模型与显式新修订边界，不改变 slot/review 权威 |

入口证据位于 `src_skeleton/app/main.py`、`custom_media_agent_2_0/app/main.py`、各自 schemas/contracts，以及 MCP 的 `versioned_tools.py`/`product_tools.py`。上述 Alchemy 自有 `/async` endpoint 不等于 AISelf upstream async 响应支持。M0 仍须核对部署前缀/代理别名、所有活跃 Web/mobile 入口及其鉴权，不能把本表当作覆盖已完成的证明。

### M1 — 配置与受控模型目录

改动边界候选：

- 部署环境安全配置提供固定 AISelf HTTPS origin（管理员/用户请求和 runtime UI 均不能修改）；V1 runtime API/UI 只配置 server-side secret 引用、默认 model ID、allowlist/catalog profile。origin 按 scheme/host/effective port 完整匹配受信 allowlist，拒绝 HTTP、IP literal、环回/私网/link-local/保留地址；首期禁止所有 redirect，并用网络 egress 规则防 DNS rebinding。
- 复用现有管理员运行设置持久化及脱敏返回；不得在 V1/V2/V3/Lab 普通运行时响应中返回 secret。
- 定义只读、身份过滤的模型目录 projection；不要将原始 upstream `/v1/models` 全量暴露给普通用户。
- 每张启用卡片都必须有 capability profile；unknown 为 fail-closed。
- 普通 disable 只挡新准入；独立 security revocation 挡冻结任务执行。投影版本与撤销有界新鲜度必须在 V1/V2 各进程验证；历史/幂等只读回放不依赖当前目录。

最小单元测试：secret write/read redaction、不可注入 gateway origin、allowlisted HTTPS origin/egress、HTTP/IP literal/私网等拒绝、同 host 不同 port 与 HTTPS→HTTP redirect 不转发凭据、非管理员写入拒绝、重复/无效 ID 拒绝、未验证模型不可选、profile/config revision、普通禁用不挡冻结续跑、撤销/过期投影阻断执行但不挡授权读取、历史快照独立、admin default 回退。

### M2 — V1 与 V2 的请求/适配闭环

- V1：在 M0 冻结的生成/修订请求位置加入可选精确 ID；所有省略该字段的请求继续旧解析，包括没有 provider 字段的请求。先按授权 owner/session/key 与原请求意图回放既有 Job，再对全新任务解析现行配置；新字段进入幂等身份与 Job 快照。
- V2：只在 V2-native schemas/service/config/provider 内实现相同字段和解析规则，不能导入 V1 backend。保留现有 V2 account billing、asset input、case/template 以及 Provider isolation。V2 使用同一逻辑 secret 和版本一致的非敏感 model catalog 投影，但仍由 V2-native 适配器本地执行请求。
- 两边复用各自已有 HTTP 客户端和 Provider protocol；AISelf adapter 只实现已冻结的同步 inline base64 响应、拒绝 URL/async 响应，不重写图像业务流程。未知接单结果保留原 Job 且不自动重发；上游去重必须有 scope/TTL 证据，旧 provider 重试规则不改。
- 对 generation/edit/reference 做新准入校验；调用前按冻结 profile 校验最终 materialized reference pack 的数量/bytes/MIME/像素/mask/模式，再查新鲜撤销与冻结配置可用性。不能只查上传张数，不能丢图、转纯文本或改选 provider。
- 旧 job 仍可查询、重试/续跑按原 snapshot。

### M3 — Lab 与 V3 任务选择闭环

- Lab session 保存创建时显式选择，内部 variant 继承这次选择，用户新 override 显式提交；字段省略的新请求保留旧行为。取消/恢复/收藏等 session 并发语义不变，每个 variant/job 快照独立。
- V3：正式 generation request 接收具体 ID；新 UI 将展示的管理员默认也显式提交，省略字段仍旧解析。改 generation router 中的固定模型解析而非 Brain/template；model/profile/route-config snapshot 进入 V3 job/provider metadata。
- 更新 Doc100：只替换 sole renderer identity 为“gateway allowlisted model selection”；保留纯远程 final-pixel、参考图所有权、真实 Vision review、最佳候选、bounded retry 和无静默 fallback 所有规则。
- V3 retry、resume、continuation 使用冻结模型/profile/route；普通 disable 不阻断已准入任务。明确安全撤销、撤销新鲜度不满足或冻结配置不可用才阻断执行，历史与授权幂等回放仍只读可用。
- 对 V3 General、Photography、E-Commerce、Brand、新媒体等现有模块只验证能力，不在本层增加垂类输出逻辑。

### M4 — Web、API 与 MCP 体验

- 桌面与移动使用同一安全模型目录投影，选择字段透传且切换页面不会漂移。
- V1/V2/V3/Lab 各入口显示不同的任务兼容状态；参考图任务只列满足要求的模型。
- API/HTTP-backed product MCP 能读取允许的 model cards 并传精确 ID；不能写管理员目录或获得网关 secret。新选择器的默认值/唯一选项也显式提交，0 个兼容型号不能静默切回 legacy。
- `GET /api/image-models` 使用现有认证/API scope，并按 module/operation/reference requirements 返回安全模型卡片；MCP 通过同一 HTTP endpoint 读取，不复制一份目录。
- 任务进度/历史展示 job snapshot，不被后续管理员改默认值追溯改变。
- 对不兼容选项显示清楚原因；提交服务端再次校验，客户端过滤不是安全边界。
- Native ImageGen 和 frozen/materialized handoff 不增加 AISelf 路由；不支持的 `image_model_id` 必须在执行前明确拒绝，原无该字段行为不变，不能丢弃字段并误报所选型号。

### M5 — 用量、错误和支持证据

- 记录安全字段：requested model ID、optional served model ID/status、gateway request ID、operation、profile revision、execution-contract/route-config revision、非敏感内部 route reference、latency、returned usage/cost when available；公开响应仍遵守白名单。
- 删除/脱敏 Authorization、完整 prompts、图像 bytes/base64、私人网关路由字段。
- 将 upstream usage/cost 与 Alchemy 用户侧扣费分开；完整复用已有计费交易与失败/退款约束。
- 规范新准入禁用、执行安全撤销/配置不可用、缺失密钥、401、429、超时/接单未知、参数不支持、5xx、空结果、unsupported response 和 served-model mismatch；不把未知接单当未收费失败，不自动重复可能付费的调用。

### M6 — 回归、灰度与放量

- 按 04 文档完成测试，先用 mock/recorded contract，不调用真实上游。
- 本地单型号旧默认对照，通过后在测试环境对每个启用型号做最小生成和编辑/参考场景。
- 小范围开启一张已验证 model card；先 V1/V2/Lab，再 V3 (V3 governance变更单独 gate)。可按模块 feature flag 回退。
- 观察成功率、参数拒绝率、延迟、上游计价差异、Alchemyside billing consistency、用户选型分布和多模态素材任务兼容率。
- 完成独立安全/数据/费用审计后才可扩大。

## 3. Change map（候选边界，不是预先授权的改动全集）

| Area | Current evidence location | Expected implementation boundary |
|---|---|---|
| V1 API/schema | `src_skeleton/app/schemas.py`, `main.py`, `services/image_service.py` | Optional request model ID; legacy parser; job snapshot/idempotency |
| V1 adapter/config | `src_skeleton/app/config.py`, `providers/`, `main.py` runtime provider-settings routes | Existing HTTP transport to AISelf; redacted admin settings |
| V1 desktop/mobile | `src_skeleton/app/static/`, `mobile_static/` | Model cards and capability-based filtering |
| V2 independent runtime | `custom_media_agent_2_0/app/schemas.py`, `services/generation.py`, `providers/images/`, `config.py` | V2-native request resolution and adapter; no V1 imports |
| V2 frontend/admin | shared shell files plus V2 APIs | Pass selected model and show safe job snapshot |
| Lab | `src_skeleton/app/services/alchemy_lab.py`, `session_service.py`, Lab schemas/UI | Session preference and per-variant snapshot |
| V3 router | `alchemy_creative_agent_3_0/app/generation_router/providers.py`, V3 API/service schemas | Request-scoped model injection; keep business/review path |
| V3 authority | `alchemy_creative_agent_3_0/docs/100_V3_GPT_IMAGE_2_SOLE_RENDERER_AND_ADAPTIVE_RERENDER_GOVERNANCE_SPEC.md` | Supersede only sole-model rule on implementation |
| HTTP API/MCP | existing public API schemas and `services/alchemy_codex_local_adapter/` | Model catalog read + optional selection pass-through |
| General config docs | `docs/21_密钥与部署配置.md` | One secret reference and migration/rollback instructions |

Do not treat file location alone as permission to change unrelated behavior in that module. A concrete TaskSpec must assign disjoint write sets or use one writer for shared contracts.

## 4. Data compatibility and rollout

- No bulk rewrite of past Job/session/output data. Existing history stays in its original model/provider vocabulary.
- New optional fields use additive migration/defaults. Backfill is not required to launch selector.
- Start from the existing default `gpt-image-2` only if the AISelf route has passed integration validation. If it has not, retain the current live route as configured and do not assert all products already use AISelf.
- Run old and new adapters side by side only during an explicit feature-flagged transition; never shadow-call paid providers.
- Feature-flag rollback disables new gateway admission/selector and restores the legacy UI/request path for new work; explicit AISelf requests then fail clearly instead of silently changing route. A compatible new worker may finish admitted Jobs using frozen snapshots and fresh revocation checks.
- Binary rollback is a separate operation: before old workers can consume the queue, drain new snapshots with compatible workers or stop/isolate their execution using existing controls. Old binaries must never execute unknown gateway/snapshot versions by treating them as legacy/default jobs. If existing controls cannot prove this exclusion, old-binary rollback is blocked. Do not add a queue merely to satisfy rollback.
- Do not remove legacy provider credentials/config until logs prove no old queued jobs or external clients require them and a separate change approves removal.

## 5. Risks and mitigation

| Risk | Mitigation |
|---|---|
| Gateway serves a different model than requested | Exact request model; record served model if present; mismatch is failure |
| Model does not support reference/edit workflow | Capability profile + server-side preflight; never drop image input |
| Model list contains opaque/ambiguous IDs | Disabled until admin verifies exact route and capability; display opaque ID |
| Model price not known | Mark estimate unavailable; preserve existing Alchemy billing; report upstream cost only if returned |
| Admin default changes during queued work | Freeze snapshot at admission; resume from snapshot |
| V3 Doc100 conflicts with selector | Explicit narrow governance change and tests; until then V3 remains fixed |
| V2 isolation regresses | Cross-tree import test and V2 standalone test environment |
| One credential increases blast radius | Secret redaction, admin-only changes, provider-call audit, budget/limit protections, rotation runbook |

## 6. Definition of implementation complete

The feature is not “done” when dropdowns render. It is complete only when all supported front doors pass the same model ID to their own native generation path; jobs/history show the frozen requested identity; unsupported capability and unknown model stop before paid calls; no silent fallback/secret leak occurs; all existing billing, review, reference, access and session invariants pass; live staged model matrix and rollback are recorded.
