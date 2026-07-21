# Doc131: V3 Codex Native ImageGen Reference Input Parity

> **Doc183 materialization note:** The reference/hash/order parity defined here
> is also required by the explicit local MCP handoff. The handoff adds no
> reference interpretation and does not make this legacy planning surface a
> delivery store.

Status: active developer-preview extension of Doc130.  This is a General-only,
conversation-only planning surface; it changes neither Web Mode nor any
Provider, review, retry, delivery, or production gate.

## Single-path rule

```text
user-provided local image path
-> ordinary V3 UploadedAssetInfo.file_path
-> shared Scenario Runtime / remote Central Brain / frozen envelope
-> canonical Web Provider materialization and reference admission
-> exact final prompt + Web-admitted reference paths returned to Codex
-> one Codex built-in ImageGen call with that prompt and those paths
```

No Local-Mode upload store, image copy, reference classifier, prompt recipe,
or second resolver is permitted.  The source is passed into Alchemy unchanged.
The normal V3 Provider materializer remains the sole authority on whether the
image is an admissible reference and which source paths are attached to an
image-edit request.

## Public MCP contract

`prepare_native_imagegen_plan` accepts `reference_inputs`, each with only:

```json
{"channel":"product_truth","file_path":"C:/user-authorized/image.png"}
```

The planner hashes the explicit source only to bind it to the returned plan.
It constructs an ordinary V3 `UploadedAssetInfo`, records the existing asset
role for the declared channel, and requires that source as Provider input.  It
does not send the file path to the remote Brain; the LLM-first compact Brain
payload receives only safe asset evidence.

`channel` describes evidence ownership, not a one-image slot. Multiple
distinct user-approved files may therefore share `product_truth` (for example,
a product's front and back) or another declared channel. Their supplied order,
paths, and hashes are preserved through ordinary V3 admission. Identical
source bytes are one physical evidence item and are coalesced by the shared
Provider boundary; the returned declared/admitted counts make that explicit.
Local Mode must not drop, relabel, merge, crop, or replace distinct
same-channel evidence to make the request fit a private schema.

For each output, the response contains:

- `imagegen_prompt` and `provider_prompt_sha256` from Doc130;
- `reference_image_paths`: exactly the V3-admitted source paths that Web
  Provider receives before its normal transport preflight; and
- `reference_input_contract`: operation, declared/admitted counts, and source
  hashes.

Codex must call native ImageGen once with `imagegen_prompt` verbatim and those
same `reference_image_paths`; it must not replace, add, drop, re-order, or
textually reinterpret the references.  An empty list means text-to-image.

## Attachment limitation

An image selected in a Codex conversation is supported only if the host gives
the skill a readable local file path that it can send in `reference_inputs`.
If the attachment has no supported path handle, the planner returns
`codex_native_imagegen_reference_path_required` or
`codex_native_imagegen_reference_path_unavailable`.  It must not probe a
Codex session, cache, token, or private artifact store to manufacture a path.

## Local Brain setup

Local Mode still requires the same remote Central Brain that owns V3 creative
direction.  An MCP configuration may set `ALCHEMY_CODEX_LOCAL_ENV_FILE` to an
existing local `.env` file containing that Brain configuration.  The setting is
only a file path: keys remain in the existing file, are loaded before V3
imports, retain ordinary process-environment precedence, and are never copied
into the plugin response or Codex configuration.

## Boundaries and acceptance meaning

This proves that the same V3 reference evidence, LLM-first planning, frozen
constraints, canonical final prompt, and Web reference-admission result are
given to Codex native ImageGen.  It can be used for controlled image-direction
and visual-quality evaluation while the Web gateway is unavailable.

It does not prove Aiself/Web Provider availability, wire-level upstream
compatibility, Provider response parsing, shared review/retry, stored final
delivery, or any production gate. Doc133 permits an explicit frozen-plan
specialist relay under the same reference-input rule. It does not permit either
template to downgrade to General.

## Required regression evidence

- a local image path enters `ScenarioRuntime.uploaded_assets` unchanged;
- the compact remote Brain payload contains no local `file_path`;
- returned prompt and hash exactly match the Web Provider request built from
  the same frozen plan;
- returned reference paths exactly match Web Provider materialization for that
  plan;
- unreadable, corrupt, or unadmitted required references fail closed before
  Codex receives a prompt; and
- the MCP continues to create no candidate, delivery, artifact, retry, review,
  Web fallback, or image Provider request.
