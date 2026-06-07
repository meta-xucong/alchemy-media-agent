# AlchemyOS Agent Development Principles

## V2 Template Lock Principle

When developing Custom Media Agent 2.0, preserve this rule:

```text
Selected case first. Uploaded assets fit into the selected case.
```

For V2 image generation:

1. If `template_case_id` is set, the selected case is the highest-priority visual anchor.
2. Claude Code is the central creative orchestrator, but it must not override the selected case's priority.
3. Uploaded images are evidence and template-slot variables. They may replace subject identity, product appearance, logo, face, copy content, or minor props.
4. Uploaded images must not override the selected case's composition, layout, lighting, background density, spatial hierarchy, mood, or overall visual rhythm unless the user explicitly unlocks the template.
5. If no case is selected, Claude Code may freely combine uploaded images with retrieved cases.
6. Hard visual constraints such as product appearance, logo, face, or required background must be passed to capable image providers as input images, not reduced to text-only prompts.
7. Final prompts must not leak internal `case_id`, `asset_id`, `provider_id`, `source_url`, API, repository, or storage identifiers.

Short form:

```text
Selected template controls the frame.
Uploaded assets fill the frame.
Claude decides how to fit them together without breaking the frame.
```

## V2 Uploaded Asset Intent Principle

When Custom Media Agent 2.0 receives uploaded images, every uploaded asset must be interpreted as a concrete fusion intent before prompt composition.

Hard rules:

1. `role` alone is not enough. V2 must derive `fusion_mode`, `placement_intent`, `target_surface`, provider input requirements, and review expectations from the user prompt, asset notes, and asset brief.
2. Hard identity assets such as subject, product, logo, face, and required background must stay as V2-native provider `input_images` whenever the provider supports them.
3. A selected template remains the highest-priority frame. Uploaded assets may fill replaceable slots, but must not override locked template structure.
4. Logo usage must distinguish product or scene surface placement from poster brand mark placement. A logo requested on clothing, packaging, a bottle, a device, a sign, or another scene object must not be treated as a generic corner badge.
5. Claude Code may improve the creative prompt, but it must obey the structured fusion policy and must not erase uploaded-asset intent.

Short form:

```text
Role identifies the material.
Fusion policy identifies what to do with it.
Claude improves the result without changing that intent.
```

## V2 Strict Isolation Principle

When developing Custom Media Agent 2.0, treat V1 and V2 as separate backend products that only share the browser shell and visual style.

Hard rules:

1. V2 backend code must not call `/api/v1/*` or `/v1/*`.
2. V2 backend code must not import modules from `custom_media_agent_docs/src_skeleton/app`.
3. V2 must not read or write V1 `.media_storage`, V1 history, V1 generated images, V1 assets, V1 queues, or V1 runtime provider settings.
4. V2 image generation must use V2-native providers, V2-native storage, V2-native history, and V2-native review.
5. `legacy_image_bridge` is an architecture debt, not an acceptable default or fallback path.
6. Hard visual constraints such as product appearance, logo, face, or required background must remain V2-native `input_images` or V2-native deterministic postprocess steps. They must not be translated into V1 asset roles.

Short form:

```text
V2 may learn from V1, but V2 must not depend on V1.
```

## V2 Claude Continuation Principle

When developing Custom Media Agent 2.0, Claude Code remains the central creative brain even when the upstream route is slow, near an output cap, or close to a context/response limit.

Hard rules:

1. `claude_timeout`, output-token-limit, structured-output exhaustion, or upstream context cancellation must not silently bypass Claude and continue with a deterministic-only creative decision.
2. V2 must use a soft stage boundary before the hard timeout/context/output boundary. When a normal stage approaches that soft boundary without valid compact JSON, the controller must compress state and continue through a shorter Claude micro or ultra-micro stage.
3. If any Claude checkpoint has completed, V2 must preserve that checkpoint, compress the visible state, and continue with a shorter Claude stage or a checkpoint-derived compressed decision.
4. Timeout guards are allowed only as internal boundary triggers for compression and continuation. They are not an acceptable final creative fallback once Claude has started reasoning.
5. Claude may think fully inside each bounded stage, but visible output must always be compact, schema-shaped, and capped by configured prompt/negative/rationale budgets.
6. If Claude is required and no recoverable Claude checkpoint or Claude decision can be produced, V2 must stop the run as failed rather than generate from a deterministic-only creative fallback.
7. Final prompts must come from Claude output or from compressed Claude checkpoints. Local deterministic logic may provide safety scaffolding, provider parameters, and hard guards, but must not replace Claude's creative role.

Short form:

```text
Claude thinks fully.
The system compresses visible state.
If a boundary is hit, continue from the compressed checkpoint instead of bypassing Claude.
```
