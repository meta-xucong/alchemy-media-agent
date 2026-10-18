# Implementation Plan and File Map

Status: implementation complete after design-v7 corrections and final focused
code audit PASS. Local real-image acceptance and production VPS activation are
separate remaining release gates.

## Design correction model

- **Intended behavior:** four products use one unified text-gateway key, call
  Claude Sonnet 5.5 first, then automatically call Kimi K3 and GPT-6.1-sol on eligible
  primary-route failures, with bounded time and truthful provenance.
- **Observed mismatch:** V1's backup model field is not used to construct its
  actual candidate; V2 has separate main/fallback credential settings and
  conditional fallback gates; LAB has a provider list but provider-specific
  credential lookups; V3 retries only its current model and has no alternate
  candidate model.
- **Responsible layer:** text model configuration and provider/outlet routing
  in each product. This is not an image-renderer or visual-review defect.
- **Authority:** the ordered model choices and unified-key contract in Doc01
  remain authoritative. Existing stage schemas and V3 Brain ownership remain
  supporting product contracts. The user's explicit four-product failover
  requirement narrowly supersedes the V2 Claude-ownership rule only when a
  classified Claude route failure requires Kimi, then GPT as needed, to answer
  the same stage;
  preserve all available checkpoints, continuation, refusals, permissions, and
  backend isolation.
- **Minimal complete fix:** one logical secret per deployment/product boundary,
  explicit ordered model candidates using that secret, protocol-aware adapters,
  common failure classification, bounded deadlines, and regression evidence in
  all four products.

## Code-audit correction model

- **Observed mismatch:** V1/LAB passed an HTTP read-idle timeout as if it were
  a per-candidate wall-clock cap; `ask_llm_json_plan` lacked an outer hard
  deadline. LAB text could also use its stale legacy model field instead of
  V1's canonical primary. V2's GPT adapter omitted the configured semantic
  reasoning effort, and an old single-model fallback could preempt the ordered
  Kimi K3 then GPT-6.1-sol chain.
  V3 kept both model attempts only on success, losing route evidence when both
  failed. V3 code default (520s) also differed from explicit deployment
  examples (550s).
- **Responsible layer:** per-product candidate orchestration, protocol
  adaptation, safe terminal provenance, and deployment-budget documentation.
- **Authority:** Doc01 remains authoritative. HTTP-client timeouts are supporting
  transport controls; the outer monotonic candidate and logical deadlines are
  authoritative. V1's canonical model pair is authoritative for LAB text;
  LAB vision remains independently configured. The configured V2 effort is
  authoritative and must map to a supported GPT parameter. The ordered V2
  fallback list is authoritative over a deprecated legacy single-model value.
  Failure provenance must preserve every bounded candidate outcome after
  sanitization.
- **Minimal complete fix:** enforce an outer per-candidate `asyncio.timeout` in
  both V1 text planning paths and LAB; route LAB text/status through the
  canonical primary; pass V2 effort through the GPT adapter only for supported
  models and keep legacy candidates after the ordered list; attach and whitelist
  V3's bounded failure attempts through the runtime/product projections; clarify
  code-default versus deployment-override budget values.

## Ownership and file map

The Main session is the sole writer on the unique main checkout. Independent
agents may inspect frozen docs/diffs read-only. Do not create parallel writers
for shared settings or provider contracts.

Expected change surfaces (final exact list is recorded after implementation):

| Product | Main code/config surfaces | Preserve |
|---|---|---|
| V1 | `src_skeleton/app/config.py`; `src_skeleton/app/services/work_intensity.py`; `src_skeleton/app/schemas.py`; `src_skeleton/app/main.py`; desktop/mobile settings pages and scripts | image-provider credentials and selectors, V1 API contract except removal of per-model text secrets, work-intensity behavior |
| LAB | `src_skeleton/app/config.py`; `src_skeleton/app/services/alchemy_lab_llm.py`; root V1/LAB runtime schema and status projection | LAB task semantics and independent image/vision route |
| V2 | `custom_media_agent_2_0/app/config.py`; `custom_media_agent_2_0/app/schemas.py`; `custom_media_agent_2_0/app/services/claude_orchestrator.py`; V2-native runtime settings; `deploy/systemd/alchemy-v2.env.example` | isolated backend, checkpoint/continuation behavior when available, V2-specific prompts/contracts, independent image credentials |
| V3 | `alchemy_creative_agent_3_0/app/llm_brain/providers.py`; `alchemy_creative_agent_3_0/app/llm_brain/adapter.py`; `alchemy_creative_agent_3_0/app/scenario_runtime/runtime.py`; `alchemy_creative_agent_3_0/app/product_api/service.py` for failure attempt provenance projection | frozen Brain contract, execution budget, remote sign-off, fail-closed required Brain paths |
| Deployment/local config | `scripts/bootstrap_env.ps1`; `scripts/deploy_vps.sh`; `src_skeleton/.env.example`; local ignored `.env` files | no API-key values in tracked files; do not deploy to VPS in this task |
| Evidence | `tests/test_unified_llm_gateway_v1_lab.py`; `custom_media_agent_2_0/tests/test_unified_llm_gateway_failover.py`; focused V3 provider tests | provider calls in unit tests are mocked; real provider use is reserved for the post-audit V3 acceptance run |

