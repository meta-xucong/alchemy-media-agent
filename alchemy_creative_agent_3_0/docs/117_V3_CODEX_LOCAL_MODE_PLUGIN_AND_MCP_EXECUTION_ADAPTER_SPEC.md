# Doc117: V3 Codex Local Mode Plugin And MCP Execution Adapter

> **Historical design notice — B2 is retired for future work.**  The
> separately configured Platform Image API materialization route described in
> this document is not the approved Local Mode product and must not be merged,
> enabled, or used as a substitute for Codex-native image generation.  Its
> security research and the finding that Codex exposes no durable artifact
> handoff remain historical evidence only.  Doc118,
> `118_V3_CODEX_NATIVE_IMAGEGEN_PROMPT_ORCHESTRATION_SPEC.md`, is the sole
> authority for new Local Mode work: Alchemy planning MCP -> Codex built-in
> image tool -> conversation-only result, with no additional API key and no
> artifact import.

## Status

Proposed development specification.  This document authorizes design and a
contained technical spike only.  It does **not** enable a new production
renderer, alter the current web runtime, or certify any Provider Gate.

## 1. Decision

V3 may offer a second, explicitly selected local execution mode:

```text
existing V3 Web Mode
  -> V3 Central Brain + configured GPT Image 2 gateway

optional Codex Local Mode
  -> Codex local agent owns explicit creative direction through stdio MCP
  -> B2 may use a separately configured official Platform Image API request
  -> Alchemy stores only a non-certified development artifact until Phase C
```

Codex Local Mode is an independently installable plugin plus a local MCP
adapter.  It is not a change of default Provider, a fallback for the web
runtime, or a web-server feature that shells out to `codex`.

The decisive control direction is:

```text
Codex agent -> Alchemy MCP tools -> Alchemy local execution facade
```

It must never be reversed into:

```text
Alchemy Web/API server -> Codex CLI process -> image generation
```

The reverse form would mix interactive desktop authentication with a long-lived
HTTP service, make lifecycle cancellation unsafe, and turn a personal Codex
session into an undocumented image-provider backend.

## 2. Why This Is A Separate Mode

The current web runtime has a deliberate production contract:

```text
Project -> Template -> Scenario Pack -> Job
  -> Central Brain -> shared capability execution
  -> GPT Image 2 through the configured provider path
  -> shared review/retry -> final delivery
```

Doc100 remains the authority for that path.  Its configured `gpt-image-2`
Provider stays the sole V3 **web-production** renderer.  Codex Local Mode does
not modify its routing, credential configuration, retry policy, or release
gates.

The current B2 route has a distinct, user-visible provenance:

```text
execution_channel = codex_local
creative_direction_owner = codex_local_agent
renderer = platform_openai_gpt_image_2
renderer_model = gpt-image-2
```

This is an explicit, independently configured Platform API call, not a Codex
Desktop/ChatGPT login-state export.  `renderer_model` is recorded only because
the B2 request itself contains the official model identifier.  The adapter
must never label a B2 artifact `codex_imagegen`, and it must not read or reuse
Codex/ChatGPT authentication or Web Mode Provider settings.

The earlier Codex Desktop interactive-artifact investigation remains a blocked
Phase B1 evidence path: no supported durable artifact handoff was available.
It is retained as a security boundary, not as an active renderer contract.

## 3. Product Boundary

### 3.1 What Codex Local Mode provides

- a no-browser local workflow for creating an Alchemy project/job;
- an explicit, inspectable render contract for a Codex agent;
- Codex-owned natural-language creative direction and explicit local-adapter invocation;
- secure import of the resulting image artifact into Alchemy;
- existing Alchemy project history, constraints, review, bounded revision,
  selection, and continuation semantics where the shared runtime supports them;
- separate development-quality evidence for prompts, references, review, and
  final artifacts.

### 3.2 What it does not provide

