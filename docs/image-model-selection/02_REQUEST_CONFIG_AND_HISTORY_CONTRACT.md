# Alchemy 图片模型选择：请求、配置与历史契约

状态：提案。本文定义跨产品语义；各版本可保留各自现有请求结构。

规范词汇：`image_model_id` 为 Alchemy 选择的精确图片模型 ID；它是 opaque string，不做别名推断。

## 1. 公共语义

### 1.1 请求字段

- 字段可选，以兼容所有省略该字段的请求；新选择器及采用该功能的 API/HTTP-backed product MCP 调用必须传递具体型号，包括接受展示的默认值或只有一个选项时。
- V1 image-job 请求在现有 body 顶层加入 `image_model_id`。
- V2 creative run 在现有 `output.image_model_id` 放模型选择；直接 `POST /api/v2/image/jobs` 的 `CreateImageJobRequest` 没有 `output`，新增顶层 `image_model_id`。revision 的确切位置及继承语义在 M0 映射表冻结，不强行套用 creative-run 结构。
- Lab 创建 session 时显式选择，内部生成的 variant 固定该次选择；用户新提交的 variant override 也必须显式携带型号。session/variant 的具体 JSONPath 与持久化映射在 M0 核实，不假设已有 image-preferences 对象。
- V3 在现有 generation/job 创建参数中接收 `image_model_id`；项目/模板合同不可把用户明确选择覆盖为隐藏默认。
- HTTP/HTTP-backed product MCP 的模型目录读取接口只返回当前调用身份可见且已启用的模型，不返回 key、gateway URL、上游路由或内部管理字段。Native ImageGen 和 frozen/materialized handoff 工具不支持 AISelf 选型：收到该字段须明确拒绝，不能忽略、误标来源或发起额外付费调用。

这些是逻辑字段位置。实施前应对照当前具体 schema/endpoint 固定 JSONPath；不应为了跨版本“完全同构”而重写各版本 API。

### 1.1.1 目录读取 API

增加一个只读的 `GET /api/image-models` projection，由现有 Alchemy authentication/API scope 保护。可选 query 为 `module` (`v1|v2|v3|lab`)、`operation` (`generate|edit`) 和 `requires_reference=true|false`。它仅筛选已经 enabled 的 profile 并返回安全 UI 字段：`model_id`, `display_name`, `labels`, `supported_operations`, `compatible`, `is_default`。`is_default` 是布尔值，只对当前身份/模块/操作有权且兼容的默认项为 true，每次响应最多一项；不能泄露被过滤的默认 ID。默认不可用时所有项为 false，明确没有默认，要求用户选择，不能猜另一个型号或省略字段。不可返回 base URL、secret、内部账户/通道、完整价格配置或未验证的上游目录数据。

该 endpoint 的 `module` 参数只是过滤提示，不是授权依据。服务端必须按现有实际身份和 surface/scope 计算可访问模块，再取与其交集；篡改 `module=v3` 不得使仅有 V1 权限的调用者看到或调用 V3 模型。未授权模块按现有 auth 语义拒绝或返回空可见集合，不透露该模块目录。Web、API Key 和 MCP 均复用现有身份/surface 授权；MCP 通过现有 HTTP 适配调用同一 endpoint，不另实现目录或缓存权威。该 endpoint 的兼容性过滤仅为 UI 提示；所有写请求仍须重新校验 model ID、任务 operation 和输入能力。管理 profile 的写接口仍限现有管理员设置边界，API Key/MCP 用户不能改目录。

### 1.2 解析顺序与旧请求兼容

1. 请求显式带 `image_model_id`：校验 exact ID 并按其执行；不得从 legacy provider 字段重解释或重定向该型号。
2. 请求没有新字段：完全沿用该模块当前解析顺序，不论是否带 legacy `provider_preference` / `provider_hint`。两类字段都省略时仍使用原模块默认，新的 AISelf admin default 不得覆盖它。
3. Lab 新请求没有新字段时，沿用既有 session preference/variant 的 provider→model 规则；已准入 session 派生的内部 variant 则使用该次原始意图和已冻结的有效选择，不通过字段省略重新解析。
4. 新 UI 从授权目录预填 admin default 或唯一选项，再显式提交具体 ID；API/MCP 要采用新默认同样显式提交。不得通过 User-Agent、payload 形状、缺省 provider 或其他隐式规则推断“新客户端”。
5. 新准入仍无法解析时，在付费生成前以安全配置错误拒绝。带显式幂等 key 的既有任务回放先按第 4 节查询，不先套用现行默认/目录。

