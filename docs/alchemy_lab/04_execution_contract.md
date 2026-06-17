# Alchemy Lab Execution Contract: rare-style-explorer

## Purpose

This document defines how rare-style-explorer should run on the backend.

The key rule:

> rare-style-explorer orchestrates exploration. Existing Alchemy services should still handle prompt processing, model routing, image generation, asset persistence, auth, and shared error handling whenever those services already exist.

## Execution Shape

```text
one user idea
  -> selected style presets
  -> composed prompts
  -> batch generation
  -> stored variants
  -> comparison board
```

## Recommended MVP Path

Use direct service orchestration:

```text
Lab controller
  -> rare-style-explorer orchestrator
  -> existing prompt transformation
  -> existing image generation service
  -> existing asset storage
```

The agent layer can be added later for advanced prompt improvement, but it should not be required for the MVP.

## Backend Steps

### 1. Validate Request

Validate:

- Idea is not empty.
- Selected styles exist and are enabled.
- Batch size is within the server cap.
- Requested model and aspect ratio are supported.
- User is allowed to create images.

### 2. Create Session

Create a session before generation starts.

Initial status:

```text
queued
```

Store the original idea, normalized request, selected style snapshots, empty prompts, and empty variants.

### 3. Compose Prompts

For each selected style:

1. Start from the user idea.
2. Resolve style directives.
3. Use existing prompt transformation logic if available.
4. Create one final prompt.
5. Store the final prompt in the session.

### 4. Create Variant Jobs

For each composed prompt, create `imagesPerStyle` generation variants.

Each variant starts as:

```text
queued
```

### 5. Execute Batch

Run each variant through the existing generation service.

The Lab module should not create a separate generation backend when the existing application already has one.

### 6. Persist Results

For each successful variant, store the generated image using the existing asset system.

For each failed variant, store a friendly error code and message.

### 7. Finalize Session

Final status rules:

- `completed`: all variants succeeded.
- `partial_success`: some variants succeeded and some failed.
- `failed`: all variants failed.
- `cancelled`: the run was cancelled before completion.

Return a comparison board payload.

## Batch Limits

Recommended MVP defaults:

```text
maxSelectedStyles = 8
maxImagesPerStyle = 2
maxTotalImages = 12
maxConcurrentGenerations = 3
maxRetriesPerVariant = 1
```

The server must enforce these limits even if the UI validates them too.

## Retry Policy

Retry only recoverable failures.

Examples:

- temporary timeout
- temporary network interruption
- safe delayed retry after provider throttling

Do not retry validation failures or unsupported request formats.

## Partial Success Policy

Partial success is expected in batch generation.

The implementation must:

- keep successful variants
- keep failed variants
- show both in the UI
- avoid discarding the session when only some variants fail

A session should only be `failed` when no variant succeeds.

## Progress Reporting

Minimum acceptable MVP:

- The create request completes after the batch finishes.
- The response includes all variants and final status.

Preferred MVP:

- The create request returns a session id quickly.
- The UI polls session status.
- Completed variants appear as soon as they are ready.

Codex should choose the simplest option that matches the target codebase.

## Prompt Composition Format

Recommended prompt structure:

```text
Subject:
{user idea}

Style direction:
{style family, visual treatment, mood}

Image guidance:
{lighting, camera, composition, color palette, detail level}

Avoid:
{avoid list, if present}
```

If the existing prompt transformer expects a different shape, adapt this content into that shape.

## Storage Requirements

Persist enough data to inspect or replay a session:

- original idea
- normalized request
- selected style snapshots
- final prompts
- generation parameters
- asset references
- provider metadata when available
- errors
- favorites

## Observability Requirements

Where logging or tracing already exists, record:

- session id
- total variants requested
- selected style ids
- success count
- failure count
- latency

## Backend Done Criteria

Backend implementation is ready when:

- styles can be listed
- a valid exploration session can be created
- prompts are composed and persisted
- batch generation calls the existing generation path
- successful and failed variants are both represented
- favorites can be saved
- a comparison board payload can be returned
- server-side limits are enforced