- a hidden replacement for the configured web Provider or its Smart Router;
- a way for unauthenticated browser users to spend or operate a local Codex
  account;
- a headless `codex exec` image-rendering API assumption;
- a substitute for Provider Gate C/D, photography P10, E-Commerce Gate C/D,
  or General Gate D evidence;
- an exception to Doc100, Doc101/102, Doc109, Doc111, Doc113, Doc114, Doc115,
  or Doc116;
- a new General, E-Commerce, or Photography delivery taxonomy.

## 4. Isolation Requirements

The feature is acceptable only when it is optional in every dimension.

| Surface | Required isolation |
| --- | --- |
| Installation | A standalone Codex plugin and local MCP adapter.  It is absent until intentionally installed. |
| Runtime loading | No module import, route registration, worker, background poller, or configuration validation is active when `codex_local_mode` is disabled or uninstalled. |
| Web behavior | Existing Web Mode retains its current Central Brain, `openai_gpt_image`, gateway-managed failover, timeout, retry, and result behavior. |
| Credentials | The adapter never reads, exports, duplicates, or forwards Codex/ChatGPT session tokens.  It does not reuse the web Provider key. |
| Invocation | Only an interactive/local Codex agent calls the MCP tools.  The Alchemy web process never spawns, kills, polls, or drives Codex CLI. |
| Data | Local artifacts go through an import boundary with content hash, declared origin, and explicit project/job binding.  They never masquerade as web-Provider files. |
| Release claims | Local evidence is tagged `codex_local_development_evidence`; it cannot advance Web Mode Provider Gate C/D, Gate D, P10, or an E-Commerce production gate. |
| Removal | Removing the plugin and its sidecar leaves the existing application configuration and routes unchanged.  Historical local-mode records remain readable as provenance. |

No global default such as `IMAGE_PROVIDER=codex`, `USE_CODEX=true`, or a
replacement of `OPENAI_BASE_URL` is permitted.

## 5. Recommended Packaging

Use a plugin because the local workflow needs both reusable instructions and
live tool calls.  A skill alone cannot reliably transfer an image artifact into
Alchemy; an MCP server alone cannot make Codex invoke its image-generation
tool with the intended orchestration policy.

```text
plugins/alchemy-codex-local-mode/
  .codex-plugin/plugin.json
  skills/alchemy-local-run/SKILL.md
  mcp/                    # local stdio or loopback MCP service configuration
  README.md

services/alchemy_codex_local_adapter/
  facade.py               # narrow local-only API boundary
  contracts.py
  artifact_import.py
  provenance.py
  tests/
```

The exact repository placement may change during implementation, but the
plugin must be separately installable and the adapter must be local-only.  Do
not embed a Codex plugin manifest, MCP setup, or Codex auth configuration into
the V3 web application package.

The plugin uses a local marketplace or personal install during development.
It is not a public production service, and it must not automatically install
or enable itself for other users.

## 6. Canonical Local Execution Contract

The adapter exposes small, task-oriented MCP tools.  Names may evolve before
implementation, but their ownership and semantics are fixed.

| Tool | Caller | Required behavior |
| --- | --- | --- |
| `create_local_job` | Codex agent | Creates a V3 job with `execution_channel=codex_local`, explicit user request, references, template identity, and immutable initial provenance. |
| `get_render_contract` | Codex agent | Returns the protected user intent, normalized job intent, frozen template deliverable plan, capability envelope, resolved constraint ledger, permitted reference files, and requested output count.  It must not disclose secret settings or internal Provider credentials. |
| `record_creative_direction` | Codex agent | Stores the agent's natural-language whole-image direction, linked to each frozen role when a specialized template defines roles.  It cannot edit user facts, template count, locked profile bindings, or reference truth. |
| `import_generated_candidate` | Codex agent | Imports one concrete local image artifact plus origin, hash, mime type, dimensions, role binding, and optional opaque Codex run identifier.  The image must be materialized before it can become a candidate. |
| `review_candidate` | Codex agent | Invokes the shared review contract and returns a public-safe verdict plus audit provenance.  It never lets the plugin self-certify an image. |
| `request_bounded_revision` | Codex agent | Obtains a shared, issue-scoped revision request only when review marks it retryable and the frozen budget permits it. |
| `finalize_local_job` | Codex agent | Runs the shared final-winner/delivery closure.  It cannot turn a metadata-only or blocked review into a certified delivery. |
| `continue_local_job` | Codex agent | Creates an append-only continuation job from a selected materialized output under the existing continuation contract. |
| `get_local_job_status` | Codex agent | Returns public job state, final deliveries, safe review certification state, and next permitted action. |

