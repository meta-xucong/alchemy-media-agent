# Alchemy Lab Acceptance Checklist

## Product

- Alchemy Lab appears as an experimental area.
- rare-style-explorer appears as the first Lab feature.
- Desktop opens Lab submodules from an Alchemy Lab dropdown.
- Mobile opens Lab submodules from square module cards.
- A beginner can complete the flow without advanced settings.

## Backend

- Rare style presets can be listed.
- The style list exposes the 620-entry library and family/mode metadata.
- Invalid empty ideas are rejected.
- Total image count is capped.
- Generation interval is accepted and capped.
- Prompt composition stores the final prompt.
- Prompt composition uses rare-style grammar and anti-drift constraints.
- Optional quality enhancement can improve Lab prompts without changing V1/V2 generation defaults.
- Text-heavy ideas use an LLM Smart Text Hierarchy Planner instead of fixed poster slots or rule-based title/time/location extraction.
- Quality enhancement metadata is persisted with prompts and Lab history.
- Batch generation supports partial success.
- Sessions store successful and failed variants.
- Favorites are saved.
- Lab generation reuses the existing image generation service without changing V1/V2 behavior.

## UI

- Setup screen asks for one image idea.
- Style selection uses friendly names, search, and family filtering.
- The create button shows the total image count.
- The UI controls total image count, images per style, interval, mode, family, freshness, and seed.
- The UI exposes quality enhancement in a beginner-safe way.
- Results render in a grid.
- Each card shows style name.
- Each card can reveal the final prompt.
- Result details show whether quality enhancement and text hierarchy planning were applied.
- Failed variants show friendly messages.
- Favorite state is visible.

## Tests

- Rare style list test.
- Request validation test.
- Batch size test.
- Prompt composer test.
- Quality enhancement mode test.
- Smart text hierarchy planner test that proves there is no fixed title/time/location formula.
- V1/V2 isolation test.
- Partial success test.
- Comparison grouping test.
- Favorite persistence test.

## Ready for MVP

The module is ready when all checklist items above are satisfied and existing stable generation flows remain unchanged.
