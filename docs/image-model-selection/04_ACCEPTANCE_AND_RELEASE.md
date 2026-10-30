# Alchemy 图片模型选择：测试、审计与发布验收

状态：实施验收规范，非当前代码测试结果。当前 PR 仅含设计文档，尚未实现本表功能。

## 1. 验收原则

- 分开判断：文档/实现正确性、AISelf route provenance、性能/稳定性、真实模型可用性、生产发布资格。
- Mock contract tests 可以证明 Alchemy 发送了什么，不可以证明网关真实路由、上游支持能力、图片质量、价格或 VPS 可用性。
- 未经授权不发起付费生成。部署前的代码审计不得调用真实模型。
- 真实验收只针对明确启用的 model ID、任务类型和素材能力，不以一个 text-to-image 样例推论所有图像操作可用。

## 2. 测试矩阵

| ID | 层 | 场景 | 通过条件 |
|---|---|---|---|
| CAT-01 | Catalog | 已启用且经验证模型 | 只返回安全用户字段；准确 model ID 不变 |
| CAT-02 | Catalog | Gateway 可发现但未分类的新模型 | 不向一般用户展示、不被自动启用 |
| CAT-03 | Catalog | 普通禁用/未验证/profile 缺字段 | 不允许新准入；普通禁用不阻断冻结任务；历史仍可读取 |
| CAT-04 | Admin | 管理员改 default/profile | secret readback 永不返回；profile revision 更新；新 Job 生效、现有 Job 不变；旧 Job 仍显示创建时 model ID/display name |
| CAT-05 | Admin | 普通用户写模型目录/base URL/key | 403/拒绝；配置无变化；gateway origin 只能来自受信部署 allowlist |
| CAT-06 | Catalog/UI | 默认模型可见/无权/不兼容/不可用 | `is_default` 仅对有权且兼容默认为 true、最多一项；默认不可用则全部 false 且 UI 明示无默认，不泄露隐藏 ID、不猜替代型号；提交仍传用户确认的具体 ID |
| SEC-01 | Egress | 配置及请求重定向 | 按 scheme/host/effective port 匹配 allowlisted HTTPS origin；拒绝 HTTP、IP literal、loopback/private/link-local/reserved；首期不跟随任何 redirect，零凭据转发 |
| SEC-02 | Deployment egress | V1 与 V2 运行时的解析/egress | 在部署环境分别验证 DNS rebinding 到私网地址被网络出口规则阻断；仅 URL 字符串校验或单元测试不足以放行 |
| SEC-03 | Egress | 同 host 不同 port、HTTPS→HTTP、跨 host redirect | 全部拒绝，包含 307/308 重定向；目标端收到零请求/Authorization/图片数据；不能仅按 hostname 判同源 |
| RES-01 | Resolve | request 显式 ID | 使用该 exact ID，不受浏览器默认、session default 或 admin default 干扰 |
| RES-02 | Resolve | 未传 ID，有/无 legacy provider/session 字段 | 全部走原模块解析/默认；改变 AISelf default 不改变旧流量，不推断客户端新旧 |
| RES-03 | Resolve | 未知/disabled/unverified ID | 有明确 4xx/配置错误；零 provider 调用、零扣费、无成功 Job |
| RES-04 | Resolve | 新 ID 与旧 provider 字段矛盾 | 按有效精确 ID 执行，legacy 字段不能重定向；新 ID 无效则拒绝，不回退旧 provider |
| RES-05 | Resolve | 新 UI 默认/唯一选项与 0 个兼容选项 | 默认/唯一值显式传具体 ID；0 选项阻止新选型提交，不通过省略字段偷偷回退 |
| CAP-01 | Capabilities | 文本生成 | 只允许已验证 generate 模型 |
| CAP-02 | Capabilities | 参考图编辑 | 必须同时验证 edit 和 reference 输入；原图确实送出 |
| CAP-03 | Capabilities | mask/transparent/size/quality/count | 不支持/unknown 被拒绝或移除 UI 选项；不静默改变请求语义 |
| CAP-04 | Capabilities | 上传素材经裁切/身份细节/模板引用展开后超限 | 付费调用前检查最终 materialized pack 的张数、单项/总 bytes、MIME、像素/尺寸、mask 配对、输入模式；超限零 provider 调用，不删图 |
| RET-01 | Retry | legacy 与新 AISelf transport retry | legacy 行为不变；新 AISelf 仅在确定未接单或有有效 scope/TTL 去重证据时复用同一请求重试，model/Job 不变 |
| RET-02 | Retry | quality rerender/resume | 使用 Job snapshot 的同一模型；沿用现有 retry budget |
| RET-03 | Retry | profile 更新/普通 disable 后继续旧任务 | 继续冻结 model/profile/route；不套用当前 enabled；新准入仍拒绝 disabled 型号 |
| RET-04 | Retry | 新 AISelf 超时、连接断开或接单后响应丢失 | 原 Job/attempt 保留；结果未知时不自动重发、不建替代 Job、不伪造退款/失败未收费；TTL 已过或去重未证实时也不重发 |
| RET-05 | Retry | profile/route 安全撤销或冻结配置不可用 | 执行阻断且原因清楚；不替代默认；授权历史/完成结果回放仍可读 |
| IDEM-01 | Idempotency | 相同 key/owner/payload/model | 复用本用户既有 Job，无重复费用 |
| IDEM-02 | Idempotency | 同 key 但不同 model ID | 冲突，不返回另一型号的结果 |
| IDEM-03 | Idempotency | 系统派生 key 且所选 model ID 不同 | 派生指纹不同；不会复用另一型号 Job |
| IDEM-04 | Idempotency | 相同显式 key/原意图，default/profile 已变或模型已禁用/撤销 | 先鉴权，再 owner/session/key 查旧 Job，按原意图（含省略标记）只读回放冻结结果；不先解析现行默认/目录，不触发生成 |
| IDEM-05 | Auth/replay | 跨 owner、跨 session/project、未登录或已失去 scope 的 key 重放 | 未授权目标按既有语义拒绝；零 Job/output/存在性泄露，零 provider 调用；同 key 在各授权作用域按既有独立规则处理 |
| IDEM-06 | Idempotency | 并发相同 key；同 key 改型号；旧记录缺少原意图证据 | 并发收敛一个 Job/付费调用；改型号明确冲突；缺证据安全拒绝、不猜默认或重发 |
| HIST-01 | History | 管理员更新 default 后查看旧 job | 显示创建时 model snapshot，不用现行默认覆盖 |
| HIST-02 | History/Resume | rename/disable/semantic revision 后读取或恢复旧 Job | 历史/幂等读取不重新准入；普通禁用仍可按冻结配置续跑；新鲜安全撤销或旧 route 不可用才阻断执行，不解析当前 default |
| HIST-03 | Snapshot | route/config 更新但 model ID 未变 | 固定 execution contract、非敏感 route reference/config revision 与能力快照；执行不悄悄换路由，公开响应不暴露内部 route reference |
| PRIV-01 | Security | 日志/异常/API 响应 | 无 Authorization、key、base64 图像、私有上游帐号路由 |
| BILL-01 | Billing | 网关返回 usage/cost | 与 Alchemy customer charge 分开保存，数值精度正确 |
| BILL-02 | Billing | 网关没有可用价格 | 估价明确 unavailable；现有余额和计费检查仍执行 |
| MISM-01 | Routing identity | gateway 回报 served model 不同 | job 不呈现为成功调用了用户选定模型；保留可诊断、脱敏证据 |
| RESP-01 | Gateway response | inline base64 正常、无效、过大或 MIME/像素/count 不符 | 只接受冻结合同内的同步内联图片；严格解码/大小/格式校验，不持久化原始 base64 |
| RESP-02 | Gateway response | URL-only/mixed URL、accepted/async 响应 | 首期拒绝且零 URL 下载/poll/cancel/自动重发；保留安全原 Job 证据，不能推断未接单/未收费 |
| UI-01 | Desktop/Mobile | 可选模型数量从 0/1/N 变化 | 0 显示配置状态，1 明示唯一型号，N 可选；两端目录和错误一致 |
| API-01 | HTTP/product MCP | 列目录、提交模型 ID | 只允许用户可见模型；HTTP-backed 工具按现有身份和 billing 运行，最终 outbound model 与选择一致 |
| API-02 | HTTP/product MCP | 低权限身份伪造 `module=v3` 查询目录 | 仅返回实际授权模块目录（或按既有语义拒绝）；不泄露 V3 catalog；HTTP-backed MCP 同样验证真实身份 |
| API-03 | Endpoint mapping | V2 creative、direct image-job、revision 及 MCP 透传 | creative 用 `output.image_model_id`；direct `/api/v2/image/jobs` 用顶层字段；其余按 M0 冻结 JSONPath，全链不能丢弃或重解释字段 |
| MCP-01 | Native/handoff | 不支持的 AISelf ID 注入 Native ImageGen 或 frozen/materialized handoff 工具 | 明确拒绝且无规划/生成/付费调用、不误标 AISelf；原无该字段的 native/handoff 路径保持不变 |
| ISO-01 | Module isolation | V2 standalone/import graph | 没有 V1 backend/storage/provider import；V2 自身模型快照正确 |
| ISO-02 | V2 config/revocation | 投影过期、回退、缺失、版本不兼容、撤销更新 | source/version/revision 校验及 M0 冻结的最大陈旧界限有效；新准入/续跑在界限外 fail closed；授权历史可读，不增配置服务 |
| V3-01 | V3 governance | 请求所选模型 + review | 选型不绕过 Vision、review、winner、delivery gates |
| V3-02 | V3 specialization | General / E-commerce / Photography / Brand / New Media | 只变 renderer route；垂类 deliverable map 不流入 General/shared cluster |
| LAB-01 | Lab | variant-level override, concurrent progress/favorite | 每个 variant 用自己的 snapshot；原 session mutation/save merge regression 全过 |
| OLD-01 | Compatibility | 历史 V1/V2/V3/Lab records | 可完整读；无 bulk rewrite；旧 retry semantics 保留 |
| ROLL-01 | Feature flag | 关闭新选择器/网关准入 | 新请求回原 UI/legacy 路径；显式 AISelf ID 拒绝而非改路由；兼容 worker 按旧快照完成已准入任务 |
| ROLL-02 | Binary rollback | 旧 worker 遇到新 gateway/未知 snapshot version | 回滚前用现有控制排空或隔离/暂停这些任务；证明旧 worker 不消费/执行未知快照，不能按 legacy default 生成 |

