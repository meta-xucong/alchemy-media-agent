# Professional Mode M5 Real Binding Preflight — Blocked

Date: 2026-07-18
Baseline: `origin/main@c6ebbf0`
Branch: `codex/professional-m5-three-view-acceptance`
Status: **non-counting preflight; M5 remains blocked**

## Scope

This record documents the real-pixel M5 preflight after the structural
Professional Mode fixes were integrated into `main`. It does not change the
Standard Mode path, open a browser entry, enable a production gate, or add a
Provider/reviewer/retry/storage implementation.

## Findings

The supplied portrait source is present and readable in the local evidence
workspace, but no server-owned active People Asset / Face Identity anchor pack
was available to the shared Professional runtime.

The audit checked the configured worktree and the previously used external
V3 storage workspace for the metadata-only catalog records expected by the
existing resolver (`people_assets.json`, `identity_anchor_packs.json`, and
their append-only history). No such project catalog records were present.
The Product API default catalog is therefore empty, and the standalone MCP
process has no host-injected persistent resolver. The correct result is the
existing fail-closed binding error, not a synthetic asset or a Standard-mode
fallback.

The V3 environment has a configured default GPT Image 2-compatible provider
setting, but provider availability cannot compensate for the missing
server-owned binding. No API key value, auth/session material, or secret was
read into this record.

## What was not run

Because the binding gate is before Provider materialization, this attempt
produced no new counted pixels and did not claim any of the following:

- front, three-quarter, or profile candidate batches;
- shared Vision review, bounded retry, or final-winner selection;
- 2/3/5 reference-budget or renderer-parity evidence for a real job;
- anchor-pack activation or persistent People Asset publication;
- M5, Gate C/D, P10, or production availability.

The earlier front and three-quarter comparison artifacts remain historical,
non-counting evidence; they cannot be promoted to this run without the
server-owned binding and a fresh shared-runtime execution.

## Required next step

Create or restore a real project-scoped People Asset with an active,
user-confirmed Face Identity pack through the existing catalog lifecycle, then
configure the embedding host to resolve that catalog for the M5 process. The
next run must use that binding and execute, in order:

```text
front (3 candidates) → shared Vision/retry → winner
three-quarter (root + front winner; 3 candidates) → shared Vision/retry → winner
profile (root + front winner + three-quarter winner; 3 candidates)
```

Only after all three stages have verified shared-review winners, exact 2/3/5
reference provenance, renderer parity, append-only lineage, and human visual
comparison may M5 be reconsidered. Production gates remain closed.

## Contract verification

Focused Professional catalog, anchor-pack, mainline-binding, boundary, and
reference-budget tests passed (`33 passed`). No source/runtime change was
needed for this preflight; the record is an audit handoff rather than a
certification result.
