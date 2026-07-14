# Alchemy Codex Local Mode

This is a deliberately isolated Doc117 development plugin.  It exists only
for an interactive Codex agent to call the local Alchemy MCP adapter.  It is
not installed by the web application, does not change an Alchemy Provider,
and cannot be used as a fallback when Web Mode fails.

The adapter uses stdio only.  It never starts an HTTP listener, controls the
Codex CLI, or reads Codex/ChatGPT credentials.  Phase B2 can make one explicit
official OpenAI Platform Image API request for one frozen role, materialize the
returned base64 bytes into importer-owned staging, then import a copy with a
content hash, job binding, role binding, and Local Mode provenance.

## Development installation

Keep this directory in the Alchemy repository.  The included `.mcp.json`
starts the explicitly enabled local adapter from the repository root through
stdio.  It intentionally does not create a Marketplace entry, enable a Web
route, or modify `.env`.

Validate the plugin after any manifest change:

```powershell
python C:\Users\T14S\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
```

## Phase A--B2 limits

- Local Mode must be selected explicitly by the user and Codex agent.
- The direction is always `Codex -> MCP -> Alchemy`; the Alchemy Web process
  must never launch, poll, or terminate Codex.
- The job provenance is always `execution_channel=codex_local`,
  `creative_direction_owner=codex_local_agent`, and, for B2,
  `renderer=platform_openai_gpt_image_2` with `renderer_model=gpt-image-2`.
- Live B2 calls require both the `live_platform_opt_in=true` tool argument and
  `ALCHEMY_CODEX_LOCAL_IMAGE_API_KEY_FILE` pointing to a readable, non-repo
  file under the user home directory.  The adapter never reads root `.env`,
  Web Provider environment variables, Codex auth/session state, or a custom
  base URL; the endpoint is fixed to `https://api.openai.com/v1`.
- Callers cannot import arbitrary paths.  Only bytes returned by the adapter's
  just-issued official API request may enter private staging and the importer.
- No imported candidate is certified or delivered in this spike.  Shared
  review/retry/final-delivery wiring belongs to Doc117 Phase C.
- B2 is a development/acceptance channel only.  It does not validate Codex
  Desktop artifact handoff and cannot contribute Web Provider Gate C/D,
  General Gate D, Photography P10, or E-Commerce Gate C/D evidence.
