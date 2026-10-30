# RB32: Alchemy and Render Bridge VPS readiness

## Goal and scope

Prepare both repositories for a later VPS deployment: Alchemy and the Bridge
task service/ledger on their VPS; Windows Node Agent and Codex CLI on the local
computer, pulling work through outbound HTTPS. This task is local preparation
only. Do not deploy, publish, merge, provision credentials, modify the live VPS,
or run paid generation.

## Fixed baseline

| Repo | Worktree | Branch | HEAD |
|---|---|---|---|
| Alchemy | `D:\AI\Alchemy Media Agent System\.codex-work\pull-relay-alchemy-20261029` | `codex/api-pull-relay-alchemy-20261029` | `0e1b9509d4d332844f2cc371908764b361ce726f` |
| Bridge | `D:\AI\Alchemy Media Agent System\.codex-work\pull-relay-bridge-20261029` | `codex/api-pull-relay-bridge-20261029` | `a971ef830e998475005833bd64d0fdae07726ac3` |

Preserve all pre-existing dirty files and data. Alchemy has V2 owner-isolation
code/tests, README/RB30 edits and untracked RB31. Bridge has API-pull contract
and recovery-test edits. The Alchemy directory
`custom_media_agent_2_0/.tmp-rb31-review-20261029` contains SQLite test state;
its creator is unconfirmed, so preserve it and exclude it from any release diff.
This task also left Bridge `.tmp-rb32-tests/` after interrupted Windows tests;
it is test-only and must be excluded from any release diff. Other Bridge
changes appeared after the initial status: `docs/README_开发边界与文档导航.md`,
`src/render_bridge/agent/hatchet_sidecar.py`,
`docs/implementation/HATCHET_ENDPOINT_ISOLATION.md`, and `.tmp-rb33-testtemp/`.
Their author is unconfirmed; preserve them and exclude them from RB32. Review
diffs before editing; never reset, clean, overwrite, rebase, commit or publish.

## Frozen architecture

- Alchemy remains authoritative for user/project access, planning, review,
  native result registration, billing and delivery.
- VPS Bridge Source API/BridgeStore owns Bridge task and artifact state. The
  Agent journal is recovery evidence, not a second queue.
- Local Agent makes short outbound HTTPS requests. No relay server, SSH tunnel,
  shared DB/filesystem, callback or second queue.
- Read-only offer is not execution permission. Existing claim/start, attempt,
  upload/commit and receipt/ACK rules remain authoritative.
- Fallback is allowed only after explicit pre-admission rejection. Accepted or
  unknown tasks and tasks with artifacts/receipts recover under the same task.
- `node_pull` does not consume an old Hatchet outbox; changing mode on the same
  ledger is not migration. Keep unresolved tasks on their endpoint, ledger and
  profile. A deliberate VPS cutover uses a new data directory. Keep one serial
  local node; multi-node scheduling is out of scope.

## Risk and workflow

D0: topology and recovery contract are fixed in RB30 and Bridge API-pull docs.
I2: dispatch, persistence and recovery interact across repos. A2: credentials,
durable tasks, billing boundaries and remote exposure are consequential.
Use one writer at a time. Delegated audits are read-only; route provenance is
unverified unless runtime metadata proves otherwise.

### Correction model — end-to-end reference capacity (2026-10-30)

- **Intended:** every reference accepted by Alchemy's 16 MiB / 16 MP admission
  can reach the current Bridge without an earlier Bridge or proxy cap forcing
  fallback. The original bytes remain unchanged. Codex output remains a
  separate 16 MiB / 40 MP profile limit; fake-image output remains 1 MiB.
- **Observed mismatch:** Alchemy and its V3 project-reference path allow up to
  16 MiB / 16 MP, but Bridge runtime advertised/enforced 4 MiB / 2 MP. V2/V3
  also admit ordinary uploads up to 12 MiB. Thus valid references could be
  stored by Alchemy and then routed away from an available Bridge.
- **Authority:** align Bridge's per-reference byte/pixel limits with Alchemy's
  existing 16 MiB / 16 MP bound. Keep HTTPS Source transport at 32 MiB for
  overhead. The 1 MiB values are limited to fake-image output and bounded
  JSON-RPC control messages, not real image artifacts or reference uploads.
- **Minimal fix and evidence:** update Bridge constants, HTTPS template,
  capability contract, matching tests, and current runtime docs. Preserve the
  separate 16 MiB Node output limit and do not resize or transcode references.

### Correction model — revoked-node admission (2026-10-30)

- **Intended:** node-pull may admit a new task only when a currently active,
  registered node has a fresh heartbeat and reports the requested profile.
