# Professional Mode Implementation Status And M5 Handoff

## Status

```text
M0-M4 IMPLEMENTED ON ISOLATED FEATURE BRANCH
M2 SERIAL THREE-VIEW CANDIDATE CONTRACT IMPLEMENTED
M5 REAL-PIXEL ACCEPTANCE BLOCKED BY EXTERNAL EVIDENCE
NO PRODUCTION CLAIM
STANDARD MODE UNCHANGED
```

This is an implementation status and handoff record for the unnumbered
Professional Mode document set. It does not alter the existing numbered V3
contracts and does not authorize a mainline merge or production activation.

## Implemented scope

The feature branch contains the following additive, isolated seams:

```text
M0  strict Professional/Standard contracts and red tests
M1  project-scoped People Asset catalog and append-only lifecycle
M2  bounded Face Identity anchor-pack preparation: three front candidates,
    then three three-quarter candidates from root+front winner, then three
    profile candidates from root+front+three-quarter winner
M3  frozen-plan binding and canonical-prompt/hash bridge
M4  General/E-Commerce/Photography consumer isolation seam
```

The first release remains Face Identity only. The module contributes typed
identity evidence and provenance; it does not own prompt prose, provider
transport, review, retry, storage, or final delivery. Standard Mode has no
People Asset lookup or Professional Mode metadata. No Web route, Provider
configuration, UI path, or production switch was changed by this branch.

## M5 evidence boundary

M5 requires real pixels from the existing authorized GPT Image 2 Provider,
shared review evidence, bounded retry/final-winner evidence, and a human visual
acceptance across the front, three-quarter, and profile views. Those artifacts
are not available in this isolated implementation run, and no credential or
external Provider call was attempted.

Therefore M5 is **blocked**, not passed. Mock contracts, lifecycle tests, and
source-boundary tests prove the shape of the implementation only; they cannot
certify identity quality, Provider Gate status, Gate C/D, P10, or production
readiness. There is no production claim for Professional Mode or for the Face
Identity anchor pack. The typed generation request now rejects any missing,
duplicated, reordered, or extra evidence in the serial root/front/three-quarter
chain before a candidate can be generated.

## Verification

The focused Professional Mode suite covers M0-M5 boundaries and must be run
from this worktree; the current M0-M5 run is 39 passed. A full repository run
currently reaches the existing product-API persistence tests but four of those
tests fail before assertions because the Windows worktree path exceeds the OS
path limit (`WinError 206`); the latest full run is 812 passed with those four
environmental failures.
That environmental failure is unrelated to `app/visual_assets` and is recorded
as an integration-environment issue rather than silently omitted.

The mainline maintainer should independently rerun the full suite from a
shorter checkout path after merge, then perform the real-pixel acceptance with
authorized Provider evidence. Until that evidence passes, the Professional
Mode branch must remain non-production.

## Integration handoff

Mainline audit should verify:

1. only the new `app/visual_assets` contracts/catalog/orchestration/bridge and
   their focused tests are integrated;
2. Standard, General, E-Commerce, Photography, and shared Provider/review
   semantics remain unchanged;
3. the active mode is explicit and no Professional-to-Standard fallback exists;
4. M5 is scheduled as a separately evidenced real-pixel acceptance, not
   inferred from this branch's tests.

The previous supervisor attempt was also unable to start its local Codex worker
because the desktop tool host executable was unavailable. Manual milestone
work continued successfully; this operational issue is not evidence of a
Provider or visual-quality pass.

