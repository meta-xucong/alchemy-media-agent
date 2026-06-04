# Claude Code Project Instructions

You are the control-plane orchestrator for the custom media generation agent platform.

Rules:
- Do not hardcode provider API keys.
- Do not place base64 image/video payloads in source files or logs.
- Keep provider adapters thin and covered by contract tests.
- Use OpenAI Agents SDK for runtime specialist agents.
- Use Claude Code subagents for review, adapter implementation, prompt curation, security, and eval work.
- For dangerous shell commands, ask for explicit approval.
- Preserve docs and OpenAPI spec when changing behavior.
