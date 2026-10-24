# Render Bridge optional module, RB00

Baseline: `6556a6ba5120fd5e17c6009f1161bd2213d2f979`, 2026-10-20.

## Total objective and current milestone

The total objective is an explicitly selected Bridge integration that reuses
Alchemy-owned frozen inputs and native registration/review authorities.
Implemented surfaces now include independent **test preview**, opt-in native
development integration for configured fake/Codex/manual profiles, administrator
controls, and the optional current-project V3 trial dialog. None is a production
provider. RB03–RB08 describe the later increments and their bounded acceptance. Preview remains unconnected to native registration and
must never emit `accepted`; only the native coordinator may acknowledge a
confirmed real native checkpoint. See RB03 for integrated acceptance and limits.

## Observed seams and authority

- Host `src_skeleton/app/main.py`: `_veyra_user_id_from_request` verifies existing
  sessions. Owner-only project writes use `metadata.veyra_user_id`.
- `project_store.get_project` is a read-only snapshot. Do not call the project
  service's reconciliation getter to make a preview. A conservative canonical
  snapshot hash detects content changes; there is no public native revision.
- Existing MCP submission remains loopback-only and handoff-bound. Neither the
  local guard nor output store is a generic native importer.
- No preview code calls native generation, Brain, provider registry, billing,
  review, selection, delivery, memory, history, or output persistence.

## Implementation boundary

One additive mount at the end of main.py provides host-owned authentication and
read-only project snapshot callbacks. All new logic, static UI and documents
live under `app/integrations/render_bridge`. The native phase adds narrowly scoped
Alchemy-owned plan/freeze/register facades and default-None checkpoint/review
hooks, described in `docs/render_bridge_module/RB02_NATIVE_FACADE_STAGE.md`.
No dependency changes. This adapter is V3-host-bound; the Bridge wire protocol remains version
neutral and does not import Alchemy or Bridge runtime objects.

`disabled` (default) leaves the administrator settings routes available, but
creates no Bridge client/store/reconciler and leaves task routes inactive; missing
Bridge configuration does not prevent host startup. See `admin-controls.md`. `enabled` permits explicit test tasks. `draining`
only resumes module tasks and rejects creation. Invalid enabled configuration
leaves the host running and reports a module-only error. Fully disabled pauses
recovery and retains the module database; use draining before disable if needed.

The module owns its SQLite mapping, input blobs and receipt blobs. It persists
stable origin/input/receipt keys before network effects, looks up by origin after
uncertain submission, never creates a second generation key, uses a two-connection
HTTP client, one dedicated local worker, bounded local admission, a single polling
loop, bounded batches, durable per-record leases and bounded retry backoff.
Bridge errors never trigger an old-provider fallback. Cancellation hides preview
immediately; late receipts are not registered. Scope/revision is rechecked before
reconciliation and every preview read. Preview tests do not write native records;
native tests use separate temporary stores and synthetic pixels.

## Restricted native extension

The approved extension now supplies plan-only, canonical freeze and queryable
idempotent native registration. It defaults to `fake-image` revision 1; configured `codex-image` and
`midjourney-manual` development profiles are also implemented (RB06). Native
options remain auto quality, PNG/JPEG original-format validation, sizes
1024x1024, 1024x768 or 768x1024, and zero to two authorized current-project
uploaded originals. Manual profiles accept no references. See RB04/RB06.
It reuses native candidate persistence and
review-only continuation, without rendering again, selecting, exporting or
promoting fake results. A receipt alone is not native acceptance.
Reference bytes/order/hash are verified; fake pixels are not visually conditioned
on references. Unsupported canonical fidelity/options are not silently removed.

100 identical receipts and concurrent replay produce one native output and one
execution audit. This audit is not billing usage. Current V3 has a zero-credit
balance stub; the historical "one usage" billing assertion is not applicable and
real billing remains unverified. No new ledger or charge was invented.

## Configuration

- `ALCHEMY_RENDER_BRIDGE_MODE=disabled|enabled|draining` (default disabled).
- `ALCHEMY_RENDER_BRIDGE_URL=https://bridge.example` (origin only).
- `ALCHEMY_RENDER_BRIDGE_TOKEN`: configured source credential, never browser data.
- `ALCHEMY_RENDER_BRIDGE_WORKSPACE`: operator-selected workspace binding.
- `ALCHEMY_RENDER_BRIDGE_STORAGE`: dedicated private module directory, outside
  native output/static roots. Back it up; do not delete it to recover tasks.
- `ALCHEMY_RENDER_BRIDGE_PROFILES=fake-image` (explicit opt-in list).
- `ALCHEMY_RENDER_BRIDGE_NATIVE_ENABLED=true` additionally enables the restricted
  native development entry. Default false; requires an authenticated owner.
  `LOCAL_PREVIEW` does not authenticate native requests.
- For isolated loopback HTTP fixtures only:
  `ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK=true`.
- For auth-disabled isolated loopback development only:
  `ALCHEMY_RENDER_BRIDGE_LOCAL_PREVIEW=true`. Nonloopback requests still fail.

Open `/render-bridge-preview` directly. The ordinary V3 project page also offers
a separate explicit trial action (RB08); ordinary Generate and its payload remain
unchanged. Administrator controls live in the existing `/admin/billing` page. It displays test-only status and a
return link. User input here is a manual test prompt, not a Brain-frozen contract.
The separate `/render-bridge-native-test` requests a new native plan explicitly,
then uses its canonical frozen contract. Startup/status never invoke Brain.

## Verification and next acceptance

Focused module tests cover disabled/no-config/outage, mock HTTP happy path,
input/create response loss, restart, cancellation, permission/revision change,
strict receipt binding/hash/media checks and no accepted ack. Host regressions
cover the existing authenticated routes and health/V3 endpoints with the module
disabled. Real Bridge HTTP plus FakeRenderer is a separate joint test, not implied
by MockTransport. No real Codex/Midjourney login, provider call, production deploy,
merge or production deployment belongs to this milestone. Feature-branch
publication is handled separately after review; it does not imply CI success.
