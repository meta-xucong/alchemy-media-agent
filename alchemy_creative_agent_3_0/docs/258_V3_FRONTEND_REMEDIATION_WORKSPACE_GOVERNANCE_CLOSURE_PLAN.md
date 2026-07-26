# Doc258 — V3 Frontend Remediation Workspace Governance Closure Plan

Status: documentation-only governance closure plan; no production code is
authorized by this document.

Owner layer: workspace governance / Git hygiene / remediation staging boundary.

Related frontend plan:

- `docs/visual_assets/PROFESSIONAL_MODE_V3_UI_CARD_AND_MOBILE_REMEDIATION_20260726.md`

This document exists because the frontend remediation itself is correct in
direction, but the current mainline workspace contains unrelated working-tree
signals that must be closed before any frontend implementation, staging, commit,
or browser acceptance work continues.

## 1. Problem statement

The current V3 frontend remediation is intended to be frontend-only:

- desktop/mobile asset-card UI;
- cache-bust versions;
- mobile route ownership;
- frontend public error sanitization;
- browser smoke tests.

Reviewer audit found two workspace governance risks:

1. `alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/module.py`
   appears as modified in the working tree.
2. `.controlled-validation/` is an untracked evidence directory.

Neither belongs in a Professional UI remediation commit. The risk is not that
either item is currently wrong; the risk is that they could be accidentally
staged, committed, or treated as part of the frontend change.

## 2. Current evidence classification

### 2.1 `shared_capabilities/visual_cluster/module.py`

Current read-only checks show no substantive diff:

- `git diff --name-only` does not list the file as an actual content diff.
- `git diff --numstat -- <file>` reports no changed line counts.
- `git diff --ignore-space-at-eol -- <file>` reports no content.
- Git warns that LF may be replaced by CRLF when touched.

Classification:

```text
workspace/index line-ending signal; not part of frontend remediation.
```

Required handling:

- Do not stage this file in the frontend remediation.
- Do not rewrite, normalize, or reset it as part of this task.
- If a future check reveals real content changes, stop and classify them as a
  separate shared Visual Capability task. Do not hide them inside frontend work.

### 2.2 `.controlled-validation/`

`.controlled-validation/` is append-only validation evidence, logs, reports, and
scratch artifacts.

Classification:

```text
evidence/scratch directory; preserved but never part of source commits.
```

Required handling:

- Do not stage or commit `.controlled-validation/`.
- Do not delete or clean it merely to make `git status` look clean.
- If a specific evidence manifest is needed for audit, write it as evidence
  under `.controlled-validation/`, not as source.
- Frontend commits must remain source/test/docs only.

## 3. Governance objective

Before frontend implementation resumes, prove that the workspace is safe for a
frontend-only patch:

1. The main checkout remains the unique `main` workspace.
2. `HEAD == origin/main` before new code work begins, unless the only local
   difference is explicitly documented and reviewer-approved.
3. All unrelated dirty signals are classified.
4. Staging rules are explicit.
5. The reviewer can inspect the exact source files that may enter the next
   commit.

## 4. Allowed and forbidden scopes

### Allowed before reviewer approval

- This Doc258 governance document.
- Read-only Git status/diff/classification commands.
- Longrun state/progress/test-log/blocker notes that record governance status.
- Reviewer notification / handoff.

### Forbidden before reviewer approval

- Frontend implementation changes.
- Browser smoke that depends on new unreviewed code.
- Staging or committing frontend files.
- Staging `shared_capabilities/visual_cluster/module.py`.
- Staging `.controlled-validation/`.
- Any backend route, Provider/MCP/Brain, generation, Formal Core, receipt, slot,
  activation, storage, or shared Visual Capability change.
- Destructive cleanup such as reset, clean, checkout-overwrite, or deleting
  evidence.

## 5. Reviewer gate

Frontend implementation may start only after the reviewer confirms this
governance model is acceptable.

Reviewer decision outcomes:

### Approved

If approved, the next instruction may authorize frontend-only implementation:

- update cache-bust versions;
- remove or document/test mobile route forcing;
- add public error sanitization;
- align status semantics;
- add narrow browser smoke and focused frontend tests.

The implementation must still exclude `module.py` and `.controlled-validation/`
from staging.

### Needs more documentation

If the reviewer finds the governance model incomplete, the next instruction
should request Doc258 refinement only. No frontend code should be changed.

### Blocked

If a real content diff is found in `module.py` or any unrelated file, stop the
frontend remediation and create a separate owning-layer task. The frontend
patch cannot proceed until the unrelated diff is classified and either preserved
outside the commit or separately resolved.

## 6. Staging and commit guard

When the frontend implementation is eventually authorized, the staging guard is:

```text
git diff --name-only
git diff --cached --name-only
```

Expected frontend implementation commit scope should be limited to files such
as:

- `src_skeleton/app/static/index.html`
- `src_skeleton/app/static/app.js`
- `src_skeleton/app/static/styles.css`
- `src_skeleton/app/mobile_static/mobile.html`
- `src_skeleton/app/mobile_static/mobile.js`
- `src_skeleton/app/mobile_static/mobile.css`
- focused frontend tests
- explicitly approved remediation docs

Explicitly excluded:

- `alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/module.py`
- `.controlled-validation/`
- `.media_storage/`
- generated images, screenshots, logs, caches, pycache, evidence roots
- backend generation, route, review, slot, receipt, Provider/MCP/Brain files

If `git diff --cached --name-only` contains an excluded path, abort commit and
unstage only that path. Do not rewrite the file unless separately authorized.

## 7. Minimal verification for this governance phase

This document phase is considered complete when:

1. Doc258 exists and describes the governance risks and handling rules.
2. A read-only diff confirms `module.py` has no substantive content diff or
   classifies any discovered diff as out of scope.
3. `.controlled-validation/` remains untracked and unstaged.
4. No frontend or backend production code is changed by the governance phase.
5. The reviewer is notified and can decide whether to approve implementation or
   request another documentation iteration.

No browser smoke, frontend tests, backend tests, or generation runs are required
for this documentation-only governance phase.

## 8. Rollback

Doc258 can be reverted independently. It does not change runtime behavior,
catalogs, receipts, evidence, UI assets, generation outputs, or public
projection.

If the reviewer rejects the model, update this document rather than changing
code.

## 9. Short form

```text
Close workspace hygiene before frontend work.
Do not stage shared visual module noise.
Do not stage controlled-validation evidence.
Only after reviewer approval may frontend-only remediation continue.
```
