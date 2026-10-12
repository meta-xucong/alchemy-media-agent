# Alchemy 图片模型选择：请求、配置与历史契约

状态：提案。本文定义跨产品语义；各版本可保留各自现有请求结构。

规范词汇：`image_model_id` 为 Alchemy 选择的精确图片模型 ID；它是 opaque string，不做别名推断。

## 1. 公共语义

### 1.1 请求字段

- 字段可选，以兼容旧客户端；新 UI、API 和 MCP 调用对用户显式选择时必须传递该字段。
- V1 image-job 请求在现有 body 顶层加入 `image_model_id`。
- V2 保持版本原有 `output` 对象合同，在 `output.image_model_id` 放模型选择；revision 可用同名显式覆盖字段。
- Lab 在创建 session 的 image preferences 中保存 `image_model_id`，单个 variant 提交可显式覆盖。
- V3 在现有 generation/job 创建参数中接收 `image_model_id`；项目/模板合同不可把用户明确选择覆盖为隐藏默认。
- HTTP/MCP 的模型目录读取接口只返回当前调用身份可见且已启用的模型，不返回 key、gateway URL、上游路由或内部管理字段。

这些是逻辑字段位置。实施前应对照当前具体 schema/endpoint 固定 JSONPath；不应为了跨版本“完全同构”而重写各版本 API。

### 1.1.1 目录读取 API

增加一个只读的 `GET /api/image-models` projection，由现有 Alchemy authentication/API scope 保护。可选 query 为 `module` (`v1|v2|v3|lab`)、`operation` (`generate|edit`) 和 `requires_reference=true|false`。它仅筛选已经 enabled 的 profile 并返回安全 UI 字段：`model_id`, `display_name`, `labels`, `supported_operations`, `compatible`。不可返回 base URL、secret、内部账户/通道、完整价格配置或未验证的上游目录数据。

该 endpoint 的 `module` 参数只是过滤提示，不是授权依据。服务端必须按现有实际身份和 surface/scope 计算可访问模块，再取与其交集；篡改 `module=v3` 不得使仅有 V1 权限的调用者看到或调用 V3 模型。未授权模块按现有 auth 语义拒绝或返回空可见集合，不透露该模块目录。Web、API Key 和 MCP 均复用现有身份/surface 授权；MCP 通过现有 HTTP 适配调用同一 endpoint，不另实现目录或缓存权威。该 endpoint 的兼容性过滤仅为 UI 提示；所有写请求仍须重新校验 model ID、任务 operation 和输入能力。管理 profile 的写接口仍限现有管理员设置边界，API Key/MCP 用户不能改目录。

### 1.2 解析顺序与旧请求兼容

1. 请求显式带 `image_model_id`：校验 exact ID 并按其执行；不得从 legacy provider 字段重解释或重定向该型号。
2. 请求没有新字段但携带 legacy `provider_preference` / `provider_hint`：兼容期内完全沿用该模块当前 provider→model 解析顺序。新的 admin default 不得覆盖旧请求原本会选择的模块模型。
3. Lab 请求没有新字段时，沿用既有 session preference/variant 的 provider→model 解析规则。
4. 新客户端无显式选择，也无 legacy provider/session 选择时，使用服务器 admin default。
5. 仍无法解析时，在付费生成前以安全配置错误拒绝。

Browser “last used” preference only prefills the selector; the resulting choice is sent explicitly. If both the new `image_model_id` and a legacy provider field exist, the enabled exact ID is authoritative and the legacy field may not redirect it. During rollout, V1/V2/Lab legacy clients and old jobs must retain their existing provider-specific behavior.

### 1.3 Model ID validation

