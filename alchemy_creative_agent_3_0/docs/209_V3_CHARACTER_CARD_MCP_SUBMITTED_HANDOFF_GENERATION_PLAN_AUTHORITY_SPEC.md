# Doc209 — Character Card MCP submitted handoff generation-plan authority

## Scope

This document supersedes the incomplete transport reading of Doc203/Doc205/Doc207/Doc208 for one narrow boundary:
when a Professional Character Card stage already has a durable MCP handoff for a scoped operation, the selected handoff
must remain authoritative all the way into the frozen per-output `GenerationPlan.metadata`.

It does not change the Character Card slot map, expression quality gate, candidate budget, shared Vision review, Provider
implementation, or MCP storage model.

## Intended behavior

For a scoped operation such as:

```text
people_asset_id:expression_set:expression.laugh:candidate_index:roundN
```

the resolver may select exactly one current handoff:

- a single `submitted` handoff wins over stale `pending` hints for the same operation;
- a matching `pending` handoff may pause/resume materialization when no submitted artifact exists;
- multiple submitted/current handoffs remain fail-closed as ambiguous.

Once selected, the same `mcp_materialization` receipt must be present at every boundary:

1. `ProductApiAnchorPackPreparationHost`
2. `V3ProductApiService.create_professional_character_card_stage_job`
3. `ScenarioRuntime._renderer_channel_metadata`
4. `CentralCreativeBrain` per-output `GenerationPlan.metadata`
5. `build_provider_generation_request`
6. `McpMaterializationProvider`

The Provider/MCP layer must consume the selected handoff. It must not infer a different handoff from operation id alone,
ask Brain for a new prompt, or create a new pending handoff for the same candidate while a selected submitted artifact is
available.

## Observed mismatch

After Doc208, real validation selected a submitted handoff at the operation resolver, but the final job opened a new
pending handoff for the same operation. The new handoff carried a fallback prompt and `fallback_used=true`.

The responsible gap was not image quality, policy refusal, or MCP artifact submission. It was projection loss:
`generation_channel` and `mcp_operation_id` survived into `GenerationPlan.metadata`, but `mcp_materialization` did not.

## Authoritative rule

`mcp_operation_id` identifies the stage/candidate operation. It is not sufficient to identify the selected artifact.

`mcp_materialization.handoff_id` is the artifact authority once the resolver has selected it. It must be carried together
with the operation id. Dropping it reopens Brain/materializer selection and violates Provider/MCP equivalence.

## Regression requirement

A regression must prove that a ScenarioRuntime request containing:

```json
{
  "generation_channel": "mcp",
  "mcp_operation_id": "...",
  "mcp_materialization": {"handoff_id": "...", "status": "submitted"}
}
```

produces a frozen `GenerationPlan.metadata` containing the exact same `mcp_materialization` receipt.

This is a transport/authority test, not a prompt-quality test.
