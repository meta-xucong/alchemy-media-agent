# Alchemy Codex Native ImageGen Mode

This isolated Docs130/131/133 plugin gives an interactive Codex agent two local
stdio MCP canonical-prompt tools: `prepare_native_imagegen_plan` and
`prepare_frozen_specialized_native_imagegen_plan`. It does not create
images, open a listener, start a background worker, control Codex, call an
image Provider, or change Web Mode. It does use the configured remote Central
Brain because an exact final Provider prompt cannot be created from a local
creative fallback.

The flow is intentionally one-way:

```text
explicit user choice -> Codex -> local Alchemy planning MCP
-> Codex built-in image tool -> conversation-only image
```

The result is neither an Alchemy project output nor a certified delivery.  It
has no artifact import, candidate, review, retry, final-delivery, or
continuation surface.

## Input boundary

`prepare_native_imagegen_plan` remains General-only. The separate
`prepare_frozen_specialized_native_imagegen_plan` accepts only explicit
`ecommerce_template` or `photographer_template` requests and relays their
normal required remote-Brain plan to the same materializer; it never downgrades
them to General. E-Commerce needs explicit factual platform evidence.
Photography accepts only an existing structural mode and a General Photography
binding; named profiles fail closed because Local MCP cannot manufacture the
Project/API immutable confirmation.

It accepts only user input, General, requested count/size, and explicit
`reference_inputs` (`channel` plus a user-authorized readable local
`file_path`). That file is passed into the ordinary V3 uploaded-asset contract
unchanged; V3 then returns the Web-admitted reference paths with the canonical
prompt.  A Codex conversation attachment is usable only when the host exposes
such a path. Otherwise the planner blocks safely: it never probes Codex
sessions/caches, imports a private artifact, or substitutes another image.
`portrait_identity`, `product_truth`, and `nonhuman_identity` remain hard
channels inside V3; callers cannot downgrade them.
One channel may contain multiple distinct user-authorized source files, such
as a product's front and back views. The MCP preserves those files in the
declared order and gives V3's ordinary admission/materialization path each
original path; it does not collapse them into a local recipe or substitute a
crop. Byte-identical files are one source and are transparently coalesced by
the shared Provider boundary, with declared/admitted counts retained.

For every successful output, Codex passes the returned `imagegen_prompt`
verbatim to exactly one built-in image-generation call. The MCP returns the
same final Unicode prompt and rendering parameters that Web Mode's Provider
would materialize for the same frozen V3 plan; its SHA-256 is the parity
receipt. Codex must not add a role, suite, camera, crop, keyword stack, or any
other text. If remote Brain planning, canonical materialization, admission, or
the built-in tool is unavailable, stop without a fallback.

Reference/image-to-image parity is described in Doc131. Codex must pass each
returned `reference_image_paths` list unchanged with the returned
`imagegen_prompt`. Text-to-image returns an empty list.

## Local repository setup

The plugin cache intentionally does not contain a second copy of Alchemy V3.
When the plugin runs from a cached install, set the non-secret environment
variable `ALCHEMY_CODEX_LOCAL_REPO_ROOT` to the root of this checked-out
repository, then restart Codex. The launcher validates that path before it
imports anything. If it cannot find the repository, the MCP stays unavailable;
it never falls back to a Web route or Platform API.

If the checked-out main worktree does not itself contain the already configured
remote Central Brain environment, set `ALCHEMY_CODEX_LOCAL_ENV_FILE` to that
existing local `.env` file. This configuration value is only a path; the
launcher loads it before V3 imports without copying keys into the plugin or
returning them through MCP. Existing process environment values take priority.

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
