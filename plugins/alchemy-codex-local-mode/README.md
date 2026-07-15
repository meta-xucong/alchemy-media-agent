# Alchemy Codex Native ImageGen Mode

This isolated Doc126 plugin gives an interactive Codex agent one local stdio
MCP planning tool: `prepare_native_imagegen_plan`. It does not create images,
open a listener, start a background worker, control Codex, call the configured
Web Brain or image Provider, or change Web Mode.

The flow is intentionally one-way:

```text
explicit user choice -> Codex -> local Alchemy planning MCP
-> Codex built-in image tool -> conversation-only image
```

The result is neither an Alchemy project output nor a certified delivery.  It
has no artifact import, candidate, review, retry, final-delivery, or
continuation surface.

## Input boundary

The planning tool currently enables only `general_template`. E-Commerce and
Photography are deliberately blocked until their independent LLM-first and
reference contracts can be proved without weakening them.

It accepts only user input, General, requested count/size, and declarations
about attachments already visible in the current Codex conversation. It never
receives a file path, local artifact, project or job ID, provider setting,
capability envelope, or credential. `portrait_identity`, `product_truth`, and
`nonhuman_identity` are always hard channels: callers cannot set a flag to
downgrade them.

For every successful output, Codex uses the returned whole-image prompt in
exactly one built-in image-generation call. Preserve the returned constraints
as guardrails, but do not turn them into a keyword list or add a structured
prompt recipe. If planning is blocked or the built-in tool is unavailable,
stop without a fallback.

## Local repository setup

The plugin cache intentionally does not contain a second copy of Alchemy V3.
When the plugin runs from a cached install, set the non-secret environment
variable `ALCHEMY_CODEX_LOCAL_REPO_ROOT` to the root of this checked-out
repository, then restart Codex. The launcher validates that path before it
imports anything. If it cannot find the repository, the MCP stays unavailable;
it never falls back to a Web route or Platform API.

## Provenance

Each plan is marked:

```text
execution_channel=codex_native_imagegen
renderer=codex_builtin_imagegen
delivery_state=conversation_only_not_certified
```

It cannot support a Provider Gate, General Gate D, Photography P10, or an
E-Commerce production gate.

Validate the plugin after manifest changes:

```powershell
python C:\Users\T14S\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
```
