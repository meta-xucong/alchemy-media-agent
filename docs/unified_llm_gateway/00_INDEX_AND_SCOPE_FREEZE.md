# Unified Text LLM Gateway and Automatic Model Failover

Status: the user authorized committing/pushing the unified gateway implementation and syncing the VPS on 2026-10-18. Final source audit passed after the latest V1/LAB receipt fix; focused regressions passed. Doc06's real V3 image result is historical evidence for an earlier audited source snapshot, not acceptance of the current working tree. The VPS runtime was previously found to have empty unified gateway key/base settings, so code activation alone cannot make model routing live; the V1 and V2 runtime environments must both receive the one gateway credential through a controlled secret update before production acceptance.

## Objective

Configure V1, V2, V3, and LAB to use one unified text-model gateway credential,
with Claude Sonnet 5.5 as the preferred model, Kimi K3 as the first backup, and
GPT-6.1-sol as the following backup. When a candidate route is unavailable, automatically retry
the same frozen logical request through the backup model, within a bounded time
budget, and report which model actually answered.

This document set is the implementation authority for this task. Runtime
defaults and deployment samples must agree with it.

## User requirements

1. Keep the existing main/backup model selection presentation where present;
   remove per-backup-model API-key configuration and use one gateway API key.
2. Add model fallback to V3. Do not request a second key to call the alternate
   model.
3. Automatically advance to the next model on a classified route failure,
   including bounded connection/read/overall timeouts, subject to the V2
   Claude-continuation invariant below.
4. Use Claude Sonnet 5.5 as the preferred text model, followed by Kimi K3 and
   GPT-6.1-sol, in V1, V2, V3, and LAB. Details are in Doc07.
5. After design documentation and its independent audit, implement the frozen
   scope, obtain an independent code audit, then perform one real local V3 image
   generation for user acceptance.

## Frozen baseline and risk

- Main checkout: `D:\AI\Alchemy Media Agent System`
- Baseline commit: `501a625e0e09b73d49e0b4dfc711fc50444e4310`
- Initial working tree: clean on `main`; `origin/main` fetched and equal to
  `HEAD` (`0` ahead / `0` behind).
- Existing worktrees were inventoried and are out of scope; do not switch,
  edit, archive, or remove them.
- Design ambiguity: D0. Model order, single-key intent, four product scopes,
  and acceptance sequence are specified by the user and existing runtime
  contracts.
- Implementation: I2, because route selection, timeout recovery, and failure
  handling interact across four isolated backends.
- Audit: A2, because credentials, runtime settings, public configuration
  contracts, and external provider calls are affected.

## Scope

- Text planning / Brain / orchestration calls in `src_skeleton` (V1),
  `custom_media_agent_2_0` (V2), `alchemy_creative_agent_3_0` (V3), and LAB.
- Model defaults, provider protocol selection, one logical text gateway
  credential, ordered model failover, bounded timeout/recovery, safe provenance,
  configuration presentation, deployment examples, focused tests, and the
  required implementation/audit/real-output evidence.

## Non-goals

- Do not change image-generation model selection, image provider retry policy,
  image quality policy, template behavior, V1/V2/V3 product semantics, or
  image-provider credentials merely to implement text-model failover.
- Do not route around model safety refusals by asking a different model.
- Do not add deterministic creative fallback to a V3 path that requires a
  remote Brain decision.
- Do not bypass the guarded VPS candidate/activation workflow or modify other worktrees.
- Do not print, log, or copy gateway secret values into Git, workflow output, or documentation.
- Do not expose, log, or copy API-key values into documentation or evidence.

## Required phase order

1. Complete this document family and have a separate read-only agent audit it.
2. Implement only the audited contract in the mainline checkout.
3. Freeze the source diff and have a separate read-only agent audit code and
   focused test evidence.
4. Only after code audit PASS, run one local V3 real-image acceptance request.
5. Report the image and phase receipts for user acceptance. User acceptance is
   still required before claiming the total objective complete.

## Authority map

- This task's user requirements and this document family define the requested
  model order, one-key text-gateway contract, and failover behavior.
- Repository `AGENTS.md` defines mainline/worktree governance, theory-first
  correction, V2 isolation, fail-closed V3 Brain ownership, and local test
  sequencing.
- Existing product contracts remain authoritative for each backend's schemas,
  reasoning/checkpoint behavior, and image workflow. This change may select a
  different model implementation of the same contract; it may not weaken the
  contract.
- Scoped V2 precedence: the user's explicit requirement that all four
  products automatically fail over from unavailable Claude through Kimi K3
  and GPT supersedes
  only the V2 Claude-ownership rule that would otherwise prohibit a backup-model
  decision when no Claude checkpoint exists. V2 may use Kimi K3, then GPT, for
  the same frozen stage request/schema after a classified Claude route failure.
  When a Claude checkpoint exists, preserve it and continue from it; when
  Claude is merely slow or has returned a checkpoint, preserve the existing
  bounded continuation behavior. This exception does not permit deterministic
  creative fallback, weaken permission/refusal handling, or change V2's
  backend isolation.

## Document set

- [01 Unified Gateway and Failover Contract](01_UNIFIED_GATEWAY_AND_FAILOVER_CONTRACT.md)
- [02 Implementation Plan and File Map](02_IMPLEMENTATION_PLAN_AND_FILE_MAP.md)
- [03 Test and Acceptance Matrix](03_TEST_AND_ACCEPTANCE_MATRIX.md)
- [04 Design Audit Receipt](04_DESIGN_AUDIT_RECEIPT.md)
- [05 Implementation and Code Audit Receipt](05_IMPLEMENTATION_AND_CODE_AUDIT_RECEIPT.md)
- [06 Local V3 Real-Image Acceptance Receipt](06_LOCAL_V3_REAL_IMAGE_ACCEPTANCE_RECEIPT.md)
- [07 Kimi-First Backup Order Amendment](07_KIMI_FIRST_BACKUP_ORDER_AMENDMENT.md)