The MCP server must use an allowlisted local transport.  No unauthenticated
LAN listener, browser-exposed administrative route, or remote tunnel is part of
the first release.

## 7. Lifecycle

### 7.1 Creation and contract freeze

```text
user asks Codex to create with Alchemy Local Mode
-> Codex calls create_local_job
-> Alchemy validates template gate and freezes the job contract
-> Codex fetches get_render_contract
-> Codex forms one natural-language direction per required role
-> Codex records the direction before importing an image
```

The frozen job must preserve the same core invariants used by other V3 paths:

- protected user intent and explicit negatives;
- `NormalizedV3JobIntent`;
- `TemplateDeliverablePlan` and exact role/count contract when applicable;
- `CapabilityExecutionEnvelope` and `ResolvedConstraintLedger`;
- reference-channel ownership, selected-result bindings, and locked profile
  checksums;
- append-only job and candidate history.

Codex Local Mode may be selected only by an explicit user/Codex action.  A
General, E-Commerce, or Photography web task can never silently switch to it
after a web Provider failure.

### 7.2 Artifact handoff

The image handoff is the first implementation spike and a release blocker.
Phase B1 investigated an interactive Codex Desktop artifact handoff and is
blocked: the supported surface did not expose a durable, safe artifact transfer
mechanism.  It must not be emulated by scraping UI state, cache, session files,
or a Codex/ChatGPT login credential.

Phase B2 is the only implemented materialization route.  It uses a separately
configured, explicit OpenAI Platform API key file, fixes the endpoint to
`https://api.openai.com/v1/images/generations`, sends exactly one `gpt-image-2`
request with `n=1` for each frozen role, receives API `b64_json` image bytes,
and materializes them in importer-owned temporary storage.  It never accepts a
caller-selected local file.  Live B2 fails closed unless Local Mode and the
per-call opt-in are both explicit, and the dedicated key file is under the user
home directory, outside the repository, and not a symlink.  It does not read
root `.env`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, Codex auth/session state, or
any Web Provider/Aiself setting.

The controlled importer must then:

1. validate image type, size, and configured local size limits;
2. copy/import it into Alchemy-controlled local storage rather than retain an
   opaque UI-only preview reference;
3. calculate a content hash and record immutable origin/provenance;
4. bind it to exactly one job attempt and, when relevant, one frozen role;
5. create an append-only candidate record;
6. reject duplicate, missing, or cross-job materializations with an explicit
   terminal/held state.

The B2 materialization proves a direct Platform API artifact only.  It does
not prove an interactive Codex image export, a supported production Local Mode,
or any existing Web Mode Provider Gate C/D, General Gate D, Photography P10,
or E-Commerce Gate C/D.

### 7.3 Review, revision, and delivery

```text
materialized local candidate
-> shared real-pixel review
-> pass/warning/manual-confirmation/blocked/retryable verdict
-> optional bounded Codex-directed revision
-> shared candidate comparison and final delivery closure
```

Doc100 retry limits, Doc109 lifecycle truthfulness, and Doc116 certification
withholding apply.  A Local Mode agent may formulate a revised whole-image
direction, but it cannot patch pixels, alter review evidence, or select an
unreviewed candidate as delivered.

