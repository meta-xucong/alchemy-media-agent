# Doc225 — Character Card Planning Metadata Projection Closure

## Status

Implemented as a root-cause closure for the Character Card `expression.laugh`
MCP handoff precheck failure observed after Doc224.

## Intended behavior

Professional Character Card stage generation has one server-owned metadata
authority:

```text
Product API / Host stage request
  -> ScenarioRuntime runtime metadata
  -> CentralCreativeBrain generation_plans[n].metadata
  -> build_provider_generation_request
  -> Provider/MCP materialized reference plan
  -> durable MCP handoff
```

For `expression_set` slots, the Provider/MCP materializer must receive the
stage/slot identity before deriving references. The canonical `face.front`
winner is a card-framing authority first, followed by identity detail and head
geometry crops:

1. `character_card_full_frame_framing_reference` with `card_framing`
2. `portrait_identity_crop`
3. `portrait_identity_pose_geometry_crop`

This is a metadata projection contract. It is not a prompt-tuning mechanism and
does not relax affect, framing, identity, shared Vision, retry, or slot gates.

## Observed mismatch

Fresh validation created `mcp_handoff_16ca86f2aa` with crop-first references.
The Product API request top-level metadata still contained the Character Card
stage fields, but `planning_result.generation_plans[0].metadata` omitted:

- `professional_character_card_preparation`
- `professional_character_card_stage`
- `professional_character_card_slot`
- `professional_character_card_source_class`
- `professional_character_card_attempt_round`
- `professional_character_card_reference_output_ids`

Doc224's Provider factory fix was therefore bypassed in the real path: the
Provider saw an ordinary identity reference job and materialized crop-first.

## Root cause

`CentralCreativeBrain` had an explicit per-output metadata projection list that
preserved Professional Anchor Pack fields but not Professional Character Card
fields. ScenarioRuntime's top-level runtime metadata was correct; the loss
occurred when the central plan created each `GenerationPlan`.

A secondary admission mismatch was found while writing the boundary test:
selected generated outputs may carry `output_id` inside the asset metadata
projection. Provider admission accepted only a top-level `output_id`, so a
canonical selected winner projected through `reference_assets` could be
misclassified as non-canonical while the duplicate uploaded projection was
retained. Provider admission now treats `metadata.output_id` as equivalent
canonical output identity; it still requires a real path, canonical binding or
source integrity, and a materialized file.

## Authoritative rule

Character Card stage metadata must be carried losslessly as immutable transport
metadata. The current authoritative fields are:

- `professional_character_card_preparation`
- `professional_character_card_stage`
- `professional_character_card_slot`
- `professional_character_card_source_class`
- `professional_character_card_attempt_round`
- `professional_character_card_reference_output_ids`
- `professional_identity_reference_strategy`
- `professional_reference_stage`
- `professional_anchor_reference_assets`
- `professional_planning_metadata`
- `generation_channel`
- `mcp_operation_id`
- `mcp_materialization`

General, E-Commerce, Photography, and Standard Mode must not synthesize these
fields. They are copied only when the stage request already supplied them.

## Acceptance coverage

The regression must cover the real boundary, not a helper-only shortcut:

1. ScenarioRuntime receives a Product API-like Character Card stage request.
2. `planning_result.generation_plans[0].metadata` preserves the stage fields.
3. `build_provider_generation_request` projects the same fields to Provider
   metadata.
4. `McpMaterializationProvider._build_app_request` materializes the MCP handoff
   with full-frame-first `card_framing` evidence and Doc222 fingerprints.

Old crop-first handoffs remain append-only stale evidence and must not be
submitted, consumed, materialized, or written as winners.
