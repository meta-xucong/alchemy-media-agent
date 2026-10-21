# Integrated administrator controls: correction model

## Objective and observed gap

The total goal is usable, opt-in Alchemy Render Bridge integration. This milestone
adds configuration and bounded diagnostics to the existing `/admin/billing` page;
it does not claim real generation, production readiness, or formal delivery.
Current bridge routes and immutable configuration are mounted only at process
startup. A disabled installation therefore cannot be enabled by an administrator.
The standalone diagnostic page is not an integrated administrator setting.

## Authority and minimal correction

The existing Veyra administrator resolver remains the authorization authority.
The existing bridge services remain task/recovery authorities. A lazy controller
owns their application lifecycle and a module-local atomic settings file stores
only nonsecret overrides. Existing environment configuration supplies credentials,
storage and development policy. The browser sees only credential presence, never
its value, and cannot install credentials or change host networking/security.

Administrator routes are always available, but all existing bridge routes remain
404 while disabled. Disabled mode constructs no bridge service, client or poller.
Explicit save enables or drains the bridge without restarting Alchemy; disabling
closes workers and preserves all durable records. A lifecycle lock fences live
HTTP requests during transitions. Endpoint/workspace and execution-policy changes
are rejected while nonterminal preview/native tasks remain. Endpoint changes may
not silently send an environment credential to a different destination.

Page load reads local settings only. A separately requested probe uses only the
saved endpoint and environment credential, with bounded capability GET and no
redirects. Disabled mode does not probe. HTTP/authentication/protocol compatibility
and advertised capability evidence are distinct from worker/login/real generation
readiness. Unknown older-server readiness is unknown, never a production-ready
claim. No diagnostic operation creates jobs, assets, billing events or providers.

## Verification and boundaries

Fixture tests cover admin/anonymous/ordinary-user access, same-origin writes,
redaction, invalid configuration, persistence, disabled zero-network behavior,
mode transitions, pending-work protection and capability failure classifications.
Existing preview/native/diagnostic regressions remain authoritative. Browser checks
cover the existing page integration, semantic forms and no automatic probe.
No real credentials, real provider calls, deployment, merge or push is performed.

### Lifecycle correction discovered by regression

The environment's FastAPI router no longer exposes `startup()`/`shutdown()`.
This is a lifecycle API mismatch, not a task-state defect. The authoritative
public lifespan context must own startup/shutdown; the controller enters and
exits `router.lifespan_context(application)` rather than invoking private hooks.
The transition fixture verifies that old workers stop and a disabled restart
constructs no clients.

## Implemented surface and evidence

- `/v1/admin/render-bridge/settings`: administrator-only GET / POST.
- `/v1/admin/render-bridge/probe`: explicit same-origin POST; disabled returns
  `bridge_disabled` without constructing a client.
- Existing `/admin/billing` now contains the integrated Render Bridge panel.
- Environment-managed credential is never accepted by this settings API, echoed
  to browsers, or written to the nonsecret settings file. Its configured URL is
  the destination binding; deployment changes to credential/URL require the
  operator's normal environment-management procedure.
- Capability HTTP/auth/protocol, advertised node state and admission are rendered
  separately. Missing older-server node evidence stays unknown. Curated task
  attention code messages reach preview/native views without forwarding arbitrary
  upstream text or changing task authority.
- Settings transitions are process-local and serialized. This development control
  surface assumes one Alchemy process owning the bridge runtime and storage; it
  is not a distributed multi-worker configuration propagation system.

Validation: all 210 then-current `tests/test_render_bridge_*.py` fixtures passed;
final expanded administrator suite passed 23 tests. Node syntax checks passed for
all three changed scripts. Three Playwright administrator tests collect, with
synthetic intercepted requests only and desktop/mobile screenshots configured as
CI artifacts. Browser execution remains for CI because this local executor's
browser socket boundary was previously denied. No local workaround was attempted.
