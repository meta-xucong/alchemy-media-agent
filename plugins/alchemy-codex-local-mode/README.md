# Alchemy Codex Local Mode

This is a deliberately isolated Doc117 development plugin.  It exists only
for an interactive Codex agent to call the local Alchemy MCP adapter.  It is
not installed by the web application, does not change an Alchemy Provider,
and cannot be used as a fallback when Web Mode fails.

The adapter uses stdio only.  It never starts an HTTP listener, controls the
Codex CLI, or reads Codex/ChatGPT credentials.  It accepts only a fully
materialized local PNG or JPEG file and imports a copy into its local storage
with a content hash, job binding, role binding, and Local Mode provenance.

## Development installation

Keep this directory in the Alchemy repository.  The included `.mcp.json`
starts the adapter from the repository root through stdio.  It intentionally
does not create a Marketplace entry, enable a Web route, or modify `.env`.

Validate the plugin after any manifest change:

```powershell
python C:\Users\T14S\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
```

## Phase A--B limits

- Local Mode must be selected explicitly by the user and Codex agent.
- The direction is always `Codex -> MCP -> Alchemy`; the Alchemy Web process
  must never launch, poll, or terminate Codex.
- The job provenance is always `execution_channel=codex_local`,
  `creative_direction_owner=codex_local_agent`, and `renderer=codex_imagegen`.
- No imported candidate is certified or delivered in this spike.  Shared
  review/retry/final-delivery wiring belongs to Doc117 Phase C.
- If Codex exposes only a preview, data URL, UI cache, or session-bound
  reference instead of a durable local image file, stop.  Do not scrape UI
  state or manufacture a handoff.
