# Professional Mode V3 UI Card and Mobile Remediation

Status: implementation remediation contract; post-`b2e0abd` audit addendum required before the next frontend code change.

Scope: V3 browser UI only. This document does not change Professional Mode backend contracts, Brain ownership, Provider routing, shared Vision review, retry, storage, M5, Gate C/D, or production gates.

## Problem statement

The Professional Mode Visual Asset Library had three user-facing defects:

1. In the desktop "建立和管理视觉资产" dialog, "查看资产内容" could appear to do nothing from a zero-knowledge user's point of view.
2. The "新建人物资产" shortcut behaved like a scroll-to-form action inside a long management dialog instead of an explicit card-style creation surface.
3. The mobile H5 V3 surface did not mirror the desktop Standard / Professional split, because `/h5` uses an independent mobile app shell.

The first card/mobile implementation (`b2e0abd`) kept the correct frontend-only
scope, but audit found five closure gaps that must be treated as blocking before
the remediation is accepted:

1. Desktop and mobile HTML still reference old cache-bust query strings after
   the JavaScript/CSS changes, so a browser can keep loading stale assets.
2. Mobile Character Card preparation silently writes `generation_channel:
   "provider"`, which can diverge from desktop Professional flow semantics.
3. Existing tests are mostly static string checks; they do not prove that the
   mobile card UI can actually open, switch modes, show details, create a card,
   and keep images visible.
4. Public error text may still render backend `detail.message` / `detail.code`
   directly. That must be proven safe before exposing it in the user-facing UI.
5. Slot display wording can drift between desktop and mobile if one side keys
   off raw `winner_selected` while the other keys off activation/formal proof.

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
- Current assets and archived/discarded assets are separated in the UI. Archive
  filtering is a view concern only; it must not delete catalog records, evidence,
  receipts, or old outputs.
- Opening Character Card content must either show the selected asset's content or show a human-readable refresh/retry instruction; it must not silently no-op.
- The "新建人物资产" home shortcut opens the Visual Asset Library dialog directly in create-card mode and collapses the existing-assets card to reduce visual noise.
- Professional home background project sync and thumbnail preloading must not
  leave a full-page loading overlay above the asset cards; the asset library and
  create card remain clickable while non-critical previews settle.
- Image enlargement must use a top-layer modal (`<dialog>` or equivalent
  browser top layer), so the large preview is above the asset dialog and cannot
  be hidden behind the page or another card.
- Expression thumbnails must use one fixed visual frame/aspect treatment. If a
  neutral/default image is shown as a reference convenience, it must be labelled
  as such and must not masquerade as a fresh formal Expression slot.

Hidden state is authoritative. Frontend CSS must include hard hidden semantics
for V3 asset and Character Card panels so card content cannot remain visible
because a class sets `display: grid`, `display: flex`, or another layout value.

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

Mobile must not silently force a generation route. The accepted direction for
this remediation is:

- Do not write `generation_channel` from mobile UI unless the user has an
  explicit route selector or the server has returned a trusted route choice for
  the current Professional action.
- For Character Card preparation, prefer omitting `generation_channel` and let
  the existing backend/default Professional contract decide, matching desktop.
- If a future mobile release intentionally supports Provider-only preparation,
  that must be declared as a product limitation and covered by a focused test.

This is a UI contract boundary, not a backend routing migration. Do not change
Provider/MCP/Brain routing, retry policy, generation budget, slot acceptance, or
storage from this frontend remediation.

## Resource version / cache-bust contract

Any frontend change that modifies `app.js`, `styles.css`, `mobile.js`, or mobile
CSS must update every corresponding `<script>` / `<link>` query version in the
HTML that serves it.

For the next remediation patch, use one new shared frontend version token across
all touched desktop and mobile assets, for example:

```text
20260726-v3-card-modal-remediation
```

Acceptance requires a real browser refresh check that confirms the loaded
network URLs include the new token for all changed JS/CSS resources. A test that
only checks source strings is not enough, because stale cached assets are the
actual user-visible blocker.

## User-visible status contract

Desktop and mobile must derive slot display text from the same proof hierarchy:

1. `activation_eligible === true` or `formal_completion_verified === true`
   means the slot can display as completed/available.
2. Raw `winner_selected` alone means the backend has selected a winner, but the
   UI must not imply full activation unless the formal/public proof says so.
