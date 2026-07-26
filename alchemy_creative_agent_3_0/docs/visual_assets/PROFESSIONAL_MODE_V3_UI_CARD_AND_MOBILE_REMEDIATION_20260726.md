# Professional Mode V3 UI Card and Mobile Remediation

Status: implementation remediation contract.

Scope: V3 browser UI only. This document does not change Professional Mode backend contracts, Brain ownership, Provider routing, shared Vision review, retry, storage, M5, Gate C/D, or production gates.

## Problem statement

The Professional Mode Visual Asset Library had three user-facing defects:

1. In the desktop "建立和管理视觉资产" dialog, "查看资产内容" could appear to do nothing from a zero-knowledge user's point of view.
2. The "新建人物资产" shortcut behaved like a scroll-to-form action inside a long management dialog instead of an explicit card-style creation surface.
3. The mobile H5 V3 surface did not mirror the desktop Standard / Professional split, because `/h5` uses an independent mobile app shell.

## UX authority

Professional Mode must be discoverable but not accidental:

- Standard Mode remains the default.
- Professional Mode must be selected explicitly.
- Person keywords, uploaded portraits, or project text must not switch the user into Professional Mode automatically.
- Uploading a source image is not activation.
- Metadata-only, manual-only, draft, blocked, stale, or unreviewed asset states must not be displayed as usable Professional assets.
- The UI must not expose internal job IDs, hashes, provider payloads, HTML errors, or implementation diagnostics as ordinary user-facing guidance.

## Desktop remediation contract

The Visual Asset Library dialog is a card stack:

- Existing assets are one card.
- New People Asset creation is a separate expandable card.
- Character Card content opens as its own workspace card.
- Opening Character Card content must either show the selected asset's content or show a human-readable refresh/retry instruction; it must not silently no-op.
- The "新建人物资产" home shortcut opens the Visual Asset Library dialog directly in create-card mode and collapses the existing-assets card to reduce visual noise.

## Mobile remediation contract

The H5 app is not a CSS-only version of desktop; it has its own shell. Therefore it needs explicit Standard / Professional state and its own card surfaces.

Mobile V3 must provide:

- A two-option Standard / Professional switch matching desktop semantics.
- A Professional asset card area that appears only after explicit Professional selection.
- A "建立和管理视觉资产" bottom-card surface.
- A "新建人物资产" bottom-card surface.
- An "资产内容" bottom-card surface for status review, stage preparation, and explicit activation through the existing Character Card routes.
- Professional project creation provenance equivalent to desktop: `metadata.v3_workspace = "professional"`.

Mobile first release keeps Character Card generation and activation on the existing shared backend. The mobile detail card may invoke the existing `character-card/prepare` and `character-card/activate` routes, but it must not create a second private generator, reviewer, retry path, or storage path.

## Acceptance checklist

- Desktop "查看资产内容" opens Character Card content or shows a readable error.
- Desktop "新建人物资产" opens the creation card directly.
- Mobile V3 shows Standard / Professional choice.
- Mobile Professional mode shows Visual Asset management and People Asset creation as tap-first card surfaces.
- Mobile project creation carries Standard / Professional provenance without changing the selected template.
- Standard, General, E-Commerce, Photography, Provider, Brain, Review, Retry, and production gates remain unchanged.
