# Doc181 — V3 Shared Serial-Anchor Non-Face Review Closure

Status: active shared-foundation correction.

This document closes a review-contract gap in the Professional Character Card
Face Identity extension. It does not add a child, kidswear, Professional-only,
or scene-specific renderer path. It applies to any frozen serial identity pack
that intentionally requests a view in which some identity geometry is not
visible.

## 1. Problem and required outcome

The `rear_head` slot is a real identity-evidence view, but it intentionally does
not show a face. The shared Vision reviewer previously received the ordinary
face-comparison contract and could therefore turn “facial landmarks are not
visible” into a false identity failure or manual-review block.

For a frozen non-face view, the system must instead:

```text
frozen target viewpoint
→ Brain-owned serial capture direction
→ shared Vision review of evidence visible in that viewpoint
→ the same quality, realism, prompt-ownership, and parity gates
```

The system must not invent a facial score, manufacture a pass, or lower the
same-person gate for views where facial evidence is visible.

## 2. Evidence authority

The view role and serial lineage come only from the immutable activation plan
and its server-owned metadata projection. The review contract records:

- the target view role;
- whether a face is expected or not expected in that view;
- the number of prior approved winners in the serial chain;
- the subset of admitted prior winners actually supplied to Vision.

The root remains identity-only. Prior approved winners retain only the frozen
neutral-capture continuity authority assigned by the serial strategy. No local
prompt, keyword, regex, negative list, or scene recipe is created.

## 3. Rear-head review semantics

When `target_view_role=rear_head` and `target_face_visibility=not_expected`,
Vision must not fail or require manual confirmation solely because the face is
not detectable. It evaluates the visible evidence instead:

- head and hair mass, parting, length, and material realism;
- ears, neck, shoulder relationship, age/presentation coherence;
- requested viewpoint and neutral capture continuity;
- prompt-owned channel obedience, technical cleanliness, and human realism;
- absence of root-scene, wardrobe, or unrelated reference leakage.

Face-specific dimensions may be reported as not verifiable. Genuine defects
remain failures, including continuity drift, age/presentation drift, source
leakage, artificial rendering, prompt conflict, or technical artifacts.

## 4. Scope and non-regression

This is a shared review-contract correction. It does not change ordinary
portraits, visible-face views, Standard Mode, General, E-Commerce, Photography,
or the existing Vision/retry/final-winner architecture. Face Identity still
requires a reviewed winner for every requested slot, and production gates remain
closed until the complete real-pixel card passes.

## 5. Acceptance

1. Serial review context is present for `standard_front`, `three_quarter`,
   `profile`, `reverse_three_quarter`, and `rear_head` only when the frozen
   strategy and Professional quality contract are present.
2. Rear-head context explicitly marks facial visibility as not expected and
   supplies the admitted prior-winner subset without exceeding the review
   evidence budget.
3. Existing face-visible identity, Human Realism, parity, retry, and isolation
   tests remain green.
4. A real `rear_head` pixel may pass only after shared Vision returns a verified
   pass/warning and all existing server-side parity/localization checks pass.
