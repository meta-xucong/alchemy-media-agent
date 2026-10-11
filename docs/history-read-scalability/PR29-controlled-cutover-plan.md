# PR #29 Controlled Cutover Readiness Plan

## Goal and current phase

The total goal is to make the merged PR #29 state safe to activate on the VPS.
This phase closes code and procedure blockers; it does not activate a release
or mutate production data.

Read-only inventory on 2026-10-11 reported active release
`5a33c05e3f54dbef786eb179973ec1407511b4e4`, an ancestor of main, persistent V1
and V2 SQLite databases, and successful SQLite quick checks. This narrows the
old RAM-only concern, but does not prove every live in-memory state has a
durable counterpart or provide a production cutover receipt. The current V1
and V2 history databases did not yet contain all target PR #29 read-index
objects. These are observations, not permission to stop services or evidence
that production is ready to switch.

## Correction model

### Intended behavior

1. Candidate preparation writes only the immutable candidate release and its
   image/runtime artifacts. It never installs dependencies into, writes a
   manifest into, or changes the active release.
2. The production operation has two distinct checks: read-only preflight checks
   storage identity, migration/import state, active jobs and free-space budget;
   after fencing writers and taking one frozen backup epoch, preparation runs,
   then read-only verification checks those same roots while services remain
   stopped. Preparation success on a fixture is not production readiness.
3. Writer fencing includes V1 API/container, V2 API and workers, inline/async
   consumers, and the V3 storage-maintenance timer/service. The operation must
   account for startup recovery effects and refuse queued, running, claimed,
   stale-recoverable, or otherwise ambiguous work unless an explicit recovery
   disposition has been recorded. If any writer cannot be fenced, it stops.
4. Before any candidate process can start, a failed preparation can restore the
   complete captured set of affected SQLite databases and source files while
   writers remain fenced. Exact compatibility of the old `5a33…` reader with
   the target schema must be verified on an isolated copy before claiming that
   restarting the old binary against prepared data is safe.
5. Candidate startup itself can recover or mutate queued work. Candidate
   consumers and public admission therefore remain held until target indexes,
   local health, static assets, and configured storage bindings are verified.
   Check every candidate unit's environment-file/drop-in ordering before any
   candidate service starts; after consumers start, check all live process
   roots and API ownership flags before public admission. After any candidate
   writer is allowed to run, never restore a stale snapshot over its writes; use
   forward repair or a separately reconciled recovery plan.
6. The legacy in-place deploy route must fail before any environment, source,
   container, history file, or service mutation. All production activations use
   the guarded candidate/activation path.

### Authority and supporting evidence

- SQLite repository/history/favorites databases and their source files remain
  the business authorities. Read indexes and count buckets are derived state.
- The candidate SHA and its immutable tree are the release authority.
- Read-only preflight and database verification are supporting evidence. A
  healthy HTTP endpoint alone does not prove the indexes are ready.
- A prepared index is not permission to deploy. Activation repeats read-only
  verification against the exact live storage roots immediately before switch.

### Independent audit correction model (2026-10-11)

The frozen read-only audit returned `FAIL/HOLD` with seven findings. The
observed mismatches, owning layer, and repair authority are:

