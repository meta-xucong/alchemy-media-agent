# RB33: Alchemy VPS and RenderBridge API-pull cutover blueprint

Date: 2026-11-02

## Objective and current phase

**Total objective:** deploy the current Alchemy release and a separate
RenderBridge API-pull service on the VPS, point Alchemy's Bridge clients at
that VPS service, and keep the Windows Codex node outbound-only. Complete the
cutover only after V1, V2, V3 and Lab have passed their product-level checks.

**Current phase:** the original Phase 8/9 status below predates later real
`codex-image` task receipts and is corrected in the 2026-11-08 addendum. The
next acceptance step is to build and activate the latest synchronized Alchemy
main revision through the guarded workflow, then run integrated V1/V2/V3/Lab
real-image acceptance. Earlier successful real tasks establish that the local
Codex CLI executor has worked; they do not replace fresh acceptance of the
current main revision.

## 2026-11-06 image-transfer contract correction

The current acceptance requires no image-byte SHA generation, transmission,
or comparison across the Alchemy/RenderBridge image-transfer path. Bind
references to the existing product reference IDs and frozen task identity;
bind generated artifacts to the existing task, attempt, slot, and receipt IDs.
Keep the existing size, MIME, image-format, dimension, and pixel-limit checks.
Prompt, task, account, and other non-image identity digests remain unchanged.
Do not use image SHA as the input or publication idempotency key.

This is a code/call-path correction discovered before the documented synthetic
Phase 8; no new image task was created for the correction. Later production
`codex-image` tasks exercised the real Bridge transfer/registration/ACK path.
See the 2026-11-08 addendum for corrected acceptance state. Existing tasks,
ledgers, artifacts, release images, and VPS data remain preserved.

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
| 3. HTTPS ingress | Configure the chosen Bridge hostname, DNS/TLS and Nginx routes for `/bridge/v1/` and `/bridge/node/v1/` to the loopback service. Keep other Bridge interfaces private. Check upload limits, Authorization forwarding, binary transfer, status propagation and no proxy request replay. | Trusted certificate; external route checks pass; root/admin/dispatcher/engine/database/CLI routes are not exposed. | Runtime ingress verified: normal TLS validation to `https://bridge.aiself.vip` passed; authenticated `/bridge/v1/capabilities` returned 200 from Windows and VPS. HTTPS root remains non-public. The earlier Nginx and certificate checks remain valid. Full artifact transfer/proxy semantics remain for Phase 8 synthetic E2E. |
| 4. Windows Node Agent | Configure a `pull-worker` entrypoint for the VPS HTTPS origin with persistent local state and the matching Node identity/profile. Keep exactly one Agent process. Connect while admission is closed and verify heartbeat/profile/status before opening tasks. | Fresh heartbeat and matching profile visible at the VPS; reconnect works after process restart; no task is created by status checks. | Closed-admission heartbeat passed at the initial staging snapshot. Later real `codex-image` task receipts prove that the local Agent executed and returned real outputs. Revalidate current process/profile readiness before final acceptance; the older fake-only heartbeat is not current-state evidence. Independent scope review at staging: NO_VIOLATION_FOUND. |
| 5. Alchemy client staging | Stage V1/V3/Lab shared settings and V2 settings for the same Bridge origin/workspace, Source token and persistent client paths. Keep modes disabled during initial staging; do not put secrets in Git or the blueprint. | Read-only checks show token is present in both approved environment files, origin/workspace/profile values match Bridge, and V1/V2 point to `/var/lib/alchemy/render-bridge-primary`; current runtime remains unchanged. Runtime capability reporting moves to the planned activation phase. | Initial file staging passed. V1/V3/Lab and V2 settings later enabled real Bridge tasks; the saved control and active release must be rechecked through the current guarded workflow before final acceptance. The V1 native test entry remained separately disabled. |
| 6. Alchemy candidate | Use the repository's guarded candidate workflow for current `origin/main`. Prepare an inactive candidate and review its receipt, V1/V2 runtime checks and staged Bridge client paths; do not activate yet. | Candidate build passes; the current guard accepts the staged shared URL/workspace and persistent paths; V1 container identity and V2 units remain available. Historical V1 data state is not digest-compared. | Run `41363241309` built commit `9a42dd87e3bd` as `/opt/alchemy-media-agent-releases/doc276-277-9a42dd87e3bd`; the Bridge path guard and candidate V2 runtime checks passed. Active release remained `/opt/alchemy-media-agent-releases/doc276-277-1eaba5539678`; V1 container and V2 units stayed available. Historical V1 data was not compared. **Rebuild required before activation:** this continuation removes file-content SHA generation/comparison from the cutover backup/restore guard, so the candidate must be rebuilt from the resulting current `origin/main`. |
| 7. Alchemy activation and runtime readiness | Schedule the guarded activation's planned V1/V2 downtime. Activate the selected Alchemy release and staged client configuration with Bridge admission still closed and Codex profile not enabled. Verify V1/V3/Lab and V2 health plus the expected Bridge origin/workspace/profile status. | All Alchemy services pass health checks; both product families read the staged Bridge configuration; no task is admitted during this phase. | Complete. Guarded activation run `41365205042` switched `/opt/alchemy-media-agent` to `/opt/alchemy-media-agent-releases/doc276-277-63368f685f8f`; run reported V1/V2 local/public health 200, desktop/H5 static markers verified, and V3 project protection 401. Rollback was not needed. Bridge admission stayed closed, and Codex profile remained disabled. The 1 GiB free-space floor passed against the measured 5.18 GB available; the current active-work inventory was idle before the maintenance window. |
| 8. Synthetic end-to-end check | Optional auxiliary check for the separate V1 native test entry (`/render-bridge-native-test`, API `/api/integrations/render-bridge/v1/native/tasks`). It is not a prerequisite for the user-facing Codex CLI return path after a real `codex-image` task has exercised planning, Agent execution, artifact transfer, registration, ACK and delivery. Do not open fake admission or create a synthetic task solely to satisfy this superseded gate. | If separately needed for native-adapter development, one fake task, one attempt, one receipt identity, final ACK accepted, and fake admission closed. | Superseded as a product acceptance gate by later real Codex E2E task evidence. No fake task was created. |
| 9. Real product acceptance | Build and activate the current main revision through the guarded VPS workflow. Revalidate the local Codex CLI Agent, then run one serial real image task through each product's user-facing route. Confirm route, same Bridge task/attempt/receipt, Agent execution, Alchemy registration/ACK and user-visible preview/download; ensure no API fallback or duplicate generation. | Fresh product-level evidence for V1, V2, V3 and Lab on the exact active revision. | Historical real Codex tasks establish executor capability and partial product coverage, including successful V1, V3 and Lab deliveries and a recovered V2 Bridge output. Fresh integrated acceptance remains open for the latest synchronized source revision and repaired V2/V3 paths. |

