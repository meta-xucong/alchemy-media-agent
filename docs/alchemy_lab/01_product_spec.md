# Alchemy Lab Product Spec: rare-style-explorer

## Feature Name

**rare-style-explorer**

## Parent Module

**Alchemy Lab**

## Short Description

rare-style-explorer helps users generate and compare multiple rare visual sub-styles for the same image idea.

It is designed for exploration, not final delivery. The user should be able to quickly discover which visual direction is most promising.

## Target Users

### Beginner Creator

A user who has an idea but does not know how to write strong image prompts.

They need simple presets, plain language, and visual comparison. The UI may use friendly labels, but the generated prompts must use concrete rare sub-style language rather than broad words alone.

### Designer or Operator

A user who needs to compare several directions before choosing one for production.

They need quick batch output, style labels, and prompt visibility.

### Developer or Power User

A user who wants reusable style presets and a session record that can be replayed.

They need structured data, reproducibility, and extension points.

## MVP User Journey

```text
Open Alchemy Lab
  -> choose rare-style-explorer
  -> describe image idea
  -> choose style presets
  -> click Generate
  -> compare results
  -> favorite one result
  -> save session
```

## MVP Screens

### 1. Lab Home

Shows available experimental modules.

For MVP, show one card:

```text
rare-style-explorer
Explore many visual styles for one idea.
```

### 2. Explorer Setup

The setup screen asks for:

- Image idea.
- Style preset selection.
- Optional aspect ratio.
- Optional number of images per style.

Default controls must be enough for a beginner.

### 3. Generation Progress

Shows progress with simple copy:

```text
Creating style variations...
3 of 8 finished
```

Partial results may be shown as soon as they are ready.

### 4. Comparison Board

Displays a grid of generated results.

Each card must show:

- Image preview.
- Style name.
- Status.
- Favorite action.
- Prompt details toggle.

### 5. Session Detail

Shows the saved exploration session with:

- Original idea.
- Selected styles.
- Generated prompts.
- Result assets.
- Favorite result.
- Errors, if any.

## Functional Requirements

### R-001: Lab Entry

The user can open Alchemy Lab from the product navigation.

### R-002: Feature Selection

The user can select rare-style-explorer from the Lab home.

### R-003: Idea Input

The user can enter a plain-language image idea.

Validation:

- Required.
- Trim whitespace.
- Minimum useful length should be enforced by the UI or API.
- Empty input must show a friendly error.

### R-004: Rare Style Presets

The user can choose from preset rare style directions.

The product should expose the upstream rare-style library as structured Alchemy presets. The current target library contains 620 styles grouped into 10 style families:

- film
- fashion
- product
- photography
- illustration
- graphic
- craft
- digital
- space
- material

Each preset must include:

- beginner display name
- one-sentence description
- style family
- mode affinity
- prompt directives
- negative or anti-drift directives

The UI must keep this large library clean by using search, family filters, and collapsible style lists. A small rewritten fallback subset may exist for recovery, but it is not the primary product experience.

### R-005: Batch Generation

The user can choose an exact total image count and a maximum number of images per style. If the total is not evenly divisible by the style count, the final used style receives the remainder.

The backend must enforce max batch size.

Recommended MVP defaults:

- `images_per_style`: 1
- `maxSelectedStyles`: 8
- `maxImagesPerStyle`: 4
- `maxTotalImages`: 12
- `target_count`: 4 when no manual style is selected
- `generation_interval_seconds`: 0 by default, capped at 60

### R-006: Existing Backend Reuse

The feature must use the existing generation path for actual image creation.

Do not call image provider SDKs directly from the Lab module if an existing generation service exists.

The Lab prompt composer is Lab-owned. It may call the existing generic image generation service, but it must not silently enter V2 template locking, V2 mode routing, V2 prompt transform, or V2 Claude creative orchestration.

### R-007: Prompt Transparency

Each generated result must expose the composed prompt used for that image.

The prompt can be hidden behind a toggle in the UI.

### R-008: Partial Success

A batch can finish with partial failures.

The UI must show successful images and failed cards separately.

A single failed style must not fail the whole session unless no image succeeds.

### R-009: Favorite Selection

The user can mark one or more results as favorite.

The system must persist this selection in the session record.

### R-010: Session Persistence

The system must persist enough information to replay or inspect an exploration session:

- Input idea.
- Style presets.
- Composed prompts.
- Generation parameters.
- Result asset references.
- Status and errors.
- Favorite selection.

## Beginner-Friendly Defaults

The UI should avoid exposing technical language by default.

Use:

- `Idea` instead of `Prompt`.
- `Style` instead of `Modifier Set`.
- `Create variations` instead of `Run batch job`.
- `Favorite` instead of `Select candidate`.

Advanced details can be available under a disclosure section.

## Cost and Safety Requirements

The MVP must prevent accidental high-cost usage.

Required controls:

- Server-side batch size cap.
- Server-side concurrency cap.
- Clear count before generation.
- Friendly error when the requested batch is too large.
- No API keys or provider secrets exposed to the client.

## Non-Goals for MVP

- Automatic image ranking.
- User feedback learning loop.
- Style crossover or mutation chains.
- Custom user-created style presets.
- Video support.
- Prompt marketplace.
- Real-time collaborative sessions.
- Direct provider SDK calls from the Lab module.

## Future Extensions

Potential future Alchemy Lab modules or rare-style-explorer upgrades:

- Style mutation engine.
- Style similarity search.
- Automatic ranking using vision models.
- User feedback loop.
- Prompt evolution across generations.
- Project-level style libraries.
- Brand kit aware style presets.
- Saved style collections.