- **Observed mismatch:** revocation updates `node_registry.active` but retains
  heartbeat history. The node status projection recognizes the revocation, but
  node-pull `create_task` consults only the newest heartbeat, so a revoked
  node's old profile report can still pass task admission.
- **Authority:** the active `node_registry` row authorizes a node; a heartbeat
  is readiness evidence only. A heartbeat from a revoked node cannot make the
  scope accepting or satisfy task admission.
- **Minimal correction:** use only heartbeats joined to active registrations in
  the node-pull status/admission decision. Preserve heartbeat and task records;
  do not add cleanup, a queue, a lease, or a fallback path. Add one regression
  proving revocation closes admission without creating a task.

### 0. Preserve baseline

Record SHAs, worktree status and dirty paths; preserve state/config/media. Verify
all later imports resolve to the candidate worktrees.

### 1. Audit requirements and code paths

Read both AGENTS files, Alchemy RB21/RB26/RB30, Bridge API-pull, remote-source
and delivery-gap docs. Trace Alchemy source origin/token, shared paths, package
install/update and same-task recovery; trace Bridge source/node credentials,
mode, durable store, HTTPS routes, Agent start and restart recovery. Classify
each item as implemented, necessary local gap, or live-VPS-only evidence.

### 2. Alchemy readiness

Only repair a concrete gap. Preserve local defaults and API semantics. Test
pre-admission-only fallback, accepted/unknown same-task recovery and local
configuration compatibility. Do not read or write VPS secrets/configuration.

### 3. Bridge readiness

Only repair a concrete gap. Preserve default Hatchet behavior; keep `node_pull`
explicit, Source and Node credentials distinct, data private/durable, and the
local Agent outbound-only. Never run both dispatchers on one ledger. Test route
access, size limits, offline admission, response-loss recovery and cutover
boundaries.

### 4. Cross-repo simulation

Run isolated HTTP processes with FakeRenderer: Source create → durable task →
Agent pull/claim/start → artifact transfer → Alchemy native-registration
fixture → same-receipt ACK. Include relevant response-loss/restart, stale node,
full queue and workspace rejection. No real provider calls. Record exact SHAs,
import paths and task/attempt/receipt identities; no accepted/unknown task may
create a replacement task or API generation.

### 5. Final read-only audit and report

Freeze exact diffs for review against this plan, repository rules and evidence.
Report pass/fail/not-run separately. VPS TLS/proxy/firewall, deployed
permissions, Windows power-loss durability, real Codex output, Veyra billing and
rollback remain later live acceptance gates.

## Progress

| Phase | Status |
|---|---|
| 0 Baseline | Complete: candidate SHAs and pre-existing changed paths recorded; no destructive Git operation. Candidate HEADs remain unchanged. |
| 1 Audit | Complete: Alchemy's 16 MiB / 16 MP reference admission exceeded Bridge's former 4 MiB / 2 MP input contract, causing valid references to fall back before task creation; Bridge proxy also omitted Node API and old remote-source wording implied a tunnel. |
| 2 Alchemy | Complete for local regression: no production code gap to repair. Final scoped Render Bridge suite passed 417, skipped 1. Two stale native-reference assertions were aligned with the current 16 MiB / 16 MP admission contract; the 12 MiB V3 upload ceiling remains unchanged. Prior candidate tests also reported 69 passed/1 skipped, and targeted unknown-task/node-unavailable, queue-capacity, workspace-scope and unchanged-byte regressions passed. No VPS files or secrets were accessed. |
| 3 Bridge | Complete for local code/config evidence: after the revoked-node admission fix, the full Bridge `tests/` suite passed 289, skipped 1. Bridge input matches Alchemy at 16 MiB / 16 MP, Source proxy has 32 MiB transport headroom, and Node accepts the existing 16 MiB output. Exact-16-MiB Source upload→Node download, pixel boundary, generated schema, node-pull admission/profile/stale-heartbeat/revocation, queue bound, TLS binding, and response-loss/recovery tests passed. Python compilation and diff checks passed. Nginx syntax and live ingress remain unverified because neither Nginx nor a running Docker engine is available locally. |
| 4 Simulation | Complete for synthetic local acceptance: separate Bridge runtime and Node pull Agent processes served a FakeRenderer image through Alchemy transport, then Alchemy ACKed the same receipt. Task `task_91f0ab8f018044d2a3e0b318538ff99a`, attempt `attempt_fe964f6c80aa4ff784df9ffbd6fe734e`, receipt `receipt_5e949812337d43d1b56e31fa32d54727`; original SHA-256 `cbce5ce6a9faa31d7ba4001981ac51f098ab6fa21ac1052f7c974d698c66cb9e`, dimensions 48×32, delivery ACK accepted. The existing remote-contract script separately passed its HTTP loss/restart assertions after explicit GC before Windows temp cleanup; it exercises the old Hatchet fixture path and is not the node-pull E2E. |
| 5 Audit/report | Complete for local scope: independent read-only audits covered Bridge API/domain/persistence, Agent recovery, configuration/install and remote deployment wording; they found and helped isolate the revoked-node admission defect fixed in this phase. The prerequisite range was reviewed by subsystem, not commit-by-commit. A direct node-pull entry point was added to Bridge README/runtime docs and independently checked. Candidate diffs remain dirty and must be reviewed as scoped changes only; unrelated pre-existing paths and scratch evidence remain excluded. |

