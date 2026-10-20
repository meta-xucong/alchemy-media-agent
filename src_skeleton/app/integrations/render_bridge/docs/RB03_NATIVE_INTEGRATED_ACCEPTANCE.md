# RB03: restricted synthetic native integration acceptance

Date: 2026-10-20. Alchemy baseline: `6556a6ba`.
Integrated code tested: `186ab0cce93609c2050fee5ba43def97c0aec3e5`.
Bridge HTTP server: `be9fe313155f5ddd18815a1d083da7b1b887dbf0`.

## What is complete

The default-off host module now has two deliberately separate entry points:

- `/render-bridge-preview`: manual test-prompt/image preview, never native
  registration and never an accepted acknowledgment.
- `/render-bridge-native-test`: explicit synthetic native development request,
  authenticated project owner only. POST to
  `/api/integrations/render-bridge/v1/native/tasks` accepts only a stable client
  key, project ID, user input and explicit synthetic-test acknowledgment.
  The server creates the plan, freezes its canonical prompt and fixes the
  supported profile/options. Browser-supplied owner, metadata, profile or image
  options are rejected.

Native support is limited to `fake-image` revision 1, one 1024x1024 PNG,
quality auto, no references/fidelity/background/moderation/compression options.
Enablement additionally requires `ALCHEMY_RENDER_BRIDGE_NATIVE_ENABLED=true`;
the overall module remains `ALCHEMY_RENDER_BRIDGE_MODE=disabled` by default.
The native entry does not accept unauthenticated loopback-preview mode.

The coordinator persists plan/origin/import/ack identities before effects,
looks up uncertain outcomes, and only sends `accepted` after the Alchemy-owned
gateway confirms an actual output plus native job-result checkpoint and matching
original hash. A Bridge receipt, downloaded file or mock acknowledgment cannot
stand in for registration. Normal Generate cannot render a server-marked Bridge
plan; ordinary unmarked jobs keep the original behavior.

Native candidate validation/persistence and shared review-only continuation are
reused. No default provider fallback, renderer retry, automatic selection,
formal delivery, MCP guard relaxation or new billing behavior is introduced.
Fake pixels remain ineligible for formal selection/export/memory promotion.
The one durable execution-audit entry is deduplication evidence, not Veyra usage.

## Integrated tests

The final combined command passed **158 tests** (46 deprecation warnings):

```sh
python -m pytest -q \
  tests/test_render_bridge_*.py \
  tests/test_api_smoke.py::test_http_smoke_image_revision_and_providers \
  alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py \
  alchemy_creative_agent_3_0/tests/test_v3_scenario_runtime_and_product_api.py \
  alchemy_creative_agent_3_0/tests/test_v3_generic_export_review_gate.py
```

This includes 26 preview, 10 native coordinator, 17 native freeze, 24 native
registration and 14 native planning tests. The native tests cover 100 identical
receipts and concurrent replay, native response loss, output checkpoint recovery,
unknown planning without another Brain call, no resurrection after cancellation,
server-owned plan markers, default-None checkpoint behavior, unchanged ordinary
Generate, no renderer in review-only, and zero debit/usage appends.

Run with the repository and `src_skeleton` on `PYTHONPATH`, isolated temporary
V1/V3/module storage, mock provider, and real Brain/vision/provider credentials
disabled. JavaScript syntax checks for both shipped scripts and `git diff --check`
also passed. A separate native-worker selection of 80 existing MCP/review/scenario
tests passed. This is not a claim that the entire historical repository is green;
the known baseline failures and browser limitation remain recorded in RB01.

## Actual independent HTTP acceptance

The final run used the full Alchemy `app.main` host with its real native gateway
factory, a separate Bridge uvicorn process, and actual loopback HTTP. The test
session, Brain sign-off and external review were explicit test doubles. The
Bridge FakeRenderer was invoked exactly once. No Alchemy runtime module imported
the Bridge Python package or opened its database; only the external fixture
driver operated Bridge's own fake executor and inspected evidence.

Observed:

- Repeated HTTP submission and ten post-completion replays reused one module task.
- Exactly one new native plan, one native output, one review-only invocation,
  one native execution audit, one Bridge task/attempt/receipt/accepted ack.
- No reference upload, second renderer invocation, selection or formal delivery.
- The accepted ack contained the actual native registration reference
  `v3_output_204525a3d6c2e324855d`.
- Persisted native image was PNG 1024x1024 with SHA256
  `d5237ec496a9e8abddc54fade9ef960a4483bf7f6262724ea43523a8210c0182`,
  matching the Bridge original receipt and deterministic fake pixels.
- Cancel after confirmed registration returned 409 rather than deleting or
  claiming cancellation of an already registered result.
- Veyra debit calls: 0. Billing usage appends: 0, matching current V3's
  zero-credit stub. Real billing is not accepted.
- Existing V3 shell and both optional static entries returned 200.
- Both fixture processes were stopped. No production data or service was used.

Evidence is retained outside Git in the cloud validation directory
`alchemy-media-agent-cloud-dev/bridge-native-joint-check/run-20261020-142300/`:
`report.json`, `source-hashes.json`, `commands.json`, state trail, native record
snapshots, registration journal, Bridge receipt/counts, PNG and HTTP logs.
The adjacent `run_native_http_check.py`, `alchemy_fixture.py` and
`bridge_fixture.py` reproduce the same isolated test with the sibling checkouts
and cloud safe-environment wrapper. The first fixture run stopped before render
because its diagnostic serializer assumed a Pydantic job rather than a dataclass;
only that external test fixture was corrected. Product code was unchanged.

## CI and unaccepted capabilities

`.github/workflows/render-bridge-regressions.yml` runs only for the feature branch
or manual dispatch. It has read-only repository permission, no production secret,
no deployment and mock-only dependencies. One job runs the combined contracts;
another uses Chromium and fully intercepted synthetic API responses to smoke-test
the shipped preview UI. No CI result is implied by committing this workflow.

Local Chromium was denied by the cloud OS; rendered browser/click/navigation
acceptance has not passed locally. The native test UI has static HTTP/syntax
coverage, not a rendered browser acceptance claim. Preview browser smoke is
delegated to the feature CI.

Real Codex/Midjourney login and tool capabilities, real Brain/vision quality,
real rendering parameter support, real billing, cross-VPS/TLS operation and
production rollout remain unverified. Free-text quality/format instructions
are not an accepted real-tool parameter contract. This milestone completes only
the explicitly restricted synthetic developer path, not production readiness.
