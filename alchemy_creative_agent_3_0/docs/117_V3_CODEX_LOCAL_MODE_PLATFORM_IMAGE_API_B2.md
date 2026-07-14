# Doc117 Phase B2: Official Platform Image API Materialization

> **Retired / do not implement or merge.**  This document is preserved solely
> as a dated record of a rejected technical spike.  Its dedicated Platform API
> key, HTTP renderer, API-image materialization, and B2 MCP tools are not an
> acceptable answer to the Local Mode requirement and must remain disabled.
> Do not revive them for a provider outage or because Codex artifact handoff
> is unavailable.  Follow Doc118,
> `118_V3_CODEX_NATIVE_IMAGEGEN_PROMPT_ORCHESTRATION_SPEC.md`, for all future
> work: Alchemy planning MCP -> Codex built-in image tool ->
> conversation-only, non-certified result.

## Decision and Scope

Phase B2 is a constrained alternative to the blocked Codex Desktop artifact
handoff in Phase B.  Codex remains the explicitly selected local MCP/Skill
creative orchestrator.  The local adapter independently calls the official
OpenAI Platform Image API for one frozen, natural-language whole-image
direction per role, materializes the returned base64 bytes, and uses the
controlled local importer.

```text
Codex local agent
  -> local stdio MCP adapter
  -> https://api.openai.com/v1/images/generations
  -> API b64_json bytes
  -> importer-owned staging -> hash/job/role-bound development artifact
```

This solves **verifiable API artifact materialization**.  It does not solve or
claim an automatic export of a Codex/ChatGPT login-state image result.

The renderer identity is immutable for B2 records:

```text
execution_channel = codex_local
creative_direction_owner = codex_local_agent
renderer = platform_openai_gpt_image_2
renderer_model = gpt-image-2
```

`renderer_model` is recorded only because the B2 request itself contains the
official model identifier.  No record is labelled `codex_imagegen`, a direct
Codex Desktop export, or a Web Mode Provider artifact.

## Official API Contract

The adapter uses the fixed official base URL and path:

```text
POST https://api.openai.com/v1/images/generations
model = gpt-image-2
n = 1 per frozen role
output_format = png
```

The [official Image generation guide](https://developers.openai.com/api/docs/guides/image-generation)
documents `gpt-image-2` generation through the Image API and its base64 image
response.  The [official create-image API reference](https://developers.openai.com/api/reference/resources/images/methods/generate)
defines the Images generation endpoint.  B2 deliberately does not stream,
edit, invoke a browser, or retry automatically.

The adapter records only a safe request/response summary: fixed endpoint,
model, role ID, output settings, prompt SHA-256, response status/request ID
when available, and response-body SHA-256.  It never records a key, an
authorization header, image base64 payload, Web Provider configuration, or a
Codex session identifier.

## Credential and Isolation Gate

Live rendering is fail-closed unless all conditions hold:

1. Local Mode was intentionally selected by starting the local stdio adapter
   with `--enable-local-mode`.
2. The MCP call includes `live_platform_opt_in=true`.
3. `ALCHEMY_CODEX_LOCAL_IMAGE_API_KEY_FILE` names a readable regular file below
   the user home directory and outside the repository.
4. The file contains a nonempty printable dedicated Platform key.

The adapter reads no root `.env`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, Codex
`auth.json`, browser state, cookies, sessions, cache, Aiself URL, or Web
Provider key.  Its base URL has no override setting and remains exactly
`https://api.openai.com/v1`.

At the MCP/`LocalJobSpec` boundary, a recursively nested structured mapping
with a credential-like key is rejected before a job is created.  Matching is
case-insensitive and covers `api_key`/`apikey`, `secret`, `token`, `password`,
`authorization`, and `credential` forms.  This is key-name validation only:
ordinary user text is not inspected or rewritten.  Storage, provenance, and
public records also defensively drop those mapping keys.  On recovery, a
legacy local JSON record is scrubbed and re-written before it can be exposed.

Mock transports may exercise the response contract with no key and no network
request.  They are test evidence only and cannot turn into a live renderer.

## Artifact Boundary

MCP callers cannot nominate an arbitrary local file for import.  The importer
accepts only a capability token produced when the adapter has just written
official API response bytes into its private staging directory.  It verifies
PNG/JPEG pixels and MIME, copies the artifact into Local Mode storage, hashes
it, binds it to one job/role, records append-only claims, and deletes staging.

Missing, duplicate, cross-job, malformed, oversized, or MIME-mismatched
artifacts fail closed with structured `codex_local_*` errors.  A future local
inbox would need a separately audited contract; B2 does not add one.

## Non-Goals and Gate Status

Phase B2 creates only an independent, non-certified development artifact
record.  It does not create a real V3 Project/Job bridge, a frozen V3 plan,
shared review, shared retry, final-winner selection, continuation, or a
certified delivery.  Those remain a separately approved Doc117 Phase C.

It does not alter or contribute evidence to Web Mode's GPT Image 2/Aiself
path, Web Provider Gate C/D, General Gate D, Photography P10, or E-Commerce
Gate C/D.  It adds no CopyRenderPlan, font/OCR/overlay path, static E-Commerce
or Photography recipe, browser route, worker, provider fallback, or Codex CLI
process control.

## Focused Test Count

The security-correction focused command is exactly:

```powershell
python -m pytest tests/test_doc117_codex_local_mode.py -q
```

At this milestone it reports **27 passed**.  That is the actual count in this
module: each scenario is an independently reported pytest test, not a loop
inside one test and not an aggregate count from unrelated V3 suites.  Broader
regression commands must report their own total separately.