Prior focused results were Alchemy 69 passed/1 skipped and Bridge Agent/runtime
23 passed, with imports from the candidate worktrees. This turn's focused
Bridge tests passed: 12 selected tests in one run included 10 passes and two
incorrect unittest class selectors; the corrected config/queue run passed 4/4.
The exact-size, node-pull and recovery focused runs passed independently. These
are not full-suite or VPS acceptance. One initial Windows run of the existing
cross-process contract reached its final temp-directory cleanup but returned
WinError 32 for the Alchemy journal SQLite file. A rerun that called
`gc.collect()` before the normal temporary-directory cleanup emitted the
contract's `PASS` result and exited successfully. This script uses the older
Hatchet fixture path and is supporting evidence only, not the node-pull E2E.

Final scoped Alchemy command used the candidate's `custom_media_agent_2_0` venv
and ran `tests/render_bridge_primary` plus the listed `tests/test_render_bridge_*`
routing, native, recovery, diagnostics and admin files: **417 passed, 1
skipped**. It used a short system-temp `--basetemp` because placing pytest's
deep temporary directories under the long Windows worktree path exceeded the
Windows path limit for journal lock files. A first run also inherited the
active local Bridge endpoint/token/workspace environment and produced
configuration-mismatch failures; the final run cleared those runtime variables
and passed. The two old native-reference cases that still asserted the former
1 MiB / 1 MP rejection boundary were updated: a valid >1 MiB original is now
accepted, while rejection is tested beyond the current 16 MP boundary. The
ordinary V3 upload cap stays 12 MiB. No production code changed in this final
test pass.

Final scoped Bridge full suite: **289 passed, 1 skipped**. Both final suites
were run against candidate imports; they are local code evidence only and do
not establish VPS deployment, TLS ingress, paid Codex execution or Veyra
billing acceptance.

The node-pull audit found and fixed one concrete prerequisite defect: after
node revocation, the retained heartbeat could still admit a fresh task even
though capabilities reported no accepting node. Status and admission now use
only heartbeats joined to active node registrations. Regression evidence proves
capabilities close, the original origin still returns its same task/attempt,
and a new origin is rejected with `node_unavailable` without adding a ledger
row. The focused test passed, the independent re-audit passed, and the full
Bridge `tests/` suite passed. A repository-root run also collected optional
Hatchet compatibility experiments; 14 of those failed in the borrowed Alchemy
venv because it has no `hatchet-sdk` distribution. Those experiments require
their separate pinned environment and are not part of the passing Bridge
`tests/` result.

Bridge checkpoint `cbc9a4c18c3c72b29820e0e609543119c4f42f1a` contains 43
commits after merge-base `73dd31209f5b7b85b7f6f4363e795ae8f07cf535`; current
node-pull HEAD `a971ef830e998475005833bd64d0fdae07726ac3` adds the 44th. The
prerequisite range was reviewed by subsystem, not commit-by-commit, and must
not be rewritten as part of this work.
Bridge checkpoint
`cbc9a4c18c3c72b29820e0e609543119c4f42f1a`
contains 43 commits from merge-base `73dd31209f5b7b85b7f6f4363e795ae8f07cf535`;
the historical range was not audited commit-by-commit and must not be rewritten
as part of this work.

### Local node-pull recheck (2026-10-30)

An additional isolated cross-process smoke used the exact Alchemy and Bridge
candidate worktrees above, Bridge runtime on `127.0.0.1:18887`, a separate
Node pull Agent process, independent temporary ledgers, synthetic credentials,
and the `fake-image` profile. Alchemy transport created one Bridge task;
the Agent rendered and uploaded the synthetic original; Alchemy verified and
downloaded it, then acknowledged the same receipt. The saved artifact was
432 bytes, PNG, 64×48, SHA-256
`a27bd82137b7abb97088a281d3adae87cf428be2ca206fb33f7ea4dee6001494`.
Bridge recorded task `task_eff3105d70c242fba809d4f31e835171`, attempt
`attempt_dba2c5b091da4e91bae61781eb4f9ba4`, and receipt
`receipt_715232a9b3d34d47b94f660f82de10c9`; the final task state was
`artifacts_ready` and the receipt ACK was accepted. Both temporary processes
were stopped after the run. This confirms the local HTTP pull/transfer/ACK
contract, not Codex image generation or the public V1/V2/V3/Lab product route.