Browser “last used” preference only prefills the selector; the resulting choice is sent explicitly. If both the new `image_model_id` and a legacy provider field exist, the enabled exact ID is authoritative and the legacy field may not redirect it. During rollout, V1/V2/Lab legacy clients and old jobs must retain their existing provider-specific behavior.

### 1.3 Model ID validation

- Trim whitespace only; preserve exact case and punctuation unless the AISelf contract declares case-insensitive IDs.
- Reject empty, overlong, malformed, disabled, unverified, unknown, or unauthorized IDs before new gateway job admission. Omission selects legacy compatibility; null/blank is not a silent default selector.
- Never accept a client-supplied capability profile, base URL, secret, provider account, channel, price, or `served_model_id` as authority.
- Capability validation is server-side: new admission uses the current profile; immediately before a provider call, check the final materialized payload against the immutable admitted profile and separately check fresh security revocation/route availability. Ordinary catalog disablement or later profile edits do not re-admit an existing Job.

## 2. Capability profile record

The admin-managed catalog record is conceptually:

```json
{
  "model_id": "opaque-exact-id",
  "display_name": "Admin reviewed label",
  "status": "enabled",
  "operations": ["generate", "edit"],
  "reference_images": {"supported": true, "max_count": 4, "modes": ["edit"]},
  "mask_edit": {"supported": false},
  "sizes": ["1024x1024"],
  "aspect_ratios": ["1:1", "3:2"],
  "quality_values": ["medium", "high"],
  "output_formats": ["png", "jpeg"],
  "max_output_count": 1,
  "transparent_background": "unknown",
  "price_profile": null,
  "profile_revision": 1,
  "verified_at": "2026-10-12T00:00:00Z",
  "verification_source": "admin-verified contract test"
}
```

`supported` fields are explicit booleans or enumerations. `unknown` is distinct from `false`; both are ineligible when the task requires that feature. A missing list does not mean an unbounded list. The example ID and values are illustrative only, not a claim that this model exists at AISelf.

Catalog update requirements:

- use the repository's current protected runtime-settings mechanism;
- allow only admin writes; user read projection is redacted;
- increment `profile_revision` for a semantic capability, route, or price change;
- retain a separate non-secret route/config revision for adapter mapping, so a frozen Job never resolves a changed route merely because its model ID is unchanged;
- preserve the old record for existing jobs (job snapshots are authoritative);
- disable a model without deleting historical metadata;
- distinguish ordinary status changes (block new admission only) from explicit security revocations of model/profile/route (block execution, including queued retry; do not erase history);
- reject duplicate exact IDs and unsafe JSON shapes; bound label/ID/list lengths.

Do not add a second persistent model catalogue database unless implementation proves the existing settings store cannot safely hold a bounded allowlist.

### 2.1 V2 配置投影与撤销新鲜度

V2 通过 M0 核实的既有认证配置桥接或受保护部署 mount 读取同一逻辑配置；不得导入 V1 backend/store。投影必须带 schema/config revision、撤销 revision 和可验证的生成/有效期信息，校验来源、完整性、版本兼容与单调性；不能退回未知版本或旧撤销状态。M0 必须给出具体最大陈旧时间、刷新/失效机制及部署验证证据，不能只写“最终一致”。

新准入要求有效且在新鲜度界限内的目录/撤销投影；每次新网关执行（含旧 Job 续跑）必须拥有界限内的安全撤销状态。缺失、失效、版本不兼容或超过界限时阻断执行；只读历史/幂等回放不依赖该投影。旧 Job 的能力来自快照，安全许可来自这次的新鲜撤销检查，二者不能互相替代。不增设配置服务、轮询编排器或独立凭据录入。

## 3. Effective job snapshot

Every newly admitted AISelf generation Job (V1, V2, Lab variant, V3) stores the following additive metadata object. Legacy-provider Jobs retain their existing fields/behavior; the object is optional for historical readers, not a reason to relabel legacy executions:

