# RB24: VPS-to-local Bridge verification boundary

## Intended topology and correction model

Alchemy and its Veyra account/billing authority run on the VPS. Render Bridge,
its dispatcher/worker and the already-authorized Codex CLI remain on the user's
computer. Alchemy makes server-to-server source API calls; browsers do not receive
the Bridge source token. No shared disk, database, user session, Codex credential,
or Bridge-to-Alchemy callback is required.

The local adapter is not rewritten for this topology. Reference bytes are uploaded
and bound by hash; the Agent creates its own local reference paths. Alchemy retrieves
original result bytes and checks the receipt before native registration and ACK.
The difference needing evidence is the network/deployment boundary, not a second
image-generation implementation.

Existing ASGI checks cover HTTP handlers but do not traverse a socket or restart a
server process. The minimal correction is to retain those checks and add a bounded,
repeatable loopback TCP check. It must never be described as real TLS, WAN, Windows
CLI, Veyra or paid-generation acceptance.

## Automated cross-process check

Using the companion's locked test environment:

```sh
python scripts/verify_render_bridge_remote_contract.py --bridge-checkout /path/to/alchemy-render-bridge
```

The script imports Alchemy from its own checkout, starts the companion's actual
source API in a child process on loopback, and uses the real Alchemy HTTP client.
Temporary databases, synthetic image bytes and public fixture tokens are the only
inputs. It does not load production configuration, invoke a CLI, call a model,
contact a billing service, or modify deployment settings. The synthetic execution
fixture operates on its temporary Bridge store; it is not an actual Agent test.

It checks:

- Invalid bearer rejection and cross-source/workspace lookup rejection.
- Reference upload, same-origin replay and a single synthetic execution permit.
- Original result byte, SHA256, MIME and decoded-dimension agreement.
- A successful artifact download whose TCP response is discarded; recovery downloads
  the same result without a second task.
- A successful ACK whose response is discarded; durable reconciliation retries the
  same ACK without a second generation or native registration.
- A successful create whose response is discarded; the original task is found by
  origin rather than submitted again.
- Actual Bridge process shutdown: admitted work remains Bridge-owned; only a fresh,
  unsubmitted unit receives pre-admission API fallback.
- Restart from the same Bridge database and endpoint, preserving task identity.

The fixture requires exactly two task-creation HTTP calls for its two admitted
units, despite the three dropped responses. Its server startup, socket handlers,
whole verification and child termination are bounded. It closes clients and child
processes on failure as well as success. The native-wire CI job runs it after the
existing ASGI adapter check against that job's exact pinned companion revision.

## Real remote acceptance still required

This is a deployment checklist, not permission to configure a network, create
credentials, expose ports, change TLS settings or run paid generation.

1. Establish a stable trusted HTTPS **origin** reaching the local Bridge source
   API. Alchemy currently accepts a root origin, not an arbitrary URL path prefix,
   query, embedded credential or redirect-to-login flow. A VPS loopback address
   points at the VPS itself, not the user's computer. Use the companion's source-only
   reverse-proxy guidance; do not expose Codex debugging, node/dispatch endpoints or
   engine/database administration through the public source endpoint.
2. Configure only the source role credential on Alchemy. Its source/workspace and
   endpoint must agree with the control configuration. Retain Veyra/user identity
   authority on the VPS and node/dispatch/CLI credentials on their original side.
   Never copy a local development `.env` over production authentication settings.
3. Use isolated fixture state and a separate approved test service for initial
   remote tests; do not copy local in-flight ledgers and change their endpoint to
   pretend they are new remote jobs. Endpoint/workspace/profile changes deliberately
   reject recovery under a different scope.
4. From the actual VPS runtime, verify trusted certificate/hostname, authorization,
   all required methods, content types, binary uploads/downloads and error bodies.
   Redirects are not followed and ordinary proxy environment variables are ignored
   (`trust_env=False`). Do not disable certificate checks to get a green result.
5. Test interrupted upload, admitted-create response loss, interrupted download,
   ACK loss, local sleep/restart and loss of Internet. Unknown accepted execution
   must stay pending/reconcilable, not become a fresh API task. Recovery should use
   the original origin/task/attempt/receipt and debit identity.
6. Test representative authorized product images and the declared reference/output
   limits, queue saturation, storage pressure and cleanup protection. Small fixture
   pixels do not certify large real inputs or multi-user capacity.
7. Verify ordinary users A/B and administrator permissions through production-style
   login/access bridging. Test insufficient funds, delayed billing and lost billing
   response with controlled test accounts; no cross-user results or duplicate debit.
8. Only after the synthetic remote checks pass, authorize bounded real CLI calls
   for V1/V2/V3/Lab. Record the route, actual original bytes/dimensions, owner,
   product review/publication and final debit outcome. Successful image return alone
   is not full acceptance.

## Timeouts and service availability

Current source-client connect timeout is 3 seconds and read/write activity timeout
is 5 seconds. The latter is not a five-second total generation deadline or total
file-transfer limit. Generation uses asynchronous task status. The existing defaults
are unchanged by this test work; evaluate actual first-byte delay, proxy buffering
and transfer stalls before tuning them, and keep any later budgets finite.

A disconnected computer can cause *new, demonstrably unsubmitted* work to fall back
according to the existing product policy. It cannot authorize migration of admitted
or unknown work. Display pending/reconciliation state accurately instead of describing
all such cases as a fresh upstream failure. A local computer remaining online is an
operational dependency, not a guarantee established by these simulations.

## Completion boundary

Passing this runner proves the tested source HTTP and recovery semantics across
processes. It does not prove trusted remote access, actual VPS configuration,
Windows power-loss durability, account validity, real tool arguments, image quality
or real billing. Those remain separate pre-deployment acceptance receipts.
