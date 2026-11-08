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

Deployment and read-only verification of the existing incident remain the next
phase. These results do not claim all legacy integration fixtures or real
visual-quality acceptance passed.
