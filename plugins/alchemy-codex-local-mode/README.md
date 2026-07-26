# Alchemy Codex Native ImageGen Mode

This isolated Docs130/131/133/183 plugin gives an interactive Codex agent the
legacy canonical-prompt tools `prepare_native_imagegen_plan`,
`prepare_frozen_specialized_native_imagegen_plan`, and
`prepare_frozen_professional_native_imagegen_plan`, plus the explicit
materialized tools `prepare_shared_mcp_materialization` and
`submit_shared_mcp_materialization`. The materialized tools read a V3-frozen
handoff and submit exactly one Codex built-in ImageGen artifact back into the
same V3 output, review, bounded-retry, winner, and Character Card slot path as
Web Provider. Neither surface calls a Platform API, reads Codex auth/session/
cache, or creates a private creative pipeline.

The legacy flow is intentionally conversation-only:

```text
explicit user choice -> Codex -> local Alchemy planning MCP
-> Codex built-in image tool -> conversation-only image
```

The result is neither an Alchemy project output nor a certified delivery.  It
has no artifact import, candidate, review, retry, final-delivery, or
continuation surface.

The opt-in materialized flow is resumable and shared:

```text
explicit MCP channel -> V3 freezes Brain-owned plan and handoff
-> Codex reads the exact prompt/reference/rendering contract
-> one built-in ImageGen call
-> MCP submits the artifact with nonce/hash checks
-> V3 shared output store -> Vision review/retry/winner
-> Character Card fixed slot after a verified winner
```

Provider and MCP are contract-equivalent and can be switched per attempt. The
prompt, reference hashes/order, rendering parameters, review rules, retry
budget, and slot writeback are shared. Independent stochastic renders are not
promised to be pixel-identical.

## Input boundary

`prepare_native_imagegen_plan` remains General-only. The separate
`prepare_frozen_specialized_native_imagegen_plan` accepts only explicit
`ecommerce_template` or `photographer_template` requests and relays their
normal required remote-Brain plan to the same materializer; it never downgrades
them to General. E-Commerce needs explicit factual platform evidence.
Photography accepts only an existing structural mode and a General Photography
binding; named profiles fail closed because Local MCP cannot manufacture the
Project/API immutable confirmation.

The General tool accepts user input, an explicit `general_template`, requested
count/size, and `reference_inputs` (`channel` plus a user-authorized readable
local `file_path`). The specialist relay accepts those shared inputs only
together with an explicit specialist template: E-Commerce provides its
platform evidence, while Photography provides its existing structural mode and
permitted profile binding. Both entries pass each source file into the ordinary
V3 uploaded-asset contract unchanged; V3 then returns the Web-admitted
reference paths with the canonical prompt. A Codex conversation attachment is
usable only when the host exposes such a path. Otherwise the planner blocks
safely: it never probes Codex sessions/caches, imports a private artifact, or
substitutes another image.
`portrait_identity`, `product_truth`, and `nonhuman_identity` remain hard
channels inside V3; callers cannot downgrade them.
One channel may contain multiple distinct user-authorized source files, such
as a product's front and back views. The MCP preserves those files in the
declared order and gives V3's ordinary admission/materialization path each
original path; it does not collapse them into a local recipe or substitute a
crop. Byte-identical files are one source and are transparently coalesced by
the shared Provider boundary, with declared/admitted counts retained.

The Professional relay is a separate explicit entry point. It accepts only
the existing template selectors, `project_id`, `people_asset_id`, bounded
active identity-view selectors, and the same reference declarations. The
embedding host must resolve those selectors to its server-owned active People
Asset/Face Identity binding; without that resolver the plugin fails closed.
Callers cannot provide a binding, pack version, job ID, provider metadata,
prompt, or storage handle. `selected_identity_reference` is an adapter-only
hard channel for the serial M5 chain and maps to the existing shared
face-reference role; it does not add a public capability.

For the Professional serial anchor-pack stages, the server-owned strategy
`serial_anchor_pack_root_reuse_v1` reuses one already-prepared root identity
anchor after the front stage. Three-quarter therefore receives root
view-conditioned geometry plus the front winner's feature-detail and
view-conditioned geometry; profile receives root view-conditioned geometry plus
the front and three-quarter winners' two derivatives each. This is the shared
Provider's bounded five-reference contract, not an extra image generation or a
caller-selected crop. Standard Mode and ordinary non-serial reference
requests retain their existing derivative behavior. A supplementary stage is
blocked before Provider dispatch if any required feature/pose evidence scope is
missing.

All stages in one serial sequence must reuse the exact same frozen
`user_input`; the stage selector and append-only reviewed-winner references are
the only moving inputs. Each result exposes `professional_serial_intent_sha256`
so the Codex host can compare the frozen intent before rendering. A mismatch is
non-counting and must stop rather than being repaired with local prompt text.

