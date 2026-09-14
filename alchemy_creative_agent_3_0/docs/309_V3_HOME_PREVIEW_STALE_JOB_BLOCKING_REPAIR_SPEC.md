# Doc309 - V3 Home Preview Stale-Job Blocking Repair

Status: implementation in progress. This document records the correction
model for the VPS regression where V3 project cards remain on placeholders even
though output files and thumbnail endpoints are healthy.

## 1. Task record

### 1.1 User request

> 修好了吗？好了就传GitHub和VPS

The requested result is a repaired V3 project home, followed by GitHub push and
VPS deployment only after the fixed version passes local tests, read-only audit,
and governed VPS verification.

### 1.2 Objective and non-goals

Objective: make the authenticated V3 home preview return usable covers when a
project has a newer deliverable, without letting stale project jobs block the
whole page.

Non-goals: this repair does not change Brain or Provider behavior, generation/retry semantics,
review policy, ownership rules, media retention, project history semantics,
V2 behavior, or migrating existing VPS records.

Baseline: clean `main` at `8438e211` (`origin/main`).

Contract revision: `DOC309_V1_HOME_PREVIEW_STALE_JOB_BLOCKING`.

Complexity gate: `ESCALATE_REQUIRED`; the defect crosses Project Mode output
ordering and desktop/mobile request lifecycle, while the public delivery gate
must remain authoritative.

Unique writer: the current mainline integrator in
`D:\AI\Alchemy Media Agent System`.

Audit owner: a separate read-only audit phase in this task. No callable worker
Agent is exposed in the current environment, so no external Agent result is
claimed.

Context mode: `ARMED`; use precise reads and milestone checkpoints. No platform
supported compact/recovery hook has been verified for this task.

## 2. Observed mismatch and evidence

1. The VPS has durable V3 output records and valid thumbnail files. A direct
   authenticated thumbnail read succeeds for a known output.
2. The summary view intentionally returns an incomplete lightweight projection
   with empty thumbnail fields. The browser therefore depends on the separate
   `surface=home_preview` request to attach covers.
3. `project_200ef57976` returns a home preview, but
   `project_65432102a2` contains an old job whose authenticated job read takes
   longer than the bounded diagnostic window. Its newer job is review-ready.
4. The preview helper sorts candidate jobs newest-first, then passes them into
   `_project_output_items`, whose established project invariant iterates
   `project.job_ids` in reverse. The effective order becomes oldest-first, so a
   stale historical job can block the newer ready output.
5. The frontend home preview request has no timeout. One blocked batch request
   therefore prevents the preview response from reaching the cover-merging
   projection for every project on that page.

## 3. Correction model

### 3.1 Backend authority

`_project_output_items` retains its existing project-order invariant. The
delivery-preview helper must therefore pass its candidate job IDs in stored
chronological order, so the existing reverse iteration evaluates the newest
candidate first. This is an internal ordering correction only; the existing
delivery, review, owner, and selection predicates remain the authority.

The helper must continue to use the bounded project output index and return at
most one formal delivery preview per project. It must not reconcile projects,
scan unrelated projects, widen review-only output into home delivery, or add a
fallback media source.

### 3.2 Browser safety boundary

Desktop and mobile home-preview reads must have a bounded client wait. A
timeout or read failure may set the existing preview error state and preserve
the project catalog/cache, but must not clear usable project cards or render an
incomplete summary as an authoritative `0 张` result. Normal project detail
and full history requests keep their existing behavior.

The bound is 30 seconds. A cold VPS batch read was measured at about 19.3
seconds immediately after the V1 container restart, while warmed reads were
about 2.7 seconds. A 10-second bound therefore converted a recoverable cold
start into a false empty-preview state; 30 seconds remains finite while
covering the observed production cold-start envelope.

The timeout is a resilience boundary, not a delivery fallback: it must not
invent covers, bypass authentication, or replace the server delivery gate.

## 4. Allowed implementation surface

- this document;
- `alchemy_creative_agent_3_0/app/project_mode/service.py`;
- `src_skeleton/app/static/app.js`;
- `src_skeleton/app/mobile_static/mobile.js`;
- focused V3 regression tests and no generated media/log/cache artifacts.

No public API/schema, ownership, review, provider, Brain, or persistence
contract changes are authorized by this repair.

## 5. Acceptance matrix

| ID | Requirement | Evidence |
| --- | --- | --- |
| R1 | Preview candidates reach the existing delivery gate newest-first despite the project list reverse invariant | focused Project Mode regression |
| R2 | A stale older job cannot prevent a newer ready output from being selected | regression with a blocked/slow legacy candidate and a ready newer candidate |
| R3 | Review-withheld and owner-filtered outputs remain hidden | existing delivery/ownership tests plus focused regression |
| R4 | Desktop home preview has a bounded wait and keeps project/cache state on timeout | browser/source regression |
| R5 | Mobile home preview has the same bounded-wait behavior | browser/source regression |
| R6 | Existing summary/detail/full-history and scoped home-preview contracts remain intact | Doc308, progressive-loading, and adjacent V3 tests |
| R7 | JavaScript syntax, focused tests, diff hygiene, and final-version audit pass | command receipts bound to the final commit |
| R8 | The exact accepted commit is pushed to GitHub, deployed through the governed VPS release path, and read-only verified | Git/VPS receipts |

## 6. Delivery gate

Do not push or deploy while implementation, tests, or audit are incomplete.
After a clean fixed commit, run the local focused and adjacent regressions,
freeze the version, perform a read-only audit without editing, then push
`origin/main`, deploy that exact commit to the governed VPS release path, and
repeat read-only health and preview checks.
