# Alchemy Lab Data Contract: rare-style-explorer

## Purpose

This document defines the implementation contract for the first Alchemy Lab feature module: **rare-style-explorer**.

The machine-readable schema lives in:

```text
specs/alchemy_lab/rare_style_explorer.schema.json
```

Codex should translate these contracts into the target repository's existing language, framework, and model conventions.

## Core Objects

The MVP uses these objects:

```text
StylePreset
ExplorationRequest
ExplorationSession
ComposedPrompt
GenerationVariant
ComparisonBoard
FavoriteSelection
ExplorationError
```

## StylePreset

A reusable visual direction.

Required fields:

- `id`
- `version`
- `displayName`
- `shortDescription`
- `category`
- `tags`
- `promptDirectives`
- `isBeginnerDefault`
- `isEnabled`

`promptDirectives` should describe visual traits such as style family, lighting, camera, composition, color palette, texture, mood, detail level, and avoid-list.

The UI should display `displayName` and `shortDescription`, not raw prompt text.

## ExplorationRequest

The request sent when a user starts an exploration run.

Required fields:

- `idea`
- `selectedStyleIds`

Optional fields:

- `imagesPerStyle`
- `aspectRatio`
- `modelId`
- `seed`
- `userControls`

Validation rules:

- `idea` is required after trimming.
- At least one enabled style must be selected.
- The total requested images must not exceed the server batch cap.
- The selected model must be allowed by the existing generation service.

## ExplorationSession

The saved record for one experiment.

Required fields:

- `id`
- `feature`
- `status`
- `createdAt`
- `updatedAt`
- `request`
- `stylePresets`
- `prompts`
- `variants`
- `favorites`
- `errors`

Status values:

```text
draft
queued
running
completed
partial_success
failed
cancelled
```

The session must snapshot selected style presets so old sessions stay explainable even after the style library changes.

## ComposedPrompt

The generated prompt for one style direction.

Required fields:

- `id`
- `sessionId`
- `stylePresetId`
- `stylePresetVersion`
- `idea`
- `finalPrompt`
- `promptMetadata`

The final prompt must be visible in the saved session and available to the UI behind a details toggle.

## GenerationVariant

One image generation attempt.

Required fields:

- `id`
- `sessionId`
- `promptId`
- `stylePresetId`
- `indexWithinStyle`
- `status`
- `createdAt`

Optional fields:

- `asset`
- `providerMetadata`
- `error`
- `completedAt`

Variant status values:

```text
queued
running
succeeded
failed
cancelled
```

## ComparisonBoard

The UI-facing view model.

Required fields:

- `sessionId`
- `status`
- `idea`
- `groups`
- `favorites`
- `errors`

Each group represents one style. Each card represents one generated variant.

The board must preserve failed variants so users can understand partial failures.

## API Contract Summary

Logical API operations:

```text
GET  /lab/modules
GET  /lab/rare-style-explorer/styles
POST /lab/rare-style-explorer/sessions
GET  /lab/rare-style-explorer/sessions/:sessionId
POST /lab/rare-style-explorer/sessions/:sessionId/favorites
```

If the implementation repository uses RPC, server actions, or internal service calls instead of REST, Codex should keep the same logical operations and adapt the transport.

## Compatibility Rule

Field names may be adapted to local conventions, but the implementation must retain these concepts:

- original idea
- selected style ids
- style preset snapshots
- composed prompts
- generated asset references
- per-variant status
- partial errors
- favorites
- session replay data
