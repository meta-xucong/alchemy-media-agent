# Doc218 — Character Card Provider/MCP Reference Order Parity

Date: 2026-07-24

Status: implemented for local validation

## Problem

Professional Character Card expression generation had already produced several visually acceptable laugh candidates, but the official slot lifecycle still blocked because the generated pixels did not preserve the approved `face.front` card framing closely enough.

The root cause was not another laugh prompt problem. The shared canonical prompt already carried the card-framing directive, but the MCP handoff could still receive reference images in the old crop-first order:

1. tight feature crop;
2. pose geometry crop;
3. full-frame `face.front`.

For expression slots, this order is wrong. The full-frame approved `face.front` image is the framing authority and must be the first native image input. The tight and geometry crops are only identity support.

The Provider path had been corrected by the provider reference-ordering helper, but the MCP materialization path could still read character-card metadata from a different location and therefore miss the same ordering contract. That meant Provider and MCP were not yet equivalent output channels.

## Intended behavior

For Professional Character Card `expression_set` slots:

- Provider and MCP must consume the same canonical prompt, reference manifest, reference hashes, and rendering contract.
- The first reference must be the full-frame `face.front` framing authority.
- Tight feature crop and head-geometry crop may follow as identity evidence.
- Pending MCP handoffs are not immutable when the current authoritative reference contract changes before materialization.
- Submitted or consumed MCP handoffs are immutable evidence and must fail closed if their references no longer match the current authoritative stage contract.

## Authoritative rule

`GenerationRequest.metadata` and `GenerationRequest.generation_plan.metadata` are both allowed carriers for professional character-card stage metadata. Provider packaging, MCP handoff construction, and reference derivation must read one merged view:

1. start with `generation_plan.metadata`;
2. overlay `request.metadata`;
3. derive the character-card reference package from that merged view.

This keeps Product API, ScenarioRuntime, Provider, and MCP aligned without introducing a private Character Card provider or a second review path.

## Pending handoff rule

If an MCP handoff is still `pending` and the current stage now has different reference hashes or a different rendering contract, it is treated as stale and ignored. The next resume creates a fresh pending handoff from the current authoritative contract.

If an MCP handoff is already `submitted` or `consumed`, a mismatch is a structured failure:

- `mcp_materialization_reference_mismatch`;
- `mcp_materialization_rendering_contract_mismatch`.

The system must not silently relabel, rewrite, or write such an artifact into a slot.

## Non-goals

Doc218 does not:

- loosen laugh, expression, identity, or framing gates;
- add another candidate budget;
- change the shared Vision reviewer;
- add a private Provider, MCP reviewer, retry loop, or storage system;
- let a visually nice but framing-failed candidate become a winner.

## Acceptance coverage

Required regression coverage:

- expression-set reference ordering reads character-card metadata from `generation_plan.metadata`;
- Provider asset plan puts `character_card_full_frame_framing_reference` first;
- a stale pending MCP handoff is superseded rather than materialized;
- a stale submitted MCP handoff fails closed;
- existing explicit handoff resume and Character Card resume behavior still pass.

## Validation implication

The existing stale pending handoff from the live validation run must not be materialized. After Doc218 is committed, the next validation resume should build a new handoff whose reference order is:

1. full-frame `face.front` card-framing reference;
2. tight identity crop;
3. head-geometry identity crop.

Only after this is confirmed may MCP generate the next `expression.laugh` candidate.
