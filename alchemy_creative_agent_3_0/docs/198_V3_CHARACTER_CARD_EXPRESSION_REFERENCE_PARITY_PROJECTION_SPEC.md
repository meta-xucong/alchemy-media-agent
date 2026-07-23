# Doc198 — Character Card Expression Reference Parity Projection

Date: 2026-07-24

## 1. Problem

During fresh MCP validation, `expression.laugh` successfully produced and
submitted a real image artifact, but Character Card candidate creation failed
before slot review with:

```text
Character Card candidate prompt/reference parity is required
```

The pixel artifact was not rejected by image quality review at that point.
The failure happened in Host-side prompt/reference parity projection.

## 2. Root cause

The Character Card Host guessed the expected renderer reference count from the
module:

```text
expression_set => 2 references
body_silhouette => 3 references
```

That assumption is stale. An expression slot can be driven by one logical
`face.front` winner while the shared reference materializer expands it into
multiple renderer references, such as:

- face feature-detail crop;
- face/head geometry crop;
- full front card frame for framing and visual channel continuity.

The fresh MCP handoff correctly carried three front-derived references and the
output metadata recorded `provider_reference_image_count=3`. The old Host
constant therefore marked a valid package as parity-false and triggered a
candidate validation error.

## 3. Correct contract

Character Card candidate acceptance must verify the renderer-facing package is
self-consistent. It must not infer a fixed reference count from the module.

The Host should require:

- `provider_prompt_sha256`;
- `prompt_compilation_id`;
- positive `provider_reference_image_count`;
- any declared reference counts in the shared metadata must match that
  provider count:
  - `reference_asset_count`;
  - `provider_reference_assets.length`;
  - `reference_asset_ids.length`;
  - `reference_input_execution.reference_count`.

If the shared metadata does not expose those richer counts, the old module
count remains only a backward-compatible fallback for legacy fixtures.

## 4. Failure behavior

If parity is not self-consistent, the Host must fail closed with the safe code:

```text
professional_character_card_prompt_reference_parity_unverified
```

It must not construct a `CharacterCardCandidateResult` with
`prompt_reference_parity_verified=false`, because that turns an expected
contract failure into an unhandled validation exception.

## 5. Scope

This is a projection fix only:

- no new Provider;
- no new MCP path;
- no new reviewer;
- no relaxation of expression quality gates;
- no change to the `face.front` framing contract;
- no image generation retry increase.

Provider and MCP remain equivalent materialization exits feeding the same
output metadata, shared review receipt, and Character Card slot gate.

## 6. Tests

Doc198 adds coverage that:

- a three-reference `expression.laugh` front-derived package passes parity;
- an inconsistent declared reference count fails closed with the safe parity
  failure code instead of crashing candidate model validation.
