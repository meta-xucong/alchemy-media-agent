# Alchemy Lab Overview

## Status

This document is a pre-development specification for a new experimental module named **Alchemy Lab**.

The first Lab feature module is **rare-style-explorer**.

## Product Definition

**Alchemy Lab** is an experimental area inside the Alchemy product where new AI creation workflows can be added without changing the stable V1/V2 generation flows.

**rare-style-explorer** is the first Lab feature. It turns single image generation into a beginner-friendly style exploration workflow:

```text
one idea
  -> multiple style directions
  -> batch image generation
  -> visual comparison board
  -> save the best result
```

## Why This Module Exists

Current image generation flows usually optimize for one prompt and one result at a time. That is useful for direct generation, but weak for early creative exploration.

rare-style-explorer adds a search layer above the existing generation system. Instead of asking the model for one best image, it asks the system to sample several style directions and make the differences visible.

## Module Hierarchy

```text
Alchemy
└── Alchemy Lab
    └── rare-style-explorer
```

Alchemy Lab is the container for experimental features.

rare-style-explorer is one feature inside Lab.

## Core Principle

The Lab layer must reuse the existing Alchemy backend logic wherever possible.

It should wrap existing generation, prompt, model-routing, asset, and session logic. It should not create a parallel image-generation backend unless the implementation repository has no reusable abstraction.

## What rare-style-explorer Does

The feature provides a guided workflow:

1. The user enters a simple image idea.
2. The user selects several style presets.
3. The system composes one prompt per style preset.
4. The system runs a controlled batch generation job.
5. The UI displays a comparison grid.
6. The user can mark a favorite and save the exploration session.

## What It Does Not Do

The first version does not implement:

- A new image model provider.
- A replacement for V1/V2 generation.
- Automatic final artistic judgment.
- Full prompt evolution or reinforcement learning.
- Multi-round style mutation beyond preset-based variations.
- Video generation.

Those can be future Lab features.

## User Experience Goal

The module must be understandable to a beginner.

A beginner should only need to answer:

- What do you want to create?
- Which styles do you want to try?
- Which result do you like best?

Advanced controls can exist later, but they must not be required for the MVP.

## Success Criteria

The MVP is successful when a user can:

- Open Alchemy Lab.
- Start rare-style-explorer.
- Enter one image idea.
- Select at least two style presets.
- Generate a batch of images using the existing backend generation path.
- View all results in a grid with style labels.
- See the prompt used for each result.
- Mark one result as favorite.
- Reopen or inspect the saved exploration session.

## Relationship to the Existing System

Alchemy Lab should be implemented as a feature layer.

```text
Lab UI / API
  -> rare-style-explorer orchestration
  -> existing prompt transformation
  -> existing generation service
  -> existing provider routing
  -> existing asset persistence
```

The stable generation flows should remain unchanged.
