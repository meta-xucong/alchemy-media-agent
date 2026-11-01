# RB33: Alchemy VPS and RenderBridge API-pull cutover blueprint

Date: 2026-11-02

## Objective and current phase

**Total objective:** deploy the current Alchemy release and a separate
RenderBridge API-pull service on the VPS, point Alchemy's Bridge clients at
that VPS service, and keep the Windows Codex node outbound-only. Complete the
cutover only after V1, V2, V3 and Lab have passed their product-level checks.

**Current phase:** document the rollout contract, record the local baseline,
and establish which next steps can be performed without changing production.
This document is an execution blueprint; a completed local phase is not VPS
deployment or final acceptance.

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
| Alchemy | GitHub `origin/main`, commit `5827e4e7` | Unique project-root checkout is on `main` and synchronized; tracked tree is clean. Numerous pre-existing untracked diagnostic/evidence paths remain and must be preserved. | Candidate source only; live VPS revision is not yet inspected. |
| RenderBridge | GitHub `origin/main`, commit `69ecec7` | Standalone checkout has local `main` divergence (8 local-only and 13 upstream-only commits at fetch) plus pre-existing tracked modifications and untracked runtime/worktree data. | Do not deploy from this checkout. Use the exact upstream release in an isolated worktree if code preparation is needed. |
| VPS | Current production Alchemy + new Bridge service | Not inspected in this phase. VPS address, current release, disk reserve, TLS/DNS, service state, and configuration agreement remain unknown. | No production mutation yet. |

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
| 1. VPS inventory | Read-only inspect the production host: active Alchemy release and services, current V1/V2 data roots, free space, TLS/Nginx, existing firewall/listeners, current unresolved Bridge work and available backup/restore evidence. Record identifiers and paths, not secret values. | Inventory matches the VPS and identifies the actual Bridge hostname, service layout and maintenance constraints. If access is unavailable, stop here and ask for the missing host/access route. | Partial: public DNS/HTTPS only; host inventory not reached. |
| 2. Bridge deployment preparation | From upstream `69ecec7`, prepare a clean isolated release/config for `node_pull`; select a durable fresh Bridge data directory and loopback listener; add or document the minimum service manager lifecycle needed by this VPS. Keep `accepting_new_tasks` false and `enabled_profiles` fake-only during initial service check. | Service starts/restarts from the pinned release; BridgeStore and artifacts persist across restart; no local DB is copied; source and node auth are distinct. | Not started. |
| 3. HTTPS ingress | Configure the chosen Bridge hostname, DNS/TLS and Nginx routes for `/bridge/v1/` and `/bridge/node/v1/` to the loopback service. Keep other Bridge interfaces private. Check upload limits, Authorization forwarding, binary transfer, status propagation and no proxy request replay. | Trusted certificate; external route checks pass; root/admin/dispatcher/engine/database/CLI routes are not exposed. | Not started. |
| 4. Windows Node Agent | Configure the existing launcher for `pull-worker` against the VPS HTTPS origin with persistent local state and the matching Node identity/profile. Keep exactly one Agent process. Connect while admission remains closed and verify heartbeat/profile/status only. | Fresh heartbeat and matching profile visible at the VPS; reconnect works after process restart; no task is created by status checks. | Not started. |
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
   divergent and dirty; any Bridge implementation must start from the fetched
   upstream branch in a separate worktree and must not disturb the existing
   checkout or its data.
2. The live VPS has not yet been inspected in this task. Do not infer hostname,
   TLS, disk capacity, service state, credentials or unresolved-task status
   from local files or prior messages.
3. Bridge's production service lifecycle is not yet supplied by the upstream
   example itself. Complete that concrete deployment preparation before
   activating Alchemy against it.
4. Final acceptance remains open until all four product routes and the real
   frontend image-delivery path pass on the VPS.

Read-only external checks during this phase found that
`alchemy.aiself.vip` resolves and responds over HTTPS (a HEAD request returned
405, so this proves reachability only, not application health). The queried
`bridge.aiself.vip` name did not return an A record. No local SSH config was
present, and a batch SSH connection to `alchemy.aiself.vip:22` timed out. These
observations do not establish which host is intended for Bridge or provide VPS
service access.

No remote workflow, service, DNS, TLS, firewall, credential or Alchemy setting
was changed during this phase.

Next operation: obtain a working VPS inspection path and the actual Bridge
hostname, then complete Phase 1 read-only. Advance one phase at a time, updating
the phase table with observed evidence and explicit not-run items. Do not report
total completion at a phase boundary.
