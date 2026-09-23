# DOC323 — Known contract closure and minimality audit

## Correction model before implementation
Baseline: origin/main 6f2f059d; isolated worktree codex/v3-known-contract-closure.
Scope: close the four reproduced V3 failures without weakening certification,
input provenance, selected references, counts, transport deadlines or billing.

Confirmed runtime defect: product admission is initially bound to the transient
v3_job_instance_id. Product API later rebinds it to the final deterministic Job ID.
The frozen Brain correctly retains the first digest; generation correctly checks
against the final admission and rejects the mismatch. This is a lifecycle identity
ordering bug, not a visual defect or a reason to disable the digest check.

Minimal correction: make the existing pre-Brain Job-ID helper side-effect-free,
using the same current user/brand/scenario/metadata inputs and ScenarioRuntime's
existing ID function. Build admission against that final Job ID from the start.
Do not recompute/overwrite Brain receipts after sign-off, add migration guesses,
skip digest comparisons or create another admission/identity mechanism.

Tests must prove equal admission IDs/digests at planning and generation, one real
execution boundary in the fixture, and retained rejection for modified source,
count or budget. An ID lookup must not read files or rebuild creative context.

DOC290: inspect actual response schema and semantic watchdog policy first. Refresh
retired test expectations only when their intended invariant remains enforced.
Historical measurements remain historical; no production timeout/schema changes
are authorized merely to satisfy stale snapshots.

V2 cleanup belongs to its existing feature branch: remove only proven unreachable
private QR code, keep existing live behavior and all regression contracts.

## Expanded-suite finding before correction
The 53-file run found one additional stale DOC270/DOC280 test fixture: it declared
final_delivery_status=ready but omitted automatic_delivery_available. The current
Project gate correctly refuses certification without literal True. Confirm this
failure on unchanged main, repair only the positive fixture, and add missing /
False / string / numeric negatives. Do not relax the production gate.

DOC290 schema was captured through the real payload/stream adapters using offline
HTTP: current hash 7eef15ecc60258514b352223f12cc6b0f0014c7fb6a28ffd1242d531ca3c09f0.
Tests now also assert exact variation receipt fields and their frozen digest.
The old measured byte counts remain unchanged. The socket read window is capped
at the current 60-second semantic-progress window plus a 1-second allowance;
stage reserves, 520-second shared deadline, attempt counts and request fidelity
are still independently asserted. Production timeout code is unchanged.

## Verified feature result
Identity red tests: 4 failed / 3 passed on unchanged code; after correction,
the seven new tests plus the original locked-person failure all passed.
DOC290 full file: 65 passed. Production transport code was not edited.
Expanded V3 run: 53 files, 1176 passed, zero failed/skipped/deselected, 252.14s.
It includes all previously changed V3 tests and adjacent E-Commerce, identity,
source-binding, review, Project/home and desktop/mobile surfaces. It is not a
claim that all 262 V3 test files were executed. Three dependency deprecations
remain warnings, not suppressed failures.
Evidence: .controlled-validation/final-known-bug-closure-20260924/
`v3-all-affected-final.log`, `v3-all-affected-final.xml`, and the file manifest.

Production-code delta: one file, 10 added / 3 removed lines. No new identifier,
state machine, capability, provider call, retry, dependency, schema or threshold.
The existing ID helper is now pure and the admission calls it before Brain.
Integrity checks are unchanged. Corrections to historical test fixtures retain
structural/digest and strict-boolean negative assertions, not just new snapshots.

Local regression is complete for this scope. Mainline integration must be tested
again before publication. VPS verification and the five historical V2 original
images are not proven by these tests; a read-only SSH attempt was blocked by the
platform safety check, and no replacement transport or CI deployment was used.
