# RB01 preview verification and correction models

## Cancellation between preparation and submit

Intended: cancellation before the remote create operation prevents generation.
Observed by focused review: cancellation during awaited capability/input work was
persisted, but the code proceeded from preparation to POST /tasks without checking
the durable flag again. Authority is the module task's persisted cancellation,
not the worker's older local snapshot. The minimal repair is to re-read that
record and current project scope/revision immediately before remote create; a
cancelled prepared task is terminal locally and does not POST. Add a deterministic
blocked-capabilities regression, then test the focused suite. This does not alter
native generation cancellation or remote dispatch authority.

## Existing-session frontend compatibility

Code inspection found the old Alchemy UI uses an existing bearer session in
`alchemy_veyra_access_token` as well as cookies. The preview UI must read that same
session rather than invent login. JSON and image reads now use same-origin
Bearer/cookie requests; image previews use temporary blob URLs and clear them on
project change, failed authorization, cancellation refresh, page exit or session
change. No new credential storage or API-key scope is introduced.

## Read-only project picker

The host's default full project-list view can reconcile job/output state.
The optional picker therefore requests the existing `view=summary` projection,
which uses lightweight summaries without native job/output/context reads.
Opening the test module must not recover or expire native jobs as a side effect.

## Evidence status

The focused preview tests and broader baseline comparison are recorded in the
milestone receipt below when complete. Native registration is a separate phase;
100 repeated preview reads are not the native registration/billing gate.

## Preview milestone receipt (2026-10-20)

- Final focused preview suite: **26 passed**. Run from the repository with
  isolated mock-provider/native storage:
  `python -m pytest -q tests/test_render_bridge_preview.py`.
- JavaScript syntax: `node --check
  src_skeleton/app/integrations/render_bridge/static/preview.js` passed.
- `git diff --check` passed. No dependency or default-provider changes.
- Expanded existing host/V3 regression selection: 306 passed, the same four
  failures already present in the baseline, plus two older fixture failures
  found by expanding coverage to API access tests. Both additional failures
  were rerun on untouched baseline `6556a6ba` and reproduced:
  `test_admin_can_read_and_delete_foreign_v3_projects_but_cannot_archive_them`
  (old test double misses the browse-compute path) and
  `test_mcp_adapter_uses_new_key_without_login_or_billing_fork`
  (old projects test double does not accept `project_headers`).
  They were not changed as part of Bridge development.
- Baseline four failures: three `test_work_intensity_*` planner fixtures do not
  configure the now-required unified LLM gateway; the frontend string contract
  still expects absent `waitForMobileV3HomePreviewImages`.
- Six existing media browser cases could not start Chromium. The default browser
  cache is absent, and explicit system Chromium fails with OS `socket() Operation
  not permitted`. No permission workaround or browser acceptance was claimed.

Actual independent HTTP joint run (not MockTransport): Alchemy and Bridge
uvicorn services communicated over loopback HTTP; one reference upload, one
task/attempt/receipt and one explicit FakeRenderer start produced an exact
32-by-32 PNG (SHA256
`4075bdde0c21523c0d1208aa1cb79a48325588a7a97d24ba90bf84932b8ca906`).
Repeated POST reused the same module task. Before cancellation the state was
`preview_ready`, native registration `not_connected`, and ack `pending`.
Cancellation immediately hid the preview (409), then persisted `canceled` and a
`rejected` ack. Zero accepted acknowledgments and zero native jobs/outputs/usage
were created. Original V3 and preview/static HTTP routes passed.

Joint evidence was captured at `run-20261020-135946` against Bridge
`be9fe313155f5ddd18815a1d083da7b1b887dbf0`. It pins per-file hashes. Its tested
service.py hash was
`46696e4785d10d5b8461b004451a4c6a8d9fd998a44facea152ca7390ca76954`.
After that run, endpoint fingerprint persistence/blocking was added and passed
the final focused suite; profile-label wording was clarified. Those two final
changes were not rerun in the separate HTTP fixture. This distinction is retained
rather than claiming a final-tree joint pass from an earlier snapshot.

This is developer preview acceptance only. No rendered browser/click/navigation
acceptance, real Codex/Midjourney, cross-VPS/TLS, native registration, real review
or billing acceptance is claimed. The follow-on native milestone is limited to
the synthetic fake-image profile and mock review until real-tool capability and
fixed rendering-parameter contracts have been independently verified.