```json
{
  "image_execution": {
    "gateway": "aiself_image_gateway",
    "requested_model_id": "opaque-exact-id",
    "display_name_snapshot": "Admin-curated name at admission",
    "profile_revision": 1,
    "execution_contract_version": 1,
    "route_ref": "aiself-images-primary",
    "route_config_revision": 1,
    "capability_profile_snapshot": {"operation": "generate", "reference_images": {"supported": false}},
    "operation": "generate",
    "input_capability_fingerprint": "sha256:...",
    "gateway_request_id": null,
    "served_model_id": null,
    "served_model_reported": false,
    "usage": null,
    "upstream_cost": null,
    "status": "requested"
  }
}
```

Rules:

- Snapshot exact request ID, display name, immutable capability profile, execution contract version and non-secret route/config revision before the upstream call; update only result fields after response. `route_ref` is an internal opaque logical identifier, not a URL, account/channel or credential; its immutable mapping must remain available to compatible workers. Keep it out of ordinary public projections. This snapshot remains readable after rename/default/profile changes or ordinary disablement. Security revocation can block execution, never historical display.
- `input_capability_fingerprint` must not contain prompts, image bytes, or credentials; it is optional and only summarizes operation/parameter compatibility.
- Never persist base URL secrets, auth headers, raw request bodies containing image data, or raw base64 provider responses.
- Preserve existing job `provider`/`model` fields for readers. New writes set provider to the Alchemy gateway adapter and model to the resolved exact model ID; if legacy columns require historical provider values, additive metadata stays authoritative for new gateway execution.
- Store gateway request ID and reported model/usage only when returned; never invent them.
- If reported `served_model_id` conflicts with requested ID, mark the execution failed/mismatched and retain the safe response summary for support.
- Old jobs without `image_execution` continue rendering from their old provider/model fields and are not rewritten.

## 4. Retry, edit and idempotency behavior

### Retry and continuation

- Existing legacy provider retries remain unchanged. For new AISelf executions, the existing product retry budget is an upper bound, not evidence that an uncertain paid call is safe to repeat.
- If transport failure occurs after the gateway may have accepted the call, retain the original Job/attempt and safe request ID (when returned), report accepted/outcome unknown using existing product status/metadata, and do not automatically resubmit. Retry only after verified non-acceptance, or with proven upstream deduplication for the same request/key inside its documented scope and TTL. Local idempotency alone cannot prevent a second upstream charge.
- Review/quality rerenders use the same model snapshot and current bounded rules after the preceding attempt is resolved; they cannot disguise an uncertain transport retry. No new queue or billing ledger is introduced.
- Resuming a queued Job uses its immutable model/profile/route configuration, even after ordinary disablement. Fresh explicit security revocation, unavailable frozen configuration or unsupported snapshot version blocks execution with a clear reason; no substitution of newer profile/default is allowed.
- Reading completed history or returning an existing Job for an authorized idempotency replay is read-only. It must not re-admit, restart generation, or require the model to remain enabled/available. Ordinary rename/default changes cannot alter historical display.
- A user-requested model change creates a new revision/job under the product's existing revision semantics.

### Edit/reference operations

Resolve `operation` before creating a paid job. If inputs require `edit`, `reference_images`, or `mask_edit`, the model profile must explicitly support the required capability. Unsupported references are never silently omitted and reference-dependent prompts are never reduced to text-only as a fallback.

准入时验证已知要求；现有参考素材处理完成后、付费调用前，按冻结 profile 再检查最终 materialized reference pack 的张数、单文件/总 bytes、MIME、像素/尺寸、mask 配对和输入模式。上传张数不能代替最终包张数：既有裁切、身份细节图、模板参考等可能展开素材。超限/不支持即停止该调用，不能删图或绕过原参考所有权/审核规则。

### Idempotency

The effective model ID is part of generation identity, but existing explicit-key replay must precede current-default resolution:

1. Authenticate and enforce existing module/scope, owner and session/project access first. Look up the explicit key only within that authorized owner + session/project scope; never disclose another owner's Job or whether its key exists.
2. Compare the canonical original request intent with the stored intent: payload/assets/parameters, supplied exact ID or an explicit legacy-omitted marker, and any legacy selection fields. Preserve omission in this comparison instead of resolving it against today's default. For old records, use sufficient existing persisted intent; if unavailable, fail safely rather than guess or resubmit.
3. Matching original intent returns the original frozen Job/result, even after default/profile changes, ordinary disablement or revocation. This is a read, not permission to resume execution. Explicitly changing the model or other relevant intent under that same key is a conflict before returning stale output or making provider calls; do not derive a replacement key.
4. Only when no authorized existing record exists may the request resolve current settings under section 1.2, validate new admission and atomically bind the key, original intent and snapshot in existing Job persistence. Concurrent duplicates must converge through the existing ownership/idempotency transaction boundary, not create extra Jobs or paid calls.

