# Doc349 — V3 Shared Capability Failure Diagnostic Capture

Status: temporary diagnostic release contract; not a root-cause repair.

## Objective

Capture enough private evidence from the next shared-capability executor
failure to locate its final Python traceback frame while preserving the
existing fail-closed Human Realism execution guard.

## Evidence and authority

The VPS failure `job_c3811e5d90` identifies
`visual_capability_cluster` as the failed executor, but its persisted receipt
has no exception type or source frame. The same prompt passed in the available
local run and a bounded context simulation, so the underlying exception is not
yet reproducible from retained evidence. No source-level correction is
justified until a failing frame is captured.

The frozen activation plan remains authoritative. A required Human Realism
execution must continue to block when its shared executor fails. This change
only extends the existing private failure receipt with an allowlisted
exception type and a sanitized final traceback frame (source basename, line,
and function). Raw exception text, prompt, provider payload, and filesystem
path are not persisted. No retry, fallback generation, prompt, routing, or
provider behavior changes.

## Files and acceptance

The temporary release is limited to:

- `app/shared_capabilities/base.py`
- `app/scenario_runtime/runtime.py`
- `tests/test_v3_shared_capability_runtime_integration.py`
- this document

Acceptance requires the focused synthetic exception and private-receipt tests,
the existing fail-closed guard test, `git diff --check`, and an independent
read-only audit of the exact frozen diff. Once a real failure provides its
source frame, diagnose and repair that specific cause before claiming the
generation issue resolved. Do not start a real image-generation job to collect
this evidence as part of this temporary deployment.

The separately requested project-output removal UI correction is excluded
from this diagnostic release and remains local for its own acceptance.