## Configuration map (names and paths only)

### Bridge VPS

- Runtime config based on `config/bridge.remote-pull.example.json`.
- `dispatch_mode=node_pull`, listener `127.0.0.1:8787`, fresh durable
  `data_dir`, stable source/workspace/node/executor IDs.
- The initial deployment used `accepting_new_tasks=false` and
  `enabled_profiles=["fake-image"]`; later real `codex-image` tasks completed.
  Read the active runtime configuration before final acceptance.
- `BRIDGE_SOURCE_TOKEN` is configured in Bridge and supplied to Alchemy.
- `BRIDGE_NODE_TOKEN` is configured in Bridge and supplied only to the local
  Node Agent. Keep both out of the repository and logs.
- Real `codex-image` tasks already confirmed that the configured local Agent
  can execute and return images; the synthetic native route is not a gate for
  the user-facing product routes.

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

1. Current synchronized `origin/main` is `0dec6de5`; the active VPS release is
   the earlier `63368f685` revision. Read-only preflight run `42435115801`
   passed for its parent `24392294`; this documentation-only commit still needs
   a fresh candidate build for the exact current SHA before guarded activation.
2. Historical evidence disproves the earlier claim that the Windows Agent is
   fake-only: it was configured for `codex-image`, the local Codex CLI login was
   verified, and real Bridge tasks completed. Revalidate current Agent
   readiness before the new run; do not infer inability from the older Phase 4
   heartbeat snapshot or the diagnostics-only `real_generation_verified=false`
   field.
3. Do not run the synthetic native fake-image task as a prerequisite. It is a
   separate auxiliary route and was superseded for this product objective by
   real `codex-image` tasks exercising Bridge transfer, registration and ACK.
4. Final acceptance remains open until fresh V1, V2, V3 and Lab runs pass on the
   exact active revision, with visible/downloadable outputs and no API fallback
   or duplicate generation. Preserve the two historical V2
   `api_execution_unknown` records unless the guarded workflow's exact
   abandonment predicates prove them eligible for this cutover.

Read-only public checks show that `alchemy.aiself.vip` responds over HTTPS (a
HEAD request returns 405, proving reachability only, not application health).
`bridge.aiself.vip` resolves locally and through public resolvers to
`114.134.186.94`; its new HTTPS certificate now passes normal hostname and
trust validation. The Alchemy VPS SSH helper connects to port `11506` with
the existing known-host key. An earlier probe of the default SSH port 22
timed out; that is not the configured SSH port.