`metadata_only`, local-only checks, absent vision evidence, or manual
confirmation must remain visibly non-certifying.  Such artifacts can be saved
as development candidates but cannot be counted as a passed production-quality
gate or a certified specialist-template delivery.

## 8. Template and Capability Boundaries

This mode changes *who executes the creative/tool call*, not the ownership of
professional deliverables.

| Area | Local Mode rule |
| --- | --- |
| Foundation | Continues to own normalized intent, references, capability activation, constraint resolution, review, retry budgets, candidate history, and final delivery mechanics. |
| General | Remains a simple, neutral single/small-set creation entry.  It gains no marketplace, photographer-profile, slot, or campaign rules. |
| E-Commerce | May expose an explicitly selected E-Commerce deliverable plan only when its own remote-Brain/fail-closed contract is satisfied.  Local Mode cannot revive static recipes, slots, default marketing copy, local overlays, or a local text renderer. |
| Photography | May expose its frozen role count/profile/reference contract only when the photography gate is enabled for the controlled environment.  Local Mode must honor locked profile checksums, require real-pixel certification, and cannot replace the LLM-first role direction with fixed shot recipes. |
| Human Realism | Remains the shared evidence-driven capability.  It must not gain a Codex-, child-, apparel-, E-Commerce-, or photography-specific hard-coded branch. |

The adapter consumes the frozen envelope and ledger.  It must not reconstruct
prompt constraints from legacy metadata or selectively drop accepted capability
contributions.

## 9. Creative-Direction Contract

For Local Mode, Codex is an alternate explicit creative owner, not a hidden
fallback:

```text
creative_direction_owner = codex_local_agent
creative_direction_source = recorded_local_agent_direction
fallback_used = false
```

This designation does not let Codex override facts.  The adapter must reject a
direction that conflicts with protected product truth, identity/reference
truth, user hard negatives, role/count contract, safety constraints, or an
immutable photographer profile binding.

The stored direction must be natural-language whole-image guidance.  It must
not introduce the deprecated structured routes below:

- static marketplace suites, camera/crop recipes, or product-box coordinates;
- `CopyRenderPlan`, fonts, local OCR correction, canvas/HTML/SVG overlays, or
  post-render text compositing;
- fixed photography lens, pose, lighting, or scene prose masquerading as a
  local plan;
- hard-coded child/kidswear prompt fragments outside the shared, generic Human
  Realism evidence path.

## 10. Security and Privacy

1. Codex authentication belongs to Codex Desktop/CLI.  The Alchemy adapter
   never reads `auth.json`, browser cookies, ChatGPT sessions, or shell secrets.
2. The plugin must show the exact files/references it will send to an image
   tool before the Codex agent invokes it when the current surface supports
   that disclosure.
3. Imported artifacts are scanned/validated as untrusted local inputs.  File
   names, image metadata, and opaque Codex identifiers are never treated as
   instructions.
4. The local adapter binds to loopback or stdio only and uses an install-time
   local trust boundary.  It must not publish an unauthenticated network API.
5. Audit records store only the minimum provenance needed for reproducibility.
   They do not persist credentials, full session tokens, or undocumented
   internal Codex tool payloads.
6. Deleting a Local Mode project follows the existing media/history retention
   policy; uninstalling the plugin does not delete user artifacts.

## 11. Compatibility and Failure Semantics

| Condition | Required outcome |
| --- | --- |
| Plugin absent/disabled | No Local Mode option or code path is active; Web Mode is unchanged. |
| User did not explicitly choose Local Mode | Use the existing web path only. |
| MCP adapter unavailable | Fail before job execution with `codex_local_adapter_unavailable`; never fall back to the web Provider. |
| Local renderer unavailable, disabled, or key gate fails | Block with a structured `codex_local_platform_renderer_*` error; do not invoke Aiself, a Web Provider, Codex CLI, or an interactive-session substitute. |
| Artifact cannot be materialized | Hold/block without creating a deliverable candidate. |
| Direction conflicts with immutable contract | Block with a structured constraint conflict; do not silently rewrite user truth. |
| Review is metadata-only/manual/blocked | Retain candidate and audit record but withhold certification/delivery as required by shared policy. |
| Revision budget exhausted | Preserve the best eligible candidate or return the shared manual-resolution state; never loop. |
| Plugin later uninstalled | Historical jobs remain readable and explicitly display their Local Mode provenance; no continuation is offered unless the adapter is reinstalled. |

