# Doc118: V3 Codex Native ImageGen Prompt Orchestration Specification

## Status and decision

**Proposed; documentation only.** This document freezes the intended
architecture and explicitly does not authorize implementation until the
maintainer confirms the design.

This document defines the only Local Mode direction authorized for the next
implementation phase:

```text
explicit user choice in Codex
  -> local Alchemy MCP planning-only contract
  -> frozen Alchemy prompt / constraints / reference instructions
  -> Codex built-in image generation tool
  -> image remains in the Codex conversation
```

It replaces the *goal* of Doc117 Phase B2.  A separately configured OpenAI
Platform API key, an HTTP call to `/v1/images/generations`, and API-image
materialization are **not** a solution to this product requirement and must
not be enabled, requested, or presented as the Local Mode path.

Doc117's B1 finding remains true: the current supported Codex surface does
not expose a durable local artifact handle for its built-in image tool.  This
is not a blocker for the prompt-orchestration product described here, because
the result intentionally remains in Codex rather than being imported into the
Alchemy website or project-delivery store.

## 1. Product intent

The user must be able to ask Codex for an Alchemy-directed image without
opening the Alchemy website and without depending on Web Mode's configured
thinking or rendering gateway.

The practical result is not an alternate HTTP image provider.  It is a native
Codex workflow in which Alchemy contributes the V3 planning algorithm and
Codex contributes its own interactive image-generation capability.

```text
User: "Use Alchemy Local Mode to create …"
  -> Codex calls local Alchemy MCP
  -> Alchemy runs planning only and returns an ImageGen-ready direction
  -> Codex calls its built-in image-generation tool
  -> Codex displays the generated image in this conversation
```

This is useful immediately even though neither a local file nor a web-project
delivery record is produced.

## 2. Non-negotiable boundaries

### 2.1 No extra credentials or provider substitution

The implementation must not:

- request, read, validate, store, or document an OpenAI Platform API key;
- call `api.openai.com`, Aiself, a Web Provider, or any image HTTP endpoint;
- read Codex/Desktop/ChatGPT login state, session files, cookies, caches, or
  undocumented tool state;
- spawn, poll, drive, or turn Codex CLI/Desktop into an HTTP service;
- become a fallback after a Web Mode, Brain, gateway, or Provider failure.

Codex owns its own built-in tool authentication.  Alchemy never receives or
  interprets that authentication.

### 2.2 No false Project Mode delivery

The native Codex image is a conversation result, not an Alchemy materialized
candidate.  Until Codex exposes a supported artifact handoff, Local Mode must
not claim any of the following:

- V3 project output, selected result, continuation input, or final delivery;
- shared review/retry/final-winner execution;
- Provider Gate C/D, General Gate D, Photography P10, or E-Commerce Gate C/D
  evidence;
- pixel-certified, vision-reviewed, or production-ready output.

The MCP may persist a small prompt-plan audit record, but it must never invent
an image hash, candidate ID, review verdict, or delivery state.

### 2.3 Existing V3 ownership remains intact

Foundation still owns normalized intent, capability activation, constraint
resolution, reference truth, and prompt safety.  General remains neutral.
E-Commerce and Photography retain their own template gates, exact role/count
contracts, LLM-first requirements, and fail-closed behavior.  This mode must
not revive static suite recipes, `CopyRenderPlan`, local text rendering,
camera/pose recipes, or child/kidswear-specific prompt fragments.

## 3. Architecture

### 3.1 Control flow

```text
Codex Skill
  -> stdio MCP: prepare_native_imagegen_plan
  -> local Alchemy planning-only facade
       -> protected user intent
       -> NormalizedV3JobIntent
       -> TemplateDeliverablePlan
       -> CapabilityExecutionEnvelope
       -> ResolvedConstraintLedger
       -> prompt compilation(s)
  <- public-safe native image plan
Codex Skill
  -> Codex built-in image-generation tool, once per returned output
```

The web service never calls Codex.  The MCP process opens no listener and is
started only through the explicitly installed plugin over stdio.

### 3.2 Planning-only Alchemy facade

`prepare_native_imagegen_plan` must reuse the V3 planning path, but it must
not call `generate_job`, instantiate `ProductionImageGenerationProvider`, or
write an output/upload/project store.

For a General request, the facade uses the V3 foundation planner to produce
one or more frozen prompt compilations.  It returns the corresponding visual
prompt, hard constraints, text policy, constraint summary, exact requested
count, and public reference instructions.

For E-Commerce and Photography, the facade does **not** weaken their existing
contracts merely because the renderer is Codex-native:

- when the selected template requires the remote Central Brain, it still must
  be available, used, and non-fallback;
- an invalid Brain result or role-count mismatch is `blocked`;
- the returned count and role lineage exactly match the frozen
  `TemplateDeliverablePlan`;
- unavailable high-fidelity reference/identity capabilities remain a block,
  not a text-only downgrade.

This preserves current LLM-first template governance while allowing Codex to
execute the final interactive image-tool call.

### 3.3 Reference boundary