The bundled desktop executable returned `codex-cli 0.164.0-alpha.11.1`, which
the candidate Bridge deliberately does not accept. The explicit npm
`codex.cmd` executable returned `codex-cli 0.163.0`; version and
`app-server --help` checks passed. This did not perform an app-server protocol
exchange or establish image capability. A no-task local codex-image handshake
using that explicit executable reached Bridge admission `enabled` with the
node `available`; the profile correctly reported
`production_verified=false` / `availability=attention`. The temporary Agent
configuration had the previously authorized acceptance booleans enabled, but
those settings are not new runtime proof. No task or generation was started.

The candidate V2 ASGI application then started with its isolated temporary
`V2_DATA_DIR`, the same local Bridge endpoint and the main checkout's existing
V2 interpreter. `GET /api/v2/health` returned HTTP 200 and `status=ok`; Bridge
admission was enabled and the node was available. No image task was created.
The captured response is in the local scratch evidence file
`.tmp-localwire-e2e-20261030/v2-api-result.json`; the isolated Bridge ledger
has zero tasks, attempts, receipts, or acknowledgements. The harness requested
termination and waited for its temporary API/Bridge/Agent child processes;
the listening ports were closed afterward. The V3/V1 frontend was not started,
and no public V1/V2/V3/Lab product generation, review, or billing flow was
exercised. Genuine Codex image execution and those product-route acceptances
remain open; do not treat this phase as VPS-ready acceptance.

#### Authorized real Codex single-image attempt

One real single-image request was submitted through the candidate Alchemy
transport to the isolated local Bridge runtime and the local node-pull Agent,
using the explicitly selected npm `codex-cli 0.163.0` executable and the
`gpt-6.1-sol` model. Bridge accepted exactly one task and one attempt:
`task_7eebcb31d10f400aa6e9908ac14ebbf5` /
`attempt_1107fecc756443fc913076cd99118d65`. Alchemy recorded route `bridge`
with reason `bridge_primary`; it did not fall back to the API provider.

The task is **not a successful image acceptance**. The durable Bridge state is
`execution_unknown`, with one attempt and zero receipts or acknowledgements.
The Agent attempt directory contains the same task's persisted Codex thread and
turn IDs, but no completed image item, original artifact, or completion record.
The matching local Codex rollout shows that the model invoked the host
`image_gen` tool through `exec`; that tool returned `aborted by user after
15.6s`. The rollout then ended with `turn_aborted` reason `interrupted` after
about 34 seconds. No image result reached the Bridge Agent. The recorded
immediate failure point is the host image-generation tool call
returning `aborted by user`; the evidence does not establish who triggered the
abort or its deeper cause. Bridge admission and Alchemy routing had already
succeeded for this task. A same-task recovery result is not present in the
retained evidence. No second Bridge task or attempt was created for this
request, and no API regeneration was recorded for this unit. No image or
billing result is claimed.

For comparison, the retained local Bridge runtime has a prior completed task
`task_ebdf29b2f9df461a80bc04d073d807ad` /
`attempt_cd5e547c8c99400aa49a12ac6beb1ab3`, executed with `codex-cli 0.163.0`.
Its Agent completion record contains `imageGeneration` and `turn/completed`
events; the original PNG is 3,073,158 bytes, 1254×1254, SHA-256
`d0136414e2913c44281e3773b44c6a23de6a434fa1fe92357e9c69d98caeb61c`. The
Bridge ledger records `artifacts_ready`, a committed receipt, and accepted
delivery ACK for that same task/attempt. This is direct evidence that the
local Codex-to-Bridge artifact path has worked before; it does not certify the
current candidate revisions or the current interrupted task. The source
records are retained under
`D:\AI\Alchemy Media Agent System\.runtime\render-bridge-local\state\bridge-data\bridge.sqlite`
and
`D:\AI\Alchemy Media Agent System\.runtime\render-bridge-local\state\agent-state\executors\task_ebdf29b2f9df461a80bc04d073d807ad\attempt_cd5e547c8c99400aa49a12ac6beb1ab3`.

Keep the original task, attempt, Bridge ledger, Agent journal, and Codex rollout
for reconciliation. The result establishes that the Alchemy-to-Bridge route
and task admission worked, but local real Codex execution/recovery did not pass.
Do not deploy this candidate to VPS until the same-task outcome is reconciled
and a complete original-image download and receipt ACK is evidenced. This
failure does not invalidate the separate synthetic HTTP transfer/ACK pass or
the V2 health smoke.