- Trim whitespace only; preserve exact case and punctuation unless the AISelf contract declares case-insensitive IDs.
- Reject empty, overlong, malformed, disabled, unverified, unknown, or unauthorized IDs before job admission.
- Never accept a client-supplied capability profile, base URL, secret, provider account, channel, price, or `served_model_id` as authority.
- Capability filtering is server-side and repeats immediately before the provider call.

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
- preserve the old record for existing jobs (job snapshots are authoritative);
- disable a model without deleting historical metadata;
- reject duplicate exact IDs and unsafe JSON shapes; bound label/ID/list lengths.

Do not add a second persistent model catalogue database unless implementation proves the existing settings store cannot safely hold a bounded allowlist.

## 3. Effective job snapshot

Every created generation Job (V1, V2, Lab variant, V3) stores an additive, optional metadata object:

```json
{
  "image_execution": {
    "gateway": "aiself_image_gateway",
    "requested_model_id": "opaque-exact-id",
    "display_name_snapshot": "Admin-curated name at admission",
    "profile_revision": 1,
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

- Snapshot exact request ID, display name and the immutable capability profile revision (or a bounded copy of the selected safe profile fields) before the upstream call; update only result fields after response. This snapshot must remain readable after rename, default changes or ordinary disablement. A security revocation may block retry execution, but must not erase or rewrite historical display data.
- `input_capability_fingerprint` must not contain prompts, image bytes, or credentials; it is optional and only summarizes operation/parameter compatibility.
- Never persist base URL secrets, auth headers, raw request bodies containing image data, or raw base64 provider responses.
- Preserve existing job `provider`/`model` fields for readers. New writes set provider to the Alchemy gateway adapter and model to the resolved exact model ID; if legacy columns require historical provider values, additive metadata stays authoritative for new gateway execution.
- Store gateway request ID and reported model/usage only when returned; never invent them.
- If reported `served_model_id` conflicts with requested ID, mark the execution failed/mismatched and retain the safe response summary for support.
- Old jobs without `image_execution` continue rendering from their old provider/model fields and are not rewritten.

## 4. Retry, edit and idempotency behavior

### Retry and continuation

- Transport retries of the same Job repeat the same model ID and compatible payload according to the current product retry limits.
- Review/quality rerenders use the same model snapshot and follow current bounded retry rules.
- Resuming or replaying a queued Job uses its immutable model/profile snapshot even if the admin default/catalog changed.
- If a frozen profile revision is unavailable or explicitly security-revoked, stop with an explicit blocked reason; do not substitute a newer profile/default behind the user's back. Ordinary rename/default changes cannot alter the old Job's display snapshot.
- A user-requested model change creates a new revision/job under the product's existing revision semantics.

### Edit/reference operations

Resolve `operation` before creating a paid job. If inputs require `edit`, `reference_images`, or `mask_edit`, the model profile must explicitly support the required capability. Unsupported references are never silently omitted and reference-dependent prompts are never reduced to text-only as a fallback.

### Idempotency

The effective model ID is part of generation identity. Repeating the same explicit idempotency key with the same owner, session, payload and model returns the existing Job. Reusing that explicit key with a different model must return a conflict before returning any prior Job/output or starting provider work. A system-derived idempotency fingerprint must include the exact model ID, so distinct model choices have distinct derived identities. Do not silently derive an alternate key from a conflicting explicit key.

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
| Old request with no `image_model_id` | Use the existing module default/provider mapping during the compatibility window |
| New request with enabled exact ID | Use that exact ID and persist the snapshot |
| Unknown/disabled/unverified ID | 4xx validation/config error; no provider call/job charge |
| Unsupported operation/reference capability | 4xx compatibility error before paid call; preserve inputs |
| Existing queued/running job from before rollout | Continue using its existing provider/model fields |
| Existing completed history | Read-only; no migration required |
| Reused idempotency key with different ID | Conflict; no stale result replay |
| Retry after catalog revision change | Continue old snapshot or stop; never resolve current default |

The compatibility window ends only after clients are migrated and telemetry proves no unqualified legacy callers remain. Removing legacy provider settings is a separate reviewed change, not part of initial enablement.
