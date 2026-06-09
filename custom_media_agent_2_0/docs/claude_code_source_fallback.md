# Claude Code Source Routing

This document describes the V2 Claude Code source-routing strategy used by Custom Media Agent 2.0.

Core rule:

```text
Claude Code remains the creative brain.
Text-only orchestration uses the fast text source.
Uploaded-image / visual-understanding orchestration uses the multimodal source.
Kimi remains the fallback Claude Code source.
```

## Why This Exists

V2 depends on Claude Code for creative orchestration. The app must not bypass Claude and continue with a deterministic creative fallback when any upstream source is overloaded, out of quota, or slow.

Routing and fallback still call `claude -p`. V2 only changes the temporary Claude Code model and, for fallback, the injected Anthropic-compatible base URL/token for the failing checkpoint stage.

## Runtime Strategy

Primary routing:

1. V2 starts a staged Claude checkpoint run through Claude Code.
2. Text-only requests use `V2_CLAUDE_ORCHESTRATOR_MODEL`, currently `deepseek-v4-pro-260425`.
3. Requests with uploaded assets that require visual understanding or hard input-image preservation use `V2_CLAUDE_ORCHESTRATOR_MULTIMODAL_MODEL`, currently `doubao-seed-2-0-lite-260428`.
4. V2 writes `claude_source_selection.json` into the Claude workspace, so every checkpoint stage and single-stage call uses the same selected source for that request.
5. A stage soft timeout first triggers shorter compression/retry stages on the same selected source.
6. If the selected source is unavailable, returns an upstream/API boundary error, or still cannot produce a valid checkpoint after compression retries, V2 preserves checkpoint state and tries the fallback source.

Current production intent:

```text
text source: deepseek-v4-pro-260425
multimodal source: doubao-seed-2-0-lite-260428
fallback source: kimi-for-coding
```

DeepSeek is used for fast text reasoning. Doubao is used when uploaded images, products, copy, QR codes, logos, faces, or required backgrounds must be understood. Kimi remains the conservative fallback.

## Configuration

Set these in the V2 service environment, not in committed files:

```bash
V2_CLAUDE_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_ORCHESTRATOR_MODEL=deepseek-v4-pro-260425
V2_CLAUDE_ORCHESTRATOR_MULTIMODAL_MODEL=doubao-seed-2-0-lite-260428
V2_CLAUDE_ORCHESTRATOR_FALLBACK_BASE_URL=https://aiself.vip
V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN=<private fallback API key>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODELS=kimi-for-coding
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MAX_MODELS_PER_STAGE=1
V2_CLAUDE_ORCHESTRATOR_FALLBACK_STAGE_TIMEOUT_SECONDS=120
```

The primary token should allow Anthropic-compatible `/v1/messages` dispatch for the text and multimodal models. The fallback token should allow `kimi-for-coding`.

## Source Selection

V2 keeps text tasks on the text model when there are no uploaded assets or provider input images.

V2 selects the multimodal model when the request or asset policy indicates visual understanding, including:

```text
provider input images are required
subject / product / logo / face / required background references
uploaded poster, menu, screenshot, QR, copy, offer, price, package, or food/product information
logo-on-surface bindings
composite content sources that must preserve business-critical information
```

The selected template still controls the frame. Uploaded assets fill replaceable slots and stay as provider input images when required.

## Claude Code Isolation

Claude Code can load user-level settings such as:

```text
~/.claude/settings.json
```

If that file contains another token, it can override a subprocess environment token and send requests to the wrong upstream group.

For external primary sources and fallback stages, V2 adds:

```text
--setting-sources project,local
```

This keeps source selection controlled by the V2 runtime environment and workspace routing file.

## Authentication Variables

Claude Code versions differ in whether `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_API_KEY` is the strict auth path, especially under `--bare`.

For fallback stages V2 injects both:

```text
ANTHROPIC_AUTH_TOKEN=<fallback token>
ANTHROPIC_API_KEY=<fallback token>
```

This keeps the fallback source stable across Claude Code versions and gateway adapters.

## Reasoning Effort Guard

Some Anthropic-compatible non-Claude models reject `reasoning.effort` request fields. V2 removes effort-related inherited environment variables and does not pass `--effort` for external primary sources and fallback stages.

This keeps DeepSeek/Doubao compatible with Claude Code while preserving compact schema-shaped output.

## Retryable Failures

Immediate fallback is attempted when the selected Claude source reports availability failures, including:

```text
claude_api_error
kimi_context_canceled
kimi_sub2api_502
kimi_no_available_accounts
kimi_upstream_error
upstream_context_canceled
```

Soft timeout, output-token-limit, hard timeout, and structured-output exhaustion are compression triggers first. If the selected source's micro/ultra-micro retries also exhaust without a valid checkpoint, the controller may try the fallback Claude Code model queue for that same compact stage.

The fallback is not a separate OpenAI-compatible executor. It is still Claude Code.

## Verification Checklist

Local or VPS checks:

```bash
curl http://127.0.0.1:8020/api/v2/runtime/model-settings
curl http://127.0.0.1:8020/api/v2/orchestrator/status
```

Expected runtime flags:

```text
claude_orchestrator_enabled=true
claude_checkpoint_orchestrator_enabled=true
claude_orchestrator_model=deepseek-v4-pro-260425
claude_orchestrator_multimodal_model=doubao-seed-2-0-lite-260428
claude_orchestrator_fallback_base_url_configured=true
claude_orchestrator_fallback_auth_token_configured=true
```

For a live run, inspect:

```text
.v2_data/claude_orchestrator_runs/<workspace_id>/claude_source_selection.json
.v2_data/claude_orchestrator_runs/<workspace_id>/orchestration_trace.json
```

Text-only primary use:

```json
{"provider":"claude-code-primary","model":"deepseek-v4-pro-260425","source_reason":"default_text_primary"}
```

Uploaded-image primary use:

```json
{"provider":"claude-code-primary","model":"doubao-seed-2-0-lite-260428","source_reason":"provider_input_images_required"}
```

Successful fallback use:

```json
{"provider":"claude-code-model-fallback","model":"kimi-for-coding"}
```

## Security Rules

Do not commit:

```text
.env
.v2_data/
.v2_storage/
actual API keys
Claude user settings with tokens
```

Only commit code, docs, tests, and example environment keys without secret values.
