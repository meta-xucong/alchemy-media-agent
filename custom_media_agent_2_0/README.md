# Custom Media Agent 2.0

Independent v2 implementation package for the Alchemy creative image agent.

Current architecture note: V2 has evolved from the early OpenAI Agents SDK-first plan into a hybrid runtime:

```text
deterministic business pipeline
+ Claude Code creative orchestrator
+ pluggable model sources
+ SDK-compatible tool boundary
+ V2-native provider/storage/history/review
```

Claude Code remains the creative decision orchestrator; Kimi, Volcengine, DeepSeek, Doubao, and similar sources are model sources behind Claude Code, not independent default orchestrators. OpenAI Agents SDK remains a useful tool/planner/tracing boundary, but it is not the current end-to-end execution engine. The authoritative architecture baseline is:

- [Current Architecture](../custom_media_agent_2_0_docs/docs/00_CURRENT_ARCHITECTURE.md)

This package is intentionally separate from `custom_media_agent_docs/src_skeleton`. It exposes `/api/v2/*` only and uses v2-specific runtime, data, provider, and storage boundaries.

## Environment

Use the project-local virtual environment. Do not install v2 dependencies into the global Python environment; the global environment may contain unrelated packages such as `pptagent`.

```powershell
cd D:\AI\AlchemyOS\custom_media_agent_2_0
.\scripts\setup_venv.ps1
```

## Run

```powershell
cd D:\AI\AlchemyOS\custom_media_agent_2_0
.\scripts\run_dev.ps1
```

Run the production-style queue worker in a separate terminal:

```powershell
cd D:\AI\AlchemyOS\custom_media_agent_2_0
.\scripts\run_worker.ps1
```

Run the provider sync worker separately when you want periodic GitHub update checks outside API startup:

```powershell
cd D:\AI\AlchemyOS\custom_media_agent_2_0
.\scripts\run_sync_worker.ps1
```

## Test

```powershell
cd D:\AI\AlchemyOS\custom_media_agent_2_0
.\scripts\test.ps1
```

## Design Docs

- [Claude Checkpoint Orchestrator](docs/claude_checkpoint_orchestrator.md): staged Claude Code orchestration plan for automatic checkpoint compression and continuation without skipping Claude.

## MVP Scope

- `/api/v2/health`
- ResourceProvider manifest and sync for the EvoLinkAI GitHub case provider
- Structured PromptCase seed publishing
- Optional remote GitHub archive sync with canonical English `cases/*.md` parsing
- Local published case index cache in `.v2_data/case_index.json`
- Case search and template listing
- Creative run orchestration through a CreativeManager runtime boundary
- SQLite-backed async task queue with a standalone worker entry point
- Standalone ResourceProvider sync worker for periodic GitHub updates
- OpenAI Agents SDK-compatible function-tool boundary for case search, case detail, and prompt safety checks
- Safety decision, prompt plan, mock image job, output provenance, feedback
- Output review decisions with a VisualCriticAgent boundary for future vision/LLM review
- Deterministic main pipeline with optional external creative orchestration and SDK planning boundary

## Isolation

Default v2 namespaces:

- API prefix: `/api/v2`
- DB namespace: `alchemy_v2`
- Redis prefix: `alchemy:v2:`
- Object storage prefix: `v2/`
- Local data directory: `.v2_data`
- Local storage directory: `.v2_storage`

## Resource Sync

Seed sync is the default, so local development works without network access:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8020/api/v2/resource-providers/github_evolinkai_gpt_image_cases/sync?mode=seed"
```

Remote GitHub archive sync can be requested manually:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8020/api/v2/resource-providers/github_evolinkai_gpt_image_cases/sync?mode=remote"
```

`mode=auto` uses `V2_ENABLE_REMOTE_GITHUB_SYNC`; when it is false, auto resolves to seed. Successful sync writes the active case index to `.v2_data/case_index.json`. Failed remote sync keeps the previous active index.
