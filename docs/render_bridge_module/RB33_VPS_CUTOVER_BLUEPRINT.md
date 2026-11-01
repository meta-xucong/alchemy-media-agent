# RB33: Alchemy VPS and RenderBridge API-pull cutover blueprint

Date: 2026-11-02

## Objective and current phase

**Total objective:** deploy the current Alchemy release and a separate
RenderBridge API-pull service on the VPS, point Alchemy's Bridge clients at
that VPS service, and keep the Windows Codex node outbound-only. Complete the
cutover only after V1, V2, V3 and Lab have passed their product-level checks.

**Current phase:** the Bridge hostname certificate and isolated Nginx ingress
are configured. Finish the VPS inventory, then install and start the prepared
Bridge service before validating its API paths. This document is an execution
blueprint; this ingress milestone is not Bridge runtime or final acceptance.

## Fixed architecture and authorities

```text
Alchemy VPS (V1/V3/Lab :8017; V2 :8020)
  -> HTTPS Bridge Source API -> VPS BridgeStore and artifact directory
                                 ^
                                 | outbound HTTPS pull
Windows Node Agent -> local Codex CLI
```

- Alchemy remains authoritative for user/project authorization, planning,
  review, native result registration, billing and delivery.
- The VPS BridgeStore is the authority for Bridge tasks and artifacts. The
  Windows Agent journal is local recovery evidence, not a second queue.
- Alchemy uses only the Bridge Source credential. The Windows Agent uses the
  separate Node credential. Do not reuse the dispatcher credential.
- The local Agent connects outbound. Do not expose a Windows port or create a
  reverse tunnel. Bridge listens on VPS loopback behind its HTTPS ingress.
- Use a fresh VPS Bridge data directory. Do not copy local SQLite or merge
  ledgers. Existing accepted/unknown local tasks stay on their original local
  endpoint, ledger and profile until reconciled; do not recreate them on VPS.
- API fallback remains limited to explicit pre-admission rejection. Once a
  Bridge task may have been accepted, keep the same origin/task identity on
  that Bridge endpoint and reconcile it there.
- Keep one serial Windows node. Do not run two dispatchers against one ledger.

## Baseline observed before this blueprint

| Component | Intended release baseline | Local workspace observation | Release use |
|---|---|---|---|
| Alchemy | GitHub `origin/main`, commit `5827e4e7` | At blueprint start, the unique project-root checkout was on synchronized `main` with a clean tracked tree. This phase intentionally updated RB33 to record live ingress progress; numerous pre-existing untracked diagnostic/evidence paths remain and must be preserved. | Candidate source only; live VPS revision is not yet inspected. |
| RenderBridge | GitHub `origin/main`, commit `69ecec7` | Standalone checkout has local `main` divergence (8 local-only and 13 upstream-only commits at fetch) plus pre-existing tracked modifications and untracked runtime/worktree data. | Do not deploy from this checkout. Use the exact upstream release in an isolated worktree if code preparation is needed. |
| VPS | Current production Alchemy + new Bridge service | SSH access confirmed to `114.134.186.94:11506` (`ser467022953094`). Nginx is active; Alchemy listeners 8017/8020 are present. Active Alchemy release pointer is `/opt/alchemy-media-agent-releases/doc276-277-1eaba5539678`; the running image is `alchemy-media-agent:latest` (635 MB, reported 9 days old). Persistent V1 media and V2 storage roots are `/var/lib/alchemy/v1/media_storage` (3.3 GB) and `/var/lib/alchemy/v2/storage` (1.6 GB); total free space is 6.7 GB of 30 GB. No Bridge service or listener on 8787 exists, so there is no VPS Bridge queue to migrate. Existing Alchemy backup snapshots through Oct 24 include runtime contracts and SQLite stores, but the inspected evidence does not establish a current media-data backup or a tested restore. | Bridge hostname ingress is ready. VPS Bridge can use a fresh empty store; Alchemy release cutover remains blocked on sufficient disk reserve and current mutable-data backup/restore evidence. |

The current RenderBridge upstream contains the API-pull runtime, remote-pull
example config and two-route HTTPS proxy example. The example config is
fake-image-only and its sample admission setting is enabled; production staging
must explicitly keep admission closed until the Agent and Alchemy are ready.
The reviewed repository does not currently provide a complete production
systemd/container installation workflow for this VPS topology. Provisioning
and service lifecycle therefore need an explicit, reviewable implementation
step before production activation.

The Alchemy guarded candidate/preflight/activation workflows handle Alchemy
releases and Alchemy's Bridge client state; they do not install or operate the
standalone RenderBridge service. `scripts/deploy_vps.sh` is not the production
activation path. The guarded workflows take a target commit and verify that the
prepared and active release matches it. Activation also has a planned V1/V2
maintenance window and requires its target commit and disk-reserve inputs.

## Step-by-step rollout

