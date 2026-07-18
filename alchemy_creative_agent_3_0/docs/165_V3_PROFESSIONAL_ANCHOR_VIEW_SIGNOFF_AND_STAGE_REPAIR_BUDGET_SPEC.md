# Doc165 — Professional Anchor View Sign-off and Stage Repair Budget

Status: implementation, regression and local formal M5 pixel acceptance complete.
Production/browser activation remains a separate release decision and stays off.

## 1. Live failure evidence

The latest bounded M5 run passed `standard_front` and `three_quarter`. The frozen
third-stage plan selected `profile`, but the Remote Brain's final canonical prompt
described a centered generic studio headshot and omitted the side-view operation.
GPT Image 2 then produced non-profile pixels, and shared Vision correctly rejected
them for pose noncompliance.

This is not a Human Realism threshold defect and not evidence that the renderer
cannot produce the requested view. The same admitted references plus a canonical
profile direction generated strict profile pixels through the local Codex ImageGen
channel. One such image passed the unchanged shared Vision and identity evidence
gate. That comparison is provider-independent evidence that the frozen view was
lost at Brain final sign-off.

The same run also exposed a budget defect. Candidate one owned the only stage repair
by ordinal. If it failed before pixels, candidates two and three could not use the
still-unspent shared repair after a real review failure.

## 2. Authority and non-goals

This document extends Docs 93, 96, 161–164. It is shared Professional execution
governance, not a child, scene, template recipe or prompt-tuning document.

It must not:

- inspect canonical prompts with keywords, regular expressions or local semantic
  classifiers;
- append a view suffix, negative list or repair fragment after Brain sign-off;
- lower pose, identity, Human Realism or visual-quality thresholds;
- create a Professional-only Provider, reviewer, retry loop or storage path;
- replan through General or change Standard Mode behavior.

## 3. Typed anchor-view sign-off

Formal anchor preparation freezes exactly one structural role:

- `standard_front`;
- `three_quarter`;
- `profile`.

ScenarioRuntime projects that server-owned role into the canonical finalizer as a
typed `professional_anchor_view_decision`. The Remote Brain remains the only author
of the complete natural-language renderer prompt. It must independently reconcile
the whole prompt with the exact frozen role, rewrite the complete prompt when
needed, and return a schema-only receipt containing the identical role.

The adapter validates only receipt shape and exact role parity. It never judges the
prompt text. Missing or mismatched receipt triggers one bounded Remote-Brain-only
complete re-answer under the same frozen context. A second invalid response blocks
before Provider with `professional_anchor_view_decision_missing`.

Shared pixel review remains the final semantic guard. A syntactically correct
receipt cannot turn a wrong-pose image into a passing anchor.

## 4. Stage-owned shared repair budget

Each anchor stage owns at most one existing shared visual repair. The budget is
consumed only when Product API evidence reports `visual_auto_retry.executed_count >
0`. It is not consumed by candidate number, planning failure, Provider rejection,
timeout or any other no-pixel terminal state.

Consequences:

- if candidate one fails before pixels, candidate two may still execute the one
  shared repair after a retryable shared review;
- once any candidate actually executes it, all later candidates in that stage have
  visual auto-retry disabled;
- the total remains one repair per stage and all attempts stay append-only;
- the repair still uses the existing review evidence → Remote Brain complete rewrite
  → shared Provider path. No local patch is introduced.

## 5. Acceptance

Code acceptance requires:

1. exact typed view role reaches the finalizer and appears in every required receipt;
2. missing or mismatched receipt receives at most one same-context Brain re-answer;
3. no prompt keyword/regex/view-suffix implementation exists;
4. no-pixel candidate failure preserves the stage repair budget;
5. an actually executed repair consumes the stage budget exactly once;
6. existing General, E-Commerce, Photography, Standard Mode and Professional tests
   remain green;
7. full V3 regression, compile checks and diff checks pass.

Pixel acceptance requires a fresh bounded formal sequence:

```text
front: 3 candidates -> shared Vision -> winner
three-quarter: root + front winner -> 3 candidates -> shared Vision -> winner
profile: root + front + three-quarter winner -> 3 candidates -> shared Vision -> winner
explicit reviewed pack activation
```

If this sequence still fails, use the recorded failure category. Do not lower a gate
or add prompt atoms. Provider/no-pixel failures, Brain contract failures, pose
failures and identity/Human Realism failures remain distinct evidence classes.

## 6. Formal local acceptance record

The bounded run `doc165_20260718T133110Z` executed on `main@7e29596` from the
authorized root portrait with SHA-256
`93786216f2a33fbdd668b7b68e2b9b2fb8a5092de26e9173314a79021684e079`.
It used a new ready upload, a new project-scoped People Asset and the formal Product
API anchor host. No hand-written pack, candidate, review or activation record was
injected.

The selected and persisted winners were:

| View | Output | Same person | Human realism | Visual quality | Pose |
|---|---|---:|---:|---:|---:|
| `standard_front` | `v3_output_8c61c64ee720490f8c65` | 0.8492 | 0.91 | 0.93 | 0.98 |
| `three_quarter` | `v3_output_5cff6bd2d5f44c3fa532` | 0.9289 | 0.89 | 0.91 | 0.94 |
| `profile` | `v3_output_21b11764830f4fa4b966` | 0.8620 | 0.90 | 0.91 | 0.93 |

All three carry verified shared real-pixel review, canonical prompt/reference parity
and face-localized identity evidence. The exact typed anchor-view receipt is present
and signed in the persisted Brain audit. Two independent candidates ended as
no-pixel generation failures and stayed append-only. The only executed shared
visual repair was profile candidate three (`executed_count=1`); no other stage or
candidate executed a repair, proving the stage budget remained bounded and followed
actual use rather than ordinal position.

The completed pack `pack_46ce1add284241b0aa2ccfc9b7d3a729` was explicitly
activated. The unchanged `0.82` identity threshold and shared Vision/Human Realism
gates decided every candidate. No local prompt patch, keyword gate, score override,
private Provider path or production flag change was used.

Sanitized local evidence is retained outside Git at
`.codex-longrun/evidence/PROFESSIONAL_M5_DOC165_FORMAL_SANITIZED.json`; it contains
IDs, hashes, scores, lineage and budget outcomes, but no source media, complete
prompt, key, endpoint or raw provider response.
