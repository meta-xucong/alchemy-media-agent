# Render Bridge native facade: restricted developer acceptance

Baseline: `6556a6ba5120fd5e17c6009f1161bd2213d2f979`, 2026-10-20.

## Supported scope and exclusions

This is an explicitly selected, default-off **developer integration** for one
Standard `image.generate` output: `fake-image` profile revision `1`, exact
1024x1024 / 1024x768 / 768x1024, quality `auto`, PNG, and zero to two ordered
current-project uploaded originals owned by the authenticated user. No explicit
fidelity, background, moderation or compression is supported. Every other profile
or option combination is rejected. Reference PNG/JPEG originals must be
single-frame, at most 1 MiB and 1,048,576 pixels; no silent resize or transcoding.
In particular `codex-image` is unverified and unsupported: text instructions to a
Codex executor are not proof of image-tool option support.

The complete supported path is plan-only -> canonical freeze -> Bridge fixture
execution -> native candidate/output checkpoint -> existing review-only flow ->
queryable native registration. Tests mock Brain sign-off and external review;
they do not claim real Brain, real renderer, real review quality or production
availability. Fake results are marked mock and are always withheld from formal
selection, export and memory promotion, even if a test review says pass.
The reference extension verifies original transport/order/hash, not image editing
or reference-fidelity effects. FakeExecutor does not condition pixels on images.

No default route, provider selection, MCP local-only permission, selection or
billing authority is replaced. The native module is optional. The integration
host owns the additive `main.py` factory/mount; the facade does not replace routes.

## Host composition and callable contract

Construct only inside the host's explicit default-off native module gate:

```python
facade = RenderBridgeNativeFacade(
    get_job_record=product_service.get_job_record,
    get_project_record=project_service.project_store.get_project,
    enabled=True,
)
gateway = NativeRenderBridgeGateway(
    facade=facade,
    service=product_service,
    project_service=project_service,
    journal_root=dedicated_native_journal_path,
    enabled=True,
)
```

The default constructor values are disabled. Use the project store's record
lookup, not the full project view, which can reconcile and save. The actor is a
positive integer from host authentication, never browser metadata or free owner
input. Strict HTTP bodies must reject arbitrary metadata, profiles and options.
Translate `BridgeNativeFacadeError` to its safe `code` and `status_code`.

Methods (all synchronous; `target` is `NativeFreezeTarget(project_id, job_id,
asset_id)`):

- `create_plan(actor_user_id, project_id, user_input, plan_key, *,
  uploaded_asset_ids=None, size='1024x1024')` returns `planned`
  with `target` and `plan_key`, `plan_blocked`, or `plan_unknown` with
  `retry_safe=False`. The caller must persist its stable plan key before calling.
  Only an explicit user request may invoke planning. This is the only native
  starting point; arbitrary pre-existing jobs are not converted into Bridge jobs.
  Ordered IDs and size participate in the stable identity; defaults preserve
  earlier square/no-reference identities.
- `plan_status(actor_user_id, project_id, plan_key)` returns `not_planned`,
  `planned`, `plan_blocked` or `plan_unknown`. Unknown plans are looked up by
  deterministic native job identity, never blindly planned again.
- `prepare(actor_user_id, target, *, execution_profile_id='fake-image')` returns
  `submission_ready=True`, canonical `prompt`, `prompt_sha256`, `image_options`,
  ordered `references`, `target_revision`, `frozen_request_id`, profile/revision,
  `test_fixture=True`, and `native_registration_connected=True`.
- `list_references(actor_user_id, project_id)` returns eligible current-project
  owned upload candidates and supported sizes without planning or mutation.
- `read_reference(actor_user_id, target, *, frozen_request_id, reference_id)`
  returns exact `content` bytes and `mime_type` after current frozen admission.
  A browser path or raw bytes are never used as native reference authority.
- `register_receipt(actor_user_id, target, *, import_key, frozen_request_id,
  receipt_id, original_sha256, artifact_bytes,
  execution_profile_id='fake-image')` returns `registered`, `import_unknown` or
  `rejected`, or raises a safe admission conflict. Only a confirmed `registered`
  response authorizes the module to acknowledge the Bridge receipt as accepted.
- `registration_status(actor_user_id, target, *, import_key)` queries the real
  native checkpoint and returns `registered`, `not_registered`, `import_unknown`
  or `rejected`. Retry exactly the same receipt only when `retry_safe=True`.
  Do not switch import keys, native IDs or receipts after an unknown response.
- `cancel_target(actor_user_id, target)` returns `canceled` before native result
  registration and marks the owned planned target blocked/cancel-requested. It
  returns `already_registered` after a native result checkpoint and never deletes,
  revokes or silently restores an existing result. The module may reject cancel
  after registration.

A registered outcome includes stable `native_registration_ref`, original and
normalized SHA256, initial `review_status`, `formal_delivery=False`,
`test_fixture=True`, `execution_audit_count=1`, `retry_safe=False` and the current
zero-credit billing description. Review progress remains the native service's
responsibility; the first registration outcome stays stable on replay.

