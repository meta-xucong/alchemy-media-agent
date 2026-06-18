# Alchemy Lab Data Contract: rare-style-explorer

## Purpose

This document defines the implementation contract for the first Alchemy Lab feature module: **rare-style-explorer**.

The machine-readable schema lives in:

```text
specs/alchemy_lab/rare_style_explorer.schema.json
```

Codex should translate these contracts into the target repository's existing language, framework, and model conventions.

This repository uses snake_case for the API wire contract and Pydantic models. Conceptual names from upstream or product notes may be camelCase, but implementation payloads must follow the snake_case schema in this file.

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
- `display_name`
- `short_description`
- `family`
- `mode_affinity`
- `category`
- `tags`
- `prompt_directives`
- `is_beginner_default`
- `is_enabled`

`prompt_directives` should describe concrete rare visual traits such as style family, lighting, camera, composition, color palette, texture, medium, defect layer, and detail level. `negative_directives` stores anti-drift constraints.

The UI should display `display_name` and `short_description`, not raw prompt text.

## ExplorationRequest

The request sent when a user starts an exploration run.

Required fields:

- `idea`

Optional fields:

- `selected_style_ids`
- `target_count`
- `images_per_style`
- `generation_interval_seconds`
- `aspect_ratio`
- `mode`
- `style_family`
- `freshness`
- `seed`
- `style_id`
- `avoid_generic`
- `provider_preference`

`seed` enables repeatable automatic style sampling. `style_id` runs a single explicit style. `avoid_generic` keeps the upstream anti-generic de-duplication behavior enabled by default.

When no style is manually selected, `target_count` is the exact output count and the service normalizes `images_per_style` to `1`. When styles are manually selected, total output count is `selected_style_count * images_per_style`.

Validation rules:

- `idea` is required after trimming.
- If `selected_style_ids` is omitted or empty, the server automatically samples `target_count` enabled styles, optionally filtered by `style_family`.
- If style ids are supplied, at least one enabled style must resolve after optional family filtering.
- The total requested images must not exceed the server batch cap.
- The selected provider preference must be allowed by the existing generation service.

## ExplorationSession

The saved record for one experiment.

Required fields:

- `id`
- `feature`
- `status`
- `created_at`
- `updated_at`
- `request`
- `style_presets`
- `prompts`
- `variants`
- `favorites`
- `errors`

Status values:

```text
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
- `session_id`
- `style_preset_id`
- `style_preset_version`
- `idea`
- `final_prompt`
- `prompt_metadata`

The final prompt must be visible in the saved session and available to the UI behind a details toggle.

## GenerationVariant

One image generation attempt.

Required fields:

- `id`
- `session_id`
- `prompt_id`
- `style_preset_id`
- `index_within_style`
- `status`
- `created_at`

Optional fields:

- `asset`
- `provider_metadata`
- `error`
- `completed_at`

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

- `session_id`
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
GET  /api/lab/modules
GET  /api/lab/rare-style-explorer/styles
POST /api/lab/rare-style-explorer/sessions
GET  /api/lab/rare-style-explorer/sessions/:session_id
POST /api/lab/rare-style-explorer/sessions/:session_id/favorites
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