| Phase | Work | Exit evidence | Status |
|---|---|---|---|
| 0. Local baseline | Confirm Alchemy root is the unique `main` checkout; record upstream Bridge release separately from the dirty/divergent local Bridge checkout; preserve all existing scratch, journals and ledgers. | Both repository states recorded; no dirty data removed or overwritten. | Complete for local read-only inspection. |
| 1. VPS inventory | Read-only inspect the production host: active Alchemy release and services, current V1/V2 data roots, free space, TLS/Nginx, existing firewall/listeners, current unresolved Bridge work and available backup/restore evidence. Record identifiers and paths, not secret values. | Inventory matches the VPS and identifies the actual Bridge hostname, service layout and maintenance constraints. If access is unavailable, stop here and ask for the missing host/access route. | Mostly complete: SSH to `114.134.186.94:11506` works with pinned host key. Host `ser467022953094`; Nginx 1.22.1; Alchemy listener ports 8017/8020; firewall 80/443; active release pointer and V1/V2 persistent roots inspected. Disk has 6.7 GB free; V1 media is 3.3 GB and V2 storage 1.6 GB. No existing VPS Bridge process/listener or VPS Bridge tasks were found. Backups through Oct 24 contain release runtime contracts and SQLite stores, but current mutable-media coverage and restore evidence are unconfirmed. Keep Alchemy candidate/activation blocked pending disk-reserve and backup/restore determination; Bridge itself can start on a fresh empty store after its local runtime workflow is validated. |
| 2. Bridge deployment preparation | From upstream `69ecec7`, prepare a clean isolated release/config for `node_pull`; select a durable fresh Bridge data directory and loopback listener; add or document the minimum service manager lifecycle needed by this VPS. Keep `accepting_new_tasks` false and `enabled_profiles` fake-only during initial service check. | Service starts/restarts from the pinned release; BridgeStore and artifacts persist across restart; no local DB is copied; source and node auth are distinct. | Complete. VPS image `alchemy-render-bridge:rb33-20261102` built from the isolated API-pull feature branch and runs in enabled systemd service `alchemy-render-bridge-api.service`, bound to `127.0.0.1:8787`. Authenticated loopback and public HTTPS capability checks returned 200; service restart retained its SQLite state. Admission remains closed and only `fake-image` is enabled. |
| 3. HTTPS ingress | Configure the chosen Bridge hostname, DNS/TLS and Nginx routes for `/bridge/v1/` and `/bridge/node/v1/` to the loopback service. Keep other Bridge interfaces private. Check upload limits, Authorization forwarding, binary transfer, status propagation and no proxy request replay. | Trusted certificate; external route checks pass; root/admin/dispatcher/engine/database/CLI routes are not exposed. | Runtime ingress verified: normal TLS validation to `https://bridge.aiself.vip` passed; authenticated `/bridge/v1/capabilities` returned 200 from Windows and VPS. HTTPS root remains non-public. The earlier Nginx and certificate checks remain valid. Full artifact transfer/proxy semantics remain for Phase 6 synthetic E2E. |
| 4. Windows Node Agent | Configure a `pull-worker` entrypoint for the VPS HTTPS origin with persistent local state and the matching Node identity/profile. Keep exactly one Agent process. Connect while admission remains closed and verify heartbeat/profile/status only. | Fresh heartbeat and matching profile visible at the VPS; reconnect works after process restart; no task is created by status checks. | Complete for closed-admission heartbeat. Dedicated `scripts/start_vps_node_agent.bat` / `.ps1` use the existing CurrentUser DPAPI NodeToken.v1 record and persistent `%LOCALAPPDATA%` state. Windows PowerShell 5.1 launcher completed HTTPS and Node-auth checks; VPS reported Node online with `fake-image` and `admission=false`. Agent is currently running. Restart/reconnect and task execution remain unverified; no task was created. Independent scope review: NO_VIOLATION_FOUND. |
| 5. Alchemy client staging | Configure V1/V3/Lab shared runtime and V2 runtime to the same Bridge origin/workspace and Source token. Keep V2 `control.json`, V2 environment and V1 environment consistent; keep Alchemy client ledgers under `/var/lib/alchemy/render-bridge-primary`. Do not put secrets in Git or the blueprint. | The VPS guards accept the common URL/workspace and persistent paths; each product reports the expected Bridge capability while new admission remains closed. | Not started. |
| 6. Synthetic end-to-end check | With a fresh isolated Bridge store and fake executor, exercise Alchemy create -> Agent pull/claim/start -> artifact transfer -> native registration fixture -> same-receipt ACK. Include only the failure/restart cases already required by RB30/RB32. | One task, one attempt, one receipt identity; final ACK accepted; no real provider call or charge. | Not started. |
| 7. Alchemy candidate | Use the repository's guarded candidate/preflight workflows for the selected upstream release. Prepare an inactive candidate and review its receipt, data preservation and V1/V2 runtime checks; do not activate yet. | Candidate is bound to the intended release; persistent media/history and Bridge client paths pass the workflow checks. | Not started. |
| 8. Production cutover | Schedule the guarded activation's planned V1/V2 downtime. During the maintenance window, activate Alchemy and its matching client config; then open Bridge admission and enable the Codex profile after the Agent is ready. | V1/V3/Lab and V2 health/status pass; Bridge task is pulled and delivered through the same task/attempt/receipt; history, viewing and download pass. | Not started. |
| 9. Real product acceptance | Run a controlled real image task through the frontend, first on one product, then verify the remaining product routes. Confirm route, Bridge task, Agent execution, uploaded original, Alchemy registration, ACK and user-visible result. | Product-level evidence for V1, V2, V3 and Lab; no duplicate API generation after Bridge acceptance. | Not started. |

