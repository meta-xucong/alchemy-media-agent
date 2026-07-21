# Doc133: V3 Codex Native ImageGen Frozen Specialized-Plan Relay

> **Doc135 refinement:** a specialized relay transports only the exact
> remote-Brain canonical prompt and admitted references. Structural roles are
> opaque lineage, never local camera/scene/phrase instructions.

> **Doc183 boundary:** Specialized relays remain conversation-only unless a
> trusted Character Card stage explicitly creates the new local handoff. The
> handoff still consumes the frozen plan and shared V3 finalization; it never
> becomes a General/E-Commerce/Photography fallback.

Status: active, explicit, conversation-only developer-preview extension of
Docs130/131. It supersedes only their former Local MCP availability restriction
for `ecommerce_template` and `photographer_template`; it does **not** relax
Doc127 production gates, Doc132 browser/lifecycle closure, or any shared
Provider/review/retry/final-delivery rule.

## 1. Purpose and decision boundary

When the Web image Provider is unavailable, Alchemy code closure may still
verify a frozen specialist plan visually without changing the Web path:

```text
normal specialist request
-> existing ScenarioRuntime + template policy
-> required remote Central Brain (no fallback)
-> frozen envelope + normalized intent + constraint ledger + deliverable plan
-> same canonical Web Provider materializer
-> exact prompt/reference inputs returned by Local MCP
-> one Codex built-in ImageGen call per returned output
-> conversation-only, non-certified image
```

The Local relay does not re-plan an image, alter a Brain direction, interpret
a reference, or create an alternate rendering route. For the same frozen plan,
the returned UTF-8 `imagegen_prompt`, SHA-256 receipt, rendering contract, and
admitted reference paths are the exact values the Web Provider materializes.

This validates Alchemy-owned planning and prompt/reference construction. It
does not validate gateway routing, account health, upstream request acceptance,
pixel review, retry, storage, project delivery, Gate C/D, Gate D, or P10.

## 2. Explicit MCP surface

The existing `prepare_native_imagegen_plan` remains unchanged and
General-only. It continues to reject specialist template IDs with its existing
safe block code; it must never silently reinterpret them as General.

The new separate tool is:

```text
prepare_frozen_specialized_native_imagegen_plan
```

It accepts only:

```json
{
  "user_input": "explicit user request",
  "template_id": "ecommerce_template | photographer_template",
  "requested_image_count": 1,
  "requested_image_size": "1024x1536 | null",
  "reference_inputs": [{"channel": "product_truth", "file_path": "C:/authorized/source.png"}],
  "platform_profile": "generic | platform evidence identifier | null",
  "photography_mode": "single_hero | reference_reshoot | professional_set | null",
  "photographer_profile_id": "general_photography | null"
}
```

All fields are required structurally so irrelevant fields are explicitly
`null`; the template determines which values are accepted. The tool rejects
unknown fields, credentials, provider metadata, job IDs, raw envelopes, raw
plans, artifact handles, and caller-authored role/recipe/camera/crop fields.

## 3. E-Commerce contract

`ecommerce_template` requires a non-empty `platform_profile`, receives the
ordinary E-Commerce ScenarioRuntime request, and requires a valid remote Brain
result with `llm_used=true`, `fallback_used=false`, and exactly the requested
number of whole-image directions.

The relay projects precisely N canonical prompts and N reference-input
contracts. It never returns a static suite, seller-copy default, recipe,
semantic slot, camera/crop/scene instruction, or local retry policy. Existing
`ecommerce_output_N` values are opaque runtime lineage only: the relay does
not read, name, interpret, or expose them as a user-visible role. It passes
the canonical materializer output byte-for-byte rather than removing or
rewriting any internal compatibility token.

An invalid Brain, count mismatch, disabled template, missing envelope/ledger,
or materialization/reference-admission fault blocks before Codex receives a
prompt.

## 4. Photography contract

`photographer_template` requires one existing structural mode:

| Mode | Exact count | Local projection |
| --- | ---: | --- |
| `single_hero` | 1 | one `hero_photograph` lineage key |
| `reference_reshoot` | 1 | one existing reshoot lineage key |
| `professional_set` | 3 | `session_hero`, `environmental_context`, `detail_or_moment` |

The role key is a frozen lineage binding only. It contains no local pose,
camera, crop, lighting, scene, or creative recipe; each actual visual
direction remains Brain-authored and is already in the canonical provider
prompt.

The relay resolves only the existing shared `general_photography` default via
the mainline photographer-profile catalog and freezes that returned binding
into the normal runtime request. A named profile fails closed because Local MCP
has no Project/API immutable-confirmation transaction. It must not mint a
named binding, imitate a browser confirmation, or silently substitute General
Photography for a requested named profile.

Photography remains unavailable when its existing template gate is disabled.
Local MCP does not change `V3_PHOTOGRAPHY_PRODUCTION_ENABLED` or any other
production flag.

## 5. Reference and rendering parity

Doc131 remains authoritative. Each user-authorized local source file enters
the normal V3 `UploadedAssetInfo` contract unchanged. The remote Brain receives
only safe compact evidence, never a local path. The canonical materializer is
the sole authority for admission, deduplication, operation type, and final
reference order.

For each returned output, Codex must make exactly one built-in ImageGen call
with the returned `imagegen_prompt` and `reference_image_paths` verbatim. It
may not append, remove, translate, summarize, re-order, crop, or replace
anything. If the built-in tool is unavailable, stop; do not use Web, Aiself,
Platform API, CLI authentication, a local renderer, or a second creative
fallback.

## 6. Hard isolation and provenance

The relay creates no Web request, credential read, Provider client, artifact,
candidate, review, retry, delivery, continuation, project/job record, or
production setting change. Its only outputs are planning data labelled:

```text
execution_channel=codex_native_imagegen
renderer=codex_builtin_imagegen
delivery_state=conversation_only_not_certified
```

General does not receive E-Commerce or Photography context. E-Commerce never
receives a photography profile binding. Photography never receives E-Commerce
creative context. If any cross-template field appears, or if the frozen
specialist contract is incomplete, the tool blocks before returning a prompt.

## 7. Acceptance and limitations

The focused acceptance suite proves:

- General public-tool compatibility and explicit specialist-tool separation;
- E-Commerce N=1/2/4/7 required-Brain count, canonical prompt/reference
  parity, opaque output bindings, and no upstream Provider selection;
- Photography required-Brain plan, General Photography binding, canonical
  prompt/reference parity, and the exact existing professional-set lineage;
- disabled template, unavailable/fallback Brain, invalid count, missing
  reference, and named-profile-without-Project-binding fail closed; and
- no Web Provider, review, retry, candidate, delivery, artifact, or project
  state is created.

A successful conversation image is valid provider-independent evidence for
the relevant Alchemy plan/materializer code. It is never a production release
claim. Doc127 remains the only real Web Provider/review release authority.
