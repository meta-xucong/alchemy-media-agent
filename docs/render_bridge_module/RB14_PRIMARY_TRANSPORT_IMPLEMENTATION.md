# RB14: durable neutral transport implementation

Base: Alchemy a15ff3e; Bridge fff5244. Scope: implementation of RB13, not merge,
deployment, credential provisioning, or a claim of real-provider validation.

## Correction model

Existing access bridges only sign API/MCP identity, while preview/native Bridge
coordinators import V1 authorities. Neither can be used as the ordinary V2
transport. The authoritative new seam is a product-neutral Python package with
an independent SQLite journal and versioned HTTP calls. Product adapters own
fencing, billing, storage, checkpoints, review, and scheduling.

Each product/owner/unit has one immutable semantic digest (including ordered
reference hashes). A journal record precedes every external execution. Only a
first create's typed queue_capacity or bridge_draining rejection permits API
fallback. A lost create response and subsequent origin 404 remain Bridge-owned.
API execution has its own one-way durable claim, so API uncertainty cannot
cause duplicate execution either. Capabilities/health are admission preflight,
never authority to migrate already admitted tasks. Cancellation never falls back.

Artifacts are verified against receipt hash, length, MIME and decoded dimensions;
bytes are retained unchanged in the journal. A product confirms registration
before ACK. ACK failures are retryable without generation. Configuration is
default-off, token comes from environment, and already owned work ignores a
later mode disable but refuses endpoint/scope changes. No withdrawal endpoint
is used. Hard controls unsupported by revision 1 are rejected before create.

## Verification plan

Isolated HTTP fixtures and temporary journals cover disabled mode, immutable
identity, first-create queue rejection, generic errors, lost response + restart,
origin 404, concurrent admission claims, API execution claim, cancellation,
receipt integrity, deferred ACK, hard controls, and product import isolation.
Product integration and shared queue concurrency tests are separate evidence.

## Adapter API and configuration

Import only `render_bridge_primary`, never a product's integration package.
`PrimarySettings.from_env(product)` reads the authoritative shared nonsecret
control JSON at `control_path()`: environment
`ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG`, otherwise repository-root-relative
`.render_bridge_primary/control.json`. Existing admin mode and codex-image
allowlist enable primary. Tokens remain in `ALCHEMY_RENDER_BRIDGE_TOKEN` (or
explicit primary-token override); `ALCHEMY_RENDER_BRIDGE_URL`, when configured,
must match the control endpoint. `state_root()` uses
`ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT`, otherwise repository-root-relative
`.render_bridge_primary/ledgers`. Independent processes must use the same absolute
control/state paths. Product journals are separate; Bridge owns the global queue.

Each V1/V3/Lab host and the isolated V2 host runs a process-local, read-only
capabilities probe immediately at startup and every five seconds while the
primary profile is enabled. An unreachable or unauthenticated Bridge is retried
on the next interval; recovery is logged when a later probe succeeds. The probe
does not create tasks or change request routing, task ownership, or fallback
rules. Shutdown cancels the probe task.

Construct immutable `PrimaryRequest(product, owner_id, unit_id, prompt,
parameters, references, hard_requirements, binding_id=None)`. References hold
original bytes and MIME. Parameters use only revision-1 width/height/seed and
image_options. Hard requirements support explicit output_format, quality=auto,
exact_dimensions only where advertised exact, and exact advertised reference
semantics. Other meaningful controls force unsupported fallback, not stripping.

`await transport.resolve(request)` returns a `PrimaryResult`. A Bridge result
with no image must not invoke any API provider, even when terminal. A result
with an image contains original bytes/hash/dimensions. `claim_api(request)` must
win once before an enabled fallback provider call; `complete_api(request)` is
called after a durable product checkpoint. A fresh disabled result has reason
bridge_disabled and no journal, preserving the existing product path. Existing
ownership is checked before disable. `has_binding`/`has_unit` are read checks.

`acknowledge(request, registration_ref)` follows durable product registration;
ACK retry does not rerender. `cancel(request)` never withdraws to API. Products
own fencing, pending scheduling, stable unit IDs, result registration and billing
idempotency. `close()`/`aclose()` or async context management closes HTTP clients.
`pending_count(settings_or_root)` supports admin endpoint/scope-change guards.

