# Doc195 — V3 Character Card MCP Interactive Handoff Pacing

Status: active

Date: 2026-07-23

Supersedes/narrows:

- Doc178 Character Card candidate budgeting, only for the Local MCP outlet.
- Doc186 reference-led slot-delta execution, only where its MCP handoff timing was ambiguous.

## Problem

Provider execution can generate, review, and rank a full three-candidate slot
budget inside one synchronous server call.

Local MCP execution cannot be treated the same way.  Once the shared runtime has
created a canonical MCP handoff, a human/Codex-side image generation step must
materialize that exact prompt and submit the resulting pixel before the shared
Vision review can continue.  If the Character Card service keeps requesting
candidate 2 and candidate 3 before returning candidate 1's handoff, the frontend
and validation operator see a long apparently stalled prepare call even though
the system already has the next actionable step.

This is a pacing bug, not a prompt-quality bug and not a Vision gate failure.

## Rule

For Character Card Expression Set and Body Silhouette slots:

1. Provider mode keeps the full three-candidate automatic budget.
2. MCP mode returns immediately after the first durable pending MCP handoff or
   pending MCP review checkpoint for the current slot.
3. The returned card must be `blocked`/resumable with exactly the pending
   handoff ID projected to the public card state.
4. After the MCP artifact is submitted, resume continues from the same frozen
   candidate.  If shared review fails, the next resume may request the next
   candidate, up to the same three-attempt budget.
5. The fix must not relax shared Vision, change Provider behavior, create a
   second reviewer, or locally rewrite the Brain-authored canonical prompt.

Short form:

```text
Provider may auto-run the candidate budget.
MCP must surface one actionable handoff at a time.
```

## Acceptance

- A regression must prove MCP Expression Set pauses after the first pending
  handoff instead of requesting all three candidates.
- Existing Provider candidate-budget tests must continue to pass unchanged.
- Resume must remain append-only and must keep prompts, references, and review
  receipts in the shared runtime path.