3. Pending/reviewing/blocked states should be displayed from public-safe status
   summaries, not from private job, handoff, provider, path, hash, or raw receipt
   internals.

It is acceptable for a non-activated `winner_selected` slot to read as "待确认"
on mobile and "已完成" on desktop only if both labels are backed by the same
formal proof semantics. The long-term target is one shared UI helper so wording
cannot drift between shells.

## Public error safety contract

Friendly error text may use backend status categories, but it must not echo raw
backend diagnostics to ordinary users.

Forbidden in user-facing errors:

- job IDs, handoff IDs, candidate IDs, output IDs, artifact IDs;
- SHA/hash values;
- local or remote file paths;
- provider names, provider raw payloads, model payloads, stack traces, HTML
  errors, or internal route names;
- prompt text, negative prompt text, reference asset internals, or storage roots.

Allowed:

- short, user-actionable messages such as "暂时无法读取资产，请刷新后重试";
- safe public status categories such as `blocked`, `preparing`, `reviewing`, or
  `not available`;
- a non-private support code only if it is explicitly designed for public UI and
  cannot be joined back to a job/handoff/output record.

`friendlyError()` must sanitize `detail.message`, `detail.code`, and any nested
detail object before rendering. Tests must include at least one backend-like
error containing private-looking values and assert that none reach the DOM.

## Minimum browser smoke

After the cache-bust and route/error/status fixes, run one narrow browser smoke
against the already-running or explicitly started local frontend service. It
does not replace backend integration tests and must not create new generation
jobs.

The smoke must verify:

1. Standard / Professional mode switching works on desktop and mobile-sized
   viewport.
2. The Professional asset library opens as cards, not as a scroll-to-section
   pile.
3. Existing asset card opens; asset detail card opens; detail can be collapsed
   without losing the asset list state.
4. New People Asset card opens independently from existing assets.
5. Existing formal images are still visible and load with non-zero natural
   dimensions.
6. The image lightbox opens above the asset dialog and closes through backdrop,
   close button, and Escape without trapping the page.
7. Expression slots render with uniform image frames.
8. No internal IDs, paths, provider payload fragments, stack traces, or raw
   backend diagnostics appear in visible user-facing text.

## Implementation order

1. Update this document and keep the work frontend-only.
2. Fix cache-bust versions for every changed desktop/mobile JS/CSS resource.
3. Remove silent mobile `generation_channel: "provider"` injection unless an
   explicit route choice is present.
4. Harden card/dialog hidden state and top-layer image preview behavior.
5. Sanitize `friendlyError()` output and unify slot status wording semantics.
6. Add the narrow browser smoke plus focused static/DOM tests.
7. Run `node --check` for changed frontend scripts, focused frontend tests,
   `git diff --check`, and the browser smoke.
8. Commit only frontend files and focused frontend tests. Do not stage evidence,
   generated images, cache folders, backend code, generation code, Formal Core,
   receipts, slots, Provider/MCP/Brain routing, or storage changes.

## Rollback

Because this remediation is frontend-only, rollback is a single frontend commit
revert. It must not require catalog repair, receipt migration, slot rewrites,
image deletion, or Provider/MCP/Brain changes. If implementation discovers a
backend/public projection dependency, stop and write a separate backend owning
layer task instead of expanding this frontend patch.

## Acceptance checklist

- Desktop "查看资产内容" opens Character Card content or shows a readable error.
- Desktop "新建人物资产" opens the creation card directly.
- Mobile V3 shows Standard / Professional choice.
- Mobile Professional mode shows Visual Asset management and People Asset creation as tap-first card surfaces.
- Mobile project creation carries Standard / Professional provenance without changing the selected template.
- Desktop and mobile HTML cache-bust versions are updated for every changed
  JS/CSS resource, and browser network/runtime verification shows the new token.
- Mobile does not silently force Provider generation for Professional Character
  Card preparation.
- Browser smoke confirms card open/detail/create/lightbox/image display on
  desktop and mobile-sized viewport.
- Public error rendering does not leak job/handoff/output IDs, hashes, paths,
  provider payloads, prompt text, stack traces, or raw backend diagnostics.
- Desktop and mobile status labels use the same activation/formal-proof
  semantics rather than raw `winner_selected` alone.
- Standard, General, E-Commerce, Photography, Provider, Brain, Review, Retry, and production gates remain unchanged.
