# Doc158 — V3 Remote Brain Latency and Final Sign-off Convergence

Status: **active shared-foundation runtime authority.**

This document optimizes the Brain call graph without changing creative
ownership, reference ownership, Human Realism obligations, Provider routing,
review, retry, or Local MCP parity.

## 1. Problem being closed

The previous enforced path for a visible real person was:

```text
remote Brain semantic plan
-> remote Brain canonical prompt finalization
-> remote Brain Human Realism natural-presence re-sign
-> Provider prompt materialization
```

The last two calls consumed the same frozen context and differed mainly in
whether the Brain was being asked to author the final prompt or approve/rewrite
that prompt. They were serialized, so normal remote latency was multiplied
before any image operation could begin. JSON serialization recovery remained a
bounded second transport attempt inside each logical Brain call.

## 2. Forward call contract

For a new enforced job, the shared runtime uses:

```text
remote Brain semantic plan
-> frozen CapabilityActivationPlan / envelope / constraint ledger
-> one remote Brain final sign-off
   (complete canonical prompt
    + Human Realism semantic preflight when required
    + Human Naturalness decision receipt when required)
-> exact Provider prompt materialization
```

The final sign-off is still a Brain decision. It receives the Brain's own
semantic directions together with the frozen shared facts and normalized retry
evidence. It may author or rewrite the complete canonical prompt, and must
return the typed `approved|rewritten` Human Naturalness receipt when the
Human Realism capability is active.

This is a convergence of two remote calls, not removal of a quality gate. The
runtime still blocks when the final prompt, semantic preflight, or naturalness
receipt is absent or invalid.

Historical records containing
`provider_prompt_human_naturalness_resign` remain readable. New forward jobs
record `canonical_provider_prompt_stages=["provider_prompt_finalize"]` and
`human_realism_natural_presence_signoff_mode="combined_finalizer"`.

## 3. Ownership and anti-overfitting boundary

- Remote Brain remains the only author of creative direction and the final
  renderer-facing natural-language prompt.
- The shared runtime supplies only frozen user/reference truth, capability
  obligations, resolved constraints, technical canvas, and normalized review
  evidence.
- No local prompt fragments, expression vocabulary, face recipe, negative-word
  list, child branch, apparel branch, or template-specific creative fallback is
  introduced.
- The Provider materializer only binds the signed prompt to the declared
  operation and admitted references.
- The Local MCP relay receives the same canonical prompt and reference binding;
  it remains conversation-only and non-certified.

## 4. Request and payload efficiency

Real-image planning uses the compact remote contract directly. The runtime no
longer constructs a broad compatibility payload and then discards it before
constructing the compact payload. Ordinary non-real General exploration keeps
its historical compatibility contract.

Each accepted Brain receipt records only safe phase provenance:

```json
{
  "stage": "plan|provider_prompt_finalize",
  "elapsed_ms": 0,
  "attempts": 1,
  "json_serialization_recovery_attempted": false
}
```

No prompt body, hidden reasoning, credential, endpoint, image, or raw provider
error is persisted by this timing receipt.

## 5. Compatibility and recovery

- Doc145's one same-request JSON serialization recovery remains unchanged.
- Historical two-stage finalization records remain readable and accepted by
  the Local MCP provenance reader.
- New Human Realism jobs require the combined finalizer receipt before any
  Provider operation.
- Product-only and non-human jobs do not receive a Human Naturalness decision
  or an extra Brain stage.
- No SDK retry is enabled. A serialization recovery is not a creative retry,
  Provider retry, or alternate-model fallback.

## 6. Acceptance matrix

The implementation is complete only when tests prove:

1. Human Realism: exactly `plan -> provider_prompt_finalize`; no third remote
   stage; canonical prompt and decision receipt are both Brain-authored.
2. Missing or malformed combined receipt blocks before materialization.
3. Product-only tasks remain `plan -> provider_prompt_finalize` without Human
   Realism fields.
4. Retry evidence remains available to the combined final sign-off and is not
   converted into renderer wording.
5. Exact canonical prompt parity and Local MCP provenance remain valid.
6. General, E-Commerce, Photography, Professional Mode, and reference input
   isolation regressions remain green.

## 7. Authority resolution

Doc139's original description of a separate serial re-sign remains a historical
semantic rationale. Its Human Realism requirement is preserved, but its
forward invocation shape is superseded by this document. Doc142's typed
`approved|rewritten` receipt remains mandatory and is now returned by the
combined finalizer.
