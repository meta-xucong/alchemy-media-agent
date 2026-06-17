# Alchemy Lab UI Flow: rare-style-explorer

## UX Goal

rare-style-explorer must feel simple enough for a beginner.

The user should not need to understand prompt engineering, batch jobs, model routing, or style metadata.

The visible workflow should be:

```text
Describe idea
  -> choose styles
  -> generate variations
  -> compare results
  -> favorite the best ones
```

## Main Navigation

Add a product entry point named:

```text
Alchemy Lab
```

The Lab home lists experimental modules.

For MVP, show one module card:

```text
rare-style-explorer
Explore different image styles for one idea.
```

## Screen 1: Lab Home

### Purpose

Let the user choose a Lab module.

### Content

- Page title: `Alchemy Lab`
- Short description: `Try experimental AI creation workflows.`
- Module card: `rare-style-explorer`
- Button: `Open Explorer`

### Empty State

If the module is disabled:

```text
This Lab feature is not available yet.
```

## Screen 2: Explorer Setup

### Purpose

Collect the minimum input needed to run a style exploration.

### Required UI Sections

#### Idea Input

Label:

```text
What do you want to create?
```

Placeholder:

```text
Example: a futuristic city at night
```

Validation message:

```text
Please describe what you want to create.
```

#### Style Selection

Label:

```text
Choose styles to try
```

Default style cards:

- Cinematic
- Photorealistic
- Editorial
- Illustration
- Minimalist
- Cyberpunk
- Watercolor
- Retro poster

Each card should show:

- style name
- one-sentence description
- selected state

Beginner default:

- preselect 4 to 6 styles, or provide a `Select recommended styles` action

#### Basic Options

Keep options minimal:

- aspect ratio
- images per style

Default:

```text
Aspect ratio: existing default
Images per style: 1
```

#### Generation Button

Button text:

```text
Create style variations
```

Before submit, show a clear count:

```text
This will create 6 images.
```

## Screen 3: Progress

### Purpose

Show the batch is running without exposing technical details.

### Copy

```text
Creating your style variations...
```

If progress count is available:

```text
3 of 8 images ready
```

### Behavior

- Disable duplicate submit while running.
- Show partial image cards if supported.
- Keep the user on the same page unless the app already has a job-detail convention.

## Screen 4: Comparison Board

### Purpose

Help the user compare generated styles quickly.

### Layout

Use a responsive grid.

Each image card must show:

- image preview
- style label
- favorite button
- prompt details toggle
- error state if generation failed

### Card Actions

Primary action:

```text
Favorite
```

Secondary action:

```text
Show prompt
```

Optional actions if existing asset features support them:

- download
- reuse prompt
- send to editor
- generate more like this

These are not required for MVP.

## Screen 5: Prompt Details

Prompt details should be hidden by default.

When expanded, show:

- original idea
- style name
- final prompt
- generation settings if available

Use beginner-friendly framing:

```text
Prompt used for this image
```

## Screen 6: Session Detail

If the product supports saved sessions, show:

- session title or idea
- creation time
- selected styles
- result grid
- favorite selections
- failed variants

If the product does not yet have session pages, the MVP can keep the result board in memory after generation, but backend session persistence is still recommended.

## Error States

### Empty Idea

```text
Please describe what you want to create.
```

### Too Many Images

```text
That is too many images for one run. Try fewer styles or fewer images per style.
```

### Some Images Failed

```text
Some styles could not be generated, but your successful results are ready.
```

### All Images Failed

```text
We could not create images for this run. Please try again with a simpler idea or fewer styles.
```

## Loading and Disabled States

The generate button should be disabled when:

- idea is empty
- no style is selected
- generation is already running
- requested image count exceeds the limit

## Beginner Mode Rules

The default UI must avoid these terms:

- batch job
- prompt AST
- model route
- provider
- concurrency
- token budget

Use these terms instead:

- style variations
- image idea
- create
- compare
- favorite

## Advanced Controls

Advanced controls are optional and should be hidden for MVP.

Future advanced options:

- custom style text
- model selection
- seed
- style intensity
- prompt enhancement toggle
- retry failed only

## UI Done Criteria

The UI is ready when:

- users can open Alchemy Lab
- users can open rare-style-explorer
- users can enter an idea
- users can select styles
- users can see the generated image count before submitting
- users can generate variations
- users can compare results in a grid
- users can view prompts
- users can favorite results
- users can understand partial failures
