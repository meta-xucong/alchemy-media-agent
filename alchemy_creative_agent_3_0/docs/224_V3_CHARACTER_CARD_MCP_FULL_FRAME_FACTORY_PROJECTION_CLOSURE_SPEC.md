# Doc224 — Character Card MCP Full-Frame Factory Projection Closure

## Status

Implemented as a narrow corrective closure after Doc223-D controlled validation.

## Intended behavior

Professional Character Card `expression_set` slots use the approved
`face.front` full-frame card as the first renderer reference. Tight feature and
geometry crops remain auxiliary references after the full-frame framing
authority. Provider and MCP materialization must receive the same canonical
reference order and the same durable semantic/rendering fingerprints.

## Observed mismatch

A fresh controlled validation on `origin/main@6cf65f0` created
`mcp_handoff_bbe68dceec` for `expression.laugh`. It was not submitted or
materialized. The durable handoff was append-only evidence and showed:

1. `portrait_identity_crop`;
2. `portrait_identity_geometry_crop`;
3. unsuffixed `face.front` full frame.

The top-level Product request metadata carried
`professional_character_card_stage=expression_set`, but the canonical provider
factory only projected a subset of `generation_plan.metadata` into
`GenerationRequest.metadata`. Character Card stage/slot fields were omitted at
that boundary, so the provider could not identify the generated `face.front`
asset as the card-framing authority.

## Responsible layer

The defect belongs to the Provider/MCP factory projection contract, not to the
prompt, Visual review, Character Card slot lifecycle, or MCP durable store.

The handoff store already preserved semantic/rendering fingerprints. However,
the renderer-facing reference projection also needed to preserve safe
`identity_evidence_scope` fields so durable handoff evidence can prove the
first input is a `card_framing` reference rather than relying only on asset-id
suffix fallback.

## Authoritative rule

Docs 216, 218 and 219 remain the authority:

- `expression_set` renderer inputs must be full-frame-first;
- the first reference must be the `character_card_full_frame_framing_reference`;
- tight identity crops are auxiliary, not framing authority;
- stale crop-first handoffs remain append-only failure evidence and must not be
  materialized.

## Fix

The provider factory now projects Character Card preparation metadata into the
canonical `GenerationRequest`:

- `professional_character_card_preparation`;
- `professional_character_card_stage`;
- `professional_character_card_slot`;
- `professional_character_card_source_class`;
- `professional_character_card_attempt_round`;
- `professional_character_card_reference_output_ids`.

The MCP materialized reference projection now preserves safe card-framing
semantic fields:

- `identity_evidence_scope`;
- `identity_evidence_group_id`;
- `character_card_framing_reference_mode`;
- `character_card_framing_mirrored`.

No prompt text, thresholds, retry budgets, Provider implementation, Vision
gate, or manual activation path was changed.

## Regression coverage

`test_doc224_expression_set_factory_projection_preserves_mcp_full_frame_first_contract`
covers the real boundary:

`build_provider_generation_request → McpMaterializationProvider._build_app_request → McpMaterializationHandoffStore.ensure_pending`

The test asserts:

- Provider/MCP receives `face.front` full-frame first;
- the first durable handoff reference is
  `character_card_full_frame_framing_reference`;
- `identity_evidence_scope=card_framing` survives into the durable handoff;
- semantic and rendering fingerprints are present.