System-derived fingerprints include the exact effective model ID, so distinct model choices have distinct derived identities. This does not create upstream request deduplication or authorize retry after an uncertain AISelf acceptance.

### Initial gateway response contract

The initial new AISelf adapter accepts only synchronous inline base64 image data in the exact response fields frozen with AISelf at M0/G0. Before enablement, verify AISelf supports this mode. Apply response-byte, decoded-byte, MIME/signature, pixel/dimension and output-count bounds before accepting artifacts. Reject malformed/oversized base64, URL-only or mixed URL responses, redirects and accepted/async responses as unsupported; do not fetch a response URL, poll, cancel remotely or repeat a possibly paid request. Preserve the existing Job and safe diagnostic/outcome-unknown evidence as appropriate, without inventing success, refunds or non-acceptance.

Future URL download or async/polling support stays disabled until a separately reviewed frozen contract defines allowlisted origins, HTTPS and approved network egress on every hop (including DNS rebinding defenses), scheme/host/effective-port checks, redirect policy, credential audience/path scope and no cross-origin forwarding, polling TTL/terminal states, cancellation/cost behavior and accepted-but-unknown reconciliation. Initial inline-only support does not prove those routes safe or available.

## 5. Response projection

Existing API response envelopes remain stable. Add safe optional fields:

```json
{
  "image_execution": {
    "gateway": "aiself_image_gateway",
    "requested_model_id": "opaque-exact-id",
    "served_model_id": null,
    "served_model_reported": false,
    "gateway_request_id": "if-returned",
    "status": "completed"
  }
}
```

The user-facing history shows the selected exact ID and display name snapshot. It does not expose account/channel, routing rules, API keys, or internal endpoint configuration. Old response consumers ignore the additive object.

## 6. Cost and usage contract

- Keep Alchemy user billing and AISelf upstream cost separate.
- Estimates are shown only when a profile includes a valid rate source, currency, unit and computation version; otherwise return/display `estimate_status=unavailable`.
- Capture gateway-reported usage/cost when available and preserve raw monetary precision as decimal strings/decimal types; do not use binary float for settlement.
- Existing Alchemy debit/refund/credit transaction boundaries remain unchanged. A model choice cannot bypass the current account budget or V2 service billing.
- Provider failure, moderation rejection, and partial output billing follow the existing product's rules; this feature does not invent refunds or charge policy.

## 7. Compatibility matrix

| Input/history case | Required result |
|---|---|
| Any request with no `image_model_id`, including no provider field | Use the existing module default/provider mapping; never infer a new client |
| New UI accepts displayed default or sole model | Send that concrete `image_model_id` explicitly |
| New request with enabled exact ID | Use that exact ID and persist the snapshot |
| New admission with unknown/disabled/unverified ID | 4xx validation/config error; no provider call/job charge |
| Unsupported operation/reference capability | 4xx compatibility error before paid call; preserve inputs |
| Existing queued/running job from before rollout | Continue using its existing provider/model fields |
| Existing completed history | Read-only; no migration required |
| Same authorized explicit key/original intent after default/profile change or disable/revocation | Return the frozen existing Job read-only before current configuration resolution |
| Reused idempotency key with different ID | Conflict; no stale result replay |
| Key replay by another owner or inaccessible session/project | Existing auth denial; no Job/output/existence disclosure |
| Retry after ordinary disable/profile change | Continue frozen snapshot with fresh revocation check; never resolve current default |
| Explicit security revocation, stale revocation state or unavailable frozen route | Block execution with reason; authorized history/replay stays readable |
| Unsupported Native ImageGen/handoff tool receives AISelf ID | Explicit rejection; no ignore, false AISelf provenance or paid gateway work |

The compatibility window ends only after clients are migrated and telemetry proves no unqualified legacy callers remain. Removing legacy provider settings is a separate reviewed change, not part of initial enablement.
