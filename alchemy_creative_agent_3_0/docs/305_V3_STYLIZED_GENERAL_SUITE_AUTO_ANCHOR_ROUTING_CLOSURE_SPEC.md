# V3 Stylized General Suite Auto-Anchor Routing Closure

## 1. Scope and observed mismatch

This is a V3 foundation/reference-routing correction. It does not change the
General mode role contract, the Provider policy classifier, or the user prompt.

The controlled VPS run used the existing fictional editorial-cover project and
explicitly selected `selection_candidates` and `creative_exploration`. Both
Jobs reached the remote Brain and carried the requested mode override, but the
first Provider operation was unexpectedly `image_edit` with one historical
generated-cover reference. aiself returned the explicit upstream code
`content_policy_violation` before pixels were returned. No mode-quality result
could therefore be accepted.

The frozen Brain profile for this project said:

```text
subject entity: person
rendering_mode: stylized
stylization_scope: whole_image
```

## 2. Authority and correction model

Doc73 and Doc287 permit the automatic first-output identity chain only for a
multi-image human suite that is photoreal/non-stylized. The typed Brain task
profile is the authority for rendering intent. An illustrated or anime-styled
character is not a real-person identity suite and must not be routed through a
historical image-edit anchor merely because its entity type is `person` or
`character`.

The defect was in the Central Brain applicability predicate:

```text
person/character + count >= 2  -> auto anchor
```

It omitted the frozen rendering-intent gate:

```text
explicit whole-image stylization -> no automatic identity anchor
```

This explains the two VPS failures without changing the upstream policy
decision. The safe policy-blocked Jobs remain terminal evidence; they are not
retried or rewritten to evade aiself. After the fix, a stylized General suite
uses its Brain-signed prompt through the normal text-to-image route while its
mode role recipe remains available for Provider and review.

## 3. Minimal implementation

1. In `CentralCreativeBrain._is_human_identity_suite_context`, inspect the
   frozen `visual_task_profile.rendering_intent` when it is present.
2. Return false for an explicit non-photoreal/stylized rendering mode, and for
   whole-image stylization without a photoreal mode.
3. Preserve compatibility for older framework-only records that do not carry a
   rendering-intent field; their existing typed subject evidence continues to
   behave as before.
4. Add a regression proving that a typed stylized person profile keeps the
   automatic-anchor policy disabled and sends no generated continuity reference
   to either output, while the existing photoreal test remains green.

## 4. Acceptance gates

- Focused Doc73 and mode-routing regressions pass.
- Provider materialization tests still prove mode role binding and canonical
  prompt ownership.
- Python compile and `git diff --check` pass.
- The VPS release contains the exact tested commit and remains healthy.
- The same safe project is rerun for all four General modes. A mode is accepted
  only when its requested role semantics, Provider operation, real pixels, and
  visual quality are all recorded. A provider policy block remains a scoped
  external non-pass, never a visual acceptance.

