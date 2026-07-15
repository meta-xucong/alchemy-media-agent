# Doc126: V3 Codex Native ImageGen Conversation-only Plugin

Status: isolated planning-only technical verification. This specification was
originally numbered Doc118 on its feature branch. The cumulative shared-runtime
correction series now owns Docs118–124 on mainline, so this document is
renumbered to Doc126 before integration. The old feature-branch Doc118 path is
superseded and must not be imported alongside the mainline Doc118 authority.

## Status and authority

**Phase N1 implemented as a developer-preview planning surface; not a Web
Provider, not a V3 delivery path, and not a production gate.**

This is the only approved local-Codex direction:

```text
explicit user choice in Codex
-> local Alchemy planning MCP
-> frozen whole-image direction and guardrails
-> Codex built-in ImageGen, one call per output
-> image remains in the Codex conversation
```

The product is intentionally separate from Web Mode. It does not use the
configured Web Central Brain or image gateway. Codex owns the built-in image
tool and its authentication; Alchemy never reads Codex authentication, a
browser session, cache, or an undocumented image handle.

## What Phase N1 provides

`prepare_native_imagegen_plan` is the sole MCP tool. It accepts only:

- user input;
- an explicit `general_template` choice;
- requested output count and size; and
- named reference channels plus whether their attachment exists in the current
  Codex conversation.

It invokes V3's planning-only path with a generation sentinel and a no-remote
Brain provider. Therefore it may reuse normalized intent, the activation
envelope, constraint ledger, and General's natural-language compilation, but
cannot create a production renderer, make a Web Brain call, or create a
candidate, output record, review, retry, or delivery.

Every successful plan is marked:

```text
execution_channel = codex_native_imagegen
renderer = codex_builtin_imagegen
delivery_state = conversation_only_not_certified
```

These values describe a prompt plan, never an image result. They cannot be
used for Provider Gate C/D, General Gate D, Photography P10, E-Commerce Gate
C/D, project continuation, or production readiness.

## Deliberate limits

1. **General only.** `ecommerce_template` and `photographer_template` return
   `codex_native_imagegen_template_not_enabled`. They must not fall back to
   General because their remote-Brain, role-count, profile, and reference
   contracts need a separate future design review.
2. **Conversation references are declarative.** The MCP never sees a path or
   image byte. It tells Codex to use the exact attached image in its native
   tool call. `portrait_identity`, `product_truth`, and `nonhuman_identity`
   are always hard channels; callers cannot send `required=false` to weaken
   them. Attachment quality and pixel fidelity remain non-certified until a
   supported artifact handoff exists.
3. **No structured prompt pile-up.** The returned `imagegen_prompt` is the
   whole-image direction. Constraint, text, and reference fields are
   accountable guardrails for Codex to preserve, not a recipe, keyword list,
   local overlay, or extra creative direction.
4. **Exact count or block.** The facade never silently truncates. A mismatch
   between requested count, frozen deliverables, or compilations is blocked.

## Rejected B2 route and historical marking

The following historical fork documents were incorrectly numbered Doc117 and
describe a rejected experiment. They were never imported into main and must
not be cherry-picked as runtime authority:

```text
origin/codex/codex-local-mode-spike@7afafa8
  117_V3_CODEX_LOCAL_MODE_PLUGIN_AND_MCP_EXECUTION_ADAPTER_SPEC.md
  117_V3_CODEX_LOCAL_MODE_PLATFORM_IMAGE_API_B2.md
  117_V3_CODEX_LOCAL_MODE_PHASE_B_HANDOFF_EVIDENCE.md
```

`Doc117` on main remains the real-reference Provider closure authority. B2's
independent Platform API key, `/v1/images/generations`, artifact import,
staging, candidate/delivery records, and old MCP render tools are withdrawn.
They must not be reintroduced under a compatibility name, hidden flag, or Web
fallback. Git history is sufficient for archival recovery.

## Plugin launch boundary

The plugin cache deliberately does not copy a second V3 source tree. The
plugin launcher resolves the repository as follows:

1. First use the non-secret `ALCHEMY_CODEX_LOCAL_REPO_ROOT` environment
   variable when present and validate that it is an Alchemy checkout.
2. Otherwise search parent directories only, which supports source-tree
   developer use.
3. If neither is valid, stop before importing V3. No HTTP, Web, API-key, or
   fallback route is attempted.

For a cached desktop-plugin installation, set that environment variable to the
checked-out repository root and restart Codex. The variable is a local path,
not a credential, and must not contain a token or an API key.

## N1 acceptance contract

- MCP `tools/list` exposes only `prepare_native_imagegen_plan`.
- The public schema rejects job IDs, paths, Provider metadata, credentials,
  raw envelopes, B2 keys, and a caller-controlled `required` flag.
- A General plan returns precisely the frozen requested count and no image
  bytes, file path, hash, candidate, review, retry, or delivery state.
- The launcher can run from a source tree or resolve an explicit repository
  path from a cached plugin installation; an invalid path fail-closes.
- Source scans prove active N1 code has no Platform API, Web Provider,
  browser/session/cache extraction, arbitrary artifact import, or Codex
  process-control path.
- The bundled Skill directs Codex to call native ImageGen once per returned
  output and to label the result conversation-only/non-certified.

## Deferred work

No future phase may claim image certification merely because Codex displayed an
image. A supported platform artifact handoff would require a new document and
separate review before any import, shared review/retry, project history, or
delivery work begins. E-Commerce and Photography native support are likewise
deferred until their stricter contracts can remain fail-closed.

Doc76, Docs93–96, Doc109, Doc113, Doc115, Doc116, and mainline Doc117 retain
their existing authority. When this document conflicts with a Web production
gate, the stricter Web gate wins.
