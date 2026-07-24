# Doc233 — Character Card Expression Slot Phase Readiness Audit

Status: implemented as a short compatibility audit before starting `expression.anger`.

## Scope

This audit checks whether the accepted `expression.laugh` single-slot result can
advance to the next Expression Set phase without confusing a phase pass with the
final Character Card acceptance.

No Provider/MCP generation, prompt change, threshold change, retry-budget change,
or production gate change is introduced by this document.

## Layer classification

| Area | Layer | Current authority |
| --- | --- | --- |
| Existing candidate/output → shared review → winner → slot receipt | Core | `SlotAcceptanceCore` plus lifecycle slot receipt persistence |
| `expression.laugh` affect/framing evidence | Enhanced | shared Visual Cluster expression review receipt |
| MCP handoff, operation index, checkpoint, stale-handoff defense | Auxiliary | Host/provider/store recovery adapters |
| Full Expression Set activation | Module policy | `activate_module(expression_set)` requires all required expression slots |

## Finding

The current code already keeps `expression.laugh` single-slot acceptance separate
from full Expression Set activation:

- `expression.laugh` may be `winner_selected` while `expression_set_status` stays
  `partial`;
- `expression.anger` and `expression.sad` may remain `empty`;
- full Expression Set activation still fails closed until all required slots are
  reviewed;
- Body Silhouette still requires an active Expression Set.

The remaining phase-readiness gap was narrower: explicit single-slot routing was
available for `laugh` and legacy `smile`, but not for the remaining required
Expression Set slots. That forced a caller to resume the whole Expression Set
instead of advancing one phase at a time.

## Fix

The explicit single-slot route now supports the required Expression Set slots:

- `expression.laugh`;
- `expression.anger`;
- `expression.sad`.

Legacy `expression.smile` remains an explicit optional extension only and still
cannot satisfy the default Professional positive slot.

The browser Character Card workspace now prepares the next missing required
expression slot when the Expression Set is `partial`. It does not treat a clean
`partial` state as a failure. This keeps the beginner-facing flow linear:

```text
laugh accepted → next click prepares anger
anger accepted → next click prepares sad
sad accepted → Expression Set can move to module confirmation
```

## Non-goals

- Do not start `expression.anger` inside this audit.
- Do not declare the whole Expression Set active after `expression.laugh`.
- Do not make Body Silhouette available before Expression Set activation.
- Do not add a private Character Card review, provider, retry, or prompt path.

## Acceptance

- A partial Expression Set with accepted `expression.laugh` can route explicit
  `expression.anger` or `expression.sad` through the same shared host and receipt
  path.
- The accepted `expression.laugh` slot is preserved.
- The other unstarted expression slot remains `empty`.
- Public UI and lifecycle wording continue to distinguish single-slot progress
  from whole-module activation.
