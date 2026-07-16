# Professional Mode Implementation Status And M5 Handoff

## Status

```text
M0-M4 IMPLEMENTED AND MAINLINE BACKEND SEAM INTEGRATED
M2 SERIAL THREE-VIEW CANDIDATE CONTRACT IMPLEMENTED
M6 ASSET-CHANNEL AUTHORITY/ADMISSION CONTRACT IMPLEMENTED
PRODUCT API / SCENARIO RUNTIME PROFESSIONAL MODE WIRING COMPLETE
M5 REAL-PIXEL ACCEPTANCE BLOCKED BY EXTERNAL EVIDENCE
NO PRODUCTION CLAIM
STANDARD MODE UNCHANGED
```

This is an implementation status and handoff record for the unnumbered
Professional Mode document set. It does not alter the existing numbered V3
contracts or authorize production activation. The backend integration status
and merge result are determined by the mainline commit and verification record.

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
M6  asset-channel authority, reference admission, and Provider/Reviewer
    evidence-parity contracts plus a framework-agnostic pre-runtime execution
    adapter; frontend intentionally deferred
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

The asset-authority backend contracts are now wired into the mainline Product
API and ScenarioRuntime seam. An explicit `professional_mode=professional`
request resolves the project-scoped People Asset binding, performs typed
reference admission before Brain execution, exposes only the safe binding and
admission evidence to the Remote Brain, and then continues through the shared
CapabilityActivationPlan, canonical prompt, Provider, review, retry, and final
delivery path. A missing or unsafe binding produces a structured blocked
result; it cannot become a Standard/General result. The frontend remains
intentionally deferred until this backend boundary and its M5 evidence are
accepted.

## Usability audit boundary

The current backend seam is contract-usable for an explicit Product API caller
that supplies `professional_mode=professional` and a project-scoped
`people_asset_id`. The service resolves the active People Asset and anchor
pack, chooses or validates the bounded view set, and stores the binding as
server-owned metadata. ScenarioRuntime then uses the same runtime job ID for
the binding, Brain task profile, frozen plan, and downstream provenance. The
typed pre-runtime adapter returns either a safe evidence context or a
structured blocked decision; the shared runtime remains the only generation,
review, retry, and delivery path.

This is a backend integration seam, not a production-ready user experience:
the browser does not yet expose Professional Mode, and no real Provider/M5
evidence has been captured. The public mode must remain explicit, and a
missing asset, invalid view binding, unsafe reference admission, unavailable
enforced planning, or canonical-evidence mismatch must remain blocked rather
than falling back to Standard/General.

This is an intentional next integration milestone, not a silent fallback. The
integration must remain additive and must preserve Standard Mode, existing
scenario semantics, Remote Brain ownership, shared Provider/review/retry, and
fail-closed behavior before any frontend work begins.

## Verification

The focused Professional Mode suite covers M0-M6 boundaries and the mainline
Product API/ScenarioRuntime seam. The current integration run includes 64
focused Professional Mode tests and 80 tests across the affected runtime,
activation, Project Mode, and Doc102 checkpoint suites. A short-checkout full
run is the authoritative regression environment; the earlier isolated feature
worktree run reported 861 passed, with four unrelated Windows `WinError 206`
path-limit failures that disappear in the short checkout. These tests prove
the backend contract and isolation only; they do not certify real pixels,
Provider quality, M5, Gate C/D, or production readiness.

The mainline maintainer should independently rerun the full suite from a
shorter checkout path after merge, then perform the real-pixel acceptance with
authorized Provider evidence. Until that evidence passes, the Professional
Mode branch must remain non-production.

## Integration handoff

The mainline integration audit must verify:

1. the Product API resolves only project-scoped active People Assets and never
   trusts client-supplied binding records;
2. the same runtime job ID and typed evidence remain bound from admission
   through Brain, frozen plan, Provider, review, retry, and provenance;
3. Standard, General, E-Commerce, Photography, and shared Provider/review
   semantics remain unchanged;
4. the active mode is explicit and no Professional-to-Standard fallback exists;
5. M5 is scheduled as a separately evidenced real-pixel acceptance, not
   inferred from this branch's tests.

The previous supervisor attempt was also unable to start its local Codex worker
because the desktop tool host executable was unavailable. Manual milestone
work continued successfully; this operational issue is not evidence of a
Provider or visual-quality pass.

