# Alchemy Lab Development Checklist

## Feature Scope

Alchemy Lab is a new experimental area.

rare-style-explorer is the first feature in Alchemy Lab.

The feature creates multiple rare sub-style image variations for one user idea, then shows the results in a comparison grid.

## Required Documents

Read the Alchemy Lab documents in `docs/alchemy_lab/` before writing product code.

## Work Items

1. Add an Alchemy Lab entry point.
2. Add a rare-style-explorer feature page.
3. Add a curated rare style preset library.
4. Add a Lab-owned rare-style prompt composer.
5. Add a capped batch runner.
6. Reuse the existing image generation path.
7. Store exploration sessions.
8. Store generated variants.
9. Store final prompts.
10. Store favorites.
11. Render a comparison grid.
12. Add validation and tests.

## MVP Rare Style Presets

- Sun-faded folk horror poster photography
- Chrome Y2K fashion editorial
- Pastel ceramic toy photography
- Overexposed tropical VHS travelogue
- Risograph botanical catalog
- Brutalist museum product plinth
- CRT pixel interface still life
- Hand-tinted archival portrait

These are rewritten MVP presets. Do not copy the upstream 620-entry library verbatim unless licensing or explicit permission is confirmed.

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
- Lab prompt composition does not default to V2 prompt transform or V2 template lock.
- Tests cover main behavior.
