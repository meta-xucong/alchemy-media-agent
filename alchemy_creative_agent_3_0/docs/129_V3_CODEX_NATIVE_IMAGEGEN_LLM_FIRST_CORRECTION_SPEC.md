# Doc129: V3 Codex Native ImageGen LLM-first Correction

Status: **superseded for active Local Mode behavior by Doc130.** It remains a
historical correction record for the rejected independently authored-prompt
route. Preserve its isolation lessons, but do not restore Codex-authored
creative directions for new Local Mode calls.

> **Authority note:** Doc130 makes canonical Provider Prompt parity the Local
> Mode invariant: the MCP returns the exact final `generation_prompt` that the
> V3 Web Provider materializes for the same frozen plan. This document's
> previous "Codex conversation authors" language is archival only.
>
> **Doc135 clarification:** this document cannot be used to revive a local
> phrase list, keyword classifier, retry patch or alternate Codex-authored
> prompt.  Local Mode relays the remote Brain's complete approved canonical
> prompt and its admitted references byte-for-byte, or blocks.

## Why N1 is superseded

N1 correctly avoided the rejected Platform-API/key-file/artifact-import route,
but an acceptance smoke test showed its returned `imagegen_prompt` carried
legacy deterministic General material such as a hero role, shot family, camera
distance, angle, crop, and suite language. That is not an LLM-first natural
image direction and must never reach Codex built-in ImageGen.

This is a Local Mode correction, not a change to Web Mode, General, E-Commerce,
Photography, the shared Provider, or any production gate.

## Corrected Local Mode contract

```text
explicit user choice in Codex
-> local Alchemy constraint admission MCP
-> protected user truth + frozen generic guardrails + declared references
-> current Codex conversation authors one natural-language whole-image direction per output
-> Codex built-in ImageGen makes one call per output
-> conversation-only, non-certified result
```

Alchemy's local MCP is responsible for request admission, exact requested
count, frozen enforced envelope identity, text/reference safeguards, and the
shared quality-capability decision. It is **not** the creative-direction
author. The current Codex conversation is the creative-direction author and
the built-in ImageGen renderer owner.

The local deterministic runtime may be observed while resolving admission
facts, but its creative strings, fallback image-set plan, prompt compilation,
template deliverable direction, legacy role metadata, capability prompt atoms,
negative prompt atoms, retry patch, and review recipe are discarded. They must
not be projected to the MCP response or Codex prompt.

## Public response boundary

For each exact-count output, the MCP returns only:

- opaque `output_binding_id`;
- protected user intent and effective image size;
- a short list of resolved non-creative guardrails;
- active shared quality capability identifiers excluding `suite_direction`;
- declared conversation-reference instructions; and
- an instruction for Codex to write one natural-language whole-image direction.

It does not return `imagegen_prompt`, role/slot identifiers, camera/crop/shot
recipes, static suites, raw envelopes, raw ledgers, provider configuration,
candidate state, artifact path, image bytes, review/retry outcome, or delivery
record.

## Required Codex behavior

The installed plugin Skill must, after a successful plan:

1. author one self-contained natural-language direction for each requested
   output, based on the protected user intent and guardrails;
2. keep references limited to their declared channel;
3. use exactly one built-in ImageGen call per output; and
4. stop if the built-in tool is unavailable or the admission request is blocked.

It must not create a Web request, API request, external provider call, local
image file, candidate, review, retry, final delivery, continuation, or release
claim. It must label any image as `conversation_only_not_certified`.

## Template and gate boundary

Only `general_template` is enabled. E-Commerce and Photography remain blocked:
their remote-Brain, reference, role-count, real-pixel review, and delivery
contracts are stronger than a conversation-only feature. This Local Mode cannot
substitute for Provider Gate C/D, General Gate D, E-Commerce Gate C/D, or
Photography P10, regardless of what Codex displays.

## Regression contract

Tests must prove all of the following:

- exact output count and enforced envelope identity are retained;
- fallback creative content is never projected;
- response text excludes static role, suite, shot, camera, crop, and
  `imagegen_prompt` fields;
- `suite_direction` is not offered to Codex;
- General-only/reference/secret/Web-provider/artifact isolation remains intact;
- the MCP exposes only `prepare_native_imagegen_plan`; and
- the plugin Skill requires Codex-authored natural language rather than a
  structured prompt stack.

Doc126 is retained solely to prevent the rejected N1 behavior from being
mistaken for the active contract. The historical B2 Platform API experiment
remains rejected as documented in Doc126.