## Initial local evidence

17 isolated tests pass (Python/pytest, temporary SQLite journals and MockTransport).
No accounts, credentials, live renderers, deployment or publication used. Includes
HTTP create-response loss, exact-origin recovery, generic 429 rejection, queue
proofs, concurrency single-create permit, API claim, semantic mutation, scope
change, stale health, pending counts, unknown cancellation and deferred ACK with
byte-for-byte originals. This is transport-level evidence, not four-product or
real Codex validation.

### Configuration validation correction

Review found that merely testing membership in an unvalidated profiles value
would accept a string, and independent V2 processes cannot rely on the admin
host's prior validation. Neutral settings therefore validate schema version,
mode, list-shaped distinct known profile IDs, endpoint syntax and transport,
and environment endpoint/workspace binding before any transport is created.
Only HTTPS or explicitly enabled loopback HTTP is accepted. Malformed saved
control fails closed rather than activating a route.

### Cancellation and standalone packaging correction

Product cancel endpoints only have authenticated product/owner/job IDs, not
frozen references. They now use `bindings_for(product, owner_id, unit_prefix)`
and `cancel_binding(product, owner_id, unit_id)`. The latter only touches an
existing journal row, sets a durable cancellation latch before HTTP, and never
creates a task or imports an artifact. Late pixels remain journal-owned but
are hidden from successful product import; accepted ACK is blocked. The owner
namespace is hashed in journal metadata. Product APIs must authorize the job
before calling this internal interface.

The neutral directory is independently installable with setuptools. For source
checkout deployments, use editable installation to preserve the shared
repository-relative control/state defaults. Noneditable installations must set
absolute ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG and
ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT identically in all product processes.

### Concurrent recovery correction

Independent review identified that an older queued response could overwrite
newer artifact metadata while SQLite retained the artifact BLOB. The journal is
the responsible layer: recovery writes must be monotone and must preserve
receipt/artifact/ACK identity and cancellation latches. The minimal fix merges
under BEGIN IMMEDIATE and prevents state regression; receipt acceptance also
binds attempt, profile revision and primary slot before byte import.

### Admission-limit correction

Review also found that dimensions beyond advertised Bridge limits would reach
POST and conservatively become unknown on a 413. These are knowable capability
mismatches, so prompt length, dimensions/pixel limits, integer seed range and
input length are checked before submission. Unknown POST failures remain owned;
this does not broaden post-submission fallback.

An already product-owned batch may encounter mode disable before its next new
unit. Explicit `claim_api` on that fresh disabled result creates the durable API
claim atomically; adapters may therefore protect partially owned batches without
forcing journals onto unrelated, wholly disabled legacy requests.

### Safe provenance completion

Bridge capabilities queue depth/limit are recorded as a timestamped diagnostic
snapshot, never used to decide admission. Product and selected profile were
already persisted. Results now explicitly distinguish the known Render Bridge
transport from unavailable underlying model evidence: actual_provider is
render_bridge with provider_evidence=transport_only; actual_model is null and
model_evidence=not_reported. The execution profile/revision are separately named.
Revision-1 receipts do not report an actual model, so no Codex model is invented.
Traditional API adapters retain responsibility for recording their real provider
and model. No token, owner namespace, endpoint, local path, or raw response is
added to provenance.

### Terminal-product ACK/cancel maintenance

Native registration now saves an immutable registration reference before the
ACK request. A response loss leaves a durable intent, not an abandoned delivery.
`await transport.reconcile_pending(limit=32)` retries only recorded ACK or
cancellation intents and returns checked/acked/canceled/pending/errors counts.
It never creates tasks, invokes a renderer, downloads pixels, or registers an
output. Callers may run this bounded maintenance while primary admission is
disabled; the original endpoint/workspace/profile must still match. Empty
ledgers and ledgers without intents do no network work. Origin-not-found after
an in-flight create remains pending, then the same remote task is canceled when
it appears. Native registration/ACK intent wins over a later cancellation;
a prior cancellation prevents new ACK intent. Reconciled terminal cancellation
no longer blocks configuration changes. `bindings_for(..., active_only=True)`
skips completed registrations/terminal units but still includes unregistered
original pixels so cancellation can suppress their later publication.
