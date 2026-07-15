# Doc120 V3 Human Realism Rendering-Style and Object-Artwork Disambiguation

Status: historical corrective specification. Its narrow illustration-word
correction is superseded for new LLM-first work by Doc134's Brain-owned
`rendering_intent` and canonical Provider-prompt sign-off. It remains useful
only to interpret the original defect and older records. It does not create a
child, apparel, product, commerce, or General-template-specific prompt branch.

## 0. Observed defect

The shared Human Realism activation layer treated every occurrence of
`illustration` as a request for an illustrated whole image. A real-person
request can instead use that word as a reference-truth fact, such as a visible
surface print or its placement. The old lexical rule then suppressed Human
Realism even when the frozen enforced plan correctly required it for a visible
real person.

## 1. Corrected invariant

Rendering style and object facts are distinct channels:

1. An explicit request to render the person or the whole image as an anime,
   cartoon, manga, or illustration remains exempt from photoreal Human
   Realism.
2. An artwork word used with generic object-detail semantics -- for example
   placement, print, pattern, motif, surface, label, or cover -- is not a
   whole-image style request.
3. In the second case, normal visible-person evidence continues to activate
   the shared Human Realism rendering and review contract.

The rule is semantic and surface-neutral. It neither identifies a garment nor
adds a vertical-specific prompt fragment; it only prevents a product fact from
silently changing the requested rendering medium.

## 2. Boundaries

- Preserve the user's actual stylized art direction whenever it is explicit.
- Do not treat Human Realism as a right to overwrite an object's reference
  truth or prompt-owned styling channels.
- Do not infer a Provider policy decision from this correction. A no-pixel
  HTTP 400 remains operation-scoped and unattributed unless the Provider
  returns stronger evidence.

## 3. Required regression

The shared Human Photorealism regression must prove both sides of the
distinction:

- an explicitly illustrated person remains exempt; and
- a real person with an object that has a visible `front illustration
  placement` still receives Human Realism guidance.

## 4. Acceptance consequence

The previously recorded no-pixel jobs remain append-only evidence and are not
retroactively altered. A new controlled real request may be evaluated only
after this shared activation correction is present; it must retain General
Template routing, the authorized reference, the configured real Provider, and
the existing shared review/retry path.
