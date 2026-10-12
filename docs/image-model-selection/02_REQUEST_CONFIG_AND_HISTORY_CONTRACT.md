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

### 1.2 解析优先级

```text
explicit request image_model_id
  > Lab session image_model_id (Lab only)
  > server admin default model ID
  > legacy provider/default mapping (old requests only)
```

Browser “last used” preference is only a UI default and must be serialized into explicit request input. If no model resolves, reject before paid work with a safe configuration error. If both the new model ID and a legacy provider field are present but contradict, the explicit model ID is authoritative only if it is enabled and the legacy value is an allowed compatibility alias; otherwise return a validation conflict. Do not reinterpret the new model ID based on `provider_preference`.

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
    "profile_revision": 1,
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

- Snapshot request ID and capability revision before the upstream call; update only result fields after response.
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
- Resuming or replaying a queued Job uses its snapshot even if the admin default/catalog changed.
- If a frozen model is now disabled or unavailable, stop with an explicit blocked reason; do not switch model behind the user's back.
- A user-requested model change creates a new revision/job under the product's existing revision semantics.

### Edit/reference operations

Resolve `operation` before creating a paid job. If inputs require `edit`, `reference_images`, or `mask_edit`, the model profile must explicitly support the required capability. Unsupported references are never silently omitted and reference-dependent prompts are never reduced to text-only as a fallback.

### Idempotency

The effective model ID is part of generation identity. Repeating the same idempotency key with the same owner, session, payload and model returns the existing Job; reusing it with a different model must return a conflict (or use a distinct derived key under the existing idempotency contract). Do not return another model's prior output as if the requested one had run.

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
