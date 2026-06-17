# Alchemy Lab Architecture: rare-style-explorer

## Architecture Goal

rare-style-explorer should be implemented as a thin exploration layer over the existing Alchemy backend.

The backend must reuse existing application services for prompt transformation, model routing, image generation, asset storage, and session persistence whenever those services exist.

The feature should not fork or duplicate the stable V1/V2 generation pipeline.

## High-Level Architecture

```text
Client UI
  |
  v
Alchemy Lab API / Controller
  |
  v
rare-style-explorer Orchestrator
  |
  +--> Style Library
  +--> Prompt Composer
  +--> Batch Controller
  |
  v
Existing Alchemy Generation Service
  |
  +--> Existing model router
  +--> Existing provider adapter
  +--> Existing asset storage
  |
  v
Exploration Session Store
  |
  v
Comparison Board View Model
```

## Component Responsibilities

### 1. Alchemy Lab Shell

The Lab shell is the parent feature area.

Responsibilities:

- Show available Lab modules.
- Route users into rare-style-explorer.
- Keep Lab features isolated from stable V1/V2 navigation.
- Provide a shared place for future experimental modules.

### 2. rare-style-explorer Orchestrator

The orchestrator owns one exploration session.

Responsibilities:

- Validate the exploration request.
- Resolve selected style presets.
- Ask the prompt composer to produce generation prompts.
- Create a batch job.
- Send generation requests through the existing generation service.
- Collect per-image results.
- Persist the session.
- Return a comparison board payload.

### 3. Style Library

The style library contains predefined style presets.

Responsibilities:

- Provide beginner-friendly style names.
- Store structured style descriptors.
- Make style presets stable and versioned.
- Avoid provider-specific wording in the public UI when possible.

A style preset is not just a text suffix. It should be a structured object with fields such as style family, lighting, camera, mood, texture, and negative constraints.

### 4. Prompt Composer

The prompt composer turns one user idea and one style preset into a generation prompt.

Responsibilities:

- Normalize the user idea.
- Merge style descriptors into the prompt.
- Use existing prompt transformation logic if available.
- Keep output prompt deterministic enough for replay.
- Preserve the original user idea in session state.

The composer must not hide the final prompt from the session record.

### 5. Batch Controller

The batch controller turns one exploration request into many generation calls.

Responsibilities:

- Enforce max batch size.
- Enforce max concurrency.
- Retry recoverable failures.
- Track per-item status.
- Support partial success.
- Return progress state to the UI when the runtime supports it.

### 6. Existing Generation Service Adapter

This adapter is only a binding layer from the Lab module into the existing generation system.

Responsibilities:

- Use the existing image generation service.
- Use existing provider selection rules.
- Use existing model configuration.
- Use existing asset persistence.
- Normalize the generation result into the Lab data contract.

Do not put provider SDK calls directly into rare-style-explorer unless there is no existing generation abstraction.

### 7. Exploration Session Store

The session store persists the experiment.

Responsibilities:

- Store request input.
- Store selected presets and versions.
- Store composed prompts.
- Store generation parameters.
- Store generated asset references.
- Store failures.
- Store favorite selections.

The first implementation may use the existing persistence mechanism. If no persistence layer exists yet, use the repository's standard lightweight persistence approach and keep the interface replaceable.

### 8. Comparison Board View Model

The comparison board is the UI-facing representation of a session.

Responsibilities:

- Group results by style.
- Show image cards in a stable order.
- Display style labels.
- Display prompt details on demand.
- Mark favorite items.
- Preserve failed items with readable error messages.

## Data Flow

```text
1. User submits idea and style selections.
2. API validates request.
3. Orchestrator creates an exploration session.
4. Style Library resolves selected presets.
5. Prompt Composer produces one prompt per style variation.
6. Batch Controller runs generation calls through the existing service.
7. Generation Service stores images as normal assets.
8. Orchestrator records result metadata.
9. API returns comparison board data.
10. UI renders the result grid.
```

## Integration Boundary

The rare-style-explorer module owns:

- Exploration-specific request and response contracts.
- Style preset definitions.
- Prompt composition rules for style exploration.
- Batch orchestration.
- Comparison board data shaping.

The existing Alchemy backend owns:

- Authentication and authorization.
- Provider credentials.
- Model routing.
- Image generation execution.
- Asset storage.
- Common error handling.
- Common tracing or telemetry.

## Recommended Repository Placement

Codex must adapt this to the actual implementation repository conventions.

Preferred conceptual placement:

```text
features/
  alchemy-lab/
    rare-style-explorer/
      style-library
      prompt-composer
      batch-controller
      session
      api
      ui
```

If the repository already has conventions such as `src/features`, `app`, `server`, `components`, or `modules`, follow the existing conventions instead of creating a conflicting structure.

## API Shape

The exact framework route names depend on the implementation repository.

Conceptual endpoints:

```text
GET  /lab/modules
GET  /lab/rare-style-explorer/styles
POST /lab/rare-style-explorer/sessions
GET  /lab/rare-style-explorer/sessions/:sessionId
POST /lab/rare-style-explorer/sessions/:sessionId/favorites
```

If the existing codebase uses RPC, server actions, or internal service methods instead of REST routes, implement the same logical operations using that pattern.

## Stability Rules

- Do not change V1/V2 generation behavior.
- Do not change existing provider defaults unless required by the existing service contract.
- Do not introduce duplicate auth/session systems.
- Do not add a new storage mechanism if existing asset/session storage can be reused.
- Do not hide batch failures.
- Do not allow unlimited batch size.

## Extension Points

The architecture should allow future additions:

- User-created style presets.
- Style mutation.
- Automatic ranking.
- Vision-model evaluation.
- Style embedding search.
- Saved style collections.
- Video exploration modules.
