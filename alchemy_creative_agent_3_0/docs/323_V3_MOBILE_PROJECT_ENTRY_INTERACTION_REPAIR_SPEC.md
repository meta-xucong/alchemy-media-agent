# Doc323 - V3 Mobile Project Entry And Interaction Repair

Status: implementation contract for reliable navigation from the V3 mobile
project list.

## 1. Objective and scope

Make a visible V3 project reachable from a phone without waiting for preview
images or guessing which part of a card is clickable. Keep the existing image
gallery available as a separate action.

This is a V3 mobile shell change. It does not change the project API, project
ownership rules, generation providers, review, or desktop behavior.

## 2. Correction model

The project catalog and its thumbnails have different jobs. The catalog is
enough to open a project; thumbnails only improve visual browsing. A full-screen
mask must therefore stop blocking input as soon as the project catalog has
rendered. Preview API latency, authenticated image loading, and image decoding
must not prevent navigation or scrolling.

The interaction contract is:

- Tap a project's title or descriptive text to open its project home directly.
- Tap the cover or the explicit “View images” action to open its image gallery.
- The gallery's “Open project home” action opens the same project, never a
  previously selected project.
- Compare project identifiers as normalized strings at the UI lookup boundary.
- If a project has no confirmed template, show its details in read-only mode.
  Do not inherit the previously selected template or submit a generation job.
- If a project disappeared from the current list, show a visible refresh hint;
  do not silently ignore the tap.

The delegated click handler must scope workspace switching to the actual
workspace buttons. The current workspace value is also mirrored on `body` for
styling, so matching any ancestor with that data attribute would consume every
project-card click before the project action is reached.

## 3. Relationship to Doc301

This document supersedes Doc301's mobile-only requirement that the home screen
remain masked until every first-page preview image settles. The mobile mask now
ends after the project catalog is available. Preview images remain progressive
and may finish loading afterward. Doc301's desktop behavior and its bounded
project/preview API contract are unchanged.

## 4. Acceptance

1. With the home preview request deliberately held open, the mobile project
   card is clickable and opens the correct project detail.
2. The project title/copy is a keyboard-accessible button for opening project
   detail.
3. The cover and “View images” action still open the gallery, and the gallery
   action opens the same project's detail.
4. A project without a confirmed template opens read-only detail; the compose
   entry is disabled and the generation function refuses to submit.
5. Mixed identifier representations resolve to the same project; missing IDs
   produce visible feedback.
6. Loading, pagination, and image preview behavior outside this navigation
   contract do not regress.
