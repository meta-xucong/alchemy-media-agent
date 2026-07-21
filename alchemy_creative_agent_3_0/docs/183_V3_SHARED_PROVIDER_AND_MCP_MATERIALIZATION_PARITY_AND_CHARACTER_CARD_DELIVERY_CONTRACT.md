# Doc183: V3 Provider/MCP Shared Materialization Parity and Character Card Delivery

Status: active shared-runtime contract. This document extends Docs130–134 for
materialized local MCP execution. It does not open a production gate, replace
the Web Provider, or turn the legacy conversation-only MCP planner into a
second delivery system.

## 1. The decision boundary

V3 has two selectable rendering channels:

```text
one frozen V3 job and one canonical Brain-signed plan
  -> one canonical final Provider prompt and prompt hash
  -> the same admitted references, order and rendering parameters
  -> either Web Provider transport or explicit local Codex/MCP transport
  -> the same V3 output store
  -> the same shared visual review, bounded retry and winner selection
  -> the same Character Card slot writeback
```

“Equivalent” means contract and lifecycle equivalence. Provider and MCP are
independent stochastic image calls, so this contract does not promise
pixel-identical images or identical random composition.

The renderer channel is transport provenance, not a creative decision. It may
be selected as `provider` or `mcp` for a trusted Professional/Character Card
stage. General, E-Commerce and Photography cannot use the MCP materialization
path as a fallback or use it to bypass their own Brain/template gates.

## 2. One canonical materialization contract

Before either channel is selected, the shared runtime must freeze:

- the remote Brain-approved whole-image direction and final provider prompt;
- the UTF-8 prompt bytes and SHA-256 hash;
- the ordered, technically admitted reference assets and their content hashes;
- model, size, quality, output format, count, operation (`image_generate` or
  `image_edit`) and input-fidelity requirements;
- the job, role/stage, project and Character Card lineage.

The Web Provider adapter and MCP handoff must consume these same values. MCP
must not rewrite, shorten, paraphrase, add negative instructions, infer a
different age/style, reorder references or accept a user-supplied replacement
prompt. The only bytes supplied by the local MCP client are the image artifact
returned by the Codex ImageGen conversation.

## 3. Explicit local MCP handoff

The shared materializer creates a nonce-protected, local-only handoff. Its
public view contains only the canonical prompt, prompt hash, admitted
reference contract, rendering contract and opaque handoff identifiers. The
local client then:

1. reads the frozen handoff;
2. calls the built-in Codex ImageGen once with the exact prompt and references;
3. submits exactly one readable PNG/JPEG/WebP artifact with the nonce,
   matching prompt hash and matching reference hashes;
4. resumes the same frozen V3 stage through an append-only continuation job.

The handoff verifies image bytes, format, size and artifact hash. A missing,
changed, duplicate, mismatched or cross-operation artifact is rejected. The
MCP bridge accepts only loopback HTTP and never reads Web Provider keys,
Codex session/auth caches or arbitrary application artifacts.

An unsubmitted handoff is a resumable pending state, not a provider failure
and not a reason to spend visual retry budget. Resuming may choose either
channel, but it must keep the same frozen stage contract. Failed attempts stay
append-only; a slot is changed only by the ordinary shared winner/finalization
path.

When a trusted Character Card stage is paused before pixels, the public asset
projection carries only the opaque pending `mcp_handoff_ids` and the selected
`generation_channel`. The user/Codex client uses those IDs to read and submit
the handoffs, then resumes the same stage. No public projection exposes the
canonical prompt, local reference path, artifact file, provider response or
review body.

## 4. Shared output and Character Card writeback

Both channels write through `V3GeneratedOutputStore`. The shared pipeline then
owns pixel receipt, review mode/verdict, retry history, final winner and
delivery projection. A Character Card fixed slot is filled only when the
shared receipt is verified and the winner is selected. Pending, blocked,
metadata-only or manual-confirmation results remain in history and leave the
slot empty/withheld.

The public asset projection may expose the selected channel as safe provenance,
but never exposes prompts, source paths, provider internals, raw review bodies,
candidate history or secrets.

## 5. Compatibility and scope

Docs130–134 remain valid for their legacy conversation-only planning tools.
Those tools do not create V3 candidates or delivery records. The new
materialized tools are the only MCP route that can hand an image to V3, and
they do so through the shared handoff contract above. Historical plans and
records remain readable; they are not silently re-executed through MCP.

No second Provider, Brain, review, retry, storage or Character Card lifecycle
is permitted. Web production defaults, Gate C/D, M5 and all template
production flags remain unchanged.

## 6. Acceptance matrix

Code acceptance must prove:

- provider and MCP materializers produce byte-identical canonical prompt/hash,
  reference hash/order and rendering contract from the same frozen request;
- pending → submit → consume is nonce-, hash-, format- and one-time-safe;
- MCP pending is resumable and non-retryable, while ordinary shared visual
  retry remains available after a real pixel review failure;
- both channels create the same V3 output-record shape and provenance fields;
- only a verified shared winner reaches the same Character Card fixed slot;
- switching channel on resume does not change the frozen prompt or references;
- General/E-Commerce/Photography cannot enter this trusted Character Card
  materialization path or downgrade into it.

Controlled local acceptance may use a Codex/MCP-produced image artifact in
place of a live Web Provider response. That proves Alchemy's shared code,
prompt parity, storage, review and slot lifecycle. It does not claim Web
Provider availability, pixel equality, M5 completion or production readiness.