## 12. Development Phases

### Phase A — Contract and package skeleton

- Create the standalone plugin skeleton, local MCP tool schemas, adapter
  contracts, and this document's provenance fields.
- Do not register it in the web service or change V3 defaults.
- Add disabled-mode/no-import/no-route tests.

### Phase B — Real artifact-handoff spike

- **B1 — Codex Desktop artifact-handoff investigation (blocked):** attempt an
  interactive handoff only through a supported, durable artifact mechanism.
  Stop and record the blocker when none exists; never scrape UI state, caches,
  session files, or login credentials, and never emit `codex_imagegen` without
  that evidence.
- **B2 — explicit Platform API materialization route:** Codex owns the
  natural-language direction and invokes the local stdio MCP adapter.  The
  adapter makes one official `gpt-image-2` API request with `n=1` per frozen
  role, then materializes only returned image bytes through importer-owned
  staging.
- B2 reads only `ALCHEMY_CODEX_LOCAL_IMAGE_API_KEY_FILE`; it must be a
  non-symlink file under user home and outside the repository.  The base URL is
  fixed to `https://api.openai.com/v1` and cannot inherit Web Provider
  configuration.
- Prove B2 hash, direct-API source, role/job binding, and reopen/persistence.
  Record `renderer=platform_openai_gpt_image_2`, never `codex_imagegen`.
- B2 remains an independent, non-certified development/acceptance channel.

### Phase C — Shared runtime integration

- Wire the imported candidate into the existing shared review, retry, final
  delivery, selected-output continuation, and public-safe provenance surfaces.
- Prove Local Mode cannot self-certify or bypass a blocked review.
- Keep `execution_channel=codex_local` separate in history and analytics.

### Phase D — Controlled quality evaluation

- Run rights-clear General, product, portrait, and children/apparel fixtures.
- Evaluate only as Local Mode development evidence.
- Confirm isolated General/E-Commerce/Photography contracts and no behavior
  change with the plugin disabled.

### Phase E — Optional specialist-template pilots

- Consider E-Commerce or Photography only after their existing web gates and
  their own fail-closed contracts are green.
- Use a fresh explicit user choice, real artifact handoff, shared pixel review,
  exact role-count delivery, and separate evidence records.

No phase authorizes changing Web Mode's Provider production gate.  A future
decision to make Local Mode a supported production channel requires a separate
architecture review and an explicit user-approved security/reliability gate.

## 13. Required Test Matrix

### Disabled and web-regression tests

- plugin/adapter absent produces no V3 route, provider choice, worker, import,
  or environment validation change;
- Web General, E-Commerce, Photography, Project Mode, gateway timeout, and
  Provider retry tests retain their exact pre-plugin behavior;
- a web Provider 5xx cannot select or invoke Local Mode;
- the web process has no imports or process-spawn call path for Codex CLI.

### Local contract tests

- explicit selection produces a job with immutable Local Mode provenance;
- `get_render_contract` returns the frozen envelope/ledger and never Provider
  credentials or mutable raw metadata fallback;
- credential-like structured keys (including nested `api_key`, `secret`,
  `token`, `password`, `authorization`, and `credential` variants) fail closed
  before persistence; legacy local JSON is scrubbed on recovery;
- B2 reads only its dedicated key-file environment name, rejects repository,
  symlink, unreadable, missing, and invalid key files before any network
  request, and never inherits `OPENAI_API_KEY` or `OPENAI_BASE_URL`;
