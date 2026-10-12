# Alchemy 图片模型选择与 AISelf 网关架构

状态：提案；只定义 Alchemy 行为。AISelf 网关实现、模型列表和上游价格由单独项目负责。

目标：四个产品入口可用一把 Alchemy 服务端持有的 AISelf 凭据，按任务精确选择经审核的图片模型。

## 1. 问题陈述

Alchemy 现有界面和服务将 Provider、模型配置与一次具体生成分散在不同层：V1 请求传 `provider_preference` 并由运行时配置解析 model；V2 请求有 `provider_hint`，但具体 model 来自 V2 自己的设置；Lab 使用 provider preference；V3 renderer 固定为 GPT Image 2。管理员设置模型名不等于普通用户能在一次任务中选择型号，且同一个模型目录不能保证四个产品实际发出的 model 字段一致。

用户需要的是“这一张/这一组图片用哪个模型”。Alchemy 应显示可读名称和准确 model ID，保存选择到该任务，并由原有业务模块继续处理提示词、输入图片、审核、重试和交付。

## 2. 目标拓扑

```text
Alchemy Web / Mobile / HTTP API / MCP
      │  image_model_id + existing product payload
      ▼
Product boundary (V1 | V2-native | V3 | Lab)
      │  resolve model, validate operation/assets, freeze job snapshot
      ▼
Alchemy Image Model Catalog + capability policy
      │  enabled exact model ID -> compatible request profile
      ▼
aiself_image_gateway adapter (product-specific implementation where required)
      │  one server-held base URL + one server-held gateway key
      ▼
AISelf OpenAI-compatible image gateway
      │  gateway chooses its upstream/channel; Alchemy does not
      ▼
Existing job, review, history, billing and delivery path
```

The catalog is an Alchemy allowlist and capability contract, not a new routing service. Do not add another queue, billing ledger, job table, provider-secret store, or fallback orchestrator. Reuse current admin runtime-settings persistence, current job records, existing product adapters, and each product's own billing/ownership path.

## 3. Product behavior

### 3.1 End users

- Each image-generation entry point has a model selector when at least two compatible models are enabled. If only one is eligible, show the selected model as a fixed value with its name; do not show a misleading disabled selector.
- Each option has an admin-curated display name, exact model ID, concise quality/speed/cost labels only when backed by declared metadata, and an operation-compatibility hint. Never infer that a model called “2.5” is Flare, Sunburst, GPT Image, or Grok.
- The UI filters choices using the current task's requirements (generate/edit/reference/mask/transparent output/size/count). A model that cannot satisfy required inputs is unavailable with a clear reason.
- A user selection is per invocation. A browser may remember the last choice as a convenience, but the request must carry it; server behavior must not depend on hidden local storage.
- Show the resolved model in the running and completed job details. Do not imply a model different from the requested one was used.
- Existing V3 user controls for image count/quality, product templates, photography roles, identity/reference policies, and review remain separate from renderer choice.

### 3.2 Administrators

The existing server-side runtime configuration UI is extended, not a separate credential center. The gateway origin is supplied only by protected deployment configuration; the admin UI can configure:

1. The single logical secret through existing protected secret handling. Do not echo it in read responses, logs, templates, or client payloads. V1/Lab and the isolated V2 process may each receive a protected runtime projection of that same source, but must not require separately entered per-product copies or drift independently.
2. The default model for new tasks.
3. Enabled exact model IDs and per-model curated capability profiles. An upstream model discovered but not yet classified remains disabled.
4. Display metadata and, only when source data is reliable, price/estimate metadata.

The deployment origin must be HTTPS, match a fixed deployment allowlist and resolve only to approved gateway egress. Reject loopback, private, link-local, unspecified, multicast, reserved, and IP-literal destinations; enforce this at the network egress boundary as well as URL validation to resist DNS rebinding. Disable redirects (or reject every cross-origin redirect before forwarding credentials). Never allow a request payload or ordinary admin setting to change the origin.

Admin changes affect newly resolved jobs only. A running/queued job keeps its snapshot. Keep a prior known-good default available for configuration rollback, without automatically retrying a failed request on it.

### 3.3 Product-specific boundaries

| Product | Existing behavior | Planned model resolution | Must remain owned by |
|---|---|---|---|
| V1 | Provider preference; configured model resolved by provider | Request `image_model_id`; legacy provider-only request maps using current default/provider configuration | V1 generation, assets, user/account/billing and history |
| V2 | `provider_hint`; model settings in V2 | `output.image_model_id` (and revision request field) resolved by V2-native catalog adapter | V2 runtime, templates, cases, billing, assets, review |
| Alchemy Lab | Session `provider_preference` passed into generation | Session preference plus optional per-variant override; effective model frozen per variant/job | Lab session lifecycle, favorites, serialized jobs and quality logic |
| V3 | Production renderer hardcoded to `gpt-image-2` | Explicit/default `image_model_id` on new generation; V3 job snapshot carries exact model and profile revision | V3 Brain, templates, reference truth, vision review, winner/delivery, project history |

