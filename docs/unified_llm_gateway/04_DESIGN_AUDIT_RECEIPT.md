# Design Audit Receipt

Status: DESIGN-V1 FAIL; DESIGN-V2 FAIL; DESIGN-V3 FAIL; DESIGN-V4 PASS; DESIGN-V5 PASS.

## Frozen target

- Baseline commit: `6672d36a978848c048b3a2bae00b7cecba6e906c`
- Frozen document set: `00_INDEX_AND_SCOPE_FREEZE.md`,
  `01_UNIFIED_GATEWAY_AND_FAILOVER_CONTRACT.md`,
  `02_IMPLEMENTATION_PLAN_AND_FILE_MAP.md`,
  `03_TEST_AND_ACCEPTANCE_MATRIX.md`
- Frozen design document-set SHA256: `3a7d064d3b69710abfe21475c1dd73a548c4ed3a9367543a9028af1a0d44e062`
- Frozen design target revision: `design-v1`.
- Auditor: `/root/design_audit` (independent read-only child; terminal result received).
- Auditor requested route: `gpt-6-luna/max`; observed runtime route: `ROUTE_UNVERIFIED`.
- Result: `FAIL`.

## Required review scope

Check the user requirements, single-key handling, default model/effort
contract, protocol mapping, error categories, timeout/circuit-breaker bounds,
V2 strict isolation, V3 fail-closed Brain semantics, local real-generation
gates, non-goals, and phase sequencing. Return exactly `PASS`, `FAIL`, or
`INSUFFICIENT_EVIDENCE` with concrete evidence. The author must not write the
auditor's findings or self-approve.

## Findings

1. Doc01 §4: the V3 180s-per-candidate wording did not fit the existing
   520s execution budget, 220s finalizer reserve, and transport grace.
2. Doc01 §5: 403 classification did not distinguish shared-key failure from
   candidate-specific model access denial.
3. Doc01 §6 / Doc03: required circuit-breaker behavior was not tested for all
   four isolated products.

Correction: design-v2 retains the existing V3 logical deadline and 220s
handoff reserve, dynamically partitions each stage window among remaining
candidates, classifies structured 403s, and makes the circuit breaker optional
and outside this implementation's acceptance scope. The corrected frozen
design requires a fresh independent audit before implementation.

## Design-v2 review

- Frozen design document-set SHA256:
  `3a3b75e38a97e6da874b1bc98c7717d12b320c8042465f584f78e84ca5ccfa76`
- Frozen design target revision: `design-v2`.
- Auditor child identity and terminal state: `/root/design_audit_v2`, completed.
- Result: `FAIL`.
- Findings: GPT fallback at the V2 initial stage was disallowed despite the
  user's four-product failover request; schema-repair budget accounting and
  its reserve test were underspecified; the aggregate hash convention was not
  defined.

## Design-v3 review

- Auditor: `/root/design_audit_v2`, completed, read-only.
- Result: `FAIL`.
- Findings: V2 initial-stage GPT fallback conflicted with the four-product
  failover requirement; V3 repair-budget and hash concerns from v2 were
  resolved.
- Correction: design-v4 records a narrow user-directed V2 precedence exception
  for classified route failure, while preserving available checkpoints,
  continuation, safety boundaries, and prohibition on deterministic creative
  fallback.

## Design-v4 review

- Frozen design document-set hash convention: SHA256 over the UTF-8 bytes of
  the four files' raw contents concatenated in numeric order (00, 01, 02, 03),
  with no inserted separators. Per-file SHA256 values are also recorded below
  so the frozen revision can be independently reproduced.
- Frozen design document-set SHA256:
  `56b4adaccbf8c9304c00118a6a29fc01191da64c8dcb940e0d446f29e8b7cb40`
- Per-file SHA256:
  - `00_INDEX_AND_SCOPE_FREEZE.md`: `746ef687d8f604f4d155b9dce285c803f797fa43d622354ad051403bc71a21e5`
  - `01_UNIFIED_GATEWAY_AND_FAILOVER_CONTRACT.md`: `5283de79b482935be94b529cbc0f530726be132ecb9f426ab53c8db5fba9da53`
  - `02_IMPLEMENTATION_PLAN_AND_FILE_MAP.md`: `e0abb42b522b6790e605fa17c1ebfbb7504c58aed5bd90a6fc68de30d2236a02`
  - `03_TEST_AND_ACCEPTANCE_MATRIX.md`: `60b84c2d31f725f1820f037a1f62f7fed4af909276d78d69410c30699fb111c4`
- Frozen design target revision: `design-v4`.
- Auditor child identity and terminal state: `/root/design_audit_v2`, completed.
- Requested route: `gpt-6-luna/max`; observed runtime route: `ROUTE_UNVERIFIED`.
- Result: `PASS`.
- Findings: none blocking. Auditor independently recomputed the aggregate and
  all four per-file hashes and confirmed the V2 precedence exception, V3
  shared-budget accounting, failure classification, and acceptance sequence.

## Design-v5 review

