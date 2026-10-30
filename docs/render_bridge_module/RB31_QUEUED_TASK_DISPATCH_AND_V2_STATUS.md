# RB31: Cross-product Hatchet dispatch isolation and V2 status projection

## Incident evidence and root cause

The exact V2 task `task_e162a1dc79824e1ca4a63a8ab05dce78` was admitted to the V2 Bridge ledger on `127.0.0.1:8798`. Its durable record remains `queued`, with no claim, start grant, start time, receipt, or terminal audit event. The 8798 outbox was acknowledged with Hatchet run `eaa0b0d0-3a18-4aea-89c6-b32fbe23f7cb`.

The Hatchet run was not simply unclaimed. Its callback ran on a worker whose Bridge URL is hardcoded by the 8797 stack supervisor. The worker queried its own `127.0.0.1:8797` ledger for the V2 task and got `404 not_found`, because that task exists only in the 8798 ledger. Hatchet retried the same run; a later attempt got `503 store_busy`, the Bridge API's single-operation semaphore response. The Hatchet run ended `FAILED` after two retries. `store_busy` is a separate transient contention response, not evidence of database corruption.

The root cause is one global Hatchet task name (`bridge-node-execute-v1`) used by independent Bridge endpoints with independent ledgers. Hatchet routes by task name, while the task payload contains only `task_id`; it has no Bridge endpoint/scope discriminator. Therefore a worker can consume a task created by another Bridge and query the wrong ledger. The worker heartbeat/listener data was misleading context, not the cause of this incident. Earlier claims that the listener never received the task or that a saved token mismatch caused the failure are withdrawn.

| Products | Bridge endpoint | Local ledger/source | Finding |
| --- | --- | --- | --- |
| V1, V3, LAB | `127.0.0.1:8797` | `primary-acceptance-source` | Share one endpoint and worker; this split-endpoint collision was not observed within these three routes. |
| V2 | `127.0.0.1:8798` | `rb27-local-source-20261026` | Shares the Hatchet task name with 8797 but not its ledger; this task hit the wrong endpoint. |

## Minimal fix

1. In Bridge, derive a stable Hatchet task name from the normalized Bridge URL. Dispatcher and worker use the same helper. Different Bridge endpoints then register different task names, while each endpoint keeps its current ledger, source identity, task payload, start latch, and receipt contract.
2. Keep V1/V2/V3/LAB product wait and generation rules unchanged. No API fallback, new retry, timeout, queue reset, or task migration is introduced.
3. In V2's authenticated image-job read, when a retryable `bridge_wait` record corresponds to a queued job in the active durable run snapshot, return the snapshot's queued status. This corrects the visible status projection only; it does not alter durable state or dispatch.

The Bridge code change routes future runs. A Hatchet run already created with the legacy fixed name is not migrated by changing the worker name. At the time of diagnosis, the exact V2 Hatchet run was terminal `FAILED`, while its Bridge task remained `queued`; this was a dispatch acknowledgement gap, not a completed or started generation.

After loading the endpoint-scoped worker and dispatcher, the original task was recovered once using the same `task_id`, `attempt_id`, and `dispatch_key`. The old outbox acknowledgement and old failed run were preserved. The new run completed through the 8798 endpoint; no new Alchemy job, Bridge task, attempt, or charge was created. Do not clear or recreate the task/ledger record. RB30 API-pull cutover applies to new deployment topology; it is not a recovery shortcut for this accepted local Hatchet task.

## Verification and limits

- Bridge agent contract suite: 14 tests passed, including URL normalization, endpoint separation, and identical task-name selection by dispatcher and worker.
- Alchemy V1/V3/LAB and shared transport regressions: 204 passed, 1 skipped. Alchemy V2 Bridge and owner-isolation regressions: 78 passed.
- Bridge's documented `unittest discover -s tests -q` run executed 289 tests: 287 passed, 1 skipped, and 1 errored when the configured HTTP-process test could not remove a Windows temporary directory still held by another process. Isolated reruns were inconsistent: one passed, and a later run hit the same cleanup error. This is a Windows test teardown issue; it is not evidence of a Bridge execution failure. The Bridge Hatchet endpoint-isolation tests passed in the full run.
- Independent review: PASS for the endpoint-specific Hatchet task name and incident model. The separate reviewer route was not independently verified.
- Live local V2 acceptance: passed with the exact existing job/task/attempt. The original V2 job `job_c901a0ee4afd` completed with one `render_bridge` output. Bridge task `task_e162a1dc79824e1ca4a63a8ab05dce78` reached `artifacts_ready`; receipt `receipt_4b2fa559540f49bf9577ce34f4a0def3` was accepted. The final PNG was 2,778,256 bytes, SHA-256 `4d7b02b98d0737e2d929999427f765efae4910820938c4fb2c47a5b3d799d1f2`, decoded dimensions 1254×1254; Bridge and Alchemy bytes/hash/dimensions matched exactly. This verifies dispatch, CLI execution, receipt, and product delivery. No visual-quality review was performed.
- The V2 endpoint-scoped worker and dispatcher were restarted from the Bridge feature worktree; V1/V3/LAB continue to share the separate 8797 endpoint. No GitHub push, merge, or VPS deployment was performed. VPS HTTPS, billing, Windows power-loss recovery, and production activation remain outside this acceptance.
- This local milestone does not push GitHub, merge PRs, or deploy VPS. VPS HTTPS, billing, Windows power-loss recovery, and production activation remain outside this acceptance.