For every successful output, Codex passes the returned `imagegen_prompt`
verbatim to exactly one built-in image-generation call. The MCP returns the
same final Unicode prompt and rendering parameters that Web Mode's Provider
would materialize for the same frozen V3 plan; its SHA-256 is the parity
receipt. Codex must not add a role, suite, camera, crop, keyword stack, or any
other text. If remote Brain planning, canonical materialization, admission, or
the built-in tool is unavailable, stop without a fallback.

Reference/image-to-image parity is described in Doc131. Codex must pass each
returned `reference_image_paths` list unchanged with the returned
`imagegen_prompt`. Text-to-image returns an empty list. The host must also
record an exact renderer parity receipt (renderer, model, size, quality, and
format); a missing or mismatched field is blocked/non-counting evidence.

For a real Professional relay, the embedding host may start the MCP with an
explicit metadata-only catalog root, for example
`--professional-asset-catalog-root <catalog-root>`. This is process
configuration, never a request field, and it reads only the existing
People-Asset/Face-Identity metadata. Without it, the Professional relay
correctly fails closed.

For the installed plugin, set the non-secret
`ALCHEMY_CODEX_LOCAL_PROFESSIONAL_ASSET_CATALOG_ROOT` environment variable or
place that directory path in the repository's ignored
`.codex-local-professional-catalog-path` pointer file, then restart Codex. The
launcher validates that the directory exists and passes it only as process
configuration; no binding, pack record or image path becomes an MCP selector.

## Local repository setup

The plugin cache intentionally does not contain a second copy of Alchemy V3.
When the plugin runs from a cached install, set the non-secret environment
variable `ALCHEMY_CODEX_LOCAL_REPO_ROOT` to the root of this checked-out
repository, then restart Codex. The launcher validates that path before it
imports anything. If it cannot find the repository, the MCP stays unavailable;
it never falls back to a Web route or Platform API.

For materialized MCP handoff tools, the bridge uses either an explicit
`v3_base_url`, the non-secret `ALCHEMY_V3_BASE_URL`, or the local runtime
descriptor written by the currently running V3 service. The bridge intentionally
has no hidden default port: if no live local V3 runtime can be discovered, it
fails closed instead of silently calling an empty or stale process on a
historical port.

The runtime descriptor is disabled by default and is meant for loopback-bound
local/dev MCP discovery only. Start the V3 service with
`ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED=true`, or set an explicit
`ALCHEMY_V3_RUNTIME_DESCRIPTOR` path, when Codex should discover the active
local service automatically. If the service is bound to `0.0.0.0` or another
non-loopback host, the descriptor is not written and
`/api/v3/creative-agent/local-runtime` stays unavailable. The descriptor is
written atomically and contains a runtime identity plus the active Professional
visual-asset storage roots. The MCP bridge verifies the descriptor's
`base_url`, `runtime_id`, and visual-asset roots against
`/api/v3/creative-agent/local-runtime`; a stale descriptor that points at a
different healthy V3 process is rejected. `ALCHEMY_V3_PUBLIC_BASE_URL` is never
used as the local descriptor address.

V3 Professional visual-asset roots are anchored to the discovered application
root so a source checkout and the Docker `/app/app` module layout both resolve
storage under the directory that owns `.media_storage`. Existing local
`src_skeleton/.media_storage/v3_visual_assets` and
`src_skeleton/.media_storage/v3_visual_asset_library` directories remain
read-compatible when the new app-root V3 directory does not exist yet. The
older V1 `MEDIA_STORAGE_ROOT` behavior is intentionally unchanged. This fix
guarantees Visual Asset Library discovery and MCP runtime identity; it does
not broaden the V3 Product job store contract for explicitly relative
`MEDIA_STORAGE_ROOT`, which remains governed by the normal application
configuration and should be handled in a separate root-contract change if
cross-launch job-resume parity is required.

If the checked-out main worktree contains its already configured remote
Central Brain environment, the launcher discovers `.env` (and the legacy
`src_skeleton/.env`) inside that checkout automatically. If the environment
intentionally lives in another user-owned checkout, set
`ALCHEMY_CODEX_LOCAL_ENV_FILE` to that existing local `.env` file. This
configuration value is only a path; the launcher loads it before V3 imports
without copying keys into the plugin or returning them through MCP. Existing
process environment values take priority. A worktree may also contain the
ignored `.codex-local-env-path` pointer file with that path; it must contain a
path only, never credentials.

## Provenance

Each plan is marked:

```text
execution_channel=codex_native_imagegen
renderer=codex_builtin_imagegen
delivery_state=conversation_only_not_certified
```

It cannot support a Provider Gate, General Gate D, Photography P10,
E-Commerce production gate, or Professional M5 pixel certification.

For a materialized handoff, the safe public receipt contains only an opaque
`handoff_id`, nonce, canonical prompt/hash, admitted reference hashes, and the
rendering contract. A pending handoff is projected in V3 job/asset status and
can be resumed later. Submitting it never bypasses shared Vision review or
activates a Character Card. The artifact is consumed once, written through
the existing V3 output store, and can fill a fixed slot only after the normal
verified winner decision.

Validate the plugin after manifest changes:

```powershell
python C:\Users\T14S\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
```
