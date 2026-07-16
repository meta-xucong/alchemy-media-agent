# Doc153 — V3 Shared Expression Authenticity Hard Gate

Status: implemented in the shared Brain and visual-review path; controlled pixel recheck pending.

## 1. Problem

Recent blue-dress comparisons show a recurring failure mode: the face can be
anatomically plausible and the skin can look photographic, while the same
camera-facing commercial smile appears across otherwise different images. This
is an AI-recognition problem, not merely a facial-artifact problem.

The prior contract correctly allowed smiles, but its phrase “explicit user
direction” was too broad. A request such as “gentle natural smile” expresses an
emotional goal; it does not authorize one fixed tooth, mouth, eye, or presenter
geometry.

## 2. Shared rule

The Remote Brain remains the only author of the complete renderer prompt.

The shared semantic interpretation is:

- Generic affect language such as “smile”, “joyful”, “pleasant”, or “friendly”
  expresses the user's emotional intention.
- A concrete physical direction such as a broad open-mouth or tooth-showing
  smile is user-owned and must be respected.
- When the physical expression is not explicitly fixed, the Brain decides how
  the person is visibly present from attention, action, timing, and situation.
- A straight-on commercial frame must not automatically become an
  interchangeable presenter grin.

This is a meaning-level decision. It is not implemented as a child rule, a
smile vocabulary, a regular expression classifier, a negative-prompt list, or
local prompt concatenation.

## 3. Pixel gate and retry

The shared vision reviewer must distinguish “a real smile” from “a generic
presenter smile.” A smile remains valid when it is genuinely user-controlled or
belongs to the visible situation. If it is physically plausible but
interchangeable across unrelated people or situations, the reviewer returns
the existing generic `human_expression_context` evidence with
`retry_recommended`.

The existing bounded retry path then sends only normalized review evidence back
to the Remote Brain. The Brain rewrites the complete canonical prompt. No local
expression phrase, child-specific repair, or second review/retry implementation
is introduced.

If the reviewer cannot certify the expression or the retry remains unresolved,
the ordinary shared withholding/manual-review rules apply. A visually plausible
image is not automatically a certified image.

## 4. Compatibility and scope

Historical fine-grained smile labels remain readable only through the existing
generic compatibility mapping. New enforced runs use the generic Human Realism
dimension. The rule applies to adult portraits, children, fashion, lifestyle,
product-on-person, and photography scenes alike.

Local MCP consumes the same Brain-signed canonical prompt and reference
binding. Its conversation-only result can validate prompt parity and visual
direction, but does not certify Web Provider delivery or production quality.

## 5. Acceptance matrix

The implementation must preserve these distinctions:

1. Generic “natural smile” may produce a smile, but must not be interpreted as
   a fixed commercial tooth display.
2. Explicit physical tooth-showing or open-mouth smile requests remain valid
   user controls.
3. A generic camera-presentational smile is retryable
   `human_expression_context` evidence.
4. A situation-owned smile passes when the reviewer can relate it to the
   person's visible attention or action.
5. No test or implementation may introduce child/apparel prompt recipes,
   fixed expression alternatives, local negative prompts, or provider-specific
   expression handling.
