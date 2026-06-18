# Alchemy Lab Development Checklist

## Feature Scope

Alchemy Lab is a new experimental area.

rare-style-explorer is the first feature in Alchemy Lab.

The feature creates multiple rare sub-style image variations for one user idea, then shows the results in a comparison grid.

## Required Documents

Read the Alchemy Lab documents in `docs/alchemy_lab/` before writing product code.

## Work Items

1. Add an Alchemy Lab entry point.
2. Add a Lab home and make rare-style-explorer the first submodule.
3. Add the 620-entry rare style preset library with a small fallback subset.
4. Add a Lab-owned rare-style prompt composer.
5. Add a capped batch runner.
6. Reuse the existing image generation path.
7. Store exploration sessions.
8. Store generated variants.
9. Store final prompts.
10. Store favorites.
11. Render a comparison grid.
12. Add desktop dropdown and mobile module-card navigation.
13. Add validation and tests.
14. Add Lab-owned quality enhancement for rare-style prompts.
15. Add LLM-based Smart Text Hierarchy Planner for text-heavy image ideas.
16. Store quality-enhancement metadata in sessions, variants, and history.

## Rare Style Library

Use the 620-entry rare-style library as the primary product library. Expose the library with search, family filters, and collapsible lists so the interface stays simple. Keep the rewritten 8-style subset only as a fallback if the data asset cannot be loaded.

## Recommended Limits

- Maximum selected styles: 8
- Maximum images per style: 4
- Maximum total images: 12
- Maximum concurrent generations: 3
- Maximum generation interval: 60 seconds

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
- Quality enhancement is optional and Lab-owned, not a hidden V2 template-lock dependency.
- Text hierarchy for posters, packaging, menus, covers, invitations, signs, and similar text-heavy ideas is decided by LLM judgment, not fixed title/time/location formulas.
- Tests cover main behavior.