| Finding | Observed mismatch | Owning layer and authoritative rule | Minimal complete repair |
|---|---|---|---|
| Lab work inventory | The cutover guard inventories V1 `jobs`, V2 tasks/leases, and V3 jobs, but omits durable `lab_sessions`; startup recovery may rewrite queued/running sessions. | Durable business state owns active-work status. Unknown/malformed state blocks; queued/running work blocks admission. | Add read-only Lab session inventory and tests for queued, running, terminal, malformed, and missing schema cases. |
| V2 API background sync | The candidate API disables inline queue processing and startup GitHub sync but can still start `ResourceSyncScheduler` through `V2_ENABLE_REMOTE_GITHUB_SYNC`. | The API never owns queue or remote-sync background work; the dedicated task and sync workers own those responsibilities across deploy and rollback. | Install a persistent API-only systemd environment contract, verify its exact files and effective process environment, and retain it after success or rollback. |
| Effective storage identity | Cutover derives roots from `/etc/alchemy/alchemy-v2.env`, without proving systemd drop-ins and running API/worker/sync-worker processes use those roots. | The live process configuration and canonical resolved paths define the storage authority; the env file alone is supporting evidence. | Before fencing, inspect active process environments; after installing candidate unit contracts but before starting any candidate service, inspect systemd `EnvironmentFiles`/drop-ins and require API/worker/sync-worker roots to agree with backup/prepare/verify roots. Recheck live process roots after startup. Unknown/relative/mismatched overrides fail closed. |
| Rollback state machine | Pre-candidate rollback can continue restoring links/images/restarting old services after an earlier restore/contract failure, and may remove the public maintenance flag even when rollback is incomplete. | Restored data plus a verified old runtime contract are prerequisites for reopening traffic. Any rollback failure keeps writers stopped and public maintenance closed. | Make rollback monotonic and fail-closed: stop on any incomplete restore/contract/repoint/service/health check, preserve the maintenance gate, and only clear it after old stack readiness is completely verified. |
| Candidate image identity | Candidate workflow builds Compose `latest`, then tags a SHA-named alias; activation verifies tag existence and source checkout SHA but not image content. Concurrent/stale builds can bind the wrong image. | Expected commit SHA must be bound to the immutable image artifact itself. | Serialize shared build/tag/activate operations with a VPS-side lock and stamp/verify `org.opencontainers.image.revision` on the actual candidate image before activation. |
| Disk peak budget | Current backup estimate covers current DB/WAL/source bytes and reserve but omits index-growth and restore-temporary peaks. | Cutover capacity must cover all simultaneous copies and configured reserve, not just the final backup size. | Estimate backup, conservative target-index growth, restore temporary copies, and reserve on their actual filesystems; reject unknown/unbounded estimates. Document remaining estimator limits. |
| V2 source/index evidence | Verifier checks schema, internal counts, marker/receipt presence, and non-empty sources but can report verified without proving retained source/index parity. | Existing migration receipts are historical import receipts, not full current-state digests; markers remain no-replay authority. | Separate structural consistency from source parity. Add a read-only reconciliation result that accounts for ongoing source/SQLite writes and duplicate IDs; if historical receipts cannot prove parity, return `inconclusive` and block deploy instead of claiming verified. Never replay/import to satisfy verification. |
| Maintenance timer lifecycle | The activation path stops an already-active V3 storage-maintenance timer but only rollback restores it. | Successful cutover must preserve the pre-cutover timer policy; a previously inactive timer stays inactive. | Check the historical-state digest while the timer is stopped, then restore and verify its prior active/inactive state after public smoke checks; a restore mismatch re-closes the public gate. |

The total objective remains deployable code and procedure. This correction
phase is accepted only when every finding has a targeted regression, the
independent audit passes on the frozen corrected diff, and the deployment
scripts remain production-read-only in local dry-run tests. This does not
authorize a VPS cutover.

The operator explicitly authorized persistent V2 API worker ownership on
2026-10-11. The activation workflow therefore installs
`/etc/alchemy/alchemy-v2-api-runtime.env` and the matching API systemd drop-in;
both set inline queue processing, startup GitHub sync, and the API's remote
sync scheduler to false. The dedicated `alchemy-v2-worker` and
`alchemy-v2-sync-worker` remain responsible for those jobs. The contract is
kept after candidate success and is re-established after rollback; it is not a
temporary cutover override. This changes the runtime contract by explicit
operator authorization and must be reflected in unit/process verification.

