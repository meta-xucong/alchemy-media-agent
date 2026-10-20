# Render Bridge optional module, RB00

Baseline: `6556a6ba5120fd5e17c6009f1161bd2213d2f979`, 2026-10-20.

## Total objective and current milestone

The total objective is an explicitly selected Bridge integration that eventually
reuses Alchemy-owned frozen inputs and native registration/review authorities.
This milestone supplies an independent **test preview**, not a production
provider and not native acceptance. Native registration remains unconnected;
preview must never emit an `accepted` receipt acknowledgment.

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
live under `app/integrations/render_bridge`. No shared schema or dependency
changes. This adapter is V3-host-bound; the Bridge wire protocol remains version
neutral and does not import Alchemy or Bridge runtime objects.

`disabled` (default) mounts nothing, creates no client/store/reconciler, and ignores
missing Bridge configuration. `enabled` permits explicit test tasks. `draining`
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
reconciliation and every preview read. Tests do not write native records.

## Native extension gate

The approved next milestone must establish a supported frozen-input facade and a
queryable, idempotent native registration outcome before accepted acknowledgments.
It must preserve native IDs, current permission/cancellation/revision checks,
review-only/selection/delivery rules and applicable exactly-once usage semantics.
Do not count a direct output write or MCP handoff submission as native acceptance.
The `100 identical receipts -> one native result/usage` gate remains BLOCKED in
this preview milestone, not waived or replaced with a mock preview assertion.

## Configuration

- `ALCHEMY_RENDER_BRIDGE_MODE=disabled|enabled|draining` (default disabled).
- `ALCHEMY_RENDER_BRIDGE_URL=https://bridge.example` (origin only).
- `ALCHEMY_RENDER_BRIDGE_TOKEN`: configured source credential, never browser data.
- `ALCHEMY_RENDER_BRIDGE_WORKSPACE`: operator-selected workspace binding.
- `ALCHEMY_RENDER_BRIDGE_STORAGE`: dedicated private module directory, outside
  native output/static roots. Back it up; do not delete it to recover tasks.
- `ALCHEMY_RENDER_BRIDGE_PROFILES=fake-image` (explicit opt-in list).
- For isolated loopback HTTP fixtures only:
  `ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK=true`.
- For auth-disabled isolated loopback development only:
  `ALCHEMY_RENDER_BRIDGE_LOCAL_PREVIEW=true`. Nonloopback requests still fail.

Open `/render-bridge-preview` directly. There is deliberately no change to the
old generation pages or default navigation. It displays test-only status and a
return link. User input here is a manual test prompt, not a Brain-frozen contract.

## Verification and next acceptance

Focused module tests cover disabled/no-config/outage, mock HTTP happy path,
input/create response loss, restart, cancellation, permission/revision change,
strict receipt binding/hash/media checks and no accepted ack. Host regressions
cover the existing authenticated routes and health/V3 endpoints with the module
disabled. Real Bridge HTTP plus FakeRenderer is a separate joint test, not implied
by MockTransport. No real Codex/Midjourney login, provider call, production deploy,
merge or push belongs to this milestone.
