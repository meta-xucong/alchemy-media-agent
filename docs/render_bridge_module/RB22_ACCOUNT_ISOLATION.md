# RB22 V2 account isolation correction

## Correction model

VPS account authentication is not job authorization. The image-job detail route
previously accepted every authenticated account, exposing a different owner's
prompt and metadata. Resume/cancel already checked the frozen request owner.

Persist the authenticated request owner on every new ImageJob (including running,
failed and mock jobs), independently of result existence. Resolve one consistent
owner from the job, its frozen Bridge request and legacy output metadata. Conflicts,
malformed owners and unresolved legacy owners return the same 404 as a missing job
when authentication is enabled. Never derive ownership from caller-supplied IDs.
Local authentication-disabled operation is unchanged. Existing legacy jobs with
a consistent frozen/output owner remain accessible to that owner. Unowned legacy
jobs need an explicit administrative migration, not implicit public access.

Ordinary detail/resume/cancel routes do not grant an admin impersonation bypass.
Existing dedicated output/history administration and download permissions are
unchanged. Bridge service tokens and Codex credentials are not user sessions.

## Verification boundary

Offline tests cover signed sessions/access headers, two-account isolation, missing
and conflicting legacy provenance, authenticated request override, persistence,
and existing Bridge billing/recovery cases. No real SSO, provider or debit is used.
VPS acceptance still requires real accounts, account expiry/revocation policy,
and server-side idempotent billing verification.

## Offline evidence, 2026-10-25

- Account isolation + Veyra auth + Bridge primary, final focused run: 100 passed.
- Expanded API/contract/durable queue/claim selection before the final malformed
  identity guard cases: 329 passed. The selections overlap; do not sum them.
- The auth suite now restores every directly mutated frozen setting on teardown;
  auth-before-Bridge runs in one process without contaminating provider defaults.
- Strict owner stamping covers running, failed, completed, mock results and the
  queue's insufficient-balance job. Existing SQLite JSON storage needs no schema
  migration; older records decode with owner=None and use the documented fallback.
