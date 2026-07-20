# Doc177 — Professional Visual Asset Hub and Project Binding UX

## Status and authority

This is the authoritative Professional Mode browser composition contract. It
supersedes earlier documents only where they placed a full People Asset form or
an uncollapsed asset inventory directly on the Professional home page. It does
not replace the Visual Asset Library, People Asset, Face Identity, frozen-plan,
canonical-prompt, shared Provider, review, retry, or activation contracts.

## Product model

Professional Mode is not a decorated version of Standard Mode. It gives a
user two related but distinct jobs:

```text
Build a reusable Visual Asset
    → explicitly activate a reviewed version
    → choose it for one or more Professional projects
    → each later job freezes the chosen asset version
```

Standard Mode remains exactly as it is. It does not acquire Visual Asset
controls, does not infer Professional Mode from keywords, and does not silently
fall back from a Professional asset choice.

## Home-page information architecture

The Professional home must be sparse and card-led, matching the progressive
disclosure used by V2 and Alchemy Lab:

1. **Visual Asset Library card** — shows a short count/status summary and two
   clear actions: `管理视觉资产` and `建立人物资产`. It never renders the full
   asset list or the complete creation form inline.
2. **Professional Projects** — keeps the familiar project creation and recent
   project rhythm. The only Professional-specific explanation is that an
   asset can be selected inside a project when continuity is needed.

The detailed library opens as an isolated workspace/dialog. It contains the
asset inventory and the complete `新建人物资产` flow: source selection,
thumbnail previews, preparation intent, consent, prepare/review/activate
status, and recovery actions. Uploading source material remains visibly
different from activating an asset.

## Project binding UX

Every Professional project exposes one compact, prominent **视觉资产** card in
its project overview. It states one of: no asset selected, active asset(s),
or action required. Its only primary action is `选择视觉资产` / `管理视觉资产`.
The detailed picker appears on demand rather than expanding a long library in
the project page.

For the first release the picker offers the active People Asset category. Its
layout and public contract are asset-type aware so later Product, Scene, and
Brand assets can be added as separate selections without redesigning the
project flow. It must not claim that multiple asset types are executable until
their corresponding runtime contracts exist.

Only explicitly confirmed active versions can be selected. Removing or
replacing a selection affects future jobs only; past jobs retain their frozen
lineage. Missing, archived, or incompatible bindings block clearly instead of
being converted into ordinary reference uploads or Standard Mode.

## Interaction and accessibility requirements

- Main pages contain short explanations, status summaries, and one obvious
  next action; complex forms are opened only by an explicit click.
- Detail work has a visible close/back action, busy protection, refresh-safe
  server readback, and human-readable errors without IDs, hashes, prompts, or
  Provider internals.
- File cards show selected filename, local thumbnail, primary/supplementary
  role, remove action, and a persistent explanation for malformed, duplicate,
  or over-budget selection.
- The People Asset form continuously states which of its four prerequisites
  remain incomplete: asset name, one or two source images, preparation intent,
  and usage confirmation. A submit with missing information must show the same
  explanation inline beside the action, not only as a remote toast or a silent
  non-action. A transport failure is likewise projected inline in plain
  language; no asset, upload, provider, or job internals are exposed.
- Desktop and 390/430-pixel mobile layouts have no horizontal overflow.

## Non-goals and safety boundaries

- No new Provider, Brain, review, retry, storage, prompt-building, or
  text/keyword inference path.
- No local semantic recipes or facial-description injection.
- No automatic asset activation, project binding, template switching, or
  Standard Mode fallback.
- No reclassification of ordinary V3 references as Visual Assets.

## Acceptance evidence

1. Standard home and standard project flow remain unchanged.
2. Professional home shows only the compact Asset Library card and Professional
   Project area; the full People Asset form is absent until the user opens the
   library workspace.
3. The library workspace supports a bounded one- or two-source People Asset
   flow, thumbnail/readback/removal, prepare, review status, and explicit
   activation.
4. Professional project summary, refresh, reopen, binding selection, removal,
   blocked state, and future-job version freezing all use the existing public
   APIs and remain fail-closed.
5. General, E-Commerce, and Photography do not show Professional asset controls
   unless the user explicitly enters Professional Mode and creates a
   Professional project.
6. Incomplete People Asset information produces a visible local explanation;
   complete information produces a clear ready-to-save state before any upload
   request is made.