- one declared requested output creates exactly one candidate/delivery role;
- materialized artifact hash and role binding survive restart/reopen;
- missing, duplicated, cross-job, or non-image artifacts block safely;
- an invalid Codex direction cannot override product/identity/profile/reference
  truth;
- all retry attempts remain append-only and selected final delivery is stable.

### Review and isolation tests

- metadata-only/local-only/manual-confirmation candidates never become
  certified Local Mode deliveries;
- vision/hybrid verdict projection is public-safe and audit evidence remains
  internal;
- Local Mode cannot import or activate E-Commerce slots, static recipes,
  CopyRenderPlan, text overlays, or photography camera recipes;
- General Local Mode requests contain no E-Commerce or Photography semantics;
- E-Commerce and Photography Local Mode requests retain their existing
  template gates, immutable bindings, count checks, and fail-closed rules.

### B2 controlled acceptance

- a separately authorized, dedicated Platform API key can produce one
  `platform_openai_gpt_image_2` development artifact without copying a Codex
  session token or using a Web Provider configuration;
- one rights-clear General project completes through materialization, shared
  review, final delivery, project reopen, and append-only history;
- an intentionally unavailable B2 key/renderer and a missing artifact each show
  clear non-web fallback failures;
- no result is recorded as web Provider Gate C/D, General Gate D, P10, or
  E-Commerce production evidence solely because it ran through Local Mode.

## 14. Acceptance Criteria

The initial development version is accepted only when all are true:

1. it installs and uninstalls as a separate plugin/sidecar without modifying
   existing Web Mode configuration or behavior;
2. control direction is Codex -> MCP -> Alchemy, with no reverse web-server
   Codex CLI invocation;
3. either a supported Codex artifact handoff is proven, or the separately
   authorized B2 Platform API materialization route is proven and labelled
   truthfully as a non-Codex-export development artifact;
4. every Local Mode image has explicit, immutable provenance and materialized
   local storage;
5. shared constraints, review, retry, final-winner, and history behavior are
   reused rather than recreated in the plugin;
6. non-certifying review states cannot be presented as certified delivery;
7. General, E-Commerce, and Photography remain isolated; and
8. existing web regression tests and controlled browser behavior remain green
   with the module disabled.

## 15. Explicit Non-Goals And Future Decision

This document deliberately does not promise that Codex Desktop's interactive
image tool is a stable unattended image API, that `codex exec` can return
durable image binaries, or that a ChatGPT/Codex login may be repurposed as an
OpenAI Platform API credential.  Those are separate surface and account
contracts.

Phase B1 remains blocked until Codex exposes a supported artifact handoff.
Phase B2 may be used only with a separately authorized Platform API key and is
not a Codex login-state route or production Local Mode certification.  Until a
future approved Phase C shared-runtime bridge and production review establish
otherwise, retain the current web Provider path for real production generation;
do not weaken the boundary by scraping session state, turning a browser into
an unattended provider, or wiring a local Codex account into V3's public
service.

## 16. Authority

- Doc76 governs foundation versus specialized-template ownership.
- Doc100 remains the Web Mode production-renderer authority.
- Doc101/102 govern frozen capability activation and execution alignment.
- Doc109 governs project truthfulness, selected-output continuity, and frontend
  finalization.
- Doc111 prohibits deterministic local text-pixel rendering for new work.
- Doc113 governs execution truth, template ownership, and the constraint ledger.
- Doc114 governs only the later children/apparel quality path; it does not
  create a Local Mode-specific child implementation.
- Doc115/116 govern Photography LLM-first direction and real-pixel
  certification/withholding.

Where this document conflicts with a production web-renderer requirement,
Doc100 wins for Web Mode.  Where it conflicts with an active shared runtime
invariant, the stricter immutable-contract, review, or fail-closed rule wins.