## 3. Mock/contract test design

HTTP fake transport must capture final outbound request and assert:

- configured AISelf origin/path and server Authorization only;
- exact `model` field equals the selected opaque ID;
- prompt, size/quality/format/count and the final product-materialized reference pack follow the frozen profile and existing reference ownership rules; adapter cannot omit references to fit limits;
- no provider key, base URL, capability claim, price, `served_model_id` or upstream channel from client JSON is trusted;
- gateway request ID / served model / usage are parsed only from allowed response fields;
- auth headers and image bytes do not enter application log fixtures;
- all supported product flows (`V1`, V2-native process, V3, Lab) pass through their current billing/asset/review boundaries.

Deterministic cases must change admin defaults between original submission and explicit-key replay, disable versus security-revoke a queued model, expire a V2 revocation projection, and expand one uploaded asset into an over-limit materialized pack. Fake endpoints must prove zero requests to response URLs, redirected ports or polling URLs, and zero repeat paid calls after an uncertain acceptance without verified deduplication. These tests are required future evidence, not results from this documentation-only PR.

Golden tests should include misleading IDs (`gpt-image-2.5`, `gpt-image-2.5-flare`, `gpt-image-2.5-sunburst`, `grok-imagine-image-*`) as opaque sample strings only. The test asserts capability comes from the profile, not the name; it does not claim those IDs exist or route in production.

