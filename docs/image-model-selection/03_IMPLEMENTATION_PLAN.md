# Alchemy 图片模型选择：分阶段开发计划

状态：提案，仅供实施前审计。

实施原则：一次只改一层；每章先添加失败测试，再实现最小契约；不可把本计划当作代码已存在。

## 1. 边界与前置条件

### 范围

- V1、V2、V3、Alchemy Lab 图片生成/修订入口。
- 桌面和移动 Web、现有 HTTP API、现有 MCP 调用表面。
- 一个服务端配置的 AISelf 图像统一网关；按精确模型 ID 路由。
- 能力兼容校验、任务模型快照、可靠状态/费用元数据、旧请求兼容。

### 不在范围

- AISelf Gateway 本身、404token/Sub2API、其上游账号/渠道分组和模型购买。
- 改 LLM/Brain 选择、模板业务职责、提示词质量策略、视觉审核阈值、生成数量默认值。
- 另建用户 BYOK、租户凭据系统、计费台账、队列、模型市场、自动模型 fallback 或复杂性能缓存。
- 仅为提供选择器而重写 V1/V2/V3 的 job schema、store、历史或 provider 架构。

### 开工硬门槛

实施前在 `AISelf Integration Facts` 表中冻结独立网关工作的结果：base URL/auth、generation/edit 请求形状、reference/multipart、成功与异步响应、错误、request ID、served model 和 usage/cost 字段。还必须确认 Alchemy 的一个逻辑 secret 和一份受版本控制的公开模型目录如何安全供应给独立 V2 进程；不允许要求用户在 V1 和 V2 两处重复录入 key。模型 ID 和能力需使用已通过 AISelf 实际验证的清单；名称猜测或模型页面截图不能当作能力证明。

若 AISelf 的目标合同暂不可用，可先实现无网络的 catalog/schema 骨架与测试，但不得接入真实生图、启用模型或部署。

## 2. 里程碑

### M0 — 契约锁定与影响盘点

1. 将 01/02 文档审计意见收敛成固定接口映射表。
2. 核对每个 product 的确切请求 schema、Job 持久化字段、重试/恢复、revision 和 idempotency 入口。
3. 确认 AISelf 返回字段与每种 edit/reference 输入的真实样例。
4. 更新冻结清单：基线 SHA、数据库/历史兼容、文件白名单、审计等级、回滚点。

退出条件：没有未定的公开字段位置/密钥来源/请求路由事实；各模块 owner 和测试目录确定。

### M1 — 配置与受控模型目录

改动边界候选：

- `src_skeleton/app/config.py`, `schemas.py`, 管理 runtime API/UI：添加 AISelf base URL 和 server-side secret 引用、默认 model ID、allowlist/catalog profile。
- 复用现有管理员运行设置持久化及脱敏返回；不得在 V1/V2/V3/Lab 普通运行时响应中返回 secret。
- 定义只读、身份过滤的模型目录 projection；不要将原始 upstream `/v1/models` 全量暴露给普通用户。
- 每张启用卡片都必须有 capability profile；unknown 为 fail-closed。

最小单元测试：secret write/read redaction、非管理员拒绝管理写入、重复/无效 ID 拒绝、未知模型不出现在可选目录、profile 更新 revision、禁用不删历史、admin default 回退。

### M2 — V1 与 V2 的请求/适配闭环

- V1：在生成/修订请求加入可选精确 ID；旧 provider-only 请求继续旧解析；新字段进入幂等签名与 Job 快照。
- V2：只在 V2-native schemas/service/config/provider 内实现相同字段和解析规则，不能导入 V1 backend。保留现有 V2 account billing、asset input、case/template 以及 Provider isolation。V2 使用同一逻辑 secret 和版本一致的非敏感 model catalog 投影，但仍由 V2-native 适配器本地执行请求。
- 两边都复用各自已有 HTTP 客户端习惯和 Provider protocol；只把 base URL/key/model 转到 AISelf；不重写图像业务流程。
- 对 generation/edit/reference capability 做准入校验。禁止因选了不兼容模型而丢图、转纯文本或改选 provider。
- 旧 job 仍可查询、重试/续跑按原 snapshot。

### M3 — Lab 与 V3 任务选择闭环

- Lab session 保存当前模型偏好，variant 显式选择可覆盖；取消/恢复/收藏等 session 并发语义不被改变。每个 variant/job 快照独立。
- V3：在正式 generation request 解析用户/管理员默认；改 generation router 中的固定模型解析而非 Brain 或 template；model/profile snapshot 进入 V3 job/provider metadata。
- 更新 Doc100：只替换 sole renderer identity 为“gateway allowlisted model selection”；保留纯远程 final-pixel、参考图所有权、真实 Vision review、最佳候选、bounded retry 和无静默 fallback 所有规则。
- V3 retry、resume、continuation 同模型；模型不再 enabled 时阻断该未完成任务并提供明确原因。
- 对 V3 General、Photography、E-Commerce、Brand、新媒体等现有模块只验证能力，不在本层增加垂类输出逻辑。

### M4 — Web、API 与 MCP 体验

- 桌面与移动使用同一安全模型目录投影，选择字段透传且切换页面不会漂移。
- V1/V2/V3/Lab 各入口显示不同的任务兼容状态；参考图任务只列满足要求的模型。
- API/MCP 能读取允许的 model cards 并传可选精确 ID；不能写管理员目录或获得网关 secret。
- 任务进度/历史展示 job snapshot，不被后续管理员改默认值追溯改变。
- 对不兼容选项显示清楚原因；提交服务端再次校验，客户端过滤不是安全边界。

### M5 — 用量、错误和支持证据

- 记录安全字段：requested model ID、optional served model ID/status、gateway request ID、operation、profile revision、latency、returned usage/cost when available。
- 删除/脱敏 Authorization、完整 prompts、图像 bytes/base64、私人网关路由字段。
- 将 upstream usage/cost 与 Alchemy 用户侧扣费分开；完整复用已有计费交易与失败/退款约束。
- 规范模型禁用、缺失密钥、401、429、超时、参数不支持、网关 5xx、空结果和 served-model mismatch 的用户错误及任务状态。

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
| V1 adapter/config | `src_skeleton/app/config.py`, `providers/`, `services/runtime_model_settings.py` | Existing HTTP transport to AISelf; redacted admin settings |
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
- Rollback disables the selector and returns new jobs to the pre-migration configured default, while in-flight jobs continue with their frozen adapter/model snapshot.
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
