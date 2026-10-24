# RB04: authorized frozen references and three synthetic output sizes

## Scope

Continue local feature HEAD `78410e2b`. Read-only GitHub verification on
2026-10-20 confirmed published `fd37ea53723bbb3aba8a8a455415b99204818d2b`
has the identical tree `95565e0e750981972327621355c316a6cc6cf70e`.
No reset or duplicate-history merge is needed.

Add only to the explicitly enabled native-test entry:

- Zero to two ordered, existing uploaded originals owned by the authenticated
  user and already bound to the selected project.
- Exact output presets 1024x1024, 1024x768 and 768x1024.
- Continue fake-image revision 1, one PNG, quality auto, review-only registration,
  no automatic selection, formal delivery or billing change.

The existing Alchemy reference admission and canonical frozen plan remain
authoritative. The adapter must not select, crop, resize, compress, reorder or
replace reference bytes. Inputs outside Bridge v1's PNG/JPEG, single-frame,
1 MiB and 1,048,576-pixel limits are rejected explicitly.
Canonical plans that require unsupported fidelity or other options remain
blocked rather than having those requirements silently removed.

Bridge already supports ordered reference uploads and these dimensions. Its wire
operation remains `image.generate`; this is not a new `image.edit` or mask API.
The read-only Alchemy projection's refs-present `image_edit` label must not be
misrepresented as a supported Bridge editing operation.

## Planned changes

1. Extend the opt-in native plan identity/admission with ordered upload IDs and
   size. Expose a read-only authorized-reference picker, preserving old square,
   no-reference tasks and normal Generate defaults.
2. Freeze with the existing Doc322/materializer authority; re-read exact
   originals through the native facade. Persist frozen input bytes/order/hashes
   and stable Bridge input keys in the module before upload.
3. Validate fake/manual output dimensions against the frozen request, not
   hardcoded square dimensions. The later Codex extension records decoded
   original dimensions instead; see RB06. Keep candidate persistence and
   existing review-only continuation.
4. Add reference and size selectors only to native-test. Display that synthetic
   output does not visually use the references.

## Acceptance and stopping point

Run focused native/preview and affected old-path regressions. Run independent
Alchemy/Bridge HTTP with two distinct originals, horizontal and vertical sizes,
actual native registration and confirmed accepted acknowledgment. Check reference
order/hash, the profile-specific output-dimension contract, repeated task/import idempotency and basic
rejection for unowned/unbound/changed/oversize inputs. One independent scoped
review, then stop expanding scope.

Use Bridge Agent + FakeExecutor for staged-reference hash evidence, rather than
the older `run_fake_once` shortcut that does not inspect references. FakeExecutor
checks transfer/order/hash but returns a deterministic synthetic image with
`synthetic_not_conditioned_on_references` provenance. Passing this milestone is
not image-editing, reference-fidelity, real model, real review or billing
acceptance. No cloud Codex login, Bridge runtime change, old default UI change,
merge, PR or production deployment is included.

## Acceptance receipt: 2026-10-20

Functional tree: `eedf195cc561336296b7aedb808d9ba608c32905`.
Bridge remained unchanged at `be9fe313155f5ddd18815a1d083da7b1b887dbf0`.
The combined contract and key old-path regression command passed **186 tests**:

```sh
python -m pytest -q \
  tests/test_render_bridge_*.py \
  tests/test_api_smoke.py::test_http_smoke_image_revision_and_providers \
  alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py \
  alchemy_creative_agent_3_0/tests/test_v3_scenario_runtime_and_product_api.py \
  alchemy_creative_agent_3_0/tests/test_v3_generic_export_review_gate.py
```

Run with the existing isolated mock-provider wrapper and fresh test storage,
not production or prior baseline data. Evidence:
`alchemy-media-agent-cloud-dev/logs/bridge-reference-final-contracts.{log,xml}`.
JavaScript syntax and `git diff --check` passed. One independent read-only review
of the integrated tree found no blocker in the bounded authority/idempotency
scope. Existing unrelated baseline failures described in RB01 were not changed
or newly rerun; this is not an entire-repository-green claim.

Actual independent HTTP acceptance used the full Alchemy host and its real native
gateway factory, Bridge runtime server, and actual `NodeAgent(HttpNodeClient)`
with `CountingFakeExecutor`. Session owner 7, Brain canonical sign-off and
external review were explicit test doubles. Two sequential tasks each used two
distinct authorized PNG/JPEG originals; the vertical task reversed their order.

- 1024x768 output SHA256:
  `31119154fe922051629971a48dbeab283b50cc8d1b851954e6616c824b12b41f`.
- 768x1024 output SHA256:
  `fb8a2b866c1f2c453968229120a9fc9d39d84de924190afb06bc68baaec92356`.
- Agent-staged original bytes, order and hashes exactly matched the Alchemy
  frozen originals. No transcoding, crop or reference substitution occurred.
- Each request, despite 13 repeat submissions and 11 Agent replays, produced one
  native plan/output, one renderer start, one accepted ack and one review-only
  invocation. Totals: two Bridge tasks, attempts, receipts and acks; four inputs.
- Both outputs carried `synthetic_not_conditioned_on_references` provenance,
  remained ineligible for formal delivery, and caused zero debit/usage calls.
- Services stopped; source files were unchanged during the run.

Evidence and the bounded replay harness are outside source Git at
`alchemy-media-agent-cloud-dev/bridge-reference-joint-check/`;
the final run is `run-20261020-163953-2/`. Its `report.json` links native IDs,
exact originals/output hashes and mocked boundaries; adjacent source hashes,
state snapshots, receipts, Agent evidence and HTTP logs retain the checks.

The feature/manual CI's existing browser job now also collects a third
intercepted-API test for the shipped native selector's order, size, repeated
submission identity and clearing on project change. All three browser tests
collect successfully; local Chromium remains unavailable due the earlier OS
restriction, so no local pixel/click pass is claimed. CI results must be checked
after publication. Real model/reference-fidelity, real review, real billing and
deployment acceptance remain outside this milestone.