## 4. Cross-product and real acceptance

### Code acceptance (no real provider)

1. Run each product's focused test suite and complete API contract tests.
2. Run V2 tests in its isolated runtime and assert no V1 backend imports.
3. Run desktop/mobile JS and browser interaction tests where the repository supports them.
4. Run settings migration, old-record read, idempotency, retry/resume and session concurrency regressions.
5. Review route/privacy/billing evidence with an independent A2 auditor.

### Staged upstream acceptance (after explicit cost authorization)

For each individual enabled model ID, record a row with:

| Evidence | Required record |
|---|---|
| Configuration | base URL fingerprint (not secret), secret presence only, catalog/profile/config revision, execution-contract version, revocation freshness |
| Request | exact requested ID, operation, sanitized params, gateway request ID |
| Actual route | gateway served-model report if available; otherwise `not reported` |
| Result | confirmed synchronous inline base64 mode, output count/MIME/dimensions, final reference-pack limits, latency, safe error |
| Billing | Alchemy customer charge/refund and gateway returned usage/cost as distinct values |
| Quality/review | Product-appropriate existing quality/review receipt; no claim from HTTP 200 alone |
| Gateway failure facts | timeout/accepted-unknown, idempotency scope/TTL, error/partial charges, poll/cancel availability and cost semantics; documented evidence, not unapproved paid fault injection |