- Correction: implementation file map now names the V1 desktop/mobile settings
  surfaces and runtime API/schema that must present one text gateway key while
  preserving separate image-provider keys. Doc03 adds the matching UI
  regression acceptance.
- Frozen design target revision: `design-v5`.
- Frozen design document-set SHA256: `361051d5eeb87ea30f2e101e36fae8c9f9355eb7ffbe732357cc34be827c1f94`.
- Per-file SHA256:
  - `00_INDEX_AND_SCOPE_FREEZE.md`: `746ef687d8f604f4d155b9dce285c803f797fa43d622354ad051403bc71a21e5`
  - `01_UNIFIED_GATEWAY_AND_FAILOVER_CONTRACT.md`: `5283de79b482935be94b529cbc0f530726be132ecb9f426ab53c8db5fba9da53`
  - `02_IMPLEMENTATION_PLAN_AND_FILE_MAP.md`: `db7d334cadd33778abdf9da6856351e5fc7b05cc93a6dd4a61aa476491b1e48d`
  - `03_TEST_AND_ACCEPTANCE_MATRIX.md`: `00602a4ef7eb9b0cede13292a0d3fda4f41d4c38f7bcea7c2afd5ab06d1bed72`
- Auditor child identity and terminal state: `/root/design_audit_v2`, completed.
- Requested route: `gpt-6-luna/max`; observed runtime route: `ROUTE_UNVERIFIED`.
- Result: `PASS`.
- Findings: none blocking. Auditor confirmed the expanded settings UI map and
  separately recomputed aggregate and per-file hashes.

## Design-v6 review

- Correction: V2 soft timeout is an internal Claude continuation boundary.
  Compressed/micro Claude continuation runs within the bounded budget before
  GPT fallback is allowed. V3 refuses cross-model retry while the prior
  transport worker has not stopped.
- Frozen design target revision: `design-v6`.
- Frozen design document-set SHA256 (raw UTF-8 contents concatenated in
  numeric order 00–03, no separators):
  `a3b2f5fa009cd4e7d7c5f9a167785daf19d559aea7cc8ba50f323b7fa0d7ce04`.
- Per-file SHA256:
  - `00_INDEX_AND_SCOPE_FREEZE.md`: `746ef687d8f604f4d155b9dce285c803f797fa43d622354ad051403bc71a21e5`
  - `01_UNIFIED_GATEWAY_AND_FAILOVER_CONTRACT.md`: `351bba65ecb9238ade5cc3c1876f1de17af75e7f630cebea76952f94db0ddb95`
  - `02_IMPLEMENTATION_PLAN_AND_FILE_MAP.md`: `debee22f23b253000bb3cdd516e7ed2ab4bd87e8bf7f3d15350fb450aac49f48`
  - `03_TEST_AND_ACCEPTANCE_MATRIX.md`: `24bdea50917e592e1ba4a7b6ec9dae53518a2c9c0691f2f80fb013bd26434089`
- Auditor: `/root/design_audit_v2`, completed, independent read-only review.
- Result: `PASS`.
- Evidence: auditor independently recomputed the aggregate hash and verified
  V2 continuation precedence, V3 worker-stop gating, protocol mapping,
  refusal/401/403 handling, and the focused validation set. The required
  shared key for separately running V2/V3 services remains a deployment
  environment injection prerequisite; cross-process dynamic synchronization
  is outside this scope.
- Focused validation reported by the auditor: V1/LAB 14 passed; V2 failover
  and model selection 11 passed; V2 soft-timeout continuation 2 passed; V3
  routing, budget, refusal, and scoped-403 set 11 passed; `git diff --check`
  passed with line-ending warnings only.

## Design-v7 review

- Correction: V1/LAB same-candidate schema repair and recovery explicitly
  share the original absolute 90-second candidate deadline. The acceptance
  matrix covers both V1 and LAB and verifies the backup retains its allotted
  remainder of the 210-second logical budget.
- Frozen design target revision: `design-v7`.
- Frozen design document-set SHA256 (raw UTF-8 contents concatenated in
  numeric order 00–03, no separators):
  `fcf37568fbc78050bd4e02e504c6fbf9b60a26eb45425180e1f0cc3895631f90`.
- Per-file SHA256:
  - `00_INDEX_AND_SCOPE_FREEZE.md`: `0e8ea128b7b3ed32a3e382b6d53663062af545d46dd796565ffe38fd4d65bcbf`
  - `01_UNIFIED_GATEWAY_AND_FAILOVER_CONTRACT.md`: `c9966f53cfce2626c4dadc9c27c928c64325e4aa4a473e5dc0bf7734e21d4c2d`
  - `02_IMPLEMENTATION_PLAN_AND_FILE_MAP.md`: `5f07ed395ecc91c5499a95ace98f2ac9d4ad4c17276d427d6c218d41660e858c`
  - `03_TEST_AND_ACCEPTANCE_MATRIX.md`: `f774f6a28c4eb96abd5eb0f689a33f6a7f5241d3280e037af80114eed77aee36`
- Auditor: `/root/design_audit`, independent read-only review.
- Result: `PASS`; no blocking design findings remain.
