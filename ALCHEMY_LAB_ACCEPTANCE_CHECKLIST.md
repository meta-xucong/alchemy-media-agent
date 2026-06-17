# Alchemy Lab Acceptance Checklist

## Product

- Alchemy Lab appears as an experimental area.
- rare-style-explorer appears as the first Lab feature.
- A beginner can complete the flow without advanced settings.

## Backend

- Style presets can be listed.
- Invalid empty ideas are rejected.
- Total image count is capped.
- Prompt composition stores the final prompt.
- Batch generation supports partial success.
- Sessions store successful and failed variants.
- Favorites are saved.

## UI

- Setup screen asks for one image idea.
- Style selection uses friendly names.
- The create button shows the total image count.
- Results render in a grid.
- Each card shows style name.
- Each card can reveal the final prompt.
- Failed variants show friendly messages.
- Favorite state is visible.

## Tests

- Style list test.
- Request validation test.
- Batch size test.
- Prompt composer test.
- Partial success test.
- Comparison grouping test.
- Favorite persistence test.

## Ready for MVP

The module is ready when all checklist items above are satisfied and existing stable generation flows remain unchanged.