At minimum, test text generation for each model selected for general availability. Separately test reference/edit for models enabled in those workflows. A failed or unknown row keeps that model disabled for the affected operation; it does not block unrelated verified models.

## 5. Rollout gates and rollback

| Gate | Required evidence | Action allowed after pass |
|---|---|---|
| G0 Design/integration facts | independent revised-design audit PASS; exact M0 field maps, AISelf inline response/auth/acceptance/dedup/error/cost facts, V2 config delivery/version/freshness bound frozen | begin M1–M6 gateway implementation; no assumed upstream availability |
| G1 Local | unit, compatibility, cross-product tests; no real calls | deploy to isolated test environment |
| G2 Staging model | per-ID/operation route, output, review and billing records | enable that model for a limited module/cohort |
| G3 Production canary | exact deployed SHA, health, error/latency/cost telemetry, no mismatch or privacy leak | expand approved model availability |
| G4 Full | all advertised model-operation combinations reviewed | general release |

Before G0, only offline M0 inventory/schema work and deterministic tests are permitted, without credentials, real calls, model enablement or deployment. This exception does not pass G0 or authorize a gateway adapter based on unconfirmed facts. AISelf inline response availability is still an external precondition; URL/async support requires a separate revised contract and is not an automatic fallback.

Feature-flag rollback: disable new gateway admission/selector and restore the original legacy UI/request path for new work; explicitly supplied AISelf IDs fail clearly. Compatible workers keep admitted snapshots, with fresh security revocation checks. Verify Web/API/HTTP-backed MCP behavior and preserve history; ordinary catalog disablement alone must not stop these frozen Jobs.

Old-binary rollback: first drain new snapshots with compatible workers or isolate/pause them through existing worker/queue controls. Verify old workers cannot consume or execute unknown gateway/snapshot versions; otherwise the binary rollback is blocked. A selector flag does not provide this protection. Do not add a new queue, delete jobs, rewrite historical identity, or automatically resubmit paid generation.

## 6. Release blockers

Any of the following blocks release for the affected model/module:

- unknown or conflicting gateway auth/route contract;
- no confirmed synchronous inline response contract, unreviewed URL/async enablement, or automatic repeat of an uncertain paid call without upstream deduplication proof;
- selected model silently replaced or cannot be verified as requested;
- reference/edit inputs dropped or degraded to text-only;
- credentials appear in client response/logs;
- model selection bypasses an existing budget/charge/permissions/review gate;
- old client requests or queued jobs change model unexpectedly;
- unauthorized idempotency replay leaks a Job/output, or replay resolves a changed default instead of the original intent;
- V2 configuration/revocation freshness is unbounded or an old worker can execute an unknown gateway snapshot;
- V2 isolation, V3 quality/result closure, or Lab persistence/concurrency regression;
- no reproducible rollback to the previous route.

## 7. Design-audit questions for Dot

Review the frozen PR and answer `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE` on each item:

1. Does the proposed one-key AISelf gateway model preserve current V1/V2/V3/Lab separation and user-visible behavior?
2. Is the capability allowlist (unknown disabled, task filter server-side) an appropriately small boundary, or is any catalog/registry abstraction unnecessary or unsafe?
3. Are request field placements and old-client compatibility realistic for current schemas and API/MCP contracts?
4. Are job snapshot, retry/resume, idempotency and model-default precedence sufficient to prevent silent model drift/duplicate charges?
5. Are reference/edit and V3 Doc100 governance changes constrained to route selection while preserving product quality authority?
6. Are gateway usage/cost, Alchemy customer billing and model identity separated correctly?
7. Are any necessary acceptance/rollback gates missing or any proposed claims unsupported by evidence?

Provide file/section-specific findings, minimal changes and severity. Do not implement or modify the PR during audit. The PR remains Draft until an independent audit and subsequent implementation plan review are complete.
