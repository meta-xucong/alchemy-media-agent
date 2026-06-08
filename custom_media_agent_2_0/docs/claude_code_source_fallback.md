# Claude Code Source Fallback

This document describes the V2 Claude Code routing strategy used by Custom Media Agent 2.0.

Core rule:

```text
Claude Code remains the creative brain.
Kimi is the primary Claude Code source.
When Kimi is unavailable, V2 re-invokes Claude Code with backup model sources.
```

## Why This Exists

V2 depends on Claude Code for creative orchestration. The app must not bypass Claude and continue with a deterministic creative fallback when Kimi is overloaded, out of quota, or slow.

The fallback path still calls `claude -p`. It only changes the temporary Claude Code source by injecting a backup base URL, token, and model queue for the failing checkpoint stage.

## Runtime Strategy

Primary path:

1. V2 starts a staged Claude checkpoint run through Claude Code.
2. The normal Claude Code user settings can keep using the primary Kimi model, for example `kimi-for-coding`.
3. Each stage has a soft boundary. If Kimi hits a retryable failure, V2 preserves checkpoint state and tries a shorter model fallback stage.

Fallback path:

1. V2 calls Claude Code again for the same checkpoint stage.
2. V2 passes `--model <fallback_model>` from the configured fallback queue.
3. V2 injects backup Anthropic-compatible credentials into the subprocess environment.
4. The fallback stage must still return compact schema-shaped JSON.
5. If a fallback model succeeds, its checkpoint is treated as a Claude Code checkpoint, not a local deterministic replacement.

## Configuration

Set these in the V2 service environment, not in committed files:

```bash
V2_CLAUDE_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_CHECKPOINT_ORCHESTRATOR_ENABLED=true
V2_CLAUDE_ORCHESTRATOR_MODEL=kimi-for-coding
V2_CLAUDE_ORCHESTRATOR_FALLBACK_BASE_URL=https://aiself.vip
V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN=<private fallback API key>
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MODELS=deepseek-v4-pro-260425,deepseek-v4-flash-260425,deepseek-v3-2-251201,doubao-seed-2-0-lite-260428,doubao-seed-2-0-lite-260215,doubao-seed-1-6-lite-251015,glm-4-7-251222,doubao-lite-128k-240428,doubao-lite-32k-240428,doubao-lite-4k-240328
V2_CLAUDE_ORCHESTRATOR_FALLBACK_MAX_MODELS_PER_STAGE=3
V2_CLAUDE_ORCHESTRATOR_FALLBACK_STAGE_TIMEOUT_SECONDS=25
```

The fallback token should be the API key whose upstream group allows Anthropic-compatible `/v1/messages` dispatch for the listed backup models.

## Important Claude Code Isolation Details

Claude Code can load user-level settings such as:

```text
~/.claude/settings.json
```

If that file contains a Kimi token, it can override a subprocess environment token and accidentally send backup-model requests to the Kimi group.

For backup stages, V2 therefore adds:

```text
--setting-sources project,local
```

This excludes user-level Claude settings for the fallback subprocess while keeping normal primary Claude Code usage unchanged.

## Authentication Variables

Claude Code versions differ in whether `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_API_KEY` is the strict auth path, especially under `--bare`.

For fallback stages V2 injects both:

```text
ANTHROPIC_AUTH_TOKEN=<fallback token>
ANTHROPIC_API_KEY=<fallback token>
```

This keeps the fallback source stable across Claude Code versions and gateway adapters.

## Reasoning Effort Guard

Desktop Codex or shell environments may contain variables such as:

```text
CLAUDE_CODE_EFFORT_LEVEL=max
```

Some Anthropic-compatible backup models reject the resulting `reasoning.effort=xhigh` request field. V2 removes effort-related inherited environment variables for fallback stages and does not pass `--effort` on those fallback calls.

This guard only applies to the backup source. The primary Kimi route keeps the normal configured Claude Code behavior.

## Retryable Failures

Fallback is attempted when the primary Claude stage reports retryable Claude/Kimi boundary failures, including:

```text
claude_soft_timeout
claude_timeout
claude_output_token_limit
claude_structured_output_retries_exhausted
kimi_context_canceled
kimi_sub2api_502
kimi_no_available_accounts
kimi_upstream_error
upstream_context_canceled
```

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
claude_orchestrator_fallback_base_url_configured=true
claude_orchestrator_fallback_auth_token_configured=true
```

For a live run, inspect the Claude workspace trace:

```text
.v2_data/claude_orchestrator_runs/<workspace_id>/orchestration_trace.json
```

Successful backup use looks like:

```json
{
  "stage": "intent",
  "status": "success",
  "provider": "claude-code-model-fallback",
  "model": "deepseek-v4-pro-260425"
}
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

