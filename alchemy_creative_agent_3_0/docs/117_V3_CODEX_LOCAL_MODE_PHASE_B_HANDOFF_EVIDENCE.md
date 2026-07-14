# Doc117 Phase B: Codex Local Artifact Handoff Evidence

> **Historical evidence, not an implementation mandate.**  The conclusion
> that Codex exposes no supported durable local image artifact remains valid.
> The former B2 Platform API workaround is retired and must not be enabled or
> merged.  This limitation no longer blocks the approved conversation-only
> workflow in Doc118,
> `118_V3_CODEX_NATIVE_IMAGEGEN_PROMPT_ORCHESTRATION_SPEC.md`: Alchemy returns
> a planning prompt and Codex renders it with its built-in image tool without
> any artifact import.

## Status

**Stopped — no supported durable artifact handoff is exposed by the current
Codex Desktop/CLI surface.**  This is a Phase B blocker, not a successful
local-image acceptance or a fallback authorization.

Doc117 Phase B2 later adds a separate official Platform API materialization
spike.  It does not change this conclusion about Codex Desktop artifact
handoff, and it is documented separately in
`117_V3_CODEX_LOCAL_MODE_PLATFORM_IMAGE_API_B2.md`.

Date checked: 2026-07-14 (Asia/Shanghai).  The check deliberately used only
public command help and the supported task tool contracts.  It did not read
Codex/ChatGPT authentication, session files, browser cookies, UI caches, or
provider configuration, and it did not start an interactive Codex run.

## Reproduction

From the repository worktree, the following read-only help commands were run:

```powershell
codex --help
codex mcp --help
codex exec --help
codex mcp-server --help
```

Observed public surface:

- `codex` and `codex exec` offer `--image <FILE>` as an **input** attachment.
- `codex exec --output-last-message <FILE>` writes the final agent message;
  its help does not expose a generated-image binary export, durable artifact
  handle, or a declared artifact provenance callback.
- `codex mcp` manages external MCP servers, and `codex mcp-server` is a stdio
  server surface.  Neither exposes an image-result file handoff contract.
- The Codex Desktop image-generation tool available to this task returns a
  conversation image result, not a documented adapter-readable local file or
  content-addressed artifact handle.  There is no supported tool parameter to
  nominate an Alchemy import destination.

The repository adapter's PNG fixture is intentionally synthetic unit-test
evidence only.  It is not a Codex Desktop image artifact and must not be
represented as the Phase B interactive validation.

## Decision

No interactive image-generation run was performed.  Starting one would yield
only a preview/result surface with no supported safe way to provide the
adapter a materialized file; turning that into a file by inspecting caches,
sessions, or undocumented UI state is prohibited by Doc117.

Consequently, Doc117 acceptance criterion 14.3 (a real supported artifact
handoff) is **not met**.  The added MCP adapter remains a Phase A contract and
file-import technical spike.  Imported records remain
`codex_local_development_evidence`, have
`certification_state=not_certified_phase_a_b`, and cannot become a shared
reviewed final delivery.

This work does not pass or contribute evidence to Web Provider Gate C/D,
General Gate D, Photography P10, or E-Commerce Gate C/D.

## Safe condition to resume Phase B

Resume only if a supported Codex Desktop/agent interface supplies one of the
following to the interactive MCP caller:

1. a durable local file path that the caller is explicitly authorized to read;
   or
2. an official artifact handle with a documented, local-only materialization
   method and provenance binding.

The mechanism must identify the artifact's actual origin without exporting
Codex credentials or reusing web Provider keys.  At that point, run one
rights-clear General job through the adapter, verify SHA-256/job/role binding
after reopen, then separately seek approval for Phase C shared review and
final-delivery integration.