Independent review also found that live process-root verification originally
ran after queue/sync consumers started. The corrected activation checks all
three candidate systemd units' environment-file/drop-in ordering before
starting any candidate service, then checks live process roots and API flags
after startup but before public admission. Emergency closure verifies either
the maintenance 503 plus stopped writers, or stops Nginx and freshly rechecks
all writers before verifying the listener is inactive; it emits `CLOSURE_FAILED`
if neither state can be proven. The V3 storage-maintenance timer stays stopped through the durable-state
digest check and public smoke tests, then returns to its prior active/inactive
state before success. A restore failure re-closes the public gate.

### Correction decisions before implementation

The intended cutover invariant is one frozen production epoch: every durable
and in-memory writer is accounted for; every preparation and verification
command addresses the canonical roots actually used by the stopped services;
the verified candidate image is the image started; and no failure path can
remove the public maintenance fence before either candidate readiness or a
fully restored and re-verified old stack.

Observed mismatches belong to four authorities:

1. **Work authority:** durable V1 jobs, Lab sessions, V2 tasks/leases, and V3
   jobs/planning operations all participate. Unknown state is not idle.
2. **Runtime/storage authority:** the running process environment plus its
   systemd unit/drop-ins and container mounts define the roots. Config files
   are inputs, not proof of effective values.
3. **Artifact authority:** the requested commit is only source identity. The
   image revision label and the candidate tag must bind the actual bytes to
   that commit; a mutable `latest` tag cannot be the build-to-activate handoff.
4. **Cutover epoch authority:** a checksummed backup manifest is the only
   rollback snapshot. Once an old or candidate writer may have run against a
   changed store, restoring an earlier snapshot is unsafe; the maintenance
   fence stays closed until the matching runtime/data state is verified.

The previous rollback behavior duplicated the decision in several independent
flags and continued after errors. Replace it with a small monotonic state
machine: `FENCED -> OLD_STACK_RESTORED_AND_VERIFIED -> PUBLIC_OPEN`. Any failed
restore or verification stays in `FENCED`, keeps all writers stopped, and
retains the 503 gate. Candidate startup transitions to forward recovery and
never to snapshot restore.

The disk estimate must be computed per filesystem from a single frozen file
inventory and include: backup copies of SQLite plus WAL/source files, target
index growth, the largest same-filesystem restore temporary copy, and the
operator's free-space reserve. If a component cannot be bounded from the
inventory/configuration, the gate must return `unknown` and block; a guessed
constant is not evidence.

V2 migration receipts attest to a completed import event, not the equality of
the current SQLite index and mutable source files. The verifier therefore
must report two independent dimensions: internal structural verification and
source/index reconciliation. It must not replay an import, update a receipt,
or treat receipt row count as current index count. Where subsequent supported
writes/deletes make retained source non-authoritative or historical provenance
insufficient, parity is `inconclusive` and deployment remains blocked until a
separate integrity receipt is available.

Minimal implementation sequence: first land failing focused tests for all
seven audit findings; then implement the work-state/config/artifact guards,
rollback gate, capacity proof, and truthful V2 verification result. Re-run the
new tests plus existing deployment/history suites, freeze the exact diff, and
request a new independent read-only audit. No production action is part of
this correction loop.

### Test-first acceptance for the correction

Before production edits, add deterministic failing tests for each finding:

1. Lab queued/running/malformed session states block; terminal session states
   pass; missing or malformed session schema fails closed.
2. Candidate V2 API environment disables inline queue, startup sync, and the
   resource scheduler; dedicated sync-worker remains separately controlled.
3. Storage-root evidence rejects systemd drop-in/process mismatches, missing
   process evidence, and relative paths; matching API/worker/sync-worker roots
   pass without emitting secret values.
4. Rollback fault injection at every restore/contract/repoint/start/health step
   proves no subsequent old writer starts and no maintenance gate is removed.
5. Candidate image label mismatch and concurrent shared-release lock contention
   block before retagging or service changes.
6. Disk budget fixtures include backup bytes, index growth, restore temporary
   bytes, and reserve across distinct filesystems; insufficient or unknown
   bounds fail closed.
