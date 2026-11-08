# V3 historical optimization integration

## Objective and audit boundary

Following the Doc354 incident, the user requested an inventory of missing
historical optimizations and integration of the still-valid critical changes.
The total goal remains reliable V3 generation and visible results. This phase
audits and repairs omissions before one guarded deployment. V1/V2 performance
work remains deferred as previously requested.

The read-only inventory covered 24 registered worktrees and six local branches
not ancestral to origin/main. Other worktrees were preserved. A branch not
merged by ancestry may already have been squash-merged; a dirty worktree is not
proof of a missing feature. Current functions and product contracts, not branch
labels, determine which changes belong in the release.

## Findings and correction model before implementation

| Historical change | Decision and authority |
| --- | --- |
| Doc351 composition warning and review visibility | Integrated in `103e758e`; Doc354 records the incident and tests. |
| Doc350 canonical mixed-attempt final delivery | Still missing. Job-owned final IDs must beat attempt-based superseding. The current independent `elif` overwrites an earlier canonical winner. Make the branches mutually exclusive; leave certification and anchor authority intact. |
| Doc350 bounded ordered review scheduling | Still missing. Independent per-image review is serial. Use at most two workers, retain input order, and honor the inspector's process-wide limit including explicit limit 1. |
| Doc353 actual provider completion | Still missing. Outer join/queue deadlines can declare timeout while a daemon still owns a live call. Execute synchronously under the semaphore; release it only after the actual call returns or raises. |
| Doc353 remove every network timeout | Do not import. It is distinct from fixing detached workers and can leave both review slots occupied indefinitely. Preserve transport-owned timeout/error handling and model fallback. Existing continuation timeout fields still configure the transport. This narrows Doc353's historical draft. |
| Doc353 native identity operation ownership | Still missing. The eight-second timer abandons a live native operation. Invoke under the native lock until actual completion. Also protect first model initialization before introducing parallel review; do not persist biometric vectors. |
| Doc353 watchdog limited to GENERATING | Do not import unchanged. FINALIZING contains actual retry generation. The current overall generation budget includes that work; removing its watchdog would alter generation semantics. |
| Doc353 Body SDK timeout removal | Do not import. This path is already synchronous and does not have the detached-worker defect. |
| Doc352 fast review deadline | Explicitly superseded/rejected in the historical documents. Do not restore. |
| Best-attempt selection, per-image receipt reconstruction, formal certification, review-only anchor deduplication | Already equivalent in main and both historical review worktrees. Preserve them. |
| Default normalization, reference-input decision and Brain shape validation | Critical behavior already integrated; newer main also contains the profile-recovery diagnostics. Do not overwrite with older functions. |
| Hard Bridge-primary policy draft | Conflicts with the later accepted RB33 contract, which preserves explicit pre-admission API fallback. Do not silently change shared V1/V2/V3 routing while repairing review. |
| V2 Claude file/inline gateway helper and login intent draft | Inventory records these as separate V2-specific differences. They require their own caller/upstream contract acceptance; keep the user's V3-first order. |

The review and projection implementations in the two historical integration
worktrees agree. The original review worktree additionally clamps worker count
to 1–2; retain that bound. Neither worktree should replace current files wholesale.

## Layering and validation

Formal winner projection is Core. Review scheduling/wait ownership is shared
foundation infrastructure. Composition advice is Enhanced. None defines a
specialized image package or adds scenario logic to General Template.

Regression tests must first reproduce mixed-attempt winner loss, serial review,
abandoned provider/native work and unsafe first-load concurrency. Then verify
ordered bounded completion, transport timeout propagation, semaphore release on
errors and the existing review/certification behavior. Use deterministic local
fakes; do not create external jobs or replay the incident. Preserve all existing
outputs and review receipts. Guarded deployment and read-only production checks
follow the integrated tests; a phase pass is not total product acceptance.

Two parallel audit agents inspected lifecycle and projection history read-only;
the mainline agent remains the sole writer. Doc354 records the separate legacy
Fake Brain test-fixture limitation, which must not be mistaken for a runtime
review regression or hidden by weakening the Brain contract.

## Branch reconciliation evidence

| Non-ancestral branch | Current main disposition |
| --- | --- |
| `codex/legacy-review-receipt-recovery` | Patch-equivalent to `23ca89c3`. |
| `codex/local-history-bridge-recovery-20261101` | Patch-equivalent to `cd6f9a24`. |
| `codex/api-pull-relay-alchemy-20261029` | TLS/status work integrated by `c87b9ea0`; main additionally has later direct-run recovery and hash-free ACK contracts. |
| `codex/no-sha-bridge-artifacts-20261105` | Integrated through `5563e5fb`; audited publication/storage/HTTP/remote verifier files are equivalent. |
| `codex/no-image-sha-native-receipt` | Integrated through `f1eb73da`, `8bd11603` and later receipt/identity corrections. Reference facade and reference plan are equivalent; main's native adapter uses the newer identity matcher rather than whole-metadata equality. |
| `codex/veyra-auth-integration-20261019` | Still differs in V2 ticket-intent handling; separate upstream login contract work, not a V3 review repair. |

