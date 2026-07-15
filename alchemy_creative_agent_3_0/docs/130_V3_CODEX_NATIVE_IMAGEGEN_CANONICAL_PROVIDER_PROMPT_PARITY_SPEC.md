# Doc130: V3 Codex Native ImageGen Canonical Provider Prompt Parity

Status: active developer-preview Local Mode authority. This document supersedes
Doc129's "Codex authors the image direction" contract for every new Local Mode
call. Doc126 remains an archive of the rejected Platform API/artifact route;
Doc129 remains a record of the rejected independently authored-prompt route.

## Non-negotiable principle

```text
For an admitted Local Mode request, the Unicode prompt handed to Codex built-in
ImageGen MUST be exactly the canonical final `generation_prompt` that the V3
Web Provider would hand to GPT Image 2 for the same frozen V3 plan.
```

Similarity is insufficient. The contract is exact UTF-8 equality, evidenced by
the same SHA-256 value. The rendering contract (`gpt-image-2`, size, quality,
and output format) is projected from that same materialization. Codex must use
the returned `imagegen_prompt` verbatim and must not append, summarize,
translate, re-order, or add a second prompt layer.

## Required execution path

```text
explicit Local Mode choice
-> shared Scenario Runtime / enforced frozen envelope
-> real remote Central Brain (no fallback)
-> same frozen V3 planning result
-> shared `build_provider_generation_request`
-> shared `ProductionImageGenerationProvider.materialize_final_prompt`
-> exact prompt + hash returned by MCP
-> one Codex built-in ImageGen call per output
-> conversation-only, non-certified result
```

The materializer is renderer-neutral: it validates reference admission,
constraint ledger, Human Realism, text policy, and the final prompt, but it
does not select an account, construct an upstream image client, call Aiself,
read an API key, or send an image request. The Web Provider calls the same
materializer before it selects and invokes GPT Image 2.

## LLM-first and failure behavior

Local Mode is not a prompt-writing fallback. It requires
`llm_used=true` and `fallback_used=false`; unavailable or malformed remote
Brain output, a non-enforced envelope, a count mismatch, or materialization
failure blocks before Codex receives an image prompt. It must never restore
local creative recipes, static slots, suite roles, camera/crop presets, or a
keyword stack merely to produce a prompt.

`general_template` uses the original public tool. Doc133 adds a separate,
explicit frozen-plan relay for E-Commerce and Photography; it does not weaken
their remote-Brain, template, reference, review, or production contracts and
must never make either template silently become General.

## Scope and reference boundary

Text-to-image is covered directly here.  Reference/image-to-image admission is
specified by Doc131.  It accepts only an explicit readable local file path:
the same source file is passed to V3 as ordinary `UploadedAssetInfo` evidence,
then V3's existing admission and canonical materialization return the exact
admitted reference paths that Codex must supply with the verbatim prompt.

A conversation attachment is equivalent only when the host exposes it as that
readable local file path.  Local Mode must block when it cannot obtain one; it
must not read undocumented Codex caches/sessions, substitute another image, or
claim a visible attachment was processed by V3.

## What this can and cannot accept

A successful Local Mode run is valid evidence that Alchemy's shared planning,
remote-Brain direction, canonical final-prompt materialization, and GPT Image
2 visual direction are functioning together. It can support controlled visual
quality evaluation of that prompt.

It is not evidence that the Web image gateway, Aiself, account routing,
provider response parsing, shared review/retry, project storage, or certified
final delivery is operational. Those remain separate Web/Provider acceptance
items. Provider uptime must not be used to invalidate this code/design
contract, and Local Mode success must not be used to hide a Web Provider
outage.

## Regression requirements

Tests must prove:

- Local Mode and Web Provider use the same request factory and canonical
  materializer;
- the returned `imagegen_prompt` is byte-for-byte equal to the Provider's
  `generation_prompt` and their SHA-256 values match;
- Local Mode never selects or calls an upstream image Provider;
- remote Brain fallback, envelope failure, incomplete output count, and a
  missing/unreadable/unadmitted reference block fail-closed;
- the MCP exposes only `prepare_native_imagegen_plan`, creates no artifact,
  candidate, review, retry, delivery, or Web fallback; and
- the plugin Skill instructs Codex to call ImageGen exactly once per output
  using the returned prompt verbatim.

No result from this developer-preview surface enables a production flag or
passes Provider Gate C/D, General Gate D, E-Commerce Gate C/D, or Photography
P10.