7. V2 verifier distinguishes internal structural validity from source/index
   parity, detects missing/extra/duplicate-conflict rows where the retained
   source is authoritative, and returns inconclusive where historical receipts
   cannot prove current parity. Verification must never write/import.

## Bounded implementation scope

1. Add a read-only V2 history/favorites verifier that cannot create a database,
   import JSON, or alter receipts. Keep the existing prepare command explicit.
2. Add a cutover support utility for read-only active-work inspection and
   SQLite backup/restore verification. Reject malformed Job/Task states rather
   than interpreting them as idle. Never print credentials or record payloads.
3. Update the guarded activation workflow to require explicit maintenance
   confirmation and a positive operator-selected disk floor. Order gates as:
   read-only preflight → fence/stop writers and consumers → verify stopped state
   → consistent backup of affected SQLite plus source/sidecar evidence → index
   preparation → read-only verification against the same roots → candidate
   switch/start with consumers/admission held → local readiness checks → admit
   traffic. Any uncertain writer or startup side effect blocks.
4. Preserve rollback data semantics: before any candidate writer starts, restore
   the full captured database/source set only while all writers stay fenced.
   Do not automatically roll back data after candidate recovery/consumption has
   begun. Verify the exact old release behavior against a synthetic target
   schema before defining the pre-admission restart path.
5. Make candidate runtime preparation candidate-only. Do not run `pip install`,
   manifest writes, or recursive ownership changes against the old release.
6. Fail closed in deprecated direct deployment entry points and explain the
   supported guarded sequence.
7. Add deterministic tests with stubbed commands/storage proving failed gates
   do not switch releases, stop services, mutate the active runtime, or accept
   an unverified index. Update this document with exact evidence.

## Out of scope

- No VPS stop/restart, live index build, data migration, release switch, or
  deployment in this phase.
- No real model/provider calls or image generation.
- No database replacement/cleanup, business-data reconciliation, or legacy
  RAM-state exporter.
- No unrelated V1/V2/Lab product behavior changes.

## Acceptance gates

1. Candidate artifact preparation has no write to the active release or
   production database. The guarded cutover may write derived history indexes
   only after the public fence, complete writer stop, and verified backup.
2. Missing/wrong maintenance confirmation, SHA mismatch, active/queued/stale
   work, incomplete writer inventory, backup failure, low disk space,
   index-preparation failure, or verification failure cannot admit traffic.
3. A preparation failure restores the full captured SQLite/source set while
   writers remain fenced; no old reader is restarted until its target-schema
   compatibility behavior has been verified.
4. A successful dry-run fixture creates verified backups, prepares V1/Lab and
   V2 indexes, and passes read-only verifiers without using production paths.
5. The guarded operation verifies configured V1/V2 roots before candidate
   startup and verifies all live V2 process roots after consumers start but
   before public admission. It holds public admission and queue/sync consumers
   until readiness checks pass. No legacy route can bypass it.
6. Focused tests, relevant deployment/storage regression suites, syntax checks,
   diff review, and an independent read-only audit pass.
7. Final status reports code readiness separately from production activation.

## Known operational boundary

The live VPS inventory is read-only evidence. It does not constitute a current
backup, a completed target-index build, an idle-job receipt, a complete writer
fence, or authorization to stop services. Those occur only in a later
explicitly requested deployment window. Code/procedure readiness is distinct
from production cutover eligibility; only the latter requires the live frozen
epoch preparation and verification to pass.

## Implementation and verification receipt

The guarded activation implementation now applies these additional hard gates:

- After the public maintenance response is verified, it stops the V3 maintenance
  timer and any service that raced into `active`, then verifies the timer,
  service, V1 container, V2 API/worker/sync-worker are stopped before backup.
- It enumerates the affected SQLite files once for both backup selection and a
  conservative backup-space estimate, includes SQLite WAL sizes and source
  files, retains the operator-selected free-space reserve, and checks that the
  reserve remains after backup creation.
