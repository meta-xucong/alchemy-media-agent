# 107 V3 Shared Text-Pixel Runtime Implementation Handoff

Status: feature-branch handoff for mainline review. Production activation is
intentionally off.

Superseded for forward implementation by Doc111. Do not certify, enable, or
extend this deterministic compositor. It remains historical provenance only;
new text-bearing images must be generated and revised provider-natively.

Handoff snapshot: the dedicated branch is `codex/shared-text-pixel-runtime`.
Before handoff it was rebased in a Git-writable feature checkout onto
`origin/main` at `1c9b2541c1d9cb20c0abca37348b3fc63c5eaefd`. The mainline
integrator must fetch the branch and rebase it again if `origin/main` advances
before integration.

## Scope and ownership

This is V3 foundation work. It adds a scenario-neutral final-text delivery
stage; it does not add an E-Commerce platform, slot, suite, UI control, or
provider path to General Template. E-Commerce remains a future consumer that
maps its approved copy intent to the shared contract after mainline accepts it.

The implementation follows Doc104, Doc105 Sections 6–8, E12, and E13:

```text
internal template copy intent
-> frozen CapabilityActivationPlan
-> shared CopyRenderPlan binding
-> normal provider background and visual review
-> deterministic shared composition
-> final-pixel OCR/layout/policy review
-> one deterministic repair / one eligible existing shared retry signal
-> append-only derived-output and delivery metadata
```

## Changed shared interfaces

- `app/shared_capabilities/text_pixel/contracts.py`
  - `CopyRenderPlan`, normalized safe area, claim/text policy, and immutable
    source lineage.
  - A template may submit internal copy intent before the activation plan
    exists. `bind_to_frozen_plan()` creates the final plan before generation;
    the runtime refuses a plan whose frozen ID does not match.
  - `TextPixelDelivery` exposes only product-level status, policy, locale,
    output lineage, append-only attempts, recovery, and Gate C eligibility.
- `app/shared_capabilities/text_pixel/runtime.py`
  - Explicit licensed-font registry and hash provenance.
  - Pillow deterministic compositor that preserves the generated background
    outside the approved text layer.
  - Final-pixel `tesseract` adapter, OCR/layout/contrast/policy review, one
    same-background repair, and a bounded shared-generation retry signal only
    for an unresolved background-readability failure.
- Activation catalog, fallback, policies, and visual-plugin registry include
  `text_pixel_delivery` only when an internal copy plan is present. The plugin
  adds no prompt text and declares the frozen review/retry vocabulary only.
- `V3ProductApiService` binds the plan after planning, runs composition after
  normal post-generation review, reuses ordinary retry when eligible, and
  merges delivery records append-only. A failed retry preserves a prior passed
  text delivery.

Compatibility: jobs with no internal plan are unchanged. Historical jobs need
no migration and remain readable. The only new status for eligible jobs is a
`text_pixel_delivery` metadata object; `planned_only`, `blocked`, and
`requires_copy_correction` do not claim delivered text pixels.

## Internal intent envelope

The runtime deliberately does not add raw copy/font/OCR/retry controls to the
public Product API. A future template-owned mapper supplies this internal
envelope before planning:

```json
{
  "text_pixel_delivery_internal": {
    "copy_render_plan": {
      "expected_copy": "Approved headline",
      "locale": "en-US",
      "text_policy": "required",
      "normalized_safe_area": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.2},
      "layout_priority": "headline",
      "claim_review_state": "approved",
      "source_lineage": {"source_asset_id": "template-owned provenance"}
    }
  }
}
```

Only the presence boolean crosses the Brain boundary for activation intent; the
copy text stays in the internal envelope. Product API binds
`capability_activation_plan_id` after the existing planner freezes the job.

## Activation, fonts, and OCR

Defaults are deliberately safe:

```text
V3_TEXT_PIXEL_DELIVERY_ENABLED=false
V3_TEXT_PIXEL_DELIVERY_PRODUCTION_ENABLED=false
V3_TEXT_PIXEL_ALLOW_DEVELOPMENT_FONTS=false
```

Production needs a deployment-owned `V3_TEXT_PIXEL_FONT_MANIFEST_JSON` entry
with a stable font ID/version/path, supported locale list, license identifier,
expected SHA-256, and `production_approved=true`. No system font is silently
selected and no font asset or license assertion is bundled by this branch.

The supported contract locales are `en-US`, `zh-CN`, and `ru-RU`. They remain
blocked until the deployment manifest supplies a verified font with actual
glyph support. The final-pixel OCR adapter invokes `tesseract` on the derived
image path; missing executable/language data is an explicit non-delivery state,
not a metadata-only pass.

## Verification completed in this worktree

- Added `tests/test_v3_shared_text_pixel_runtime.py` covering frozen-plan
  binding, General isolation, gated-off Product API result, deterministic
  composition, actual derived-output lineage, final-pixel OCR adapter input,
  forbidden-text policy, claim/OCR correction, locale-font blocking, and one
  append-only deterministic repair.
- `compileall` passed for `alchemy_creative_agent_3_0/app` and tests.
- Direct assertion smoke checks passed for composition/review, repair,
  text-forbidden policy, OCR mismatch, frozen activation, Product API
  plan-binding, and gate-off delivery status.
- `git diff --check` passed.

The sandbox runtime has Pillow but no pytest, tesseract executable, tesseract
language data, or owner-approved Gate C product fixture. Therefore pytest and
real Provider Gate C have not been executed here. Production activation must
remain off.

## Mainline integration order

1. Fetch and inspect this feature branch, then rebase it onto the current
   `origin/main` if main has advanced since the recorded handoff base.
2. Review font-license source and deploy a verified font manifest plus
   tesseract and `eng`, `chi_sim`, and `rus` language data in an equivalent
   environment.
3. Run the new focused pytest suite, Doc102 activation tests, visual auto-retry
   tests, Product API tests, and the full V3 suite.
4. Supply owner-approved product references and execute Doc104 Gate C for the
   forbidden case, all three locales, repair, and provider failure. Retain
   terminal diagnostics and do not enable production until the evidence is
   accepted.
5. Announce the integrated main commit and stable result contract. Only then
   may the E-Commerce worktree map its D6 template-safe copy intent to this
   shared envelope.