The current Alchemy source has already passed the read-only V3 preflight. Build
the inactive candidate from the exact current `origin/main`, run the Bridge
storage guard, and activate only through the guarded V1/V2 maintenance workflow.
Before generating, revalidate current Agent readiness and the product routes.
Then run the serial real Codex acceptance for V1, V2, V3 and Lab, preserving
existing fallback policy and stopping a product if any request leaves Bridge
after acceptance. Do not report total completion at a phase boundary.

The guarded candidate, preflight and activation workflows no longer compute or
compare SHA-256 digests of V1 historical state, and cutover backup manifests
do not store or compare file-content SHA values. Restore retains path-scope,
metadata and SQLite quick-check behavior. Candidate environment equivalence
uses a quiet direct diff; the Git commit identifier remains the release
selector. Candidate build run `41363241309` completed for commit
`9a42dd87e3bd`; historical V1 data was not compared.

## 2026-11-06 no-image-SHA correction model

The user selected end-to-end removal of image-content SHA from the Bridge
artifact contract and authorized replacing image-based replay identity with
stable task/output/reference IDs. The failure was not limited to upload or
receipt fields: V3 froze and rechecked reference bytes before the Bridge
adapter ran, and API fallback results managed by the Bridge primary route were
still stored with output-content SHA.

For Bridge-managed V3 jobs, the server marks the request before freezing its
reference plan. New plans use schema v4 and bind references by stable asset ID,
order, and existing file path; plan JSON digests remain metadata digests. Old
schema-v3 plans remain readable, but their historical image digest fields are
not recalculated or compared during Bridge-managed execution. The Bridge
primary API fallback keeps the same `legacy_generate(app_request)` call,
reference files, prompt, and provider result handling; its Bridge-managed
output record omits image-content SHA just like a successful Bridge output.
Ordinary API jobs without the Bridge primary marker retain their existing
path.

### Follow-up theory correction: V3 continuity and reference materialization

The first implementation still left two reachable image-byte hash paths in
Bridge-managed V3 generation: generic reference evidence deduplication ran
before Bridge transport, and Doc73 same-batch continuity required an image
digest in its output binding. This contradicted the no-image-SHA contract even
though the V4 plan and Bridge receipt omitted that field.

The owning layers are V3 provider reference materialization and the Doc73
output-identity binding. For Bridge-managed V3 only, deduplication must use
the already-authoritative asset/output IDs, and Doc73 continuity must bind to
the persisted output ID plus its existing job, project, batch, asset, and
candidate identity. The binding's canonical metadata digest may remain; it
must not include or require an image-content digest. Existing non-Bridge
Doc73 v1 behavior remains unchanged. Regression coverage must include a
Bridge-managed first output, its hash-free Doc73 receipt, and the resulting
V4 same-batch reference plan before running the focused generation tests.

Focused acceptance must prove: the new V3 plan contains no image-content SHA;
the Bridge input and receipt/ACK payloads contain none; output and API-fallback
records managed by Bridge primary contain none; reference bytes still reach
the selected provider; stable IDs preserve replay; and ordinary API routing
still works. This design does not claim that every unrelated V3 asset-library
or project-mode record in the product database has been migrated.

### Follow-up theory correction: E-Commerce admission before Bridge materialization

The code-first trace found that E-Commerce Bridge jobs still entered Doc263
product-truth admission before provider materialization. Its v1 source schema
required computing and comparing uploaded image bytes, and optional Doc270
binding repeated that image-content comparison before issuing the Bridge
request. This made the earlier V4/Doc269 omission incomplete for E-Commerce.

Bridge-marked E-Commerce requests now use a Doc263 v2 source binding keyed by
the existing asset ID and omit the image-content field. The provider still
requires the canonical product asset, role, project/job binding, and selected
projection, but skips image-byte fingerprinting in this marked path. Optional
Doc270 binding likewise retains project/source IDs and its existing metadata
receipts while omitting the image-content comparison and selected-source field.
The ordinary unmarked API path retains Doc263 v1 and Doc270's current image
integrity behavior. A focused regression test makes `Path.read_bytes` fail if
the Bridge admission path attempts to read image bytes.

### Follow-up theory correction: output-store delivery closure

The successful Bridge output path also seals an immutable V3 output-store
delivery closure after review. Its v1 schema required each output's image SHA,
so a hash-free output could remain available in memory but could not be sealed
for restart/history recovery. Bridge-marked output jobs now use closure v2,
which binds output, asset, candidate, job, execution-envelope, and ledger IDs;
it confirms the canonical download file exists without reading its bytes.
The existing v1 closure schema and byte-integrity path remain in place for
unmarked API jobs and previously stored receipts.