Avoid introducing a shared backend import that makes V2 depend on V1. A small
provider-neutral contract may be repeated at independent product boundaries;
matching failure classifications and acceptance tests are the parity guard.

## Configuration migration

1. Add `LLM_GATEWAY_API_KEY` and `LLM_GATEWAY_BASE_URL` as the canonical text
   gateway settings.
2. Set the default ordered models to `claude-sonnet-5-5`, `kimi-k3`, then `gpt-6.1-sol` in
   each product and deployment sample.
3. Derive OpenAI-compatible and Anthropic-compatible request headers from the
   canonical secret at call time. Keep protocol-specific URL/parameter
   adaptation separate from secret storage.
4. Remove independent backup-model key/token settings from runtime schemas,
   settings responses, V2 fallback env overrides, and LAB provider token
   lookup. Update local ignored env files through a secret-safe migration that
   does not print values.
   V2 runtime settings accept one write-only gateway key and persist it in
   `V2_DATA_DIR/llm_gateway.env` with owner-only permissions. Workers reload
   this file at each V2 orchestration entry, so API and queue-worker processes
   observe updates without writing to root-owned systemd EnvironmentFiles.
5. Retain any independent image-renderer credentials and mark them explicitly
   out of this text-model credential migration.
6. Do not deploy the resulting config to a VPS as part of local validation.

## Work sequence

1. Finish and independently audit the document family.
2. Implement config migration and safe model/protocol mapping.
3. Implement V1 and LAB candidate selection using exact model selectors and
   unified credentials.
4. Implement V2 candidate fallback on a classified Claude route failure,
   including before the first checkpoint, while preserving any available
   compression/checkpoint continuation and strict isolation. Kimi K3 is first,
   GPT-6.1-sol follows after eligible failure; deterministic creative
   substitution remains prohibited.
5. Implement V3 candidate selection and transport classification inside the
   remote Brain provider; preserve total execution deadline.
6. Add safe provenance for each route attempt. Circuit-breaker state is
   deferred as an optional optimization; basic failover must work without it.
7. Add/run the focused unit/regression suite; review the complete diff for
   unrelated files, secret leakage, and route-contract drift.
8. Freeze a revision and request a separate read-only code audit. Correct only
   bounded findings and re-audit the new revision.
9. After code audit PASS, start local services with the new config and run one
   V3 text-planning + real image-rendering request. The image result is the
   final external-provider acceptance gate and must not be used to debug code
   defects.

## Failure handling and stop conditions

- If a model-protocol capability is unsupported, correct the adapter before
  enabling failover for that error; do not convert all HTTP 400 responses into
  model outages.
- If a 403 does not carry a recognized gateway error category, stop that
  request with an explicit unclassified authorization failure; do not guess
  whether another model is permitted.
- If the single key cannot authorize both model families at the unified
  gateway, stop before external generation and report the missing account
  capability. Do not silently add another secret.
- A V2 settings update must persist atomically before changing in-memory state;
  the key must never enter `runtime_model_settings.json`, response bodies, or
  raw provider response files.
- If V3's required Brain contract cannot be met by either candidate, stop
  before sending an image-generation request.
- If code audit is FAIL or INSUFFICIENT_EVIDENCE, do not run real image
  generation. Fix/evidence-gather, freeze the next revision, and repeat the
  independent code audit.
- Preserve any unexpected job/output append-only; do not delete it to make the
  acceptance run appear clean.
