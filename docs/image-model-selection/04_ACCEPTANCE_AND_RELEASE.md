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
| CAT-03 | Catalog | 禁用/过期/profile 缺字段 | 不可选择；历史仍可读取 |
| CAT-04 | Admin | 管理员改 default/profile | secret readback 永不返回；profile revision 更新；新 Job 生效、现有 Job 不变；旧 Job 仍显示创建时 model ID/display name |
| CAT-05 | Admin | 普通用户写模型目录/base URL/key | 403/拒绝；配置无变化；gateway origin 只能来自受信部署 allowlist |
| SEC-01 | Egress | 配置及请求重定向 | 只允许 allowlisted HTTPS gateway origin；拒绝 HTTP、IP literal、loopback/private/link-local/reserved 目标；跨 host redirect 不转发凭据 |
| SEC-02 | Deployment egress | V1 与 V2 运行时的解析/egress | 在部署环境分别验证 DNS rebinding 到私网地址被网络出口规则阻断；仅 URL 字符串校验或单元测试不足以放行 |
| RES-01 | Resolve | request 显式 ID | 使用该 exact ID，不受浏览器默认、session default 或 admin default 干扰 |
| RES-02 | Resolve | 未传 ID 的旧请求 | 兼容既有模块解析和当前默认；不得无意切换用户现有流量 |
| RES-03 | Resolve | 未知/disabled/unverified ID | 有明确 4xx/配置错误；零 provider 调用、零扣费、无成功 Job |
| RES-04 | Resolve | 新 ID 与旧 provider 字段矛盾 | 可预测拒绝/兼容规则；绝不按旧 provider 猜另一模型 |
| CAP-01 | Capabilities | 文本生成 | 只允许已验证 generate 模型 |
| CAP-02 | Capabilities | 参考图编辑 | 必须同时验证 edit 和 reference 输入；原图确实送出 |
| CAP-03 | Capabilities | mask/transparent/size/quality/count | 不支持/unknown 被拒绝或移除 UI 选项；不静默改变请求语义 |
| RET-01 | Retry | transport retry | 同一 Job/model ID；不改变 idempotency identity |
| RET-02 | Retry | quality rerender/resume | 使用 Job snapshot 的同一模型；沿用现有 retry budget |
| RET-03 | Retry | catalog 更新后继续旧任务 | 使用已冻结 profile/model；若安全要求 profile 已撤销则 fail closed，不选默认 |
| IDEM-01 | Idempotency | 相同 key/owner/payload/model | 复用本用户既有 Job，无重复费用 |
| IDEM-02 | Idempotency | 同 key 但不同 model ID | 冲突，不返回另一型号的结果 |
| IDEM-03 | Idempotency | 系统派生 key 且所选 model ID 不同 | 派生指纹不同；不会复用另一型号 Job |
| HIST-01 | History | 管理员更新 default 后查看旧 job | 显示创建时 model snapshot，不用现行默认覆盖 |
| HIST-02 | History/Resume | rename/disable/semantic revision 后读取或恢复旧 Job | 历史使用冻结的 ID/display-name/profile snapshot；续跑只能用冻结配置，若旧 route 已不可用则安全失败，不得解析成当前 default |
| PRIV-01 | Security | 日志/异常/API 响应 | 无 Authorization、key、base64 图像、私有上游帐号路由 |
| BILL-01 | Billing | 网关返回 usage/cost | 与 Alchemy customer charge 分开保存，数值精度正确 |
| BILL-02 | Billing | 网关没有可用价格 | 估价明确 unavailable；现有余额和计费检查仍执行 |
| MISM-01 | Routing identity | gateway 回报 served model 不同 | job 不呈现为成功调用了用户选定模型；保留可诊断、脱敏证据 |
| UI-01 | Desktop/Mobile | 可选模型数量从 0/1/N 变化 | 0 显示配置状态，1 明示唯一型号，N 可选；两端目录和错误一致 |
| API-01 | HTTP/MCP | 列目录、提交模型 ID | 只允许用户可见模型；生成按现有 API/MCP 身份和 billing 运行 |
| API-02 | HTTP/MCP | 低权限身份伪造 `module=v3` 查询目录 | 仅返回实际授权模块可见目录（或按既有语义拒绝）；不泄露 V3 catalog；MCP 同样验证真实调用身份 |
| ISO-01 | Module isolation | V2 standalone/import graph | 没有 V1 backend/storage/provider import；V2 自身模型快照正确 |
| V3-01 | V3 governance | 请求所选模型 + review | 选型不绕过 Vision、review、winner、delivery gates |
| V3-02 | V3 specialization | General / E-commerce / Photography / Brand / New Media | 只变 renderer route；垂类 deliverable map 不流入 General/shared cluster |
| LAB-01 | Lab | variant-level override, concurrent progress/favorite | 每个 variant 用自己的 snapshot；原 session mutation/save merge regression 全过 |
| OLD-01 | Compatibility | 历史 V1/V2/V3/Lab records | 可完整读；无 bulk rewrite；旧 retry semantics 保留 |

## 3. Mock/contract test design

HTTP fake transport must capture final outbound request and assert:

- configured AISelf origin/path and server Authorization only;
- exact `model` field equals the selected opaque ID;
- prompt, size/quality/format/count and reference files are passed unchanged according to the selected model profile;
- no provider key, base URL, capability claim, price, `served_model_id` or upstream channel from client JSON is trusted;
- gateway request ID / served model / usage are parsed only from allowed response fields;
- auth headers and image bytes do not enter application log fixtures;
- all supported product flows (`V1`, V2-native process, V3, Lab) pass through their current billing/asset/review boundaries.

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
| Configuration | base URL fingerprint (not secret), secret presence only, catalog/profile revision |
| Request | exact requested ID, operation, sanitized params, gateway request ID |
| Actual route | gateway served-model report if available; otherwise `not reported` |
| Result | output count, MIME, dimensions, reference handling, latency, safe error |
| Billing | Alchemy customer charge/refund and gateway returned usage/cost as distinct values |
| Quality/review | Product-appropriate existing quality/review receipt; no claim from HTTP 200 alone |

At minimum, test text generation for each model selected for general availability. Separately test reference/edit for models enabled in those workflows. A failed or unknown row keeps that model disabled for the affected operation; it does not block unrelated verified models.

## 5. Rollout gates and rollback

| Gate | Required evidence | Action allowed after pass |
|---|---|---|
| G0 Design | independent design audit PASS; AISelf interface facts known | begin implementation |
| G1 Local | unit, compatibility, cross-product tests; no real calls | deploy to isolated test environment |
| G2 Staging model | per-ID/operation route, output, review and billing records | enable that model for a limited module/cohort |
| G3 Production canary | exact deployed SHA, health, error/latency/cost telemetry, no mismatch or privacy leak | expand approved model availability |
| G4 Full | all advertised model-operation combinations reviewed | general release |

Rollback sequence: disable the new selector/individual catalog entry; pin new jobs to the previous configured route; keep in-flight job snapshots unchanged; verify Web/API/MCP errors and legacy paths; preserve histories for diagnosis. Do not delete jobs, rewrite historical model identity, or automatically resubmit paid generation.

## 6. Release blockers

Any of the following blocks release for the affected model/module:

- unknown or conflicting gateway auth/route contract;
- selected model silently replaced or cannot be verified as requested;
- reference/edit inputs dropped or degraded to text-only;
- credentials appear in client response/logs;
- model selection bypasses an existing budget/charge/permissions/review gate;
- old client requests or queued jobs change model unexpectedly;
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