The MCP cannot extract, copy, or pretend to possess images attached in the
Codex conversation.  Instead it returns public instructions such as:

```text
reference_handling = "If the user attached the declared reference in this
Codex conversation, include that exact attachment in the native image tool
call and preserve the stated channel.  Otherwise block if the channel is
required."
```

Codex, which can see the conversation attachments, is responsible for adding
them to the native image-tool call.  Alchemy must never consume a guessed path
or a browser/cache artifact as a substitute.

## 4. Public MCP contract

### 4.1 `prepare_native_imagegen_plan`

The first implementation exposes exactly one planning tool.

Input:

```json
{
  "user_input": "Create a warm editorial portrait …",
  "template_id": "general_template",
  "requested_image_count": 1,
  "requested_image_size": "1024x1024",
  "reference_declarations": [
    {
      "channel": "portrait_identity",
      "attached_in_current_codex_conversation": true
    }
  ]
}
```

The caller never supplies a raw capability envelope, arbitrary local path,
provider metadata, API key, `base_url`, platform recipe, or an existing V3
job identifier.  Alchemy creates all planning contracts internally.

Successful result shape:

```json
{
  "status": "planned_for_codex_native_imagegen",
  "execution_channel": "codex_native_imagegen",
  "requested_output_count": 1,
  "outputs": [
    {
      "output_index": 1,
      "role_lineage": "general_output_1",
      "imagegen_prompt": "natural-language whole-image direction",
      "hard_constraints": ["…"],
      "text_policy": "provider_native_text_forbidden",
      "reference_instructions": ["…"]
    }
  ],
  "provenance": {
    "planner": "alchemy_v3_planning_only",
    "renderer": "codex_builtin_imagegen",
    "fallback_used": false,
    "delivery_state": "conversation_only_not_certified"
  }
}
```

The output is intentionally prompt-oriented.  It must not include provider
credentials, private storage paths, raw legacy metadata, a review verdict, or
a statement that a picture was created.

Blocked result shape:

```json
{
  "status": "blocked",
  "code": "codex_native_imagegen_required_reference_missing",
  "message": "A required identity reference is not attached in the current Codex conversation.",
  "delivery_state": "no_image_created"
}
```

The exact error code may differ by the frozen capability/template contract,
but all failures must be explicit and must not fall back to Web Mode or an
external image API.

### 4.2 Deliberately absent tools

The native prompt plugin must not expose any of these Doc117 B2 tools or
equivalents:

- `render_platform_candidate`;
- `import_generated_candidate`;
- arbitrary-file import;
- local image HTTP rendering;
- `review_candidate`, `request_bounded_revision`, or `finalize_local_job` as
  functional operations.

Those names must either be removed or return a clear
`codex_native_imagegen_conversation_only` refusal.  The preferred initial
surface is omission, so Codex cannot accidentally select a stale API route.

## 5. Codex Skill behavior

The standalone plugin skill is the executor of the interactive part:

1. Run only when the user explicitly chooses Alchemy Local Mode / Codex Native
   ImageGen Mode.  Never select it based on a Web Mode failure.
2. Call `prepare_native_imagegen_plan` once for the user's request.
3. If it is blocked, show the public-safe reason and do not create an image.
4. For every returned output, use exactly one Codex built-in image-generation
   call with the returned `imagegen_prompt`, hard constraints, and the
   declared conversation attachment when required.
5. Do not modify the prompt with platform recipes, static ecommerce slots,
   local text overlays, pixel coordinates, or hidden provider fields.
6. Make it clear that the result is conversation-only and not a certified V3
   delivery.  Do not ask the user to upload it to the website as part of the
   normal happy path.

If Codex built-in image generation is unavailable in the current surface,
the run ends with `codex_native_imagegen_tool_unavailable`; it does not call
any external renderer.

## 6. Provenance and persistence

The optional local audit record is limited to:

- request ID and planning timestamp;
- selected template/scenario;
- frozen output count and role lineage;
- a safe digest of planning provenance;
- `execution_channel=codex_native_imagegen`;
- `renderer=codex_builtin_imagegen`;
- `delivery_state=conversation_only_not_certified`.

It must not store authentication data, actual image bytes, artifact paths,
Codex conversation IDs, cached tool payloads, review results, or a false
candidate/delivery record.

## 7. Compatibility and failure policy

| Condition | Required result |
| --- | --- |
| Plugin absent or disabled | No Local Mode option and no V3 Web change. |
| User did not explicitly choose the mode | Existing Web Mode only. |
| MCP unavailable | `codex_native_imagegen_adapter_unavailable`; no fallback. |
| Planner/template gate blocks | Public-safe blocked result; no image tool call. |
| Required attachment is absent | Block; do not replace with text-only for hard identity/product/nonhuman truth. |
| Built-in image tool unavailable | Stop with no image created; do not call API/Web Provider. |
| Image is generated | Displayed in Codex only; never marked reviewed/certified/delivered. |
| Plugin is later removed | No effect on Web Mode or historical V3 projects. |

## 8. Mandatory retirement and migration plan

