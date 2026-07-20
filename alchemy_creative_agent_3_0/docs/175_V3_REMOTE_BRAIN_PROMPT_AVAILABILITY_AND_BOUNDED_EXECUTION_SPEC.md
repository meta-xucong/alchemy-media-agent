# Doc175 — V3 Remote Brain Prompt Availability and Bounded Execution

Status: **active shared-foundation authority.**

This document closes the MCP/Web planning failure in which a valid Remote
Brain was invoked repeatedly inside one logical request until the outer caller
timed out. It does not authorize local creative fallback, static prompt
recipes, child-specific routes, keyword matching, or a second image path.

## 1. Required outcome

For every real-image planning request, V3 must do one of two things within a
finite, observable execution budget:

```text
return an exact Remote-Brain-signed canonical prompt plan
or
return one explicit, safe blocked outcome before any image operation
```

The runtime must never leave a client in an unbounded planning state. A
blocked outcome is not a prompt fallback and does not authorize image
generation. Availability means a terminal, diagnosable contract—not pretending
that an unreachable external model can produce creative language.

## 2. Creative ownership stays unchanged

```text
protected user intent + reference authority
-> Remote Brain semantic plan
-> frozen activation envelope + resolved constraint ledger
-> Remote Brain canonical final sign-off
-> exact Provider/MCP prompt materialization
```

The Remote Brain remains the only author of creative direction and final
renderer language. Local code may validate contracts, bind admitted
references, calculate a deadline, and project safe provenance. It must not
assemble, append, compact, translate, or substitute a renderer prompt.

## 3. New forward execution shape

New enforced real-person, age-transition, and ordinary real-image jobs use:

```text
plan -> provider_prompt_finalize
```

The finalizer receives the frozen Human Realism, developmental-age,
developmental-presence, reference-ownership, and retry-evidence contracts. It
returns the complete prompt plus required typed receipts in the same Remote
Brain response. A current-request-owned age transition does **not** cause the
old additional `provider_prompt_developmental_presence_verify` call.

This is a call-graph convergence, not removal of age or Human Realism review.
The finalizer blocks when any required receipt is absent or invalid. Historical
records containing a developmental-presence re-sign remain readable and their
payload parser remains compatible, but no new forward job emits that stage.

Professional serial capture continuity remains its own narrow, frozen
post-winner sign-off because it has a distinct prior-winner authority. It is
not a generic age/person retry path.

## 4. Execution budget and transport behavior

`V3_LLM_BRAIN_TIMEOUT_SECONDS` remains a per-remote-call maximum.
`V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS` is a single deadline shared by all
remote decisions in one ScenarioRuntime preparation. Its default is at least
two ordinary per-call windows plus a small hand-off margin.

Each transport call uses the smaller of its ordinary per-call timeout and the
remaining logical budget. When no time remains, the runtime returns
`execution_budget_exhausted` as a safe Remote Brain failure class; it neither
starts another Brain call nor sends an image request.

The deadline is an ephemeral transport control. It is never sent to the Brain,
never becomes prompt text, and never persists as a secret or a creative fact.
SDK retries remain disabled. The existing one JSON serialization recovery is
still allowed only when the remaining shared budget can support it.

## 5. Prompt payload efficiency

Semantic planning keeps the complete planning instruction set. Canonical prompt
sign-off uses a smaller, stage-specific Brain instruction that preserves:

- protected user intent and reference-channel ownership;
- holistic Human Realism, developmental-stage, expression, and material
  judgement;
- mandatory typed receipts;
- one complete Brain-authored prompt, never fragments or local repair text.

It intentionally excludes planning-only repetitions already represented by the
frozen finalization context. This is not semantic compression of user intent
and does not change provider prompt parity.

## 6. Safe provenance projection

V3 records only safe aggregate execution facts:

```json
{
  "remote_brain_call_count": 2,
  "stages": ["plan", "provider_prompt_finalize"],
  "total_elapsed_ms": 0,
  "execution_budget": {
    "logical_budget_seconds": 0,
    "remaining_ms": 0,
    "state": "within_budget|exhausted"
  }
}
```

The MCP relay may expose this receipt for a planned or blocked result. It must
not reveal a raw prompt in failure provenance, an endpoint, provider body,
credential, source path, hidden reasoning, or internal timestamp. It does not
create a second lifecycle, candidate, delivery, retry, or certification path.

## 7. Configuration ownership

The Codex Local Mode launcher loads only the repository-owned Alchemy runtime
environment selected by its explicit non-secret path mechanism. It never reads
Codex login/session/cache state and never uses it as a hidden Brain or Provider
credential. The configured remote Brain remains the common Web/MCP planning
authority, so a successful Local Mode plan has the same canonical prompt and
reference binding as normal V3 Provider materialization.

## 8. Acceptance matrix

1. A real-person current-age request makes exactly two Remote Brain calls:
   `plan`, then `provider_prompt_finalize`.
2. The combined finalizer must reject a missing semantic, naturalness,
   developmental-age, developmental-presence, reference-ownership, or
   Professional receipt before materialization.
3. A logical deadline is shared across plan/finalizer, produces a safe terminal
   `execution_budget_exhausted` outcome, and never starts Provider work.
4. The finalizer instruction is smaller than the planning instruction while
   retaining Brain-only authorship and no local renderer wording.
5. MCP returns the exact canonical prompt/reference parity plus safe planning
   receipt for success, and safe failure/budget facts for a block.
6. General, E-Commerce, Photography, Professional Mode, product-only,
   non-human, and historical developmental re-sign compatibility remain
   isolated and green.

## 9. Authority resolution

Doc158 remains the call-graph convergence authority. Its former narrow
developmental re-sign exception is superseded by this document for new forward
jobs. Docs130/133/134/135 retain exact Local MCP parity and anti-local-fallback
requirements. Docs166/167 retain their shared developmental-age and vitality
semantic contracts; only their former extra forward transport stage is
superseded.
