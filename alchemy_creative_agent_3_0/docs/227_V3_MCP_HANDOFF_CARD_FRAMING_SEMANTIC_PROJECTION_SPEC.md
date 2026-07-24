# Doc227 — MCP handoff card-framing semantic projection closure

Date: 2026-07-24

## Problem

Post-Doc226 controlled validation created a fresh `expression.laugh` MCP
handoff with the correct full-frame-first reference order:

1. approved `face.front` full-frame reference;
2. identity detail crop;
3. head-geometry crop.

The handoff still failed Gate 1 because the first durable reference lost two
card-framing semantic fields:

- `character_card_framing_reference_mode=independent_original_card_framing`
- `character_card_framing_mirrored=false`

Provider reference construction already produced these fields. The loss
occurred only inside the durable MCP handoff projection layer:
`McpMaterializationHandoffStore._safe_reference_contract()`.

## Authoritative rule

The MCP handoff store is allowed to sanitize references, but it must not erase
safe semantic fields that are part of the current reference contract. For
Character Card Expression Set framing, the durable handoff reference and its
semantic fingerprint must preserve:

- `derivative_kind`
- `identity_evidence_scope`
- `identity_evidence_group_id`
- `reference_truth_layer`
- `character_card_framing_reference_mode`
- `character_card_framing_mirrored`

These are not prompt, private path, biometric vector, provider response, or raw
review fields. They are minimal typed contract fields required to prove which
reference owns framing authority and whether the face-front card was mirrored.

## Scope

This fix is limited to MCP handoff durable projection and semantic
fingerprinting. It does not change:

- prompt wording;
- Provider canonical binding;
- MCP/Provider generation behavior;
- shared Vision review;
- laugh/framing/identity thresholds;
- candidate or retry budgets;
- slot writer or activation gates;
- any old handoff record.

Old handoffs remain append-only historical evidence. They are not migrated,
rewritten, consumed, or promoted.

## Regression coverage

The Doc227 regression proves:

- Provider-style full-frame reference fields survive
  `ensure_pending() -> durable readback`;
- the existing Character Card handoff-order gate can read the durable contract;
- changing `character_card_framing_reference_mode`,
  `character_card_framing_mirrored`, or `identity_evidence_group_id` changes
  the `reference_semantic_fingerprint`, preventing stale pending resume when
  the same pixels carry a different semantic role.

