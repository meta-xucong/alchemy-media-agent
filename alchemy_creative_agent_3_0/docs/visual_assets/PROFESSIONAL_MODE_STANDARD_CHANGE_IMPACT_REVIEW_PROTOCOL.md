# Professional Mode Standard-Change Impact Review Protocol

## Purpose

Professional Mode is intentionally isolated from Standard Mode, but it reuses
the shared V3 foundation. A Standard Mode improvement may therefore be either
irrelevant to Professional Mode or a shared-contract change that requires a
controlled adaptation. This protocol makes that decision explicit and
repeatable.

This is an unnumbered Professional Mode operating document. It does not change
Standard Mode, General Template, E-Commerce, Photography, or any numbered V3
authority.

## Trigger

Run this review whenever a Standard Mode change touches any of the following:

```text
Remote Brain semantic task profile or capability activation intent
CapabilityActivationPlan or frozen-plan timing
reference-channel ownership, identity evidence, or adaptive reference limits
Human Realism semantic preflight or independent re-signing
canonical Provider prompt creation, signing, or hash verification
GPT Image 2 provider materialization
shared pixel review, bounded retry, final-result selection, or history
shared request/response schemas used by Professional Mode bindings
Project/Reference/Output/History storage contracts used by People Assets
```

Purely Standard-only changes still receive a lightweight classification so the
absence of impact is recorded rather than assumed:

```text
Standard UI copy/layout only
General-only beginner interaction
E-Commerce/Photography deliverable semantics
Standard-only defaults or compatibility aliases
```

There is no safe assumption that a change is irrelevant merely because its
commit message says “refactor”. Inspect the changed contract and tests.

## Impact Classification

Every reviewed Standard Mode change receives exactly one status:

| Status | Meaning | Professional Mode action |
| --- | --- | --- |
| `NO_IMPACT` | Standard-only surface or behavior; no shared contract changes. | Record the evidence; no Professional Mode code/doc change. |
| `REVIEW_REQUIRED` | Shared bugfix or internal refactor that is intended to preserve the existing contract. | Run focused Professional Mode parity and isolation checks; update the register. |
| `ADAPT_REQUIRED` | Shared schema, semantic profile, activation, reference, prompt-signing, review/retry, or storage contract changed. | Create a scoped adapter/document/test change on the Professional Mode branch. |
| `BLOCKED` | The change invalidates a required Professional Mode invariant or has no compatible interpretation. | Stop Professional Mode integration until a separate architecture decision resolves it. |

`NO_IMPACT` is not a shortcut around review. It is a recorded conclusion with
the inspected commit range and affected paths.

## Standard Maintainer Handoff

After a Standard Mode change, the maintainer should send this compact handoff
to the Professional Mode audit session:

```text
Professional Mode impact audit requested.
Standard baseline: origin/main@<commit>
Previous audited baseline: <commit or unknown>
Changed docs/code: <paths or commit range>
Intended status: <NO_IMPACT | REVIEW_REQUIRED | ADAPT_REQUIRED>
Known shared-contract changes: <none or list>
Standard tests: <exact command and result>
Please fetch origin, inspect the range, classify independently, append the
impact record, and create a scoped Professional Mode adaptation only if needed.
Do not modify Standard Mode or merge main.
```

The audit session must not rely solely on the intended status; it verifies the
classification from the actual diff.

## Professional Mode Audit Procedure

The audit is performed in the dedicated Professional Mode worktree and branch:

```text
1. git fetch origin
2. compare the previous audited baseline with the new origin/main
3. inspect changed contracts, implementation paths, and regression tests
4. classify the change using the table above
5. verify Standard/Professional isolation and the current Brain-owned path
6. if NO_IMPACT, append a no-action record
7. if REVIEW_REQUIRED, run focused parity tests and append the evidence
8. if ADAPT_REQUIRED, update only this document set and the smallest required
   Professional Mode adapter/tests, then commit and push the feature branch
9. if BLOCKED, record the exact invariant and stop before implementation
```

The current Professional Mode forward path remains:

```text
explicit mode + selected People Asset evidence
  -> complete Remote Brain semantic task profile and capability intent
  -> frozen CapabilityActivationPlan
  -> complete signed canonical Provider prompt and hashes
  -> Human Realism preflight/re-signing when active
  -> exact GPT Image 2 materialization
  -> shared real-pixel review, bounded retry, and final delivery
```

The Face Identity Module may adapt to shared improvements through a typed,
versioned binding. It may not absorb Standard Mode UI, defaults, keyword
heuristics, local prompt fragments, or scenario-specific recipes.

## Required Invariants During Every Review

```text
Standard Mode behavior remains unchanged by the Professional Mode adaptation.
Professional Mode remains explicit opt-in and binds one project asset/version
per job.
Face Identity supplies evidence and lifecycle state, not creative prompt prose.
Remote Brain remains the owner of semantic judgment and canonical Provider
prompt creation/signing.
Capability activation remains frozen before Provider execution.
Human Realism preflight/re-signing remains mandatory when active.
Provider and Reviewer receive the same admitted reference IDs/hashes.
Shared retry remains bounded and append-only.
No second Provider, Brain, reviewer, retry system, image store, or registry is
created.
No Standard Mode fallback, silent asset migration, or legacy heuristic
activation is introduced.
```

## Append-Only Impact Register

Add one row for every reviewed Standard Mode baseline. Do not rewrite previous
rows; if a classification changes, append a correction row with the reason.

| Date | Standard baseline | Changed scope | Status | Professional action/commit | Evidence | Auditor |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-07-16 | `origin/main@267f8b1` | Brain semantic profile, canonical prompt signing, Human Realism gates | `ADAPT_REQUIRED` | `7d59f75` — aligned the three Professional Mode docs with Doc134–Doc140 | `git diff --check`; markdown fence check; `761 passed, 3 pre-existing Windows long-path failures` | Professional Mode audit session |

## Completion Rules

An audit is complete only when the register contains:

```text
the exact Standard Mode baseline/commit range
the inspected changed paths
the classification and reasoning
the Professional Mode files/tests changed, or an explicit no-action result
the exact verification commands and results
any remaining blocker or compatibility dependency
```

The Professional Mode branch is never merged automatically. The mainline
maintainer separately audits and merges an `ADAPT_REQUIRED` change. A
`BLOCKED` result requires an architecture decision before implementation.

## One-Line Future Trigger

For routine use, the user only needs to send:

```text
请执行 Professional Mode 标准版影响审计：origin/main@<commit>，变更范围 <paths/commit range>。按 PROFESSIONAL_MODE_STANDARD_CHANGE_IMPACT_REVIEW_PROTOCOL.md 分类、登记，并在需要时适配锚点包；不要修改或合并 main。
```