The next implementation must remove the rejected B2 route from the native
prompt plugin rather than merely leave a hidden button or an undocumented
fallback.  The following disposition is mandatory and must be reviewed in one
dedicated change set before N1 can be called complete.

| Existing B2 surface | Required disposition | Completion proof |
| --- | --- | --- |
| `services/alchemy_codex_local_adapter/platform_renderer.py` | Remove from the native prompt mode; do not import, wrap, or leave a callable Platform API path. | Source scan finds no `api.openai.com`, Platform key-file variable, or renderer import in the native mode. |
| `artifact_import.py` and `PlatformRenderedImage` materialization types | Remove from the native prompt mode; no arbitrary-file or staged API import substitute may remain. | MCP schema has no render/import operation and no local candidate/artifact record is written. |
| `render_platform_candidate`, `render_platform_candidates`, and B2 MCP schema entries | Delete rather than hide; a stale Codex session must not discover them. | `tools/list` exposes only the approved prompt-planning surface. |
| `ALCHEMY_CODEX_LOCAL_IMAGE_API_KEY_FILE`, Platform API documentation, B2 provenance names, and live opt-in flags | Delete from active plugin/adapter configuration and instructions.  Historic references stay only in the clearly retired Doc117 records. | Repository scan proves active native files do not mention the variable or `platform_openai_gpt_image_2`. |
| Plugin `SKILL.md`, `README.md`, manifest description, and MCP server version | Rewrite for `prepare_native_imagegen_plan` and the conversation-only boundary. | Plugin validation passes and the Skill asks Codex to use its built-in image tool exactly once per returned output. |
| Existing B2 tests | Replace them with negative regression tests: no API key, renderer, HTTP call, file import, or false delivery is possible. | Tests fail if any retired B2 tool/configuration is restored. |

The retired B2 code must not be moved into a compatibility namespace.  This
would preserve an attractive but wrong fallback route and make a later audit
ambiguous.  Git history and the three marked Doc117 documents are sufficient
for historical recovery.

Migration must also change active provenance vocabulary to:

```text
execution_channel = codex_native_imagegen
renderer = codex_builtin_imagegen
delivery_state = conversation_only_not_certified
```

No historical B2 `platform_openai_gpt_image_2` record may be rewritten as if
it were Codex-native.  It remains an old, non-certified experiment.

## 9. Implementation phases

### Phase N1 — Prompt contract and plugin correction

- Add this mode as a separate plugin/adapter contract.
- Remove B2 API-key renderer/tool exposure from the native prompt plugin.
- Implement General planning-only prompt output and its test double-free
  regression suite.
- Preserve Doc117 B1 evidence as historical research only.

### Phase N2 — Codex-native interactive workflow

- Update the Skill so it calls the planning tool and then Codex's native image
  tool exactly once per output.
- Validate that no API-key, Web Provider, browser, or session path is used.
- Verify one General text-to-image request in a fresh Codex task.

### Phase N3 — guarded specialized-template support

- Add E-Commerce and Photography only after proving their existing remote
  Brain, role-count, profile/reference, and fail-closed contracts remain
  intact.
- Keep all generated images conversation-only and outside production Gate
  evidence.

### Explicitly deferred

No artifact materialization, project continuation, shared pixel review, retry,
or final delivery is part of this document.  A future platform-supported
artifact handoff would require a new design review before such a phase begins.

## 10. Required tests and acceptance

Implementation may start only with tests covering:

- plugin disabled / uninstalled has no Web imports, routes, configuration, or
  Provider behavior changes;
- MCP schema contains `prepare_native_imagegen_plan` and contains no B2/API
  key/render/import tool;
- General request returns exactly the requested prompt count and no image
  artifact/candidate/delivery record;
- output contains Alchemy prompt, frozen hard constraints, text policy, and
  public reference instructions, but no secret-like fields;
- missing hard reference, unavailable required capability, invalid template,
  remote-Brain failure, fallback, and specialized role-count mismatch all
  block before Codex ImageGen invocation;
- General does not leak E-Commerce/Photography semantics;
- E-Commerce and Photography retain their respective isolation and fail-closed
  tests when later enabled;
- source scan proves no `api.openai.com`, `OPENAI_API_KEY`, dedicated local
  key-file environment variable, Aiself, browser/session/cache access, or
  Codex CLI process invocation in the native prompt mode;
- the Skill directs one native image-tool call per frozen output and labels
  results conversation-only/non-certified.

Acceptance is limited to: **Codex can obtain a V3 Alchemy-generated prompt
and use its built-in image tool without an additional image API key or the
Alchemy website.** It is not acceptance of production rendering, image review,
or any existing V3 quality gate.

## 11. Authority

Doc76 governs foundation/template separation.  Docs100–102 govern Web Mode
rendering and frozen capability execution.  Docs109, 113, 115, and 116 remain
authoritative for lifecycle truthfulness, constraint ownership, Photography
LLM-first direction, and real-pixel certification.  When this document
conflicts with any Web Mode production gate, that stricter Web Mode requirement
wins.
