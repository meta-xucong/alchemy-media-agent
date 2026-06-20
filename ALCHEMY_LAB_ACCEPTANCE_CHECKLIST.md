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
- Optional Lab-owned reference-image uploads can be created, stored, completed, and attached to rare-style-explorer sessions.
- Reference-image policy preserves uploaded subject/product/logo/material intent without overriding the selected rare style.
- Lab public history shows reference-image summaries without leaking source image URLs, asset ids, storage paths, filenames, or user account data.
- A Lab Intent Director reuses the existing Lab LLM JSON planning center instead of adding a separate provider SDK layer.
- Text-only and text-plus-reference requests both receive intent plans.
- Intent plans can guide automatic style-scope selection but cannot replace manually selected styles.
- Quality enhancement reads the intent plan so it refines the same constraints instead of inventing a separate direction.
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
- The UI exposes reference images as an optional collapsed control on desktop and a compact card flow on H5.
- The UI shows a concise, editable smart-intent summary for text-only and reference-image requests.
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
- Lab upload lifecycle test.
- Lab reference-image privacy and history-redaction test.
- Lab reference-image provider compatibility test.
- Lab Intent Director text-only test.
- Lab Intent Director reference-image test.
- Lab Intent Director manual-style-preservation test.
- V1/V2 isolation test.
- Partial success test.
- Comparison grouping test.
- Favorite persistence test.

## Ready for MVP

The module is ready when all checklist items above are satisfied and existing stable generation flows remain unchanged.