V2 stays backend-isolated: no imports from `src_skeleton` V1 modules, V1 Provider or V1 storage. Sharing a JSON contract and a read-only versioned model catalog/config projection is allowed; sharing a backend implementation or V1-owned persistence is not. The configuration source remains one logical admin-managed source; implementation must use the existing authenticated V2 configuration bridge or a protected deployment secret/config mount, whichever is already supported and safest. Do not create a second independent UI/key entry to satisfy the process boundary.

## 4. Catalog and capability profile

The catalog must distinguish “model exists” from “Alchemy can safely use it for this task.” A profile has at least:

| Field | Meaning |
|---|---|
| `model_id` | Exact opaque gateway request ID; primary key for routing |
| `display_name` | Admin-curated user-facing label |
| `status` | `enabled`, `disabled`, `unverified`, or `deprecated` |
| `operations` | Verified subset of `generate`, `edit` |
| `reference_images` | Whether image references are accepted; include max count and input modes if known |
| `mask_edit` | Whether mask-based edit is verified |
| `sizes`, `aspect_ratios`, `quality_values`, `output_formats` | Allowed, verified parameter values; an empty/unknown set is not “all supported” |
| `max_output_count` | Verified output count limit |
| `transparent_background` | Verified boolean or unknown |
| `limits` | Request/input/pixel/file constraints that affect safe submission |
| `price_profile` | Optional source, currency, unit, version and estimate formula; unknown is explicit |
| `verified_at`, `verification_source`, `profile_revision` | Audit and invalidation metadata |

Capabilities are explicit facts, never model-name heuristics. Any required task capability marked unknown is treated as unsupported for that task. A text-only generation model may still be used for a text-only request if its generate operation was verified.

Initially, Alchemy may use a manually curated configuration-backed catalog. If AISelf later exposes a model/catalog endpoint, it can inform discovery but does not automatically enable entries; capabilities and pricing still need verified mapping. This avoids coupling Alchemy to an unfinished AISelf catalog contract.

## 5. Routing and failure rules

1. Resolve a concrete exact ID before creating or admitting a paid generation job.
2. Check that it is enabled, configured, and capable of the required operation and inputs.
3. Freeze the resolved ID/profile revision into the job. Never look up the current default again in a running job.
4. Send the exact `model_id` through the gateway adapter. Preserve the original route response safely.
5. If upstream reports a served model and it conflicts with the requested exact model, mark provider execution as mismatch/failure; do not call it successful on the requested model.
6. If upstream omits served model, record requested ID and mark served-model identity unreported; do not fabricate proof.
7. Transport retry may repeat the same exact model according to the existing product retry contract. Quality rerender uses the same frozen model. Changing models requires an explicit user choice/new revision.
8. Unsupported capability, disabled model, missing key, bad route, or unknown ID fails before silently stripping references or parameters.

There is no automatic fallback to GPT Image 2, Grok, or another model. Fallback would change quality, privacy, cost and task identity and therefore requires an explicit product decision.

## 6. Model identity versus billing identity

The Alchemy user-facing model ID answers “what did Alchemy request from AISelf?” It does not identify AISelf's internal upstream account/channel. Store the gateway request ID and reported usage/cost metadata when available. Keep upstream account/channel and credentials hidden from ordinary users.

Alchemy's own existing customer-charge logic remains authoritative. Gateway cost/usage is a separate reconciliation fact; do not replace customer credits/prices with upstream cost, double charge, or infer a price when no reliable rate card exists. If Alchemy cannot estimate cost before a job, display that clearly and apply current product budget/confirmation rules.

## 7. V3 governance update required at implementation

Doc100 currently says GPT Image 2 is the sole final-pixel renderer and missing GPT Image 2 config is a hard error. That remains current until code and governance are deliberately changed. The implementation phase must replace only the renderer-selection clause with: “Alchemy V3 may use an explicitly selected, enabled AISelf catalog model whose capability profile satisfies the task; the model ID is frozen per job; there is no silent model fallback.”

Preserve all unrelated Doc100 invariants: only the remote image API writes final pixels; no local/sidecar pixel renderer; V3 Visual Capability/Brain owns planning and review; reference truth and prompt channels stay unchanged; review and best-result closure remain authoritative; retry stays bounded and uses the selected model. Add isolation tests proving model choice does not leak scenario-specific output logic into General Template or shared capability code.

## 8. Open integration facts (must be frozen before implementation)

These are not reasons to redesign Alchemy now; they are implementation gates to confirm against the separate AISelf work:

- supported base URL and key header;
- exact generation/edit routes and multipart/reference request format;
- whether model IDs are accepted unchanged and what served-model field means;
- synchronous response versus accepted/polling job semantics;
- returned output formats and usage/cost/request IDs;
- stable limits/rate behavior and the way gateway errors are surfaced.

The code plan supports a narrow OpenAI-compatible adapter first. If AISelf's final contract differs, update the adapter mapping and contract tests only; do not duplicate per-upstream routing in Alchemy.