### Follow-up theory correction: E-Commerce public review projection

The code audit found one more reachable Bridge-marked consumer after delivery
closure: V3 status projection derives the E-Commerce review disposition from
persisted OutputStore records. Its existing unmarked-API path verifies file
bytes against `content_sha256`, which is absent by design on Bridge outputs.
For the Bridge marker only, the projection must bind the same job/output/asset
IDs, require the canonical file to exist, and avoid reading its contents. The
unmarked API branch keeps its existing byte-integrity comparison. A focused
test will make `Path.read_bytes` fail while the marked review disposition is
derived, then assert that the existing final-delivery state is projected.

### Follow-up theory correction: Doc73 Project Mode continuity lookup

The downstream Project Mode anchor reader also accepts Doc73 v2's ID-bound
receipt, then incorrectly re-hashes the referenced output and rejects the
receipt because v2 has no `source_content_sha256`. In the Bridge-marked v2
case, the authoritative binding is the validated Doc73 receipt plus its job,
project, output, asset and candidate IDs; the existing output path must exist,
but its bytes are not read. Doc73 v1 remains on the original SHA comparison.
A focused regression test will make `Path.read_bytes` fail during v2 anchor
lookup and assert that the exact bound output is returned.

### Follow-up theory correction: explicit Project Mode continuity binding

Manual or automatic Project Mode continuity binding has its own durable
Doc322 record. Its v1 resolver hashes the selected output, and the persisted
anchor stores that image digest; later generation also requires the digest in
Doc269 admission. For a Bridge-marked output, use a v2 anchor record bound by
the existing project, job, output, asset and candidate IDs, with a canonical
file-existence check and no image digest. The v1 record and resolver remain
unchanged for ordinary API outputs. Doc269's Bridge-marked admission must
preserve the same selected reference while omitting image-content fields.
Regression coverage now verifies ID-bound v2 persistence/reload, Project Mode
source resolution, and hash-free Doc269 admission without reading output
bytes.

### Follow-up theory correction: Doc271 E-Commerce source closure

The independent Project Mode audit traced selected outputs one step further:
E-Commerce's Doc271 current-source receipt re-read generated output bytes and
required the selected-continuation digest. It also projected Doc269 physical
reference plans into a receipt that required an image digest for every input.
Bridge-marked v2 plans now project stable source IDs and file existence into a
v2 binding without reading image bytes; their Doc271 source binding omits image
digests. The existing v1 digest path remains for ordinary API plans. A focused
regression test rejects any image-byte read while deriving the v2 physical
binding.

## 2026-11-08 correction: Codex CLI executor and prior real-task evidence

The Phase 4/8/9 status above was carried forward from the earlier fake-only
heartbeat stage and was not reconciled with later live acceptance. That was a
documentation and evidence-selection error, not a Codex CLI capability failure.

The linked acceptance conversation records that the local Codex CLI login was
valid and the Windows pull Agent configuration included the Codex executor.
V1 task `job_b2825c0641ba` used `codex-image` with automatic API fallback
disabled; it reached `ready`, was ACKed by Bridge, and its preview/download
returned 200. Lab also completed a real Bridge task and its preview/download
returned 200. V3 task `job_a306456164` later produced two Bridge ACKs with no
API fallback; its two candidate outputs returned 200 from preview/download.
An earlier four-product run also produced Bridge outputs for V1, V2, V3 and
Lab, but that run exposed a V2 projection/recovery issue and one V3 API
fallback, so it was partial acceptance rather than a clean final pass. The
existing V2 task `job_8639d8669f30` was subsequently recovered from its
original Bridge receipt without creating a new image task.

`src_skeleton/app/integrations/render_bridge/diagnostics.py` intentionally
types and emits `real_generation_verified` as false for its diagnostic
response. That field is not a history of completed Codex tasks. The authoritative
evidence is the persisted product task, Bridge task/attempt/receipt and ACK,
plus the product output and preview/download. The native `fake-image` endpoint
is a separate auxiliary path and is not a required gate for the user-facing
Codex CLI workflow after real tasks have exercised the shared transfer path.

These historical results prove the Codex CLI return design has worked and
supersede the stale “Codex executor unverified/fake-only” conclusion. They do
not certify the latest `0dec6de5` source because that revision has not yet been
activated. Run final integrated acceptance only after the guarded workflow has
activated the fresh candidate, and record current task IDs and delivery results
there. No image content SHA/hash/checksum is part of this acceptance.
