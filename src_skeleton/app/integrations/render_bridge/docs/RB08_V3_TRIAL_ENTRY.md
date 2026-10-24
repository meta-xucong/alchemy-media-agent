# RB08: current-project V3 trial entry

## Correction model and scope

Normal V3 has no convenient project-aware Bridge entry, while the native module
already owns planning, capability negotiation, execution, registration and review.
This is a frontend composition gap, not permission to replace ordinary Generate.

Add a separate simple trial dialog to the existing composer. Copy only the prompt
when explicitly opened. Admit active Standard/general projects only. Its own form
requests one image, one of the three native sizes, an enabled profile, PNG/JPEG,
and zero to two explicitly selected active project references. Pending composer
uploads, count, presets, project-context options and advanced locks are not copied.
No hidden reference persistence, output promotion, normal-job dispatch or billing
changes are allowed. Unsupported canonical requirements remain server-rejected.

The native module API is the sole task authority. Browser state is only ephemeral
view state and a session-scoped idempotency key, not another project/job lifecycle.
Close, project navigation and account changes invalidate outstanding UI responses.
HTTP availability is not real-tool acceptance. Registered/accepted means native
receipt acknowledgement, never formal delivery. Review recovery remains server
owned, and the UI displays live projected review_pending/review_status.

## Acceptance

Use only synthetic intercepted APIs. Cover unsupported contexts, absent/disabled/
draining service, owner denial, selection and payload bounds, duplicate submission,
reload key reuse, stale responses after close/project/account changes, review-only
status and no select/export controls. Do not change ordinary Generate semantics from the integrated main baseline;
retain main's current operation/job recovery and result-projection fixes. No real providers or accounts run.

This phase does not integrate ordinary Generate, V1, V2, Lab/Professional or Video,
and does not accept production delivery, real renderer fidelity or real billing.

## First-time setup

The existing administrator module mode switch alone does not enable native trials.
An operator must explicitly set `ALCHEMY_RENDER_BRIDGE_NATIVE_ENABLED=true`, plus
compatible module/native profile allowlists and connection configuration. The UI
never changes these settings. Missing native routes explain that the administrator
may not yet have enabled the trial; ordinary Generate remains untouched.

## Review image viewing

A confirmed native output offers “查看审核图片”. It fetches only the existing
owner-authorized `/api/v3/creative-agent/outputs/{output_id}/preview` route using
the current session, displays a local blob image, and revokes object URLs on close,
project/account change or navigation. No download, select or export action is
introduced. Fake mode is labeled “生成测试图”, not a connection probe: it invokes
planning and synthetic generation. Technical errors and registration IDs are folded.

## Compatibility and verification record

This phase supersedes RB00's earlier no-old-page-entry milestone only by adding
an explicit optional composer action. It does not change the default navigation,
ordinary Generate handler, provider selection or default API path.

On the scoped feature tree, the existing Bridge contract suite plus the selected
API smoke/minimal UX/scenario/export-gate regressions passed **288 tests**. The
existing `tests/v3_*.test.mjs` selection passed **35 tests**. JS syntax and whitespace
checks passed. `createV3Job`, `buildV3JobPayload` and `uploadV3Files` were compared
byte-for-byte against base `8089edbf` and are unchanged.

Browser acceptance uses the shipped HTML, controller and actual host button hook
with synthetic state/API fixtures. The unrelated legacy application bootstrap is
paused in the fixture, so this is not full live-login/full-app acceptance. Browser execution subsequently passed **46 cases** (30 trial and 16 existing),
with desktop/mobile/review-image screenshots inspected, in GitHub workflow
[39555157577](https://github.com/meta-xucong/alchemy-media-agent/actions/runs/39555157577)
at remote revision `7c00eb3b52bd87fc18ac9c7a57ec74f1a4f57fad`. The original
capacity/retention workflow
[39555165142](https://github.com/meta-xucong/alchemy-media-agent/actions/runs/39555165142)
also passed all five jobs. Local Chromium was not run because its environment
is restricted. These are revision-specific prior results, not acceptance of
subsequent changes. No real provider,
account, production deployment or formal-output acceptance is claimed.

Current-main compatibility and review semantics supersede old fixture assumptions;
see `docs/render_bridge_module/RB12_MAINLINE_INTEGRATION_20261024.md`.
