# Alchemy Lab Development Checklist

## Feature Scope

Alchemy Lab is a new experimental area.

rare-style-explorer is the first feature in Alchemy Lab.

The feature creates multiple image style variations for one user idea, then shows the results in a comparison grid.

## Required Documents

Read the Alchemy Lab documents in `docs/alchemy_lab/` before writing product code.

## Work Items

1. Add an Alchemy Lab entry point.
2. Add a rare-style-explorer feature page.
3. Add a style preset library.
4. Add a prompt composer.
5. Add a capped batch runner.
6. Reuse the existing image generation path.
7. Store exploration sessions.
8. Store generated variants.
9. Store final prompts.
10. Store favorites.
11. Render a comparison grid.
12. Add validation and tests.

## MVP Style Presets

- Cinematic
- Photorealistic
- Editorial
- Illustration
- Minimalist
- Cyberpunk
- Watercolor
- Retro poster

## Recommended Limits

- Maximum selected styles: 8
- Maximum images per style: 2
- Maximum total images: 12
- Maximum concurrent generations: 3

## Acceptance Checklist

- Lab entry exists.
- Explorer opens.
- Styles can be listed.
- A session can be created.
- Image generation uses the existing backend path.
- Results render in a grid.
- Prompts can be viewed.
- Favorites can be saved.
- Partial failures remain visible.
- Tests cover main behavior.