- The operator free-space input is bounded to a safe integer range. Any
  unknown status, failed inventory, inadequate disk budget, or incomplete
  backup still aborts before index preparation.
- The API-only persistent systemd contract disables inline queue processing,
  startup GitHub sync, and the API resource-sync scheduler. It remains installed
  after candidate success and is re-established before old services restart on
  rollback. The actual API process flags are checked before and after consumer
  startup; the dedicated V2 workers remain stopped through local health,
  storage verification, and frontend binding checks. Public admission opens last.
- V2 source/index parity uses disk-backed reconciliation and caps an individual
  JSONL record at 4 MiB. An oversized record blocks the cutover verifier without
  changing source or index; this bounds verifier input memory per record rather
  than claiming zero transient allocation.
- Emergency rollback closure verifies either maintenance 503 plus stopped
  writers, or a stopped Nginx listener plus stopped writers. If neither closure
  state can be proven, it emits a distinct failure instead of claiming the
  service is closed.

Focused local evidence on the implementation worktree, 2026-10-11:

- Cutover guard, activation ordering/rollback, and release runtime tests:
  45 passed.
- V1/Lab history index, strict import, retention, delete atomicity, and favorite
  migration/retention tests: 209 passed (six existing FastAPI deprecation
  warnings).
- V2 read-only verifier/source parity, history paging/admission/counting, and
  migration/favorite tests: 300 passed.
- Frontend history-demand tests: 150 passed.
- All 7 GitHub Actions workflows parsed as YAML; all 25 workflow Bash run steps
  and both legacy deployment shell scripts passed Bash syntax checking;
  `git diff --check` passed.
- These are local tests, not GitHub CI, real browser heap measurement, or
  production rehearsal. Independent read-only review of the exact timer/closure follow-up passed with no new code blocker. No VPS service, live database, candidate release, or public traffic was changed.


## Incremental correction: d7ca deployment-gate findings

A read-only review of `d7ca089a8715376aab2df4a97167ef84133b5e49` found two
deployment blockers and two conditional procedure gaps. The correction keeps
the existing authorities intact:

1. **V1 path binding remains strict.** `storage_root` stored by the prepared
   index is authoritative. Preparation and both pre-start and post-start
   verification now run from the candidate image with the same bind mount at
   `/app/.media_storage`; post-start verification mounts the data read-only.
   No host-path exception was added.
2. **V2 writes use the systemd service identity.** The V2 history/favorites
   prepare, read-only verify, and explicit directory/SQLite/JSONL write probes
   run as `alchemy`. The SQLite probe opens existing databases read-write and
   obtains/rolls back an immediate transaction; the file probe opens existing
   source files append-only without writing. Backup snapshots remain private
   (`0600` files, `0700` directory), while schema 2 manifests preserve each
   original regular file's uid, gid, and mode for restore. Restore applies and
   verifies those attributes on a temporary file before atomic replacement;
   metadata-less schema 1 manifests fail closed.
3. **The declared revision must match the build-context source.** Candidate and
   activation workflows compare `HEAD` against the index/worktree using
   `git diff HEAD --`, and reject non-ignored untracked files except the
   runtime `src_skeleton/.env`. This check runs before candidate build and
   before activation. Ignored runtime and virtual-environment paths remain
   governed by repository ignore and Docker build-context rules.
4. **Rollback restores inactive timer policy too.** If the timer was inactive
   before cutover, rollback stops and verifies both timer and oneshot service
   inactive before restoring the public Nginx configuration. Any command or
   verification failure keeps the public gate closed.

### Regression and evidence

The correction adds tests for the previously failing container-path, service
identity, permission-probe, original file metadata, staged/untracked source,
and prior-inactive timer cases. The Git test uses a disposable repository and
proves `git diff --quiet HEAD --` detects both staged and unstaged edits.
The backup tests keep private backup permissions separate from restored business
file permissions.