## Configuration map (names and paths only)

### Bridge VPS

- Runtime config based on `config/bridge.remote-pull.example.json`.
- `dispatch_mode=node_pull`, listener `127.0.0.1:8787`, fresh durable
  `data_dir`, stable source/workspace/node/executor IDs.
- Start with `accepting_new_tasks=false` and `enabled_profiles=["fake-image"]`.
- `BRIDGE_SOURCE_TOKEN` is configured in Bridge and supplied to Alchemy.
- `BRIDGE_NODE_TOKEN` is configured in Bridge and supplied only to the local
  Node Agent. Keep both out of the repository and logs.
- After synthetic acceptance, add `codex-image` only when the local Agent's
  configured executor and runtime capability are confirmed.

### Alchemy VPS

- V1/V3/Lab share the Alchemy-side `ALCHEMY_RENDER_BRIDGE_*` configuration.
  The URL is an HTTPS origin with no path prefix; the Source token and workspace
  must match the Bridge service. Profile/native profile settings must match the
  enabled Bridge/Agent profile. Preserve the existing fallback policy.
- V2 reads its persistent primary control file and V2 environment. Keep
  `ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG` at
  `/var/lib/alchemy/render-bridge-primary/control.json` and
  `ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT` at
  `/var/lib/alchemy/render-bridge-primary/ledgers`. Its control URL/workspace
  must match V1/V3/Lab and its token remains in the protected V2 environment.
- The Bridge task database/artifact path is separate from the Alchemy client
  `ledgers` path. Back up Bridge database and artifacts together.

Exact secrets, production hostnames, token values and current runtime values
belong in the approved secret/configuration store, never in this document.

## Rollback boundary

- Before VPS Bridge accepts a task: close new admission, restore the previous
  Alchemy release/configuration through the guarded process, and leave the
  existing local service and data untouched.
- After VPS Bridge accepts a task: stop only new admission; preserve the VPS
  Bridge database and artifact directory; resolve that same task on the same
  endpoint before changing routes. Never recreate an accepted/unknown task on
  the local ledger or delete either ledger as cleanup.
- Keep the previous Alchemy candidate and Bridge data available until the
  relevant post-cutover checks have passed.

## Current blockers and next action

1. The RenderBridge local checkout is not a safe release source because it is
   divergent and dirty; the VPS Bridge was built from the isolated fetched
   upstream feature branch, and that checkout remains untouched.
2. VPS inventory found 6.7 GB free and mapped the active V1/V2 persistent
   roots. Existing Alchemy backups through Oct 24 contain SQLite stores and
   runtime contracts; current mutable-media coverage and tested restore remain
   unconfirmed. Keep the Alchemy release candidate/activation behind the
   repository's disk-reserve and backup requirements.
3. Bridge service and the local fake-image Node heartbeat are live. The Node
   Agent has not yet pulled or executed a task. Keep admission closed and
   fake-only until the Alchemy client configuration and synthetic E2E receipt
   flow pass.
4. Final acceptance remains open until all four product routes and the real
   frontend image-delivery path pass on the VPS.
5. V1/V3/Lab and V2 clients still have no VPS Bridge configuration. Source
   token provisioning and client readiness checks are the next phase; do not
   change the existing fallback policy.

Read-only public checks show that `alchemy.aiself.vip` responds over HTTPS (a
HEAD request returns 405, proving reachability only, not application health).
`bridge.aiself.vip` resolves locally and through public resolvers to
`114.134.186.94`; its new HTTPS certificate now passes normal hostname and
trust validation. The Alchemy VPS SSH helper connects to port `11506` with
the existing known-host key. An earlier probe of the default SSH port 22
timed out; that is not the configured SSH port.

No Alchemy configuration was changed during Bridge deployment. The next
operation is Phase 5 Alchemy client staging: provision Source credentials into
the approved VPS secret/configuration locations, stage both product clients
with admission still closed, and check that V1/V3/Lab and V2 report the same
Bridge origin/workspace/profile. Preserve existing API fallback behavior.
Advance to the synthetic fake-image task only after the staged client guards
pass; do not report total completion at a phase boundary.
