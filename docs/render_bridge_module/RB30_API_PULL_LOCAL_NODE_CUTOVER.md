# RB30: VPS Alchemy with a locally pulled Render Bridge node

## Objective and boundary

Run Alchemy and the Render Bridge control plane on the existing VPS. Keep the
Windows Node Agent, its local recovery journal, executors and Codex CLI on the
user's computer. The local Agent initiates short HTTPS requests to the VPS and
polls for work; no public port on the computer and no persistent SSH tunnel are
required.

The BridgeStore on the VPS is the sole Bridge task authority. The local Agent
journal is execution evidence and recovery material, not a second dispatch
queue. Alchemy continues to own user/project authorization, planning, review,
native result registration, billing and delivery. Source API request, task,
receipt and ACK schemas remain unchanged.

This supersedes the direct VPS-to-local-source-API transport option in RB24.
RB24's identity, byte-integrity, ACK and unknown-execution rules remain in force.

## Alchemy changes

1. Keep the existing `BridgeClient` and source API calls. Configure the existing
   source origin to the VPS HTTPS origin; do not add a second task broker or an
   Alchemy-side polling database.
2. Use RB21's shared absolute control and ledger paths for every Alchemy process
   on the VPS. Keep credentials in their existing protected configuration.
   Only the Bridge source-role token belongs to Alchemy.
3. Treat Bridge admission as available only when the VPS Bridge accepts work and
   the configured local execution node has a fresh heartbeat advertising the
   selected profile. A stale/missing node is a pre-admission unavailable result.
   Queue capacity remains an atomic BridgeStore decision.
4. Allow the existing API fallback only before Bridge task acceptance for the
   existing connectivity, `node_unavailable`, and `queue_capacity` outcomes.
   Once create may have been accepted, keep the original origin/task identity and
   reconcile it through Bridge. Never switch an admitted or unknown task to API.
5. Do not change product prompts, image parameters, product review, native import,
   cancellation, billing or delivery behavior for this transport change.

## Bridge changes required by this contract

The Bridge service on the VPS owns `/bridge/v1` and the durable task/artifact
store. The existing local Node Agent uses the node credential and short-polls the
VPS Node API. A read-only task offer does not claim or start work; the Agent then
uses the existing claim/start/upload/commit protocol. Only the Bridge execution
backend selected for this deployment may dispatch new tasks. The local pull mode
must not run the Hatchet dispatcher in parallel.

The local Node Agent uses the existing persisted start boundary, attempt identity,
unknown-state reconciliation and upload-only recovery. It sends each request
independently over HTTPS and reconnects after transport errors. A dropped poll is
safe to repeat. A dropped start, upload, commit or ACK response follows the
existing idempotent recovery rules.

## Cutover sequence

1. Freeze exact Alchemy and Bridge revisions. Complete their offline regression
   tests and the independent diff audit before publishing either branch.
2. Build an inactive VPS candidate. Preserve VPS users, Veyra configuration,
   media, databases and task history; do not copy local test databases or replace
   VPS `.env` files.
3. Provision Bridge's dedicated durable control, database and artifact paths on
   the existing VPS. Configure the Bridge source API for Alchemy and a distinct
   node credential for the one local Agent. Do not reuse the dispatcher token.
4. Publish only the required HTTPS source and node API routes through the existing
   TLS host. Keep the Bridge listener private to the VPS; do not expose the local
   computer, CLI, Agent journal, dispatcher, database or admin endpoints.
5. Start the local Agent in pull mode against the VPS origin. Verify its heartbeat,
   supported profile and poll response using synthetic tasks before opening
   Alchemy admission.
6. Run the repository's guarded VPS preflight and activation. Schedule the planned
   V1/V2 maintenance window; this path is staged but not zero-downtime.
7. Verify each product's route, original bytes/hash/dimensions, review, native
   registration, ACK, recovery and charge receipt. Do not infer Bridge success
   from an image appearing in the UI.

## Existing local work and rollback

Do not migrate the current local Alchemy or Bridge SQLite databases to the VPS.
First reconcile any local accepted task and pending ACK on its original endpoint.
Keep the local service available until that ledger is terminal and confirmed.

Before the new VPS Bridge accepts work, revert by returning Alchemy to its prior
release/configuration and keeping the local test service intact. After acceptance,
preserve the VPS Bridge database and artifact files and restore connectivity to
the same endpoint. Do not change origin/workspace/profile or let an older release
regenerate a task whose execution is unknown.

## Local acceptance evidence

Required synthetic test path: Alchemy source API client → VPS-shaped Bridge source
API process → local pull Agent process → FakeRenderer → artifact retrieval →
Alchemy durable native-registration fixture → same-receipt ACK. Test process and
HTTP response loss at poll, create, start, upload/commit, download and ACK; local
Agent restart; stale heartbeat; full queue; cross-workspace rejection; and verify
no second start or task after an accepted/unknown result.

This test does not certify real VPS TLS, Windows power-loss durability, live
Codex output, Veyra billing or production permissions. Those remain deployment
acceptance gates.
