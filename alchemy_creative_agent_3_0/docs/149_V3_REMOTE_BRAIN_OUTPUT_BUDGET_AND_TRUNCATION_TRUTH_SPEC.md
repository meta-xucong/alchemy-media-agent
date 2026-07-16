# Doc149 — V3 Remote Brain Output Budget and Truncation Truth

## Status

Implemented shared-runtime transport correction.  This document supplements
Doc145; Doc145 remains the authority for the single, bounded JSON
serialization recovery.  It does not alter Human Realism, template ownership,
reference channels, image Providers, or Local MCP materialization.

## Observed evidence

During the controlled one-reference General blue-dress plan, the configured
DeepSeek-compatible Central Brain returned Chat Completions with
`finish_reason=length` and `completion_tokens=4201` on both the original and
Doc145 recovery request.  Both partial bodies were therefore invalid JSON.
No image operation, Local MCP ImageGen call, candidate, review, retry, or
delivery was created.

The issue is a transport capacity boundary, not a reference-input failure,
Human Realism semantic decision, deterministic plan fallback, or renderer
prompt defect.

## Contract

1. A real-image job still requires a complete remote Brain result.  The
   remote Brain remains the only author of a canonical renderer prompt.
2. Default `V3_LLM_BRAIN_MAX_TOKENS` is `8000`.  It gives a
   reasoning-capable remote model enough output capacity to complete the
   compact JSON contract after its private deliberation.  An explicit operator
   environment value remains authoritative and is bounded to the documented
   transport range.
3. A provider transport that explicitly reports an output-length finish is
   classified as `BrainOutputTruncated`, never parsed, never locally repaired,
   and never mistaken for an ordinary malformed response.
4. Doc145's one recovery remains unchanged: it receives the same frozen user
   request, reference bindings, capability envelope and payload; only the
   recovery serialization instruction is added.  No third request is allowed.
5. If both calls are truncated, the Job fails closed with the safe public
   error class `truncated_response`.  It must not use a local plan, compact
   away factual evidence, substitute an old prompt, change the model, or start
   an image operation.

## Non-goals and anti-overfitting boundary

- No child, apparel, complexion, template, model-specific, or keyword branch
  is introduced.
- No request content is shortened opportunistically to make one sample pass.
- No raw remote response, endpoint, credential, prompt, image, or hidden
  reasoning is persisted as diagnostic evidence.
- This is not a Web Provider reliability claim or a certified visual-quality
  gate.  It only makes the remote planning transport truthful and complete.

## Required regression evidence

`test_v3_llm_brain_adapter.py` proves all of the following:

1. the default complete-plan output budget is `8000`;
2. one `finish_reason=length` response can use Doc145's same-request recovery;
3. two such responses stop after exactly two calls with
   `BrainOutputTruncated`;
4. neither path creates a local creative result.

After a live plan succeeds, a Local MCP comparison may materialize only the
exact remote-Brain-signed canonical prompt and admitted source-reference hash
from that fresh plan.  It remains conversation-only and non-certified.