The old native-input pixel-limit draft is superseded by the current shared
`MAX_REFERENCE_INPUT_BYTES` / `MAX_REFERENCE_INPUT_PIXELS` limits. The duplicated
Bridge hard-primary worktrees contain the same policy draft discussed above.
Planning/reference worktrees without pending changes are ancestors of main.
The inventory does not delete, reset or mark those worktrees disposable.

## Focused verification before deployment

- New ownership regressions first reproduced seven failures (and one existing
  pass), then all eight passed after repair.
- 25 lifecycle/concurrency/transport/continuation checks passed, including those
  eight. Provider transport timeouts and no duplicate same-image request remain.
- 55 vision policy/provider checks passed; six identity checks passed.
- One isolated Project API regression passed with mixed-attempt certified
  winners, an earlier-round continuity anchor and non-winners in review history.
- 27 desktop/mobile review identity and terminal-state checks passed for the
  Doc354 changes. No live generation was used during this integration.

These results do not claim all legacy integration fixtures or real
visual-quality acceptance passed. This expanded audit supersedes Doc354's
initial narrow scope for the four additional proven historical defects above.

## Deployment outcome: blocked by VPS capacity

The runtime integration was committed and pushed as
`1ade93e5919f2001ec031640c3af0bbc67989fff`, including the earlier `103e758e`
visibility/composition repair. Read-only diagnostic commits `ca977ef2` and
`863c77e6` add cache inventory only; they do not change application behavior.

- Candidate build run `42470058448` succeeded. The exact unused `cb89ec1a`
  candidate image was retired through the existing protected-image helper;
  source worktrees and all stored data were preserved.
- Activation run `42470516243` stopped with
  `backup_consumed_data_reserve`. Its rollback was verified at
  2026-11-08 10:15:40 UTC. The newly created backup was preserved.
- Production is still `3744ed76658da3daf7776db292b1c8db9355306e`.
  The new candidate is not active. Existing service health is not evidence
  that the new review or frontend fixes are live.
- Read-only preflight run `42471724416` found 1,752,805,376 bytes free on
  the shared root/data/backup filesystem. The cutover estimate requires
  1,909,051,926 bytes for data-side headroom after backup creation, with an
  additional estimated 346,876,527 bytes for the next backup. Capacity must
  be checked again before any further activation.
- The active, rollback and prepared application images are all protected.
  Two old Bridge images have only about 80 MB of unique layers combined;
  pip and apt download caches total 247,979,421 bytes. Even reclaiming all
  of those would not satisfy the estimated cutover capacity. None was
  deleted during this diagnosis. Docker's aggregate reclaimable number
  includes protected images and is not authorization to prune them.

The next required phase is sufficient verified VPS capacity, then guarded
activation of the integrated release and read-only checks of the existing
incident's canonical review images and served frontend. Do not lower the
reserve, delete images/history/backups, or remove rollback environments to
force a pass. No new generation or review replay has been performed, and
production acceptance remains incomplete.

## Resumed deployment: correction model for capacity

The user renewed the instruction to audit, test, synchronize and deploy. The
capacity layer owns the remaining mismatch: the protected cutover needs a new
backup plus data headroom, while fourteen release directories retain separate
generated V2 dependency environments of about 385 MB each. Lowering the reserve
or removing user history is not a correction. Read-only run `42474397439`
confirmed those environments and their release-bound runtime manifests.

Use a bounded, recoverable archive operation for explicitly selected inactive
historical dependency environments only. Keep source checkouts, configuration,
runtime manifests, media, databases and every existing backup. Protect all
releases with a retained application image, including active/rollback/candidate,
and reject container, systemd or live-process references. Hold the existing
release lock. Default to read-only inspection. Before removing an uncompressed
environment, preserve it as a sibling archive and verify its complete member
inventory, metadata, link targets and file bytes directly without hashes.
Stop once deployment headroom is available. A matching archive restores the
environment at its original path; old releases require restoration before use.

Regression tests must cover protected/referenced selections, source/manifest
identity, linked paths, complete archive verification and recovery. Then inspect
the exact production selection read-only before applying. This replaces the
previous phase's decision not to touch old runtimes with a scoped reversible
operation supported by new evidence and the renewed deployment instruction.

The archive helper's 13 focused checks passed, including complete file recovery,
same-size content corruption, links, process/container/systemd references and
retained release protection. The 24 existing cutover checks passed. The resumed
V3 check set also passed: nine review ownership/mixed-winner checks, thirteen
composition policy cases and sixteen desktop/mobile review projection checks.
Read-only preview `42475218535` verified the exact five selected runtimes and
healthy running services. No provider generation or review replay was used.

For recovery of an archived old release, extract `.venv.inactive.tar.gz` in that
release's `custom_media_agent_2_0` directory only after confirming `.venv` is
absent. Preserve the archive outside the source checkout after successful
restoration: the existing source-clean gate correctly rejects the untracked
archive in a release being activated. Run the normal V2 runtime guard and
candidate/activation checks; extraction alone does not authorize old release
activation. The current active and rollback environments are never archived.