This correction is limited to deployment preparation and recovery. It does not
run the workflow against VPS paths, activate a release, or establish production
readiness. The deployment workflow still requires an isolated cutover drill and
operator authorization before any production switch.


### Local validation receipt (2026-10-11)

- Deployment guard, activation contract, and runtime guard: 55 passed.
- V1/Lab history index and deployment/maintenance regressions: 100 passed,
  6 existing FastAPI deprecation warnings.
- V2 history prepare, scalability, and migration atomicity: 205 passed, run
  from the V2 project directory to avoid the shared `app` package-name
  collection collision.
- Both guarded workflows parsed as YAML; each embedded remote Bash script
  passed `bash -n`; `vps_cutover_guard.py` compiled; `git diff --check` passed.
- An independent read-only audit reviewed the corrected fixed diff and passed
  all four finding scopes, including the post-start V2 verifier identity.

The local host is Windows, so the V2 `alchemy` UID/GID and POSIX filesystem
permission effects were not exercised here as an actual Linux service account.
The implementation performs those checks at cutover time and fails closed; a
Linux isolated permission fixture and production cutover drill remain separate
acceptance evidence. No VPS operation, commit, push, merge, or provider call was
performed in this correction phase.

### Incremental correction: 221dbe29 deployment-gate follow-up

A read-only audit of `221dbe29f5b74b0048c702b73722b70836a9e3b1` found two
remaining deployment-gate gaps. The correction preserves read-only business
data verification and makes the SQLite write probe exercise actual transactional
page writes:

1. **V1 post-start verification keeps the container path but permits SQLite
   sidecars.** The data directory bind at `/app/.media_storage` is writable in
   this short-lived verifier container so SQLite can create required WAL/SHM
   files when they are absent. `prepare_v1_history_index.py --verify` still
   opens the database with URI `mode=ro` and only reads/compares index state;
   the workflow does not use `immutable=1` or a host-path exception.
2. **V2 write permission probe performs rollback-only DDL and DML.** For each
   existing database it begins an immediate transaction, creates a unique
   temporary table, inserts one row, rolls back, and confirms no table remains.
   This tests the SQLite write/journal path rather than merely obtaining a write
   reservation. The probe contains no application-table mutation and commits
   no changes; failures fail closed as `write_probe_database_unwritable`.

Regression coverage includes both DELETE and WAL mode normal-write controls,
no-residue/data-preservation assertions, an unwritable main database file, an
unwritable DELETE/WAL journal directory, and a workflow contract proving that the
post-start bind is writable while the verifier itself stays in `mode=ro`.
POSIX permission tests are skipped on Windows and when run as root, because
those environments do not enforce the tested denial condition. They must run
under an unprivileged Linux identity as part of independent cutover validation.
This remains code/test evidence only; no VPS or production cutover was run.

#### Follow-up validation receipt

- Deployment/cutover plus V1/Lab storage and migration regressions: 304 passed,
  4 skipped (the permission-denial pytest cases are skipped on this Windows
  host), 6 existing deprecation warnings.
- The same SQLite permission-denial cases were exercised separately in a local
  Linux container as uid 1000: mode-0444 main databases were rejected in both
  DELETE and WAL modes, and unwritable DELETE/WAL journal directories were rejected.
  Normal-write controls passed in pytest for both modes, with original data
  unchanged and no probe table left behind.
- A closed-connection WAL database with absent `-wal`/`-shm` sidecars opened for
  `mode=ro` SELECT in a writable temporary directory, confirming the precise
  sidecar requirement behind the workflow change.
- Independent read-only diff review passed. Both guarded workflow YAML files,
  shell syntax checks, Python compilation, and `git diff --check` passed.
- No VPS action, merge, or deployment was performed. Linux probes used isolated
  temporary databases and do not substitute for service-account cutover
  rehearsal.