The separate `RenderBridgeNativeFacade.freeze/read_reference` methods remain a
read-only diagnostic API supporting eligible Standard frozen references. They
never authorize dispatch and return `submission_ready=False`. Its original
registration placeholders remain unavailable; use `NativeRenderBridgeGateway`
for the restricted complete path, not those diagnostic methods.

## Existing authorities reused

`V3ProjectModeService.create_render_bridge_plan` calls the normal V3 planning
service and links the resulting job with existing project context/timeline
helpers. A typed server-only plan identity supplies deterministic job identity.
The public request sanitizer drops any attempted native marker. The marker can
only be issued by the dedicated plan-only method. Ordinary Generate returns
without rendering for that marker; ordinary unmarked jobs retain their original
flow. A blocked Brain result stays blocked. There is no automatic LLM call at
startup, prepare, registration, status lookup or retry.

The plan-only seam copies the already-issued Doc322 reference-plan snapshot into
its own frozen generation plan, with the same project binding. It does not
recompute a reference plan. Freeze calls the unchanged
`build_provider_generation_request` and
`ProductionImageGenerationProvider.materialize_final_prompt`, requiring
`remote_brain_canonical`. No free prompt is represented as Brain-processed.
Reference admission reuses existing project active-upload membership and upload
owner/readiness checks. The canonical materialized references must match selected
IDs/order/hash. Canonical requirements such as high fidelity remain blocked when
outside the supported subset rather than being dropped to fit the fixture.

`ProductionImageGenerationProvider._native_output_checkpoint_id` defaults to
`None`; normal providers therefore retain fresh output identity and the MCP
checkpoint branch is unchanged. The dedicated receipt provider supplies a
server-derived deterministic identity and returns only validated existing pixels.
The original provider `generate` still owns validation, normalization,
output-store persistence and candidate creation. The integration never writes
an output-store artifact directly.

The service extracts the existing candidate projection shared with MCP, stores a
FINALIZING native checkpoint, then calls the existing shared
`_resume_finalizing_generation_review(..., review_only=True)`. Review-only skips
renderer auto-retries. An optional current-target callback checks authority again
after review and before save; default callers retain the prior behavior. Native
registration itself performs no selection, export or memory operation.

## Deduplication, unknown outcomes and cancellation

One target-scoped journal binds actor, project/job/asset, import key, frozen
revision, receipt ID and raw hash before the native effect. Atomic replace and a
bounded cross-process file lock serialize writers. Deterministic native output
identity permits querying the actual output and generation-result checkpoint
after response loss or restart. A lone output checkpoint can safely be resumed
with the same binding; a committed result is not imported or reviewed twice.
Conflicting keys/bytes/receipts are rejected.

Plan intent is journaled before planning. If a native job was durably saved but
the response or project-link step was lost, lookup can reattach that same proven
job only while the project revision still matches. If no durable job exists,
`plan_unknown` does not invoke Brain again. Operator/user resolution may be
needed; this is deliberately not a new generic recovery state machine.

Every new native effect checks current owner, membership, active project,
cancellation/deletion markers and frozen request/project revision. Canceling a
planned target cannot be undone by receipt replay. A committed registration is
historical: lookup can report it without repeating an effect, but deleted or
ownership-transferred targets remain inaccessible.

## Billing boundary

Current V3 uses `V3BalanceAdapter`, a zero-credit estimate stub. This path accepts
that adapter only, performs no Veyra debit or `record_veyra_usage`, and does not
invent a charge. The one execution-audit entry is **deduplication/audit, not a
billing usage event or equivalent ledger**. The older Bridge document's
"one native result / one usage" assertion is not applicable as a billing
acceptance criterion to current V3. Real billing remains unaccepted/unverified.

## Verification

Focused fixtures use real V3 schemas, canonical materialization, native job and
output stores, real gateway/provider checkpoint and shared service continuation.
Only the planning sign-off and external review boundaries are mocked.

- Read-only facade: 17 tests for exact prompt/reference parity, no mutation,
  default-off, ownership, membership, revision, cancellation and unavailable
  diagnostic registration.
- Native registration: same receipt 100 times and concurrent replay produce one
  output and one execution audit; restart/lost response query the actual native
  checkpoint; conflicts, invalid profile/options/bytes and canceled targets fail;
  no rendering, Veyra charge, usage append or auto-selection occurs; fake results
  cannot formally select/export even with a passing test review.
- Plan-only: stable key creates one job/one planning call, lost responses do not
  rerun Brain, unknown outcome remains query-only, cancellation blocks import,
  browser metadata cannot spoof the marker, and ordinary unmarked Generate still
  follows its old path.

For a host-level fixture, reuse `planning_fixture.local_plan_with_mock_signoff`
in `tests/test_render_bridge_native_planning.py` and `native_fixture.mock_review`
in `tests/test_render_bridge_native_registration.py`. Canonical fixture authority
is defined in `tests/test_render_bridge_native_facade.py:target_fixture`.
