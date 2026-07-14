# Alchemy Codex Native ImageGen Mode

This isolated Doc118 plugin gives an interactive Codex agent one local stdio
MCP planning tool: `prepare_native_imagegen_plan`.  It does not create images,
open a listener, start a background worker, control Codex, or change Web Mode.

The flow is intentionally one-way:

```text
explicit user choice -> Codex -> local Alchemy planning MCP
-> Codex built-in image tool -> conversation-only image
```

The result is neither an Alchemy project output nor a certified delivery.  It
has no artifact import, candidate, review, retry, final-delivery, or
continuation surface.

## Input boundary

The planning tool accepts only user input, an explicit template ID, requested
count/size, and declarations about attachments already visible in the current
Codex conversation.  It never receives a file path, local artifact, project or
job ID, provider setting, capability envelope, or credential.

For every successful output, Codex uses the returned whole-image prompt and
hard constraints in exactly one built-in image-generation call.  If planning
is blocked or the built-in tool is unavailable, stop without a fallback.

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
