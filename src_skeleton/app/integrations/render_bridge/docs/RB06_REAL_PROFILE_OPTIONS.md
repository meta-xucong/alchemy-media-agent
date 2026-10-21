# RB06: bounded native real-profile options

## Scope and authoritative evidence

Start from clean Alchemy `041ebd97` / published PR #37 head `5443222b` (identical
tree `ef1348d4cff9db46279d90f35b74945a63d2b28a`) and Bridge `5c157ff9` /
published `c43f8acc` (identical tree `0ccdec5dbffe801d5774f35f8463d89f289aba81`).
Independent feature worktrees own Bridge and Alchemy's native service changes.
Legacy CI/fixture repairs are a separate workstream, not scope for this module.

Pinned Codex CLI 0.163.0 exposes no structured image-generation quality,
output_format or input_fidelity controls in the official
[TurnStartParams](https://raw.githubusercontent.com/openai/codex/rust-v0.163.0/codex-rs/app-server-protocol/schema/json/v2/TurnStartParams.json),
[ThreadStartParams](https://raw.githubusercontent.com/openai/codex/rust-v0.163.0/codex-rs/app-server-protocol/schema/json/v2/ThreadStartParams.json)
or [configuration schema](https://raw.githubusercontent.com/openai/codex/rust-v0.163.0/codex-rs/core/config.schema.json).
Assistant outputSchema is not an image format setting; localImage detail is not
generation input fidelity. Do not invent those APIs or treat text instructions
as enforced renderer controls.

## Finite implementation

- Add optional `parameters.image_options` with its own `schema_version: "1"`,
  required quality `auto` and output_format `png` or `jpeg`. Omission retains
  old v1 request bytes/hashes. Explicit fidelity is unsupported, including auto.
- Quality auto means no requested quality tier, not a quality guarantee. Format
  is a decoded **original artifact postcondition**, not native parameter control.
  Reject a mismatch without relabeling, transcoding or fresh generation.
- Negotiate each profile's versioned descriptor before native planning. Old v1
  servers remain usable for the old fake/PNG subset, never silently for real
  profiles or new JPEG options. Manual profiles accept no references.
- A separate native profile allowlist defaults to fake-image. Explicitly enabled
  Codex/manual profiles use the existing frozen canonical plan and registration
  authority, with immutable profile/format binding and bounded original limits.
  Canonical high quality/fidelity, including identity-reference-derived fidelity,
  remains rejected; it must not be rewritten to fit the adapter.
- Real pixels are not labeled mock or verified. Every result in this development
  integration remains review-only and ineligible for automatic/formal delivery.
  Default generation, shared review/billing authority and local Agent gates stay
  unchanged. No account configuration or real provider is used in cloud tests.

## Acceptance and stop

Test mock Codex protocol lifecycle, PNG/JPEG exact-byte registration, profile
negotiation and truthful rejection, manual reference refusal, old identities,
repeat execution/import and already-generated original recovery. Run focused
default-path regressions, actual HTTP with mocked tools/Brain/review and one
independent review, then stop. Report separately: integration code completed;
upstream controls unavailable; real local account/tool capability unverified.


## Explicit operator configuration (not performed by cloud tests)

Both `ALCHEMY_RENDER_BRIDGE_PROFILES` and the narrower
`ALCHEMY_RENDER_BRIDGE_NATIVE_PROFILES` must include each requested profile;
the latter defaults to `fake-image`. Native routes still require
`ALCHEMY_RENDER_BRIDGE_NATIVE_ENABLED=true` and the existing enabled module,
authenticated project owner and configured Bridge connection. Example profile
lists are `fake-image,codex-image` or `fake-image,midjourney-manual`; changing
configuration does **not** authenticate or verify an executor. The independently
configured Bridge service/node must advertise the same compatible profile and
typed descriptor. Existing Agent capability/acceptance gates remain required.

Use `/render-bridge-diagnostics` for a read-only capability check, then the
optional `/render-bridge-native-test` profile and PNG/JPEG selectors. Only an
explicit submission invokes the configured Brain. A real profile needs the new
`acknowledge_native_development` acknowledgement; an old fake acknowledgement
alone never authorizes it. Manual references must be explicitly deselected.
An incompatible/missing descriptor stops before planning, with a stable code.
The old fake/PNG v1 wire without the additive descriptor remains supported.

Quality `low/medium/high`, any explicit `input_fidelity` (even `auto`/null), WebP,
and identity references whose canonical plan derives fidelity are not supported.
They fail instead of being stripped, substituted or sent as a false native tool
control. Native maximums remain the same three sizes and two 1 MiB original
references. Output originals are bounded to 1 MiB for fake and 16 MiB for real
profiles, plus the same one-megapixel/dimension bounds. No re-encoding occurs.

The server capability page distinguishes code support from configured profiles,
HTTP declarations from local measurements, and original-format validation from
native renderer control. Imported doctor reports still cannot enable a profile.

## Integrated acceptance (2026-10-21)

- Alchemy feature contracts and key default-path regressions: **257 passed**.
  Command: `python -m pytest -q tests/test_render_bridge_*.py
  tests/test_api_smoke.py::test_http_smoke_image_revision_and_providers
  alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py
  alchemy_creative_agent_3_0/tests/test_v3_scenario_runtime_and_product_api.py
  alchemy_creative_agent_3_0/tests/test_v3_generic_export_review_gate.py`.
  Run under the established isolated mock environment and unique storage.
- Bridge full suite: **141 passed** (`python -m unittest discover -s tests -v`),
  including actual fixed mock-process JSONL, completed-artifact recovery,
  mismatch retention, no second turn, old omitted wire identity and manual input.
- Independent bounded code review found no actionable introduced issue.
  JS syntax, schema reproduction and whitespace checks passed.
- The feature workflow automatically includes the new contract files. Browser
  tests collect **11** cases, including profile/format selection and explicit
  manual-reference refusal. Local Chromium remains unavailable under cloud OS
  restrictions; no retry/bypass was made. Actual GitHub browser/Windows checks
  are separate, not pre-declared green by this receipt.

### Actual HTTP proof, not just MockTransport

Independent full Alchemy and Bridge uvicorn processes used real loopback HTTP,
actual NodeAgent/HttpNodeClient, actual CodexExecutor with a **fixed Python mock
JSON-RPC subprocess**, and actual MidjourneyManualExecutor with a synthetic
original. Host session, Brain sign-off, external review and Codex capability
attestation were explicit test doubles. No account, real CLI or provider ran.

Code revisions: Alchemy `466bbc9b5bc427af1baac0d508a1b3cd738a0721`, Bridge
`1159150c8f85861553ea4e93b193fd2b4b186124`. Source hashes were stable during the
run. Three chains passed:

1. codex-image PNG, 1024×768, two ordered authorized reference originals.
2. codex-image JPEG, 768×1024, the references in explicitly reversed order.
3. midjourney-manual JPEG, 1024×1024, no references; explicit original import.

All three preserved exact typed options and original bytes/MIME/hash, performed
native review-only persistence, and left ACK pending while native confirmation
was held. Only after confirmation was accepted recorded. Real-profile candidate
flags were non-mock and locally unverified, never formal delivery eligible.
Each task underwent eight duplicate submissions and six Agent replays, still one
plan, output, receipt and ACK per task. Totals: 3 tasks, 3 attempts, 4 inputs,
3 receipts/ACKs, exactly 2 mock Codex subprocesses, zero debit/usage calls.
Both services stopped normally. Initial harness-only strict-null comparison was
corrected; the full successful fresh run is `run-20261021-022226-2/report.json`
under the separate `bridge-options-joint-check` acceptance directory, alongside
commands, source hashes, protocol logs and task/native evidence.

### Legacy regression repairs and stop

The separately repaired historical PR28 audit, history-browser state fixture,
V2 gateway fixtures and six earlier focused fixtures are integrated without
changing production behavior. The three Doc263 doubles found in the last
narrow MCP regression were also fixed by supplying the current `is_mock=False`
field and asserting its preservation; generated/finalizing and no-regeneration
assertions remain intact. That entire file passed 73 cases. Other repair evidence
includes V2 801, V1/API smoke 509, Node 185, source/SQLite 69 and focused legacy
fixtures 118. These are specific selections, not a full-repository green claim.

Code adaptation is complete for this restricted contract. Native quality tiers
and explicit fidelity are **unsupported by the pinned upstream protocol**, not
unfinished pass-through code. Real local authentication, image capability,
visual/reference fidelity, and billing remain **unverified**. This milestone
stops after the above main chain, repeat/recovery tests and one review.
